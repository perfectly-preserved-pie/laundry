"""Dash callback registration for the laundry app."""

from __future__ import annotations

from typing import Any

from dash import Dash, Input, Output, State, callback_context, html, no_update
from dash.exceptions import PreventUpdate

from laundry_app.components import build_sheet_summary
from laundry_app.data import load_app_data
from laundry_app.types import ClickPayload, ColumnDef, GridRow


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


def register_callbacks(app: Dash) -> None:
    """Register the app's callbacks on a Dash instance.

    Args:
        app: The Dash application receiving the callbacks.

    Returns:
        None.
    """

    app.callback(
        Output("laundry-grid", "rowData"),
        Output("laundry-grid", "columnDefs"),
        Output("sheet-summary", "children"),
        Input("laundry-tabs", "active_tab"),
    )(update_grid)

    app.callback(
        Output("product-modal", "is_open"),
        Output("product-modal-title", "children"),
        Output("product-modal-body", "children"),
        Input("laundry-grid", "cellClicked"),
        Input("product-modal-close", "n_clicks"),
        State("laundry-grid", "virtualRowData"),
        prevent_initial_call=True,
    )(toggle_product_modal)
