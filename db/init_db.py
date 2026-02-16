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


def _create_deal_profiles_table(connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS deal_profiles (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                template_id INTEGER,
                schema_id VARCHAR(100) NOT NULL,
                inputs_raw_json TEXT NOT NULL,
                inputs_normalized_json TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(project_id) REFERENCES prospectus_projects(id),
                FOREIGN KEY(template_id) REFERENCES templates(id)
            )
            """
        )
    )
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_deal_profiles_id ON deal_profiles (id)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_deal_profiles_project_id ON deal_profiles (project_id)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_deal_profiles_template_id ON deal_profiles (template_id)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_deal_profiles_schema_id ON deal_profiles (schema_id)"))


def _apply_lightweight_migrations() -> None:
    with engine.begin() as connection:
        if _table_exists(connection, "templates") and not _column_exists(connection, "templates", "metadata_json"):
            connection.execute(text("ALTER TABLE templates ADD COLUMN metadata_json TEXT"))
        if not _table_exists(connection, "deal_profiles"):
            _create_deal_profiles_table(connection)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
