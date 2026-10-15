"""config/settings.py-ды бір рет автоматты түрде баптайды (қайта іске қосса — зиян жоқ).

1) SECRET_KEY, DEBUG, ALLOWED_HOSTS -> .env файлынан (Git-ке түспейді)
2) "rest_framework" қосымшасын INSTALLED_APPS-қа қосады
3) REST_FRAMEWORK баптауларын (рұқсат, беттеу) қосады
Іске қосу:  python patch_settings.py
"""
import re
from pathlib import Path

path = Path("config/settings.py")
text = path.read_text(encoding="utf-8")
changed = []

if "load_dotenv" not in text:
    text = re.sub(r"^SECRET_KEY = .*$",
                  'SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key")',
                  text, flags=re.M)
    text = re.sub(r"^DEBUG = .*$",
                  'DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"',
                  text, flags=re.M)
    text = re.sub(r"^ALLOWED_HOSTS = .*$",
                  'ALLOWED_HOSTS = os.environ.get(\n'
                  '    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")',
                  text, flags=re.M)
    text = text.replace("from pathlib import Path",
                        "import os\nfrom pathlib import Path\n\nfrom dotenv import load_dotenv", 1)
    text = re.sub(r"^(BASE_DIR = .*)$", r'\1\n\nload_dotenv(BASE_DIR / ".env")',
                  text, count=1, flags=re.M)
    changed.append(".env баптауы")

if '"rest_framework"' not in text:
    text = text.replace('"django.contrib.staticfiles",',
                        '"django.contrib.staticfiles",\n    "rest_framework",', 1)
    changed.append("rest_framework қосымшасы")

if "REST_FRAMEWORK" not in text:
    text += '''

# Django REST Framework
REST_FRAMEWORK = {
    # оқуға — бәріне, өзгертуге — тек кірген қолданушыға
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
}
'''
    changed.append("REST_FRAMEWORK баптаулары")

path.write_text(text, encoding="utf-8")
print("Өзгертілді:", ", ".join(changed) if changed else "ештеңе (бұрын жасалған)")
