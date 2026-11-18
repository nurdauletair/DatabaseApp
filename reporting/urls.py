from django.urls import path
from .views import report

app_name = "reporting"
urlpatterns = [path("", report, name="report")]
