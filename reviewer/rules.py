import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    title: str
    message: str
    penalty: int

    def to_dict(self) -> dict:
        return asdict(self)


def split_statements(sql: str) -> list[str]:
    return [
        statement.strip()
        for statement in sql.split(";")
        if statement.strip()
    ]


def check_select_star(statement: str) -> list[Finding]:
    if re.search(
        r"\bSELECT\s+(?:DISTINCT\s+)?(?:\w+\.)?\*",
        statement,
        re.IGNORECASE,
    ):
        return [
            Finding(
                code="SELECT_STAR",
                severity="WARNING",
                title="Обнаружен SELECT *",
                message=(
                    "Рекомендуется явно перечислить необходимые столбцы "
                    "вместо использования SELECT *."
                ),
                penalty=1,
            )
        ]

    return []


def check_delete_without_where(statement: str) -> list[Finding]:
    if (
        re.match(
            r"^\s*DELETE\s+FROM\b",
            statement,
            re.IGNORECASE,
        )
        and not re.search(
            r"\bWHERE\b",
            statement,
            re.IGNORECASE,
        )
    ):
        return [
            Finding(
                code="DELETE_WITHOUT_WHERE",
                severity="CRITICAL",
                title="DELETE без WHERE",
                message=(
                    "DELETE без условия WHERE может удалить "
                    "все строки таблицы."
                ),
                penalty=4,
            )
        ]

    return []


def check_update_without_where(statement: str) -> list[Finding]:
    if (
        re.match(
            r"^\s*UPDATE\b",
            statement,
            re.IGNORECASE,
        )
        and not re.search(
            r"\bWHERE\b",
            statement,
            re.IGNORECASE,
        )
    ):
        return [
            Finding(
                code="UPDATE_WITHOUT_WHERE",
                severity="CRITICAL",
                title="UPDATE без WHERE",
                message=(
                    "UPDATE без условия WHERE может изменить "
                    "все строки таблицы."
                ),
                penalty=4,
            )
        ]

    return []


def check_leading_wildcard(statement: str) -> list[Finding]:
    if re.search(
        r"\b(?:LIKE|ILIKE)\s+'%",
        statement,
        re.IGNORECASE,
    ):
        return [
            Finding(
                code="LEADING_WILDCARD",
                severity="WARNING",
                title="Шаблон LIKE начинается с %",
                message=(
                    "Шаблон поиска, начинающийся с %, может привести "
                    "к неэффективному использованию индексов."
                ),
                penalty=2,
            )
        ]

    return []


def check_many_joins(statement: str) -> list[Finding]:
    join_count = len(
        re.findall(
            r"\bJOIN\b",
            statement,
            re.IGNORECASE,
        )
    )

    if join_count >= 4:
        return [
            Finding(
                code="MANY_JOINS",
                severity="WARNING",
                title="Большое количество JOIN",
                message=(
                    f"Запрос содержит {join_count} операций JOIN. "
                    "Стоит проверить сложность запроса и необходимость "
                    "каждого соединения."
                ),
                penalty=1,
            )
        ]

    return []


def check_function_in_where(statement: str) -> list[Finding]:
    where_match = re.search(
        r"\bWHERE\b(.+)",
        statement,
        re.IGNORECASE | re.DOTALL,
    )

    if not where_match:
        return []

    where_part = where_match.group(1)

    if re.search(
        r"\b(?:LOWER|UPPER|DATE|COALESCE)\s*\(\s*[a-zA-Z_][\w.]*",
        where_part,
        re.IGNORECASE,
    ):
        return [
            Finding(
                code="FUNCTION_IN_WHERE",
                severity="WARNING",
                title="Функция применяется к столбцу в WHERE",
                message=(
                    "Применение функции к фильтруемому столбцу "
                    "может снизить эффективность использования "
                    "обычного индекса."
                ),
                penalty=1,
            )
        ]

    return []


def check_dangerous_ddl(statement: str) -> list[Finding]:
    if re.match(
        r"^\s*DROP\s+",
        statement,
        re.IGNORECASE,
    ):
        return [
            Finding(
                code="DROP_STATEMENT",
                severity="CRITICAL",
                title="Обнаружена команда DROP",
                message=(
                    "DROP удаляет объект базы данных. "
                    "Такая операция потенциально необратима."
                ),
                penalty=4,
            )
        ]

    if re.match(
        r"^\s*TRUNCATE\b",
        statement,
        re.IGNORECASE,
    ):
        return [
            Finding(
                code="TRUNCATE_STATEMENT",
                severity="CRITICAL",
                title="Обнаружена команда TRUNCATE",
                message=(
                    "TRUNCATE удаляет все строки таблицы."
                ),
                penalty=4,
            )
        ]

    return []


RULES = [
    check_select_star,
    check_delete_without_where,
    check_update_without_where,
    check_leading_wildcard,
    check_many_joins,
    check_function_in_where,
    check_dangerous_ddl,
]


def run_custom_rules(sql: str) -> dict:
    if not sql or not sql.strip():
        raise ValueError(
            "SQL-запрос не может быть пустым."
        )

    findings: list[Finding] = []

    for statement in split_statements(sql):
        for rule in RULES:
            findings.extend(
                rule(statement)
            )

    total_penalty = sum(
        finding.penalty
        for finding in findings
    )

    return {
        "score": max(
            0,
            10 - total_penalty,
        ),
        "findings": [
            finding.to_dict()
            for finding in findings
        ],
    }