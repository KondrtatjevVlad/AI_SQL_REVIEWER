import sqlfluff


def lint_sql(sql: str) -> list[dict]:
    """Run SQLFluff using the PostgreSQL dialect."""

    if not sql or not sql.strip():
        raise ValueError("SQL query cannot be empty.")

    # SQLFluff treats input like a SQL file and expects a trailing newline.
    # In the web UI the user should not have to enter it manually.
    normalized_sql = sql.rstrip() + "\n"

    violations = sqlfluff.lint(
        normalized_sql,
        dialect="postgres",
    )

    findings = []

    for violation in violations:
        findings.append(
            {
                "code": violation.get("code"),
                "name": violation.get("name"),
                "line": violation.get("start_line_no"),
                "position": violation.get("start_line_pos"),
                "description": violation.get("description"),
                "warning": violation.get("warning", False),
            }
        )

    return findings