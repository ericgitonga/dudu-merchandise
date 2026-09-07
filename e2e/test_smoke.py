"""Golden-path smoke checks across the storefront's real pages and flows."""

import re

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


def test_prints_mockup_renders_and_enables_add_to_cart():
    """Regression guard: a strict CSP once silently broke the inline data-injection script,
    leaving PRINT_SIZES undefined and the add-to-cart button permanently disabled with no
    visible error. This exercises the real client-side render path, not just that the page
    returns 200."""
    with browser_page() as page:
        page.goto("/prints")
        page.wait_for_selector("#add-to-cart-print:not([disabled])", timeout=5000)
        assert page.locator("#selected-price").inner_text() != "—"
        assert page.locator("#wall-print").get_attribute("src")


def test_apparel_mockup_renders_and_enables_add_to_cart():
    with browser_page() as page:
        page.goto("/apparel")
        page.wait_for_selector("#add-to-cart-apparel:not([disabled])", timeout=5000)
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
    test_health_endpoint,
    test_prints_page_lists_catalogue_and_sizes,
    test_apparel_page_lists_catalogue_and_colours,
    test_coasters_page_is_a_placeholder,
    test_prints_mockup_renders_and_enables_add_to_cart,
    test_apparel_mockup_renders_and_enables_add_to_cart,
    test_checkout_modal_opens_and_is_clickable,
    test_cart_add_and_checkout_flow,
    test_checkout_rejects_missing_or_malformed_mpesa_code,
    test_checkout_rejects_empty_cart,
]

if __name__ == "__main__":
    for t in TESTS:
        t()
        print(f"PASS {t.__name__}")
