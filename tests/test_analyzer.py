from reviewer.analyzer import analyze_sql


def test_clean_query_gets_three_max_scores():
    sql = """SELECT
    id,
    username
FROM users
WHERE id = 1;
"""

    result = analyze_sql(
        sql,
        include_ai=False,
        include_explain=False,
    )

    assert result["risk_score"] == 10
    assert result["quality_score"] == 10.0
    assert result["overall_score"] == 10.0

    assert result["custom_findings"] == []
    assert result["sqlfluff_findings"] == []
    assert result["ai_review"] is None
    assert result["explain"] is None


def test_select_star_affects_both_analysis_layers():
    sql = """SELECT *
FROM users;
"""

    result = analyze_sql(
        sql,
        include_ai=False,
        include_explain=False,
    )

    custom_codes = {
        finding["code"]
        for finding in result["custom_findings"]
    }

    sqlfluff_codes = {
        finding["code"]
        for finding in result["sqlfluff_findings"]
    }

    assert result["risk_score"] == 9
    assert "SELECT_STAR" in custom_codes
    assert "AM04" in sqlfluff_codes
    assert result["quality_score"] < 10
    assert result["overall_score"] < 10


def test_parse_error_limits_overall_score():
    sql = """SELECT id
FROM users
WHERE = 1;
"""

    result = analyze_sql(
        sql,
        include_ai=False,
        include_explain=False,
    )

    codes = {
        finding["code"]
        for finding in result["sqlfluff_findings"]
    }

    assert "PRS" in codes
    assert result["overall_score"] <= 4.0


def test_explain_without_database_session_is_handled():
    result = analyze_sql(
        "SELECT 1;",
        include_ai=False,
        include_explain=True,
        db=None,
    )

    assert result["explain"] is not None
    assert result["explain"]["available"] is False
    assert result["explain"]["plan"] == []
