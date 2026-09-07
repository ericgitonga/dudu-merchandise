"""Golden-path smoke checks across the storefront's real pages and flows."""

import json
import re

from playwright.sync_api import expect

from _common import BASE_URL, browser_page


def _csrf_token(page):
    match = re.search(r'name="csrf-token" content="([^"]+)"', page.content())
    assert match, "csrf-token meta tag not found on page"
    return match.group(1)


def test_index_loads_with_nav_links():
    with browser_page() as page:
        resp = page.goto("/")
        assert resp.status == 200
        nav = page.locator(".site-header nav")
        assert nav.get_by_role("link", name="Prints", exact=True).is_visible()
        # Apparel is deliberately not linked yet (issue #18) — its route stays reachable
        # directly, covered by test_apparel_page_lists_catalogue_and_colours below.
        assert nav.get_by_role("link", name="Apparel", exact=True).count() == 0
        # Coasters is deliberately not linked yet (issue #14) — its route stays reachable
        # directly, covered by test_coasters_page_is_a_placeholder below.
        assert nav.get_by_role("link", name="Coasters", exact=True).count() == 0


def test_no_page_links_to_hidden_apparel():
    """Regression guard: the nav and home-page links were hidden for issue #18, but a stray
    link survived on the empty-cart message and on the Coasters placeholder page (issue #26) —
    caught only by manual inspection after both had shipped. Sweep every real page for any
    link pointing at /apparel, not just the nav."""
    with browser_page() as page:
        for path in ["/", "/prints", "/coasters", "/cart"]:
            page.goto(path)
            assert page.locator('a[href="/apparel"]').count() == 0, f"{path} still links to /apparel"


def test_health_endpoint():
    with browser_page() as page:
        resp = page.request.get(f"{BASE_URL}/_health")
        assert resp.status == 200
        assert resp.json() == {"status": "ok"}


def test_prints_page_lists_catalogue_and_sizes():
    with browser_page() as page:
        resp = page.goto("/prints")
        assert resp.status == 200
        assert page.locator(".catalogue-thumb").count() > 0
        assert page.locator('input[name="size"]').count() == 5  # A4..A0


def test_apparel_page_lists_catalogue_and_colours():
    with browser_page() as page:
        resp = page.goto("/apparel")
        assert resp.status == 200
        assert page.locator(".catalogue-thumb").count() > 0
        assert page.locator(".shirt-swatch").count() == 14
        assert page.locator('input[name="age_group"]').count() == 2


def test_coasters_page_is_a_placeholder():
    with browser_page() as page:
        resp = page.goto("/coasters")
        assert resp.status == 200
        assert "coming soon" in page.content().lower()


def test_cart_add_and_checkout_flow():
    with browser_page() as page:
        page.goto("/prints")
        token = _csrf_token(page)

        add_resp = page.request.post(
            f"{BASE_URL}/cart/add",
            headers={"X-CSRFToken": token},
            form={"type": "print", "photo_id": "001", "size": "A4"},
        )
        assert add_resp.status == 200
        assert add_resp.json()["ok"] is True

        cart_resp = page.goto("/cart")
        assert cart_resp.status == 200
        assert "photo #001" in page.content()
        assert "15,000" in page.content()

        checkout_resp = page.request.post(
            f"{BASE_URL}/api/checkout/submit",
            headers={"X-CSRFToken": token, "Content-Type": "application/json"},
            data=(
                '{"name": "Test Buyer", "contact": "test@example.com", "location": "Nairobi", '
                '"mpesa_code": "QGH7XXXXXX"}'
            ),
        )
        assert checkout_resp.status == 200
        body = checkout_resp.json()
        assert body["ok"] is True
        # No RESEND_API_KEY in CI — email delivery is skipped, not attempted.
        assert body["email_status"] == "skipped"

        # Cart is cleared after a successful checkout submission.
        page.goto("/cart")
        assert "Your cart is empty" in page.content()


def test_prints_quantity_adds_one_merged_line_and_cart_steppers_adjust_it():
    """Regression guard for issue #32: picking a quantity >1 in the Prints selection pane adds
    that many as a single cart line (not duplicate lines), and the cart's own +/- buttons adjust
    that line's quantity and total in place, removing it once decremented to zero."""
    with browser_page() as page:
        page.goto("/prints")
        page.wait_for_selector("#add-to-cart-print:not([disabled])", timeout=20000)

        sizes = json.loads(page.locator("#print-sizes-data").inner_text())
        checked_size = page.locator('input[name="size"]:checked').get_attribute("value")
        unit_price = sizes[checked_size]["price"]

        page.click('.qty-stepper .qty-btn[data-step="1"]')
        page.click('.qty-stepper .qty-btn[data-step="1"]')
        assert page.locator("#selected-qty").input_value() == "3"

        page.click("#add-to-cart-print")
        # wait_for_function isn't usable here: this app's own CSP forbids 'unsafe-eval',
        # same class of restriction test_prints_mockup_renders_and_enables_add_to_cart guards
        # against for the inline data-injection script. expect() polls without eval.
        expect(page.locator("#cart-badge")).to_have_text("3")
        # Quantity resets so the next pick doesn't inherit the last one.
        assert page.locator("#selected-qty").input_value() == "1"

        page.goto("/cart")
        assert page.locator(".cart-item").count() == 1, "qty>1 should merge into one line, not duplicate rows"
        assert page.locator(".cart-qty-value").inner_text() == "3"
        assert f"{unit_price * 3:,}" in page.content()

        for _ in range(3):
            with page.expect_navigation():
                page.click(".cart-qty-btn[data-delta='-1']")
        assert "Your cart is empty" in page.content()


def test_prints_price_line_updates_with_quantity():
    """Regression guard for issue #34: the price line only ever reacted to the size radios, not
    the quantity stepper, so picking qty 2 of a KES 70,000 print still showed "KES 70,000" with
    no hint that's the per-unit price, not the KES 140,000 total about to be added."""
    with browser_page() as page:
        page.goto("/prints")
        page.wait_for_selector("#add-to-cart-print:not([disabled])", timeout=20000)

        sizes = json.loads(page.locator("#print-sizes-data").inner_text())
        checked_size = page.locator('input[name="size"]:checked').get_attribute("value")
        unit_price = sizes[checked_size]["price"]

        assert page.locator("#selected-price").inner_text() == f"KES {unit_price:,}"

        page.click('.qty-stepper .qty-btn[data-step="1"]')
        expect(page.locator("#selected-price")).to_have_text(
            f"KES {unit_price:,} each — KES {unit_price * 2:,} total"
        )

        page.click("#add-to-cart-print")
        expect(page.locator("#cart-badge")).to_have_text("2")
        # Quantity (and the price line with it) resets after a successful add.
        assert page.locator("#selected-price").inner_text() == f"KES {unit_price:,}"


def test_apparel_price_line_updates_with_quantity():
    """Same fix as test_prints_price_line_updates_with_quantity, for issue #34."""
    with browser_page() as page:
        page.goto("/apparel")
        page.wait_for_selector("#add-to-cart-apparel:not([disabled])", timeout=20000)

        prices = json.loads(page.locator("#apparel-prices-data").inner_text())
        checked_age = page.locator('input[name="age_group"]:checked').get_attribute("value")
        unit_price = prices[checked_age]

        assert page.locator("#selected-price").inner_text() == f"KES {unit_price:,}"

        page.click('.qty-stepper .qty-btn[data-step="1"]')
        expect(page.locator("#selected-price")).to_have_text(
            f"KES {unit_price:,} each — KES {unit_price * 2:,} total"
        )


def test_prints_mockup_renders_and_enables_add_to_cart():
    """Regression guard: a strict CSP once silently broke the inline data-injection script,
    leaving PRINT_SIZES undefined and the add-to-cart button permanently disabled with no
    visible error. This exercises the real client-side render path, not just that the page
    returns 200."""
    with browser_page() as page:
        page.goto("/prints")
        # Longer timeout than other waits in this suite, kept as a generous ceiling: the button
        # used to also wait on a redundant full-resolution image fetch (issue #30), which
        # competed with the wall-mockup background photo for the dev server's attention and
        # occasionally blew a 20s budget in CI. Fixed by reading aspect ratio off the
        # already-loaded thumbnail instead — this wait is no longer on that network path, but
        # the generous budget costs nothing and guards against future regressions.
        page.wait_for_selector("#add-to-cart-print:not([disabled])", timeout=20000)
        assert page.locator("#selected-price").inner_text() != "—"
        assert page.locator("#wall-print").get_attribute("src")


def test_prints_mockup_size_fixed_at_a2_regardless_of_selected_size():
    """Regression guard for issue #25: rendering the mockup at the actually-selected size once
    looked disproportionate at the extremes (A0 read as roughly couch-sized against room.jpg,
    which it isn't). The mockup should always render at A2 dimensions; only price should change
    when a different size is picked."""
    with browser_page() as page:
        page.goto("/prints")
        page.wait_for_selector("#add-to-cart-print:not([disabled])", timeout=20000)
        width_before = page.locator("#wall-print").evaluate("el => el.style.width")
        height_before = page.locator("#wall-print").evaluate("el => el.style.height")
        price_before = page.locator("#selected-price").inner_text()

        page.click("input[name='size'][value='A0']")
        page.wait_for_timeout(200)

        assert page.locator("#wall-print").evaluate("el => el.style.width") == width_before
        assert page.locator("#wall-print").evaluate("el => el.style.height") == height_before
        assert page.locator("#selected-price").inner_text() != price_before


def test_apparel_mockup_renders_and_enables_add_to_cart():
    with browser_page() as page:
        page.goto("/apparel")
        # Same generous budget as the Prints mockup test, for the same reason (issue #36): a
        # 5000ms timeout here occasionally blew under CI's runner variance even after #30 removed
        # the actual network dependency (both mockup scripts read aspect ratio off the
        # already-loaded thumbnail rather than re-fetching the full-resolution image) — the
        # catalogue grid's own thumbnails still have to load somewhere, and 5s wasn't a
        # meaningful measurement of that, just an unwidened leftover from before #30.
        page.wait_for_selector("#add-to-cart-apparel:not([disabled])", timeout=20000)
        assert page.locator("#selected-price").inner_text() != "—"
        assert page.locator("#shirt-design").get_attribute("href")


def test_checkout_modal_opens_and_is_clickable():
    """Regression guard: `.modal-overlay { display: flex }` once overrode the browser's
    default `[hidden]` styling, so the modal stayed interactive (and blocked clicks on
    whatever was behind it) even while `hidden` was set."""
    with browser_page() as page:
        page.goto("/prints")
        token = _csrf_token(page)
        page.request.post(
            f"{BASE_URL}/cart/add",
            headers={"X-CSRFToken": token},
            form={"type": "print", "photo_id": "001", "size": "A4"},
        )
        page.goto("/cart")
        assert page.locator("#checkout-modal").is_hidden()
        page.click("#open-checkout")
        page.wait_for_selector("#checkout-modal:not([hidden])")
        page.click("#close-checkout")
        assert page.locator("#checkout-modal").is_hidden()


def test_checkout_rejects_missing_or_malformed_mpesa_code():
    with browser_page() as page:
        page.goto("/prints")
        token = _csrf_token(page)
        page.request.post(
            f"{BASE_URL}/cart/add",
            headers={"X-CSRFToken": token},
            form={"type": "print", "photo_id": "001", "size": "A4"},
        )

        missing_resp = page.request.post(
            f"{BASE_URL}/api/checkout/submit",
            headers={"X-CSRFToken": token, "Content-Type": "application/json"},
            data='{"name": "Test Buyer", "contact": "test@example.com", "location": "Nairobi"}',
        )
        assert missing_resp.status == 400
        assert missing_resp.json()["ok"] is False

        malformed_resp = page.request.post(
            f"{BASE_URL}/api/checkout/submit",
            headers={"X-CSRFToken": token, "Content-Type": "application/json"},
            data=(
                '{"name": "Test Buyer", "contact": "test@example.com", "location": "Nairobi", '
                '"mpesa_code": "??"}'
            ),
        )
        assert malformed_resp.status == 400
        assert malformed_resp.json()["ok"] is False


def test_checkout_rejects_empty_cart():
    with browser_page() as page:
        page.goto("/")
        token = _csrf_token(page)
        resp = page.request.post(
            f"{BASE_URL}/api/checkout/submit",
            headers={"X-CSRFToken": token, "Content-Type": "application/json"},
            data='{"name": "Test Buyer", "contact": "test@example.com", "location": "Nairobi"}',
        )
        assert resp.status == 400
        assert resp.json()["ok"] is False


TESTS = [
    test_index_loads_with_nav_links,
    test_no_page_links_to_hidden_apparel,
    test_health_endpoint,
    test_prints_page_lists_catalogue_and_sizes,
    test_apparel_page_lists_catalogue_and_colours,
    test_coasters_page_is_a_placeholder,
    test_prints_mockup_renders_and_enables_add_to_cart,
    test_prints_mockup_size_fixed_at_a2_regardless_of_selected_size,
    test_apparel_mockup_renders_and_enables_add_to_cart,
    test_checkout_modal_opens_and_is_clickable,
    test_cart_add_and_checkout_flow,
    test_checkout_rejects_missing_or_malformed_mpesa_code,
    test_checkout_rejects_empty_cart,
    test_prints_quantity_adds_one_merged_line_and_cart_steppers_adjust_it,
    test_prints_price_line_updates_with_quantity,
    test_apparel_price_line_updates_with_quantity,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
        print(f"PASS {t.__name__}")
