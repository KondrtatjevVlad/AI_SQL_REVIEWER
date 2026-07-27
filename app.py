import streamlit as st

from auth.auth import authenticate_user, register_user
from database.db import SessionLocal
from reviewer.analyzer import analyze_sql
from database.reviews import get_user_reviews, save_review


st.set_page_config(
    page_title="AI SQL Reviewer",
    page_icon="🔍",
    layout="wide",
)


def init_session_state() -> None:
    if "user_id" not in st.session_state:
        st.session_state.user_id = None

    if "username" not in st.session_state:
        st.session_state.username = None


def show_login() -> None:
    st.title("AI SQL Reviewer")
    st.caption(
        "Static analysis, SQLFluff and local AI-assisted PostgreSQL review."
    )

    login_tab, register_tab = st.tabs(
        ["Login", "Register"]
    )

    with login_tab:
        st.subheader("Login")

        with st.form("login_form"):
            username = st.text_input("Username")
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
                    st.error("Invalid username or password.")
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
                st.error("Passwords do not match.")
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
                st.error(str(exc))

            finally:
                db.close()


def render_custom_findings(findings: list[dict]) -> None:
    st.subheader("Custom Rules")

    if not findings:
        st.success("No custom rule violations found.")
        return

    for finding in findings:
        severity = finding["severity"]

        text = (
            f'**{severity} — {finding["code"]}**\n\n'
            f'{finding["title"]}\n\n'
            f'{finding["message"]}\n\n'
            f'Penalty: -{finding["penalty"]}'
        )

        if severity == "CRITICAL":
            st.error(text)
        elif severity == "WARNING":
            st.warning(text)
        else:
            st.info(text)


def render_sqlfluff_findings(findings: list[dict]) -> None:
    st.subheader("SQLFluff")

    if not findings:
        st.success("No SQLFluff violations found.")
        return

    for finding in findings:
        code = finding.get("code", "UNKNOWN")
        line = finding.get("line")
        position = finding.get("position")
        description = finding.get(
            "description",
            "No description.",
        )

        st.warning(
            f"**{code}** — "
            f"line {line}, position {position}\n\n"
            f"{description}"
        )


def show_reviewer() -> None:
    st.subheader("Review SQL")

    st.caption(
        "The query is analyzed statically. "
        "It is not executed against the database."
    )

    sql = st.text_area(
        "PostgreSQL query",
        height=250,
        placeholder=(
            "SELECT *\n"
            "FROM users\n"
            "WHERE LOWER(username) LIKE '%vlad%';"
        ),
    )

    include_ai = st.checkbox(
        "Generate AI review with Ollama",
        value=True,
    )

    analyze_clicked = st.button(
        "Analyze SQL",
        type="primary",
        use_container_width=True,
    )

    if not analyze_clicked:
        return

    if not sql.strip():
        st.error("Enter a SQL query first.")
        return

    try:
        with st.spinner(
            "Analyzing SQL..."
            if not include_ai
            else "Analyzing SQL and generating AI review..."
        ):
            result = analyze_sql(
                sql,
                include_ai=include_ai,
            )

            db = SessionLocal()

            try:
                save_review(
                    db=db,
                    user_id=st.session_state.user_id,
                    sql_query=sql,
                    score=result["score"],
                    review_text=result["ai_review"],
                )
            finally:
                db.close()

    except Exception as exc:
        st.error(
            f"Analysis failed: {exc}"
        )
        return

    st.divider()

    score = result["score"]

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Score",
        f"{score}/10",
    )

    col2.metric(
        "Custom findings",
        len(result["custom_findings"]),
    )

    col3.metric(
        "SQLFluff findings",
        len(result["sqlfluff_findings"]),
    )

    st.progress(score / 10)

    st.divider()

    left_column, right_column = st.columns(2)

    with left_column:
        render_custom_findings(
            result["custom_findings"]
        )

    with right_column:
        render_sqlfluff_findings(
            result["sqlfluff_findings"]
        )

    st.divider()

    st.subheader("AI Review")

    if result["ai_review"]:
        st.markdown(result["ai_review"])
    else:
        st.info(
            "AI review was not requested."
        )

def show_history() -> None:
    st.subheader("Review History")

    db = SessionLocal()

    try:
        reviews = get_user_reviews(
            db=db,
            user_id=st.session_state.user_id,
        )

        if not reviews:
            st.info("No reviews yet.")
            return

        for review in reviews:
            created_at = (
                review.created_at.strftime("%Y-%m-%d %H:%M")
                if review.created_at
                else "Unknown time"
            )

            title = (
                f"Review #{review.id} — "
                f"{review.score}/10 — "
                f"{created_at}"
            )

            with st.expander(title):
                st.code(
                    review.sql_query,
                    language="sql",
                )

                st.metric(
                    "Score",
                    f"{review.score}/10",
                )

                if review.review_text:
                    st.markdown("### AI Review")
                    st.markdown(review.review_text)
                else:
                    st.caption(
                        "AI review was not requested."
                    )

    finally:
        db.close()


def show_app() -> None:
    with st.sidebar:
        st.title("AI SQL Reviewer")

        st.write(
            f"Logged in as **{st.session_state.username}**"
        )

        st.divider()

        st.caption(
            "Custom Rules + SQLFluff + Ollama"
        )

        if st.button(
            "Logout",
            use_container_width=True,
        ):
            st.session_state.user_id = None
            st.session_state.username = None
            st.rerun()

    st.title("AI SQL Reviewer")

    st.caption(
        "Automated PostgreSQL query review with "
        "deterministic rules and local AI."
    )

    reviewer_tab, history_tab = st.tabs(
        ["Reviewer", "History"]
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