from sqlalchemy.orm import Session

from reviewer.ai_reviewer import get_ai_review
from reviewer.explain import explain_query
from reviewer.linter import lint_sql
from reviewer.rules import run_custom_rules


def analyze_sql(
    sql: str,
    include_ai: bool = False,
    include_explain: bool = False,
    db: Session | None = None,
) -> dict:
    """
    Run SQL review.

    Includes:
    - custom deterministic rules
    - SQLFluff static analysis
    - optional PostgreSQL EXPLAIN
    - optional Ollama AI review
    """

    custom_result = run_custom_rules(sql)
    sqlfluff_findings = lint_sql(sql)

    result = {
        "score": custom_result["score"],
        "custom_findings": custom_result["findings"],
        "sqlfluff_findings": sqlfluff_findings,
        "explain": None,
        "ai_review": None,
    }

    if include_explain:
        if db is None:
            result["explain"] = {
                "available": False,
                "reason": "Database session was not provided.",
                "plan": [],
            }
        else:
            result["explain"] = explain_query(
                db=db,
                sql=sql,
            )

    if include_ai:
        result["ai_review"] = get_ai_review(
            sql=sql,
            custom_findings=custom_result["findings"],
            sqlfluff_findings=sqlfluff_findings,
        )

    return result