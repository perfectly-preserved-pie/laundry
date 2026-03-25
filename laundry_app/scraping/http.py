"""HTTP fetch helpers for source scrapers."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import httpx
from bs4 import BeautifulSoup


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass(frozen=True, slots=True)
class FetchedPage:
    """A fetched page plus a content hash for provenance."""

    url: str
    text: str
    raw_sha256: str


class Fetcher:
    """Thin wrapper around ``httpx.Client`` with shared defaults."""

    def __init__(self, *, timeout: float = 30.0, enable_browser: bool = False) -> None:
        self._client = httpx.Client(
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=timeout,
        )
        self._enable_browser = enable_browser
        self._playwright = None
        self._browser = None

    @property
    def browser_enabled(self) -> bool:
        """Return whether rendered-page fetching is enabled."""

        return self._enable_browser

    def fetch(self, url: str) -> FetchedPage:
        """Fetch a URL and return the resolved URL, text, and content hash."""

        response = self._client.get(url)
        response.raise_for_status()
        text = response.text
        return FetchedPage(
            url=str(response.url),
            text=text,
            raw_sha256=sha256(text.encode("utf-8")).hexdigest(),
        )

    def fetch_soup(self, url: str) -> tuple[FetchedPage, BeautifulSoup]:
        """Fetch a URL and build a BeautifulSoup tree from it."""

        page = self.fetch(url)
        return page, BeautifulSoup(page.text, "html.parser")

    def _ensure_browser(self):
        """Start a Playwright Chromium browser on first use."""

        if not self._enable_browser:
            raise RuntimeError(
                "Playwright rendering is disabled. Re-run the scraper with --use-playwright."
            )

        if self._browser is not None:
            return self._browser

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "Playwright is not installed. Run `uv sync --extra scraping-browser` first."
            ) from exc

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - environment dependent
            self._playwright.stop()
            self._playwright = None
            raise RuntimeError(
                "Playwright is installed, but Chromium is unavailable. Run `uv run playwright install chromium`."
            ) from exc

        return self._browser

    def fetch_rendered(self, url: str, *, wait_for: str | None = None) -> FetchedPage:
        """Fetch a URL with a headless browser and return the rendered HTML."""

        browser = self._ensure_browser()
        page = browser.new_page(user_agent=DEFAULT_USER_AGENT)
        try:
            page.goto(url, wait_until="networkidle", timeout=30_000)
            if wait_for:
                page.locator(wait_for).first.wait_for(timeout=30_000)
            text = page.content()
            return FetchedPage(
                url=page.url,
                text=text,
                raw_sha256=sha256(text.encode("utf-8")).hexdigest(),
            )
        finally:
            page.close()

    def fetch_rendered_soup(
        self,
        url: str,
        *,
        wait_for: str | None = None,
    ) -> tuple[FetchedPage, BeautifulSoup]:
        """Fetch a rendered page and build a BeautifulSoup tree from it."""

        page = self.fetch_rendered(url, wait_for=wait_for)
        return page, BeautifulSoup(page.text, "html.parser")

    def close(self) -> None:
        """Close the underlying client."""

        self._client.close()
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
