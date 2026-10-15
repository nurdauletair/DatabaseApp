#!/bin/sh
# Git тарихын 4 кезең бойынша жасайды. Іске қосу:  sh make_commits.sh
set -e
git init -b main 2>/dev/null || git init
git add .gitignore requirements.txt .env.example manage.py config \
  blog/__init__.py blog/apps.py blog/models.py blog/migrations blog/admin.py \
  blog/management blog/queries.py blog/tests.py blog/test_models.py
git commit -m "Этап 1: модели (Doctor, Patient, Diagnosis, Appointment), миграции, админка, тесты моделей"
git add blog/forms.py blog/views.py blog/urls.py blog/templates blog/static \
  blog/test_crud.py blog/test_web.py
git commit -m "Этап 2: веб-CRUD (приёмы, пациенты, врачи), формы с валидацией, поиск, фильтр, пагинация, дизайн"
git add blog/api blog/test_api.py
git commit -m "Этап 3: REST API на DRF: сериализаторы, ViewSet, router, права доступа, без N+1"
git add .
git commit -m "Этап 4: README, настройки через .env, шпаргалка для защиты"
git log --oneline
