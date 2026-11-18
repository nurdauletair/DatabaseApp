# Емхана — управление приёмами клиники

Django-приложение для врачей, пациентов и регистратуры: запись на приём,
диагнозы, поиск, фильтры, REST API и разграничение доступа.
Основная база данных — PostgreSQL. Интерфейс сайта на казахском языке.

## Одна папка, одна ветка

Вся актуальная работа находится в **`main`** этого репозитория.
На текущем Mac проект находится в `/Users/nurdaulet/DatabaseApp`.
Следующие задания выполняются здесь же. Переключать учебные ветки не требуется.
Предыдущие версии сохранены в истории Git; метки `clinic-before-lab10`
и `clinic-before-lab11` отмечают состояние до соответствующих работ.

## Обычный запуск на текущем Mac

```bash
cd /Users/nurdaulet/DatabaseApp
source venv/bin/activate
brew services start postgresql@17
git pull --ff-only
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Открыть http://127.0.0.1:8000/ . Остановить сервер: **Ctrl+C** в его терминале.
Если порт занят другим запущенным сервером, можно использовать
`python manage.py runserver 8001` и http://127.0.0.1:8001/ .
Локальные учебные пароли: `.local-backups/demo-credentials.txt`.

## Первый запуск на другом ноутбуке

Нужны Python 3.12+ и PostgreSQL. Команды ниже для macOS/Linux;
в Windows активация окружения: `venv\Scripts\activate`.

```bash
git clone https://github.com/nurdauletair/DatabaseApp.git
cd DatabaseApp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Записать сгенерированный ключ в `DJANGO_SECRET_KEY` файла `.env`.
В PostgreSQL от имени администратора создать пользователя и пустую базу,
подставив собственный пароль:

```sql
CREATE ROLE clinic_user LOGIN CREATEDB PASSWORD 'choose-your-own-password';
CREATE DATABASE clinic_db OWNER clinic_user;
```

В `.env` указать `DB_ENGINE=postgresql`, `DB_NAME=clinic_db`,
`DB_USER=clinic_user`, `DB_PASSWORD` с выбранным паролем,
`DB_HOST=127.0.0.1`, `DB_PORT=5432`. Право CREATEDB нужно для тестовой базы.

Далее выбрать один способ подготовки данных:

- **Перенести текущие записи и аккаунты:** восстановить копию базы по разделу ниже,
  затем выполнить `python manage.py migrate`. Учебных пользователей заново создавать не нужно.
- **Начать с новой базы и новыми учебными аккаунтами:** выполнить команды ниже один раз.

```bash
python manage.py migrate
python manage.py create_demo_users --credentials-file .local-backups/demo-credentials.txt
```

После подготовки базы:

```bash
python manage.py check
python manage.py runserver
```

Для демонстрации производительности установить `PERFORMANCE_LAB=1` в `.env`.
На новой базе после создания учебных аккаунтов можно один раз выполнить
`python manage.py seed_perf`: он добавляет 20 000 учебных приёмов.
Если восстановлена текущая база, эти данные уже есть.
Команда `seed` удаляет существующие записи клиники: для запуска и обновления она не нужна.

## Перенос текущей базы

Git переносит код. PostgreSQL, `.env`, виртуальное окружение и файл паролей
хранятся отдельно и не публикуются на GitHub.
Чтобы на другом ноутбуке появились те же приёмы и аккаунты, сначала на исходном компьютере:

```bash
mkdir -p .local-backups
pg_dump -h 127.0.0.1 -U clinic_user -d clinic_db -Fc -f .local-backups/clinic_db.dump
```

Команда запросит пароль PostgreSQL из `.env`. На Mac с Homebrew при необходимости
сначала добавить инструменты в PATH:
`export PATH="$(brew --prefix postgresql@17)/bin:$PATH"`.
Передать файл `clinic_db.dump` лично на другой ноутбук. Затем восстановить его
в **новую пустую** базу `clinic_db`, созданную выше, до первого `migrate`:

```bash
pg_restore -h 127.0.0.1 -U clinic_user -d clinic_db --no-owner --no-privileges --exit-on-error /path/to/clinic_db.dump
python manage.py migrate
```

Для входа сохранёнными учебными аккаунтами также передать себе
`.local-backups/demo-credentials.txt` вне GitHub. Настройки `.env` должны
соответствовать PostgreSQL на новом ноутбуке.

## Работа с двух ноутбуков

Перед изменениями в папке проекта:

```bash
git pull --ff-only
```

После работы сохранить изменённые файлы и отправить их:

```bash
git status
git add ИМЕНА_ИЗМЕНЁННЫХ_ФАЙЛОВ
git commit -m "Описание изменений"
git push
```

В `git add` указать реальные пути нужных файлов из `git status`.
Сначала отправить изменения с первого ноутбука, затем выполнить `git pull --ff-only`
на втором. Изменения записей в PostgreSQL передаются отдельной копией базы.

## Доступ и разделы

| Роль | Доступ |
| --- | --- |
| Пациент | Свои приёмы и запись к врачу |
| Врач | Свои приёмы и связанные пациенты |
| Регистратор | Записи клиники и управление приёмами |
| Администратор | Полный доступ, пользователи и роли |

Сайт: `/`; приёмы: `/appointments/`; пациенты: `/patients/`; врачи: `/doctors/`.
Вход: `/login/`; регистрация: `/signup/`; профиль: `/profile/`; админка: `/admin/`.
Служебный раздел «Жүйе күйі»: `/monitoring/` (при `PERFORMANCE_LAB=1`).
Debug Toolbar скрывается настройкой `LAB11_TOOLBAR=0` в `.env` и перезапуском сервера.

REST API: `/api/`, ресурсы `doctors`, `patients`, `diagnoses`, `appointments`.
Token: `/api/token/`, `/api/token/logout/`.
JWT: `/api/jwt/`, `/api/jwt/refresh/`, `/api/jwt/logout/`.
Объектные ограничения действуют также на API и статистику.

## Материалы и проверка

- [LAB10.md](LAB10.md) — роли, сессии, Token/JWT и защита работы.
- [LAB11.md](LAB11.md) — оптимизация запросов, индексы, кэш и измерения.
- `reports/` — PDF-отчёт; `evidence/` — измерения и скриншоты.
- `accounts/` — пользователи и роли; `blog/` — клиника и API;
  `performance/` — мониторинг; `config/` — настройки.

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```


## Отчёты с GPT API

Раздел **«Есептер»**: `/report/`. Доступен администратору и регистратору.
Вопрос → GPT → проверка SELECT → отдельное подключение PostgreSQL только для чтения → таблица.
Результаты запросов в OpenAI не отправляются. Учебные приёмы исключены из отчётов.

На текущем Mac всё подготовлено. Осталось самостоятельно создать ключ в своей
OpenAI Platform организации с балансом и заполнить **только локальный `.env`**:

```dotenv
OPENAI_API_KEY=вставь_свой_ключ
OPENAI_MODEL=gpt-5.4-mini
```

После изменения `.env` перезапустить `runserver`. Ключ не вставляется в сайт,
код, переписку или `.env.example`. Инструкция: **[LAB12.md](LAB12.md)**.

На новом ноутбуке после установки зависимостей и `migrate` также выполнить
`python manage.py setup_report_reader` от имени локального администратора PostgreSQL.
Команда создаёт отдельную роль и сама записывает её пароль в игнорируемый `.env`.
Для установки PostgreSQL с другим администратором см. LAB12.md.
