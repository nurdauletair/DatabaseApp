from django.db.models import Avg, Count, ProtectedError, Sum
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from blog.models import Appointment, Diagnosis, Doctor, Patient

from .serializers import (
    AppointmentSerializer, DiagnosisSerializer, DoctorSerializer,
    PatientSerializer)


class DoctorViewSet(viewsets.ModelViewSet):
    serializer_class = DoctorSerializer
    queryset = Doctor.objects.annotate(
        n_appointments=Count("appointments")).order_by("full_name")
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["full_name", "phone"]
    ordering_fields = ["full_name", "n_appointments"]

    def get_queryset(self):
        qs = super().get_queryset()
        specialty = self.request.query_params.get("specialty")
        return qs.filter(specialty=specialty) if specialty else qs

    def destroy(self, request, *args, **kwargs):
        # Appointment.doctor — PROTECT: 500 орнына түсінікті 409 қайтарамыз
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Бұл дәрігерде қабылдаулар бар: алдымен оларды жойыңыз."},
                status=status.HTTP_409_CONFLICT)


class PatientViewSet(viewsets.ModelViewSet):
    serializer_class = PatientSerializer
    queryset = (Patient.objects
                .annotate(n_appointments=Count("appointments"))
                .prefetch_related("doctors")          # N+1 жоқ
                .order_by("full_name"))
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["full_name"]
    ordering_fields = ["full_name", "birth_date", "n_appointments"]


class DiagnosisViewSet(viewsets.ModelViewSet):
    serializer_class = DiagnosisSerializer
    queryset = Diagnosis.objects.all()
    filter_backends = [SearchFilter]
    search_fields = ["name"]


class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    queryset = (Appointment.objects
                .select_related("doctor", "patient")   # ForeignKey -> JOIN
                .prefetch_related("diagnoses"))        # ManyToMany -> 2-ші сұраныс
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["patient__full_name", "doctor__full_name"]
    ordering_fields = ["date", "price", "duration"]
    ordering = ["-date"]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get("status") in Appointment.Status.values:
            qs = qs.filter(status=params["status"])
        if params.get("doctor", "").isdigit():
            qs = qs.filter(doctor_id=params["doctor"])
        return qs

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """aggregate + GROUP BY: жалпы қорытынды және күйлері бойынша."""
        totals = Appointment.objects.aggregate(
            total=Count("id"), sum_price=Sum("price"), avg_price=Avg("price"))
        by_status = {
            row["status"]: row["n"]
            for row in Appointment.objects.values("status").annotate(n=Count("id"))}
        return Response({**totals, "by_status": by_status})
