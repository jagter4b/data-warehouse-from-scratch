"""
ai_service.py — Google Gemini Integration (google-genai SDK)
─────────────────────────────────────────────────────────────
Converts Arabic/English business questions to T-SQL using Gemini.
Supports Egyptian Arabic dialect natively.
Uses the new google.genai SDK (not the deprecated google.generativeai).
"""

import json
import logging
import os
import re
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Model fallback chain ──────────────────────────────────────────────────────
# Tries models in order until one works (quota-safe)
# Use full 'models/...' names as returned by client.models.list()
_MODEL_CHAIN = [
    "models/gemini-2.5-flash-lite",   # primary — separate quota pool
    "models/gemini-2.5-flash",
    "models/gemini-3.1-flash-lite",
    "models/gemini-3.5-flash",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-lite",
    "models/gemini-flash-lite-latest",
]


def _get_api_key() -> str:
    key = (
        os.getenv("Gemini_API_Key")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )
    if not key:
        raise EnvironmentError(
            "مفتاح Gemini API غير موجود.\n"
            "Gemini API key not found.\n"
            "Set Gemini_API_Key in your .env file."
        )
    return key


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """
أنت خبير قواعد بيانات Microsoft SQL Server ومحلل ذكاء أعمال (Business Intelligence).
You are a Microsoft SQL Server expert and Business Intelligence analyst.

مهمتك: تحويل أسئلة الأعمال المكتوبة بالعربية (بما في ذلك العامية المصرية) أو الإنجليزية إلى استعلامات T-SQL صحيحة.
Your task: Convert business questions in Arabic (including Egyptian dialect) or English into correct T-SQL SELECT queries.

LANGUAGE RULES:
- Detect the language automatically.
- Reply in the SAME language as the question.
- Egyptian Arabic you must understand:
  ايه/إيه=what, فين=where, مين=who, كام/قد ايه=how many/much, ليه=why, ازاي/إزاي=how,
  اللي=that/which, عايز/محتاج=want/need, وريني/اعمللي=show me, أكتر=most/more,
  اقل=least/less, الشهر ده=this month, السنة دي=this year, امبارح=yesterday

SQL RULES:
1. Use ONLY tables from the provided schema. ALL tables belong to the 'gold' schema.
2. Always prefix table names with 'gold.' (e.g. SELECT * FROM gold.table_name).
3. Write valid T-SQL syntax (SQL Server only).
4. Generate ONLY SELECT or WITH (CTE) statements.
5. Use table aliases. Add TOP 1000 unless the question implies full aggregation.
6. Handle NULLs with COALESCE/ISNULL.
7. DATABASE DATE RANGE: The database contains historical transaction data spanning the years 2016 to 2020. When the user asks for "this year", "last year", "recent trends", or dynamic periods, target the year 2018 (which has the most complete records) or the years 2016-2020. Do NOT use functions like GETDATE() or YEAR(GETDATE()) which resolve to the current system year (e.g. 2026), as this will return 0 rows.

CRITICAL ALIAS RULES — READ CAREFULLY:
8.  Column aliases MUST use square brackets when they contain Arabic, spaces, or special characters.
    CORRECT:   SUM(col) AS [إجمالي المبيعات]
    INCORRECT: SUM(col) AS 'إجمالي المبيعات'   ← single quotes create a STRING LITERAL, NOT an alias!
9.  In ORDER BY, NEVER reference an alias by name — always repeat the full expression:
    CORRECT:   ORDER BY SUM(foi.line_total) DESC
    INCORRECT: ORDER BY [إجمالي المبيعات] DESC   ← aliases are not visible in ORDER BY in SQL Server
    INCORRECT: ORDER BY 'إجمالي المبيعات' DESC   ← this is a string constant, will cause error 408!
10. For English aliases with spaces use square brackets too: AS [Total Sales]
11. Return ONLY a valid JSON object — no markdown, no code fences, no extra text.

STRICT JSON RESPONSE FORMAT:
{
  "sql": "<the complete T-SQL SELECT query>",
  "sql_explanation": "<step-by-step SQL explanation — in the question's language>",
  "business_explanation": "<plain-language business meaning — in the question's language>",
  "chart_suggestion": "<one of: bar, line, pie, scatter, table, kpi>",
  "confidence": <integer 0-100>,
  "detected_language": "<arabic or english>"
}
""".strip()


# ── SQL post-processor ────────────────────────────────────────────────────────

def _fix_sql(sql: str) -> str:
    """
    Auto-fix common T-SQL mistakes that Gemini produces with Arabic aliases:

    1. ORDER BY 'alias'  →  ORDER BY column_position
       SQL Server error 408: constant expression in ORDER BY.
       We replace ORDER BY '<any quoted string>' with the ordinal position.

    2. AS 'alias'  →  AS [alias]
       Single-quoted aliases are not valid in T-SQL; use square brackets.
    """
    if not sql:
        return sql

    # Fix 1: AS 'alias' → AS [alias]  (single-quoted column aliases)
    sql = re.sub(
        r"\bAS\s+'([^']+)'",
        lambda m: f"AS [{m.group(1)}]",
        sql,
        flags=re.IGNORECASE,
    )

    # Fix 2: ORDER BY 'alias'  →  ORDER BY <ordinal>
    # Find all ORDER BY clauses that reference a quoted string and replace
    # with the column ordinal position of the matching SELECT alias.
    def _replace_order_by_alias(match: re.Match) -> str:
        direction = match.group(2) or ""
        alias_text = match.group(1)

        # Try to find the ordinal position of this alias in SELECT list
        select_match = re.search(
            r"SELECT\s+(?:TOP\s+\d+\s+)?(.+?)\s+FROM",
            sql, flags=re.IGNORECASE | re.DOTALL
        )
        if select_match:
            cols = [c.strip() for c in select_match.group(1).split(",")]
            for i, col in enumerate(cols, 1):
                # Check if this column has the alias we're looking for
                col_upper = col.upper()
                alias_upper = alias_text.upper()
                if (f"AS [{alias_upper}]" in col_upper
                        or f"AS {alias_upper}" in col_upper
                        or col_upper.rstrip().endswith(f"[{alias_upper}]")):
                    return f"{i} {direction}"
        # Fallback: use position 1
        return f"1 {direction}"

    sql = re.sub(
        r"(ORDER\s+BY)\s+'([^']+)'\s*(ASC|DESC)?",
        lambda m: f"{m.group(1)} {_ordinal_for_alias(m.group(2), sql)} {m.group(3) or ''}".rstrip(),
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Fix 3: ORDER BY [ArabicAlias] → ORDER BY <ordinal>
    sql = re.sub(
        r"(ORDER\s+BY)\s+\[([^\]]+)\]\s*(ASC|DESC)?",
        lambda m: (
            f"{m.group(1)} {_ordinal_for_alias(m.group(2), sql)} {m.group(3) or ''}".rstrip()
            if re.search(r"[\u0600-\u06ff]", m.group(2))
            else m.group(0)
        ),
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return sql.strip()


def _ordinal_for_alias(alias_text: str, sql: str) -> str:
    """Find the SELECT-list ordinal position (1-based) of a column alias."""
    select_match = re.search(
        r"SELECT\s+(?:TOP\s+\d+\s+)?(.+?)\s+FROM",
        sql, flags=re.IGNORECASE | re.DOTALL,
    )
    if select_match:
        cols = [c.strip() for c in select_match.group(1).split(",")]
        alias_upper = alias_text.upper().strip()
        for i, col in enumerate(cols, 1):
            col_upper = col.upper()
            if (
                f"AS [{alias_upper}]" in col_upper
                or f"AS {alias_upper}" in col_upper
                or col_upper.rstrip().endswith(f"[{alias_upper}]")
                or col_upper.rstrip().endswith(alias_upper)
            ):
                return str(i)
    return "1"  # safe fallback


# ── Generation ────────────────────────────────────────────────────────────────

def generate_sql(
    question: str,
    schema_context: str,
    model: str = "gemini-2.0-flash",
    max_tokens: int = 2048,
    temperature: float = 0.1,
    chat_history: Optional[List[dict]] = None,
) -> Dict[str, Any]:
    """
    Convert an Arabic or English question into a T-SQL SELECT query.
    Automatically falls back to lighter models if quota is exceeded.
    """
    try:
        from google import genai
        from google.genai import types as gtypes
    except ImportError:
        return _error_result(
            "google-genai not installed. Run: pip install google-genai"
        )

    try:
        api_key = _get_api_key()
    except EnvironmentError as e:
        return _error_result(str(e))

    client = genai.Client(api_key=api_key)

    user_content = (
        f"DATABASE SCHEMA (gold schema only):\n{schema_context}\n\n"
        f"BUSINESS QUESTION:\n{question}\n\n"
        "Return strict JSON only — no markdown fences."
    )

    # Build conversation history
    history = []
    if chat_history:
        for turn in chat_history[-6:]:
            role    = turn.get("role", "")
            content = turn.get("content", "")
            if role == "user" and content:
                history.append(gtypes.Content(role="user",    parts=[gtypes.Part(text=content)]))
            elif role == "assistant" and content:
                history.append(gtypes.Content(role="model",   parts=[gtypes.Part(text=content)]))

    # Try model chain — normalise short names to full names
    def _norm(m: str) -> str:
        return m if m.startswith("models/") else f"models/{m}"
    models_to_try = [_norm(model)] + [m for m in _MODEL_CHAIN if m != _norm(model)]
    last_error = ""

    for m_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=m_name,
                contents=history + [gtypes.Content(role="user", parts=[gtypes.Part(text=user_content)])],
                config=gtypes.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",
                ),
            )
            raw = response.text.strip()
            # Strip accidental markdown fences
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw.strip())

            result = json.loads(raw)
            result.setdefault("sql", "")
            result.setdefault("sql_explanation", "")
            result.setdefault("business_explanation", "")
            result.setdefault("chart_suggestion", "table")
            result.setdefault("confidence", 0)
            result.setdefault("detected_language", "english")
            result["error"] = None
            result["model_used"] = m_name

            # Auto-fix T-SQL alias / ORDER BY issues before returning
            if result["sql"]:
                result["sql"] = _fix_sql(result["sql"])

            logger.info("SQL generated via %s (lang=%s, confidence=%s)",
                        m_name, result["detected_language"], result["confidence"])
            return result

        except json.JSONDecodeError as e:
            logger.error("JSON parse error from %s: %s", m_name, e)
            return _error_result(f"الرد لم يكن JSON صحيحاً / Invalid JSON from AI: {e}")

        except Exception as e:
            err_str = str(e)
            last_error = err_str
            if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str or "quota" in err_str.lower():
                logger.warning("Quota exceeded for %s, trying next model…", m_name)
                continue
            else:
                logger.error("Gemini error on %s: %s", m_name, err_str)
                return _error_result(f"Gemini API error: {err_str}")

    return _error_result(
        f"تم استنفاد الحصة لجميع النماذج / All models quota exhausted.\n"
        f"الخطأ الأخير / Last error: {last_error}\n\n"
        "حاول مرة أخرى بعد دقيقة / Please try again in a minute."
    )


def generate_explanation(
    sql: str,
    results_preview: str,
    schema_context: str,
    lang: str = "english",
) -> str:
    """Explain a SQL query and its results in the user's language."""
    try:
        from google import genai
    except ImportError:
        return "google-genai not installed."

    try:
        api_key = _get_api_key()
    except EnvironmentError as e:
        return str(e)

    client = genai.Client(api_key=api_key)

    if lang == "arabic":
        prompt = (
            "أنت خبير ذكاء أعمال. اشرح الاستعلام التالي بالعربية البسيطة "
            "ثم فسّر ماذا تعني النتائج للأعمال في 3-5 جمل.\n\n"
            f"استعلام SQL:\n{sql}\n\n"
            f"معاينة النتائج:\n{results_preview}"
        )
    else:
        prompt = (
            "You are a BI expert. Explain this SQL query in plain English "
            "and what the results mean for the business in 3-5 sentences.\n\n"
            f"SQL:\n{sql}\n\nResults preview:\n{results_preview}"
        )

    for m_name in ["models/gemini-2.5-flash-lite", "models/gemini-3.1-flash-lite", "models/gemini-2.5-flash"]:
        try:
            response = client.models.generate_content(model=m_name, contents=prompt)
            return response.text.strip()
        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                continue
            return f"تعذّر توليد الشرح / Could not generate explanation: {e}"

    return "تم استنفاد الحصة / Quota exhausted. Try again later."


def _error_result(message: str) -> Dict[str, Any]:
    return {
        "sql": "",
        "sql_explanation": "",
        "business_explanation": "",
        "chart_suggestion": "table",
        "confidence": 0,
        "detected_language": "english",
        "model_used": "",
        "error": message,
    }
