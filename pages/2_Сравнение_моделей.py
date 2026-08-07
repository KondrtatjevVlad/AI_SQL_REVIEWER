from __future__ import annotations

import streamlit as st

from reviewer.model_comparison import compare_ai_models
from reviewer.model_registry import get_all_models


st.set_page_config(
    page_title="Сравнение AI-моделей",
    layout="wide",
)


DEFAULT_SQL = """SELEC
    username
FROM users;"""


st.title("Сравнение AI-моделей")

st.caption(
    "На основной странице проекта используется одна основная модель. "
    "Эта дополнительная страница последовательно запускает Qwen и DeepSeek "
    "на одинаковом SQL и показывает оба AI-разбора для сравнения."
)


with st.expander(
    "Используемые модели",
    expanded=True,
):
    for model in get_all_models():
        st.markdown(
            f"**{model.display_name}**  \n"
            f"`{model.ollama_name}`  \n"
            f"{model.description}"
        )


sql = st.text_area(
    "SQL-запрос для сравнения",
    value=st.session_state.get(
        "comparison_sql",
        DEFAULT_SQL,
    ),
    height=240,
    key="comparison_sql",
)


button_column, clear_column = st.columns([1, 4])

with button_column:
    start_comparison = st.button(
        "Сравнить модели",
        type="primary",
        use_container_width=True,
    )

with clear_column:
    clear_result = st.button(
        "Очистить результат",
    )


if clear_result:
    st.session_state.pop(
        "model_comparison_result",
        None,
    )
    st.rerun()


if start_comparison:
    if not sql.strip():
        st.warning("Введите SQL-запрос.")
    else:
        try:
            with st.spinner(
                "Сначала запускается Qwen, затем DeepSeek. "
                "Анализ может занять некоторое время..."
            ):
                comparison = compare_ai_models(sql)

            st.session_state[
                "model_comparison_result"
            ] = comparison

        except Exception as exc:
            st.error(
                "Не удалось выполнить сравнение."
            )
            st.exception(exc)


comparison = st.session_state.get(
    "model_comparison_result"
)

if comparison is None:
    st.info(
        "Введите SQL и нажмите «Сравнить модели»."
    )
    st.stop()


base_analysis = comparison["base_analysis"]


st.divider()
st.subheader("Исходный автоматический анализ")

risk_column, quality_column, overall_column = st.columns(3)

with risk_column:
    st.metric(
        "Оценка рисков",
        f"{base_analysis['risk_score']:.1f}/10",
    )

with quality_column:
    st.metric(
        "Качество SQL",
        f"{base_analysis['quality_score']:.1f}/10",
    )

with overall_column:
    st.metric(
        "Итоговая оценка",
        f"{base_analysis['overall_score']:.1f}/10",
    )


model_results = comparison["model_results"]


st.divider()
st.subheader("Сводное сравнение")

summary_rows = []

for result in model_results:
    summary_rows.append(
        {
            "Модель": result["display_name"],
            "Статус": (
                "Успешно"
                if result["status"] == "success"
                else "Ошибка"
            ),
            "Время ответа, сек.": result[
                "elapsed_seconds"
            ],
            "Ollama-модель": result["model_name"],
        }
    )


st.dataframe(
    summary_rows,
    hide_index=True,
    use_container_width=True,
)


successful_results = [
    result
    for result in model_results
    if result["status"] == "success"
]

if successful_results:
    fastest_result = min(
        successful_results,
        key=lambda item: item["elapsed_seconds"],
    )

    st.success(
        "Самая быстрая модель в этом запуске: "
        f"**{fastest_result['display_name']}** — "
        f"{fastest_result['elapsed_seconds']} сек."
    )


st.divider()
st.subheader("AI-разборы моделей")

for index, result in enumerate(model_results):
    if index > 0:
        st.divider()

    status_column, time_column = st.columns(2)

    with status_column:
        st.metric(
            f"Статус — {result['display_name']}",
            (
                "Успешно"
                if result["status"] == "success"
                else "Ошибка"
            ),
        )

    with time_column:
        st.metric(
            f"Время — {result['display_name']}",
            f"{result['elapsed_seconds']} сек.",
        )

    if result["status"] == "success":
        st.markdown(result["report"])
    else:
        st.error(
            result["error"]
            or "Модель не вернула результат."
        )


st.divider()

st.warning(
    "Текстовые комментарии моделей могут содержать неточности. "
    "Итоговые оценки рассчитываются не нейросетью, а повторной "
    "проверкой через Custom Rules и SQLFluff."
)