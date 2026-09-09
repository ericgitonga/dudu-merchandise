"""Unit tests for app.py's pure business logic — pricing, cart-item validation, and the order
email body. No server, no network, no DB — see e2e/test_smoke.py for the driven-browser flows."""

import pytest

import app as appmod

# Real catalogue ids — these tests only care that an id exists in the catalogue, not which photo
# it is, so pick three distinct real ones rather than hardcoding a filename that can be renamed
# (issue #82 renumbered every catalogue photo, which is what broke this the first time).
PHOTO_ID, PHOTO_ID_2, PHOTO_ID_3 = sorted(appmod.CATALOGUE_IDS)[:3]


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
        appmod._validate_catalogue([{"id": "999", "thumb": "x", "thumb_sm": "z", "full": "y", "category": "Beetles"}])
    with pytest.raises(RuntimeError):
        appmod._validate_catalogue(
            [{"id": "999", "thumb": "x", "thumb_sm": "z", "full": "y", "width": 100, "category": "Beetles"}]
        )


def test_catalogue_validation_rejects_entries_missing_thumb_sm():
    with pytest.raises(RuntimeError):
        appmod._validate_catalogue(
            [{"id": "999", "thumb": "x", "full": "y", "width": 100, "height": 50, "category": "Beetles"}]
        )


def test_catalogue_validation_rejects_entries_missing_or_unknown_category():
    with pytest.raises(RuntimeError):
        appmod._validate_catalogue(
            [{"id": "999", "thumb": "x", "thumb_sm": "z", "full": "y", "width": 100, "height": 50}]
        )
    with pytest.raises(RuntimeError):
        appmod._validate_catalogue(
            [{
                "id": "999", "thumb": "x", "thumb_sm": "z", "full": "y",
                "width": 100, "height": 50, "category": "Not A Real Category",
            }]
        )


def test_catalogue_validation_accepts_complete_entries():
    appmod._validate_catalogue(
        [{
            "id": "999", "thumb": "x", "thumb_sm": "z", "full": "y",
            "width": 100, "height": 50, "category": "Beetles",
        }]
    )


def test_category_slug_is_lowercase_and_hyphenated():
    assert appmod._category_slug("True Bugs") == "true-bugs"
    assert appmod._category_slug("Flies") == "flies"


def test_group_catalogue_by_category_sorts_largest_group_first():
    images = [
        {"id": "1", "category": "Wasps"},
        {"id": "2", "category": "Flies"},
        {"id": "3", "category": "Flies"},
        {"id": "4", "category": "Flies"},
        {"id": "5", "category": "Beetles"},
        {"id": "6", "category": "Beetles"},
    ]
    groups = appmod.group_catalogue_by_category(images)
    assert [g["category"] for g in groups] == ["Flies", "Beetles", "Wasps"]
    assert [g["count"] for g in groups] == [3, 2, 1]


def test_group_catalogue_by_category_breaks_ties_alphabetically():
    images = [{"id": "1", "category": "Wasps"}, {"id": "2", "category": "Ants"}]
    groups = appmod.group_catalogue_by_category(images)
    assert [g["category"] for g in groups] == ["Ants", "Wasps"]


def test_group_catalogue_by_category_preserves_manifest_order_within_a_group():
    images = [
        {"id": "3", "category": "Flies"},
        {"id": "1", "category": "Flies"},
        {"id": "2", "category": "Flies"},
    ]
    groups = appmod.group_catalogue_by_category(images)
    assert [img["id"] for img in groups[0]["images"]] == ["3", "1", "2"]


def test_group_catalogue_by_category_puts_other_last_regardless_of_count():
    images = [
        {"id": "1", "category": "Other"},
        {"id": "2", "category": "Other"},
        {"id": "3", "category": "Other"},
        {"id": "4", "category": "Wasps"},
    ]
    groups = appmod.group_catalogue_by_category(images)
    assert [g["category"] for g in groups] == ["Wasps", "Other"]


def test_group_catalogue_by_category_slug_matches_category_slug():
    groups = appmod.group_catalogue_by_category([{"id": "1", "category": "True Bugs"}])
    assert groups[0]["slug"] == appmod._category_slug("True Bugs")


def test_print_price_matches_catalogue():
    item = appmod.build_print_item({"photo_id": PHOTO_ID, "size": "a3"})
    assert item["price"] == appmod.PRINT_SIZES["A3"]["price"]
    assert item["size"] == "A3"
    assert item["qty"] == 1


def test_print_item_qty_is_parsed_and_clamped():
    assert appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A4", "qty": "3"})["qty"] == 3
    assert appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A4", "qty": "0"})["qty"] == 1
    assert appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A4", "qty": "-5"})["qty"] == 1
    assert appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A4", "qty": "not-a-number"})["qty"] == 1
    assert (
        appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A4", "qty": str(appmod.MAX_ITEM_QTY + 50)})["qty"]
        == appmod.MAX_ITEM_QTY
    )


def test_print_item_rejects_unknown_size():
    with pytest.raises(appmod.CartItemError):
        appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A6"})


def test_print_item_rejects_unknown_photo():
    with pytest.raises(appmod.CartItemError):
        appmod.build_print_item({"photo_id": "not-a-real-id", "size": "A4"})


def test_cart_total_sums_item_prices():
    cart = [
        appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A4"}),
        appmod.build_apparel_item({"photo_id": PHOTO_ID_2, "age_group": "child", "shirt_colour": "Black"}),
    ]
    assert appmod.cart_total(cart) == appmod.PRINT_SIZES["A4"]["price"] + appmod.APPAREL_PRICES["child"]


def test_cart_total_accounts_for_quantity():
    cart = [appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A4", "qty": "3"})]
    assert appmod.cart_total(cart) == appmod.PRINT_SIZES["A4"]["price"] * 3


def test_revalidate_cart_prices_corrects_a_tampered_price():
    item = appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A4"})
    item["price"] = 1  # simulates a forged session cookie (issue #47) setting an arbitrary price
    cart = [item]
    appmod.revalidate_cart_prices(cart)
    assert cart[0]["price"] == appmod.PRINT_SIZES["A4"]["price"]


def test_revalidate_cart_prices_drops_items_with_invalid_size_or_age_group():
    valid_item = appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A4"})
    tampered_size = appmod.build_print_item({"photo_id": PHOTO_ID_2, "size": "A3"})
    tampered_size["size"] = "NOT-A-REAL-SIZE"
    tampered_age = appmod.build_apparel_item({"photo_id": PHOTO_ID_3, "age_group": "adult", "shirt_colour": "Black"})
    tampered_age["age_group"] = "not-a-real-age-group"
    cart = [valid_item, tampered_size, tampered_age]
    appmod.revalidate_cart_prices(cart)
    assert cart == [valid_item]


def test_cart_item_count_sums_quantities_not_lines():
    cart = [
        appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A4", "qty": "3"}),
        appmod.build_apparel_item({"photo_id": PHOTO_ID_2, "age_group": "child", "shirt_colour": "Black", "qty": "2"}),
    ]
    assert appmod.cart_item_count(cart) == 5


def test_item_key_matches_same_print_selection_not_different_sizes():
    a4_one = appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A4"})
    a4_two = appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A4", "qty": "2"})
    a3 = appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A3"})
    assert appmod._item_key(a4_one) == appmod._item_key(a4_two)
    assert appmod._item_key(a4_one) != appmod._item_key(a3)


def test_order_email_includes_total_and_payment_instructions():
    cart = [appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A2"})]
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


def test_strip_control_chars_removes_newlines_and_null_bytes():
    assert appmod.strip_control_chars("Jane\r\nBcc: attacker@evil.com") == "JaneBcc: attacker@evil.com"
    assert appmod.strip_control_chars("Nairobi\x00\x1b") == "Nairobi"
    assert appmod.strip_control_chars("ordinary text, no control chars") == "ordinary text, no control chars"


def test_neutralize_formula_injection_prefixes_a_leading_quote():
    assert appmod.neutralize_formula_injection("=cmd|'/c calc'!A1") == "'=cmd|'/c calc'!A1"
    assert appmod.neutralize_formula_injection("+254712345678") == "'+254712345678"
    assert appmod.neutralize_formula_injection("-1+1") == "'-1+1"
    assert appmod.neutralize_formula_injection("@SUM(A1)") == "'@SUM(A1)"
    assert appmod.neutralize_formula_injection("Jane Doe") == "Jane Doe"
    assert appmod.neutralize_formula_injection("") == ""


def test_sanitize_customer_field_strips_and_neutralizes_together():
    assert appmod.sanitize_customer_field("=cmd\r\n") == "'=cmd"


def test_send_order_email_skips_without_api_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    cart = [appmod.build_print_item({"photo_id": PHOTO_ID, "size": "A4"})]
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
