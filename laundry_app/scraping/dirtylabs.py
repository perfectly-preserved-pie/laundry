"""Scraper for Dirty Labs product pages with folding ingredient sections."""

from __future__ import annotations

from datetime import datetime, UTC
import re

from laundry_app.scraping.html_utils import clean_text, page_text
from laundry_app.scraping.http import Fetcher
from laundry_app.scraping.models import IngredientRecord, ScrapedProduct, SourceSeed
from laundry_app.scraping.normalize import infer_form, infer_scent


INGREDIENT_RE = re.compile(r"(?P<name>[^,]+?)\s+\(CAS\s+(?P<cas>[^)]+)\)")
LOAD_RE = re.compile(r"\b\d+\s*loads(?:\s*-\s*refill)?\b", re.IGNORECASE)


def _section_text(section_text: str, heading: str) -> str:
    """Strip the accordion heading from the extracted section text."""

    if section_text.startswith(heading):
        return clean_text(section_text[len(heading) :])
    return section_text


def scrape(seed: SourceSeed, fetcher: Fetcher) -> list[ScrapedProduct]:
    """Scrape a Dirty Labs product page."""

    page, soup = fetcher.fetch_soup(seed.url)
    form = soup.find("form", class_=re.compile("pdp-form"))
    page_content = page_text(form or soup)

    title = clean_text(soup.find("h1").get_text(" ", strip=True)) if soup.find("h1") else seed.url
    subtitle = None
    if soup.find("h1") is not None:
        next_heading = soup.find("h1").find_next(["h2", "h3"])
        subtitle = clean_text(next_heading.get_text(" ", strip=True)) if next_heading else None

    load_count_matches = sorted({clean_text(match.group(0)) for match in LOAD_RE.finditer(page_content)})
    load_count_text = ", ".join(load_count_matches) or None

    product = ScrapedProduct(
        source_family=seed.family,
        source_type=seed.source_type,
        source_url=page.url,
        seed_url=seed.url,
        parser_name=seed.family,
        source_product_name=title,
        brand="Dirty Labs",
        variant=subtitle or title,
        form=infer_form(title, subtitle, "powder"),
        scent=infer_scent(title, subtitle, page_content),
        load_count_text=load_count_text,
        ingredient_page_url=page.url,
        notes=seed.notes or None,
        raw_sha256=page.raw_sha256,
        extracted_at=datetime.now(UTC).isoformat(),
    )

    sections: dict[str, str] = {}
    for section in soup.select(".folding-section"):
        button = section.find(["button", "summary"])
        if button is None:
            continue
        heading = clean_text(button.get_text(" ", strip=True))
        if not heading:
            continue
        sections[heading.casefold()] = _section_text(page_text(section), heading)

    ingredients_text = sections.get("ingredients", "")
    for position, match in enumerate(INGREDIENT_RE.finditer(ingredients_text), start=1):
        product.ingredients.append(
            IngredientRecord(
                ingredient_group="intentionally_added",
                ingredient_name_raw=clean_text(match.group("name")),
                cas_number=clean_text(match.group("cas")),
                position=position,
                source_url=page.url,
            )
        )

    return [product]
