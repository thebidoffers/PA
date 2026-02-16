import json

import streamlit as st

from db.init_db import init_db
from db.session import SessionLocal
from models import Document, GenerationRun, ProspectusProject, Template
from services.document_service import extract_preview_and_outline

init_db()

st.title("AUTO GENERATION")
st.caption("Validated inputs + assembly + generation runs.")

session = SessionLocal()
try:
    templates = session.query(Template).order_by(Template.created_at.desc()).all()
    projects = session.query(ProspectusProject).order_by(ProspectusProject.created_at.desc()).all()
finally:
    session.close()

if not templates or not projects:
    st.info("You need at least one template and one project to start generation.")
    st.stop()

template = st.selectbox("Template", options=templates, format_func=lambda t: f"#{t.id} {t.name} ({t.status})")
project = st.selectbox("Project", options=projects, format_func=lambda p: f"#{p.id} {p.name}")

session = SessionLocal()
try:
    project_documents = (
        session.query(Document)
        .filter(Document.project_id == project.id)
        .order_by(Document.created_at.desc())
        .all()
    )
finally:
    session.close()

if not project_documents:
    st.warning("Selected project has no documents.")
    st.stop()

source_document = st.selectbox(
    "Source document",
    options=project_documents,
    format_func=lambda d: f"#{d.id} {d.doc_type} v{d.version} ({d.file_name})",
)

preview_data = extract_preview_and_outline(source_document.file_path)

st.divider()
left, right = st.columns(2)
with left:
    st.subheader("Extracted Text Preview")
    st.text_area("Preview", value=preview_data["preview"] or "(empty text)", height=260, disabled=True)

with right:
    st.subheader("Outline JSON Preview")
    st.code(json.dumps(preview_data["outline"], indent=2), language="json")

st.divider()
st.subheader("Generation Inputs")

issuer_name = st.text_input("issuer.name", value="TBD")
offer_size = st.text_input("offer.size", value="[[MISSING: offer.size]]")
offer_price_range = st.text_input("offer.price_range", value="[[MISSING: offer.price_range]]")
key_dates = st.text_input("key_dates", value="[[MISSING: key_dates]]")
business_description = st.text_area("business_description", value="[[MISSING: business_description]]")
risk_factors = st.text_area(
    "risk_factors (one per line)",
    value="[[MISSING: risk_factor_1]]\n[[MISSING: risk_factor_2]]",
)

confirm_disclaimer = st.checkbox(
    "I confirm all facts are verified and that missing facts are marked as TBD or [[MISSING: field]]."
)

if st.button("Generate"):
    if not confirm_disclaimer:
        st.error("You must confirm the disclaimer before generating.")
    else:
        inputs_payload = {
            "issuer": {"name": issuer_name or "TBD"},
            "offer": {
                "size": offer_size or "[[MISSING: offer.size]]",
                "price_range": offer_price_range or "[[MISSING: offer.price_range]]",
            },
            "key_dates": key_dates or "[[MISSING: key_dates]]",
            "business_description": business_description or "[[MISSING: business_description]]",
            "risk_factors": [rf.strip() for rf in risk_factors.splitlines() if rf.strip()],
            "source_document_id": source_document.id,
            "template_id": template.id,
            "project_id": project.id,
        }

        session = SessionLocal()
        try:
            generation_run = GenerationRun(
                project_id=project.id,
                template_id=template.id,
                source_document_id=source_document.id,
                status="completed",
                inputs_json=json.dumps(inputs_payload),
                output_path=None,
            )
            session.add(generation_run)
            session.commit()
            st.success(f"Generation run #{generation_run.id} recorded with placeholder status completed.")
        finally:
            session.close()
