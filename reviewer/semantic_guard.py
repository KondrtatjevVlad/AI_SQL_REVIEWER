from __future__ import annotations

import re
from collections import Counter


SQL_KEYWORDS = {
    "SELECT", "FROM", "WHERE", "AS",
    "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "OUTER", "CROSS",
    "ON", "USING",
    "AND", "OR", "NOT",
    "GROUP", "BY", "HAVING",
    "ORDER", "ASC", "DESC",
    "LIMIT", "OFFSET",
    "DISTINCT", "ALL",
    "CASE", "WHEN", "THEN", "ELSE", "END",
    "NULL", "IS", "IN", "LIKE", "ILIKE", "BETWEEN", "EXISTS",
    "TRUE", "FALSE",
    "WITH", "RECURSIVE",
    "UNION", "INTERSECT", "EXCEPT",
    "WINDOW", "OVER", "PARTITION",
    "ROWS", "RANGE",
    "CURRENT", "ROW",
    "UNBOUNDED", "PRECEDING", "FOLLOWING",
    "FILTER", "WITHIN",
    "INSERT", "INTO", "VALUES",
    "UPDATE", "SET",
    "DELETE", "RETURNING",
    "CREATE", "ALTER", "DROP", "TRUNCATE",
    "TABLE", "VIEW", "INDEX",
    "CAST",
}


STRUCTURE_PATTERNS = {
    "JOIN": r"\bJOIN\b",
    "WHERE": r"\bWHERE\b",
    "AND": r"\bAND\b",
    "OR": r"\bOR\b",
    "GROUP BY": r"\bGROUP\s+BY\b",
    "HAVING": r"\bHAVING\b",
    "ORDER BY": r"\bORDER\s+BY\b",
    "LIMIT": r"\bLIMIT\b",
    "OFFSET": r"\bOFFSET\b",
    "UNION": r"\bUNION\b",
    "INTERSECT": r"\bINTERSECT\b",
    "EXCEPT": r"\bEXCEPT\b",
    "RETURNING": r"\bRETURNING\b",
}


DANGEROUS_COMMANDS = {
    "INSERT": r"\bINSERT\b",
    "UPDATE": r"\bUPDATE\b",
    "DELETE": r"\bDELETE\b",
    "DROP": r"\bDROP\b",
    "TRUNCATE": r"\bTRUNCATE\b",
    "ALTER": r"\bALTER\b",
    "CREATE": r"\bCREATE\b",
}


TABLE_PATTERN = re.compile(
    r"\b(?:FROM|JOIN)\s+"
    r"(?:ONLY\s+)?"
    r"(?P<table>"
    r"(?:\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_$]*)"
    r"(?:\.(?:\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_$]*))?"
    r")",
    re.IGNORECASE,
)

STRING_PATTERN = re.compile(
    r"'(?:''|[^'])*'"
)

NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_$])"
    r"[-+]?\d+(?:\.\d+)?"
    r"(?![A-Za-z0-9_$])"
)

IDENTIFIER_PATTERN = re.compile(
    r'"[^"]+"|[A-Za-z_][A-Za-z0-9_$]*'
)

COMPARISON_PATTERN = re.compile(
    r"<>|!=|<=|>=|=|<|>"
)


def remove_comments(sql: str) -> str:
    sql = re.sub(
        r"/\*.*?\*/",
        " ",
        sql,
        flags=re.DOTALL,
    )

    sql = re.sub(
        r"--[^\r\n]*",
        " ",
        sql,
    )

    return sql


def mask_string_literals(sql: str) -> str:
    return STRING_PATTERN.sub(
        "''",
        sql,
    )


def split_sql_statements(sql: str) -> list[str]:
    """
    Делит SQL по ;, игнорируя ; внутри строковых литералов.
    """

    sql = remove_comments(sql)

    statements = []
    current = []

    in_single_quote = False
    in_double_quote = False

    index = 0

    while index < len(sql):
        char = sql[index]

        if char == "'" and not in_double_quote:
            current.append(char)

            if in_single_quote:
                if (
                    index + 1 < len(sql)
                    and sql[index + 1] == "'"
                ):
                    current.append("'")
                    index += 2
                    continue

                in_single_quote = False
            else:
                in_single_quote = True

            index += 1
            continue

        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            current.append(char)
            index += 1
            continue

        if (
            char == ";"
            and not in_single_quote
            and not in_double_quote
        ):
            statement = "".join(current).strip()

            if statement:
                statements.append(statement)

            current = []
            index += 1
            continue

        current.append(char)
        index += 1

    final_statement = "".join(current).strip()

    if final_statement:
        statements.append(final_statement)

    return statements


def validate_single_statement(
    sql: str,
) -> tuple[bool, str | None]:
    statements = split_sql_statements(sql)

    if not statements:
        return (
            False,
            "SQL-запрос пуст.",
        )

    if len(statements) != 1:
        return (
            False,
            "Для сравнения моделей разрешён только один SQL-запрос за один запуск.",
        )

    return True, None


def extract_string_literals(
    sql: str,
) -> Counter:
    sql = remove_comments(sql)

    return Counter(
        STRING_PATTERN.findall(sql)
    )


def extract_numbers(
    sql: str,
) -> Counter:
    sql = remove_comments(sql)
    sql = mask_string_literals(sql)

    return Counter(
        NUMBER_PATTERN.findall(sql)
    )


def extract_tables(
    sql: str,
) -> Counter:
    sql = remove_comments(sql)
    sql = mask_string_literals(sql)

    return Counter(
        match.group("table").lower()
        for match in TABLE_PATTERN.finditer(sql)
    )


def extract_comparison_operators(
    sql: str,
) -> Counter:
    sql = remove_comments(sql)
    sql = mask_string_literals(sql)

    return Counter(
        COMPARISON_PATTERN.findall(sql)
    )


def extract_structure(
    sql: str,
) -> dict[str, int]:
    sql = remove_comments(sql)
    sql = mask_string_literals(sql)

    return {
        name: len(
            re.findall(
                pattern,
                sql,
                flags=re.IGNORECASE,
            )
        )
        for name, pattern in STRUCTURE_PATTERNS.items()
    }


def extract_dangerous_commands(
    sql: str,
) -> dict[str, int]:
    sql = remove_comments(sql)
    sql = mask_string_literals(sql)

    return {
        name: len(
            re.findall(
                pattern,
                sql,
                flags=re.IGNORECASE,
            )
        )
        for name, pattern in DANGEROUS_COMMANDS.items()
    }


def extract_identifiers(
    sql: str,
) -> Counter:
    """
    Выделяет пользовательские идентификаторы:
    таблицы, столбцы, алиасы и функции.

    Первый токен SQL намеренно не учитывается.
    Это позволяет исправить очевидную опечатку
    SELEC -> SELECT.
    """

    sql = remove_comments(sql)
    sql = mask_string_literals(sql)

    tokens = IDENTIFIER_PATTERN.findall(sql)

    if tokens:
        tokens = tokens[1:]

    result = []

    for token in tokens:
        normalized = token.upper()

        if normalized in SQL_KEYWORDS:
            continue

        result.append(
            token.lower()
        )

    return Counter(result)


def validate_semantic_preservation(
    original_sql: str,
    candidate_sql: str,
) -> tuple[bool, list[str]]:
    """
    Проверяет, не внесла ли AI структурные или смысловые
    изменения в SQL.

    Это эвристическая защита, а не математическое доказательство
    семантической эквивалентности.
    """

    reasons = []

    original_single, _ = validate_single_statement(
        original_sql
    )
    candidate_single, _ = validate_single_statement(
        candidate_sql
    )

    if not original_single:
        reasons.append(
            "Исходный SQL содержит не один запрос."
        )

    if not candidate_single:
        reasons.append(
            "Модель изменила количество SQL-запросов."
        )

    if extract_tables(original_sql) != extract_tables(candidate_sql):
        reasons.append(
            "Изменён набор таблиц или JOIN-источников."
        )

    if extract_identifiers(original_sql) != extract_identifiers(candidate_sql):
        reasons.append(
            "Изменены столбцы, функции или алиасы."
        )

    if extract_string_literals(original_sql) != extract_string_literals(candidate_sql):
        reasons.append(
            "Изменены строковые значения."
        )

    if extract_numbers(original_sql) != extract_numbers(candidate_sql):
        reasons.append(
            "Изменены числовые значения."
        )

    if (
        extract_comparison_operators(original_sql)
        != extract_comparison_operators(candidate_sql)
    ):
        reasons.append(
            "Изменены операторы сравнения."
        )

    if extract_structure(original_sql) != extract_structure(candidate_sql):
        reasons.append(
            "Изменена структура WHERE, JOIN, AND/OR, GROUP BY или других условий."
        )

    if (
        extract_dangerous_commands(original_sql)
        != extract_dangerous_commands(candidate_sql)
    ):
        reasons.append(
            "Изменён тип операции SQL."
        )

    return not reasons, reasons
