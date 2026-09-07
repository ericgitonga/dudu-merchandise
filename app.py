"""
Flask app for the Dudu Merchandise storefront.

Two live sections — Prints and Apparel — built from a fixed, curated catalogue of insect
macro photographs (no upload flow; clients pick from what's on file). Coasters is scaffolded
as a nav entry + placeholder page only, not built out yet.

A client picks a photo and a size/variant on the Prints or Apparel page, sees a live preview
(a living-room wall mockup for Prints, a t-shirt mockup for Apparel — the latter folding in
merch-mockup's own compositing approach: a programmatically-drawn shirt silhouette, no
photographed garment template needed), and adds it to a cart. The cart is plain Flask session
state (a signed cookie) — no database. Checkout is a modal overlaid on the cart page: it
collects delivery details, shows the M-Pesa payment instructions, and on submit emails the
order (via Resend) to the site owner. Payment itself is manual/out-of-band — there is no
online payment gateway.
"""

import json
import os
import re
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf

BASE_DIR = Path(__file__).parent
CATALOGUE_MANIFEST = BASE_DIR / "static" / "images" / "catalogue" / "manifest.json"

app = Flask(__name__)
APP_VERSION = (BASE_DIR / "VERSION").read_text().strip()

# ── Secret key ───────────────────────────────────────────────────────────────
# Cookie-session cart contents (and CSRF tokens) are only as trustworthy as this key. On
# Vercel it's a project environment variable; locally, an ad-hoc dev key is fine.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"])


# ── Catalogue ────────────────────────────────────────────────────────────────

def _load_catalogue():
    data = json.loads(CATALOGUE_MANIFEST.read_text())
    return data["images"]


CATALOGUE = _load_catalogue()
CATALOGUE_IDS = {img["id"] for img in CATALOGUE}
CATALOGUE_BY_ID = {img["id"]: img for img in CATALOGUE}


# ── Pricing (KES) — the only place prices are defined; the client never gets to set one ──

PRINT_SIZES = {
    # w_mm/h_mm are ISO 216 A-series short/long edge, used to size the wall-mockup frame.
    "A4": {"price": 15_000, "w_mm": 210, "h_mm": 297},
    "A3": {"price": 25_000, "w_mm": 297, "h_mm": 420},
    "A2": {"price": 40_000, "w_mm": 420, "h_mm": 594},
    "A1": {"price": 70_000, "w_mm": 594, "h_mm": 841},
    "A0": {"price": 100_000, "w_mm": 841, "h_mm": 1189},
}

APPAREL_PRICES = {
    "adult": 3_000,
    "child": 2_800,
}

# Same 14-swatch palette as merch-mockup, so a shirt colour picked here reads the same way it
# would over there.
SHIRT_COLOURS = {
    "Black": "#000000",
    "White": "#FFFFFF",
    "Deep Navy": "#0F0F2D",
    "Slate Grey": "#707070",
    "Coral / Red-Orange": "#FF452B",
    "Mustard Yellow": "#E5A93B",
    "Deep Plum": "#7D1B4E",
    "Bright Orange": "#FFA11A",
    "Terracotta": "#A46B55",
    "Forest Green": "#38662B",
    "Crimson Red": "#CE1A1A",
    "Lime Green": "#4CD337",
    "Alabaster / Beige": "#EAE2C8",
    "Khaki / Tan": "#C1AD8F",
}

TURNAROUND_TEXT = "2 weeks from date of order"
MPESA_NUMBER = "+254 725 561 459"
MPESA_NAME = "Eric Mbaya"
SHIPPING_NOTE = "Shipping is extra, priced by delivery location — confirmed with you before dispatch."

ORDER_RECIPIENT = "gitonga@gmail.com"


# ── Cart validation — server recomputes every price, never trusts the client's ─────────────

class CartItemError(ValueError):
    """Raised when a submitted cart item fails validation."""


def _require_photo(form):
    photo_id = (form.get("photo_id") or "").strip()
    if photo_id not in CATALOGUE_IDS:
        raise CartItemError("Please pick a photo from the catalogue.")
    return photo_id


def build_print_item(form):
    photo_id = _require_photo(form)
    size = (form.get("size") or "").strip().upper()
    if size not in PRINT_SIZES:
        raise CartItemError(f"Unknown print size '{size}'.")
    return {
        "type": "print",
        "photo_id": photo_id,
        "size": size,
        "price": PRINT_SIZES[size]["price"],
    }


def build_apparel_item(form):
    photo_id = _require_photo(form)
    age_group = (form.get("age_group") or "").strip().lower()
    if age_group not in APPAREL_PRICES:
        raise CartItemError(f"Unknown size group '{age_group}'.")
    shirt_colour = (form.get("shirt_colour") or "").strip()
    if shirt_colour not in SHIRT_COLOURS:
        shirt_colour = next(iter(SHIRT_COLOURS))
    return {
        "type": "apparel",
        "photo_id": photo_id,
        "age_group": age_group,
        "shirt_colour": shirt_colour,
        "price": APPAREL_PRICES[age_group],
    }


def cart_total(cart):
    return sum(item["price"] for item in cart)


# ── Order email (Resend) ────────────────────────────────────────────────────

CONTACT_RE = re.compile(r"^\S{2,120}$")
MPESA_CODE_RE = re.compile(r"^[A-Z0-9]{6,15}$")


def _describe_item(item):
    photo = CATALOGUE_BY_ID.get(item["photo_id"])
    label = f"photo #{item['photo_id']}" if photo else f"photo #{item['photo_id']} (unknown)"
    if item["type"] == "print":
        return f"Print — {label} — {item['size']} — KES {item['price']:,}"
    return (
        f"Apparel (T-shirt) — {label} — {item['age_group'].title()} — "
        f"{item['shirt_colour']} — KES {item['price']:,}"
    )


def build_order_email(cart, customer):
    lines = [f"New order from {customer['name']} ({customer['contact']})", ""]
    lines.append(f"Delivery location: {customer['location']}")
    if customer.get("notes"):
        lines.append(f"Notes: {customer['notes']}")
    lines.append("")
    lines.append("Items:")
    for item in cart:
        lines.append(f"  - {_describe_item(item)}")
    lines.append("")
    lines.append(f"Total: KES {cart_total(cart):,}")
    lines.append("")
    lines.append(f"Payment: M-Pesa to {MPESA_NUMBER} ({MPESA_NAME})")
    lines.append(f"M-Pesa confirmation code (client-reported, not verified): {customer['mpesa_code']}")
    lines.append(f"Turnaround: {TURNAROUND_TEXT}")
    lines.append(SHIPPING_NOTE)

    subject = f"Dudu Merchandise order — {customer['name']} — {date.today():%d %b %Y}"
    return {"subject": subject, "text": "\n".join(lines)}


def send_order_email(cart, customer):
    """Returns 'sent', 'failed', or 'skipped' (mirrors career-transition/intake's convention) —
    email delivery never blocks the order confirmation shown to the client."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        app.logger.warning("RESEND_API_KEY not set — order email skipped")
        return "skipped"

    import resend

    resend.api_key = api_key
    from_email = os.environ.get("FROM_EMAIL", "onboarding@resend.dev")
    email = build_order_email(cart, customer)
    try:
        resend.Emails.send({
            "from": from_email,
            "to": [ORDER_RECIPIENT],
            "subject": email["subject"],
            "text": email["text"],
        })
        return "sent"
    except Exception:
        app.logger.warning("Resend order email failed", exc_info=True)
        return "failed"


# ── Security headers ─────────────────────────────────────────────────────────

@app.after_request
def _security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; img-src 'self'; connect-src 'self';"
    )
    return resp


@app.context_processor
def _inject_globals():
    return {
        "app_version": APP_VERSION,
        "cart_count": len(session.get("cart", [])),
        "csrf_token": generate_csrf,
    }


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/prints")
def prints():
    return render_template(
        "prints.html", catalogue=CATALOGUE, sizes=PRINT_SIZES,
    )


@app.route("/apparel")
def apparel():
    return render_template(
        "apparel.html", catalogue=CATALOGUE, prices=APPAREL_PRICES,
        shirt_colours=SHIRT_COLOURS,
    )


@app.route("/coasters")
def coasters():
    return render_template("coasters.html")


@app.route("/cart")
def cart_page():
    cart = session.get("cart", [])
    return render_template(
        "cart.html", cart=cart, total=cart_total(cart), catalogue_by_id=CATALOGUE_BY_ID,
        mpesa_number=MPESA_NUMBER, mpesa_name=MPESA_NAME,
        turnaround=TURNAROUND_TEXT, shipping_note=SHIPPING_NOTE,
    )


@app.route("/cart/add", methods=["POST"])
@limiter.limit("60 per minute")
def cart_add():
    item_type = request.form.get("type")
    try:
        if item_type == "print":
            item = build_print_item(request.form)
        elif item_type == "apparel":
            item = build_apparel_item(request.form)
        else:
            return jsonify({"ok": False, "error": "Unknown item type."}), 400
    except CartItemError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    cart = session.get("cart", [])
    cart.append(item)
    session["cart"] = cart
    return jsonify({"ok": True, "cart_count": len(cart)})


@app.route("/cart/remove/<int:index>", methods=["POST"])
def cart_remove(index):
    cart = session.get("cart", [])
    if 0 <= index < len(cart):
        cart.pop(index)
        session["cart"] = cart
    return jsonify({"ok": True, "cart_count": len(cart)})


@app.route("/api/checkout/submit", methods=["POST"])
@limiter.limit("10 per minute")
def checkout_submit():
    cart = session.get("cart", [])
    if not cart:
        return jsonify({"ok": False, "error": "Your cart is empty."}), 400

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    contact = (data.get("contact") or "").strip()
    location = (data.get("location") or "").strip()
    notes = (data.get("notes") or "").strip()
    mpesa_code = (data.get("mpesa_code") or "").strip().upper()

    if not name or not contact or not location or not mpesa_code:
        return jsonify({
            "ok": False,
            "error": "Name, contact, delivery location, and M-Pesa confirmation code are required.",
        }), 400
    if not CONTACT_RE.match(contact):
        return jsonify({"ok": False, "error": "Please enter a valid phone number or email."}), 400
    if not MPESA_CODE_RE.match(mpesa_code):
        return jsonify({"ok": False, "error": "Please enter a valid M-Pesa confirmation code."}), 400

    customer = {
        "name": name[:200], "contact": contact[:200], "location": location[:400],
        "notes": notes[:1000], "mpesa_code": mpesa_code[:20],
    }
    email_status = send_order_email(cart, customer)

    session["cart"] = []
    return jsonify({
        "ok": True,
        "email_status": email_status,
        "total": cart_total(cart),
        "mpesa_number": MPESA_NUMBER,
        "mpesa_name": MPESA_NAME,
        "turnaround": TURNAROUND_TEXT,
    })


@app.route("/_health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
