from sqlalchemy import text

from db.session import Base, engine

# Import models exactly once so SQLAlchemy mappings are registered on Base.metadata.
# NOTE: Do not reload this module; reloading remaps classes and duplicates tables.
import models.entities  # noqa: F401


def _column_exists(connection, table: str, column: str) -> bool:
    result = connection.execute(text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result.fetchall())


def _table_exists(connection, table: str) -> bool:
    result = connection.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table"),
        {"table": table},
    )
    return result.first() is not None


def _apply_lightweight_migrations() -> None:
    with engine.begin() as connection:
        if _table_exists(connection, "templates") and not _column_exists(connection, "templates", "metadata_json"):
            connection.execute(text("ALTER TABLE templates ADD COLUMN metadata_json TEXT"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
