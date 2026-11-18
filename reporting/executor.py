import psycopg
from django.conf import settings
from .guard import MAX_ROWS, ReportError, validate_sql


def reader_configured():
    return bool(settings.REPORT_DATABASE.get("password")) and settings.DATABASES["default"]["ENGINE"].endswith("postgresql")


def reader_connection():
    if not reader_configured():
        raise ReportError("Есеп дерекқорына қосылу бапталмаған. Әкімшіге хабарласыңыз.")
    config = dict(settings.REPORT_DATABASE)
    if config["user"] == settings.DATABASES["default"].get("USER"):
        raise ReportError("Есептерге бөлек тек оқитын пайдаланушы қажет.")
    return psycopg.connect(**config, connect_timeout=3, options=(
        "-c default_transaction_read_only=on -c statement_timeout=3000 "
        "-c lock_timeout=1000 -c search_path=pg_catalog,clinic_reports -c timezone=Asia/Almaty"
    ))


def run_readonly(sql):
    # Revalidate even when called outside the view/LLM wrapper.
    checked = validate_sql(sql)
    try:
        with reader_connection() as connection:
            flags = connection.execute("""SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls,
                current_setting('transaction_read_only') FROM pg_catalog.pg_roles WHERE rolname = current_user""").fetchone()
            if not flags or any(flags[:4]) or flags[4] != "on":
                raise ReportError("Есеп пайдаланушысының құқықтары қауіпсіз емес.")
            cursor = connection.execute(checked, prepare=False)
            return [c.name for c in cursor.description], cursor.fetchmany(MAX_ROWS)
    except psycopg.errors.QueryCanceled:
        raise ReportError("Сұраныс 3 секундтан асты. Сұрақты жеңілдетіңіз.") from None
    except psycopg.Error:
        raise ReportError("Есепті орындау мүмкін болмады. Сұрақты өзгертіңіз немесе әкімшіге хабарласыңыз.") from None
