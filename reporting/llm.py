from dataclasses import dataclass
from django.conf import settings
from django.views.decorators.debug import sensitive_variables
from openai import OpenAI, APIError, AuthenticationError, RateLimitError, APITimeoutError, APIConnectionError
from .guard import ReportError, extract_sql, validate_sql
from .prompts import system_prompt


@dataclass(frozen=True)
class SQLAnswer:
    sql: str
    input_tokens: int = 0
    output_tokens: int = 0


def api_configured():
    key = settings.OPENAI_API_KEY.strip()
    return bool(key) and not key.startswith(("replace-", "your-", "sk-your", "вставь"))


@sensitive_variables("key", "client")
def ask_sql(question, version="enhanced"):
    if not api_configured():
        raise ReportError("Есеп көмекшісі әзірге қосылмаған. Әкімшіге хабарласыңыз.")
    key = settings.OPENAI_API_KEY.strip()
    try:
        # Fixed official endpoint: OPENAI_BASE_URL cannot redirect our key.
        with OpenAI(api_key=key, base_url="https://api.openai.com/v1", timeout=20.0, max_retries=0) as client:
            response = client.responses.create(
                model=settings.OPENAI_MODEL,
                instructions=system_prompt(version),
                input=question,
                reasoning={"effort": "none"},
                max_output_tokens=700,
                store=False,
            )
    except AuthenticationError:
        raise ReportError("OpenAI кілті қабылданбады. Әкімші кілтті тексеруі керек.") from None
    except RateLimitError:
        raise ReportError("OpenAI лимиті немесе баланс таусылды. Әкімшіге хабарласыңыз.") from None
    except (APITimeoutError, APIConnectionError):
        raise ReportError("OpenAI уақытша қолжетімсіз. Кейінірек қайталаңыз.") from None
    except APIError:
        raise ReportError("OpenAI сұранысты орындай алмады. Әкімші модель баптауын тексеруі керек.") from None
    if response.status != "completed":
        raise ReportError("Модель толық SQL қайтармады. Сұрақты жеңілдетіңіз.")
    raw = extract_sql(response.output_text)
    try:
        sql = validate_sql(raw)
    except ReportError as error:
        # Only model SQL, never provider exceptions/headers, is retained for audit.
        error.sql = raw[:6000]
        raise
    usage = response.usage
    return SQLAnswer(sql, usage.input_tokens if usage else 0, usage.output_tokens if usage else 0)
