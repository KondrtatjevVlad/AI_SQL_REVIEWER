from reviewer.semantic_guard import (
    validate_semantic_preservation,
    validate_single_statement,
)


def test_single_statement_allowed():
    ok, error = validate_single_statement(
        "SELECT id FROM users;"
    )

    assert ok is True
    assert error is None


def test_multiple_statements_blocked():
    ok, error = validate_single_statement(
        "SELECT 1; SELECT 2;"
    )

    assert ok is False
    assert error is not None


def test_safe_syntax_fix_allowed():
    original = """
    SELEC username
    FROM users;
    """

    candidate = """
    SELECT username
    FROM users;
    """

    ok, reasons = validate_semantic_preservation(
        original,
        candidate,
    )

    assert ok is True
    assert reasons == []


def test_ai_hallucinated_conditions_blocked():
    original = """
    SELECT
        u.username,
        r1.score,
        r2.score
    FROM users AS u
    INNER JOIN reviews AS r1
        ON u.id = r1.user_id
    INNER JOIN reviews AS r2
        ON u.id = r2.user_id
    WHERE r1.score < 5;
    """

    candidate = """
    SELECT
        u.username,
        r1.score,
        r2.score
    FROM users AS u
    INNER JOIN reviews AS r1
        ON u.id = r1.user_id
    INNER JOIN reviews AS r2
        ON u.id = r2.user_id
        AND r2.score <= 4
    WHERE r1.score < 5;
    """

    ok, reasons = validate_semantic_preservation(
        original,
        candidate,
    )

    assert ok is False
    assert reasons
