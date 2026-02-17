import importlib
import sys

import pytest

pytest.importorskip("sqlalchemy")


def _init_test_modules(monkeypatch, db_file):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")

    session_module = importlib.import_module("db.session")
    importlib.reload(session_module)

    session_module.Base.metadata.clear()
    for module_name in ["models", "models.entities", "services.document_service"]:
        sys.modules.pop(module_name, None)

    models_module = importlib.import_module("models.entities")
    document_service = importlib.import_module("services.document_service")

    session_module.Base.metadata.create_all(bind=session_module.engine)
    return session_module, models_module, document_service


def test_normalize_document_type_from_filename_suffix(tmp_path, monkeypatch):
    _, _, document_service = _init_test_modules(monkeypatch, tmp_path / "test_document_type.db")

    assert document_service.normalize_document_type("issuer_source.DOCX") == "docx"
    assert document_service.normalize_document_type("prospectus.pdf") == "pdf"
    assert document_service.normalize_document_type("notes.txt") == "unknown"


def test_project_docx_query_returns_same_project_docs_only(tmp_path, monkeypatch):
    session_module, models_module, document_service = _init_test_modules(monkeypatch, tmp_path / "test_doc_query.db")

    session = session_module.SessionLocal()
    try:
        project_one = models_module.ProspectusProject(name="Project One")
        project_two = models_module.ProspectusProject(name="Project Two")
        session.add_all([project_one, project_two])
        session.commit()
        session.refresh(project_one)
        session.refresh(project_two)

        session.add_all(
            [
                models_module.Document(
                    project_id=project_one.id,
                    doc_type="docx",
                    file_name="project_one_source.docx",
                    file_path=f"storage/projects/{project_one.id}/project_one_source.docx",
                    sha256="a" * 64,
                    version=1,
                    is_locked=False,
                ),
                models_module.Document(
                    project_id=project_one.id,
                    doc_type="pdf",
                    file_name="project_one_source.pdf",
                    file_path=f"storage/projects/{project_one.id}/project_one_source.pdf",
                    sha256="b" * 64,
                    version=1,
                    is_locked=False,
                ),
                models_module.Document(
                    project_id=project_two.id,
                    doc_type="docx",
                    file_name="project_two_source.docx",
                    file_path=f"storage/projects/{project_two.id}/project_two_source.docx",
                    sha256="c" * 64,
                    version=1,
                    is_locked=False,
                ),
            ]
        )
        session.commit()

        project_one_docs = document_service.get_project_source_docx_documents(session, project_one.id)

        assert len(project_one_docs) == 1
        assert project_one_docs[0].project_id == project_one.id
        assert project_one_docs[0].doc_type == "docx"
        assert project_one_docs[0].file_name == "project_one_source.docx"
    finally:
        session.close()
