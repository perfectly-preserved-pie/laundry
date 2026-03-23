"""Dash AG Grid app for exploring laundry detergents, pretreaters, and boosters."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any, TypeAlias, TypedDict
from urllib.request import Request, urlopen
import os
import re

import dash
from dash import Input, Output, State, callback, callback_context, dcc, html, no_update
from dash.exceptions import PreventUpdate
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash_iconify import DashIconify
import pandas as pd

GridRow: TypeAlias = dict[str, Any]
ColumnDef: TypeAlias = dict[str, Any]
ClickPayload: TypeAlias = dict[str, Any]


class SheetConfig(TypedDict):
    """Configuration metadata for a single workbook sheet."""

    tab_id: str
    label: str
    description: str


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


class AppData(TypedDict):
    """Fully prepared app data derived from the workbook."""

    payloads: dict[str, SheetPayload]
    sheet_order: list[str]
    default_tab: str
    glossary: GlossarySections
    sheet_count: int
    row_count: int


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

BOOLEANISH_TOKENS = {
    "yes",
    "yes*",
    "no",
    "no*",
    "unknown",
    "varies",
    "see notes",
}

SET_FILTER_MAX_UNIQUES = 12
NUMERIC_PATTERN = re.compile(r"^-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?$")


ag_grid_theme: dict[str, str] = {
    "function": (
        "themeQuartz.withParams({"
        "accentColor: 'var(--mantine-primary-color-filled)', "
        "backgroundColor: 'var(--mantine-color-body)', "
        "foregroundColor: 'var(--mantine-color-text)', "
        "fontFamily: 'var(--mantine-font-family)', "
        "headerFontWeight: 600"
        "})"
    )
}


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


def parse_number(value: Any) -> int | float | None:
    """Convert a scalar cell value into a numeric value when possible.

    Args:
        value: Cell value that may already be numeric or may be a numeric string.

    Returns:
        An ``int`` or ``float`` when parsing succeeds, otherwise ``None``.
    """

    if value is None:
        return None

    if isinstance(value, (int, float)):
        return value

    text = str(value).strip().replace(",", "")
    if not NUMERIC_PATTERN.fullmatch(text):
        return None

    numeric = float(text)
    return int(numeric) if numeric.is_integer() else numeric


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
            Path(__file__).with_name("laundry_sheet.xlsx"),
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

    values = [value for value in series.tolist() if value not in (None, "")]
    if not values:
        return "text"

    if all(parse_number(value) is not None for value in values):
        return "number"

    unique_values = {str(value).strip() for value in values}
    normalized_tokens = {token.casefold() for token in unique_values}
    max_length = max(len(token) for token in unique_values)

    if normalized_tokens and normalized_tokens <= BOOLEANISH_TOKENS:
        return "boolean"

    if len(unique_values) <= SET_FILTER_MAX_UNIQUES and max_length <= 36:
        return "set"

    return "text"


def build_column_def(column: str, kind: str) -> ColumnDef:
    """Create a Dash AG Grid column definition for a normalized column.

    Args:
        column: The display name for the column.
        kind: The inferred filter kind for the column.

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

    if column == "Product Name":
        column_def.update(
            {
                "pinned": "left",
                "minWidth": 260,
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
        column_def.update(
            {
                "filter": "agSetColumnFilter",
                "filterParams": {
                    "buttons": ["reset", "apply"],
                    "closeOnApply": True,
                },
                "minWidth": 150 if kind == "boolean" else 140,
                "tooltipField": column,
            }
        )
        if kind == "boolean":
            column_def["cellClass"] = "flag-column"
        return column_def

    column_def["tooltipField"] = column
    return column_def


def build_sheet_payload(sheet_name: str, frame: pd.DataFrame) -> SheetPayload:
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
        },
    )

    working_frame = frame.copy()
    column_defs: list[ColumnDef] = []
    kind_map: dict[str, str] = {}

    for column in working_frame.columns:
        kind = infer_column_kind(column, working_frame[column])
        kind_map[column] = kind
        if kind == "number":
            working_frame[column] = working_frame[column].map(parse_number)
        column_defs.append(build_column_def(column, kind))

    return {
        "tab_id": config["tab_id"],
        "label": config["label"],
        "sheet_name": sheet_name,
        "description": config["description"],
        "count": len(working_frame),
        "rowData": working_frame.where(pd.notna(working_frame), None).to_dict("records"),
        "columnDefs": column_defs,
        "columnKinds": kind_map,
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

    glossary = {}
    payloads: dict[str, SheetPayload] = {}
    sheet_order: list[str] = []
    total_rows = 0

    for sheet_name, raw_sheet in workbook.items():
        if sheet_name == "Key":
            glossary = parse_glossary(raw_sheet)
            continue

        payload = build_sheet_payload(sheet_name, prepare_sheet_frame(raw_sheet))
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


def build_title_card(data: AppData | None) -> dbc.Card:
    """Build the page title card with links and attribution.

    Args:
        data: Loaded app data, or ``None`` when the workbook could not be read.

    Returns:
        A Bootstrap card that introduces the app and links back to its sources.
    """

    sheet_count = data["sheet_count"] if data else 0
    row_count = data["row_count"] if data else 0

    return dbc.Card(
        [
            html.Div("Laundry Grid", className="title-kicker"),
            html.H1("Laundry Detergents, Pretreaters, and Boosters", className="card-title mb-2"),
            html.I(
                "A Ludex-style Dash AG Grid for comparing laundry formulas across multiple sheets.",
                className="d-block mb-3",
            ),
            html.P(
                "Switch tabs to browse detergents, pretreaters, and boosters. Use column filters to "
                "slice categorical flags, retailer brands, and long-form notes, then click any row for a detail view.",
                className="mb-3",
            ),
            html.Div(
                [
                    dbc.Badge(f"{sheet_count} source sheets", className="metric-pill"),
                    dbc.Badge(f"{row_count} rows loaded", className="metric-pill"),
                    dbc.Badge("Dash AG Grid", className="metric-pill"),
                ],
                className="title-metrics",
            ),
            html.Div(
                [
                    html.Span(
                        [
                            DashIconify(icon="octicon:mark-github-16", width=18),
                            html.A("GitHub", href=GITHUB_URL, target="_blank"),
                        ],
                        className="title-link",
                    ),
                    html.Span(
                        [
                            DashIconify(icon="material-symbols:table-chart-outline-rounded", width=18),
                            html.A("Source Sheet", href=WORKBOOK_URL, target="_blank"),
                        ],
                        className="title-link",
                    ),
                    html.Span(
                        [
                            DashIconify(icon="mdi:reddit", width=18),
                            html.A(
                                "Attribution: /u/KismaiAesthetics",
                                href=REDDIT_ATTRIBUTION_URL,
                                target="_blank",
                            ),
                        ],
                        className="title-link",
                    ),
                ],
                className="title-links",
            ),
        ],
        body=True,
        id="title-card",
        className="mb-4",
    )


def build_sheet_summary(payload: SheetPayload) -> html.Div:
    """Create the small metadata strip shown above the grid.

    Args:
        payload: The active tab payload.

    Returns:
        An HTML container summarizing the current sheet label, row count, and description.
    """

    return html.Div(
        [
            dbc.Badge(payload["label"], className="sheet-pill sheet-pill-primary"),
            dbc.Badge(f"{payload['count']} rows", className="sheet-pill"),
            html.Span(payload["description"], className="grid-caption"),
        ],
        className="sheet-summary",
    )


def build_glossary_card(glossary: GlossarySections) -> dbc.Card | None:
    """Render the glossary card from the workbook's Key sheet.

    Args:
        glossary: Parsed glossary sections keyed by section title.

    Returns:
        A Bootstrap card containing accordion items, or ``None`` when no glossary
        data is available.
    """

    if not glossary:
        return None

    items = []
    for section, entries in glossary.items():
        items.append(
            dbc.AccordionItem(
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(entry["term"], className="glossary-term"),
                                html.Div(entry["definition"], className="glossary-definition"),
                            ],
                            className="glossary-entry",
                        )
                        for entry in entries
                    ],
                    className="glossary-list",
                ),
                title=section,
            )
        )

    return dbc.Card(
        [
            dbc.CardBody(
                [
                    html.H2("Column Key", className="h4 mb-2"),
                    html.P(
                        "Glossary terms pulled from the workbook's Key sheet so the grid labels stay grounded in the source.",
                        className="mb-3 grid-caption",
                    ),
                    dbc.Accordion(items, always_open=True, start_collapsed=True),
                ]
            )
        ],
        className="glossary-card mt-4",
    )


def build_error_card(message: str) -> dbc.Alert:
    """Build the workbook-load error banner shown in the layout fallback.

    Args:
        message: The user-facing error message describing the load failure.

    Returns:
        A Bootstrap alert with troubleshooting guidance for the workbook path.
    """

    local_override = os.getenv("LAUNDRY_WORKBOOK_PATH", "/path/to/laundry_sheet.xlsx")
    return dbc.Alert(
        [
            html.H4("Workbook Load Failed", className="alert-heading"),
            html.P(
                "The app shell loaded, but the spreadsheet data could not be read. "
                "The title card links still point to the live source workbook."
            ),
            html.P(f"Error: {message}", className="mb-2"),
            html.Code(f"LAUNDRY_WORKBOOK_PATH={local_override}"),
        ],
        color="warning",
        className="mt-3",
    )


def build_layout() -> dmc.MantineProvider:
    """Build the full application layout.

    Args:
        None.

    Returns:
        A Mantine provider wrapping the full Bootstrap-based page shell.
    """

    data, error = get_app_data()

    sections: list[Any] = [build_title_card(data)]

    if error:
        sections.append(build_error_card(error))
    else:
        default_payload = data["payloads"][data["default_tab"]]
        sections.append(
            dbc.Card(
                dbc.CardBody(
                    [
                        html.P(
                            "Choose a sheet, filter the columns, and click a row to open the product detail modal.",
                            className="mb-3 grid-caption",
                        ),
                        dbc.Tabs(
                            id="laundry-tabs",
                            active_tab=data["default_tab"],
                            children=[
                                dbc.Tab(
                                    label=data["payloads"][tab_id]["label"],
                                    tab_id=tab_id,
                                )
                                for tab_id in data["sheet_order"]
                            ],
                            className="mb-3",
                        ),
                        html.Div(
                            build_sheet_summary(default_payload),
                            id="sheet-summary",
                            className="mb-3",
                        ),
                        dag.AgGrid(
                            id="laundry-grid",
                            rowData=default_payload["rowData"],
                            columnDefs=default_payload["columnDefs"],
                            defaultColDef={
                                "sortable": True,
                                "resizable": True,
                                "filter": True,
                                "floatingFilter": True,
                            },
                            style={"width": "100%", "height": "clamp(28rem, 66vh, 52rem)"},
                            dashGridOptions={
                                "theme": ag_grid_theme,
                                "pagination": True,
                                "paginationPageSize": 25,
                                "animateRows": False,
                                "tooltipShowDelay": 0,
                            },
                            dangerously_allow_code=True,
                        ),
                    ]
                ),
                className="grid-card",
            )
        )

        glossary_card = build_glossary_card(data["glossary"])
        if glossary_card is not None:
            sections.append(glossary_card)

    return dmc.MantineProvider(
        dbc.Container(
            [
                dbc.Row(
                    dbc.Col(
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Div("Laundry Lookup", className="toolbar-title"),
                                        html.Div(
                                            "Dash AG Grid with source-backed sheet tabs",
                                            className="toolbar-subtitle",
                                        ),
                                    ]
                                ),
                                dmc.ColorSchemeToggle(
                                    id="theme-toggle",
                                    lightIcon=DashIconify(
                                        icon="radix-icons:sun",
                                        width=16,
                                        color="var(--mantine-color-yellow-7)",
                                    ),
                                    darkIcon=DashIconify(
                                        icon="radix-icons:moon",
                                        width=16,
                                        color="var(--mantine-color-blue-3)",
                                    ),
                                    size="lg",
                                ),
                            ],
                            className="top-toolbar",
                        ),
                        width=12,
                    ),
                    className="pt-3",
                ),
                *sections,
                dbc.Modal(
                    [
                        dbc.ModalHeader(id="product-modal-title"),
                        dbc.ModalBody(id="product-modal-body"),
                        dbc.ModalFooter(
                            dbc.Button("Close", id="product-modal-close", color="secondary", outline=True)
                        ),
                    ],
                    id="product-modal",
                    is_open=False,
                    scrollable=True,
                    size="lg",
                ),
            ],
            fluid=True,
            className="dbc dmc app-shell",
        ),
        defaultColorScheme="auto",
    )


app = dash.Dash(
    __name__,
    title="Laundry Lookup",
    description="A Dash AG Grid app for comparing laundry detergent formulas.",
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
dmc.pre_render_color_scheme()
app.layout = build_layout


@callback(
    Output("laundry-grid", "rowData"),
    Output("laundry-grid", "columnDefs"),
    Output("sheet-summary", "children"),
    Input("laundry-tabs", "active_tab"),
)
def update_grid(active_tab: str) -> tuple[list[GridRow], list[ColumnDef], html.Div]:
    """Swap the AG Grid payload when the selected tab changes.

    Args:
        active_tab: The currently selected tab id from the Bootstrap tabs component.

    Returns:
        A tuple containing the new row data, new column definitions, and the
        updated summary component for the active sheet.
    """

    data = load_app_data()
    payload = data["payloads"].get(active_tab) or data["payloads"][data["default_tab"]]
    return payload["rowData"], payload["columnDefs"], build_sheet_summary(payload)


@callback(
    Output("product-modal", "is_open"),
    Output("product-modal-title", "children"),
    Output("product-modal-body", "children"),
    Input("laundry-grid", "cellClicked"),
    Input("product-modal-close", "n_clicks"),
    State("laundry-grid", "virtualRowData"),
    prevent_initial_call=True,
)
def toggle_product_modal(
    cell_clicked_data: ClickPayload | None,
    close_clicks: int | None,
    virtual_row_data: list[GridRow] | None,
) -> tuple[bool, Any, Any]:
    """Open or close the product detail modal in response to grid interaction.

    Args:
        cell_clicked_data: The Dash AG Grid click payload for the selected row.
        close_clicks: The modal close button click count, used only as a callback trigger.
        virtual_row_data: The visible row set from the grid, used as a fallback lookup.

    Returns:
        A tuple of ``(is_open, modal_title, modal_body)`` for the product detail modal.
    """

    del close_clicks

    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if trigger_id == "product-modal-close":
        return False, no_update, no_update

    if trigger_id != "laundry-grid" or not cell_clicked_data:
        raise PreventUpdate

    selected_row = cell_clicked_data.get("data")
    row_index = cell_clicked_data.get("rowIndex")

    if (
        selected_row is None
        and isinstance(row_index, int)
        and virtual_row_data
        and 0 <= row_index < len(virtual_row_data)
    ):
        selected_row = virtual_row_data[row_index]

    if not selected_row:
        raise PreventUpdate

    details = []
    for key, value in selected_row.items():
        if value in (None, ""):
            continue
        details.append(
            html.Div(
                [
                    html.Div(key, className="detail-term"),
                    html.Div(str(value), className="detail-value"),
                ],
                className="detail-row",
            )
        )

    return (
        True,
        selected_row.get("Product Name", "Product Details"),
        html.Div(details, className="detail-grid"),
    )


server = app.server


if __name__ == "__main__":
    app.run(debug=True)
