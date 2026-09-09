"""Golden-path smoke checks across the storefront's real pages and flows."""

import json
import re

from playwright.sync_api import expect

import _common
from _common import BASE_URL, MOCKUP_ENABLE_TIMEOUT_MS, browser_page

# Below style.css's 800px breakpoint, Prints (and later Apparel/Coasters, issue #97) swaps the
# sidebar+grid picker for a dropdown + horizontal strip (issue #98).
MOBILE_VIEWPORT = {"width": 390, "height": 844}


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
        # directly, but its functional tests are removed for now (issue #88, restore via #89).
        assert nav.get_by_role("link", name="Apparel", exact=True).count() == 0
        # Coasters is deliberately not linked yet (issue #14) — same treatment as Apparel above.
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


def test_catalogue_sidebar_jumps_to_category_section():
    """Regression guard for issue #74: clicking a sidebar category button highlights it (and
    only it) and points at a real, matching section heading in the grid. Picks the last category
    from the live page rather than hardcoding a name, so it keeps working whatever categories the
    manifest actually has (ONBOARDING's no-hardcoded-data rule). Doesn't assert on scroll
    position/distance — the e2e fixture catalogue is deliberately tiny (issue #44) and its whole
    grid can fit without any scrolling at all, unlike the real ~218-photo catalogue."""
    with browser_page() as page:
        page.goto("/prints")
        buttons = page.locator(".cat-sidebar button[data-target]")
        count = buttons.count()
        assert count > 1, "need at least 2 categories to test jumping between them"

        last_button = buttons.nth(count - 1)
        category_name = last_button.get_attribute("data-category")
        target_id = last_button.get_attribute("data-target")
        heading = page.locator(f"#{target_id}")
        assert heading.count() == 1
        assert category_name in heading.inner_text()

        last_button.click()
        expect(last_button).to_have_class(re.compile(r"(^|\s)is-active(\s|$)"))
        active = page.locator(".cat-sidebar button.is-active")
        assert active.count() == 1, "only the clicked category should be active"


def test_mobile_picker_replaces_sidebar_and_filters_the_grid_by_category():
    """Regression guard for issue #98: below the 800px breakpoint the sidebar+grid from #74 is
    replaced by a category dropdown filtering the same catalogue-thumb elements the desktop
    grid renders (not a second copy), reflowed into a horizontal strip. Picks the last category
    from the live page rather than hardcoding a name (ONBOARDING's no-hardcoded-data rule)."""
    with browser_page(viewport=MOBILE_VIEWPORT) as page:
        page.goto("/prints")
        assert page.locator(".cat-sidebar").is_hidden()
        assert page.locator("#mobile-category-select").is_visible()

        options = page.locator("#mobile-category-select option")
        count = options.count()
        assert count > 1, "need at least 2 categories to test switching"
        last_slug = options.nth(count - 1).get_attribute("value")

        thumbs_in_category = page.locator(f'.catalogue-thumb[data-category="{last_slug}"]')
        thumbs_count = thumbs_in_category.count()
        assert thumbs_count > 0

        page.select_option("#mobile-category-select", last_slug)
        assert thumbs_in_category.first.is_visible()
        assert page.locator(".catalogue-thumb:visible").count() == thumbs_count


def test_mobile_picker_photo_and_size_selection_drive_the_real_mockup():
    """Regression guard for issue #98: the mobile strip's thumbnails are the same elements
    catalogue-picker.js/prints-mockup.js already wire up (clicking one still renders the wall
    mockup and enables Add to cart), and the mobile size <select> mirrors the real "size" radio
    group rather than holding separate state."""
    with browser_page(viewport=MOBILE_VIEWPORT) as page:
        page.goto("/prints")
        page.wait_for_selector("#add-to-cart-print:not([disabled])", timeout=MOCKUP_ENABLE_TIMEOUT_MS)

        thumb = page.locator(".catalogue-thumb:visible").last
        thumb_id = thumb.get_attribute("data-id")
        thumb.click()
        expect(page.locator("#wall-print")).to_have_attribute("src", re.compile(re.escape(thumb_id)))

        price_before = page.locator("#selected-price").inner_text()
        page.select_option("#mobile-size-select", "A0")
        assert page.locator("input[name='size'][value='A0']").is_checked()
        assert page.locator("#selected-price").inner_text() != price_before


def test_desktop_catalogue_grid_shows_every_category_not_just_the_first():
    """Regression guard for issue #104: applyFilter() in mobile-picker.js ran unconditionally on
    load, hiding every catalogue-thumb outside the mobile select's default category (whichever
    sorts first) — including on desktop, where the sidebar+grid design (#74) expects every
    category's photos visible at once. Confirmed live in production: 409 of 657 thumbnails were
    hidden. Uses the default (desktop) viewport, not MOBILE_VIEWPORT."""
    with browser_page() as page:
        page.goto("/prints")
        assert page.locator(".cat-sidebar").is_visible()
        total = page.locator(".catalogue-thumb").count()
        visible = page.locator(".catalogue-thumb:visible").count()
        assert visible == total, f"{total - visible} of {total} thumbnails hidden on desktop"


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
        page.wait_for_selector("#add-to-cart-print:not([disabled])", timeout=MOCKUP_ENABLE_TIMEOUT_MS)

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
        page.wait_for_selector("#add-to-cart-print:not([disabled])", timeout=MOCKUP_ENABLE_TIMEOUT_MS)

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


def test_prints_mockup_renders_and_enables_add_to_cart():
    """Regression guard: a strict CSP once silently broke the inline data-injection script,
    leaving PRINT_SIZES undefined and the add-to-cart button permanently disabled with no
    visible error. This exercises the real client-side render path, not just that the page
    returns 200."""
    with browser_page() as page:
        page.goto("/prints")
        # The button used to wait on a live image load to compute aspect ratio (first a
        # redundant full-resolution fetch, issue #30; then the already-visible thumbnail's own
        # load, which still wasn't enough under CI contention, issue #36) — both replaced by
        # #38's fix of baking width/height into manifest.json, so there's no network/image-load
        # dependency left at all. This wait is now just headroom for page load/JS execution.
        page.wait_for_selector("#add-to-cart-print:not([disabled])", timeout=MOCKUP_ENABLE_TIMEOUT_MS)
        assert page.locator("#selected-price").inner_text() != "—"
        assert page.locator("#wall-print").get_attribute("src")


def test_prints_mockup_size_fixed_at_a2_regardless_of_selected_size():
    """Regression guard for issue #25: rendering the mockup at the actually-selected size once
    looked disproportionate at the extremes (A0 read as roughly couch-sized against room.jpg,
    which it isn't). The mockup should always render at A2 dimensions; only price should change
    when a different size is picked."""
    with browser_page() as page:
        page.goto("/prints")
        page.wait_for_selector("#add-to-cart-print:not([disabled])", timeout=MOCKUP_ENABLE_TIMEOUT_MS)
        width_before = page.locator("#wall-print").evaluate("el => el.style.width")
        height_before = page.locator("#wall-print").evaluate("el => el.style.height")
        price_before = page.locator("#selected-price").inner_text()

        page.click("input[name='size'][value='A0']")
        page.wait_for_timeout(200)

        assert page.locator("#wall-print").evaluate("el => el.style.width") == width_before
        assert page.locator("#wall-print").evaluate("el => el.style.height") == height_before
        assert page.locator("#selected-price").inner_text() != price_before


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
    test_catalogue_sidebar_jumps_to_category_section,
    test_mobile_picker_replaces_sidebar_and_filters_the_grid_by_category,
    test_mobile_picker_photo_and_size_selection_drive_the_real_mockup,
    test_desktop_catalogue_grid_shows_every_category_not_just_the_first,
    test_prints_mockup_renders_and_enables_add_to_cart,
    test_prints_mockup_size_fixed_at_a2_regardless_of_selected_size,
    test_checkout_modal_opens_and_is_clickable,
    test_cart_add_and_checkout_flow,
    test_checkout_rejects_missing_or_malformed_mpesa_code,
    test_checkout_rejects_empty_cart,
    test_prints_quantity_adds_one_merged_line_and_cart_steppers_adjust_it,
    test_prints_price_line_updates_with_quantity,
]

if __name__ == "__main__":
    try:
        for t in TESTS:
            t()
            print(f"PASS {t.__name__}")
    finally:
        _common.shutdown()
