from reviewer.linter import lint_sql


def test_clean_sql_has_no_sqlfluff_findings():
    sql = """SELECT
    id,
    username
FROM users
WHERE id = 1;"""

    result = lint_sql(sql)

    assert result == []


def test_select_star_is_detected_by_sqlfluff():
    sql = """SELECT *
FROM users;"""

    result = lint_sql(sql)

    codes = {
        finding["code"]
        for finding in result
    }

    assert "AM04" in codes


def test_invalid_sql_has_parse_error():
    sql = """SELECT id
FROM users
WHERE = 1;"""

    result = lint_sql(sql)

    codes = {
        finding["code"]
        for finding in result
    }

    assert "PRS" in codes


def test_linter_normalizes_trailing_newline():
    result = lint_sql(
        "SELECT 1;"
    )

    codes = {
        finding["code"]
        for finding in result
    }

    assert "LT12" not in codes


def test_bad_spacing_is_detected():
    sql = """SELECT id
FROM users
WHERE id=1;"""

    result = lint_sql(sql)

    codes = {
        finding["code"]
        for finding in result
    }

    assert "LT01" in codes
