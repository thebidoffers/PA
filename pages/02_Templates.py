from pathlib import Path

import streamlit as st

from db.init_db import init_db
from db.session import SessionLocal
from models import Template
from services.file_service import save_uploaded_file

init_db()

st.title("TEMPLATES")
st.caption("Manage your template library (upload, status, preview, and download).")

with st.form("template_upload_form"):
    st.subheader("Upload Template")
    template_name = st.text_input("Template name", placeholder="e.g., Standard Prospectus Template v1")
    status = st.selectbox("Status", options=["draft", "approved"], index=0)
    uploaded_template = st.file_uploader("Upload DOCX template", type=["docx"])
    submitted = st.form_submit_button("Save Template")

if submitted:
    if not template_name.strip() or uploaded_template is None:
        st.error("Template name and DOCX file are required.")
    else:
        safe_name = f"{template_name.strip().replace(' ', '_')}_{uploaded_template.name}"
        file_path, file_sha256 = save_uploaded_file(uploaded_template, "storage/templates", safe_name)

        session = SessionLocal()
        try:
            template = Template(
                name=template_name.strip(),
                status=status,
                sha256=file_sha256,
                file_path=str(file_path),
            )
            session.add(template)
            session.commit()
            st.success("Template saved.")
        finally:
            session.close()

st.divider()
st.subheader("Template Library")

session = SessionLocal()
try:
    templates = session.query(Template).order_by(Template.created_at.desc()).all()
finally:
    session.close()

if not templates:
    st.info("No templates available yet.")
else:
    table_data = [
        {
            "ID": t.id,
            "Name": t.name,
            "Status": t.status,
            "Version": t.version,
            "SHA256": t.sha256,
            "Path": t.file_path,
            "Created At": t.created_at,
        }
        for t in templates
    ]
    st.dataframe(table_data, use_container_width=True)

    st.markdown("#### Downloads")
    for t in templates:
        template_path = Path(t.file_path)
        if template_path.exists():
            with template_path.open("rb") as f:
                st.download_button(
                    label=f"Download Template #{t.id}: {t.name}",
                    data=f.read(),
                    file_name=template_path.name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"template_download_{t.id}",
                )
        else:
            st.warning(f"File not found for template #{t.id}: {t.file_path}")
