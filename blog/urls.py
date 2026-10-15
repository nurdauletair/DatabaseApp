from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),

    # қабылдаулар (FBV)
    path("appointments/", views.appointment_list, name="appointment_list"),
    path("appointments/new/", views.appointment_create, name="appointment_create"),
    path("appointments/<int:pk>/", views.appointment_detail, name="appointment_detail"),
    path("appointments/<int:pk>/edit/", views.appointment_update, name="appointment_update"),
    path("appointments/<int:pk>/delete/", views.appointment_delete, name="appointment_delete"),

    # науқастар (CBV)
    path("patients/", views.PatientListView.as_view(), name="patient_list"),
    path("patients/new/", views.PatientCreateView.as_view(), name="patient_create"),
    path("patients/<int:pk>/", views.PatientDetailView.as_view(), name="patient_detail"),
    path("patients/<int:pk>/edit/", views.PatientUpdateView.as_view(), name="patient_update"),
    path("patients/<int:pk>/delete/", views.PatientDeleteView.as_view(), name="patient_delete"),

    # дәрігерлер (CBV)
    path("doctors/", views.DoctorListView.as_view(), name="doctor_list"),
    path("doctors/new/", views.DoctorCreateView.as_view(), name="doctor_create"),
    path("doctors/<int:pk>/", views.DoctorDetailView.as_view(), name="doctor_detail"),
    path("doctors/<int:pk>/edit/", views.DoctorUpdateView.as_view(), name="doctor_update"),
    path("doctors/<int:pk>/delete/", views.DoctorDeleteView.as_view(), name="doctor_delete"),
]
