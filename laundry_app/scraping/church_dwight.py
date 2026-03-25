"""Scraper for Church & Dwight ingredient disclosure pages."""

from __future__ import annotations

from datetime import datetime, UTC
import re

from laundry_app.scraping.html_utils import clean_text, extract_between_labels, page_text, parse_html_table
from laundry_app.scraping.http import Fetcher
from laundry_app.scraping.models import IngredientRecord, ScrapedProduct, SourceSeed
from laundry_app.scraping.normalize import infer_form, infer_scent


DISCLOSURE_DATE_RE = re.compile(r"DATE OF DISCLOSURE:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})")


def _ingredient_group_from_headers(headers: list[str]) -> str:
    heading = " ".join(headers).casefold()
    if "fragrance components" in heading:
        return "fragrance"
    return "intentionally_added"


def scrape(seed: SourceSeed, fetcher: Fetcher) -> list[ScrapedProduct]:
    """Scrape a single Church & Dwight disclosure page."""

    page, soup = fetcher.fetch_soup(seed.url)
    text = page_text(soup)

    product_name = extract_between_labels(text, "PRODUCT NAME:", "CATEGORY:") or extract_between_labels(
        text, "PRODUCT NAME:", "MATERIAL NUMBER:"
    )
    category = extract_between_labels(text, "CATEGORY:", "MATERIAL NUMBER:")
    material_number = extract_between_labels(text, "MATERIAL NUMBER:", "INGREDIENTS:")

    disclosure_match = DISCLOSURE_DATE_RE.search(text)
    disclosure_date = clean_text(disclosure_match.group(1)) if disclosure_match else None
    sds_anchor = soup.find("a", string=re.compile("SDS is available here", re.IGNORECASE))
    sds_url = sds_anchor["href"] if sds_anchor and sds_anchor.has_attr("href") else None

    product = ScrapedProduct(
        source_family=seed.family,
        source_type=seed.source_type,
        source_url=page.url,
        seed_url=seed.url,
        parser_name=seed.family,
        source_product_name=product_name or seed.url.rsplit("/", 1)[-1],
        brand="OxiClean" if product_name and "oxiclean" in product_name.casefold() else "Church & Dwight",
        variant=product_name,
        form=infer_form(product_name, page.url),
        scent=infer_scent(product_name),
        ingredient_page_url=page.url,
        sds_url=sds_url,
        disclosure_date=disclosure_date,
        notes=seed.notes or None,
        raw_sha256=page.raw_sha256,
        extracted_at=datetime.now(UTC).isoformat(),
        extra={
            "category": category,
            "material_number": material_number,
        },
    )

    tables = soup.find_all("table")
    for table in tables:
        rows = parse_html_table(table)
        if not rows:
            continue
        headers = list(rows[0].keys())
        if "CAS #" not in headers and not any("CAS" in header for header in headers):
            continue
        ingredient_group = _ingredient_group_from_headers(headers)
        for position, row in enumerate(rows, start=1):
            ingredient_name = row.get(headers[0], "")
            if not ingredient_name:
                continue
            if ingredient_group == "intentionally_added":
                product.ingredients.append(
                    IngredientRecord(
                        ingredient_group=ingredient_group,
                        ingredient_name_raw=ingredient_name,
                        cas_number=row.get(headers[1]) or None,
                        function=row.get(headers[2]) or None,
                        designated_list_flag="Yes" if row.get(headers[3]) and row.get(headers[3]) != "No" else row.get(headers[3]) or None,
                        designated_list_text=row.get(headers[3]) or None,
                        position=position,
                        source_url=page.url,
                    )
                )
            else:
                designated_text = row.get(headers[2]) or None
                product.ingredients.append(
                    IngredientRecord(
                        ingredient_group=ingredient_group,
                        ingredient_name_raw=ingredient_name,
                        cas_number=row.get(headers[1]) or None,
                        designated_list_flag="Yes" if designated_text and designated_text != "No" else designated_text or None,
                        designated_list_text=designated_text,
                        position=position,
                        source_url=page.url,
                    )
                )

    return [product]
