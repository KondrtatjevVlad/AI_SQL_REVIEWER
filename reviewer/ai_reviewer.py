import json

from ollama import chat


MODEL_NAME = "qwen2.5-coder:3b"


SYSTEM_PROMPT = (
    "You are an expert PostgreSQL SQL reviewer.\n\n"

    "Your task is to explain SQL problems using evidence from "
    "deterministic custom rules and SQLFluff.\n\n"

    "The deterministic findings are the source of truth. "
    "Do not claim that a reported finding has been fixed unless "
    "the suggested SQL actually removes that exact problem.\n\n"

    "Analyze:\n"
    "- correctness\n"
    "- data safety\n"
    "- performance risks\n"
    "- readability\n"
    "- PostgreSQL best practices\n\n"

    "Important constraints:\n"
    "- Never invent database columns, indexes, constraints, or schema details.\n"
    "- If the original query uses SELECT *, do not guess which columns "
    "should replace it.\n"
    "- A leading wildcard such as LIKE '%text%' remains a leading wildcard "
    "unless the pattern itself is changed.\n"
    "- LOWER(column), UPPER(column), DATE(column), and similar expressions "
    "remain functions on a filtered column unless the expression is removed.\n"
    "- Do not claim that a normal index solves a leading wildcard search.\n"
    "- Do not change query semantics just to remove a warning.\n"
    "- If a safe rewrite requires missing schema or business context, "
    "do not invent a rewrite.\n\n"

    "Before writing the final answer, compare Suggested SQL with every "
    "custom finding. If a finding remains in the suggested query, explicitly "
    "state that it remains unresolved.\n\n"

    "Return these sections:\n"
    "1. Summary\n"
    "2. Main risks\n"
    "3. Recommendations\n"
    "4. Suggested SQL\n\n"

    "If a safe equivalent rewrite cannot be produced, write exactly:\n"
    "Suggested SQL: No safe rewrite without additional context."
)


def build_ai_prompt(
    sql: str,
    custom_findings: list[dict],
    sqlfluff_findings: list[dict],
) -> str:
    """Build a grounded prompt for the local LLM."""

    custom_json = json.dumps(
        custom_findings,
        indent=2,
        ensure_ascii=False,
    )

    sqlfluff_json = json.dumps(
        sqlfluff_findings,
        indent=2,
        ensure_ascii=False,
    )

    return (
        "Review the following PostgreSQL query.\n\n"
        "SQL:\n"
        "```sql\n"
        f"{sql}\n"
        "```\n\n"
        "Custom rule findings:\n"
        f"{custom_json}\n\n"
        "SQLFluff findings:\n"
        f"{sqlfluff_json}\n\n"
        "Explain the important problems and propose a safer or cleaner "
        "query when appropriate."
    )


def get_ai_review(
    sql: str,
    custom_findings: list[dict],
    sqlfluff_findings: list[dict],
) -> str:
    """Generate an AI-assisted SQL review using Ollama."""

    prompt = build_ai_prompt(
        sql=sql,
        custom_findings=custom_findings,
        sqlfluff_findings=sqlfluff_findings,
    )

    response = chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    return response.message.content.strip()