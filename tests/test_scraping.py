"""Lightweight regression tests for scrape normalization and matching."""

from __future__ import annotations

import unittest

from laundry_app.scraping.html_utils import parse_html_table
from laundry_app.scraping.matching import match_products
from laundry_app.scraping.models import ScrapedProduct, WorkbookRow
from laundry_app.scraping.normalize import compare_names, infer_form, normalize_identifier


class NormalizeTests(unittest.TestCase):
    """Normalization helper coverage."""

    def test_normalize_identifier_folds_symbols(self) -> None:
        self.assertEqual(normalize_identifier("Dropps Odor+Stain"), "dropps odor plus stain")

    def test_compare_names_handles_trademarks(self) -> None:
        score = compare_names(
            "OxiClean™ White Revive™ Whitener and Stain Remover",
            "OxiClean White Revive",
        )
        self.assertGreater(score, 0.85)

    def test_infer_form_detects_powder(self) -> None:
        self.assertEqual(infer_form("Tide Original Powder Laundry Detergent"), "powder")


class HtmlParsingTests(unittest.TestCase):
    """Table parsing coverage."""

    def test_parse_html_table_preserves_multiline_cells(self) -> None:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(
            """
            <table>
              <tr><th>Ingredient</th><th>CAS</th></tr>
              <tr><td>Alpha<br/>Amylase</td><td>9000-90-2</td></tr>
            </table>
            """,
            "html.parser",
        )
        rows = parse_html_table(soup.find("table"))
        self.assertEqual(rows[0]["Ingredient"], "Alpha | Amylase")
        self.assertEqual(rows[0]["CAS"], "9000-90-2")


class MatchingTests(unittest.TestCase):
    """Workbook matching coverage."""

    def test_match_products_uses_alias_and_form(self) -> None:
        product = ScrapedProduct(
            source_family="tide",
            source_type="product_page",
            source_url="https://example.com/tide-free-and-gentle",
            seed_url="https://example.com/tide-free-and-gentle",
            parser_name="tide",
            source_product_name="Tide Free and Gentle Liquid Laundry Detergent",
            form="liquid",
        )
        product.extra["seed_target_products"] = ["Tide Clean & Gentle"]
        workbook_rows = [
            WorkbookRow(
                sheet_name="Detergents - North America",
                product_name="Tide Clean & Gentle",
                form="liquid",
            )
        ]
        aliases = {
            "tide": {
                "Tide Clean & Gentle": ("Tide Free and Gentle Liquid Laundry Detergent",),
            }
        }

        matches = match_products([product], workbook_rows, aliases)
        self.assertEqual(matches[0].workbook_row, workbook_rows[0])
        self.assertEqual(matches[0].match_type, "alias")
        self.assertGreaterEqual(matches[0].match_score, 0.9)


if __name__ == "__main__":
    unittest.main()
