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
| `SECRET_KEY` | Production only | Signs the session cookie (cart contents) and CSRF tokens. A dev-only default is used locally. |
| `RESEND_API_KEY` | For order emails | Without it, order submission still succeeds but email delivery is skipped (logged, not sent) — see `send_order_email` in `app.py`. |
| `FROM_EMAIL` | No | Sender address for order emails. Defaults to Resend's `onboarding@resend.dev` sandbox address. |

Order emails always go to `gitonga@gmail.com` (a constant in `app.py`, not configurable via env).

## Catalogue images

`static/images/catalogue/` (`thumbs/` for the picker grid, `full/` for the live mockup preview,
plus `manifest.json` listing every available photo id) is the *only* source of photos clients
can pick from — there is no upload flow. To add more, resize into both directories and add an
entry to `manifest.json`; see `extras/projects/dudu-merchandise/assets/catalogue/` (outside this
repo) for the verified full-resolution originals these were generated from.

## Tests

```bash
pytest                             # unit tests — pricing, cart-item validation, order email
conda run -n ds python e2e/run.py  # e2e suite, against a running server — full page/cart/checkout flows
```
