"""6-ЗС: ORM арқылы оқу, жазу және оңтайландыру. Әр сұраныс — бөлек функция."""
from datetime import timedelta
from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Avg, Count, F, Max, Q
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from .models import Appointment, Diagnosis, Doctor, Patient


def show(title, qs):
    """Атауын және SQL-ді шығарады (print(qs.query))."""
    print(f"\n--- {title}")
    print(qs.query)
    return qs


def count_queries(func):
    """func() орындалғанда дерекқорға неше сұраныс кеткенін санайды."""
    with CaptureQueriesContext(connection) as ctx:
        func()
    return len(ctx)


# ============ 3-қадам. ОҚУ ============

def read_filter():
    # үтір = AND: жоспарланған және қымбат қабылдаулар
    return show("filter", Appointment.objects.filter(
        status=Appointment.Status.PLANNED, price__gte=5000))


def read_q():
    # Q: арзан НЕМЕСЕ ұзақ қабылдаулар
    return show("Q (OR)", Appointment.objects.filter(
        Q(price__lt=3000) | Q(duration__gt=45)))


def read_not_q():
    # ~Q: терапевттерден басқа дәрігерлердің қабылдаулары
    return show("~Q (NOT)", Appointment.objects.filter(
        ~Q(doctor__specialty=Doctor.Specialty.THERAPIST)))


def read_order():
    # баға кему, күн өсу ретімен, алғашқы 10
    return show("order_by", Appointment.objects.order_by("-price", "date")[:10])


def read_by_relation():
    # байланыс арқылы сүзу (JOIN): кардиологтардың қабылдаулары
    return show("doctor__specialty", Appointment.objects.filter(
        doctor__specialty=Doctor.Specialty.CARDIOLOGIST))


def read_aggregate():
    # aggregate: бір қорытынды сөздік
    result = Appointment.objects.aggregate(
        total=Count("id"), avg_price=Avg("price"), max_duration=Max("duration"))
    print("\n--- aggregate\n", result)
    return result


def read_annotate():
    # annotate: әр дәрігерге қабылдау саны
    return show("annotate", Doctor.objects.annotate(
        n=Count("appointments")).order_by("-n"))


def read_group_by():
    # values + annotate = GROUP BY: мамандық бойынша
    return show("GROUP BY", Doctor.objects.values("specialty").annotate(
        n=Count("appointments"), avg=Avg("appointments__price")
    ).order_by("specialty"))


def read_having():
    # annotate-тен кейін filter = HAVING: кемінде 5 қабылдауы барлар
    return show("HAVING", Doctor.objects.annotate(
        n=Count("appointments")).filter(n__gte=5))


# ============ 4-қадам. ЖАЗУ ============

def write_create():
    doctor = Doctor.objects.create(
        full_name="Тест Дәрігер", specialty=Doctor.Specialty.SURGEON)
    patient = Patient.objects.create(
        full_name="Тест Науқас", birth_date="1990-05-05")
    appointment = Appointment(
        doctor=doctor, patient=patient, price=Decimal("4000"), duration=30,
        date=timezone.now() + timedelta(days=1))
    appointment.save()  # INSERT
    print("\n--- create:", appointment)
    return appointment


def write_update(appointment):
    # F(): бағаны дерекқордың өзінде 10%-ға көтереміз (жарыс жағдайынсыз)
    Appointment.objects.filter(pk=appointment.pk).update(
        price=F("price") * Decimal("1.1"))
    appointment.refresh_from_db()
    print("--- update(F): жаңа баға =", appointment.price)


def write_set_tags(appointment):
    # ManyToMany: set() ескі байланыстарды ауыстырады
    d1, d2 = Diagnosis.objects.all()[:2]
    appointment.diagnoses.set([d1, d2])
    print("--- diagnoses.set:", list(appointment.diagnoses.all()))


def write_atomic():
    # atomic(): блок ішінде қате болса — бәрі қайтарылады (ROLLBACK)
    before = Doctor.objects.count()
    try:
        with transaction.atomic():
            Doctor.objects.create(full_name="Уақытша дәрігер")
            raise ValueError("әдейі қате")
    except ValueError:
        pass
    print(f"--- atomic: дәрігер саны {before} -> {Doctor.objects.count()} (өзгермеді)")


def write_delete(appointment):
    patient, doctor = appointment.patient, appointment.doctor
    appointment.delete()
    patient.delete()
    doctor.delete()  # PROTECT: қабылдау өшкен соң ғана өшеді
    print("--- delete: тест деректері өшірілді")


# ============ 5-қадам. ОҢТАЙЛАНДЫРУ (N+1) ============

def n_plus_one():
    for a in Appointment.objects.all():
        a.doctor.full_name            # әр қабылдауға +1 сұраныс


def with_select_related():
    for a in Appointment.objects.select_related("doctor"):
        a.doctor.full_name


def tags_plain():
    for a in Appointment.objects.all():
        [d.name for d in a.diagnoses.all()]


def tags_prefetch():
    for a in Appointment.objects.prefetch_related("diagnoses"):
        [d.name for d in a.diagnoses.all()]


def both_plain():
    for a in Appointment.objects.all():
        a.doctor.full_name
        [d.name for d in a.diagnoses.all()]


def both_optimized():
    qs = Appointment.objects.select_related("doctor").prefetch_related("diagnoses")
    for a in qs:
        a.doctor.full_name
        [d.name for d in a.diagnoses.all()]


def reverse_plain():
    for d in Doctor.objects.all():
        list(d.appointments.all())


def reverse_prefetch():
    for d in Doctor.objects.prefetch_related("appointments"):
        list(d.appointments.all())


def report():
    rows = [
        ("100 қабылдау + дәрігер", 'select_related("doctor")',
         n_plus_one, with_select_related),
        ("100 қабылдау + диагноздар", 'prefetch_related("diagnoses")',
         tags_plain, tags_prefetch),
        ("100 қабылдау + дәрігер + диагноз", "екеуі бірге",
         both_plain, both_optimized),
        ("20 дәрігер + қабылдаулары", 'prefetch_related("appointments")',
         reverse_plain, reverse_prefetch),
    ]
    print("\n=== Сұраныстар саны: дейін / кейін ===")
    print(f"{'Сценарий':36} {'Әдіс':32} {'Дейін':>6} {'Кейін':>6}")
    for scenario, method, before, after in rows:
        print(f"{scenario:36} {method:32} "
              f"{count_queries(before):>6} {count_queries(after):>6}")


# ============ Бәрін іске қосу ============

def run_all():
    read_filter()
    read_q()
    read_not_q()
    read_order()
    read_by_relation()
    read_aggregate()
    read_annotate()
    read_group_by()
    read_having()

    report()

    appointment = write_create()
    write_update(appointment)
    write_set_tags(appointment)
    write_atomic()
    write_delete(appointment)