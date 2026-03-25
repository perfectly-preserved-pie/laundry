"""HTML parsing utilities shared by multiple source scrapers."""

from __future__ import annotations

from typing import Iterable
import re

from bs4 import Tag

from laundry_app.scraping.normalize import collapse_whitespace


DATE_RE = re.compile(
    r"(Date of data entry|DATE OF DISCLOSURE|Revision Date)\s*:?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2}|New)",
    re.IGNORECASE,
)


def clean_text(value: str | None) -> str:
    """Normalize scraped text into a compact single-line string."""

    return collapse_whitespace(value or "")


def page_text(tag: Tag) -> str:
    """Return all visible text from a BeautifulSoup tag."""

    return clean_text(tag.get_text(" ", strip=True))


def extract_between_labels(text: str, start_label: str, end_label: str | None = None) -> str | None:
    """Extract text between two label markers from a flat page text string."""

    start_index = text.find(start_label)
    if start_index == -1:
        return None
    start_index += len(start_label)
    chunk = text[start_index:]
    if end_label:
        end_index = chunk.find(end_label)
        if end_index != -1:
            chunk = chunk[:end_index]
    cleaned = clean_text(chunk)
    return cleaned or None


def parse_html_table(table: Tag) -> list[dict[str, str]]:
    """Convert an HTML table into a list of row dictionaries."""

    rows = table.find_all("tr")
    if not rows:
        return []

    headers = [clean_text(cell.get_text(" | ", strip=True)) for cell in rows[0].find_all(["th", "td"])]
    parsed_rows: list[dict[str, str]] = []

    for row in rows[1:]:
        cells = [clean_text(cell.get_text(" | ", strip=True)) for cell in row.find_all(["th", "td"])]
        if not cells:
            continue
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))
        parsed_rows.append(dict(zip(headers, cells, strict=False)))

    return parsed_rows


def find_anchor_href(tag: Tag, pattern: str) -> str | None:
    """Find the first anchor whose visible text matches a regex pattern."""

    regex = re.compile(pattern, re.IGNORECASE)
    for anchor in tag.find_all("a", href=True):
        if regex.search(anchor.get_text(" ", strip=True)):
            return anchor["href"]
    return None


def find_dates(text: str) -> list[tuple[str, str]]:
    """Extract labeled date strings from a page text blob."""

    return [(clean_text(label), clean_text(value)) for label, value in DATE_RE.findall(text)]


def first(items: Iterable[str | None]) -> str | None:
    """Return the first non-empty string from an iterable."""

    for item in items:
        cleaned = clean_text(item)
        if cleaned:
            return cleaned
    return None
