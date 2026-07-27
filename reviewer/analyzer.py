from reviewer.rules import run_custom_rules


def analyze_sql(sql: str) -> dict:
    """
    Main entry point for SQL analysis.

    SQLFluff, PostgreSQL EXPLAIN and AI analysis
    will be added here later.
    """

    custom_result = run_custom_rules(sql)

    return {
        "score": custom_result["score"],
        "custom_findings": custom_result["findings"],
    }