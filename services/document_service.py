from pathlib import Path

from sqlalchemy.orm import Session

from models import Document


def normalize_document_type(file_name: str | None) -> str:
    suffix = Path(file_name or "").suffix.lower()
    if suffix == ".docx":
        return "docx"
    if suffix == ".pdf":
        return "pdf"
    return "unknown"


def get_project_source_docx_documents(session: Session, project_id: int) -> list[Document]:
    return (
        session.query(Document)
        .filter(Document.project_id == project_id, Document.doc_type == "docx")
        .order_by(Document.created_at.desc())
        .all()
    )
