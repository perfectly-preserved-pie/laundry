"""Scraping utilities and CLI for dataset enrichment."""

from __future__ import annotations

__all__ = ["run_pipeline"]


def run_pipeline(*args, **kwargs):
    """Proxy to the pipeline entrypoint without eager package imports."""

    from laundry_app.scraping.pipeline import run_pipeline as _run_pipeline

    return _run_pipeline(*args, **kwargs)
