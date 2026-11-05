from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Avg, Count, ProtectedError, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView)
from django.views.decorators.http import require_POST

from .forms import (
    SORT_FIELDS, AppointmentFilterForm, AppointmentForm, BookingForm, DoctorForm, PatientForm)
from .access import (appointment_condition, check_appointment, check_clinical_changes,
                     visible_appointments, visible_patients)
from .models import Appointment, Doctor, Patient


# ============ Басты бет: қорытынды көрсеткіштер ============

@login_required
@permission_required("blog.view_appointment", raise_exception=True)
def home(request):
    appointments = visible_appointments(request.user, Appointment.objects.all())
    status_labels = dict(Appointment.Status.choices)
    by_status = [
        (status_labels[row["status"]], row["status"], row["n"])
        for row in appointments.values("status")
        .annotate(n=Count("id")).order_by("status")]
    context = {
        "n_doctors": Doctor.objects.count(),
        "n_patients": visible_patients(request.user, Patient.objects.all()).count(),
        "totals": appointments.aggregate(
            n=Count("id"), sum_price=Sum("price"), avg_price=Avg("price")),
        "by_status": by_status,
        "top_doctors": Doctor.objects.annotate(
            n_appointments=Count("appointments", filter=appointment_condition(request.user, "appointments__"))).order_by("-n_appointments", "full_name")[:5],
        "recent": appointments.select_related("doctor", "patient")
        .order_by("-date")[:5],
    }
    return render(request, "blog/home.html", context)


# ============ Қабылдаулар: функциялық көріністер (FBV) ============

@login_required
@permission_required("blog.view_appointment", raise_exception=True)
def appointment_list(request):
    form = AppointmentFilterForm(request.GET)
    appointments = (visible_appointments(request.user, Appointment.objects.all())
                    .select_related("doctor", "patient")
                    .prefetch_related("diagnoses"))
    sort = "-date"
    if form.is_valid():
        cd = form.cleaned_data
        if cd["q"]:
            appointments = appointments.filter(
                Q(patient__full_name__icontains=cd["q"])
                | Q(doctor__full_name__icontains=cd["q"]))
        if cd["status"]:
            appointments = appointments.filter(status=cd["status"])
        if cd["doctor"]:
            appointments = appointments.filter(doctor=cd["doctor"])
        sort = SORT_FIELDS.get(cd["sort"], "-date")
    appointments = appointments.order_by(sort, "-pk")

    # aggregate: сүзілген тізімнің қорытындысы
    stats = appointments.aggregate(
        total=Count("id"), avg_price=Avg("price"), sum_price=Sum("price"))
    page_obj = Paginator(appointments, 15).get_page(request.GET.get("page"))
    return render(request, "blog/appointment_list.html",
                  {"form": form, "page_obj": page_obj, "stats": stats})


@login_required
@permission_required("blog.view_appointment", raise_exception=True)
def appointment_detail(request, pk):
    appointment = get_object_or_404(
        Appointment.objects.select_related("doctor", "patient")
        .prefetch_related("diagnoses"), pk=pk)
    check_appointment(request.user, appointment)
    return render(request, "blog/appointment_detail.html",
                  {"appointment": appointment})


@login_required
@permission_required("blog.add_appointment", raise_exception=True)
def appointment_create(request):
    form = AppointmentForm(request.POST if request.method == "POST" else None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()                                  # INSERT
        messages.success(request, "Қабылдау қосылды.")
        return redirect("appointment_list")          # PRG
    return render(request, "blog/appointment_form.html", {"form": form})


@login_required
@permission_required("blog.change_appointment", raise_exception=True)
def appointment_update(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    check_appointment(request.user, appointment)
    # Keep original values: ModelForm validation mutates its instance.
    original = Appointment.objects.get(pk=pk)
    form = AppointmentForm(request.POST if request.method == "POST" else None, instance=appointment, user=request.user)
    if request.method == "POST" and form.is_valid():
        check_clinical_changes(request.user, original, form.cleaned_data)
        form.save()                                  # UPDATE, INSERT емес
        messages.success(request, "Өзгерістер сақталды.")
        return redirect("appointment_detail", pk=appointment.pk)
    return render(request, "blog/appointment_form.html",
                  {"form": form, "appointment": appointment})


@login_required
@permission_required("blog.delete_appointment", raise_exception=True)
def appointment_delete(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    check_appointment(request.user, appointment)
    if request.method == "POST":                     # GET тек сұрайды
        appointment.delete()
        messages.success(request, f"«{appointment}» жойылды.")
        return redirect("appointment_list")
    return render(request, "blog/appointment_confirm_delete.html",
                  {"appointment": appointment})


# ============ Науқастар: класс көріністері (CBV) ============

class PatientListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "blog.view_patient"
    model = Patient
    context_object_name = "patients"
    paginate_by = 15

    def get_queryset(self):
        # annotate: қабылдау саны; prefetch: дәрігерлер (N+1 жоқ)
        patients = (visible_patients(self.request.user, Patient.objects.all())
                    .annotate(n_appointments=Count("appointments", filter=appointment_condition(self.request.user, "appointments__"), distinct=True))
                    .prefetch_related("doctors")
                    .order_by("full_name"))   # annotate-тен кейін Meta.ordering жұмыс істемейді
        q = self.request.GET.get("q", "").strip()
        if q:
            patients = patients.filter(full_name__icontains=q)
        return patients

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "").strip()
        return ctx


class PatientDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "blog.view_patient"
    model = Patient
    context_object_name = "patient"

    def get_queryset(self):
        return visible_patients(self.request.user, super().get_queryset())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["appointments"] = (visible_appointments(self.request.user, self.object.appointments.all())
                               .select_related("doctor")
                               .prefetch_related("diagnoses"))
        ctx["doctors"] = self.object.doctors.all()
        return ctx


class PatientCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "blog.add_patient"
    model = Patient
    form_class = PatientForm
    success_url = reverse_lazy("patient_list")

    def form_valid(self, form):
        messages.success(self.request, "Науқас қосылды.")
        return super().form_valid(form)


class PatientUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "blog.change_patient"
    model = Patient
    form_class = PatientForm
    context_object_name = "patient"
    success_url = reverse_lazy("patient_list")

    def form_valid(self, form):
        messages.success(self.request, "Өзгерістер сақталды.")
        return super().form_valid(form)


class PatientDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "blog.delete_patient"
    model = Patient
    context_object_name = "patient"
    success_url = reverse_lazy("patient_list")

    def form_valid(self, form):
        messages.success(self.request, f"«{self.object}» жойылды.")
        return super().form_valid(form)


# ============ Дәрігерлер: класс көріністері (CBV) ============

class DoctorListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "blog.view_doctor"
    model = Doctor
    context_object_name = "doctors"
    paginate_by = 12

    def get_queryset(self):
        doctors = Doctor.objects.annotate(
            n_appointments=Count("appointments", filter=appointment_condition(self.request.user, "appointments__")),
            avg_price=Avg("appointments__price", filter=appointment_condition(self.request.user, "appointments__"))).order_by("full_name")
        specialty = self.request.GET.get("specialty", "")
        if specialty in Doctor.Specialty.values:
            doctors = doctors.filter(specialty=specialty)
        q = self.request.GET.get("q", "").strip()
        if q:
            doctors = doctors.filter(full_name__icontains=q)
        return doctors

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "").strip()
        ctx["specialty"] = self.request.GET.get("specialty", "")
        ctx["specialties"] = Doctor.Specialty.choices
        return ctx


class DoctorDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = "blog.view_doctor"
    model = Doctor
    context_object_name = "doctor"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        appointments = visible_appointments(self.request.user, self.object.appointments.all())
        ctx["stats"] = appointments.aggregate(n=Count("id"), avg_price=Avg("price"))
        ctx["appointments"] = (appointments.select_related("patient")
                               .prefetch_related("diagnoses")[:20])
        return ctx


class DoctorCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = "blog.add_doctor"
    model = Doctor
    form_class = DoctorForm
    success_url = reverse_lazy("doctor_list")

    def form_valid(self, form):
        messages.success(self.request, "Дәрігер қосылды.")
        return super().form_valid(form)


class DoctorUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = "blog.change_doctor"
    model = Doctor
    form_class = DoctorForm
    context_object_name = "doctor"
    success_url = reverse_lazy("doctor_list")

    def form_valid(self, form):
        messages.success(self.request, "Өзгерістер сақталды.")
        return super().form_valid(form)


class DoctorDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = "blog.delete_doctor"
    model = Doctor
    context_object_name = "doctor"
    success_url = reverse_lazy("doctor_list")

    def form_valid(self, form):
        # Appointment.doctor — PROTECT: қабылдауы бар дәрігерді өшіруге болмайды
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Бұл дәрігерде қабылдаулар бар: алдымен оларды жойыңыз.")
            return redirect("doctor_detail", pk=self.object.pk)
        messages.success(self.request, f"«{self.object}» жойылды.")
        return response


@login_required
@permission_required("blog.book_appointment", raise_exception=True)
def appointment_book(request):
    patient = get_object_or_404(Patient, user=request.user)
    form = BookingForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        appointment = form.save(commit=False)
        appointment.patient = patient
        appointment.save()
        messages.success(request, "Қабылдауға жазылдыңыз. Тіркеушінің растауын күтіңіз.")
        return redirect("appointment_detail", pk=appointment.pk)
    return render(request, "blog/appointment_book.html", {"form": form})


@login_required
@permission_required("blog.confirm_appointment", raise_exception=True)
@require_POST
def appointment_confirm(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    check_appointment(request.user, appointment)
    if appointment.status == Appointment.Status.PLANNED:
        appointment.status = Appointment.Status.CONFIRMED
        appointment.save(update_fields=["status"])
        messages.success(request, "Қабылдау расталды.")
    else:
        messages.error(request, "Тек жоспарланған қабылдауды растауға болады.")
    return redirect("appointment_detail", pk=pk)
