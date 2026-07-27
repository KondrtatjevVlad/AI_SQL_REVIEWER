from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.security import hash_password, verify_password
from database.models import User


def normalize_username(username: str) -> str:
    
    return username.strip().lower()


def register_user(
    db: Session,
    username: str,
    password: str,
) -> User:
    """Register a new user."""

    username = normalize_username(username)

    if len(username) < 3:
        raise ValueError("Username must contain at least 3 characters.")

    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")

    existing_user = db.scalar(
        select(User).where(User.username == username)
    )

    if existing_user is not None:
        raise ValueError("Username already exists.")

    user = User(
        username=username,
        password_hash=hash_password(password),
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Username already exists.") from exc

    return user


def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> User | None:
    

    username = normalize_username(username)

    user = db.scalar(
        select(User).where(User.username == username)
    )

    if user is None:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user