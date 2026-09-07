# dudu-merchandise

Merchandise storefront for Eric Gitonga Mbaya's insect macro photography — Prints today, Apparel
and Coasters coming later. Clients pick a photo from a fixed catalogue (no upload flow), see a
live preview — a living-room wall mockup for Prints — and add it to a cart. Checkout is a modal
on the cart page: it shows the M-Pesa payment details, requires the client to enter the M-Pesa
confirmation code from their payment (self-reported, not verified against M-Pesa), and on
submission emails the order to the site owner via [Resend](https://resend.com).

## Local setup

```bash
conda activate ds
pip install -r requirements.txt -r requirements-dev.txt
python app.py
```

Runs at `http://127.0.0.1:5000`. Flask's dev server caches templates outside debug mode —
restart the process after editing anything in `templates/`.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `SECRET_KEY` | Production only | Signs the session cookie (cart contents) and CSRF tokens. A dev-only default is used locally; the app refuses to start if it's missing and `VERCEL_ENV=production` (issue #47) rather than silently falling back to that default. |
| `RESEND_API_KEY` | For order emails | Without it, order submission still succeeds but email delivery is skipped (logged, not sent) — see `send_order_email` in `app.py`. |
| `FROM_EMAIL` | No | Sender address for order emails. Defaults to Resend's `onboarding@resend.dev` sandbox address, which shows the raw address as the sender name. Set a display name instead — e.g. `Dudu Merch <onboarding@resend.dev>` — to brand it (Resend's sandbox address accepts a custom display name; a verified custom domain would additionally allow a fully custom `from` address). |

Order emails always go to `gitonga@gmail.com` (a constant in `app.py`, not configurable via env).

**Setting/changing any of these in Vercel requires a fresh deploy to take effect** — a Python
serverless function's already-warm instances don't pick up an added or changed environment
variable on their own; `vercel env add` alone doesn't affect what's currently live. After
changing one, redeploy (`vercel --prod` for production) and run
`scripts/smoke_test_production.py` against it to confirm the change actually took (issue #40:
`RESEND_API_KEY`/`SECRET_KEY` sat unset in production for hours, caught only when a real
customer's order email never arrived — see "Production smoke test" below).

## Production smoke test

`scripts/smoke_test_production.py` places one clearly-marked test order through the real API
(`/cart/add` + `/api/checkout/submit` — no hidden/backdoor route) and asserts the response's
`email_status` comes back `"sent"`:

```bash
conda run -n ds python scripts/smoke_test_production.py                              # production
conda run -n ds python scripts/smoke_test_production.py --base-url https://<preview>  # a PR preview
```

Run this after any deploy that touches `RESEND_API_KEY`/`SECRET_KEY`/`FROM_EMAIL`, checkout, or
cart logic — `e2e/` intentionally never has `RESEND_API_KEY` configured (it asserts `"skipped"`
is the *correct* behaviour without one), so it can never catch a real environment
misconfiguration the way this can.

## Catalogue images

`static/images/catalogue/` (`thumbs/` for the picker grid, `full/` for the live mockup preview,
plus `manifest.json` listing every available photo id) is the *only* source of photos clients
can pick from — there is no upload flow. To add more: resize into both directories, add an entry
to `manifest.json` (`id`/`thumb`/`full` — `width`/`height` can be omitted), then run

```bash
conda run -n ds python scripts/add_catalogue_dimensions.py
```

to fill in `width`/`height` (read from the full-resolution image) for any entry missing them —
already-populated entries are left alone, so it's safe to run any time. The Prints/Apparel
mockup scripts read aspect ratio from these fields with no runtime image load involved (issue
#38); a photo without them will never enable its add-to-cart button. See
`extras/projects/dudu-merchandise/assets/catalogue/` (outside this repo) for the verified
full-resolution originals these were generated from.

## Prints wall mockup

`static/images/mockup/room.jpg` is the real room photo the chosen print is positioned onto in
`templates/prints.html` / `static/js/prints-mockup.js` — a plain rectangle placement against a
moulded wall panel, no perspective correction needed since the photo is shot dead-on frontal.
The mockup always renders at A2 (`MOCKUP_SIZE` in `prints-mockup.js`) regardless of which size
is selected for ordering — rendering at the actually-selected size looked disproportionate at
the extremes against this one room photo (issue #25); the size picker only changes price and
what's ordered. Sizing uses an authored scale constant (`ROOM_WIDTH_CM`), not a measured one —
see that file's comments, and issues #17/#20/#25 for how the geometry was derived.

## Tests

```bash
pytest                             # unit tests — pricing, cart-item validation, order email

# e2e suite — run against a server started with a small 5-photo fixture catalogue instead of the
# real one (issue #44), so the suite isn't re-fetching the full ~117-photo catalogue on every
# test's page load:
CATALOGUE_MANIFEST_PATH=static/images/catalogue-e2e/manifest.json python app.py  # one terminal
conda run -n ds python e2e/run.py                                               # another
```
