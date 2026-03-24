"""Application entrypoint for the laundry grid Dash app."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

from laundry_app.callbacks import register_callbacks
from laundry_app.components import build_layout

app = dash.Dash(
    __name__,
    title="Laundry Lookup",
    description="A Dash AG Grid app for comparing laundry detergent formulas.",
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    external_scripts=[
        {
            "src": "https://plausible.automateordie.io/js/pa-ju6FKAd5xzT9Ac6UE0BMH.js",
            "async": "async",
        }
    ],
    suppress_callback_exceptions=True,
)
dmc.pre_render_color_scheme()
app.layout = build_layout

register_callbacks(app)

server = app.server


if __name__ == "__main__":
    app.run(debug=True)
