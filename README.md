# Емхана: Django жобасы (CRUD веб-қосымша + REST API)

Емхана қабылдауларын жүргізуге арналған оқу жобасы: **дәрігерлер**, **науқастар**,
**диагноздар** және **қабылдаулар**. Бір дерекқорға екі интерфейс бар:
адамға арналған веб-беттер және бағдарламаларға арналған REST API.

## Мүмкіндіктер

- **Модельдер:** `Doctor`, `Patient`, `Diagnosis`, `Appointment`
  (`ForeignKey`: қабылдау → дәрігер, науқас; `ManyToManyField`: науқас ↔ дәрігер, қабылдау ↔ диагноз).
- **Веб-CRUD:** қабылдаулар (функциялық көріністер), науқастар мен дәрігерлер (класс көріністері);
  `ModelForm` және қазақша валидация; іздеу, сүзу, сұрыптау, беттеу; басты бетте қорытынды көрсеткіштер.
- **REST API (DRF):** `ModelSerializer`, `ModelViewSet`, `DefaultRouter`, толық CRUD (JSON),
  іздеу/сұрыптау/сүзу, беттеу, `IsAuthenticatedOrReadOnly` рұқсаты.
- **ORM сапасы:** `select_related`, `prefetch_related`, `annotate`, `aggregate`; N+1 жоқ (тестпен бекітілген).
- **Тесттер:** модель, веб және API тесттері.
- **Әкімшілік панелі:** барлық модель, іздеу, сүзгі, «Өтті деп белгілеу» әрекеті.

## Орнату және іске қосу

```bash
git clone <репозиторий-сілтемесі>
cd <папка>
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                # құпия кілтті жасау:
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
# шыққан мәнді .env ішіндегі DJANGO_SECRET_KEY-ге жазыңыз

python manage.py migrate
python manage.py createsuperuser    # API мен әкімшілік панеліне кіру үшін
python manage.py seed               # демо-деректер: 20 дәрігер, 30 науқас, 100 қабылдау
python manage.py runserver
```

Сайт: http://127.0.0.1:8000/ · API: http://127.0.0.1:8000/api/ · Админка: http://127.0.0.1:8000/admin/

## Тесттер

```bash
python manage.py test blog
```

## Веб-беттер

| Бет | URL |
| --- | --- |
| Басты бет | `/` |
| Қабылдаулар: тізім, қарау, қосу, өңдеу, жою | `/appointments/`, `/appointments/<id>/`, `/new/`, `/<id>/edit/`, `/<id>/delete/` |
| Науқастар | `/patients/`, `/patients/<id>/`, `/new/`, `/<id>/edit/`, `/<id>/delete/` |
| Дәрігерлер | `/doctors/`, `/doctors/<id>/`, `/new/`, `/<id>/edit/`, `/<id>/delete/` |

Жою екі қадамды: GET растау бетін көрсетеді, POST жояды. Сәтті POST-тан кейін redirect (302).

## REST API

Базалық адрес: `/api/`. Ресурстар: `doctors`, `patients`, `diagnoses`, `appointments`.

| Әдіс | URL | Әрекет | Код |
| --- | --- | --- | --- |
| GET | `/api/appointments/` | тізім (беттеумен) | 200 |
| POST | `/api/appointments/` | құру | 201 |
| GET | `/api/appointments/1/` | бір жазба | 200 |
| PUT, PATCH | `/api/appointments/1/` | жаңарту | 200 |
| DELETE | `/api/appointments/1/` | өшіру | 204 |
| GET | `/api/appointments/stats/` | қорытынды (aggregate) | 200 |

Параметрлер: `?search=`, `?ordering=-price`, `?status=done`, `?doctor=3`, `?page=2`.

**Рұқсаттар:** оқуға (GET) бәріне ашық; жазуға, өзгертуге және өшіруге тек кірген қолданушыға рұқсат
(`IsAuthenticatedOrReadOnly`). Браузерде кіру: `/api-auth/login/`.
Қабылдаулары бар дәрігерді өшіруге тырысқанда API `409 Conflict` қайтарады.

Мысал (curl, кіру үшін Basic auth):

```bash
curl "http://127.0.0.1:8000/api/appointments/?status=planned"

curl -u admin:ПАРОЛЬ -X POST http://127.0.0.1:8000/api/appointments/ \
  -H "Content-Type: application/json" \
  -d '{"doctor_id": 1, "patient_id": 1, "diagnoses": ["Грипп"],
       "price": "4500.00", "duration": 30, "status": "planned",
       "date": "2026-11-01T10:00:00+05:00"}'
```

## Жоба құрылымы

```
config/            баптаулар, басты urls.py
blog/models.py     модельдер
blog/forms.py      ModelForm және валидация
blog/views.py      веб-көріністер (FBV және CBV)
blog/urls.py       веб-маршруттар
blog/templates/    шаблондар (base.html + беттер)
blog/static/       стиль (style.css)
blog/api/          serializers.py, views.py, urls.py (DRF)
blog/admin.py      әкімшілік панелі
blog/queries.py    ORM сұраныстары және N+1 өлшеу
blog/test_*.py     тесттер (модель, веб, API)
```

## Құпиялар

`SECRET_KEY` пен басқа құпия баптаулар `.env` файлында тұрады және Git-ке түспейді
(`.gitignore`). Үлгі: `.env.example`.

## Сұраныстар саны (N+1 жоқ)

| Сценарий | Дейін | Кейін |
| --- | --- | --- |
| 100 қабылдау + дәрігер (`select_related`) | 101 | 1 |
| 100 қабылдау + диагноздар (`prefetch_related`) | 101 | 2 |
| 100 қабылдау + дәрігер + диагноз (екеуі бірге) | 201 | 2 |
| API: қабылдаулар беті (10 жазба) | — | 3 |
