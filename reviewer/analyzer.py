from reviewer.linter import lint_sql
from reviewer.rules import run_custom_rules


def analyze_sql(sql: str) -> dict:
    """
    Run complete static SQL analysis.

    Includes:
    - custom project rules
    - SQLFluff linting
    """

    custom_result = run_custom_rules(sql)
    sqlfluff_findings = lint_sql(sql)

    return {
        "score": custom_result["score"],
        "custom_findings": custom_result["findings"],
        "sqlfluff_findings": sqlfluff_findings,
    }