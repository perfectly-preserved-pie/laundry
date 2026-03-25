"""End-to-end scrape runner, CSV export, and CLI entrypoint."""

from __future__ import annotations

import argparse
from datetime import datetime, UTC
import json
from pathlib import Path
from typing import Any

import pandas as pd

from laundry_app.scraping.http import Fetcher
from laundry_app.scraping.matching import load_workbook_rows, match_products
from laundry_app.scraping.models import MatchedProduct, ScrapeErrorRecord, ScrapedProduct
from laundry_app.scraping.registry import PRODUCT_ALIASES, SCRAPER_REGISTRY, SOURCE_SEEDS


PRODUCT_SOURCE_COLUMNS = [
    "sheet_name",
    "workbook_product_name",
    "workbook_form",
    "source_family",
    "source_type",
    "source_product_name",
    "source_form",
    "source_scent",
    "source_brand",
    "variant",
    "size_text",
    "load_count_text",
    "seed_url",
    "resolved_url",
    "ingredient_page_url",
    "sds_url",
    "disclosure_date",
    "sds_revision_date",
    "match_score",
    "match_type",
    "parser_name",
    "raw_sha256",
    "notes",
    "extra_json",
    "extracted_at",
]

INGREDIENT_COLUMNS = [
    "sheet_name",
    "workbook_product_name",
    "workbook_form",
    "source_family",
    "source_product_name",
    "source_url",
    "ingredient_group",
    "ingredient_name_raw",
    "cas_number",
    "function",
    "designated_list_flag",
    "designated_list_text",
    "position",
    "notes",
]

ERROR_COLUMNS = ["family", "seed_url", "error_type", "message"]


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> Path:
    frame = pd.DataFrame(rows, columns=columns)
    frame.to_csv(path, index=False)
    return path


def _product_source_row(match: MatchedProduct) -> dict[str, Any]:
    workbook_row = match.workbook_row
    product = match.product
    return {
        "sheet_name": workbook_row.sheet_name if workbook_row else None,
        "workbook_product_name": workbook_row.product_name if workbook_row else None,
        "workbook_form": workbook_row.form if workbook_row else None,
        "source_family": product.source_family,
        "source_type": product.source_type,
        "source_product_name": product.source_product_name,
        "source_form": product.form,
        "source_scent": product.scent,
        "source_brand": product.brand,
        "variant": product.variant,
        "size_text": product.size_text,
        "load_count_text": product.load_count_text,
        "seed_url": product.seed_url,
        "resolved_url": product.source_url,
        "ingredient_page_url": product.ingredient_page_url,
        "sds_url": product.sds_url,
        "disclosure_date": product.disclosure_date,
        "sds_revision_date": product.sds_revision_date,
        "match_score": match.match_score,
        "match_type": match.match_type,
        "parser_name": product.parser_name,
        "raw_sha256": product.raw_sha256,
        "notes": product.notes,
        "extra_json": json.dumps(product.extra, sort_keys=True),
        "extracted_at": product.extracted_at,
    }


def _ingredient_rows(matches: list[MatchedProduct]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in matches:
        workbook_row = match.workbook_row
        for ingredient in match.product.ingredients:
            rows.append(
                {
                    "sheet_name": workbook_row.sheet_name if workbook_row else None,
                    "workbook_product_name": workbook_row.product_name if workbook_row else None,
                    "workbook_form": workbook_row.form if workbook_row else None,
                    "source_family": match.product.source_family,
                    "source_product_name": match.product.source_product_name,
                    "source_url": ingredient.source_url or match.product.source_url,
                    "ingredient_group": ingredient.ingredient_group,
                    "ingredient_name_raw": ingredient.ingredient_name_raw,
                    "cas_number": ingredient.cas_number,
                    "function": ingredient.function,
                    "designated_list_flag": ingredient.designated_list_flag,
                    "designated_list_text": ingredient.designated_list_text,
                    "position": ingredient.position,
                    "notes": ingredient.notes,
                }
            )
    return rows


def _error_rows(errors: list[ScrapeErrorRecord]) -> list[dict[str, Any]]:
    return [
        {
            "family": error.family,
            "seed_url": error.seed_url,
            "error_type": error.error_type,
            "message": error.message,
        }
        for error in errors
    ]


def run_pipeline(
    *,
    families: set[str] | None = None,
    output_dir: Path | None = None,
    use_playwright: bool = False,
) -> dict[str, Path]:
    """Run the scrape pipeline and write CSV outputs."""

    output_path = output_dir or Path("data/enrichment")
    output_path.mkdir(parents=True, exist_ok=True)

    scraped_products: list[ScrapedProduct] = []
    errors: list[ScrapeErrorRecord] = []

    with Fetcher(enable_browser=use_playwright) as fetcher:
        for seed in SOURCE_SEEDS:
            if families and seed.family not in families:
                continue

            scraper = SCRAPER_REGISTRY[seed.family]
            try:
                products = scraper(seed, fetcher)
            except Exception as exc:  # noqa: BLE001 - keep pipeline resilient
                errors.append(
                    ScrapeErrorRecord(
                        family=seed.family,
                        seed_url=seed.url,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                continue

            for product in products:
                product.extra.setdefault("seed_target_products", list(seed.target_products))
                scraped_products.append(product)

    workbook_rows = load_workbook_rows()
    matches = match_products(scraped_products, workbook_rows, PRODUCT_ALIASES)

    product_rows = [_product_source_row(match) for match in matches]
    ingredient_rows = _ingredient_rows(matches)
    unmatched_rows = [row for row in product_rows if row["workbook_product_name"] is None]

    written_paths = {
        "product_sources": _write_csv(output_path / "product_sources.csv", product_rows, PRODUCT_SOURCE_COLUMNS),
        "ingredients_long": _write_csv(output_path / "ingredients_long.csv", ingredient_rows, INGREDIENT_COLUMNS),
        "unmatched_products": _write_csv(output_path / "unmatched_products.csv", unmatched_rows, PRODUCT_SOURCE_COLUMNS),
        "scrape_errors": _write_csv(output_path / "scrape_errors.csv", _error_rows(errors), ERROR_COLUMNS),
    }

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "families": sorted(families) if families else sorted({seed.family for seed in SOURCE_SEEDS}),
        "product_sources": len(product_rows),
        "ingredients_long": len(ingredient_rows),
        "unmatched_products": len(unmatched_rows),
        "scrape_errors": len(errors),
    }
    summary_path = output_path / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    written_paths["summary"] = summary_path

    return written_paths


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(description="Scrape official laundry disclosure pages into sidecar CSV tables.")
    parser.add_argument(
        "--family",
        action="append",
        choices=sorted(SCRAPER_REGISTRY),
        help="Restrict scraping to one or more source families.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/enrichment",
        help="Directory where CSV outputs should be written.",
    )
    parser.add_argument(
        "--list-families",
        action="store_true",
        help="Print the available source families and exit.",
    )
    parser.add_argument(
        "--use-playwright",
        action="store_true",
        help="Use Playwright for JS-heavy sources such as Tide SmartLabel and Dropps disclosure pages.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.list_families:
        for family in sorted(SCRAPER_REGISTRY):
            print(family)
        return 0

    families = set(args.family) if args.family else None
    written = run_pipeline(
        families=families,
        output_dir=Path(args.output_dir),
        use_playwright=args.use_playwright,
    )
    for label, path in written.items():
        print(f"{label}: {path}")
    return 0
