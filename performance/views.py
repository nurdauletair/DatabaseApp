from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .queries import slow_rows, optimized_rows


def lab_access(view):
    def checked(request, *args, **kwargs):
        if not settings.PERFORMANCE_LAB:
            raise Http404
        return view(request, *args, **kwargs)
    return login_required(permission_required("blog.view_appointment", raise_exception=True)(require_GET(checked)))


@lab_access
def slow(request):
    return render(request, "performance/list.html", {"appointments": slow_rows(request.user), "stage": "Бастапқы нұсқа", "slow": True})


@lab_access
def optimized(request):
    return render(request, "performance/list.html", {"appointments": optimized_rows(request.user), "stage": "N+1 түзетілген"})


@lab_access
def index(request):
    return render(request, "performance/index.html")


def _cached_content(request):
    from .cache import clinic_stats
    return render(request, "performance/list.html", {"appointments": optimized_rows(request.user),
                  "stage": "Кэш", "stats": clinic_stats(request.user)})


@lab_access
def cached(request):
    from django.views.decorators.cache import cache_page
    from django.views.decorators.vary import vary_on_cookie
    from django.utils.cache import patch_cache_control
    from .cache import scope_key
    # Authorization runs on EVERY request, before a response can be served from cache.
    # Revision, user, clinic permission and session cookie isolate cached results.
    response = cache_page(60, key_prefix="clinic:list:" + scope_key(request.user))(
        vary_on_cookie(_cached_content))(request)
    patch_cache_control(response, private=True)
    return response
