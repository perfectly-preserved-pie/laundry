"""Scraper for Sprouts California Cleaning Product Right to Know pages."""

from __future__ import annotations

from datetime import datetime, UTC
import re

from bs4 import Tag

from laundry_app.scraping.html_utils import clean_text, parse_html_table
from laundry_app.scraping.http import Fetcher
from laundry_app.scraping.models import IngredientRecord, ScrapedProduct, SourceSeed
from laundry_app.scraping.normalize import infer_form, infer_scent


HEADING_PREFIX_RE = re.compile(r"^\d{5}-\d{5}\s+")
LAUNDRY_KEYWORDS = ("laundry", "oxygen brightener")


def _strip_code(title: str) -> tuple[str, str | None]:
    """Split the Sprouts product code from the title."""

    match = HEADING_PREFIX_RE.match(title)
    if not match:
        return title, None
    return clean_text(title[match.end() :]), clean_text(title[: match.end()].strip())


def scrape(seed: SourceSeed, fetcher: Fetcher) -> list[ScrapedProduct]:
    """Scrape the Sprouts disclosure hub page."""

    page, soup = fetcher.fetch_soup(seed.url)
    products: list[ScrapedProduct] = []

    for heading in soup.find_all("h4"):
        raw_title = clean_text(heading.get_text(" ", strip=True))
        if not raw_title or "Sprouts" not in raw_title:
            continue

        title, product_code = _strip_code(raw_title)
        if not any(keyword in title.casefold() for keyword in LAUNDRY_KEYWORDS):
            continue
        product = ScrapedProduct(
            source_family=seed.family,
            source_type=seed.source_type,
            source_url=page.url,
            seed_url=seed.url,
            parser_name=seed.family,
            source_product_name=title,
            brand="Sprouts Farmers Market",
            variant=title,
            form=infer_form(title),
            scent=infer_scent(title),
            ingredient_page_url=page.url,
            notes=seed.notes or None,
            raw_sha256=page.raw_sha256,
            extracted_at=datetime.now(UTC).isoformat(),
            extra={"product_code": product_code},
        )

        position = 1
        node = heading
        while True:
            node = node.find_next_sibling()
            if node is None:
                break
            if isinstance(node, Tag) and node.name == "h4":
                break
            if not isinstance(node, Tag):
                continue

            if node.name == "table":
                rows = parse_html_table(node)
                if not rows:
                    continue
                headers = list(rows[0].keys())
                first_header = next(iter(headers), "")
                group = "fragrance" if "fragrance" in first_header.casefold() else "intentionally_added"
                for row in rows:
                    ingredient_name = row.get(headers[0], "")
                    if not ingredient_name:
                        continue
                    product.ingredients.append(
                        IngredientRecord(
                            ingredient_group=group,
                            ingredient_name_raw=ingredient_name,
                            cas_number=row.get(headers[1]) or None if len(headers) > 1 else None,
                            function=row.get(headers[2]) or None if len(headers) > 2 else None,
                            designated_list_flag="Yes" if len(headers) > 3 and row.get(headers[3]) else None,
                            designated_list_text=row.get(headers[3]) or None if len(headers) > 3 else None,
                            position=position,
                            source_url=page.url,
                        )
                    )
                    position += 1

            for anchor in node.find_all("a", href=True):
                anchor_text = clean_text(anchor.get_text(" ", strip=True))
                if "sds" in anchor_text.casefold() or "safety data sheet" in anchor_text.casefold():
                    product.sds_url = anchor["href"]

        products.append(product)

    return products
