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
from datetime import date, datetime
from pathlib import Path

import vercel_blob
from flask import Flask, jsonify, render_template, request, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf

BASE_DIR = Path(__file__).parent
# CATALOGUE_MANIFEST_PATH lets e2e point at a small fixture catalogue (issue #44) instead of the
# real 218-photo one, so the test suite isn't hammering the dev server with the full set on
# every page load — never set in production, where this always resolves to the real manifest.
# A relative override is resolved against BASE_DIR, not the process's current working directory.
_manifest_override = os.environ.get("CATALOGUE_MANIFEST_PATH")
CATALOGUE_MANIFEST = (
    (BASE_DIR / _manifest_override) if _manifest_override
    else (BASE_DIR / "static" / "images" / "catalogue" / "manifest.json")
)

app = Flask(__name__)
APP_VERSION = (BASE_DIR / "VERSION").read_text().strip()

# ── Secret key ───────────────────────────────────────────────────────────────

def _resolve_secret_key(env):
    """Cookie-session cart contents (and CSRF tokens) are only as trustworthy as this key.
    Fails fast in production rather than silently falling back to a hardcoded, publicly-known
    value (issue #47) — that fallback is exactly what let #40's incident (SECRET_KEY unset in
    production for hours) go undetected until a customer noticed a missing order email, instead
    of the app simply refusing to start. VERCEL_ENV is set automatically by Vercel's platform
    (production/preview/development) — no new configuration needed to tell "a real deployment"
    apart from "a laptop running `python app.py`"."""
    secret_key = env.get("SECRET_KEY")
    if secret_key:
        return secret_key
    if env.get("VERCEL_ENV") == "production":
        raise RuntimeError("SECRET_KEY must be set in production.")
    return "dev-only-insecure-key"  # local dev only


app.config["SECRET_KEY"] = _resolve_secret_key(os.environ)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"])


# ── Catalogue ────────────────────────────────────────────────────────────────

# Taxonomic groupings for the catalogue sidebar (issue #72/#73) — every manifest entry must
# carry one of these in its "category" field, or _validate_catalogue below fails loudly rather
# than the sidebar silently dropping an uncategorised photo.
CATALOGUE_CATEGORIES = {
    "Flies", "Spiders", "Beetles", "Bees", "Moths", "Butterflies", "Ants",
    "Damselflies", "Dragonflies", "Mantises", "Wasps", "True Bugs",
    "Neuroptera", "Orthoptera", "Caterpillars", "Scorpions", "Stick Insects", "Other",
}


def _validate_catalogue(images):
    """Every entry needs width/height (issue #38) — the Prints/Apparel mockup scripts read
    aspect ratio straight from these, with no runtime image load to fall back on, so a missing
    pair would silently ship a permanently-disabled add-to-cart button for that photo."""
    missing = [img["id"] for img in images if not img.get("width") or not img.get("height")]
    if missing:
        raise RuntimeError(
            f"Catalogue entries missing width/height: {missing} — run "
            "scripts/add_catalogue_dimensions.py before starting the app."
        )
    missing_thumb_sm = [img["id"] for img in images if not img.get("thumb_sm")]
    if missing_thumb_sm:
        raise RuntimeError(
            f"Catalogue entries missing thumb_sm: {missing_thumb_sm} — run "
            "scripts/generate_thumb_sm.py before starting the app."
        )
    uncategorised = [img["id"] for img in images if img.get("category") not in CATALOGUE_CATEGORIES]
    if uncategorised:
        raise RuntimeError(
            f"Catalogue entries missing or with an unknown category: {uncategorised} — every "
            f"entry needs a \"category\" from CATALOGUE_CATEGORIES."
        )


def _load_catalogue():
    data = json.loads(CATALOGUE_MANIFEST.read_text())
    images = data["images"]
    _validate_catalogue(images)
    return images


def _category_slug(category):
    """URL/DOM-safe id for a category, e.g. "True Bugs" -> "true-bugs" — used to link a sidebar
    button to the grid section it jumps to."""
    return re.sub(r"[^a-z0-9]+", "-", category.lower()).strip("-")


def group_catalogue_by_category(images):
    """Groups catalogue images by category for the sidebar + jump-links nav (issue #74),
    largest group first (ties broken alphabetically) so the most-stocked categories are always
    at the top regardless of how the manifest itself is ordered — except "Other" (the catch-all
    for anything that isn't a real taxonomic group), which always sorts last regardless of its
    count. Preserves each group's original manifest order internally."""
    by_category = {}
    for img in images:
        by_category.setdefault(img["category"], []).append(img)

    groups = [
        {"category": category, "slug": _category_slug(category), "count": len(imgs), "images": imgs}
        for category, imgs in by_category.items()
    ]
    groups.sort(key=lambda g: (g["category"] == "Other", -g["count"], g["category"]))
    return groups


CATALOGUE = _load_catalogue()
CATALOGUE_IDS = {img["id"] for img in CATALOGUE}
CATALOGUE_BY_ID = {img["id"]: img for img in CATALOGUE}
CATALOGUE_BY_CATEGORY = group_catalogue_by_category(CATALOGUE)


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

# Per-line cap — generous for a genuine bulk order, small enough to keep a single line sane.
MAX_ITEM_QTY = 20

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
MPESA_NUMBER = "+254725561459"
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


def _parse_qty(form):
    try:
        qty = int(form.get("qty", 1))
    except (TypeError, ValueError):
        qty = 1
    return max(1, min(qty, MAX_ITEM_QTY))


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
        "qty": _parse_qty(form),
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
        "qty": _parse_qty(form),
    }


def _item_key(item):
    """Identity used to merge a new /cart/add into an existing line rather than duplicating it."""
    if item["type"] == "print":
        return ("print", item["photo_id"], item["size"])
    return ("apparel", item["photo_id"], item["age_group"], item["shirt_colour"])


def _current_price(item):
    """The current pricing-table value for an item's stored size/age_group, or None if it no
    longer resolves to one (issue #50) — never trust the price (or the size/age_group it's
    keyed on) stored in the session cookie."""
    if item["type"] == "print":
        return PRINT_SIZES.get(item.get("size"), {}).get("price")
    return APPAREL_PRICES.get(item.get("age_group"))


def revalidate_cart_prices(cart):
    """Overwrite every item's price with its current pricing-table value in place, dropping any
    item whose stored size/age_group no longer resolves to one. Called at checkout — the point
    of truth — rather than trusting whatever price was set at add time, in case the session
    cookie was ever tampered with (compounds with #47's SECRET_KEY finding)."""
    valid = []
    for item in cart:
        price = _current_price(item)
        if price is None:
            continue
        item["price"] = price
        valid.append(item)
    cart[:] = valid


def cart_total(cart):
    return sum(item["price"] * item.get("qty", 1) for item in cart)


def cart_item_count(cart):
    return sum(item.get("qty", 1) for item in cart)


# ── Order email (Resend) ────────────────────────────────────────────────────

CONTACT_RE = re.compile(r"^\S{2,120}$")
MPESA_CODE_RE = re.compile(r"^[A-Z0-9]{6,15}$")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def strip_control_chars(s):
    """Strip control characters — newlines, carriage returns, null bytes, etc. (issue #53) —
    before a customer-submitted field reaches the order email's subject/body. Resend's HTTP API
    (JSON over HTTPS, not raw SMTP) likely insulates against classic header injection, but
    that's Resend's implementation detail, not this app's own control, and an unstripped
    newline in e.g. `notes` already garbles the email's readability today regardless."""
    return CONTROL_CHARS_RE.sub("", s)


FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@")


def neutralize_formula_injection(s):
    """Prefix with a single quote if the value starts with a character (=, +, -, @) that
    triggers formula interpretation in Excel/Google Sheets/LibreOffice — this app has no CSV/
    spreadsheet export today, so there's no code path that opens this directly, but the order
    email exists to be read and acted on by a human, who may reasonably copy order details into
    a spreadsheet for bookkeeping. The leading single quote is the standard OWASP-recommended
    mitigation — forces the cell to be read as literal text — and costs nothing to apply now."""
    if s and s[0] in FORMULA_TRIGGER_CHARS:
        return "'" + s
    return s


def sanitize_customer_field(s):
    return neutralize_formula_injection(strip_control_chars(s))


# ── M-Pesa replay guard (issue #48) ─────────────────────────────────────────
# The M-Pesa code is entirely self-reported — there is no Safaricom Daraja API integration to
# verify a code is real (that's the eventual real fix, a bigger project of its own). This is the
# cheap interim mitigation: track which codes have already been used and reject a repeat, so the
# same real payment can't be claimed as proof for multiple orders.
#
# Storage: Vercel Blob, one small immutable blob per code (pathname derived from the code
# itself), rather than one shared mutable JSON object. Deliberate: overwriting a single shared
# blob hits Vercel Blob's CDN cache floor for *reads* (observed directly — served
# `cache-control: public, max-age=60` with `x-vercel-cache: HIT` regardless of the
# cacheControlMaxAge requested on write, so a read shortly after a write can return a stale
# pre-write snapshot for up to a minute). A brand-new pathname doesn't have this problem — a
# `list()` existence-check for a pathname that was *just created* returns correctly and
# immediately (verified directly), since it's a fresh object rather than a cached-then-updated
# one. `allowOverwrite: false` also turns creation into an atomic compare-and-swap: if a
# concurrent request already claimed this exact code between our existence check and our write,
# the write itself fails, closing the race window almost entirely rather than just narrowing it.
#
# The store must be *public* access — Vercel Blob's private-access mode currently rejects writes
# made with a deployed app's own BLOB_READ_WRITE_TOKEN (only an authenticated `vercel` CLI
# session can write to a private store as of this writing). The data itself is low-sensitivity
# (an opaque already-used code as the pathname, no names/amounts/contact info in the content),
# and no pathname is linked from anywhere public.
#
# Fails open (logs a warning, allows the order through) if Blob isn't configured or the check
# itself errors — this guard reduces fraud, it isn't infrastructure the whole checkout flow
# should depend on being up.
MPESA_CODES_BLOB_PREFIX = "used-mpesa-codes/"


def _mpesa_code_blob_pathname(code):
    """Pure, split out from the Blob I/O so it's directly unit-testable."""
    return f"{MPESA_CODES_BLOB_PREFIX}{code}.json"


def check_and_record_mpesa_code(code):
    """Returns True if `code` was already used in a previous order (reject this checkout), False
    if it's newly recorded as used (or the guard couldn't run at all)."""
    if not os.environ.get("BLOB_READ_WRITE_TOKEN"):
        app.logger.warning("BLOB_READ_WRITE_TOKEN not set — M-Pesa replay guard skipped")
        return False
    pathname = _mpesa_code_blob_pathname(code)
    try:
        existing = vercel_blob.list({"prefix": pathname, "limit": 1})
        if existing.get("blobs"):
            return True
        vercel_blob.put(
            pathname, json.dumps({"used_at": datetime.utcnow().isoformat()}).encode(),
            {"allowOverwrite": "false"},
        )
        return False
    except vercel_blob.errors.BlobRequestError:
        # A concurrent request claimed this exact code between our existence check and our
        # write (allowOverwrite=false made that write fail) — that's a replay too.
        return True
    except Exception:
        app.logger.warning("M-Pesa replay guard check/record failed", exc_info=True)
        return False


def _describe_item(item):
    photo = CATALOGUE_BY_ID.get(item["photo_id"])
    label = f"photo #{item['photo_id']}" if photo else f"photo #{item['photo_id']} (unknown)"
    qty = item.get("qty", 1)
    if item["type"] == "print":
        base = f"Print — {label} — {item['size']}"
    else:
        base = f"Apparel (T-shirt) — {label} — {item['age_group'].title()} — {item['shirt_colour']}"
    return f"{base} — Qty {qty} — KES {item['price']:,} each — KES {item['price'] * qty:,} total"


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
        "cart_count": cart_item_count(session.get("cart", [])),
        "csrf_token": generate_csrf,
    }


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/prints")
def prints():
    return render_template(
        "prints.html", catalogue_by_category=CATALOGUE_BY_CATEGORY, sizes=PRINT_SIZES,
        max_qty=MAX_ITEM_QTY, turnaround=TURNAROUND_TEXT,
    )


@app.route("/apparel")
def apparel():
    return render_template(
        "apparel.html", catalogue_by_category=CATALOGUE_BY_CATEGORY, prices=APPAREL_PRICES,
        shirt_colours=SHIRT_COLOURS, max_qty=MAX_ITEM_QTY,
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
    key = _item_key(item)
    for existing in cart:
        if _item_key(existing) == key:
            existing["qty"] = min(existing.get("qty", 1) + item["qty"], MAX_ITEM_QTY)
            break
    else:
        cart.append(item)
    session["cart"] = cart
    return jsonify({"ok": True, "cart_count": cart_item_count(cart)})


@app.route("/cart/remove/<int:index>", methods=["POST"])
@limiter.limit("60 per minute")
def cart_remove(index):
    cart = session.get("cart", [])
    if 0 <= index < len(cart):
        cart.pop(index)
        session["cart"] = cart
    return jsonify({"ok": True, "cart_count": cart_item_count(cart)})


@app.route("/cart/qty/<int:index>", methods=["POST"])
@limiter.limit("60 per minute")
def cart_qty(index):
    cart = session.get("cart", [])
    if not (0 <= index < len(cart)):
        return jsonify({"ok": False, "error": "Item not found."}), 404

    data = request.get_json(silent=True) or {}
    try:
        delta = int(data.get("delta", 0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid quantity change."}), 400
    if delta == 0:
        return jsonify({"ok": False, "error": "No quantity change given."}), 400

    new_qty = cart[index].get("qty", 1) + delta
    if new_qty <= 0:
        cart.pop(index)
        new_qty = 0
    else:
        cart[index]["qty"] = min(new_qty, MAX_ITEM_QTY)
        new_qty = cart[index]["qty"]
    session["cart"] = cart

    return jsonify({
        "ok": True,
        "removed": new_qty == 0,
        "qty": new_qty,
        "cart_count": cart_item_count(cart),
        "total": cart_total(cart),
    })


@app.route("/api/checkout/submit", methods=["POST"])
@limiter.limit("10 per minute")
def checkout_submit():
    cart = session.get("cart", [])
    if not cart:
        return jsonify({"ok": False, "error": "Your cart is empty."}), 400
    revalidate_cart_prices(cart)
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
    if check_and_record_mpesa_code(mpesa_code):
        return jsonify({
            "ok": False,
            "error": "This M-Pesa code has already been used for a previous order.",
        }), 400

    customer = {
        "name": sanitize_customer_field(name)[:200],
        "contact": sanitize_customer_field(contact)[:200],
        "location": sanitize_customer_field(location)[:400],
        "notes": sanitize_customer_field(notes)[:1000],
        "mpesa_code": mpesa_code[:20],
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
    # threaded=True: the dev server otherwise handles one request at a time, serialising every
    # asset a page needs (HTML/CSS/JS/images) — fine when a page needed few requests, but the
    # Prints wall mockup now also loads room.jpg alongside the catalogue photo, which was
    # enough to blow e2e's wait budgets under this server's default single-threaded behaviour.
    # Vercel's actual production deployment is unaffected either way (one request per
    # serverless invocation, no shared server process to serialise through).
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), threaded=True)
