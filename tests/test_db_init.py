import os
import sys

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
inspect = sqlalchemy.inspect


def test_init_db_creates_tables(tmp_path, monkeypatch):
    db_file = tmp_path / "test_init.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")

    for module_name in ("models.entities", "db.init_db", "db.session"):
        sys.modules.pop(module_name, None)

    import importlib

    session_module = importlib.import_module("db.session")
    init_db_module = importlib.import_module("db.init_db")

    init_db_module.init_db()
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
