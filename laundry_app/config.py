"""Configuration constants for the laundry app."""

from __future__ import annotations

import os
import re

from laundry_app.types import SheetConfig

WORKBOOK_TITLE = "Lipase List 20260105"
WORKBOOK_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1oHWzZ1Sth0Y0J2ynmXFl7M4mGZe-T_MJ_m_Y39pfBug/edit?gid=0#gid=0"
)
WORKBOOK_EXPORT_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1oHWzZ1Sth0Y0J2ynmXFl7M4mGZe-T_MJ_m_Y39pfBug/export?format=xlsx"
)
DEFAULT_GITHUB_URL = "https://github.com/perfectly-preserved-pie/ludex/tree/main"
GITHUB_URL = os.getenv("LAUNDRY_APP_GITHUB_URL", DEFAULT_GITHUB_URL)
REDDIT_ATTRIBUTION_URL = "https://www.reddit.com/user/KismaiAesthetics/"

SHEET_CONFIGS: dict[str, SheetConfig] = {
    "Detergents - North America": {
        "tab_id": "detergents",
        "label": "Detergents",
        "description": "Laundry detergents with formula notes, fragrance options, and enzyme-related flags.",
    },
    "Pretreaters - North America": {
        "tab_id": "pretreaters",
        "label": "Pretreaters",
        "description": "Stain removers and pretreaters with enzyme coverage, solvent presence, and retailer-brand markers.",
    },
    "Boosters - North America": {
        "tab_id": "boosters",
        "label": "Boosters",
        "description": "Laundry boosters grouped by class with oxygen bleach, scent-control, and enzyme traits.",
    },
}

HEADER_NORMALIZATIONS = {
    "Plant-Based Surfactants": "Plant-Based Surfactants",
    "Primarily Plant-Based Surfactants": "Primarily Plant-Based Surfactants",
    "Fragrance - Free Option": "Fragrance-Free Option",
    "Fragrance - Free Variety": "Fragrance-Free Variety",
    "Fragrance Free?": "Fragrance-Free?",
    "WoolSafe / Protease-Free": "Wool Safe / Protease-Free",
    "Wool Safe / Protease-Free": "Wool Safe / Protease-Free",
    "WoolSafe / Protease- Free": "Wool Safe / Protease-Free",
    "Wool Safe / Protease- Free": "Wool Safe / Protease-Free",
    "Oxygen Bleach": "Oxygen Bleach",
    "Retailer Brand": "Retailer Brand",
    "Retailer/Brand": "Retailer Brand",
    "Pectic Lyase": "Pectic Lyase",
    "DNAse": "DNase",
    "Dnase": "DNase",
    "HE Antifoam": "HE Antifoam",
    "Water Softener": "Water Softener",
    "Secret Sauce": "Secret Sauce",
    "Anti-Redep": "Anti-Redep",
    "Anti- Redep": "Anti-Redep",
}

VALUE_NORMALIZATIONS = {
    "y": "Yes",
    "yes": "Yes",
    "yea": "Yes",
    "yes*": "Yes*",
    "n": "No",
    "no": "No",
    "no*": "No*",
    "mo": "No",
    "unknown": "Unknown",
    "varies": "Varies",
    "see notes": "See Notes",
}

COLUMN_VALUE_OVERRIDES: dict[str, dict[str, str | None]] = {
    "Anti-Redep": {
        "Unknown": None,
    },
    "Soapy Ingredients": {
        "Unknown": None,
        "Varies": None,
    },
    "HE Antifoam": {
        "Unknown": None,
    },
    "Pectic Lyase": {
        "Unknown": None,
    },
    "Mannanase": {
        "Unknown": None,
    },
    "DNase": {
        "Unknown": None,
    },
    "Cellulase": {
        "Unknown": None,
    },
    "Fragrance-Free?": {
        "No*": "No",
    },
    "Fragrance-Free Option": {
        "Unknown": None,
        "See Notes": None,
    },
    "OBA": {
        "Yes*": "Yes",
        "Unknown": None,
    }
}

PURE_BOOLEAN_TOKENS = {
    "yes",
    "no",
}

SET_FILTER_MAX_UNIQUES = 12
NUMERIC_PATTERN = re.compile(r"^-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?$")

AG_GRID_CLASS_NAME = "ag-theme-quartz grid-shell laundry-grid-theme"
