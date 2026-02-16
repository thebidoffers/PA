import pytest

pytest.importorskip("docx")

from services.auto_generation_form_service import (
    build_template_form_spec,
    find_unresolved_template_placeholders,
    load_schema,
)


def test_build_template_form_spec_is_placeholder_driven():
    schema = load_schema()
    placeholders = ["issuer.name", "offer.price_range", "issuer.country"]

    form_spec = build_template_form_spec(placeholders, schema)

    assert form_spec["schema_id"] == "talabat_v1"
    assert form_spec["requested_paths"] == [
        "issuer.name",
        "offer.price_range_high_aed",
        "offer.price_range_low_aed",
    ]
    assert form_spec["required_paths"] == [
        "issuer.name",
        "offer.price_range_high_aed",
        "offer.price_range_low_aed",
    ]


def test_find_unresolved_template_placeholders_only_reports_selected_template_fields():
    placeholders = ["issuer.name", "offer.offer_shares", "issuer.country"]
    rendered = {
        "issuer.name": "Acme Holdings",
        "offer.offer_shares": "[[MISSING: offer.offer_shares]]",
        "key_dates": "[[MISSING: key_dates]]",
    }

    unresolved = find_unresolved_template_placeholders(placeholders, rendered)

    assert unresolved == ["issuer.country", "offer.offer_shares"]
