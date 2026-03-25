"""Scraper for Whole Foods Market California disclosure pages."""

from __future__ import annotations

from datetime import datetime, UTC
import re

from bs4 import Tag

from laundry_app.scraping.html_utils import clean_text, parse_html_table
from laundry_app.scraping.http import Fetcher
from laundry_app.scraping.models import IngredientRecord, ScrapedProduct, SourceSeed
from laundry_app.scraping.normalize import infer_form, infer_scent, normalize_identifier


STOP_HEADINGS = {
    "Links to California Cleaning Product Right to Know Act Designated Lists",
    "Shopping",
    "Mission in Action",
    "About",
    "Need Help?",
    "Connect With Us",
}
DATE_RE = re.compile(r"Date of data entry:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", re.IGNORECASE)


def _is_brand_heading(text: str) -> bool:
    normalized = normalize_identifier(text)
    return "whole foods market" in normalized


def _is_stop_heading(text: str) -> bool:
    normalized = normalize_identifier(text)
    return normalized in {normalize_identifier(value) for value in STOP_HEADINGS}


def _parse_block(
    *,
    brand: str,
    title: str,
    nodes: list[Tag],
    page_url: str,
    page_hash: str,
    seed: SourceSeed,
) -> ScrapedProduct:
    block_text = clean_text(" ".join(node.get_text(" ", strip=True) for node in nodes))
    sds_url = None
    for node in nodes:
        for anchor in node.find_all("a", href=True):
            anchor_text = clean_text(anchor.get_text(" ", strip=True))
            if "safety data sheet" in anchor_text.casefold():
                sds_url = anchor["href"]
                break
        if sds_url:
            break

    date_match = DATE_RE.search(block_text)
    disclosure_date = clean_text(date_match.group(1)) if date_match else None

    source_product_name = f"{brand} {title}"
    product = ScrapedProduct(
        source_family=seed.family,
        source_type=seed.source_type,
        source_url=page_url,
        seed_url=seed.url,
        parser_name=seed.family,
        source_product_name=source_product_name,
        brand=brand,
        variant=title,
        form=infer_form(title, source_product_name, page_url),
        scent=infer_scent(title),
        ingredient_page_url=page_url,
        sds_url=sds_url,
        disclosure_date=disclosure_date,
        notes=seed.notes or None,
        raw_sha256=page_hash,
        extracted_at=datetime.now(UTC).isoformat(),
    )

    position = 1
    for node in nodes:
        if node.name != "table":
            continue
        rows = parse_html_table(node)
        if not rows:
            continue
        first_header = next(iter(rows[0].keys()), "")
        ingredient_group = "fragrance" if "fragrance" in first_header.casefold() else "intentionally_added"
        headers = list(rows[0].keys())
        for row in rows:
            ingredient_name = row.get(headers[0], "")
            if not ingredient_name:
                continue
            ingredient = IngredientRecord(
                ingredient_group=ingredient_group,
                ingredient_name_raw=ingredient_name,
                cas_number=row.get(headers[1]) or None if len(headers) > 1 else None,
                function=row.get(headers[2]) or None if len(headers) > 2 else None,
                position=position,
                source_url=page_url,
            )
            product.ingredients.append(ingredient)
            position += 1

    return product


def scrape(seed: SourceSeed, fetcher: Fetcher) -> list[ScrapedProduct]:
    """Scrape a Whole Foods multi-product disclosure page."""

    page, soup = fetcher.fetch_soup(seed.url)
    nodes = list(soup.find_all(["h3", "table", "a", "p"]))
    products: list[ScrapedProduct] = []
    index = 0

    while index < len(nodes) - 1:
        current = nodes[index]
        if current.name != "h3":
            index += 1
            continue

        brand = clean_text(current.get_text(" ", strip=True))
        if _is_stop_heading(brand):
            break
        if not _is_brand_heading(brand):
            index += 1
            continue

        next_node = nodes[index + 1]
        if next_node.name != "h3":
            index += 1
            continue

        title = clean_text(next_node.get_text(" ", strip=True))
        if _is_brand_heading(title) or _is_stop_heading(title):
            index += 1
            continue

        index += 2
        block: list[Tag] = []
        while index < len(nodes):
            node = nodes[index]
            if node.name == "h3":
                text = clean_text(node.get_text(" ", strip=True))
                if _is_brand_heading(text) or _is_stop_heading(text):
                    break
            block.append(node)
            index += 1

        products.append(
            _parse_block(
                brand=brand,
                title=title,
                nodes=block,
                page_url=page.url,
                page_hash=page.raw_sha256,
                seed=seed,
            )
        )

    return products
