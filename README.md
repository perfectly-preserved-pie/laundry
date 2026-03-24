# Laundry Lookup

A small Dash app for browsing and comparing laundry detergents, pretreaters, and boosters in one grid.

Data sourced by /u/KismaiAesthetics on Reddit.

# AI Disclosure
This project was created with the assistance of GPT-5.4-Codex.

## Run it

### Docker (Registry)

```bash
docker pull strayingfromthepath/laundry:latest
docker run -p 8050:8050 strayingfromthepath/laundry:latest
```

### Docker (Building Locally)

```bash
docker build -t laundry-app .
docker run -p 8050:8050 laundry-app
```

### Git Clone and run:
```bash
git clone https://github.com/strayingfromthepath/laundry.git
cd laundry
uv sync
uv run python app.py
```

Then open `http://127.0.0.1:8050`.

## Data

The app reads `laundry_sheet.xlsx` if it's present locally, or falls back to the linked Google Sheet export.


## Backend
The main logic is in `components.py`, which defines the layout and callbacks for the app.

## Frontend
The frontend is built using Dash Bootstrap Components, Dash Mantine Components, and Dash AG Grid.
