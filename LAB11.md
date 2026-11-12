# 11-ЗС: производительность Django в проекте клиники

Вся работа продолжается в `/Users/nurdaulet/DatabaseApp`, в том же Git-репозитории и PostgreSQL `clinic_db`. Ветка `lab11-performance`; версия 10-ЗС сохранена в `lab10-auth` и теге `clinic-before-lab11`. Резервная копия до изменения данных: `.local-backups/before-lab11/clinic_db.sql`.

## Запуск

```bash
cd /Users/nurdaulet/DatabaseApp
source venv/bin/activate
brew services start postgresql@17
python manage.py migrate
python manage.py check
python manage.py runserver
```

Открой http://127.0.0.1:8000/lab11/ и войди как `demo_admin`. Пароли прежние: `.local-backups/demo-credentials.txt`. `PERFORMANCE_LAB=1` уже записан в локальном `.env`. Если порт 8000 занят, используй `python manage.py runserver 8001` и соответствующий адрес.

Три страницы: `/lab11/slow/`, `/lab11/optimized/`, `/lab11/cached/`. В меню добавлена ссылка «11-ЗС». Правила доступа 10-ЗС действуют на всех трёх страницах.

## Если проект клонируется на чистый компьютер

Настрой PostgreSQL и `.env` по LAB10.md, выполни `pip install -r requirements.txt` и установи `PERFORMANCE_LAB=1` в `.env`. На НОВОЙ пустой базе затем выполни:

```bash
python manage.py migrate
python manage.py setup_roles
python manage.py create_demo_users --credentials-file .local-backups/demo-credentials.txt
python manage.py seed_perf
```

Эти команды первоначальной подготовки уже выполнены на этом компьютере. При дальнейшем запуске достаточно `runserver`; `seed_perf` повторять не нужно. Пароли генератора случайные и сохраняются только в указанном локальном файле.

## Данные

Генератор `seed_perf` добавил 20 000 записей с `is_training=True`, 60 000 заметок, 50 учебных диагнозов, 199 врачей и 1 999 пациентов. В наборе генерации участвуют также прежние профили `demo_doctor` и `demo_patient`, поэтому пул содержит 200 врачей и 2 000 пациентов. Старые 100 приёмов, 20 врачей, 32 пациента, 5 диагнозов и их связи проверены по SQL-резервной копии. Генератор повторный запуск отклоняет и существующие данные не удаляет.

```bash
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
python manage.py dbshell
```

```sql
\conninfo
\dt
SELECT count(*) FROM blog_appointment WHERE is_training;
SELECT count(*) FROM blog_appointmentnote;
SELECT count(*) FROM blog_appointment WHERE NOT is_training;
\d blog_appointment
\q
```

Новая модель `AppointmentNote` соответствует комментариям из примера блога. Поле `reason` содержит длинный учебный текст для демонстрации `defer`. Основная клиника и API продолжают работать с теми же моделями.

## Измерения и профилирование

`TimingMiddleware` пишет метод, путь, время и SQL в `.local-backups/perf.log`; запросы дольше 300 мс получают WARNING. Сырые SQL можно включить переменной `LAB11_SQL_LOG=1` при запуске. Middleware и Toolbar включаются только при DEBUG и PERFORMANCE_LAB.

```bash
tail -f .local-backups/perf.log
```

Справа в браузере нажми SQL в Debug Toolbar. Для показа серверного cache hit используй принудительную перезагрузку Cmd+Shift+R: обычная навигация может вернуть сохранённый браузером HTML вместе со старыми цифрами Toolbar. В автоматических скриншотах отключён HTTP-кэш браузера, серверный кэш остаётся включённым. Доступ Toolbar ограничен локальными IP. Для чистых автоматических измерений его middleware отключён; обычная сессионная аутентификация в полном HTTP-измерении сохраняется.

Каждый JSON в `evidence/` содержит все пять повторений и медианы. `business` — представление с уже определённым пользователем; `http` — полный стек с сессией, проверкой доступа и middleware. Время SQL измеряется через execute_wrapper с perf_counter без округления до миллисекунд. Время из стандартного Django connection.queries в perf.log округляется драйвером, поэтому может отличаться.

```bash
python manage.py benchmark_perf --stage slow-current --path /lab11/slow/ --output .local-backups/slow-current.json
python manage.py benchmark_perf --stage optimized-current --path /lab11/optimized/ --output .local-backups/optimized-current.json
python manage.py benchmark_perf --stage miss-current --path /lab11/cached/ --cache-mode miss --output .local-backups/miss-current.json
python manage.py benchmark_perf --stage hit-current --path /lab11/cached/ --cache-mode hit --output .local-backups/hit-current.json
```

Это новые измерения уже с установленным индексом. Исторические результаты до индекса сохранены в `evidence/04-explain-*-before.txt` и предыдущих Git-коммитах.

Для baseline запросов 201, а не 151 из примера: каждый из 50 приёмов загружает отдельно врача, пациента, диагнозы и количество заметок. Оптимизированный запрос сначала выбирает ID 50 видимых приёмов вложенным SELECT, затем делает JOIN врача/пациента и annotate(Count(notes)); диагнозы загружаются второй SQL-командой. Это позволяет не агрегировать заметки всех 20 000 приёмов. `defer("reason")` исключает большой текст из списка.

## Индекс

Составной индекс `appt_status_date_idx` описан в Meta.indexes модели Appointment и добавлен миграцией 0006. В evidence сохранены планы фильтра и полного оптимизированного запроса до/после. Проверка текущего плана:

```bash
python manage.py shell
```

```python
from django.contrib.auth import get_user_model
from performance.queries import base_queryset
u = get_user_model().objects.get(username="demo_admin")
print(base_queryset(u)[:50].explain(analyze=True, buffers=True))
exit()
```

Не нужно отключать планировщик или принудительно включать Index Scan: сохранён реальный выбор PostgreSQL.

## Кэш и очистка

LocMemCache хранит страницу и загруженные данные таблицы 60 секунд, статистику 600 секунд. Дополнительный кэш данных позволяет обойтись без SQL даже при изменении cookies, которое меняет ключ кэша страницы. Первый miss выполняет 5 SQL к данным (2 для таблицы и 3 для статистики), повторный hit — 0. В полном HTTP-запросе остаются 2 SQL авторизации. Перед измерением hit выполняются прогрев и установка стабильного CSRF cookie.

Проверка прав выполняется перед серверным кэшем. Ключ учитывает пользователя, право manage_clinic и версию данных; дополнительно используется Vary: Cookie. Во внешний ответ добавляется Cache-Control: private. Изменения приёмов, заметок, диагнозов, врачей, пациентов и M2M диагнозов увеличивают версию кэша через transaction.on_commit. Это немедленно делает прежние ключи недействительными после фиксации транзакции. Для bulk_create/update/QuerySet.update, которые не вызывают post_save, после фиксации вызывайте `performance.cache.invalidate()` явно. LocMem предназначен для одного процесса; для нескольких процессов нужен общий backend, например Redis.

Чтобы показать обновление статистики: открой кэшированную страницу под админом, в соседней вкладке добавь заметку через `/admin/blog/appointmentnote/add/`, указав ID учебного приёма, затем обнови страницу кэша. Запись можно затем удалить. Сигналы проверяются также автоматическими тестами в отдельной БД.

## Тесты и материалы для защиты

```bash
python manage.py test --verbosity 2
python manage.py makemigrations --check --dry-run
```

На PostgreSQL прошли 94 теста. Новые проверки подтверждают 201→2 (на маленькой фикстуре 41→2), одинаковость данных, отложенную загрузку reason, нулевой SQL на cache hit, изоляцию пациентов, отзыв разрешений и обновление кэша. Полный вывод: `evidence/tests.txt`. Исходные записи сверены в `evidence/data-integrity.json`; SHA-256 содержимого таблицы одинаков во всех этапах измерения.

Скриншоты находятся в `evidence/screenshots/`. Отчёт: `reports/Мұратов_Нұрдәулет_ЗС11.pdf`. Скрипт сборки: `scripts/build_lab11_report.py`; для пересборки нужны зависимости из `requirements-report.txt`.

На защите покажи: количество данных; perf.log; Toolbar SQL для медленной/быстрой страницы; индекс и EXPLAIN; два открытия кэша; добавление заметки и обновление статистики; итог OK тестов. При сравнении ролей используй разные профили браузера или инкогнито.

## Ответы на вопросы

1. select_related работает через JOIN для FK/OneToOne. Для M2M диагнозов нужен prefetch_related, иначе JOIN умножит строки основной модели.
2. Индекс ускоряет существующий SELECT; число SQL-команд может остаться тем же.
3. Индекс (status, date) наиболее подходит для WHERE status=... ORDER BY date. Для одного date его эффективность не гарантирована: нужен EXPLAIN; планировщик может предпочесть другой план.
4. Кэш устаревает до TTL или инвалидирования. Здесь версия меняется после commit; массовые обновления требуют явного invalidate.
5. DEBUG и Toolbar нужны локально; в продакшне они раскрывают диагностическую информацию и добавляют накладные расходы.

Официальные источники: https://docs.djangoproject.com/en/6.1/topics/cache/ и https://django-debug-toolbar.readthedocs.io/en/stable/installation.html .
