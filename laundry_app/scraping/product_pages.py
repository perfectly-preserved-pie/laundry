"""Scrapers for official product pages that surface SmartLabel or similar links."""

from __future__ import annotations

from datetime import datetime, UTC
import re

from bs4 import BeautifulSoup

from laundry_app.scraping.html_utils import clean_text, find_anchor_href, page_text, parse_html_table
from laundry_app.scraping.http import Fetcher
from laundry_app.scraping.models import IngredientRecord, ScrapedProduct, SourceSeed
from laundry_app.scraping.normalize import infer_form, infer_scent, normalize_identifier


SIZE_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:fl oz|oz|ounces|ounce)\b", re.IGNORECASE)


def _find_smartlabel_url(soup: BeautifulSoup) -> str | None:
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "smartlabel" in href.casefold() or "labelinsight" in href.casefold():
            return href
    return None


def _parse_labelinsight_page(url: str, fetcher: Fetcher) -> tuple[str, list[IngredientRecord], str | None]:
    """Parse a labelinsight-backed SmartLabel page."""

    page, soup = fetcher.fetch_soup(url)
    container = soup.find("div", class_=re.compile("IngredientList__Container"))
    ingredient_links = container.select('a[href*="/ingredients/"]') if container else []
    ingredients: list[IngredientRecord] = []
    for position, anchor in enumerate(ingredient_links, start=1):
        name = clean_text(anchor.get_text(" ", strip=True)).removesuffix(" DL").strip()
        if not name:
            continue
        ingredients.append(
            IngredientRecord(
                ingredient_group="intentionally_added",
                ingredient_name_raw=name,
                position=position,
                source_url=page.url,
            )
        )

    sds_url = None
    for anchor in soup.find_all("a", href=True):
        if "safety data sheet" in clean_text(anchor.get_text(" ", strip=True)).casefold():
            sds_url = anchor["href"]
            break

    title = clean_text(soup.find("h1").get_text(" ", strip=True)) if soup.find("h1") else clean_text(soup.title.get_text(" ", strip=True))
    return title, ingredients, sds_url


def _extract_table_ingredients(soup: BeautifulSoup, source_url: str) -> list[IngredientRecord]:
    """Extract ingredient rows from rendered tables when available."""

    ingredients: list[IngredientRecord] = []

    for table in soup.find_all("table"):
        rows = parse_html_table(table)
        if not rows:
            continue

        headers = {normalize_identifier(header): header for header in rows[0]}
        ingredient_header = next(
            (
                header
                for normalized, header in headers.items()
                if normalized in {"ingredient", "ingredients", "ingredient name"}
                or normalized.startswith("ingredient ")
            ),
            None,
        )
        if ingredient_header is None:
            continue

        cas_header = next((header for normalized, header in headers.items() if normalized.startswith("cas")), None)
        function_header = next(
            (
                header
                for normalized, header in headers.items()
                if any(token in normalized for token in ("function", "purpose", "role"))
            ),
            None,
        )
        designated_header = next(
            (
                header
                for normalized, header in headers.items()
                if "designated" in normalized or normalized.startswith("list ")
            ),
            None,
        )

        table_ingredients: list[IngredientRecord] = []
        for position, row in enumerate(rows, start=1):
            ingredient_name = clean_text(row.get(ingredient_header))
            if not ingredient_name:
                continue

            normalized_name = ingredient_name.casefold()
            if normalized_name in {"ingredient", "ingredients"}:
                continue

            table_ingredients.append(
                IngredientRecord(
                    ingredient_group="intentionally_added",
                    ingredient_name_raw=ingredient_name,
                    cas_number=clean_text(row.get(cas_header)) if cas_header else None,
                    function=clean_text(row.get(function_header)) if function_header else None,
                    designated_list_text=clean_text(row.get(designated_header)) if designated_header else None,
                    position=position,
                    source_url=source_url,
                )
            )

        if table_ingredients:
            ingredients.extend(table_ingredients)
            break

    return ingredients


def _parse_pg_smartlabel_page(
    url: str,
    fetcher: Fetcher,
) -> tuple[str | None, list[IngredientRecord], str | None, str | None]:
    """Render a P&G SmartLabel page and extract ingredient content when possible."""

    try:
        page, soup = fetcher.fetch_rendered_soup(url, wait_for="body")
    except RuntimeError as exc:
        return None, [], None, str(exc)

    title = clean_text(soup.find("h1").get_text(" ", strip=True)) if soup.find("h1") else clean_text(soup.title.get_text(" ", strip=True))
    ingredients = _extract_table_ingredients(soup, page.url)
    sds_url = find_anchor_href(soup, r"(safety data sheet|\bSDS\b)")

    if ingredients:
        return title, ingredients, sds_url, "Ingredient details extracted from the rendered SmartLabel page."

    return (
        title,
        [],
        sds_url,
        "Rendered SmartLabel page loaded, but no ingredient table was detected.",
    )


def _scrape_brand_page(seed: SourceSeed, fetcher: Fetcher, brand: str) -> list[ScrapedProduct]:
    page, soup = fetcher.fetch_soup(seed.url)
    content = page_text(soup)
    h1 = soup.find("h1")
    title = clean_text(h1.get_text(" ", strip=True)) if h1 else seed.url
    smartlabel_url = _find_smartlabel_url(soup)
    size_match = SIZE_RE.search(content)
    size_text = clean_text(size_match.group(0)) if size_match else None

    product = ScrapedProduct(
        source_family=seed.family,
        source_type=seed.source_type,
        source_url=page.url,
        seed_url=seed.url,
        parser_name=seed.family,
        source_product_name=title,
        brand=brand,
        variant=title,
        form=infer_form(title, page.url),
        scent=infer_scent(title, content),
        size_text=size_text,
        ingredient_page_url=smartlabel_url,
        notes=seed.notes or None,
        raw_sha256=page.raw_sha256,
        extracted_at=datetime.now(UTC).isoformat(),
    )

    if smartlabel_url and "labelinsight.com" in smartlabel_url:
        smartlabel_title, ingredients, sds_url = _parse_labelinsight_page(smartlabel_url, fetcher)
        if smartlabel_title:
            product.extra["smartlabel_product_name"] = smartlabel_title
        product.ingredients.extend(ingredients)
        if sds_url:
            product.sds_url = sds_url
    elif smartlabel_url and "smartlabel.pg.com" in smartlabel_url:
        smartlabel_title, ingredients, sds_url, smartlabel_note = _parse_pg_smartlabel_page(smartlabel_url, fetcher)
        if smartlabel_title:
            product.extra["smartlabel_product_name"] = smartlabel_title
        product.ingredients.extend(ingredients)
        if sds_url:
            product.sds_url = sds_url
        if smartlabel_note:
            product.notes = clean_text(
                " ".join(
                    filter(
                        None,
                        [
                            product.notes,
                            smartlabel_note,
                        ],
                    )
                )
            )

    return [product]


def scrape_tide(seed: SourceSeed, fetcher: Fetcher) -> list[ScrapedProduct]:
    """Scrape a Tide official product page."""

    return _scrape_brand_page(seed, fetcher, brand="Tide")


def scrape_clorox(seed: SourceSeed, fetcher: Fetcher) -> list[ScrapedProduct]:
    """Scrape a Clorox official product page."""

    return _scrape_brand_page(seed, fetcher, brand="Clorox")
