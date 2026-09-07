"""Unit tests for app.py's pure business logic — pricing, cart-item validation, and the order
email body. No server, no network, no DB — see e2e/test_smoke.py for the driven-browser flows."""

import pytest

import app as appmod


def test_print_price_matches_catalogue():
    item = appmod.build_print_item({"photo_id": "001", "size": "a3"})
    assert item["price"] == appmod.PRINT_SIZES["A3"]["price"]
    assert item["size"] == "A3"


def test_print_item_rejects_unknown_size():
    with pytest.raises(appmod.CartItemError):
        appmod.build_print_item({"photo_id": "001", "size": "A6"})


def test_print_item_rejects_unknown_photo():
    with pytest.raises(appmod.CartItemError):
        appmod.build_print_item({"photo_id": "not-a-real-id", "size": "A4"})


def test_apparel_price_matches_age_group():
    adult = appmod.build_apparel_item({"photo_id": "001", "age_group": "adult", "shirt_colour": "Black"})
    child = appmod.build_apparel_item({"photo_id": "001", "age_group": "child", "shirt_colour": "Black"})
    assert adult["price"] == appmod.APPAREL_PRICES["adult"]
    assert child["price"] == appmod.APPAREL_PRICES["child"]


def test_apparel_item_falls_back_to_a_known_colour():
    item = appmod.build_apparel_item({"photo_id": "001", "age_group": "adult", "shirt_colour": "Not A Real Colour"})
    assert item["shirt_colour"] in appmod.SHIRT_COLOURS


def test_cart_total_sums_item_prices():
    cart = [
        appmod.build_print_item({"photo_id": "001", "size": "A4"}),
        appmod.build_apparel_item({"photo_id": "004", "age_group": "child", "shirt_colour": "Black"}),
    ]
    assert appmod.cart_total(cart) == appmod.PRINT_SIZES["A4"]["price"] + appmod.APPAREL_PRICES["child"]


def test_order_email_includes_total_and_payment_instructions():
    cart = [appmod.build_print_item({"photo_id": "001", "size": "A2"})]
    customer = {
        "name": "Jane Doe", "contact": "+254700000000", "location": "Nairobi", "notes": "",
        "mpesa_code": "QGH7XXXXXX",
    }
    email = appmod.build_order_email(cart, customer)
    assert "Jane Doe" in email["subject"]
    assert f"KES {appmod.PRINT_SIZES['A2']['price']:,}" in email["text"]
    assert appmod.MPESA_NUMBER in email["text"]
    assert appmod.TURNAROUND_TEXT in email["text"]
    assert "QGH7XXXXXX" in email["text"]


def test_send_order_email_skips_without_api_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    cart = [appmod.build_print_item({"photo_id": "001", "size": "A4"})]
    customer = {
        "name": "Jane Doe", "contact": "jane@example.com", "location": "Nairobi", "notes": "",
        "mpesa_code": "QGH7XXXXXX",
    }
    assert appmod.send_order_email(cart, customer) == "skipped"
