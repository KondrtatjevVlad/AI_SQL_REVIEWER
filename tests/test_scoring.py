from reviewer.scoring import (
    calculate_overall_score,
    calculate_quality_score,
    get_sqlfluff_penalty,
)


def test_no_sqlfluff_findings_gives_quality_10():
    result = calculate_quality_score([])

    assert result["score"] == 10.0
    assert result["total_penalty"] == 0.0


def test_sqlfluff_penalties_have_different_weight():
    assert get_sqlfluff_penalty("LT09") == 0.25
    assert get_sqlfluff_penalty("AL01") == 0.50
    assert get_sqlfluff_penalty("AM05") == 1.00
    assert get_sqlfluff_penalty("ST09") == 0.75
    assert get_sqlfluff_penalty("PRS") == 3.00


def test_example_five_findings_give_quality_7():
    findings = [
        {"code": "LT09"},
        {"code": "AL01"},
        {"code": "AM05"},
        {"code": "AL01"},
        {"code": "ST09"},
    ]

    result = calculate_quality_score(
        findings
    )

    assert result["total_penalty"] == 3.0
    assert result["score"] == 7.0


def test_regular_overall_score_uses_60_40_weights():
    result = calculate_overall_score(
        risk_score=10,
        quality_score=7,
        custom_findings=[],
        sqlfluff_findings=[],
    )

    assert result == 8.8


def test_critical_finding_caps_overall_score():
    custom_findings = [
        {
            "code": "DELETE_WITHOUT_WHERE",
            "severity": "CRITICAL",
        }
    ]

    result = calculate_overall_score(
        risk_score=6,
        quality_score=10,
        custom_findings=custom_findings,
        sqlfluff_findings=[],
    )

    assert result == 6.0


def test_parse_error_caps_overall_score_at_4():
    result = calculate_overall_score(
        risk_score=10,
        quality_score=7,
        custom_findings=[],
        sqlfluff_findings=[
            {"code": "PRS"}
        ],
    )

    assert result == 4.0


def test_quality_score_cannot_be_negative():
    findings = [
        {"code": "AM05"}
        for _ in range(20)
    ]

    result = calculate_quality_score(
        findings
    )

    assert result["score"] == 0.0
