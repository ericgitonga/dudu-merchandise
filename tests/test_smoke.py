"""Unit tests for app.py's pure business logic — pricing, cart-item validation, and the order
email body. No server, no network, no DB — see e2e/test_smoke.py for the driven-browser flows."""

import pytest

import app as appmod


def test_resolve_secret_key_uses_provided_value():
    assert appmod._resolve_secret_key({"SECRET_KEY": "abc123"}) == "abc123"
    assert appmod._resolve_secret_key({"SECRET_KEY": "abc123", "VERCEL_ENV": "production"}) == "abc123"


def test_resolve_secret_key_fails_fast_in_production_without_one():
    with pytest.raises(RuntimeError):
        appmod._resolve_secret_key({"VERCEL_ENV": "production"})


def test_resolve_secret_key_falls_back_locally_without_one():
    assert appmod._resolve_secret_key({}) == "dev-only-insecure-key"
    assert appmod._resolve_secret_key({"VERCEL_ENV": "preview"}) == "dev-only-insecure-key"
    assert appmod._resolve_secret_key({"VERCEL_ENV": "development"}) == "dev-only-insecure-key"


def test_catalogue_validation_rejects_entries_missing_dimensions():
    with pytest.raises(RuntimeError):
        appmod._validate_catalogue([{"id": "999", "thumb": "x", "full": "y"}])
    with pytest.raises(RuntimeError):
        appmod._validate_catalogue([{"id": "999", "thumb": "x", "full": "y", "width": 100}])


def test_catalogue_validation_accepts_complete_entries():
    appmod._validate_catalogue([{"id": "999", "thumb": "x", "full": "y", "width": 100, "height": 50}])


def test_print_price_matches_catalogue():
    item = appmod.build_print_item({"photo_id": "001", "size": "a3"})
    assert item["price"] == appmod.PRINT_SIZES["A3"]["price"]
    assert item["size"] == "A3"
    assert item["qty"] == 1


def test_print_item_qty_is_parsed_and_clamped():
    assert appmod.build_print_item({"photo_id": "001", "size": "A4", "qty": "3"})["qty"] == 3
    assert appmod.build_print_item({"photo_id": "001", "size": "A4", "qty": "0"})["qty"] == 1
    assert appmod.build_print_item({"photo_id": "001", "size": "A4", "qty": "-5"})["qty"] == 1
    assert appmod.build_print_item({"photo_id": "001", "size": "A4", "qty": "not-a-number"})["qty"] == 1
    assert (
        appmod.build_print_item({"photo_id": "001", "size": "A4", "qty": str(appmod.MAX_ITEM_QTY + 50)})["qty"]
        == appmod.MAX_ITEM_QTY
    )


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


def test_cart_total_accounts_for_quantity():
    cart = [appmod.build_print_item({"photo_id": "001", "size": "A4", "qty": "3"})]
    assert appmod.cart_total(cart) == appmod.PRINT_SIZES["A4"]["price"] * 3


def test_cart_item_count_sums_quantities_not_lines():
    cart = [
        appmod.build_print_item({"photo_id": "001", "size": "A4", "qty": "3"}),
        appmod.build_apparel_item({"photo_id": "004", "age_group": "child", "shirt_colour": "Black", "qty": "2"}),
    ]
    assert appmod.cart_item_count(cart) == 5


def test_item_key_matches_same_print_selection_not_different_sizes():
    a4_one = appmod.build_print_item({"photo_id": "001", "size": "A4"})
    a4_two = appmod.build_print_item({"photo_id": "001", "size": "A4", "qty": "2"})
    a3 = appmod.build_print_item({"photo_id": "001", "size": "A3"})
    assert appmod._item_key(a4_one) == appmod._item_key(a4_two)
    assert appmod._item_key(a4_one) != appmod._item_key(a3)


def test_item_key_matches_same_apparel_selection_not_different_colours():
    black = appmod.build_apparel_item({"photo_id": "001", "age_group": "adult", "shirt_colour": "Black"})
    black_again = appmod.build_apparel_item({"photo_id": "001", "age_group": "adult", "shirt_colour": "Black"})
    white = appmod.build_apparel_item({"photo_id": "001", "age_group": "adult", "shirt_colour": "White"})
    assert appmod._item_key(black) == appmod._item_key(black_again)
    assert appmod._item_key(black) != appmod._item_key(white)


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


def test_mpesa_code_blob_pathname_is_derived_from_the_code():
    assert appmod._mpesa_code_blob_pathname("QGH7ABC123") == "used-mpesa-codes/QGH7ABC123.json"
    assert appmod._mpesa_code_blob_pathname("QGH7XYZ999") != appmod._mpesa_code_blob_pathname("QGH7ABC123")


def test_check_and_record_mpesa_code_skips_without_blob_token(monkeypatch):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    assert appmod.check_and_record_mpesa_code("QGH7XXXXXX") is False
