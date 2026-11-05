from django.db.models import Avg, Count, ProtectedError, Sum
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError

from blog.models import Appointment, Diagnosis, Doctor, Patient
from blog.access import (appointment_condition, check_clinical_changes,
                         visible_appointments, visible_patients)
from blog.permissions import ClinicModelPermissions
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied

from .serializers import (
    AppointmentSerializer, DiagnosisSerializer, DoctorSerializer,
    PatientSerializer)


class DoctorViewSet(viewsets.ModelViewSet):
    permission_classes = [ClinicModelPermissions]
    serializer_class = DoctorSerializer
    queryset = Doctor.objects.annotate(
        n_appointments=Count("appointments")).order_by("full_name")
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["full_name", "phone"]
    ordering_fields = ["full_name", "n_appointments"]

    def get_queryset(self):
        qs = super().get_queryset().annotate(n_appointments=Count(
            "appointments", filter=appointment_condition(self.request.user, "appointments__")))
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
    permission_classes = [ClinicModelPermissions]
    serializer_class = PatientSerializer
    queryset = (Patient.objects
                .annotate(n_appointments=Count("appointments"))
                .prefetch_related("doctors")          # N+1 жоқ
                .order_by("full_name"))
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["full_name"]
    ordering_fields = ["full_name", "birth_date", "n_appointments"]

    def get_queryset(self):
        return visible_patients(self.request.user, super().get_queryset()).annotate(
            n_appointments=Count("appointments", filter=appointment_condition(self.request.user, "appointments__"), distinct=True))


class DiagnosisViewSet(viewsets.ModelViewSet):
    permission_classes = [ClinicModelPermissions]
    serializer_class = DiagnosisSerializer
    queryset = Diagnosis.objects.all()
    filter_backends = [SearchFilter]
    search_fields = ["name"]


class AppointmentViewSet(viewsets.ModelViewSet):
    permission_classes = [ClinicModelPermissions]
    serializer_class = AppointmentSerializer
    queryset = (Appointment.objects
                .select_related("doctor", "patient")   # ForeignKey -> JOIN
                .prefetch_related("diagnoses"))        # ManyToMany -> 2-ші сұраныс
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["patient__full_name", "doctor__full_name"]
    ordering_fields = ["date", "price", "duration"]
    ordering = ["-date"]

    def get_queryset(self):
        qs = visible_appointments(self.request.user, super().get_queryset())
        params = self.request.query_params
        if params.get("status") in Appointment.Status.values:
            qs = qs.filter(status=params["status"])
        if params.get("doctor", "").isdigit():
            qs = qs.filter(doctor_id=params["doctor"])
        return qs

    def perform_update(self, serializer):
        try:
            check_clinical_changes(self.request.user, serializer.instance, serializer.validated_data)
        except DjangoPermissionDenied as exc:
            raise PermissionDenied(str(exc)) from exc
        serializer.save()

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        if not request.user.has_perm("blog.confirm_appointment"):
            raise PermissionDenied()
        appointment = self.get_object()
        if appointment.status != Appointment.Status.PLANNED:
            raise ValidationError({"status": "Тек жоспарланған қабылдауды растауға болады."})
        appointment.status = Appointment.Status.CONFIRMED
        appointment.save(update_fields=["status"])
        return Response(self.get_serializer(appointment).data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """aggregate + GROUP BY: жалпы қорытынды және күйлері бойынша."""
        qs = self.filter_queryset(self.get_queryset())
        totals = qs.aggregate(
            total=Count("id"), sum_price=Sum("price"), avg_price=Avg("price"))
        by_status = {
            row["status"]: row["n"]
            for row in qs.order_by().values("status").annotate(n=Count("id"))}
        return Response({**totals, "by_status": by_status})
