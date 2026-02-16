import os

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
inspect = sqlalchemy.inspect


def test_init_db_creates_tables(tmp_path, monkeypatch):
    db_file = tmp_path / "test_init.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")

    import importlib

    session_module = importlib.import_module("db.session")
    importlib.reload(session_module)

    import db.init_db as init_db_module

    importlib.reload(init_db_module)
    init_db_module.init_db()

    inspector = inspect(session_module.engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "users",
        "templates",
        "prospectus_projects",
        "documents",
        "extracted_structures",
        "generation_runs",
        "audit_logs",
    }
    assert expected_tables.issubset(table_names)
    assert os.path.exists(db_file)
