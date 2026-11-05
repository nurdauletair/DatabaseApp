# 10-ЗС · Емхана: аутентификация және авторизация

«Онлайн курстар» мысалы емханаға бейімделді: student → patient,
teacher → doctor, manager → registrar. Түпнұсқа Doctor, Patient, Diagnosis,
Appointment модельдері, CRUD, іздеу, сүзу және API сақталды.

## Іске қосу

Жергілікті орта дайын болғанда:

```bash
cd /Users/nurdaulet/DatabaseApp
source venv/bin/activate
python manage.py runserver
```

Сайт: http://127.0.0.1:8000/ · Кіру: http://127.0.0.1:8000/login/
Жеке кабинет: http://127.0.0.1:8000/profile/ · Админ: http://127.0.0.1:8000/admin/

Бұрынғы әкімші аккаунтының паролі өзгертілмейді. Демо аккаунттардың кездейсоқ
парольдері `.local-backups/demo-credentials.txt` файлында сақталады, Git-ке кірмейді.
`demo_patient` — науқас, `demo_doctor` — дәрігер, `demo_registrar` — тіркеуші,
`demo_admin` — барлық мүмкіндікті тексеруге арналған әкімші.

## Таза компьютерде PostgreSQL орнату (macOS, Homebrew)

```bash
brew install postgresql@17
brew services start postgresql@17
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
psql postgres
```

psql ішінде (жеке пароль таңдаңыз):

```sql
CREATE ROLE clinic_user LOGIN CREATEDB PASSWORD 'YOUR_OWN_PASSWORD';
CREATE DATABASE clinic_db OWNER clinic_user;
\q
```

`CREATEDB` осы жергілікті оқу ортасында Django-ның `test_clinic_db` құруы үшін қажет.
`.env.example` файлын `.env` атымен көшіріп, DB_PASSWORD пен DJANGO_SECRET_KEY
мәндерін өзіңіздікіне ауыстырыңыз. Парольдер репозиторийге қосылмайды.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py setup_roles
python manage.py createsuperuser
python manage.py seed
python manage.py create_demo_users --credentials-file .local-backups/demo-credentials.txt
python manage.py test
python manage.py runserver
```

Демо команданы бір рет орындаңыз: бұрыннан бар аккаунттардың паролін ол өзгертпейді.
Homebrew Intel Mac-та болса, PostgreSQL жолы `/usr/local/opt/postgresql@17/bin` болады.

PostgreSQL тексеру:

```bash
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
python manage.py dbshell
```

```sql
\conninfo
\dt
SELECT username, left(password, 24) AS password_hash FROM accounts_user;
SELECT session_key, expire_date FROM django_session;
```

Кестелер арасында `accounts_user`, `auth_group`, `auth_permission`,
`django_session`, `authtoken_token`, `blog_appointment` және blacklist кестелері болады.
`accounts_user.password` ішінде парольдің өзі сақталмайды.

## Бұрынғы SQLite деректері

Ескі `db.sqlite3` өзгертілмейді. Қосымша көшірме және бастапқы `.env`
`.local-backups/before-lab10-.../` қалтасында сақталады.
Бастапқы экспорт: `.local-backups/legacy-data.json`.
`auth.user` → `accounts.user` және admin журналының User content type сілтемесі
түзетілген экспорт: `.local-backups/clinic-data.json`.
Алғашқы миграциялар жаңа бос дерекқорда орындалады, содан кейін экспорт жүктеледі.
User ID және пароль хештері сақталады. Бұрынғы сеанстар тасымалданбайды: қайта кіріңіз.

Егер жаңа бос дерекқорға жергілікті экспортты қалпына келтіру қажет болса:

```bash
python manage.py migrate
python manage.py loaddata .local-backups/clinic-data.json
python manage.py setup_roles
```

Бұрынғы `auth.User` бар SQLite-қа жаңа `AUTH_USER_MODEL` параметрімен жай ғана
`migrate` жасауға болмайды: admin миграциясының тәуелділігі өзгереді.
Ескі миграциялар жойылмайды, деректер жаңа схемаға көшіріледі.

## Рөлдер және рұқсаттар

| Әрекет | Аноним | Науқас | Дәрігер | Тіркеуші |
| --- | --- | --- | --- | --- |
| HTML беттер | login-ге 302 | өзінің жазбалары | өзінің қабылдаулары | барлық жазба |
| API оқу | 401 | өзінің жазбалары | өзінің қабылдаулары | барлық жазба |
| Өзіне жазылу `/appointments/book/` | 302 | рұқсат | 403 | 403 |
| Жалпы қабылдау қосу | 302 / API 401 | 403 | 403 | рұқсат / API 201 |
| Қабылдауды өңдеу | 302 / API 401 | 403 | тек өзінікі | барлық жазба |
| Қабылдауды растау | 302 / API 401 | 403 | 403 | рұқсат |
| Науқас/дәрігерді қосу, өзгерту, жою | 302 / API 401 | 403 | 403 | рұқсат |
| Админ панелі | login | login | шектелген | шектелген |
| Пайдаланушы/топ/рөл тағайындау | жоқ | жоқ | жоқ | жоқ |

Әкімші (`is_superuser`) барлық рұқсатқа ие. `is_staff` тек админ панеліне кіруге
мүмкіндік береді; ол модель рұқсаттарын бермейді. Топтар `setup_roles` командасымен
құрылады. Команданы қайталау топтарды көбейтпейді.

Науқас жалпы CRUD формасына кірмейді. Жазылу формасы тек дәрігер мен уақытты
қабылдайды. Науқас, баға, диагноз және күй серверде белгіленеді.
Дәрігер диагноз, ұзақтық және күйді өңдейді, бірақ дәрігерді/науқасты ауыстыра,
бағаны/уақытты өзгерте немесе тіркеушінің орнына қабылдауды растай алмайды.
HTML, API, admin формалары мен bulk action осы шектеулерді орындайды.

Бөгде қабылдауды HTML арқылы ашу/өңдеу — 403; API сүзілген queryset-інде
бөгде объект — 404. Тізімдер, науқас/дәрігер карточкалары және агрегаттар
пайдаланушыға көрінетін қабылдаулармен ғана есептеледі.
Мәзірдегі батырманы жасыруға қоса серверде permission және объект иесі тексеріледі.

Жаңа дәрігер аккаунтына әкімші Users бетінде `doctor` тобын және `is_staff`
белгісін қояды, содан кейін Doctors бетінде User өрісіне осы аккаунтты таңдайды.
Тіркеушіге `registrar` тобы және `is_staff` беріледі. Науқастың тіркелуі
Patient профилін автоматты жасайды. Демо тіркелгілер осы байланыстармен дайындалады.

## Сеанстар

`/profile/` бетінде логин, рөл, телефон, рұқсаттар, ағымдағы сеанс кілті,
мерзімі және келу санағышы бар. Кілтті өзгеге бермеңіз.
Сервер деректерді `django_session` ішінде сақтайды, браузер cookie-де кілтті ұстайды.
`SESSION_COOKIE_AGE=28800`, `HttpOnly=True`, `SameSite=Lax`.
`DEBUG=False` кезінде Secure cookie тек HTTPS арқылы жіберіледі.
Жергілікті HTTP тексеруі үшін `.env` ішінде `DJANGO_DEBUG=1` болады.

`/logout/` — POST + CSRF. `/logout-all/` — POST + CSRF, пайдаланушының барлық
браузер сеанстарын жояды, басқа пайдаланушылардың сеанстарын сақтайды.
Бұл батырма API токендерін жоймайды: Token/JWT үшін бөлек logout endpoint бар.
Пароль өзгергенде бұрынғы браузер сеансының auth hash тексеруі өтпейді.

Ескі жазбаларды тазалау: `python manage.py clearsessions`.

## Token және JWT: curl арқылы көрсету

Төмендегі мысалдарда нақты пароль/токен орнына өз аккаунтыңыздың мәнін жазыңыз.

```bash
# 401: API-ға аноним кіре алмайды
curl -i http://127.0.0.1:8000/api/appointments/

# Token алу
curl -X POST http://127.0.0.1:8000/api/token/ \
  -d 'username=demo_patient' -d 'password=YOUR_PASSWORD'

# 200: тек осы науқастың жазбалары
curl -i -H 'Authorization: Token YOUR_TOKEN' http://127.0.0.1:8000/api/appointments/

# 403: науқас жалпы CRUD арқылы жазба қоса алмайды
curl -i -X POST -H 'Authorization: Token YOUR_TOKEN' http://127.0.0.1:8000/api/appointments/ \
  -H 'Content-Type: application/json' -d '{}'

# Token жою → келесі сұраныс 401
curl -i -X POST -H 'Authorization: Token YOUR_TOKEN' http://127.0.0.1:8000/api/token/logout/

# JWT: access + refresh
curl -X POST http://127.0.0.1:8000/api/jwt/ \
  -d 'username=demo_doctor' -d 'password=YOUR_PASSWORD'

curl -i -H 'Authorization: Bearer YOUR_ACCESS' http://127.0.0.1:8000/api/me/

# Жаңа access + refresh; бұрынғы refresh blacklist-ке түседі
curl -X POST http://127.0.0.1:8000/api/jwt/refresh/ \
  -H 'Content-Type: application/json' -d '{"refresh":"YOUR_REFRESH"}'

# Шығу: қазіргі refresh-ті blacklist-ке қосу
curl -i -X POST http://127.0.0.1:8000/api/jwt/logout/ \
  -H 'Authorization: Bearer YOUR_ACCESS' -H 'Content-Type: application/json' \
  -d '{"refresh":"YOUR_CURRENT_REFRESH"}'
```

JWT access — 15 минут, refresh — 7 күн. Blacklist refresh-ті жаңартуға тыйым
салады; бұрын берілген access мерзімі біткенше жарамды. JWT payload шифрланбайды,
оған диагноз, пароль және медициналық деректер салынбайды.
Өзге пайдаланушының refresh токенін logout арқылы жою — 403.
Ескі blacklist жазбаларын тазалау: `python manage.py flushexpiredtokens`.

## Тесттер және тапсыру

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --verbosity 2
```

Тесттер тіркелу рөлін, пароль хешін, әлсіз парольді, объект иесін, статистикадағы
оқшаулауды, admin шектеулерін, CSRF, сеанс пен logout-all, Token және JWT,
refresh blacklist пен ротацияны тексереді. Бұрынғы CRUD және ORM тесттері де сақталған.
PostgreSQL бапталғанда тесттер `test_clinic_db` жеке дерекқорында жүреді.

Тапсыруға: құпиясыз Git репозиторийі, PostgreSQL `\dt`, admin рөлдер/шектеу
скриншоттары, 200/401/403 API мысалдары, өткен тесттердің нәтижесі.
Қосымша тапсырма ретінде **B · JWT blacklist** орындалды.

Осы компьютердегі тексеру нәтижелері `.local-backups/evidence/` ішінде:
`tests-postgresql.txt` — 84 тесттің нәтижесі,
`postgresql-tables.txt` — нақты `\conninfo` және `\dt` шығысы,
`curl-api.txt` — нақты curl сұраныстары, токендер мен парольдер жасырылған.
Автоматты браузерді іске қосуға рұқсат берілмегендіктен, скриншоттар жасалмады.
Тапсыру үшін `\dt` шығысын, admin Groups пен Users беттерін және дәрігердің
шектелген әрекетіне арналған 403 бетін браузер/терминал арқылы суретке түсіріңіз.

## Git арқылы қайту

Бастапқы код: `main`, нақты нүкте: `clinic-before-lab10` (`0aa87b7`).
Жаңа код: `lab10-auth`. Git `.env` пен дерекқорды сақтамайды.

Ескі сайтты жаңа тармаққа тимей бөлек қалтада ашу:

```bash
git worktree add ../DatabaseApp-before-lab10 clinic-before-lab10
```

Содан кейін `.local-backups/before-lab10-.../` ішіндегі `.env` және `db.sqlite3`
файлдарын **сол жаңа қалтаға** көшіріңіз. Бұрынғы виртуалды орта Python-ын пайдаланып:

```bash
cd ../DatabaseApp-before-lab10
../DatabaseApp/venv/bin/python manage.py runserver 8001
```

Бұл тәсіл жаңа PostgreSQL базасын және `lab10-auth` тармағын өзгертпейді.
`.local-backups/` ішіндегі парольдер мен медициналық деректер GitHub-қа жіберілмейді.

## Қорғау сұрақтарына қысқа жауаптар

- Аутентификация — кім кіргенін тексеру. Авторизация — не істеуге рұқсаты барын тексеру.
- 401 — API аутентификациясы жоқ/жарамсыз. 403 — әрекетке рұқсат жоқ; CSRF қатесі де 403 беруі мүмкін.
- Salt бірдей парольдердің хешін әртүрлі етеді. Итерациялар парольді жаппай болжауды баяулатады.
- Пароль `create_user`, `UserCreationForm`, `set_password` арқылы хештеледі; тікелей password өрісіне жазылмайды.
- Сеанс браузерге ыңғайлы; DRF Token қарапайым API клиентіне; JWT қысқа access пен refresh ағынына ыңғайлы.
- is_staff админге кіруді ашады. is_superuser барлық permission тексеруінен өтеді.
- Шаблон батырманы ғана жасырады. URL/API сұранысын қолмен жіберуге болатындықтан сервердегі тексеру міндетті.

## Ресми құжаттама

- https://docs.djangoproject.com/en/6.0/topics/auth/customizing/
- https://docs.djangoproject.com/en/6.0/topics/http/sessions/
- https://www.django-rest-framework.org/api-guide/permissions/
- https://django-rest-framework-simplejwt.readthedocs.io/en/stable/blacklist_app.html
- https://www.postgresql.org/download/macosx/
