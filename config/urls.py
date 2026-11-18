from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("report/", include("reporting.urls")),
    path("monitoring/", include("performance.urls")),
    path("lab11/", include("performance.urls", namespace="performance_legacy")),
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("api/", include("blog.api.urls")),
    path("api-auth/", include("rest_framework.urls")),   # браузердегі API-ға кіру
    path("", include("blog.urls")),
]

if settings.LAB11_TOOLBAR:
    urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
