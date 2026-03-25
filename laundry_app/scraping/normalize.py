"""Normalization helpers shared by the scraping pipeline."""

from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata


WHITESPACE_RE = re.compile(r"\s+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def collapse_whitespace(value: str) -> str:
    """Collapse repeated whitespace into single spaces."""

    return WHITESPACE_RE.sub(" ", value.replace("\xa0", " ")).strip()


def strip_diacritics(value: str) -> str:
    """Fold accents and other diacritics into ASCII."""

    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_identifier(value: str | None) -> str:
    """Build a forgiving identifier for fuzzy matching."""

    if not value:
        return ""

    text = value
    for token in ("™", "®", "©", "℠"):
        text = text.replace(token, " ")
    text = collapse_whitespace(strip_diacritics(text))
    text = text.replace("&", " and ").replace("+", " plus ")
    text = text.casefold()
    text = NON_ALNUM_RE.sub(" ", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def tokenize(value: str | None) -> set[str]:
    """Tokenize a string after identifier normalization."""

    normalized = normalize_identifier(value)
    return {token for token in normalized.split() if token}


def compare_names(left: str | None, right: str | None) -> float:
    """Score two names from 0 to 1 using exact, substring, and token overlap."""

    left_norm = normalize_identifier(left)
    right_norm = normalize_identifier(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    if left_norm in right_norm or right_norm in left_norm:
        return 0.92

    left_tokens = tokenize(left_norm)
    right_tokens = tokenize(right_norm)
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    jaccard = overlap / union if union else 0.0
    ratio = SequenceMatcher(a=left_norm, b=right_norm).ratio()
    return max(jaccard, ratio * 0.9)


def canonical_form(value: str | None) -> str | None:
    """Normalize form labels into a smaller matching-friendly set."""

    normalized = normalize_identifier(value)
    if not normalized:
        return None
    if any(token in normalized for token in ("powder", "whitener", "booster", "oxygen brightener")):
        return "powder"
    if any(token in normalized for token in ("pac", "pacs", "pak", "paks")):
        return "pacs"
    if "pod" in normalized:
        return "pods"
    if "tablet" in normalized:
        return "tablet"
    if any(token in normalized for token in ("liquid", "spray", "gel", "stain remover", "prewash")):
        return "liquid"
    return normalized


def infer_form(*values: str | None) -> str | None:
    """Infer a canonical form from one or more strings."""

    for value in values:
        form = canonical_form(value)
        if form is not None:
            return form
    return None


def infer_scent(*values: str | None) -> str | None:
    """Infer a scent/free-clear style label from product text."""

    for value in values:
        normalized = normalize_identifier(value)
        if not normalized:
            continue
        if "free and clear" in normalized or "free clear" in normalized:
            return "Free & Clear"
        if "unscented" in normalized:
            return "Unscented"
        if "fragrance free" in normalized:
            return "Fragrance-Free"
        if "lavender" in normalized:
            return "Lavender"
        if "citrus" in normalized:
            return "Citrus"
        if "clean linen" in normalized:
            return "Clean Linen"
        if "original" in normalized:
            return "Original"
    return None
