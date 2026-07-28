import streamlit as st

from auth.auth import authenticate_user, register_user
from database.db import SessionLocal
from database.reviews import get_user_reviews, save_review
from reviewer.analyzer import analyze_sql


st.set_page_config(
    page_title="AI SQL Reviewer",
    page_icon="🔍",
    layout="wide",
)


# Скрываем стандартный индикатор выполнения Streamlit
# в правом верхнем углу.
st.markdown(
    """
    <style>
    div[data-testid="stStatusWidget"] {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


SQLFLUFF_RUSSIAN_DESCRIPTIONS = {
    "LT01": (
        "Нарушено рекомендуемое форматирование пробелов."
    ),
    "LT09": (
        "При выборе нескольких столбцов SQLFluff рекомендует "
        "размещать их на отдельных строках."
    ),
    "LT12": (
        "SQLFluff ожидает один перенос строки в конце SQL."
    ),
    "LT13": (
        "SQL не должен начинаться с пустой строки "
        "или лишних пробелов."
    ),
    "AL01": (
        "Стиль использования псевдонимов таблиц "
        "не соответствует выбранному правилу SQLFluff."
    ),
    "AM04": (
        "Запрос возвращает неопределённое количество столбцов. "
        "Это характерно, например, для SELECT *."
    ),
    "AM05": (
        "SQLFluff обнаружил неоднозначность в оформлении JOIN. "
        "Рекомендуется явно указать тип соединения."
    ),
    "ST09": (
        "SQLFluff рекомендует изменить порядок ссылок "
        "на таблицы в условии JOIN для единообразия структуры SQL."
    ),
    "PRS": (
        "SQLFluff не смог корректно разобрать запрос. "
        "Вероятна синтаксическая ошибка."
    ),
}


def init_session_state() -> None:
    if "user_id" not in st.session_state:
        st.session_state.user_id = None

    if "username" not in st.session_state:
        st.session_state.username = None


def show_login() -> None:
    st.title("AI SQL Reviewer")

    st.caption(
        "Анализ PostgreSQL-запросов с помощью "
        "детерминированных правил, SQLFluff и локальной AI-модели."
    )

    login_tab, register_tab = st.tabs(
        ["Login", "Register"]
    )

    with login_tab:
        st.subheader("Login")

        with st.form("login_form"):
            username = st.text_input(
                "Username"
            )

            password = st.text_input(
                "Password",
                type="password",
            )

            submitted = st.form_submit_button(
                "Login",
                use_container_width=True,
            )

        if submitted:
            db = SessionLocal()

            try:
                user = authenticate_user(
                    db,
                    username,
                    password,
                )

                if user is None:
                    st.error(
                        "Invalid username or password."
                    )
                else:
                    st.session_state.user_id = user.id
                    st.session_state.username = user.username
                    st.rerun()

            finally:
                db.close()

    with register_tab:
        st.subheader("Create account")

        with st.form("register_form"):
            username = st.text_input(
                "Username",
                key="register_username",
            )

            password = st.text_input(
                "Password",
                type="password",
                key="register_password",
            )

            confirm_password = st.text_input(
                "Confirm password",
                type="password",
            )

            submitted = st.form_submit_button(
                "Register",
                use_container_width=True,
            )

        if submitted:
            if password != confirm_password:
                st.error(
                    "Passwords do not match."
                )
                return

            db = SessionLocal()

            try:
                user = register_user(
                    db,
                    username,
                    password,
                )

                st.success(
                    f"User '{user.username}' created. "
                    "You can now log in."
                )

            except ValueError as exc:
                st.error(
                    str(exc)
                )

            finally:
                db.close()


def severity_name(
    severity: str,
) -> str:
    translations = {
        "CRITICAL": "КРИТИЧЕСКОЕ",
        "WARNING": "ПРЕДУПРЕЖДЕНИЕ",
        "INFO": "ИНФОРМАЦИЯ",
    }

    return translations.get(
        severity,
        severity,
    )


def translate_sqlfluff(
    finding: dict,
) -> str:
    code = finding.get(
        "code",
        "UNKNOWN",
    )

    return SQLFLUFF_RUSSIAN_DESCRIPTIONS.get(
        code,
        (
            f"SQLFluff обнаружил нарушение правила {code}. "
            "Проверьте структуру, однозначность и оформление SQL."
        ),
    )


def render_custom_findings(
    findings: list[dict],
) -> None:
    st.subheader(
        "Наши правила"
    )

    if not findings:
        st.success(
            "Нарушений наших правил не обнаружено."
        )
        return

    for finding in findings:
        severity = finding["severity"]

        text = (
            f'**{severity_name(severity)} — '
            f'{finding["code"]}**\n\n'
            f'**{finding["title"]}**\n\n'
            f'{finding["message"]}\n\n'
            f'Штраф к оценке рисков: -{finding["penalty"]}'
        )

        if severity == "CRITICAL":
            st.error(
                text
            )

        elif severity == "WARNING":
            st.warning(
                text
            )

        else:
            st.info(
                text
            )


def render_sqlfluff_findings(
    findings: list[dict],
) -> None:
    st.subheader(
        "SQLFluff"
    )

    if not findings:
        st.success(
            "Нарушений SQLFluff не обнаружено."
        )
        return

    for finding in findings:
        code = finding.get(
            "code",
            "UNKNOWN",
        )

        line = finding.get(
            "line"
        )

        position = finding.get(
            "position"
        )

        description = translate_sqlfluff(
            finding
        )

        penalty = finding.get(
            "quality_penalty",
            0,
        )

        st.warning(
            f"**{code}** — "
            f"строка {line}, позиция {position}\n\n"
            f"{description}\n\n"
            f"Влияние на оценку качества: **-{penalty}**"
        )


def show_scores(
    result: dict,
) -> None:
    risk_score = result[
        "risk_score"
    ]

    quality_score = result[
        "quality_score"
    ]

    overall_score = result[
        "overall_score"
    ]

    col1, col2, col3 = st.columns(
        3
    )

    col1.metric(
        "Оценка рисков",
        f"{risk_score}/10",
    )

    col2.metric(
        "Качество SQL",
        f"{quality_score}/10",
    )

    col3.metric(
        "Итоговая оценка",
        f"{overall_score}/10",
    )

    st.progress(
        overall_score / 10
    )

    left, right = st.columns(
        2
    )

    left.caption(
        "Наши правила: "
        f"{len(result['custom_findings'])} нарушений"
    )

    right.caption(
        "SQLFluff: "
        f"{len(result['sqlfluff_findings'])} нарушений"
    )

    st.caption(
        "Итоговая оценка: 60% оценки рисков + 40% качества SQL. "
        "Критические нарушения и ошибки синтаксического разбора "
        "дополнительно ограничивают итоговую оценку."
    )


def show_reviewer() -> None:
    st.subheader(
        "Проверка SQL"
    )

    st.caption(
        "Наши правила оценивают риски, SQLFluff — качество SQL. "
        "PostgreSQL EXPLAIN доступен дополнительно для SELECT-запросов "
        "к подключённой базе данных."
    )

    sql = st.text_area(
        "PostgreSQL-запрос",
        height=250,
        placeholder=(
            "SELECT *\n"
            "FROM users\n"
            "WHERE LOWER(username) LIKE '%vlad%';"
        ),
    )

    include_ai = st.checkbox(
        "Выполнить AI-разбор с помощью Ollama",
        value=True,
    )

    include_explain = st.checkbox(
        "Получить план PostgreSQL EXPLAIN",
        value=False,
        help=(
            "EXPLAIN работает только для одиночного SELECT "
            "и только если используемые таблицы существуют "
            "в подключённой PostgreSQL."
        ),
    )

    analyze_clicked = st.button(
        "Проверить SQL",
        type="primary",
        use_container_width=True,
    )

    if not analyze_clicked:
        return

    if not sql.strip():
        st.error(
            "Введите SQL-запрос."
        )
        return

    try:
        analysis_db = SessionLocal()

        try:
            result = analyze_sql(
                sql,
                include_ai=include_ai,
                include_explain=include_explain,
                db=analysis_db,
            )

        finally:
            analysis_db.close()

        history_db = SessionLocal()

        try:
            save_review(
                db=history_db,
                user_id=st.session_state.user_id,
                sql_query=sql,
                score=result["score"],
                review_text=result["ai_review"],
            )

        finally:
            history_db.close()

    except Exception as exc:
        st.error(
            "Не удалось выполнить анализ SQL. "
            f"Техническая причина: {exc}"
        )
        return

    st.divider()

    show_scores(
        result
    )

    st.divider()

    left_column, right_column = st.columns(
        2
    )

    with left_column:
        render_custom_findings(
            result["custom_findings"]
        )

    with right_column:
        render_sqlfluff_findings(
            result["sqlfluff_findings"]
        )

    st.divider()

    st.subheader(
        "План выполнения PostgreSQL"
    )

    explain_result = result[
        "explain"
    ]

    if explain_result is None:
        st.info(
            "EXPLAIN не запрашивался."
        )

    elif explain_result["available"]:
        st.caption(
            "План сформирован PostgreSQL. "
            "EXPLAIN ANALYZE не используется, "
            "поэтому сам SELECT не выполняется."
        )

        st.code(
            "\n".join(
                explain_result["plan"]
            ),
            language="text",
        )

    else:
        st.info(
            explain_result["reason"]
        )

    st.divider()

    st.subheader(
        "AI-разбор"
    )

    if result["ai_review"]:
        st.markdown(
            result["ai_review"]
        )

    else:
        st.info(
            "AI-разбор не запрашивался."
        )


def show_history() -> None:
    st.subheader(
        "История проверок"
    )

    st.caption(
        "В истории хранится округлённая итоговая оценка."
    )

    db = SessionLocal()

    try:
        reviews = get_user_reviews(
            db=db,
            user_id=st.session_state.user_id,
        )

        if not reviews:
            st.info(
                "История проверок пока пуста."
            )
            return

        for review in reviews:
            created_at = (
                review.created_at.strftime(
                    "%Y-%m-%d %H:%M"
                )
                if review.created_at
                else "Время неизвестно"
            )

            title = (
                f"Проверка #{review.id} — "
                f"{review.score}/10 — "
                f"{created_at}"
            )

            with st.expander(
                title
            ):
                st.markdown(
                    "**SQL-запрос**"
                )

                st.code(
                    review.sql_query,
                    language="sql",
                )

                st.metric(
                    "Итоговая оценка",
                    f"{review.score}/10",
                )

                if review.review_text:
                    st.markdown(
                        "### AI-разбор"
                    )

                    st.markdown(
                        review.review_text
                    )

                else:
                    st.caption(
                        "AI-разбор для этой проверки "
                        "не запрашивался."
                    )

    finally:
        db.close()


def show_app() -> None:
    with st.sidebar:
        st.title(
            "AI SQL Reviewer"
        )

        st.write(
            f"Logged in as "
            f"**{st.session_state.username}**"
        )

        st.divider()

        st.caption(
            "Rules + SQLFluff + PostgreSQL + Ollama"
        )

        if st.button(
            "Logout",
            use_container_width=True,
        ):
            st.session_state.user_id = None
            st.session_state.username = None
            st.rerun()

    st.title(
        "AI SQL Reviewer"
    )

    st.caption(
        "Автоматический анализ PostgreSQL-запросов: "
        "риски, качество SQL, план выполнения и AI-разбор."
    )

    reviewer_tab, history_tab = st.tabs(
        [
            "Проверка SQL",
            "История проверок",
        ]
    )

    with reviewer_tab:
        show_reviewer()

    with history_tab:
        show_history()


def main() -> None:
    init_session_state()

    if st.session_state.user_id is None:
        show_login()
    else:
        show_app()


if __name__ == "__main__":
    main()