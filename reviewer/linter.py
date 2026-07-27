import sqlfluff


def lint_sql(sql: str) -> list[dict]:
    """Run SQLFluff using the PostgreSQL dialect."""

    if not sql or not sql.strip():
        raise ValueError("SQL query cannot be empty.")

    violations = sqlfluff.lint(
        sql,
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