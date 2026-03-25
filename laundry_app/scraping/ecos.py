"""Scraper for ECOS product pages with embedded ingredient disclosure tables."""

from __future__ import annotations

from datetime import datetime, UTC
import re

from laundry_app.scraping.html_utils import clean_text, find_anchor_href, page_text, parse_html_table
from laundry_app.scraping.http import Fetcher
from laundry_app.scraping.models import IngredientRecord, ScrapedProduct, SourceSeed
from laundry_app.scraping.normalize import infer_form, infer_scent


def scrape(seed: SourceSeed, fetcher: Fetcher) -> list[ScrapedProduct]:
    """Scrape a single ECOS product page."""

    page, soup = fetcher.fetch_soup(seed.url)
    page_content = page_text(soup)
    title = clean_text(soup.find("h1").get_text(" ", strip=True)) if soup.find("h1") else seed.url

    product = ScrapedProduct(
        source_family=seed.family,
        source_type=seed.source_type,
        source_url=page.url,
        seed_url=seed.url,
        parser_name=seed.family,
        source_product_name=title,
        brand="ECOS",
        variant=title,
        form=infer_form(title, page.url, page_content),
        scent=infer_scent(title),
        ingredient_page_url=page.url,
        sds_url=find_anchor_href(soup, r"safety data sheets"),
        notes=seed.notes or None,
        raw_sha256=page.raw_sha256,
        extracted_at=datetime.now(UTC).isoformat(),
    )

    size_match = re.search(
        r"Available Sizes:\s*([A-Za-z0-9 .,&+-]+?)\s+Reasons to love",
        page_content,
        re.IGNORECASE,
    )
    if size_match:
        product.size_text = clean_text(size_match.group(1))

    table = soup.find("table")
    if table is not None:
        rows = parse_html_table(table)
        headers = list(rows[0].keys()) if rows else []
        for position, row in enumerate(rows, start=1):
            ingredient_name = row.get(headers[0], "")
            if not ingredient_name:
                continue
            product.ingredients.append(
                IngredientRecord(
                    ingredient_group="intentionally_added",
                    ingredient_name_raw=ingredient_name,
                    cas_number=row.get(headers[1]) or None if len(headers) > 1 else None,
                    function=row.get(headers[2]) or None if len(headers) > 2 else None,
                    designated_list_flag=row.get(headers[4]) or None if len(headers) > 4 else None,
                    designated_list_text=row.get(headers[5]) or None if len(headers) > 5 else None,
                    position=position,
                    source_url=page.url,
                )
            )

    return [product]
