from sqlalchemy.orm import Session

from reviewer.ai_reviewer import get_ai_review
from reviewer.explain import explain_query
from reviewer.linter import lint_sql
from reviewer.rules import run_custom_rules
from reviewer.scoring import (
    calculate_overall_score,
    calculate_quality_score,
)


def analyze_sql(
    sql: str,
    include_ai: bool = False,
    include_explain: bool = False,
    db: Session | None = None,
) -> dict:
    """
    Выполняет полный анализ SQL-запроса.

    Оценка рисков:
        формируется нашими детерминированными правилами.

    Оценка качества:
        формируется на основе SQLFluff.

    Итоговая оценка:
        60% риски + 40% качество SQL.
    """

    custom_result = run_custom_rules(
        sql
    )

    raw_sqlfluff_findings = lint_sql(
        sql
    )

    quality_result = calculate_quality_score(
        raw_sqlfluff_findings
    )

    risk_score = custom_result["score"]

    quality_score = quality_result["score"]

    sqlfluff_findings = quality_result[
        "findings"
    ]

    overall_score = calculate_overall_score(
        risk_score=risk_score,
        quality_score=quality_score,
        custom_findings=custom_result["findings"],
        sqlfluff_findings=sqlfluff_findings,
    )

    result = {
        # Три независимых показателя.
        "risk_score": risk_score,
        "quality_score": quality_score,
        "overall_score": overall_score,

        # Округлённая итоговая оценка используется
        # для текущего поля score в PostgreSQL.
        "score": int(
            round(overall_score)
        ),

        "custom_findings": custom_result[
            "findings"
        ],

        "sqlfluff_findings": sqlfluff_findings,

        "explain": None,
        "ai_review": None,
    }

    if include_explain:
        if db is None:
            result["explain"] = {
                "available": False,
                "reason": (
                    "Для выполнения EXPLAIN не была "
                    "передана сессия базы данных."
                ),
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
            custom_findings=result[
                "custom_findings"
            ],
            sqlfluff_findings=result[
                "sqlfluff_findings"
            ],
            risk_score=risk_score,
            quality_score=quality_score,
            overall_score=overall_score,
        )

    return result