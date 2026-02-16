import importlib

import pytest

pytest.importorskip("sqlalchemy")


def test_template_and_document_crud(tmp_path, monkeypatch):
    db_file = tmp_path / "test_crud.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")

    session_module = importlib.import_module("db.session")
    importlib.reload(session_module)

    models_module = importlib.import_module("models.entities")
    importlib.reload(models_module)

    base = session_module.Base
    engine = session_module.engine
    base.metadata.create_all(bind=engine)

    session = session_module.SessionLocal()
    try:
        project = models_module.ProspectusProject(name="Project A")
        session.add(project)
        session.commit()
        session.refresh(project)

        template = models_module.Template(
            name="Template One",
            status="draft",
            sha256="a" * 64,
            file_path="storage/templates/template_one.docx",
        )
        session.add(template)
        session.commit()
        session.refresh(template)

        document = models_module.Document(
            project_id=project.id,
            doc_type="original",
            file_name="orig.pdf",
            file_path=f"storage/projects/{project.id}/orig.pdf",
            sha256="b" * 64,
            version=1,
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        assert template.id is not None
        assert document.id is not None
    finally:
        session.close()
