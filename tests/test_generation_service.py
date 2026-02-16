import pytest

pytest.importorskip("docx")

import importlib
import json
from pathlib import Path

from docx import Document as DocxDocument


def test_generate_draft_docx_creates_file_and_db_rows(tmp_path, monkeypatch):
    db_file = tmp_path / "generation.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")

    session_module = importlib.import_module("db.session")
    importlib.reload(session_module)

    models_module = importlib.import_module("models.entities")
    importlib.reload(models_module)

    generation_service = importlib.import_module("services.generation_service")
    importlib.reload(generation_service)

    base = session_module.Base
    engine = session_module.engine
    base.metadata.create_all(bind=engine)

    template_path = tmp_path / "template.docx"
    template_doc = DocxDocument()
    template_doc.add_paragraph("Issuer: {{issuer.name}}")
    template_doc.add_paragraph("Offer Size: {{offer.size}}")
    template_doc.add_paragraph("Undisclosed: {{issuer.country}}")
    template_doc.save(str(template_path))

    session = session_module.SessionLocal()
    try:
        project = models_module.ProspectusProject(name="Project Gen")
        session.add(project)
        session.flush()

        template = models_module.Template(
            name="Draft Template",
            status="approved",
            sha256="a" * 64,
            file_path=str(template_path),
        )
        session.add(template)
        session.flush()

        source_document = models_module.Document(
            project_id=project.id,
            doc_type="original",
            file_name="source.docx",
            file_path=str(template_path),
            sha256="b" * 64,
            version=1,
        )
        session.add(source_document)
        session.flush()

        run = models_module.GenerationRun(
            project_id=project.id,
            template_id=template.id,
            source_document_id=source_document.id,
            status="pending",
            inputs_json=json.dumps({"seed": "value"}),
            output_path=None,
        )
        session.add(run)
        session.commit()

        result = generation_service.generate_draft_docx(
            project.id,
            template.id,
            {
                "issuer": {"name": "Acme Holdings"},
                "offer": {"size": "$10M"},
                "source_document_id": source_document.id,
            },
        )

        output_path = Path(result["output_path"])
        assert output_path.exists()

        created_document = session.get(models_module.Document, result["document_id"])
        assert created_document is not None
        assert created_document.doc_type == "draft"
        assert created_document.version == 1

        updated_run = session.get(models_module.GenerationRun, run.id)
        assert updated_run.status == "completed"
        assert updated_run.output_document_id == created_document.id

        generated_doc = DocxDocument(str(output_path))
        generated_text = "\n".join(paragraph.text for paragraph in generated_doc.paragraphs)
        assert "Missing Information" in generated_text
        assert "[[MISSING: issuer.country]]" in generated_text
    finally:
        session.close()
