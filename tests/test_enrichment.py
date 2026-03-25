"""Regression tests for enrichment lookup and modal rendering."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from laundry_app.callbacks import build_product_detail_body
from laundry_app.data import build_sheet_payload
from laundry_app.enrichment import load_enrichment_dataset, lookup_product_enrichment


def collect_text(node: object) -> list[str]:
    """Collect nested string children from Dash component trees."""

    if node is None:
        return []
    if isinstance(node, str):
        return [node]
    if isinstance(node, (list, tuple)):
        values: list[str] = []
        for item in node:
            values.extend(collect_text(item))
        return values

    children = getattr(node, "children", None)
    if children is None:
        return []
    return collect_text(children)


class EnrichmentLookupTests(unittest.TestCase):
    """Coverage for enrichment CSV loading and UI rendering."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        os.environ["LAUNDRY_ENRICHMENT_DIR"] = self.temp_dir.name
        self.addCleanup(os.environ.pop, "LAUNDRY_ENRICHMENT_DIR", None)
        load_enrichment_dataset.cache_clear()

    def tearDown(self) -> None:
        load_enrichment_dataset.cache_clear()

    def write_csv(self, filename: str, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
        path = Path(self.temp_dir.name) / filename
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_lookup_product_enrichment_prefers_matching_form(self) -> None:
        self.write_csv(
            "product_sources.csv",
            [
                "sheet_name",
                "workbook_product_name",
                "workbook_form",
                "source_family",
                "source_type",
                "source_product_name",
                "resolved_url",
                "ingredient_page_url",
                "sds_url",
            ],
            [
                {
                    "sheet_name": "Detergents - North America",
                    "workbook_product_name": "Tide Clean & Gentle",
                    "workbook_form": "powder",
                    "source_family": "tide",
                    "source_type": "product_page",
                    "source_product_name": "Tide Clean & Gentle Powder",
                    "resolved_url": "https://example.com/powder",
                    "ingredient_page_url": "https://example.com/powder/ingredients",
                    "sds_url": "",
                },
                {
                    "sheet_name": "Detergents - North America",
                    "workbook_product_name": "Tide Clean & Gentle",
                    "workbook_form": "liquid",
                    "source_family": "tide",
                    "source_type": "product_page",
                    "source_product_name": "Tide Clean & Gentle Liquid",
                    "resolved_url": "https://example.com/liquid",
                    "ingredient_page_url": "https://example.com/liquid/ingredients",
                    "sds_url": "",
                },
            ],
        )
        self.write_csv(
            "ingredients_long.csv",
            [
                "sheet_name",
                "workbook_product_name",
                "workbook_form",
                "ingredient_group",
                "ingredient_name_raw",
                "cas_number",
                "function",
                "position",
                "designated_list_text",
            ],
            [
                {
                    "sheet_name": "Detergents - North America",
                    "workbook_product_name": "Tide Clean & Gentle",
                    "workbook_form": "powder",
                    "ingredient_group": "intentionally_added",
                    "ingredient_name_raw": "Sodium carbonate",
                    "cas_number": "497-19-8",
                    "function": "Builder",
                    "position": "1",
                    "designated_list_text": "",
                },
                {
                    "sheet_name": "Detergents - North America",
                    "workbook_product_name": "Tide Clean & Gentle",
                    "workbook_form": "liquid",
                    "ingredient_group": "intentionally_added",
                    "ingredient_name_raw": "Water",
                    "cas_number": "7732-18-5",
                    "function": "Solvent",
                    "position": "1",
                    "designated_list_text": "",
                },
            ],
        )
        enrichment, is_loaded = lookup_product_enrichment(
            "Detergents - North America",
            {
                "Product Name": "Tide Clean & Gentle",
                "Form": "powder",
            },
        )

        self.assertTrue(is_loaded)
        self.assertEqual(len(enrichment["sources"]), 1)
        self.assertEqual(enrichment["sources"][0]["source_product_name"], "Tide Clean & Gentle Powder")
        self.assertEqual(len(enrichment["ingredients"]), 1)
        self.assertEqual(enrichment["ingredients"][0]["ingredient_name_raw"], "Sodium carbonate")

    def test_build_sheet_payload_adds_filterable_ingredient_column(self) -> None:
        self.write_csv(
            "product_sources.csv",
            [
                "sheet_name",
                "workbook_product_name",
                "workbook_form",
                "source_family",
                "source_type",
                "source_product_name",
                "resolved_url",
                "ingredient_page_url",
                "sds_url",
            ],
            [
                {
                    "sheet_name": "Detergents - North America",
                    "workbook_product_name": "ECOS Laundry Detergent With Enzymes",
                    "workbook_form": "liquid",
                    "source_family": "ecos",
                    "source_type": "product_page",
                    "source_product_name": "ECOS Free & Clear",
                    "resolved_url": "https://example.com/ecos",
                    "ingredient_page_url": "https://example.com/ecos",
                    "sds_url": "",
                }
            ],
        )
        self.write_csv(
            "ingredients_long.csv",
            [
                "sheet_name",
                "workbook_product_name",
                "workbook_form",
                "ingredient_group",
                "ingredient_name_raw",
                "cas_number",
                "function",
                "position",
                "designated_list_text",
            ],
            [
                {
                    "sheet_name": "Detergents - North America",
                    "workbook_product_name": "ECOS Laundry Detergent With Enzymes",
                    "workbook_form": "liquid",
                    "ingredient_group": "intentionally_added",
                    "ingredient_name_raw": "Water",
                    "cas_number": "7732-18-5",
                    "function": "Solvent",
                    "position": "1",
                    "designated_list_text": "",
                },
                {
                    "sheet_name": "Detergents - North America",
                    "workbook_product_name": "ECOS Laundry Detergent With Enzymes",
                    "workbook_form": "liquid",
                    "ingredient_group": "intentionally_added",
                    "ingredient_name_raw": "Cocamidopropylamine Oxide",
                    "cas_number": "68155-09-9",
                    "function": "Surfactant",
                    "position": "2",
                    "designated_list_text": "",
                },
            ],
        )
        payload = build_sheet_payload(
            "Detergents - North America",
            pd.DataFrame(
                [
                    {
                        "Product Name": "ECOS Laundry Detergent With Enzymes",
                        "Form": "liquid",
                    }
                ]
            ),
            {},
        )

        self.assertIn("Ingredients", payload["rowData"][0])
        self.assertIn("Water", payload["rowData"][0]["Ingredients"])
        self.assertIn("Cocamidopropylamine Oxide", payload["rowData"][0]["Ingredients"])
        ingredient_column = next(
            column for column in payload["columnDefs"] if column["field"] == "Ingredients"
        )
        self.assertEqual(ingredient_column["filter"], "agTextColumnFilter")

    def test_build_product_detail_body_renders_enrichment_sections(self) -> None:
        body = build_product_detail_body(
            {
                "Product Name": "ECOS Laundry Detergent With Enzymes",
                "Form": "liquid",
                "Fragrance-Free?": True,
            },
            {
                "sources": [
                    {
                        "source_family": "ecos",
                        "source_type": "product_page",
                        "source_product_name": "Laundry Detergent Ultra-Concentrated Free & Clear",
                        "resolved_url": "https://example.com/source",
                        "ingredient_page_url": "https://example.com/source",
                        "sds_url": "https://example.com/sds",
                        "source_form": "liquid",
                        "source_scent": "Free & Clear",
                        "source_brand": "ECOS",
                        "variant": "Ultra-Concentrated",
                        "size_text": "16 fl oz",
                        "load_count_text": "32 loads",
                        "disclosure_date": "2024-03-26",
                        "sds_revision_date": None,
                        "notes": None,
                    }
                ],
                "ingredients": [
                    {
                        "ingredient_group": "intentionally_added",
                        "ingredient_name_raw": "Water",
                        "function": "Solvent",
                        "cas_number": "7732-18-5",
                        "designated_list_text": None,
                    }
                ],
            },
            enrichment_loaded=True,
        )

        text = " ".join(collect_text(body))
        self.assertIn("Official Sources", text)
        self.assertIn("Ingredients", text)
        self.assertIn("CAS 7732-18-5", text)


if __name__ == "__main__":
    unittest.main()
