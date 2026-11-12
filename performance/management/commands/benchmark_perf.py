import hashlib
import json
from pathlib import Path
import re
import statistics
import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import connection
from django.test import Client, RequestFactory, override_settings
from django.urls import resolve
from django.utils import timezone


class SQLTimer:
    def __init__(self):
        self.durations = []

    def __call__(self, execute, sql, params, many, context):
        start = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            self.durations.append((time.perf_counter() - start) * 1000)


class Command(BaseCommand):
    help = "Five real measurements: business view and full session-authenticated HTTP stack."

    def add_arguments(self, parser):
        parser.add_argument("--path", default="/lab11/slow/")
        parser.add_argument("--stage", required=True)
        parser.add_argument("--cache-mode", choices=["none", "miss", "hit"], default="none")
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        user = get_user_model().objects.get(username="demo_admin")
        path = options["path"]
        view = resolve(path).func
        factory, client = RequestFactory(), Client()
        client.force_login(user)

        def direct():
            request = factory.get(path, HTTP_HOST="localhost")
            request.user, request.session = user, SessionStore()
            return view(request)

        def full():
            return client.get(path, HTTP_HOST="localhost")

        def series(function):
            cache.clear()
            if options["cache_mode"] == "hit":
                function()
            results = []
            for _ in range(5):
                if options["cache_mode"] == "miss":
                    cache.clear()
                timer = SQLTimer()
                start = time.perf_counter()
                with connection.execute_wrapper(timer):
                    response = function()
                elapsed = (time.perf_counter() - start) * 1000
                if response.status_code != 200:
                    raise RuntimeError(f"{path}: HTTP {response.status_code}")
                match = re.search(rb"<tbody>(.*?)</tbody>", response.content, re.S)
                results.append({"sql_count": len(timer.durations), "sql_ms": sum(timer.durations),
                                "page_ms": elapsed, "table_sha256": hashlib.sha256(match.group(1)).hexdigest()})
            return {"samples": results, "median": {key: statistics.median(row[key] for row in results)
                    for key in ("sql_count", "sql_ms", "page_ms")}}

        # Keep Toolbar UI overhead out of reproducible measurements.
        middleware = [m for m in settings.MIDDLEWARE
                      if "debug_toolbar" not in m]
        with override_settings(ALLOWED_HOSTS=["localhost", "testserver"], MIDDLEWARE=middleware):
            data = {"stage": options["stage"], "path": path, "cache_mode": options["cache_mode"],
                    "measured_at": timezone.localtime().isoformat(), "backend": connection.vendor,
                    "repetitions": 5, "business": series(direct), "http": series(full)}
        client.logout()
        target = Path(options["output"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        self.stdout.write(json.dumps({"stage": data["stage"], "business": data["business"]["median"],
                                     "http": data["http"]["median"]}, ensure_ascii=False))
