"""Shared dataclasses for scrape seeds, results, and workbook matching."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SourceSeed:
    """A single seed URL to scrape."""

    family: str
    url: str
    source_type: str
    notes: str = ""
    target_products: tuple[str, ...] = ()


@dataclass(slots=True)
class IngredientRecord:
    """A single ingredient entry extracted from a source page."""

    ingredient_group: str
    ingredient_name_raw: str
    cas_number: str | None = None
    function: str | None = None
    designated_list_flag: str | None = None
    designated_list_text: str | None = None
    position: int = 0
    notes: str | None = None
    source_url: str | None = None


@dataclass(slots=True)
class ScrapedProduct:
    """A normalized product payload plus its extracted ingredients."""

    source_family: str
    source_type: str
    source_url: str
    seed_url: str
    parser_name: str
    source_product_name: str
    brand: str | None = None
    variant: str | None = None
    form: str | None = None
    scent: str | None = None
    size_text: str | None = None
    load_count_text: str | None = None
    ingredient_page_url: str | None = None
    sds_url: str | None = None
    disclosure_date: str | None = None
    sds_revision_date: str | None = None
    notes: str | None = None
    raw_sha256: str | None = None
    extracted_at: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    ingredients: list[IngredientRecord] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class WorkbookRow:
    """A workbook product row that a scraped source may match to."""

    sheet_name: str
    product_name: str
    form: str | None = None


@dataclass(slots=True)
class MatchedProduct:
    """A scraped product plus its workbook match metadata."""

    product: ScrapedProduct
    workbook_row: WorkbookRow | None
    match_score: float
    match_type: str


@dataclass(slots=True)
class ScrapeErrorRecord:
    """A non-fatal scrape error captured for reporting."""

    family: str
    seed_url: str
    error_type: str
    message: str
