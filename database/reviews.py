from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Review


def save_review(
    db: Session,
    user_id: int,
    sql_query: str,
    score: int,
    review_text: str | None,
) -> Review:
    """Save a completed SQL review."""

    review = Review(
        user_id=user_id,
        sql_query=sql_query,
        score=score,
        review_text=review_text,
    )

    db.add(review)
    db.commit()
    db.refresh(review)

    return review


def get_user_reviews(
    db: Session,
    user_id: int,
    limit: int = 20,
) -> list[Review]:
    """Return the latest reviews for a user."""

    statement = (
        select(Review)
        .where(Review.user_id == user_id)
        .order_by(Review.created_at.desc())
        .limit(limit)
    )

    return list(db.scalars(statement).all())