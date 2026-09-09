"""Shared helpers for the Playwright E2E smoke suite.

Written against the Python `playwright` package (the `ds` conda env already has it installed
with browsers pre-cached), not `@playwright/test`. Specs are plain scripts (`TESTS = [...]`
list of functions, `assert`-based), run via:

    python app.py                        # in one terminal
    conda run -n ds python e2e/run.py    # in another

BASE_URL overrides the default local Flask dev server.

The Chromium process is launched once and shared across every test (issue #44) — each test
still gets its own isolated `browser.new_context()`/page, so there's no cookie/storage bleed
between tests, but launching a whole new browser process per test (16x in a single run) was
itself real CPU overhead competing with the single Flask dev-server process for cycles on a
constrained CI runner, on top of every test re-fetching all ~117 catalogue thumbnails from a
cold context. `run.py` (and this module's own `__main__` block) call `shutdown()` once after
the whole suite finishes.
"""

import os
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000").rstrip("/")

# How long a test waits for a mockup script to enable its add-to-cart button after selecting a
# photo (issue #77). This has nothing to do with image loading or network — enabling is a pure
# synchronous DOM update reacting to catalogue-picker.js's "photo-selected" event — but a CI
# runner under shared-tenant CPU contention can occasionally starve the page's own JS execution
# long enough to blow past a short budget even so. 5000ms flaked 3 times across 2 unrelated PRs
# in the same short window (including one PR that touched no JS/template code at all), always
# clean on an immediate re-run — a generous fixed budget is simpler and cheaper than chasing
# per-test timing.
MOCKUP_ENABLE_TIMEOUT_MS = 15000

_playwright = None
_browser = None


def _get_browser():
    global _playwright, _browser
    if _browser is None:
        _playwright = sync_playwright().start()
        # Headless Chromium throttles setTimeout/setInterval on a backgrounded/occluded page —
        # a real risk here since many contexts get created and closed in sequence within one
        # shared browser process (issue #44). These flags disable that throttling; the actual
        # setTimeout-based race this harness tripped over (issue #90) is fixed at the source in
        # catalogue-picker.js, but this is cheap, standard defense-in-depth for any other JS
        # timer a future page might add.
        _browser = _playwright.chromium.launch(args=[
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
        ])
    return _browser


def shutdown():
    """Close the shared browser/Playwright instance. Call once after the whole suite has run —
    not after each test."""
    global _playwright, _browser
    if _browser is not None:
        _browser.close()
        _browser = None
    if _playwright is not None:
        _playwright.stop()
        _playwright = None


@contextmanager
def browser_page(viewport=None):
    """`viewport=None` (the default) leaves Playwright's own default viewport in place —
    passing `viewport=None` straight through to `new_context()` would instead turn viewport
    emulation off entirely, which is a different thing. Pass an explicit {"width", "height"}
    to test a specific breakpoint, e.g. the sub-800px mobile picker (issue #98)."""
    kwargs = {"base_url": BASE_URL}
    if viewport is not None:
        kwargs["viewport"] = viewport
    context = _get_browser().new_context(**kwargs)
    try:
        yield context.new_page()
    finally:
        context.close()
