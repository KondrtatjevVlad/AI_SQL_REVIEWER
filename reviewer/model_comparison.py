from time import perf_counter

from reviewer.ai_reviewer import get_ai_review
from reviewer.analyzer import analyze_sql
from reviewer.model_registry import get_model


DEFAULT_COMPARISON_MODELS = (
    "qwen",
    "deepseek",
)


def compare_ai_models(
    sql: str,
    model_keys: tuple[str, ...] = DEFAULT_COMPARISON_MODELS,
) -> dict:
    """
    Последовательно запускает несколько Ollama-моделей
    на одинаковом SQL и одинаковых результатах анализа.
    """

    normalized_sql = sql.strip()

    if not normalized_sql:
        raise ValueError(
            "Для сравнения моделей необходимо передать SQL."
        )

    unique_model_keys = tuple(
        dict.fromkeys(model_keys)
    )

    if not unique_model_keys:
        raise ValueError(
            "Не выбрано ни одной модели."
        )

    base_analysis = analyze_sql(
        normalized_sql,
        include_ai=False,
        include_explain=False,
    )

    model_results = []

    for model_key in unique_model_keys:
        model = get_model(model_key)
        started_at = perf_counter()

        try:
            report = get_ai_review(
                sql=normalized_sql,
                custom_findings=base_analysis[
                    "custom_findings"
                ],
                sqlfluff_findings=base_analysis[
                    "sqlfluff_findings"
                ],
                risk_score=base_analysis[
                    "risk_score"
                ],
                quality_score=base_analysis[
                    "quality_score"
                ],
                overall_score=base_analysis[
                    "overall_score"
                ],
                model_key=model_key,
            )

            status = "success"
            error = None

        except Exception as exc:
            report = None
            status = "error"
            error = str(exc)

        elapsed_seconds = round(
            perf_counter() - started_at,
            2,
        )

        model_results.append(
            {
                "model_key": model.key,
                "model_name": model.ollama_name,
                "display_name": model.display_name,
                "description": model.description,
                "status": status,
                "elapsed_seconds": elapsed_seconds,
                "report": report,
                "error": error,
            }
        )

    return {
        "sql": normalized_sql,
        "base_analysis": base_analysis,
        "model_results": model_results,
    }
