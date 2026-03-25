"""Scraper for Dropps ingredient disclosure landing pages."""

from __future__ import annotations

from datetime import datetime, UTC

from laundry_app.scraping.html_utils import clean_text, parse_html_table
from laundry_app.scraping.http import Fetcher
from laundry_app.scraping.models import IngredientRecord, ScrapedProduct, SourceSeed
from laundry_app.scraping.normalize import infer_form, infer_scent


def _extract_rendered_ingredients(fetcher: Fetcher, url: str) -> tuple[list[IngredientRecord], str | None]:
    """Attempt a richer ingredient extraction from the rendered disclosure page."""

    try:
        page, soup = fetcher.fetch_rendered_soup(url, wait_for="body")
    except RuntimeError as exc:
        return [], str(exc)

    for table in soup.find_all("table"):
        rows = parse_html_table(table)
        if not rows:
            continue

        ingredient_header = next(
            (
                header
                for header in rows[0]
                if "ingredient" in clean_text(header).casefold()
            ),
            None,
        )
        if ingredient_header is None:
            continue

        function_header = next(
            (
                header
                for header in rows[0]
                if any(token in clean_text(header).casefold() for token in ("function", "purpose", "role"))
            ),
            None,
        )
        cas_header = next(
            (
                header
                for header in rows[0]
                if clean_text(header).casefold().startswith("cas")
            ),
            None,
        )

        ingredients: list[IngredientRecord] = []
        for position, row in enumerate(rows, start=1):
            name = clean_text(row.get(ingredient_header))
            if not name:
                continue
            ingredients.append(
                IngredientRecord(
                    ingredient_group="intentionally_added",
                    ingredient_name_raw=name,
                    cas_number=clean_text(row.get(cas_header)) if cas_header else None,
                    function=clean_text(row.get(function_header)) if function_header else None,
                    position=position,
                    source_url=page.url,
                )
            )

        if ingredients:
            return ingredients, "Ingredient details extracted from the rendered Dropps disclosure page."

    return [], "Rendered Dropps disclosure page loaded, but no ingredient table was detected."


def scrape(seed: SourceSeed, fetcher: Fetcher) -> list[ScrapedProduct]:
    """Scrape a Dropps disclosure page.

    The live Dropps pages currently expose strong title/metadata server-side, but
    the detailed ingredient grid appears to render client-side. We still capture
    provenance and product metadata, and leave room for a future browser scraper
    to enrich the ingredient list.
    """

    page, soup = fetcher.fetch_soup(seed.url)
    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(" ", strip=True)) if title_tag else clean_text(soup.title.get_text(" ", strip=True))
    meta = soup.find("meta", attrs={"name": "description"})
    description = clean_text(meta["content"]) if meta and meta.has_attr("content") else None

    product = ScrapedProduct(
        source_family=seed.family,
        source_type=seed.source_type,
        source_url=page.url,
        seed_url=seed.url,
        parser_name=seed.family,
        source_product_name=title,
        brand="Dropps",
        variant=title,
        form=infer_form(title, page.url),
        scent=infer_scent(title),
        ingredient_page_url=page.url,
        notes=description or seed.notes or "Detailed ingredient entries appear to be client-rendered on this page.",
        raw_sha256=page.raw_sha256,
        extracted_at=datetime.now(UTC).isoformat(),
    )

    rendered_ingredients, rendered_note = _extract_rendered_ingredients(fetcher, seed.url)
    if rendered_ingredients:
        product.ingredients.extend(rendered_ingredients)
    if rendered_note:
        product.notes = clean_text(
            " ".join(
                filter(
                    None,
                    [
                        product.notes,
                        rendered_note,
                    ],
                )
            )
        )

    return [product]
