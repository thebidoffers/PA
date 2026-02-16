import pytest

pytest.importorskip("docx")

from pathlib import Path

from docx import Document as DocxDocument

from services.placeholder_service import replace_placeholders_in_docx


def test_replace_placeholders_in_paragraphs_and_tables(tmp_path):
    template_path = Path(tmp_path) / "placeholder_fixture.docx"

    document = DocxDocument()
    paragraph = document.add_paragraph()
    paragraph.add_run("Issuer: {{issuer")
    paragraph.add_run(".name}}")
    paragraph.add_run(" | Country: {{issuer.country}}")

    table = document.add_table(rows=1, cols=1)
    table.rows[0].cells[0].text = "Offer size: {{offer.size}}"

    document.save(str(template_path))

    loaded = DocxDocument(str(template_path))
    missing_fields = replace_placeholders_in_docx(
        loaded,
        {
            "issuer": {"name": "Acme Holdings"},
        },
    )

    assert loaded.paragraphs[0].text == "Issuer: Acme Holdings | Country: [[MISSING: issuer.country]]"
    assert loaded.tables[0].rows[0].cells[0].text == "Offer size: [[MISSING: offer.size]]"
    assert missing_fields == ["issuer.country", "offer.size"]
