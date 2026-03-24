"""Shared type definitions for the laundry app."""

from __future__ import annotations

from typing import Any, TypeAlias, TypedDict

GridRow: TypeAlias = dict[str, Any]
ColumnDef: TypeAlias = dict[str, Any]
ClickPayload: TypeAlias = dict[str, Any]


class SheetConfig(TypedDict):
    """Configuration metadata for a single workbook sheet."""

    tab_id: str
    label: str
    description: str
    glossary_section: str


class GlossaryEntry(TypedDict):
    """A single glossary term and its definition."""

    term: str
    definition: str


GlossarySections: TypeAlias = dict[str, list[GlossaryEntry]]


class SheetPayload(TypedDict):
    """Prepared grid payload for a workbook tab."""

    tab_id: str
    label: str
    sheet_name: str
    description: str
    count: int
    rowData: list[GridRow]
    columnDefs: list[ColumnDef]
    columnKinds: dict[str, str]
    glossary: GlossarySections


class AppData(TypedDict):
    """Fully prepared app data derived from the workbook."""

    payloads: dict[str, SheetPayload]
    sheet_order: list[str]
    default_tab: str
    glossary: GlossarySections
    sheet_count: int
    row_count: int
