"""Helpers for loading and matching scraped enrichment CSVs."""

from __future__ import annotations

from collections import defaultdict
import csv
from functools import lru_cache
import os
from pathlib import Path
import re
from typing import Any

from laundry_app.scraping.normalize import canonical_form, normalize_identifier


ENRICHMENT_FILENAMES = (
    "product_sources.csv",
    "ingredients_long.csv",
)
WHITESPACE_RE = re.compile(r"\s+")
ProductEnrichment = dict[str, list[dict[str, Any]]]


def _clean_text(value: Any) -> str | None:
    """Normalize a raw CSV value into a trimmed string."""

    if value is None:
        return None

    text = WHITESPACE_RE.sub(" ", str(value).replace("\xa0", " ")).strip()
    return text or None


def _coerce_row_value(field: str, value: Any) -> Any:
    """Apply light type coercion to known enrichment fields."""

    text = _clean_text(value)
    if text is None:
        return None

    if field == "position":
        try:
            return int(text)
        except ValueError:
            return text

    return text


def enrichment_dir_candidates() -> list[Path]:
    """Return the ordered set of enrichment directories to try."""

    candidates: list[Path] = []

    env_path = os.getenv("LAUNDRY_ENRICHMENT_DIR")
    if env_path:
        candidates.append(Path(env_path))

    candidates.append(Path(__file__).resolve().parent.parent / "data" / "enrichment")

    seen: set[Path] = set()
    unique_candidates: list[Path] = []
    for candidate in candidates:
        resolved = candidate.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_candidates.append(resolved)

    return unique_candidates


def resolve_enrichment_dir() -> Path | None:
    """Find the first directory that contains any enrichment CSVs."""

    for candidate in enrichment_dir_candidates():
        if not candidate.exists():
            continue
        if any((candidate / filename).exists() for filename in ENRICHMENT_FILENAMES):
            return candidate
    return None


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    """Read a CSV into normalized row dictionaries."""

    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            {field: _coerce_row_value(field, value) for field, value in row.items()}
            for row in reader
        ]


def _build_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Index rows by workbook sheet and normalized workbook product name."""

    index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        sheet_name = _clean_text(row.get("sheet_name"))
        product_name = _clean_text(row.get("workbook_product_name"))
        if not sheet_name or not product_name:
            continue
        index[(sheet_name, normalize_identifier(product_name))].append(row)

    return dict(index)


@lru_cache(maxsize=1)
def load_enrichment_dataset() -> dict[str, Any] | None:
    """Load enrichment CSVs and build lookup indexes."""

    enrichment_dir = resolve_enrichment_dir()
    if enrichment_dir is None:
        return None

    source_rows = _read_csv_rows(enrichment_dir / "product_sources.csv")
    ingredient_rows = _read_csv_rows(enrichment_dir / "ingredients_long.csv")

    return {
        "directory": enrichment_dir,
        "source_index": _build_index(source_rows),
        "ingredient_index": _build_index(ingredient_rows),
    }


def _filter_by_form(rows: list[dict[str, Any]], workbook_form: Any) -> list[dict[str, Any]]:
    """Prefer rows whose workbook form matches the selected workbook row."""

    requested_form = canonical_form(_clean_text(workbook_form))
    if not rows or requested_form is None:
        return list(rows)

    exact_matches = [
        row
        for row in rows
        if canonical_form(_clean_text(row.get("workbook_form"))) == requested_form
    ]
    if exact_matches:
        return exact_matches

    formless_matches = [
        row
        for row in rows
        if canonical_form(_clean_text(row.get("workbook_form"))) is None
    ]
    if formless_matches:
        return formless_matches

    return list(rows)


def _dedupe_rows(rows: list[dict[str, Any]], *, fields: tuple[str, ...]) -> list[dict[str, Any]]:
    """Remove duplicate rows while preserving the original order."""

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for row in rows:
        key = tuple(row.get(field) for field in fields)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped


def empty_product_enrichment() -> ProductEnrichment:
    """Return the empty product enrichment payload shape."""

    return {
        "sources": [],
        "ingredients": [],
    }


def build_ingredient_search_text(ingredients: list[dict[str, Any]]) -> str | None:
    """Collapse ingredient rows into a compact, searchable string."""

    values: list[str] = []
    seen: set[str] = set()

    for ingredient in ingredients:
        name = _clean_text(ingredient.get("ingredient_name_raw"))
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        values.append(name)

    if not values:
        return None

    return ", ".join(values)


def lookup_product_enrichment(
    sheet_name: str | None,
    selected_row: dict[str, Any],
) -> tuple[ProductEnrichment, bool]:
    """Return source and ingredient records for a workbook row."""

    dataset = load_enrichment_dataset()
    if dataset is None:
        return empty_product_enrichment(), False

    product_name = _clean_text(selected_row.get("Product Name"))
    if not sheet_name or not product_name:
        return empty_product_enrichment(), True

    lookup_key = (sheet_name, normalize_identifier(product_name))
    workbook_form = selected_row.get("Form")

    sources = _filter_by_form(dataset["source_index"].get(lookup_key, []), workbook_form)
    ingredients = _filter_by_form(dataset["ingredient_index"].get(lookup_key, []), workbook_form)

    group_order = {
        "intentionally_added": 0,
        "fragrance": 1,
        "allergen": 2,
        "nonfunctional": 3,
    }

    sources = _dedupe_rows(
        sources,
        fields=(
            "resolved_url",
            "ingredient_page_url",
            "sds_url",
            "source_product_name",
            "source_family",
            "source_scent",
        ),
    )
    sources.sort(
        key=lambda row: (
            row.get("source_family") or "",
            row.get("source_product_name") or "",
            row.get("source_scent") or "",
        )
    )

    ingredients = _dedupe_rows(
        ingredients,
        fields=(
            "ingredient_group",
            "ingredient_name_raw",
            "cas_number",
            "function",
            "designated_list_text",
        ),
    )
    ingredients.sort(
        key=lambda row: (
            group_order.get(str(row.get("ingredient_group") or ""), 99),
            row.get("position") if isinstance(row.get("position"), int) else 999,
            row.get("ingredient_name_raw") or "",
        )
    )

    return {
        "sources": sources,
        "ingredients": ingredients,
    }, True
