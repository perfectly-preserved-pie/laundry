# Laundry Lookup

A small Dash app for browsing and comparing laundry detergents, pretreaters, and boosters in one grid.

Data sourced by /u/KismaiAesthetics on Reddit.

# AI Disclosure
This project was created with the assistance of GPT-5.4-Codex.

## Run it

```bash
uv sync
uv run python app.py
```

Then open `http://127.0.0.1:8050`.

## Data

The app reads `laundry_sheet.xlsx` if it's present locally, or falls back to the linked Google Sheet export.


## Backend
The main logic is in `components.py`, which defines the layout and callbacks for the app.

## Frontend
The frontend is built using Dash and AG Grid. The main component is the `AgGrid` component, which displays the data in a sortable and filterable grid. The grid is configured with options for row animation, tooltip delay, and localized text for boolean values.

