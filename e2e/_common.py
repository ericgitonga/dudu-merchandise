"""Shared helpers for the Playwright E2E smoke suite.

Written against the Python `playwright` package (the `ds` conda env already has it installed
with browsers pre-cached), not `@playwright/test`. Specs are plain scripts (`TESTS = [...]`
list of functions, `assert`-based), run via:

    python app.py                        # in one terminal
    conda run -n ds python e2e/run.py    # in another

BASE_URL overrides the default local Flask dev server.
"""

import os
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000").rstrip("/")


@contextmanager
def browser_page():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(base_url=BASE_URL)
            yield page
        finally:
            browser.close()
