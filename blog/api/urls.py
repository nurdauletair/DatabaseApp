from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register("doctors", views.DoctorViewSet, basename="doctor")
router.register("patients", views.PatientViewSet, basename="patient")
router.register("diagnoses", views.DiagnosisViewSet, basename="diagnosis")
router.register("appointments", views.AppointmentViewSet, basename="appointment")

urlpatterns = router.urls
