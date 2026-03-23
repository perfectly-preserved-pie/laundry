"""Helpers for low-cardinality categorical filters in community AG Grid."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

BLANK_FILTER_TOKEN = "__laundry_blank__"


def encode_filter_value(value: Any) -> str:
    """Convert a cell value into the token used by the custom set filter."""

    if value in (None, ""):
        return BLANK_FILTER_TOKEN
    return str(value)


def format_filter_label(value: Any) -> str:
    """Create the display label for a custom set filter option."""

    if value in (None, ""):
        return "(Blank)"
    return str(value)


def build_filter_options(values: Iterable[Any]) -> list[dict[str, str]]:
    """Return unique, ordered filter options for a low-cardinality column."""

    seen_tokens: set[str] = set()
    options: list[dict[str, str]] = []

    for value in values:
        token = encode_filter_value(value)
        if token in seen_tokens:
            continue

        seen_tokens.add(token)
        options.append({"value": token, "label": format_filter_label(value)})

    options.sort(
        key=lambda option: (
            option["value"] == BLANK_FILTER_TOKEN,
            option["label"].casefold(),
        )
    )
    return options
