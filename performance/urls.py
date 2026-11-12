from django.urls import path
from . import views

app_name = "performance"
urlpatterns = [path("slow/", views.slow, name="slow")]
