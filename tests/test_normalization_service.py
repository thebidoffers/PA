from services.normalization_service import (
    format_currency_aed,
    format_int_commas,
    format_percent,
    format_price_range_aed,
    normalize_inputs,
)


def test_number_and_currency_formatting() -> None:
    assert format_int_commas(3493236093) == "3,493,236,093"
    assert format_currency_aed(5000) == "AED 5,000"


def test_format_price_range_aed_matches_required_output() -> None:
    assert format_price_range_aed(1.3, 1.5) == "AED 1.30 – AED 1.50"


def test_format_percent() -> None:
    assert format_percent(15) == "15%"


def test_normalize_inputs_generates_rendered_map_and_aliases() -> None:
    normalized, rendered, missing = normalize_inputs(
        "talabat_v1",
        {
            "issuer": {"name": "Talabat Holding plc"},
            "offer": {
                "offer_shares": 3493236093,
                "price_range_low_aed": 1.3,
                "price_range_high_aed": 1.5,
                "nominal_value_per_share_aed": 0.04,
                "percentage_offered": 15,
            },
        },
    )

    assert normalized["offer"]["currency"] == "AED"
    assert rendered["offer.offer_shares"] == "3,493,236,093"
    assert rendered["offer.size"] == "3,493,236,093"
    assert rendered["offer.price_range"] == "AED 1.30 – AED 1.50"
    assert rendered["offer.nominal_value_per_share"] == "AED 0.04"
    assert rendered["offer.percentage_offered"] == "15%"
    assert "offer.offer_shares_words" in missing
