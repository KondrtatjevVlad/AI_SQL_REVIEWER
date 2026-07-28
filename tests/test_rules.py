from reviewer.rules import run_custom_rules


def test_clean_select_has_max_risk_score():
    sql = """SELECT
    id,
    username
FROM users
WHERE id = 1;
"""

    result = run_custom_rules(sql)

    assert result["score"] == 10
    assert result["findings"] == []


def test_select_star_is_detected():
    result = run_custom_rules(
        "SELECT * FROM users;"
    )

    codes = {
        finding["code"]
        for finding in result["findings"]
    }

    assert result["score"] == 9
    assert "SELECT_STAR" in codes


def test_delete_without_where_is_critical():
    result = run_custom_rules(
        "DELETE FROM users;"
    )

    assert result["score"] == 6
    assert len(result["findings"]) == 1

    finding = result["findings"][0]

    assert finding["code"] == "DELETE_WITHOUT_WHERE"
    assert finding["severity"] == "CRITICAL"
    assert finding["penalty"] == 4


def test_update_without_where_is_critical():
    result = run_custom_rules(
        "UPDATE users SET username = 'test';"
    )

    finding = result["findings"][0]

    assert result["score"] == 6
    assert finding["code"] == "UPDATE_WITHOUT_WHERE"
    assert finding["severity"] == "CRITICAL"


def test_multiple_warnings_reduce_risk_score():
    sql = """SELECT *
FROM users
WHERE LOWER(username) LIKE '%vlad%';
"""

    result = run_custom_rules(sql)

    codes = {
        finding["code"]
        for finding in result["findings"]
    }

    assert result["score"] == 6
    assert "SELECT_STAR" in codes
    assert "LEADING_WILDCARD" in codes
    assert "FUNCTION_IN_WHERE" in codes


def test_risk_score_cannot_be_negative():
    sql = """DELETE FROM users;
DROP TABLE users;
TRUNCATE TABLE reviews;
"""

    result = run_custom_rules(sql)

    assert result["score"] == 0
