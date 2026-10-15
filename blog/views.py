from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, ProtectedError, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView)

from .forms import (
    SORT_FIELDS, AppointmentFilterForm, AppointmentForm, DoctorForm, PatientForm)
from .models import Appointment, Doctor, Patient


# ============ Басты бет: қорытынды көрсеткіштер ============

def home(request):
    status_labels = dict(Appointment.Status.choices)
    by_status = [
        (status_labels[row["status"]], row["status"], row["n"])
        for row in Appointment.objects.values("status")
        .annotate(n=Count("id")).order_by("status")]
    context = {
        "n_doctors": Doctor.objects.count(),
        "n_patients": Patient.objects.count(),
        "totals": Appointment.objects.aggregate(
            n=Count("id"), sum_price=Sum("price"), avg_price=Avg("price")),
        "by_status": by_status,
        "top_doctors": Doctor.objects.annotate(
            n_appointments=Count("appointments")).order_by("-n_appointments", "full_name")[:5],
        "recent": Appointment.objects.select_related("doctor", "patient")
        .order_by("-date")[:5],
    }
    return render(request, "blog/home.html", context)


# ============ Қабылдаулар: функциялық көріністер (FBV) ============

def appointment_list(request):
    form = AppointmentFilterForm(request.GET)
    appointments = (Appointment.objects
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


def appointment_detail(request, pk):
    appointment = get_object_or_404(
        Appointment.objects.select_related("doctor", "patient")
        .prefetch_related("diagnoses"), pk=pk)
    return render(request, "blog/appointment_detail.html",
                  {"appointment": appointment})


def appointment_create(request):
    form = AppointmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()                                  # INSERT
        messages.success(request, "Қабылдау қосылды.")
        return redirect("appointment_list")          # PRG
    return render(request, "blog/appointment_form.html", {"form": form})


def appointment_update(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    form = AppointmentForm(request.POST or None, instance=appointment)
    if request.method == "POST" and form.is_valid():
        form.save()                                  # UPDATE, INSERT емес
        messages.success(request, "Өзгерістер сақталды.")
        return redirect("appointment_detail", pk=appointment.pk)
    return render(request, "blog/appointment_form.html",
                  {"form": form, "appointment": appointment})


def appointment_delete(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == "POST":                     # GET тек сұрайды
        appointment.delete()
        messages.success(request, f"«{appointment}» жойылды.")
        return redirect("appointment_list")
    return render(request, "blog/appointment_confirm_delete.html",
                  {"appointment": appointment})


# ============ Науқастар: класс көріністері (CBV) ============

class PatientListView(ListView):
    model = Patient
    context_object_name = "patients"
    paginate_by = 15

    def get_queryset(self):
        # annotate: қабылдау саны; prefetch: дәрігерлер (N+1 жоқ)
        patients = (Patient.objects
                    .annotate(n_appointments=Count("appointments"))
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


class PatientDetailView(DetailView):
    model = Patient
    context_object_name = "patient"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["appointments"] = (self.object.appointments
                               .select_related("doctor")
                               .prefetch_related("diagnoses"))
        ctx["doctors"] = self.object.doctors.all()
        return ctx


class PatientCreateView(CreateView):
    model = Patient
    form_class = PatientForm
    success_url = reverse_lazy("patient_list")

    def form_valid(self, form):
        messages.success(self.request, "Науқас қосылды.")
        return super().form_valid(form)


class PatientUpdateView(UpdateView):
    model = Patient
    form_class = PatientForm
    context_object_name = "patient"
    success_url = reverse_lazy("patient_list")

    def form_valid(self, form):
        messages.success(self.request, "Өзгерістер сақталды.")
        return super().form_valid(form)


class PatientDeleteView(DeleteView):
    model = Patient
    context_object_name = "patient"
    success_url = reverse_lazy("patient_list")

    def form_valid(self, form):
        messages.success(self.request, f"«{self.object}» жойылды.")
        return super().form_valid(form)


# ============ Дәрігерлер: класс көріністері (CBV) ============

class DoctorListView(ListView):
    model = Doctor
    context_object_name = "doctors"
    paginate_by = 12

    def get_queryset(self):
        doctors = Doctor.objects.annotate(
            n_appointments=Count("appointments"),
            avg_price=Avg("appointments__price")).order_by("full_name")
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


class DoctorDetailView(DetailView):
    model = Doctor
    context_object_name = "doctor"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        appointments = self.object.appointments
        ctx["stats"] = appointments.aggregate(n=Count("id"), avg_price=Avg("price"))
        ctx["appointments"] = (appointments.select_related("patient")
                               .prefetch_related("diagnoses")[:20])
        return ctx


class DoctorCreateView(CreateView):
    model = Doctor
    form_class = DoctorForm
    success_url = reverse_lazy("doctor_list")

    def form_valid(self, form):
        messages.success(self.request, "Дәрігер қосылды.")
        return super().form_valid(form)


class DoctorUpdateView(UpdateView):
    model = Doctor
    form_class = DoctorForm
    context_object_name = "doctor"
    success_url = reverse_lazy("doctor_list")

    def form_valid(self, form):
        messages.success(self.request, "Өзгерістер сақталды.")
        return super().form_valid(form)


class DoctorDeleteView(DeleteView):
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
