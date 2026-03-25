"""Workbook loading and scraped-product matching helpers."""

from __future__ import annotations

from io import BytesIO
from typing import Iterable

import pandas as pd

from laundry_app.data import load_workbook_bytes, prepare_sheet_frame
from laundry_app.scraping.models import MatchedProduct, ScrapedProduct, WorkbookRow
from laundry_app.scraping.normalize import canonical_form, compare_names


def load_workbook_rows() -> list[WorkbookRow]:
    """Load workbook product rows for scrape matching."""

    workbook = pd.read_excel(
        BytesIO(load_workbook_bytes()),
        sheet_name=None,
        header=None,
        keep_default_na=False,
    )
    rows: list[WorkbookRow] = []

    for sheet_name, raw_sheet in workbook.items():
        if sheet_name == "Key":
            continue
        frame = prepare_sheet_frame(raw_sheet)
        for record in frame.to_dict("records"):
            rows.append(
                WorkbookRow(
                    sheet_name=sheet_name,
                    product_name=str(record.get("Product Name") or ""),
                    form=canonical_form(record.get("Form")),
                )
            )

    return rows


def _candidate_rows(
    product: ScrapedProduct,
    workbook_rows: Iterable[WorkbookRow],
    aliases: dict[str, dict[str, tuple[str, ...]]],
) -> list[WorkbookRow]:
    family_aliases = aliases.get(product.source_family, {})
    seed_targets = {value for value in product.extra.get("seed_target_products", []) if value}
    if seed_targets:
        candidates = [row for row in workbook_rows if row.product_name in seed_targets]
        if candidates:
            return candidates
    family_products = set(family_aliases)
    if family_products:
        candidates = [row for row in workbook_rows if row.product_name in family_products]
        if candidates:
            return candidates
    return list(workbook_rows)


def _name_score(product: ScrapedProduct, row: WorkbookRow, aliases: dict[str, dict[str, tuple[str, ...]]]) -> tuple[float, str]:
    family_aliases = aliases.get(product.source_family, {})
    candidate_names = [row.product_name, *family_aliases.get(row.product_name, ())]
    best_score = 0.0
    best_type = "none"

    for candidate_name in candidate_names:
        score = compare_names(product.source_product_name, candidate_name)
        match_type = "alias" if candidate_name != row.product_name else "exact"
        if score > best_score:
            best_score = score
            best_type = match_type if score >= 0.92 else "fuzzy"

    return best_score, best_type


def _form_adjustment(product: ScrapedProduct, row: WorkbookRow) -> float:
    source_form = canonical_form(product.form)
    workbook_form = canonical_form(row.form)
    if source_form and workbook_form:
        return 0.08 if source_form == workbook_form else -0.18
    return 0.0


def match_products(
    scraped_products: list[ScrapedProduct],
    workbook_rows: list[WorkbookRow],
    aliases: dict[str, dict[str, tuple[str, ...]]],
    *,
    threshold: float = 0.72,
) -> list[MatchedProduct]:
    """Match scraped products back to workbook rows."""

    matches: list[MatchedProduct] = []

    for product in scraped_products:
        candidates = _candidate_rows(product, workbook_rows, aliases)
        best_row: WorkbookRow | None = None
        best_score = 0.0
        best_type = "none"

        for row in candidates:
            score, match_type = _name_score(product, row, aliases)
            score += _form_adjustment(product, row)
            if score > best_score:
                best_row = row
                best_score = min(max(score, 0.0), 1.0)
                best_type = match_type

        if best_score < threshold:
            best_row = None
            best_type = "none"

        matches.append(
            MatchedProduct(
                product=product,
                workbook_row=best_row,
                match_score=round(best_score, 4),
                match_type=best_type,
            )
        )

    return matches
