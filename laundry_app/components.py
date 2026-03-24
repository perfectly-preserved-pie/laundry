"""Layout and presentational helpers for the laundry app."""

from __future__ import annotations

from typing import Any

import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import html
from dash_iconify import DashIconify

from laundry_app.config import (
    AG_GRID_CLASS_NAME,
    GITHUB_URL,
    REDDIT_ATTRIBUTION_URL,
    WORKBOOK_TITLE,
    WORKBOOK_URL,
)
from laundry_app.data import get_app_data
from laundry_app.types import AppData, GlossarySections, SheetPayload


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
                "A Dash AG Grid app for comparing laundry formulas across multiple products.",
                className="d-block mb-3",
            ),
            html.Div(
                [
                    dbc.Badge(f"{sheet_count} source sheets", className="metric-pill"),
                    dbc.Badge(f"{row_count} rows loaded", className="metric-pill"),
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
                            DashIconify(icon="simple-icons:googlesheets", width=18),
                            html.A("Source Sheet", href=WORKBOOK_URL, target="_blank", title=WORKBOOK_TITLE),
                        ],
                        className="title-link",
                    ),
                    html.Span(
                        [
                            DashIconify(icon="mdi:reddit", width=18),
                            html.A(
                                "Data compiled by /u/KismaiAesthetics",
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
        A Bootstrap card containing the relevant glossary entries, or ``None``
        when no glossary data is available.
    """

    if not glossary:
        return None

    sections = []
    for section, entries in glossary.items():
        sections.append(
            html.Div(
                [
                    html.Div(section, className="glossary-section-title"),
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
                ],
                className="glossary-section",
            )
        )

    return dbc.Card(
        [
            dbc.CardBody(
                html.Div(
                    [
                        html.H2("Column Key", className="h4 mb-2"),
                        html.P(
                            "Glossary terms are pulled from the spreadsheet's Key sheet.",
                            className="mb-3 grid-caption",
                        ),
                        html.Div(sections, className="glossary-sections"),
                    ]
                )
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

    return dbc.Alert(
        [
            html.H4("Workbook Load Failed", className="alert-heading"),
            html.P(
                "The app shell loaded, but the spreadsheet data could not be read. "
                "The title card links still point to the live source workbook."
            ),
            html.P(f"Error: {message}", className="mb-2"),
            html.Code("LAUNDRY_WORKBOOK_PATH=/path/to/laundry_sheet.xlsx"),
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
                            "Choose a sheet, use the floating filter row and column menus to narrow the grid, and click "
                            "a row to open the product detail modal.",
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
                                "animateRows": False,
                                "tooltipShowDelay": 0,
                            },
                            className=AG_GRID_CLASS_NAME,
                        ),
                    ]
                ),
                className="grid-card",
            )
        )

        sections.append(
            html.Div(
                build_glossary_card(default_payload["glossary"]),
                id="glossary-card-container",
            )
        )

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
