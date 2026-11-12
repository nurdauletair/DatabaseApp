from django.urls import path
from . import views

app_name = "performance"
urlpatterns = [path("", views.index, name="index"), path("cached/", views.cached, name="cached"), path("slow/", views.slow, name="slow"), path("optimized/", views.optimized, name="optimized")]
