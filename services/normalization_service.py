from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any


def format_int_commas(n: int) -> str:
    return f"{int(n):,}"


def _normalize_decimal(value: int | float | str | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float):
        return Decimal(str(value))
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            raise ValueError("Empty numeric string")
        return Decimal(cleaned)
    raise ValueError(f"Unsupported numeric value: {value!r}")


def _is_integral(value: Decimal) -> bool:
    return value == value.to_integral_value()


def format_currency_aed(amount: int | float) -> str:
    amount_decimal = _normalize_decimal(amount)
    if _is_integral(amount_decimal):
        formatted = f"{int(amount_decimal):,}"
    else:
        formatted = f"{amount_decimal:,.2f}".rstrip("0").rstrip(".")
    return f"AED {formatted}"


def format_price_range_aed(low: float, high: float, decimals: int = 2) -> str:
    low_decimal = _normalize_decimal(low)
    high_decimal = _normalize_decimal(high)
    precision = Decimal(f"1.{'0' * decimals}")
    low_text = f"{low_decimal.quantize(precision):.{decimals}f}"
    high_text = f"{high_decimal.quantize(precision):.{decimals}f}"
    return f"AED {low_text} – AED {high_text}"


def format_percent(p: float) -> str:
    decimal_value = _normalize_decimal(p)
    text = f"{decimal_value.normalize():f}" if not _is_integral(decimal_value) else str(int(decimal_value))
    return f"{text}%"


def _parse_json_like(raw_inputs_json: str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(raw_inputs_json, Mapping):
        return dict(raw_inputs_json)
    parsed = json.loads(raw_inputs_json)
    if not isinstance(parsed, dict):
        raise ValueError("raw_inputs_json must decode to an object")
    return parsed


def _deep_get(data: Mapping[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _deep_set(data: dict[str, Any], path: str, value: Any) -> None:
    current: dict[str, Any] = data
    parts = path.split(".")
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _render_or_missing(path: str, value: str | None, missing_fields: set[str]) -> str:
    if value is None or not str(value).strip():
        missing_fields.add(path)
        return f"[[MISSING: {path}]]"
    return value


def normalize_inputs(
    schema_id: str,
    raw_inputs_json: str | Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    if schema_id != "talabat_v1":
        raise ValueError(f"Unsupported schema_id: {schema_id}")

    raw = _parse_json_like(raw_inputs_json)
    normalized_inputs = dict(raw)
    missing_fields: set[str] = set()

    _deep_set(normalized_inputs, "offer.currency", "AED")

    rendered_fields_map: dict[str, str] = {}

    issuer_name = _deep_get(raw, "issuer.name")
    issuer_text = None if issuer_name is None else str(issuer_name).strip()
    rendered_fields_map["issuer.name"] = _render_or_missing("issuer.name", issuer_text, missing_fields)

    offer_shares_value = _deep_get(raw, "offer.offer_shares")
    offer_shares_text: str | None = None
    if offer_shares_value is not None and str(offer_shares_value).strip():
        try:
            offer_shares = int(_normalize_decimal(offer_shares_value))
            if offer_shares > 0:
                _deep_set(normalized_inputs, "offer.offer_shares", offer_shares)
                offer_shares_text = format_int_commas(offer_shares)
        except (ValueError, InvalidOperation):
            offer_shares_text = None
    rendered_fields_map["offer.offer_shares"] = _render_or_missing(
        "offer.offer_shares", offer_shares_text, missing_fields
    )

    low_value = _deep_get(raw, "offer.price_range_low_aed")
    high_value = _deep_get(raw, "offer.price_range_high_aed")
    price_range_text: str | None = None
    if low_value is not None and high_value is not None:
        try:
            low = float(_normalize_decimal(low_value))
            high = float(_normalize_decimal(high_value))
            _deep_set(normalized_inputs, "offer.price_range_low_aed", low)
            _deep_set(normalized_inputs, "offer.price_range_high_aed", high)
            if low < high:
                price_range_text = format_price_range_aed(low, high)
        except (ValueError, InvalidOperation):
            price_range_text = None

    rendered_fields_map["offer.price_range"] = _render_or_missing(
        "offer.price_range", price_range_text, missing_fields
    )

    nominal_value = _deep_get(raw, "offer.nominal_value_per_share_aed")
    nominal_text: str | None = None
    if nominal_value is not None and str(nominal_value).strip():
        try:
            nominal = float(_normalize_decimal(nominal_value))
            _deep_set(normalized_inputs, "offer.nominal_value_per_share_aed", nominal)
            nominal_text = f"AED {nominal:.2f}"
        except (ValueError, InvalidOperation):
            nominal_text = None
    rendered_fields_map["offer.nominal_value_per_share"] = _render_or_missing(
        "offer.nominal_value_per_share", nominal_text, missing_fields
    )

    percentage_value = _deep_get(raw, "offer.percentage_offered")
    percentage_text: str | None = None
    if percentage_value is not None and str(percentage_value).strip():
        try:
            percentage = float(_normalize_decimal(percentage_value))
            _deep_set(normalized_inputs, "offer.percentage_offered", percentage)
            percentage_text = format_percent(percentage)
        except (ValueError, InvalidOperation):
            percentage_text = None
    rendered_fields_map["offer.percentage_offered"] = _render_or_missing(
        "offer.percentage_offered", percentage_text, missing_fields
    )

    rendered_fields_map["offer.offer_shares_words"] = _render_or_missing(
        "offer.offer_shares_words", None, missing_fields
    )

    legacy_offer_size = rendered_fields_map["offer.offer_shares"]
    rendered_fields_map["offer.size"] = legacy_offer_size

    for key, value in rendered_fields_map.items():
        _deep_set(normalized_inputs, key, value)

    return normalized_inputs, rendered_fields_map, sorted(missing_fields)
