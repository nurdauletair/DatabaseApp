from datetime import timedelta
from time import perf_counter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from blog.access import manages_clinic
from .executor import reader_configured, run_readonly
from .forms import AskForm
from .guard import NoAnswer, ReportError, UnsafeSQL
from .llm import api_configured, ask_sql
from .models import QueryLog

EXAMPLE_QUESTIONS = (
    "Қабылдаулардың әр күйі бойынша саны қанша?",
    "Әр дәрігерде қанша қабылдау бар?",
    "Осы айдағы аяқталған қабылдаулардан түскен түсім қанша?",
)


def reserve_request(user, question):
    # A persistent per-user lock/count also works with multiple Django workers.
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        now = timezone.now()
        attempts = QueryLog.objects.filter(user=user).exclude(status=QueryLog.Status.UNAVAILABLE)
        if (attempts.filter(created_at__gte=now - timedelta(minutes=1)).count() >= settings.REPORT_REQUESTS_PER_MINUTE
                or attempts.filter(created_at__gte=now - timedelta(days=1)).count() >= settings.REPORT_REQUESTS_PER_DAY):
            raise ReportError("Сұраныс лимиті аяқталды. Біраз уақыттан кейін қайталаңыз.")
        return QueryLog.objects.create(user=user, question=question, model=settings.OPENAI_MODEL)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
@sensitive_post_parameters("question")
def report(request):
    if not request.user.is_active or not manages_clinic(request.user):
        raise PermissionDenied("Есептер тек әкімші мен тіркеушіге қолжетімді.")
    ready = api_configured() and reader_configured()
    form = AskForm(request.POST if request.method == "POST" else None)
    ctx = {"form": form, "ready": ready, "examples": EXAMPLE_QUESTIONS}
    if request.method == "POST" and form.is_valid():
        start = perf_counter()
        question = form.cleaned_data["question"]
        log = None
        try:
            if not ready:
                QueryLog.objects.create(user=request.user, question=question,
                    status=QueryLog.Status.UNAVAILABLE, error="Көмекші қосылмаған.")
                raise ReportError("Есеп көмекшісі әзірге қосылмаған. Әкімшіге хабарласыңыз.")
            log = reserve_request(request.user, question)
            answer = ask_sql(question)
            log.sql = answer.sql
            log.input_tokens, log.output_tokens = answer.input_tokens, answer.output_tokens
            cols, rows = run_readonly(answer.sql)
            ctx.update(sql=answer.sql, cols=cols, rows=rows, result=True, row_count=len(rows))
            log.status, log.row_count = QueryLog.Status.SUCCESS, len(rows)
        except (UnsafeSQL, NoAnswer) as error:
            ctx["error"] = str(error)
            if log:
                log.status, log.error = QueryLog.Status.REJECTED, str(error)
                log.sql = getattr(error, "sql", "")
        except ReportError as error:
            ctx["error"] = str(error)
            if log:
                log.status, log.error = QueryLog.Status.ERROR, str(error)
        except Exception:
            # Never render a DEBUG traceback containing provider/client internals.
            ctx["error"] = "Есепті дайындау мүмкін болмады. Әкімшіге хабарласыңыз."
            if log:
                log.status, log.error = QueryLog.Status.ERROR, ctx["error"]
        finally:
            if log:
                log.duration_ms = round((perf_counter() - start) * 1000)
                log.save(update_fields=["sql", "status", "error", "row_count", "duration_ms", "input_tokens", "output_tokens"])
    return render(request, "reporting/report.html", ctx)
