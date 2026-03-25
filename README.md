# Laundry Lookup

[![Build and Publish Image](https://github.com/perfectly-preserved-pie/laundry/actions/workflows/build_and_push.yml/badge.svg)](https://github.com/perfectly-preserved-pie/laundry/actions/workflows/build_and_push.yml)

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

## Scraping Enrichment

The repo now includes a first-pass enrichment pipeline for official disclosure and product pages.

Run the full scrape:

```bash
uv run python -m laundry_app.scraping
```

Run a subset of source families:

```bash
uv run python -m laundry_app.scraping --family wholefoods --family sprouts --family clorox
```

List available source families:

```bash
uv run python -m laundry_app.scraping --list-families
```

By default the pipeline writes CSV sidecar tables to `data/enrichment/`:

- `product_sources.csv`
- `ingredients_long.csv`
- `unmatched_products.csv`
- `scrape_errors.csv`
- `summary.json`

Current source-family coverage includes:

- Church & Dwight / OxiClean disclosure pages
- Whole Foods Market disclosure pages
- Sprouts California disclosure pages
- ECOS product pages with embedded ingredient tables
- Dirty Labs product pages
- Dropps disclosure landing pages
- Tide official product pages with SmartLabel source links
- Clorox official product pages with Label Insight / SmartLabel ingredient pages

This is intentionally a sidecar pipeline, not an app dependency. It is meant to generate enrichment tables you can join back to the workbook dataset over time.

When those CSVs are present, the product detail modal will surface official source links and ingredient snippets directly in the app.

### Playwright for JS-only Pages

Use Playwright selectively, not as the default scrape path. It is most useful for:

- Tide SmartLabel pages on `smartlabel.pg.com`
- Dropps disclosure pages whose ingredient tables are client-rendered

Install the optional browser tooling:

```bash
uv sync --extra scraping-browser
uv run playwright install chromium
```

Then run the scraper with rendered-page support:

```bash
uv run python -m laundry_app.scraping --use-playwright
```

Everything else in the pipeline still works over plain HTTP, so this stays an opt-in path instead of slowing down the whole scrape.


## Backend
The main logic is in `components.py`, which defines the layout and callbacks for the app.

## Frontend
The frontend is built using Dash Bootstrap Components, Dash Mantine Components, and Dash AG Grid.
