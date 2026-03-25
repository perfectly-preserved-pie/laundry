"""Module entrypoint for ``python -m laundry_app.scraping``."""

from __future__ import annotations

from laundry_app.scraping.pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())
