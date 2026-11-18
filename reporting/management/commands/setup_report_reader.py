"""Provision a separate PostgreSQL role. Credentials are only written to ignored .env."""
import getpass
import os
import secrets
import psycopg
from psycopg import sql
from dotenv import set_key
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from reporting.schema import SCHEMA, VIEW_MODELS


class Command(BaseCommand):
    help = "Create/update the dedicated read-only reports role and save its password to local .env."

    def add_arguments(self, parser):
        parser.add_argument("--admin-user", default=getpass.getuser())
        parser.add_argument("--admin-host", default="", help="Empty = local Unix socket (Homebrew default).")
        parser.add_argument("--ask-password", action="store_true")

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        if not db["ENGINE"].endswith("postgresql"):
            raise CommandError("Reports execution requires PostgreSQL.")
        role = settings.REPORT_DATABASE["user"]
        if not role.startswith("clinic_report_") or role in {db.get("USER"), options["admin_user"]}:
            raise CommandError("Use a separate role named clinic_report_…")
        password = settings.REPORT_DATABASE["password"] or secrets.token_urlsafe(36)
        admin_password = getpass.getpass("PostgreSQL administrator password: ") if options["ask_password"] else os.environ.get("PGPASSWORD", "")
        try:
            with psycopg.connect(dbname=db["NAME"], user=options["admin_user"], host=options["admin_host"],
                                  port=db.get("PORT", 5432), password=admin_password, connect_timeout=3) as connection:
                if not connection.execute("SELECT rolsuper FROM pg_roles WHERE rolname=current_user").fetchone()[0]:
                    raise CommandError("Run using a PostgreSQL administrator account.")
                exists = connection.execute("SELECT oid FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
                if exists:
                    if connection.execute("SELECT 1 FROM pg_auth_members WHERE member=%s OR roleid=%s", (exists[0], exists[0])).fetchone():
                        raise CommandError("Reader must not have role memberships or members.")
                    if connection.execute("SELECT 1 FROM pg_class WHERE relowner=%s LIMIT 1", (exists[0],)).fetchone():
                        raise CommandError("Reader must not own tables or views.")
                command = "ALTER" if exists else "CREATE"
                connection.execute(sql.SQL(command + " ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
                connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(str(db["NAME"])), sql.Identifier(role)))
                connection.execute(sql.SQL("REVOKE ALL ON SCHEMA public FROM {}").format(sql.Identifier(role)))
                connection.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(sql.Identifier(role)))
                connection.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM {}").format(sql.Identifier(SCHEMA), sql.Identifier(role)))
                connection.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(SCHEMA), sql.Identifier(role)))
                connection.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM {}").format(sql.Identifier(SCHEMA), sql.Identifier(role)))
                for view in VIEW_MODELS:
                    connection.execute(sql.SQL("GRANT SELECT ON {}.{} TO {}").format(sql.Identifier(SCHEMA), sql.Identifier(view), sql.Identifier(role)))
                for setting, value in (("default_transaction_read_only", "on"), ("statement_timeout", "3s"), ("lock_timeout", "1s")):
                    connection.execute(sql.SQL("ALTER ROLE {} SET {} TO {}").format(sql.Identifier(role), sql.Identifier(setting), sql.Literal(value)))
                # Refuse privileges inherited from PUBLIC that would expose clinic source tables.
                if connection.execute("SELECT has_table_privilege(%s, 'public.accounts_user', 'SELECT') OR has_table_privilege(%s, 'public.blog_appointment', 'SELECT')", (role, role)).fetchone()[0]:
                    raise CommandError("PUBLIC grants expose source tables. Review database privileges before using reports.")
        except psycopg.Error:
            raise CommandError("Could not provision reports reader. Check administrator connection and run migrate first; no credentials printed.") from None
        env = settings.BASE_DIR / ".env"
        if not env.exists():
            env.touch(mode=0o600)
        env.chmod(0o600)
        set_key(str(env), "REPORT_DB_USER", role)
        set_key(str(env), "REPORT_DB_PASSWORD", password)
        # Leave API key creation and entry to the owner. Never replace an existing key.
        from dotenv import dotenv_values
        values = dotenv_values(env)
        if "OPENAI_API_KEY" not in values:
            set_key(str(env), "OPENAI_API_KEY", "")
        if "OPENAI_MODEL" not in values:
            set_key(str(env), "OPENAI_MODEL", "gpt-5.4-mini")
        self.stdout.write(self.style.SUCCESS("Reports reader ready; credentials saved only to local .env. Restart Django."))
