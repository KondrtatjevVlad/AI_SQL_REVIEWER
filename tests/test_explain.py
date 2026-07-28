from reviewer.explain import is_safe_select


def test_select_is_allowed_for_explain():
    assert is_safe_select(
        "SELECT id FROM users WHERE id = 1;"
    )


def test_delete_is_blocked_for_explain():
    assert not is_safe_select(
        "DELETE FROM users;"
    )


def test_update_is_blocked_for_explain():
    assert not is_safe_select(
        "UPDATE users SET username = 'test';"
    )


def test_drop_is_blocked_for_explain():
    assert not is_safe_select(
        "DROP TABLE users;"
    )


def test_multiple_statements_are_blocked():
    assert not is_safe_select(
        "SELECT 1; DELETE FROM users;"
    )


def test_select_without_semicolon_is_allowed():
    assert is_safe_select(
        "SELECT id FROM users"
    )
