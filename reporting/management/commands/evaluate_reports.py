import hashlib
import json
from collections import Counter
from pathlib import Path
from time import perf_counter
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from reporting.executor import run_readonly
from reporting.guard import ReportError, validate_sql
from reporting.llm import api_configured, ask_sql
from reporting.prompts import system_prompt


class Command(BaseCommand):
    help = "Check 10 reference queries. --run-llm additionally makes 20 PAID API calls for two prompt versions."

    def add_arguments(self, parser):
        parser.add_argument("--run-llm", action="store_true", help="Make 20 real API calls; requires your local key.")
        parser.add_argument("--output", default=".local-backups/report-evaluation.json")

    def handle(self, *args, **options):
        if options["run_llm"] and not api_configured():
            raise CommandError("Add your key to local .env first. No API calls made.")
        cases = json.loads((settings.BASE_DIR / "reporting/golden.json").read_text())
        output = Path(options["output"])
        if not output.is_absolute():
            output = settings.BASE_DIR / output
        output.parent.mkdir(parents=True, exist_ok=True)
        prompts = {v: system_prompt(v) for v in ("baseline", "enhanced")}
        result = {"created_at": timezone.now().isoformat(), "date_context": timezone.localdate().isoformat(),
                  "model": settings.OPENAI_MODEL, "llm_evaluated": options["run_llm"], "complete": False,
                  "cases": [], "accuracy": {}, "api_calls_attempted": 0,
                  "prompts": prompts,
                  "prompt_sha256": {v: hashlib.sha256(p.encode()).hexdigest() for v, p in prompts.items()},
                  "note": "Only schema, questions and SQL; no API keys or database result rows are stored."}

        def save():
            temporary = output.with_suffix(output.suffix + ".tmp")
            temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            temporary.replace(output)

        save()
        totals = {"baseline": 0, "enhanced": 0}
        # Check every reference before making the first paid request.
        expected_rows = {}
        for case in cases:
            row = {k: case[k] for k in ("id", "difficulty", "question")}
            try:
                reference = validate_sql(case["sql"])
                _, expected = run_readonly(reference)
            except ReportError as error:
                raise CommandError(f"Reference #{case['id']}: {error}") from None
            row.update(reference_sql=reference, reference_rows=len(expected), reference_valid=True,
                       empty_reference=not expected)
            expected_rows[case["id"]] = expected
            result["cases"].append(row)
        save()
        for case, row in zip(cases, result["cases"], strict=True):
            if options["run_llm"]:
                for version in totals:
                    started = perf_counter()
                    answer = None
                    result["api_calls_attempted"] += 1
                    try:
                        answer = ask_sql(case["question"], version=version)
                        _, actual = run_readonly(answer.sql)
                        good = Counter(actual) == Counter(expected_rows[case["id"]])
                        row[version] = {"correct": good, "sql": answer.sql, "result_rows": len(actual),
                                        "input_tokens": answer.input_tokens, "output_tokens": answer.output_tokens,
                                        "error_type": "" if good else "result_mismatch"}
                        totals[version] += int(good)
                    except ReportError as error:
                        row[version] = {"correct": False, "error_type": type(error).__name__, "error": str(error),
                                        "sql": answer.sql if answer else getattr(error, "sql", "")}
                        if answer:
                            row[version].update(input_tokens=answer.input_tokens, output_tokens=answer.output_tokens)
                    row[version]["elapsed_ms"] = round((perf_counter() - started) * 1000)
                    save()
                    self.stdout.write(f"Question {case['id']}/10 {version}: {'PASS' if row[version]['correct'] else row[version]['error_type']}")
                    self.stdout.flush()
            else:
                self.stdout.write(f"Reference {case['id']}: OK ({row['reference_rows']} rows)")
        if options["run_llm"]:
            result["accuracy"] = {v: {"correct": n, "total": len(cases), "percent": n / len(cases) * 100} for v, n in totals.items()}
        result.update(complete=True, completed_at=timezone.now().isoformat())
        save()
        self.stdout.write(self.style.SUCCESS(f"Saved {output}. LLM evaluated: {options['run_llm']}"))
