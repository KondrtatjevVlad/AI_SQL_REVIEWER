import re

from sqlalchemy import text
from sqlalchemy.orm import Session


def is_safe_select(sql: str) -> bool:
    """Разрешает EXPLAIN только для одного SELECT-запроса."""

    if not sql or not sql.strip():
        return False

    cleaned_sql = sql.strip()

    if cleaned_sql.endswith(";"):
        cleaned_sql = cleaned_sql[:-1].strip()

    # Несколько SQL-команд запрещены.
    if ";" in cleaned_sql:
        return False

    # Для EXPLAIN разрешаем только SELECT.
    if not re.match(
        r"^\s*SELECT\b",
        cleaned_sql,
        re.IGNORECASE,
    ):
        return False

    dangerous_keywords = (
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "TRUNCATE",
        "ALTER",
        "CREATE",
        "GRANT",
        "REVOKE",
    )

    for keyword in dangerous_keywords:
        if re.search(
            rf"\b{keyword}\b",
            cleaned_sql,
            re.IGNORECASE,
        ):
            return False

    return True


def explain_query(
    db: Session,
    sql: str,
) -> dict:
    """Получает план PostgreSQL EXPLAIN без EXPLAIN ANALYZE."""

    if not is_safe_select(sql):
        return {
            "available": False,
            "reason": (
                "EXPLAIN доступен только для одного "
                "безопасного SELECT-запроса."
            ),
            "plan": [],
        }

    cleaned_sql = sql.strip().rstrip(";")

    try:
        db.execute(
            text("SET TRANSACTION READ ONLY")
        )

        db.execute(
            text(
                "SET LOCAL statement_timeout = '2000ms'"
            )
        )

        result = db.execute(
            text(
                f"EXPLAIN {cleaned_sql}"
            )
        )

        plan = [
            row[0]
            for row in result.fetchall()
        ]

        db.rollback()

        return {
            "available": True,
            "reason": None,
            "plan": plan,
        }

    except Exception as exc:
        db.rollback()

        return {
            "available": False,
            "reason": (
                "Не удалось получить план выполнения PostgreSQL. "
                f"Техническая причина: {exc}"
            ),
            "plan": [],
        }