import json
import re
from pathlib import Path
from typing import Any

from docx import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph

from db.session import SessionLocal
from models import Template
from services.file_service import ensure_dir, sha256_bytes
from services.prospectus_analysis_service import analyze_prospectus


PRICE_RANGE_VARIANTS = [
    "{currency} {low:.2f} – {currency} {high:.2f}",
    "{currency} {low:.2f}-{currency} {high:.2f}",
    "{currency} {low:.2f} - {currency} {high:.2f}",
    "{currency} {low:.2f} to {currency} {high:.2f}",
]


def _replace_match_in_runs(paragraph: Paragraph, pattern: re.Pattern[str], replacement: str) -> int:
    if not paragraph.runs:
        return 0

    replacements = 0
    while True:
        runs = paragraph.runs
        run_ranges: list[tuple[int, int]] = []
        cursor = 0
        for run in runs:
            run_text = run.text
            run_ranges.append((cursor, cursor + len(run_text)))
            cursor += len(run_text)

        full_text = "".join(run.text for run in runs)
        match = pattern.search(full_text)
        if not match:
            break

        span_start, span_end = match.span()
        overlap_indexes = [
            i
            for i, (start, end) in enumerate(run_ranges)
            if start < span_end and end > span_start
        ]
        if not overlap_indexes:
            break

        first_index = overlap_indexes[0]
        last_index = overlap_indexes[-1]
        first_start, _ = run_ranges[first_index]
        last_start, _ = run_ranges[last_index]

        prefix = runs[first_index].text[: max(0, span_start - first_start)]
        suffix = runs[last_index].text[max(0, span_end - last_start) :]

        runs[first_index].text = f"{prefix}{replacement}"
        for index in overlap_indexes[1:-1]:
            runs[index].text = ""
        if last_index != first_index:
            runs[last_index].text = suffix
        else:
            runs[first_index].text = f"{prefix}{replacement}{suffix}"

        replacements += 1

    return replacements


def _iter_containers(document: DocxDocument):
    yield document, "document"
    for t_index, table in enumerate(document.tables):
        yield from _iter_table(table, f"document/tables/{t_index}")


def _iter_table(table: Table, table_path: str):
    for r_index, row in enumerate(table.rows):
        for c_index, cell in enumerate(row.cells):
            cell_path = f"{table_path}/rows/{r_index}/cells/{c_index}"
            yield cell, cell_path
            for nested_t_index, nested in enumerate(cell.tables):
                yield from _iter_table(nested, f"{cell_path}/tables/{nested_t_index}")


def _replace_field(
    document: DocxDocument,
    placeholder: str,
    patterns: list[re.Pattern[str]],
    allowed_paths: set[str],
) -> list[dict[str, Any]]:
    report_items: list[dict[str, Any]] = []
    block_counter = 0
    for container, container_path in _iter_containers(document):
        for p_index, paragraph in enumerate(container.paragraphs):
            if container_path == "document":
                location_path = f"document/paragraphs/{p_index}"
                block_type = "paragraph"
            else:
                location_path = f"{container_path}/paragraphs/{p_index}"
                block_type = "table_cell"

            if allowed_paths:
                is_allowed = any(
                    location_path == allowed or location_path.startswith(f"{allowed}/")
                    for allowed in allowed_paths
                )
                if not is_allowed:
                    block_counter += 1
                    continue

            original_text = paragraph.text
            total_here = 0
            for pattern in patterns:
                total_here += _replace_match_in_runs(paragraph, pattern, placeholder)

            if total_here > 0:
                report_items.append(
                    {
                        "block_id": f"block-{block_counter}",
                        "block_type": block_type,
                        "location_path": location_path,
                        "placeholder": placeholder,
                        "count": total_here,
                        "original_text_snippet": original_text[:160],
                    }
                )
            block_counter += 1
    return report_items


def _build_patterns(inputs: dict[str, Any]) -> dict[str, list[re.Pattern[str]]]:
    issuer_name = str(inputs.get("issuer", {}).get("name") or "").strip()
    offer = inputs.get("offer", {})

    patterns: dict[str, list[re.Pattern[str]]] = {}

    if issuer_name:
        escaped = re.escape(issuer_name)
        patterns["{{issuer.name}}"] = [re.compile(escaped), re.compile(escaped, re.IGNORECASE)]

    offer_shares = offer.get("offer_shares")
    if offer_shares is not None:
        formatted = f"{int(offer_shares):,}"
        patterns["{{offer.offer_shares}}"] = [re.compile(re.escape(formatted))]

    percentage = offer.get("percentage_offered")
    if percentage is not None:
        percent_text = f"{float(percentage):g}%"
        patterns["{{offer.percentage_offered}}"] = [re.compile(re.escape(percent_text))]

    nominal = offer.get("nominal_value_per_share_aed")
    if nominal is not None:
        nominal_text = f"AED {float(nominal):.2f}"
        patterns["{{offer.nominal_value_per_share}}"] = [re.compile(re.escape(nominal_text), re.IGNORECASE)]

    low = offer.get("price_range_low_aed")
    high = offer.get("price_range_high_aed")
    if low is not None and high is not None:
        variants = [
            v.format(currency="AED", low=float(low), high=float(high))
            for v in PRICE_RANGE_VARIANTS
        ]
        patterns["{{offer.price_range}}"] = [re.compile(re.escape(v), re.IGNORECASE) for v in variants]

    return patterns


def _next_template_version(session, template_name: str) -> int:
    latest = (
        session.query(Template)
        .filter(Template.name == template_name)
        .order_by(Template.version.desc())
        .first()
    )
    return 1 if latest is None else latest.version + 1


def _safe_stem(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip())
    return cleaned.strip("_") or "parameterized_template"


def parameterize_template_from_source(
    source_docx_path: str,
    inputs: dict[str, Any],
    base_template_id: int,
    source_document_id: int,
    project_id: int,
    aliases: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    _ = aliases
    analysis = analyze_prospectus(
        source_docx_path,
        issuer_name=str(inputs.get("issuer", {}).get("name") or "").strip() or None,
        offer_shares=inputs.get("offer", {}).get("offer_shares"),
    )
    allowed_paths = {
        block["location_path"]
        for block in analysis["blocks"]
        if block["classification"] in {"deal_specific", "mixed"}
    }

    document = DocxDocument(source_docx_path)
    patterns = _build_patterns(inputs)
    report_entries: list[dict[str, Any]] = []

    for placeholder, pattern_list in patterns.items():
        report_entries.extend(_replace_field(document, placeholder, pattern_list, allowed_paths))

    placeholder_count = sum(item["count"] for item in report_entries)
    unresolved = sorted({placeholder for placeholder in patterns if placeholder not in {r['placeholder'] for r in report_entries}})

    if placeholder_count == 0:
        raise ValueError(
            "No placeholders were inserted. This is likely a static prospectus with unmatched patterns for the provided inputs."
        )

    session = SessionLocal()
    try:
        base_template = session.get(Template, base_template_id)
        if base_template is None:
            raise ValueError(f"Base template not found: {base_template_id}")

        parameterized_name = f"{base_template.name} (parameterized)"
        next_version = _next_template_version(session, parameterized_name)
        output_dir = ensure_dir(Path("storage") / "templates" / "parameterized")
        output_name = f"{_safe_stem(base_template.name)}_v{next_version}.docx"
        output_path = output_dir / output_name

        document.save(str(output_path))
        file_bytes = output_path.read_bytes()

        metadata = {
            "source_template_id": base_template_id,
            "parameterized_from_document_id": source_document_id,
            "placeholder_count": placeholder_count,
            "report": report_entries,
            "analysis_counts": analysis["counts"],
        }

        template = Template(
            name=parameterized_name,
            status="draft",
            sha256=sha256_bytes(file_bytes),
            file_path=str(output_path),
            version=next_version,
            metadata_json=json.dumps(metadata),
        )
        session.add(template)
        session.commit()
        session.refresh(template)

        return {
            "template_id": template.id,
            "new_template_docx_path": str(output_path),
            "parameterization_report": {
                "placeholder_count": placeholder_count,
                "replacements": report_entries,
                "unresolved": unresolved,
            },
            "analysis": analysis,
        }
    finally:
        session.close()
