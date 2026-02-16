import json
from pathlib import Path
from typing import Any

import streamlit as st

from db.init_db import init_db
from db.session import SessionLocal
from models import Document, ProspectusProject, Template
from services.auto_generation_form_service import (
    build_raw_inputs_payload,
    build_template_form_spec,
    extract_template_placeholders,
    find_unresolved_template_placeholders,
    load_schema,
    validate_required_paths,
)
from services.deal_profile_service import get_latest_profile, save_profile
from services.document_service import extract_preview_and_outline
from services.generation_service import generate_draft_docx
from services.normalization_service import normalize_inputs

init_db()

st.title("AUTO GENERATION")
st.caption("Schema-driven deal inputs + assembly + generation runs.")

session = SessionLocal()
try:
    templates = session.query(Template).order_by(Template.created_at.desc()).all()
    projects = session.query(ProspectusProject).order_by(ProspectusProject.created_at.desc()).all()
finally:
    session.close()

if not templates or not projects:
    st.info("You need at least one template and one project to start generation.")
    st.stop()

try:
    schema = load_schema()
except (FileNotFoundError, ValueError) as exc:
    st.error(str(exc))
    st.stop()

field_meta = {field["path"]: field for field in schema["fields"]}


def _field_help(path: str) -> str:
    field = field_meta[path]
    return f"{field['help_text']} Example: {field['example']}"


def _field_state_key(path: str) -> str:
    return f"deal_input__{path.replace('.', '__')}"


def _coerce_loaded_value(path: str, value: Any) -> Any:
    field_type = field_meta[path]["type"]
    if field_type == "list_string":
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
        return "" if value is None else str(value)
    return value


def _set_form_values(values_by_path: dict[str, Any]) -> None:
    for path, value in values_by_path.items():
        st.session_state[_field_state_key(path)] = _coerce_loaded_value(path, value)


def _deep_get(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _extract_values_for_paths(payload: dict[str, Any], paths: list[str]) -> dict[str, Any]:
    return {path: _deep_get(payload, path) for path in paths}


template = st.selectbox("Template", options=templates, format_func=lambda t: f"#{t.id} {t.name} ({t.status})")
project = st.selectbox("Project", options=projects, format_func=lambda p: f"#{p.id} {p.name}")

template_placeholders = extract_template_placeholders(Path(template.file_path))
if not template_placeholders:
    st.error(
        "Selected template has placeholder_count=0. Generation is blocked. "
        "Use Templates → Auto-Parameterize from Source Prospectus first."
    )
    st.stop()

form_spec = build_template_form_spec(template_placeholders, schema)
if not form_spec["fields"]:
    st.warning("No Talabat schema-mapped placeholders were detected in this template.")

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

use_template_as_source = False
source_document = None
source_for_preview_path = template.file_path

if project_documents:
    source_document = st.selectbox(
        "Source document",
        options=project_documents,
        format_func=lambda d: f"#{d.id} {d.doc_type} v{d.version} ({d.file_name})",
    )
    source_for_preview_path = source_document.file_path
else:
    st.warning("Selected project has no documents.")
    use_template_as_source = st.checkbox(
        "Use selected template as source document for preview (skip project upload)",
        value=False,
    )
    if not use_template_as_source:
        st.info("Enable the checkbox above to preview from the template and generate without a project upload.")

if source_document is not None or use_template_as_source:
    preview_data = extract_preview_and_outline(source_for_preview_path)

    st.divider()
    left, right = st.columns(2)
    with left:
        st.subheader("Extracted Text Preview")
        st.text_area("Preview", value=preview_data["preview"] or "(empty text)", height=260, disabled=True)

    with right:
        st.subheader("Outline JSON Preview")
        st.code(json.dumps(preview_data["outline"], indent=2), language="json")

latest_profile = get_latest_profile(project.id, schema["schema_id"], template.id)
profile_available = latest_profile is not None
load_profile = st.toggle("Load last saved deal profile", value=profile_available)
if load_profile and latest_profile is not None:
    if st.button("Load profile values into form", key="load_deal_profile_values"):
        loaded_payload = json.loads(latest_profile.inputs_raw_json)
        _set_form_values(_extract_values_for_paths(loaded_payload, form_spec["requested_paths"]))
        st.success("Loaded last saved deal profile values.")
elif load_profile and latest_profile is None:
    st.info("No previously saved deal profile found for this project/template.")

st.divider()
st.subheader("Deal Profile Inputs (template placeholders only)")

field_values: dict[str, Any] = {}
for field in form_spec["fields"]:
    path = field["path"]
    key = _field_state_key(path)
    label = field["label"]
    help_text = _field_help(path)

    field_type = field["type"]
    if field_type in {"string", "rich_text"}:
        widget = st.text_area if field_type == "rich_text" else st.text_input
        if key not in st.session_state:
            st.session_state[key] = ""
        field_values[path] = widget(label, key=key, help=help_text)
    elif field_type == "list_string":
        if key not in st.session_state:
            st.session_state[key] = ""
        field_values[path] = st.text_area(
            f"{label} (one per line)",
            key=key,
            help=help_text,
        )
    elif field_type == "integer":
        if key not in st.session_state:
            st.session_state[key] = 0
        field_values[path] = st.number_input(label, step=1, key=key, help=help_text)
    elif field_type in {"decimal", "percent"}:
        if key not in st.session_state:
            st.session_state[key] = 0.0
        field_values[path] = st.number_input(
            label,
            step=0.01,
            format="%.2f",
            key=key,
            help=help_text,
        )

source_document_id = source_document.id if source_document is not None else None
raw_inputs_payload = build_raw_inputs_payload(
    schema_id=schema["schema_id"],
    project_id=project.id,
    template_id=template.id,
    source_document_id=source_document_id,
    use_template_as_source=use_template_as_source,
    field_values=field_values,
)

normalized_payload, rendered_preview, _ = normalize_inputs(schema["schema_id"], raw_inputs_payload)

st.subheader("Normalized Preview")
st.json({key: rendered_preview[key] for key in sorted(rendered_preview) if key in template_placeholders})

confirm_disclaimer = st.checkbox(
    "I confirm all facts are verified and that missing facts are marked as TBD or [[MISSING: field]]."
)

if st.button("Generate"):
    required_errors = validate_required_paths(form_spec["required_paths"], raw_inputs_payload, rendered_preview)
    unresolved_fields = find_unresolved_template_placeholders(template_placeholders, rendered_preview)

    if source_document is None and not use_template_as_source:
        required_errors.append("Select a source document or enable 'Use selected template as source document'.")

    if required_errors:
        for error in required_errors:
            st.error(error)
    elif not confirm_disclaimer:
        st.error("You must confirm the disclaimer before generating.")
    else:
        save_profile(
            project_id=project.id,
            schema_id=schema["schema_id"],
            template_id=template.id,
            inputs_raw=raw_inputs_payload,
            inputs_normalized=normalized_payload,
        )

        result = generate_draft_docx(project.id, template.id, normalized_payload)

        output_path = Path(result["output_path"])
        st.success(f"Generation run #{result['generation_run_id']} completed.")

        if unresolved_fields:
            st.warning("Missing fields (template placeholders only): " + ", ".join(unresolved_fields))

        with output_path.open("rb") as generated_file:
            st.download_button(
                label="Download Generated Draft DOCX",
                data=generated_file.read(),
                file_name=output_path.name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"generated_download_{result['document_id']}",
            )
