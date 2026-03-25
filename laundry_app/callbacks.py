"""Dash callback registration for the laundry app."""

from __future__ import annotations

from typing import Any

from dash import Dash, Input, Output, State, callback_context, html, no_update
from dash.exceptions import PreventUpdate

from laundry_app.components import build_sheet_summary
from laundry_app.data import load_app_data
from laundry_app.enrichment import lookup_product_enrichment
from laundry_app.types import ClickPayload, ColumnDef, GridRow

LABEL_OVERRIDES = {}


def update_grid(active_tab: str) -> tuple[list[GridRow], list[ColumnDef], html.Div]:
    """Swap the AG Grid payload when the selected tab changes.

    Args:
        active_tab: The currently selected tab id from the Bootstrap tabs component.

    Returns:
        A tuple containing the new row data, new column definitions, and the
        updated summary component.
    """

    data = load_app_data()
    payload = data["payloads"].get(active_tab) or data["payloads"][data["default_tab"]]
    return (
        payload["rowData"],
        payload["columnDefs"],
        build_sheet_summary(payload),
    )


def get_boolean_badge_label(value: Any) -> str | None:
    """Return a Yes/No label when the value should be displayed as a boolean badge."""

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"yes", "true"}:
            return "Yes"
        if normalized in {"no", "false"}:
            return "No"

    return None


def build_detail_value_node(value: Any) -> tuple[Any, bool]:
    """Create the rendered value node for the modal detail grid."""

    badge_label = get_boolean_badge_label(value)
    if badge_label is not None:
        badge_class = "detail-badge detail-badge-yes" if badge_label == "Yes" else "detail-badge detail-badge-no"
        return html.Span(badge_label, className=badge_class), True

    return html.Div(str(value), className="detail-value"), False


def build_detail_item(label: str, value: Any, *, wide: bool = False) -> html.Div:
    """Render a compact key/value item for the product detail modal."""

    value_node, is_boolean_style = build_detail_value_node(value)
    class_names = ["detail-item"]
    if wide:
        class_names.append("detail-item-wide")
    if is_boolean_style:
        class_names.append("detail-item-boolean")

    return html.Div(
        [
            html.Div(label, className="detail-term"),
            value_node,
        ],
        className=" ".join(class_names),
    )


def titleize_identifier(value: str | None) -> str:
    """Convert a machine-readable identifier into a display label."""

    if not value:
        return ""

    return LABEL_OVERRIDES.get(value, value.replace("_", " ").title())


def build_detail_section(title: str, body_children: list[Any], *, meta: str | None = None) -> html.Section:
    """Render a titled section inside the product detail modal."""

    header_children = [html.Div(title, className="detail-section-title")]
    if meta:
        header_children.append(html.Div(meta, className="detail-section-meta"))

    return html.Section(
        [
            html.Div(header_children, className="detail-section-header"),
            html.Div(body_children, className="detail-section-body"),
        ],
        className="detail-section",
    )


def build_detail_link(label: str, href: str) -> html.A:
    """Render a compact external link pill for an enrichment source."""

    return html.A(label, href=href, target="_blank", rel="noreferrer", className="detail-link")


def build_source_card(source: dict[str, Any]) -> html.Div:
    """Render a single official-source card."""

    chip_values = [
        titleize_identifier(source.get("source_family")),
        titleize_identifier(source.get("source_type")),
        titleize_identifier(source.get("source_form")),
        source.get("source_scent"),
    ]
    chips = [
        html.Span(value, className="detail-chip")
        for value in chip_values
        if value
    ]

    meta_values = [
        source.get("source_brand"),
        source.get("variant"),
        source.get("size_text"),
        source.get("load_count_text"),
        f"Disclosure {source['disclosure_date']}" if source.get("disclosure_date") else None,
        f"SDS rev. {source['sds_revision_date']}" if source.get("sds_revision_date") else None,
    ]
    meta_items = [html.Span(value, className="source-card-meta-item") for value in meta_values if value]

    links = []
    if source.get("resolved_url"):
        links.append(build_detail_link("Source", source["resolved_url"]))
    if source.get("ingredient_page_url") and source.get("ingredient_page_url") != source.get("resolved_url"):
        links.append(build_detail_link("Ingredients", source["ingredient_page_url"]))
    if source.get("sds_url"):
        links.append(build_detail_link("SDS", source["sds_url"]))

    children: list[Any] = [
        html.Div(
            [
                html.Div(source.get("source_product_name") or "Official source", className="source-card-title"),
                html.Div(chips, className="detail-chip-list") if chips else None,
            ],
            className="source-card-header",
        )
    ]

    if meta_items:
        children.append(html.Div(meta_items, className="source-card-meta"))
    if links:
        children.append(html.Div(links, className="detail-link-list"))
    if source.get("notes"):
        children.append(html.Div(source["notes"], className="detail-section-note"))

    return html.Div(children, className="source-card")


def build_ingredient_item(ingredient: dict[str, Any]) -> html.Div:
    """Render a single ingredient entry."""

    chips = []
    if ingredient.get("ingredient_group"):
        chips.append(html.Span(titleize_identifier(ingredient["ingredient_group"]), className="detail-chip"))

    meta_values = [
        f"Function: {ingredient['function']}" if ingredient.get("function") else None,
        f"CAS {ingredient['cas_number']}" if ingredient.get("cas_number") else None,
        (
            f"Designated list: {ingredient['designated_list_text']}"
            if ingredient.get("designated_list_text")
            else None
        ),
    ]

    return html.Div(
        [
            html.Div(
                [
                    html.Div(ingredient.get("ingredient_name_raw") or "Unnamed ingredient", className="ingredient-name"),
                    html.Div(chips, className="detail-chip-list") if chips else None,
                ],
                className="ingredient-header",
            ),
            html.Div(
                [
                    html.Span(value, className="ingredient-meta-item")
                    for value in meta_values
                    if value
                ],
                className="ingredient-meta",
            )
            if any(meta_values)
            else None,
        ],
        className="ingredient-item",
    )


def build_product_detail_body(
    selected_row: GridRow,
    product_enrichment: dict[str, list[dict[str, Any]]] | None = None,
    *,
    enrichment_loaded: bool = False,
) -> html.Div:
    """Create a denser, less noisy modal body for a selected product row."""

    detail_items = []
    notes_item: html.Div | None = None

    for key, value in selected_row.items():
        if value in (None, "") or key == "Product Name":
            continue

        if key == "Notes":
            notes_item = build_detail_item(key, value, wide=True)
            continue

        detail_items.append(build_detail_item(key, value))

    children: list[Any] = []
    workbook_section_children: list[Any] = []
    if detail_items:
        workbook_section_children.append(html.Div(detail_items, className="detail-grid"))
    if notes_item is not None:
        workbook_section_children.append(notes_item)
    if workbook_section_children:
        children.append(build_detail_section("Workbook Details", workbook_section_children))

    enrichment = product_enrichment or {"sources": [], "ingredients": []}
    sources = enrichment.get("sources", [])
    ingredients = enrichment.get("ingredients", [])

    if sources:
        children.append(
            build_detail_section(
                "Official Sources",
                [html.Div([build_source_card(source) for source in sources], className="source-card-grid")],
                meta=f"{len(sources)} source{'s' if len(sources) != 1 else ''}",
            )
        )
    elif enrichment_loaded:
        children.append(
            build_detail_section(
                "Official Sources",
                [html.Div("No official-source enrichment matched this product yet.", className="detail-empty")],
            )
        )

    if ingredients:
        children.append(
            build_detail_section(
                "Ingredients",
                [
                    html.Div(
                        html.Div(
                            [build_ingredient_item(ingredient) for ingredient in ingredients],
                            className="ingredient-list",
                        ),
                        className="ingredient-scroll-region",
                    )
                ],
                meta=f"{len(ingredients)} extracted",
            )
        )

    if not children:
        children.append(
            html.Div(
                "No additional details available.",
                className="detail-empty",
            )
        )

    return html.Div(children, className="product-detail-body")


def toggle_product_modal(
    cell_clicked_data: ClickPayload | None,
    close_clicks: int | None,
    virtual_row_data: list[GridRow] | None,
    active_tab: str | None,
) -> tuple[bool, Any, Any]:
    """Open or close the product detail modal in response to grid interaction.

    Args:
        cell_clicked_data: The Dash AG Grid click payload for the selected row.
        close_clicks: The modal close button click count, used only as a callback trigger.
        virtual_row_data: The visible row set from the grid, used as a fallback lookup.
        active_tab: The active tab id, used to resolve the workbook sheet for enrichment lookups.

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

    app_data = load_app_data()
    payloads = app_data["payloads"]
    default_tab = app_data["default_tab"]
    payload = payloads.get(active_tab or "") or payloads[default_tab]
    product_enrichment, enrichment_loaded = lookup_product_enrichment(payload["sheet_name"], selected_row)

    return (
        True,
        selected_row.get("Product Name", "Product Details"),
        build_product_detail_body(
            selected_row,
            product_enrichment,
            enrichment_loaded=enrichment_loaded,
        ),
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
        State("laundry-tabs", "active_tab"),
        prevent_initial_call=True,
    )(toggle_product_modal)
