SQLFLUFF_PREFIX_PENALTIES = {
    # Ошибка разбора SQL обрабатывается отдельно.
    "AM": 1.00,  # неоднозначность
    "RF": 1.00,  # ссылки на таблицы/столбцы
    "ST": 0.75,  # структура запроса
    "JJ": 0.75,  # JOIN
    "AL": 0.50,  # псевдонимы
    "CV": 0.50,  # соглашения
    "TQ": 0.50,  # особенности T-SQL и похожих диалектных правил
    "LT": 0.25,  # форматирование
    "CP": 0.25,  # регистр
}


def get_sqlfluff_penalty(code: str | None) -> float:
    """Возвращает штраф за конкретное нарушение SQLFluff."""

    if not code:
        return 0.50

    if code == "PRS":
        return 3.00

    prefix = code[:2]

    return SQLFLUFF_PREFIX_PENALTIES.get(
        prefix,
        0.50,
    )


def calculate_quality_score(
    findings: list[dict],
) -> dict:
    """
    Рассчитывает качество SQL по результатам SQLFluff.

    Оценка начинается с 10 и уменьшается
    в зависимости от типа найденных нарушений.
    """

    enriched_findings = []
    total_penalty = 0.0

    for finding in findings:
        penalty = get_sqlfluff_penalty(
            finding.get("code")
        )

        total_penalty += penalty

        enriched_finding = {
            **finding,
            "quality_penalty": penalty,
        }

        enriched_findings.append(
            enriched_finding
        )

    score = max(
        0.0,
        10.0 - total_penalty,
    )

    return {
        "score": round(score, 1),
        "total_penalty": round(
            total_penalty,
            2,
        ),
        "findings": enriched_findings,
    }


def calculate_overall_score(
    risk_score: float,
    quality_score: float,
    custom_findings: list[dict],
    sqlfluff_findings: list[dict],
) -> float:
    """
    Рассчитывает итоговую оценку.

    60% — риски наших правил.
    40% — качество SQL по SQLFluff.

    Критические риски и ошибки парсинга
    дополнительно ограничивают итоговую оценку.
    """

    score = (
        risk_score * 0.60
        + quality_score * 0.40
    )

    has_critical = any(
        finding.get("severity") == "CRITICAL"
        for finding in custom_findings
    )

    has_parse_error = any(
        finding.get("code") == "PRS"
        for finding in sqlfluff_findings
    )

    # Критически опасный SQL не должен получать
    # высокую итоговую оценку только за хороший стиль.
    if has_critical:
        score = min(
            score,
            risk_score,
        )

    # Если SQLFluff не может разобрать запрос,
    # итоговая оценка не может быть выше 4.
    if has_parse_error:
        score = min(
            score,
            4.0,
        )

    return round(
        max(0.0, score),
        1,
    )