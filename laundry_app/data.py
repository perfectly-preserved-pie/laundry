"""Workbook parsing and grid payload preparation helpers."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
import os
import re

import pandas as pd

from laundry_app.config import (
    COLUMN_VALUE_OVERRIDES,
    GLOSSARY_TERM_ALIASES,
    HEADER_NORMALIZATIONS,
    NUMERIC_PATTERN,
    PURE_BOOLEAN_TOKENS,
    SET_FILTER_MAX_UNIQUES,
    SHEET_CONFIGS,
    VALUE_NORMALIZATIONS,
    WORKBOOK_EXPORT_URL,
)
from laundry_app.filtering import build_filter_options
from laundry_app.types import AppData, ColumnDef, GlossarySections, SheetPayload


def compact_whitespace(value: str) -> str:
    """Collapse repeated whitespace and trim the resulting string.

    Args:
        value: Raw workbook text that may contain newlines or non-breaking spaces.

    Returns:
        A normalized string with consecutive whitespace collapsed to single spaces.
    """

    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def clean_header(value: Any) -> str:
    """Normalize a workbook header into its display name.

    Args:
        value: Raw header cell value from the workbook.

    Returns:
        A cleaned header label with known naming inconsistencies corrected.
    """

    text = compact_whitespace(str(value or "").replace("\n", " "))
    return HEADER_NORMALIZATIONS.get(text, text)


def clean_cell(value: Any) -> Any:
    """Normalize a workbook cell value for use in the grid.

    Args:
        value: Raw cell value from the workbook.

    Returns:
        A cleaned Python value with empty cells converted to ``None`` and known
        categorical tokens normalized to consistent display values.
    """

    if pd.isna(value):
        return None

    if isinstance(value, str):
        text = compact_whitespace(value.replace("\n", " "))
        if not text:
            return None
        return VALUE_NORMALIZATIONS.get(text.casefold(), text)

    if isinstance(value, float) and value.is_integer():
        return int(value)

    return value


def normalize_column_value(column: str, value: Any) -> Any:
    """Apply column-specific overrides after the base cell normalization step.

    Args:
        column: The normalized column name.
        value: The cleaned cell value for that column.

    Returns:
        The overridden value when a column-specific mapping exists, otherwise the
        original cleaned value.
    """

    if value is None:
        return None

    overrides = COLUMN_VALUE_OVERRIDES.get(column)
    if not overrides:
        return value

    return overrides.get(str(value), value)


def parse_number(value: Any) -> int | float | None:
    """Convert a scalar cell value into a numeric value when possible.

    Args:
        value: Cell value that may already be numeric or may be a numeric string.

    Returns:
        An ``int`` or ``float`` when parsing succeeds, otherwise ``None``.
    """

    if value is None or pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        return value

    text = str(value).strip().replace(",", "")
    if not NUMERIC_PATTERN.fullmatch(text):
        return None

    numeric = float(text)
    return int(numeric) if numeric.is_integer() else numeric


def parse_boolean(value: Any) -> bool | None:
    """Convert a normalized yes/no value into a Python boolean.

    Args:
        value: Cell value that may represent a boolean in the workbook.

    Returns:
        ``True`` for ``Yes``, ``False`` for ``No``, and ``None`` for empty cells
        or values that are not strict booleans.
    """

    if value is None or pd.isna(value):
        return None

    if isinstance(value, bool):
        return value

    token = str(value).strip().casefold()
    if token == "yes":
        return True
    if token == "no":
        return False
    return None


def workbook_candidates() -> list[Path]:
    """Build the ordered list of workbook file paths to try locally.

    Args:
        None.

    Returns:
        A list of candidate paths, starting with any explicit environment override.
    """

    candidates: list[Path] = []

    env_path = os.getenv("LAUNDRY_WORKBOOK_PATH")
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(
        [
            Path(__file__).resolve().parent.parent / "laundry_sheet.xlsx",
            Path("/tmp/laundry_sheet.xlsx"),
        ]
    )

    return candidates


def load_workbook_bytes() -> bytes:
    """Load the workbook from disk or, as a fallback, from Google Sheets.

    Args:
        None.

    Returns:
        The raw XLSX bytes for the workbook.
    """

    for candidate in workbook_candidates():
        if candidate.exists():
            return candidate.read_bytes()

    request = Request(WORKBOOK_EXPORT_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def prepare_sheet_frame(raw_sheet: pd.DataFrame) -> pd.DataFrame:
    """Extract a clean data frame from a raw workbook sheet.

    Args:
        raw_sheet: The sheet as loaded by pandas without a predefined header row.

    Returns:
        A cleaned data frame whose columns begin at the detected ``Product Name``
        header row and whose empty rows and empty cells are normalized.

    Raises:
        ValueError: If the sheet does not contain a ``Product Name`` header row.
    """

    first_column = raw_sheet.iloc[:, 0].fillna("").astype(str).map(compact_whitespace)
    header_rows = first_column[first_column.eq("Product Name")]
    if header_rows.empty:
        raise ValueError("Could not find the header row that starts with 'Product Name'.")

    header_index = header_rows.index[0]
    raw_headers = [clean_header(value) for value in raw_sheet.iloc[header_index].tolist()]
    valid_positions = [index for index, header in enumerate(raw_headers) if header]
    headers = [raw_headers[index] for index in valid_positions]

    frame = raw_sheet.iloc[header_index + 1 :, valid_positions].copy()
    frame.columns = headers
    frame = frame.map(clean_cell)
    for column in frame.columns:
        frame[column] = frame[column].map(lambda value, *, _column=column: normalize_column_value(_column, value))
    frame = frame.astype(object).where(pd.notna(frame), None)
    frame = frame.loc[
        frame.apply(lambda row: any(value not in (None, "") for value in row), axis=1)
    ].reset_index(drop=True)

    return frame


def parse_glossary(raw_sheet: pd.DataFrame) -> GlossarySections:
    """Build glossary sections from the workbook's Key sheet.

    Args:
        raw_sheet: The raw Key sheet loaded from the workbook.

    Returns:
        A mapping of glossary section names to ordered lists of term-definition pairs.
    """

    sections: GlossarySections = {}
    current_section: str | None = None

    for _, row in raw_sheet.iterrows():
        left = clean_cell(row.iloc[0]) if len(row) else None
        right = clean_cell(row.iloc[1]) if len(row) > 1 else None

        if not left and not right:
            continue

        left_text = clean_header(left) if isinstance(left, str) else str(left or "")
        right_text = str(right or "")

        if left_text.endswith("Key") and not right_text:
            current_section = left_text
            sections[current_section] = []
            continue

        if current_section and left_text:
            sections[current_section].append({"term": left_text, "definition": right_text})

    return sections


def get_sheet_glossary(sheet_name: str, glossary: GlossarySections) -> GlossarySections:
    """Return just the glossary section that belongs to a given sheet."""

    config = SHEET_CONFIGS.get(sheet_name)
    if not config:
        return {}

    glossary_section = config["glossary_section"]
    if glossary_section not in glossary:
        return {}

    return {
        glossary_section: glossary[glossary_section],
    }


def infer_column_kind(column: str, series: pd.Series) -> str:
    """Infer the best AG Grid filter kind for a sheet column.

    Args:
        column: The normalized column name.
        series: The pandas series containing that column's values.

    Returns:
        One of ``text``, ``number``, ``boolean``, or ``set``.
    """

    if column in {"Product Name", "Notes"}:
        return "text"

    values = [value for value in series.tolist() if value not in (None, "") and not pd.isna(value)]
    if not values:
        return "text"

    if all(parse_number(value) is not None for value in values):
        return "number"

    unique_values = {str(value).strip() for value in values}
    normalized_tokens = {token.casefold() for token in unique_values}
    max_length = max(len(token) for token in unique_values)

    if normalized_tokens and normalized_tokens <= PURE_BOOLEAN_TOKENS:
        return "boolean"

    if len(unique_values) <= SET_FILTER_MAX_UNIQUES and max_length <= 36:
        return "set"

    return "text"


def build_glossary_lookup(glossary: GlossarySections) -> dict[str, str]:
    """Map glossary terms to grid column names and definitions."""

    lookup: dict[str, str] = {}

    for entries in glossary.values():
        for entry in entries:
            term = clean_header(entry["term"])
            column = GLOSSARY_TERM_ALIASES.get(term, term)
            definition = compact_whitespace(str(entry["definition"] or ""))
            if column and definition and column not in lookup:
                lookup[column] = definition

    return lookup


def build_column_def(
    column: str,
    kind: str,
    filter_options: list[dict[str, str]] | None = None,
    header_tooltip: str | None = None,
) -> ColumnDef:
    """Create a Dash AG Grid column definition for a normalized column.

    Args:
        column: The display name for the column.
        kind: The inferred filter kind for the column.
        filter_options: Optional low-cardinality values used by the OSS set filter.

    Returns:
        A Dash AG Grid column definition tailored to the column's content type.
    """

    column_def: ColumnDef = {
        "field": column,
        "headerName": column,
        "sortable": True,
        "resizable": True,
        "filter": "agTextColumnFilter",
        "wrapHeaderText": True,
        "autoHeaderHeight": True,
        "minWidth": 135,
    }
    if header_tooltip:
        column_def["headerTooltip"] = header_tooltip
        column_def["headerClass"] = "glossary-header"

    if column == "Product Name":
        column_def.update(
            {
                "pinned": "left",
                "width": 280,
                "minWidth": 180,
                "tooltipField": column,
            }
        )
        return column_def

    if column == "Notes":
        column_def.update(
            {
                "minWidth": 340,
                "flex": 2,
                "tooltipField": column,
                "wrapText": True,
                "autoHeight": True,
                "cellClass": "notes-column",
            }
        )
        return column_def

    if kind == "number":
        column_def.update(
            {
                "filter": "agNumberColumnFilter",
                "type": "numericColumn",
                "minWidth": 120,
            }
        )
        return column_def

    if kind in {"boolean", "set"}:
        if kind == "boolean":
            column_def.update(
                {
                    "filter": True,
                    "cellDataType": "boolean",
                    "minWidth": 120,
                }
            )
            return column_def

        column_def.update(
            {
                "filter": {"function": "LaundrySetFilter"},
                "filterParams": {
                    "values": filter_options or [],
                },
                "minWidth": 140,
                "tooltipField": column,
            }
        )
        return column_def

    column_def["tooltipField"] = column
    return column_def


def build_sheet_payload(
    sheet_name: str,
    frame: pd.DataFrame,
    glossary: GlossarySections,
) -> SheetPayload:
    """Convert a cleaned sheet data frame into a tab payload for the app.

    Args:
        sheet_name: The original workbook sheet name.
        frame: The cleaned data frame for that sheet.

    Returns:
        A structured payload containing tab metadata, row data, and column definitions.
    """

    config = SHEET_CONFIGS.get(
        sheet_name,
        {
            "tab_id": re.sub(r"[^a-z0-9]+", "-", sheet_name.casefold()).strip("-"),
            "label": sheet_name,
            "description": "Filterable sheet data.",
            "glossary_section": "",
        },
    )

    working_frame = frame.copy()
    sheet_glossary = get_sheet_glossary(sheet_name, glossary)
    glossary_lookup = build_glossary_lookup(sheet_glossary)
    column_defs: list[ColumnDef] = []
    kind_map: dict[str, str] = {}

    for column in working_frame.columns:
        kind = infer_column_kind(column, working_frame[column])
        kind_map[column] = kind
        if kind == "number":
            working_frame[column] = working_frame[column].map(parse_number)
        if kind == "boolean":
            working_frame[column] = working_frame[column].map(parse_boolean)
        filter_options = build_filter_options(working_frame[column].tolist()) if kind == "set" else None
        column_defs.append(
            build_column_def(
                column,
                kind,
                filter_options,
                header_tooltip=glossary_lookup.get(column),
            )
        )

    return {
        "tab_id": config["tab_id"],
        "label": config["label"],
        "sheet_name": sheet_name,
        "description": config["description"],
        "count": len(working_frame),
        "rowData": working_frame.where(pd.notna(working_frame), None).to_dict("records"),
        "columnDefs": column_defs,
        "columnKinds": kind_map,
        "glossary": sheet_glossary,
    }


@lru_cache(maxsize=1)
def load_app_data() -> AppData:
    """Load and cache the prepared workbook data for the whole app.

    Args:
        None.

    Returns:
        A cached application data structure containing all tab payloads,
        glossary data, and summary counts.

    Raises:
        ValueError: If the workbook does not contain any supported data sheets.
    """

    workbook_bytes = load_workbook_bytes()
    workbook = pd.read_excel(
        BytesIO(workbook_bytes),
        sheet_name=None,
        header=None,
        keep_default_na=False,
    )

    glossary: GlossarySections = {}
    data_sheets: list[tuple[str, pd.DataFrame]] = []
    payloads: dict[str, SheetPayload] = {}
    sheet_order: list[str] = []
    total_rows = 0

    for sheet_name, raw_sheet in workbook.items():
        if sheet_name == "Key":
            glossary = parse_glossary(raw_sheet)
            continue

        data_sheets.append((sheet_name, raw_sheet))

    for sheet_name, raw_sheet in data_sheets:
        payload = build_sheet_payload(sheet_name, prepare_sheet_frame(raw_sheet), glossary)
        payloads[payload["tab_id"]] = payload
        sheet_order.append(payload["tab_id"])
        total_rows += payload["count"]

    if not sheet_order:
        raise ValueError("The workbook did not contain any supported data sheets.")

    return {
        "payloads": payloads,
        "sheet_order": sheet_order,
        "default_tab": sheet_order[0],
        "glossary": glossary,
        "sheet_count": len(sheet_order),
        "row_count": total_rows,
    }


def get_app_data() -> tuple[AppData | None, str | None]:
    """Safely load app data for layout rendering.

    Args:
        None.

    Returns:
        A tuple of ``(data, error_message)`` where only one value is populated.
    """

    try:
        return load_app_data(), None
    except Exception as exc:  # pragma: no cover - user-facing fallback
        return None, str(exc)
