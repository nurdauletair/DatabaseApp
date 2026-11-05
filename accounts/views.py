from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.sessions.models import Session
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.cache import never_cache

from blog.models import Patient
from .forms import SignUpForm


@sensitive_post_parameters("password1", "password2")
def signup(request):
    if request.user.is_authenticated:
        return redirect("profile")
    form = SignUpForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            user.groups.add(Group.objects.get(name="patient"))
            Patient.objects.create(user=user, full_name=form.cleaned_data["full_name"],
                                   birth_date=form.cleaned_data["birth_date"])
        login(request, user)
        messages.success(request, "Тіркелу сәтті аяқталды. Емханаға қош келдіңіз!")
        return redirect("profile")
    return render(request, "registration/signup.html", {"form": form})


@login_required
@never_cache
def profile(request):
    request.session["visits"] = request.session.get("visits", 0) + 1
    return render(request, "registration/profile.html", {
        "visits": request.session["visits"],
        "session_key": request.session.session_key,
        "expiry": request.session.get_expiry_date(),
        "permissions": sorted(request.user.get_all_permissions()),
    })


@login_required
@require_POST
def logout_all(request):
    user_id = str(request.user.pk)
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        if session.get_decoded().get("_auth_user_id") == user_id:
            session.delete()
    logout(request)
    messages.success(request, "Барлық браузердегі сеанстар аяқталды.")
    return redirect("login")
