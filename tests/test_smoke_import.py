import pytest

pytest.importorskip("sqlalchemy")


def test_smoke_imports():
    import db.init_db  # noqa: F401
    import models  # noqa: F401
    import services.document_service  # noqa: F401
    import services.file_service  # noqa: F401
