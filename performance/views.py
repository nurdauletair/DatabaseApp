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
