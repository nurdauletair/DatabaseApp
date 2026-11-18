import json
from collections import Counter
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from reporting.executor import run_readonly
from reporting.guard import ReportError, validate_sql
from reporting.llm import api_configured, ask_sql


class Command(BaseCommand):
    help = "Check 10 reference queries. --run-llm additionally makes 20 PAID API calls for two prompt versions."

    def add_arguments(self, parser):
        parser.add_argument("--run-llm", action="store_true", help="Make 20 real API calls; requires your local key.")
        parser.add_argument("--output", default=".local-backups/report-evaluation.json")

    def handle(self, *args, **options):
        if options["run_llm"] and not api_configured():
            raise CommandError("Add your key to local .env first. No API calls made.")
        cases = json.loads((settings.BASE_DIR / "reporting/golden.json").read_text())
        result = {"created_at": timezone.now().isoformat(), "model": settings.OPENAI_MODEL,
                  "llm_evaluated": options["run_llm"], "cases": [], "accuracy": {},
                  "note": "No patient/result rows or API keys are stored in this file."}
        totals = {"baseline": 0, "enhanced": 0}
        for case in cases:
            row = {k: case[k] for k in ("id", "difficulty", "question")}
            try:
                reference = validate_sql(case["sql"])
                _, expected = run_readonly(reference)
            except ReportError as error:
                raise CommandError(f"Reference #{case['id']}: {error}") from None
            row.update(reference_sql=reference, reference_rows=len(expected), reference_valid=True)
            if options["run_llm"]:
                for version in totals:
                    try:
                        answer = ask_sql(case["question"], version=version)
                        _, actual = run_readonly(answer.sql)
                        good = Counter(actual) == Counter(expected)
                        row[version] = {"correct": good, "sql": answer.sql,
                                        "input_tokens": answer.input_tokens, "output_tokens": answer.output_tokens,
                                        "error_type": "" if good else "result_mismatch"}
                        totals[version] += int(good)
                    except ReportError as error:
                        row[version] = {"correct": False, "error_type": type(error).__name__, "error": str(error)}
            result["cases"].append(row)
            self.stdout.write(f"Reference {case['id']}: OK ({len(expected)} rows)")
        if options["run_llm"]:
            result["accuracy"] = {v: {"correct": n, "total": len(cases), "percent": n / len(cases) * 100} for v, n in totals.items()}
        output = Path(options["output"])
        if not output.is_absolute():
            output = settings.BASE_DIR / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        self.stdout.write(self.style.SUCCESS(f"Saved {output}. LLM evaluated: {options['run_llm']}"))
