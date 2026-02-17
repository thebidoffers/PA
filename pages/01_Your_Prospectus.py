from pathlib import Path

import streamlit as st

from db.init_db import init_db
from db.session import SessionLocal
from models import Document, ProspectusProject
from services.document_service import normalize_document_type
from services.file_service import save_uploaded_file

init_db()

st.title("YOUR PROSPECTUS")
st.caption("Upload, version, preview, and lock project documents.")

session = SessionLocal()
try:
    projects = session.query(ProspectusProject).order_by(ProspectusProject.created_at.desc()).all()
finally:
    session.close()

project_options = {"Create new project": None}
for project in projects:
    project_options[f"{project.name} (ID {project.id})"] = project.id

selected_project_label = st.selectbox("Project", options=list(project_options.keys()))
selected_project_id = project_options[selected_project_label]

if selected_project_id is None:
    with st.form("create_project_form"):
        project_name = st.text_input("New project name", placeholder="e.g., 2026 IPO Draft")
        create_project = st.form_submit_button("Create Project")

    if create_project:
        if not project_name.strip():
            st.error("Project name is required.")
        else:
            session = SessionLocal()
            try:
                existing = session.query(ProspectusProject).filter_by(name=project_name.strip()).first()
                if existing:
                    st.warning("Project already exists. Select it from the dropdown.")
                else:
                    new_project = ProspectusProject(name=project_name.strip())
                    session.add(new_project)
                    session.commit()
                    st.success("Project created. Reload or reselect to continue.")
            finally:
                session.close()
else:
    session = SessionLocal()
    try:
        current_project = session.get(ProspectusProject, selected_project_id)
    finally:
        session.close()

    st.subheader(f"Project: {current_project.name}")
    st.write(f"Final locked status: **{current_project.locked_final}**")

    with st.form("upload_project_document_form"):
        uploaded_doc = st.file_uploader("Upload PDF/DOCX", type=["pdf", "docx"])
        upload_document = st.form_submit_button("Upload Document")

    if upload_document:
        if uploaded_doc is None:
            st.error("Please choose a PDF or DOCX file.")
        else:
            session = SessionLocal()
            try:
                normalized_doc_type = normalize_document_type(uploaded_doc.name)
                existing_versions = (
                    session.query(Document)
                    .filter(Document.project_id == selected_project_id, Document.doc_type == normalized_doc_type)
                    .count()
                )
                next_version = existing_versions + 1
                destination_dir = f"storage/projects/{selected_project_id}"
                destination_name = f"v{next_version}_{uploaded_doc.name}"
                file_path, file_sha256 = save_uploaded_file(uploaded_doc, destination_dir, destination_name)

                doc = Document(
                    project_id=selected_project_id,
                    doc_type=normalized_doc_type,
                    file_name=uploaded_doc.name,
                    file_path=str(file_path),
                    sha256=file_sha256,
                    version=next_version,
                    is_locked=False,
                )
                session.add(doc)
                session.commit()
                st.success("Document uploaded and versioned.")
            finally:
                session.close()

    session = SessionLocal()
    try:
        documents = (
            session.query(Document)
            .filter(Document.project_id == selected_project_id)
            .order_by(Document.created_at.desc())
            .all()
        )
    finally:
        session.close()

    st.divider()
    st.subheader("Project Documents")

    if not documents:
        st.info("No documents uploaded yet.")
    else:
        table_data = [
            {
                "ID": d.id,
                "Type": d.doc_type,
                "Version": d.version,
                "File": d.file_name,
                "SHA256": d.sha256,
                "Locked": d.is_locked,
                "Created At": d.created_at,
            }
            for d in documents
        ]
        st.dataframe(table_data, use_container_width=True)

        st.markdown("#### Downloads")
        for d in documents:
            document_path = Path(d.file_path)
            if document_path.exists():
                with document_path.open("rb") as f:
                    st.download_button(
                        label=f"Download Document #{d.id} ({d.doc_type} v{d.version})",
                        data=f.read(),
                        file_name=document_path.name,
                        key=f"document_download_{d.id}",
                    )

        target_doc = st.selectbox(
            "Select document to lock",
            options=documents,
            format_func=lambda d: f"ID {d.id} | {d.doc_type} v{d.version} | {d.file_name}",
        )
        if st.button("Lock selected document"):
            session = SessionLocal()
            try:
                db_doc = session.get(Document, target_doc.id)
                db_doc.is_locked = True
                project = session.get(ProspectusProject, selected_project_id)
                project.locked_final = True
                session.commit()
                st.success("Selected document locked.")
            finally:
                session.close()
