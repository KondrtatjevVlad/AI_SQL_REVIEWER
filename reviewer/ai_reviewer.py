import json
import os
import re

import sqlfluff
from ollama import Client

from reviewer.linter import lint_sql
from reviewer.model_registry import DEFAULT_MODEL_KEY, get_model
from reviewer.rules import run_custom_rules
from reviewer.scoring import calculate_overall_score, calculate_quality_score


OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

MAX_AI_ATTEMPTS = 3
MAX_SQLFLUFF_FIX_PASSES = 3

SQLFLUFF_RULE_INFO = {
    "LT01": "Исправить пробелы и форматирование.",
    "LT09": "Разместить элементы SELECT на отдельных строках.",
    "LT12": "Корректно завершить SQL переносом строки.",
    "LT13": "Убрать лишние пробелы в начале SQL.",
    "AL01": "Привести стиль псевдонимов к требованиям SQLFluff.",
    "AM04": "SELECT * требует явного списка столбцов.",
    "AM05": "Сделать тип существующего JOIN явным.",
    "ST09": "Исправить порядок ссылок в условии JOIN.",
    "PRS": "Исправить синтаксическую ошибку.",
}

NO_ALT_REASONS = {
    "SELECT_STAR": (
        "Нельзя корректно заменить SELECT * без знания того, "
        "какие именно столбцы должны возвращаться."
    ),
    "MANY_JOINS": (
        "Нельзя автоматически удалить или заменить JOIN без знания "
        "связей и бизнес-смысла запроса."
    ),
    "DELETE_WITHOUT_WHERE": (
        "Нельзя придумывать WHERE для DELETE без знания того, "
        "какие строки требуется удалить."
    ),
    "UPDATE_WITHOUT_WHERE": (
        "Нельзя придумывать WHERE для UPDATE без знания того, "
        "какие строки требуется изменить."
    ),
    "DROP": (
        "DROP нельзя автоматически заменить другой операцией "
        "без знания намерения пользователя."
    ),
    "TRUNCATE": (
        "TRUNCATE нельзя автоматически заменить другой операцией "
        "без знания намерения пользователя."
    ),
}

FIX_SYSTEM_PROMPT = (
    "Ты эксперт по PostgreSQL.\n\n"
    "Исправь только очевидную синтаксическую ошибку в SQL.\n"
    "Сохрани таблицы, столбцы, значения, числа, фильтры и смысл запроса.\n"
    "Не придумывай новые таблицы, столбцы, WHERE, JOIN или значения.\n"
    "Верни только один полный SQL в блоке ```sql ... ```."
)

SUMMARY_SYSTEM_PROMPT = (
    "Ты эксперт по PostgreSQL. Ответь только на русском языке.\n"
    "Кратко объясни, что изменилось между исходным и рекомендуемым SQL.\n"
    "Не пересчитывай оценки, не придумывай новые проблемы и "
    "не предлагай другой SQL. Максимум четыре коротких предложения."
)

CASE_FUNCTION_LIKE_PATTERN = re.compile(
    r"\b(?:LOWER|UPPER)\s*\(\s*"
    r"(?P<column>(?:\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\.(?:\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_]*))?)\s*\)"
    r"\s*(?:LIKE|ILIKE)\s*"
    r"(?P<literal>'(?:''|[^'])*')",
    re.IGNORECASE,
)

LIKE_LITERAL_PATTERN = re.compile(
    r"\b(?P<operator>LIKE|ILIKE)\s*(?P<literal>'(?:''|[^'])*')",
    re.IGNORECASE,
)


def analyze_candidate_sql(sql: str) -> dict:
    custom = run_custom_rules(sql)
    raw_lint = lint_sql(sql)
    quality = calculate_quality_score(raw_lint)
    sqlfluff_findings = quality["findings"]
    overall = calculate_overall_score(
        risk_score=custom["score"],
        quality_score=quality["score"],
        custom_findings=custom["findings"],
        sqlfluff_findings=sqlfluff_findings,
    )
    return {
        "risk_score": custom["score"],
        "quality_score": quality["score"],
        "overall_score": overall,
        "custom_findings": custom["findings"],
        "sqlfluff_findings": sqlfluff_findings,
    }


def get_codes(findings: list[dict]) -> set[str]:
    return {f.get("code") for f in findings if f.get("code")}


def get_remaining_codes(analysis: dict) -> list[str]:
    result = []
    for finding in analysis["custom_findings"] + analysis["sqlfluff_findings"]:
        code = finding.get("code")
        if code and code not in result:
            result.append(code)
    return result


def is_perfect(analysis: dict) -> bool:
    return (
        analysis["risk_score"] == 10
        and analysis["quality_score"] == 10
        and analysis["overall_score"] == 10
        and not analysis["custom_findings"]
        and not analysis["sqlfluff_findings"]
    )


def rank(analysis: dict) -> tuple:
    count = len(analysis["custom_findings"]) + len(analysis["sqlfluff_findings"])
    return (
        analysis["overall_score"],
        analysis["quality_score"],
        analysis["risk_score"],
        -count,
    )


def has_prs(analysis: dict) -> bool:
    return "PRS" in get_codes(analysis["sqlfluff_findings"])


def apply_safe_custom_fixes(sql: str) -> str:
    def replace(match: re.Match) -> str:
        return f"{match.group('column')} ILIKE {match.group('literal')}"

    return CASE_FUNCTION_LIKE_PATTERN.sub(replace, sql)


def sqlfluff_autofix(sql: str) -> str:
    current = sql.strip()
    if not current or has_prs(analyze_candidate_sql(current)):
        return current

    for _ in range(MAX_SQLFLUFF_FIX_PASSES):
        try:
            fixed = sqlfluff.fix(
                current.rstrip() + "\n",
                dialect="postgres",
                fix_even_unparsable=False,
            ).strip()
        except Exception:
            return current

        if not fixed or fixed == current:
            break

        current = fixed
        analysis = analyze_candidate_sql(current)

        if not analysis["sqlfluff_findings"] or has_prs(analysis):
            break

    return current


def run_safe_fix_pipeline(sql: str) -> str:
    result = sqlfluff_autofix(sql)
    result = apply_safe_custom_fixes(result)
    result = sqlfluff_autofix(result)
    return result.strip()


def extract_sql_from_ai(text: str) -> str | None:
    match = re.search(r"```sql\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def prepare_sqlfluff_findings(findings: list[dict]) -> list[dict]:
    result = []
    for finding in findings:
        code = finding.get("code", "UNKNOWN")
        result.append(
            {
                "code": code,
                "line": finding.get("line"),
                "position": finding.get("position"),
                "description_ru": SQLFLUFF_RULE_INFO.get(
                    code,
                    f"Исправить нарушение SQLFluff {code}.",
                ),
            }
        )
    return result


def try_ai_syntax_fix(
    client: Client,
    model_name: str,
    sql: str,
    analysis: dict,
) -> tuple[str, dict]:
    best_sql = sql
    best_analysis = analysis

    for _ in range(MAX_AI_ATTEMPTS):
        prompt = (
            "Исправь синтаксис следующего PostgreSQL-запроса.\n\n"
            "```sql\n"
            f"{best_sql}\n"
            "```\n\n"
            "Ошибки SQLFluff:\n"
            f"{json.dumps(prepare_sqlfluff_findings(best_analysis['sqlfluff_findings']), ensure_ascii=False)}"
        )

        response = client.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": FIX_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0},
            keep_alive="2m",
        )

        ai_sql = extract_sql_from_ai(response.message.content)
        if not ai_sql:
            break

        candidate_sql = run_safe_fix_pipeline(ai_sql)
        candidate_analysis = analyze_candidate_sql(candidate_sql)

        if rank(candidate_analysis) > rank(best_analysis):
            best_sql = candidate_sql
            best_analysis = candidate_analysis

        if not has_prs(candidate_analysis):
            break

    return best_sql, best_analysis


def transform_leading_wildcard(sql: str, mode: str) -> str:
    def replace(match: re.Match) -> str:
        operator = match.group("operator")
        literal = match.group("literal")
        content = literal[1:-1]

        if not content.startswith("%"):
            return match.group(0)

        without_leading = content.lstrip("%")

        if mode == "prefix":
            new_content = without_leading
        elif mode == "exact":
            stripped = without_leading.rstrip("%")
            if "%" in stripped or "_" in stripped:
                return match.group(0)
            new_content = stripped
        else:
            return match.group(0)

        return f"{operator} '{new_content}'"

    return LIKE_LITERAL_PATTERN.sub(replace, sql)


def generate_alternative_candidates(sql: str, analysis: dict) -> list[dict]:
    """
    Универсальная точка расширения.

    Для каждого правила, для которого можно сформировать осмысленный
    компромиссный SQL-вариант, здесь добавляется стратегия.
    """
    codes = get_codes(analysis["custom_findings"])
    candidates = []

    if "LEADING_WILDCARD" in codes:
        prefix_sql = transform_leading_wildcard(sql, "prefix")
        if prefix_sql != sql:
            candidates.append(
                {
                    "title": "Поиск только с начала строки",
                    "sql": prefix_sql,
                    "warning": (
                        "Изменяет смысл поиска: совпадение будет искаться "
                        "только с начала значения."
                    ),
                }
            )

        exact_sql = transform_leading_wildcard(sql, "exact")
        if exact_sql not in {sql, prefix_sql}:
            candidates.append(
                {
                    "title": "Точное совпадение",
                    "sql": exact_sql,
                    "warning": (
                        "Сильнее изменяет смысл: wildcard удаляется, "
                        "поэтому условие перестаёт искать подстроку."
                    ),
                }
            )

    return candidates


def score_alternatives(
    safe_sql: str,
    safe_analysis: dict,
) -> tuple[list[dict], list[str]]:
    scored = []
    seen = {safe_sql.strip()}

    for candidate in generate_alternative_candidates(safe_sql, safe_analysis):
        candidate_sql = run_safe_fix_pipeline(candidate["sql"])
        normalized = candidate_sql.strip()

        if not normalized or normalized in seen:
            continue
        seen.add(normalized)

        candidate_analysis = analyze_candidate_sql(candidate_sql)

        if rank(candidate_analysis) <= rank(safe_analysis):
            continue

        scored.append(
            {
                **candidate,
                "sql": candidate_sql,
                "analysis": candidate_analysis,
            }
        )

    scored.sort(key=lambda item: rank(item["analysis"]), reverse=True)

    reasons = []
    for code in sorted(get_codes(safe_analysis["custom_findings"])):
        reason = NO_ALT_REASONS.get(code)
        if reason:
            reasons.append(f"{code}: {reason}")

    return scored, reasons


def build_recommendations(
    original_analysis: dict,
    safe_analysis: dict,
) -> str:
    original_codes = (
        get_codes(original_analysis["custom_findings"])
        | get_codes(original_analysis["sqlfluff_findings"])
    )
    final_codes = (
        get_codes(safe_analysis["custom_findings"])
        | get_codes(safe_analysis["sqlfluff_findings"])
    )
    fixed = original_codes - final_codes

    lines = []

    if fixed:
        lines.append("Автоматически исправлены: " + ", ".join(sorted(fixed)) + ".")

    if "FUNCTION_IN_WHERE" in fixed:
        lines.append(
            "LOWER/UPPER перед LIKE заменён на ILIKE без изменения шаблона поиска."
        )

    if "LEADING_WILDCARD" in final_codes:
        lines.append(
            "Ведущий % сохранён в рекомендуемом варианте, "
            "потому что его удаление меняет смысл поиска."
        )

    if "SELECT_STAR" in final_codes or "AM04" in final_codes:
        lines.append(
            "SELECT * не заменяется неизвестными столбцами без информации о схеме."
        )

    if "MANY_JOINS" in final_codes:
        lines.append(
            "JOIN не удаляются автоматически, потому что это может изменить результат."
        )

    if "DELETE_WITHOUT_WHERE" in final_codes:
        lines.append(
            "WHERE для DELETE нельзя придумывать без знания нужных строк."
        )

    if "UPDATE_WITHOUT_WHERE" in final_codes:
        lines.append(
            "WHERE для UPDATE нельзя придумывать без знания нужных строк."
        )

    if "PRS" in final_codes:
        lines.append(
            "Синтаксическую ошибку не удалось исправить однозначно."
        )

    if not final_codes:
        lines.append("Все обнаруженные нарушения устранены.")

    if not lines:
        lines.append(
            "Запрос улучшен настолько, насколько это можно сделать "
            "без изменения его смысла."
        )

    return "\n\n".join(f"- {line}" for line in lines)


def get_ai_summary(
    client: Client,
    model_name: str,
    original_sql: str,
    safe_sql: str,
    original_analysis: dict,
    safe_analysis: dict,
) -> str | None:
    prompt = (
        "Исходный SQL:\n"
        "```sql\n"
        f"{original_sql}\n"
        "```\n\n"
        "Рекомендуемый SQL:\n"
        "```sql\n"
        f"{safe_sql}\n"
        "```\n\n"
        f"Исходные нарушения: {get_remaining_codes(original_analysis)}\n"
        f"Оставшиеся нарушения: {get_remaining_codes(safe_analysis)}"
    )

    try:
        response = client.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0},
            keep_alive=0,
        )
        text = response.message.content.strip()
        return text or None
    except Exception:
        return None


def score_block(analysis: dict) -> str:
    return (
        f"**Оценка рисков:** {analysis['risk_score']}/10  \n"
        f"**Качество SQL:** {analysis['quality_score']}/10  \n"
        f"**Итоговая оценка:** {analysis['overall_score']}/10"
    )


def alternatives_report(
    alternatives: list[dict],
    unavailable_reasons: list[str],
) -> str:
    result = "### Альтернативные варианты\n\n"

    if not alternatives:
        result += (
            "Дополнительных SQL-вариантов, которые можно корректно "
            "сформировать и автоматически проверить, не найдено."
        )

    for index, item in enumerate(alternatives, start=1):
        analysis = item["analysis"]
        result += (
            f"\n\n#### Вариант {index} — {item['title']}\n\n"
            f"⚠️ {item['warning']}\n\n"
            "```sql\n"
            f"{item['sql'].strip()}\n"
            "```\n\n"
            f"{score_block(analysis)}"
        )

        if is_perfect(analysis):
            result += (
                "\n\nЭтот вариант получил 10/10 по текущим "
                "автоматическим правилам приложения."
            )
        else:
            remaining = get_remaining_codes(analysis)
            if remaining:
                result += "\n\nОстались нарушения: " + ", ".join(remaining) + "."

    if unavailable_reasons:
        result += "\n\n#### Где альтернативу нельзя построить автоматически\n\n"
        result += "\n".join(f"- {reason}" for reason in unavailable_reasons)

    return result


def build_report(
    model_display_name: str,
    original_analysis: dict,
    safe_sql: str,
    safe_analysis: dict,
    ai_summary: str | None,
    alternatives: list[dict],
    unavailable_reasons: list[str],
) -> str:
    result = (
        f"## AI-разбор — {model_display_name}\n\n"
        "### Итог исходного запроса\n\n"
        f"{score_block(original_analysis)}\n\n"
        "### Что удалось улучшить\n\n"
        f"{build_recommendations(original_analysis, safe_analysis)}\n\n"
    )

    if ai_summary:
        result += f"### Комментарий модели\n\n{ai_summary}\n\n"

    result += (
        "### Рекомендуемый SQL — смысл сохранён\n\n"
        "```sql\n"
        f"{safe_sql.strip()}\n"
        "```\n\n"
        "### Проверка рекомендуемого SQL\n\n"
        f"{score_block(safe_analysis)}\n\n"
    )

    if is_perfect(safe_analysis):
        result += "Рекомендуемый SQL прошёл Custom Rules и SQLFluff без нарушений."
    else:
        remaining = get_remaining_codes(safe_analysis)
        result += (
            "Это максимальное автоматическое улучшение "
            "без намеренного изменения смысла запроса."
        )
        if remaining:
            result += "\n\n**Остались нарушения:** " + ", ".join(remaining) + "."

    result += "\n\n" + alternatives_report(alternatives, unavailable_reasons)
    return result


def get_ai_review(
    sql: str,
    custom_findings: list[dict],
    sqlfluff_findings: list[dict],
    risk_score: float,
    quality_score: float,
    overall_score: float,
    model_key: str = DEFAULT_MODEL_KEY,
) -> str:
    original_sql = sql.strip()

    original_analysis = {
        "risk_score": risk_score,
        "quality_score": quality_score,
        "overall_score": overall_score,
        "custom_findings": custom_findings,
        "sqlfluff_findings": sqlfluff_findings,
    }

    model = get_model(model_key)
    client = Client(host=OLLAMA_HOST)

    safe_sql = run_safe_fix_pipeline(original_sql)
    safe_analysis = analyze_candidate_sql(safe_sql)

    if has_prs(safe_analysis):
        ai_sql, ai_analysis = try_ai_syntax_fix(
            client,
            model.ollama_name,
            safe_sql,
            safe_analysis,
        )
        if rank(ai_analysis) > rank(safe_analysis):
            safe_sql = ai_sql
            safe_analysis = ai_analysis

    alternatives, unavailable_reasons = score_alternatives(
        safe_sql,
        safe_analysis,
    )

    ai_summary = get_ai_summary(
        client,
        model.ollama_name,
        original_sql,
        safe_sql,
        original_analysis,
        safe_analysis,
    )

    return build_report(
        model.display_name,
        original_analysis,
        safe_sql,
        safe_analysis,
        ai_summary,
        alternatives,
        unavailable_reasons,
    )