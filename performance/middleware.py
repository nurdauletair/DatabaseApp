import logging
import time
from django.conf import settings
from django.db import connection
from django.test.utils import CaptureQueriesContext

logger = logging.getLogger("perf")

class TimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.DEBUG or not settings.PERFORMANCE_LAB or not request.path.startswith("/lab11/"):
            return self.get_response(request)
        start = time.perf_counter()
        with CaptureQueriesContext(connection) as queries:
            response = self.get_response(request)
        milliseconds = (time.perf_counter() - start) * 1000
        sql_ms = sum(float(q["time"]) * 1000 for q in queries)
        logger.log(logging.WARNING if milliseconds > 300 else logging.INFO,
                   "%s %s %.3f ms, %d SQL, SQL %.3f ms", request.method, request.path,
                   milliseconds, len(queries), sql_ms)
        response["X-SQL-Count"] = str(len(queries))
        response["X-Page-Ms"] = f"{milliseconds:.3f}"
        return response
