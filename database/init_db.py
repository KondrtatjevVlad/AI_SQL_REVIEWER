from sqlalchemy import text

from database.db import Base, engine

# Import models so SQLAlchemy registers the tables.
from database import models  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    with engine.connect() as connection:
        database_name = connection.execute(
            text("SELECT current_database()")
        ).scalar_one()

    print(f"Database connected: {database_name}")
    print("Tables created successfully.")


if __name__ == "__main__":
    init_db()