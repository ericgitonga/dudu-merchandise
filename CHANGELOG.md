# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org) (pre-1.0: MINOR = new features/user-facing
behaviour, PATCH = fixes/docs/housekeeping — see `SKILL.md`).

## [0.7.0] - 2026-09-07

### Added

- M-Pesa replay guard (`check_and_record_mpesa_code`, `app.py`) — checkout now rejects an M-Pesa
  confirmation code already used in a previous order, instead of accepting the same real payment
  as proof for unlimited orders. Storage is Vercel Blob: one small immutable blob per code
  (`used-mpesa-codes/<code>.json`, public-access store), `allowOverwrite: false` making creation
  an atomic compare-and-swap. Doesn't verify a code is authentic — only that it hasn't been
  claimed before — see issue #48 for the real fix (Daraja API integration) this stands in for.
  Fails open (order still succeeds, warning logged) if `BLOB_READ_WRITE_TOKEN` isn't configured
  or the check errors (closes #48)

tag: `v0.7.0`

## [0.6.1] - 2026-09-07

### Security

- `SECRET_KEY` now fails fast at startup if unset with `VERCEL_ENV=production`, instead of
  silently falling back to a hardcoded, publicly-known value — the exact pattern that let #40's
  incident (SECRET_KEY unset in production for hours) go undetected. Local dev is unaffected
  (closes #47)

tag: `v0.6.1`

## [0.6.0] - 2026-09-07

### Added

- `scripts/smoke_test_production.py` — places one clearly-marked test order through the real API
  and asserts `email_status` comes back `"sent"`, so a live misconfiguration (a required env var
  never actually set in Vercel) can be caught deliberately rather than only by a customer report
  (issue #40). `e2e/` intentionally never has `RESEND_API_KEY` configured and so can never catch
  this class of gap
- README documents `FROM_EMAIL`'s recommended display-name value (`Dudu Merch
  <onboarding@resend.dev>`) and that Vercel env var changes need a fresh deploy to take effect
- SKILL.md's launch checklist now requires `vercel env ls production` + a smoke-test run for any
  change touching `RESEND_API_KEY`/`SECRET_KEY`/`FROM_EMAIL`, checkout, or cart logic

(closes #41)

tag: `v0.6.0`

## [0.5.5] - 2026-09-07

### Changed

- M-Pesa number now displays as one unbroken unit (`+254725561459`) instead of clustered with
  spaces (`+254 725 561 459`), in both the checkout modal and the order-confirmation email
  (closes #42)

tag: `v0.5.5`

## [0.5.4] - 2026-09-07

### Fixed

- e2e suite hammered the dev server: 16 tests each launched a brand-new Chromium process (real
  CPU overhead competing with the single Flask process for cycles) and re-fetched the full
  ~117-photo catalogue from a cold browser context every time — confirmed via a CI run logging
  1046 thumbnail requests and repeated timeouts on unrelated tests despite #38 already removing
  the button-enable gate's network dependency entirely. Now: one shared Chromium process for the
  whole suite (`e2e/_common.py`, isolated `browser.new_context()` per test — no cookie/storage
  bleed), plus a 5-photo fixture catalogue (`static/images/catalogue-e2e/`, real copies of ids
  001/004/005/007/008) used by CI and documented for local runs, instead of the real catalogue.
  Cut one local run's thumbnail requests from 1046 to 65 (closes #44)
- `app.py` gains `CATALOGUE_MANIFEST_PATH` (optional env override, resolved against `BASE_DIR`)
  so e2e can point at the fixture catalogue without touching production's default

tag: `v0.5.4`

## [0.5.3] - 2026-09-07

### Fixed

- Eliminated the Prints/Apparel mockup's remaining network dependency for the add-to-cart
  enable gate — `manifest.json` now carries each catalogue photo's width/height (added via new
  `scripts/add_catalogue_dimensions.py`, run once over the existing 117 photos), so aspect ratio
  comes straight from JSON with no image load involved at all. Supersedes the timeout-only
  mitigations in #30/#36 — this removes the flake's actual root cause rather than budgeting
  around it. `app.py` now fails fast at startup if any catalogue entry is missing dimensions
  (closes #38)

tag: `v0.5.3`

## [0.5.2] - 2026-09-07

### Fixed

- Flaky `test_apparel_mockup_renders_and_enables_add_to_cart` e2e test — widened its 5000ms
  wait budget to 20000ms, matching the Prints mockup test's budget (#30) — this test was never
  updated when #30 removed the actual network dependency from both mockup scripts (closes #36)

tag: `v0.5.2`

## [0.5.1] - 2026-09-07

### Fixed

- Prints/Apparel selection-pane price line now reacts to the quantity stepper — previously it
  only re-rendered on size/age-group selection, so picking qty > 1 still showed the unit price
  with no total, matching the cart's own "KES X each — KES Y total" wording once qty > 1
  (closes #34)

tag: `v0.5.1`

## [0.5.0] - 2026-09-07

### Added

- Quantity picker (−/input/+, capped at 20 per line) on the Prints and Apparel selection panes —
  "Add to cart" adds that many, merging into an existing matching line rather than creating a
  duplicate row (closes #32)
- +/- buttons on each cart line to adjust its quantity in place; decrementing to 0 removes the
  line, same as the existing Remove button (closes #32)

### Changed

- The nav cart badge now shows the total quantity across all lines, not the number of lines
- Order-confirmation emails list each line's quantity and line total, not just its unit price

tag: `v0.5.0`

## [0.4.3] - 2026-09-07

### Fixed

- Flaky `test_prints_mockup_renders_and_enables_add_to_cart` e2e test — the Prints and Apparel
  mockup scripts were gating the add-to-cart button on a redundant full-resolution image fetch
  just to read its dimensions, which competed with the wall-mockup background photo and every
  catalogue thumbnail for the dev server's attention and occasionally blew CI's wait budget; both
  now read aspect ratio off the already-loaded thumbnail instead (closes #30)

tag: `v0.4.3`

## [0.4.2] - 2026-09-07

### Changed

- Prints copy rewritten to name the actual print process/material — dye-sublimation onto an
  aluminium panel — and lead with benefit-led, gift-oriented language instead of "framed for
  your wall", which conflicted with the frameless wall mockup (closes #28)

tag: `v0.4.2`

## [0.4.1] - 2026-09-07

### Fixed

- Two stray links to the hidden Apparel page — the cart's empty-cart message and the Coasters
  placeholder page — missed when Apparel was hidden in #18 (closes #26)

tag: `v0.4.1`

## [0.4.0] - 2026-09-07

### Added

- Photo #276 added to the catalogue (closes #23)

### Changed

- Prints wall mockup replaced with a real, frameless, photo-real living-room wall (was a
  CSS-drawn illustrated wall) — the chosen photo's own aspect ratio now picks portrait vs.
  landscape orientation, instead of always force-cropping into portrait (closes #20)
- Wall mockup now always renders at A2 dimensions regardless of the size selected for
  ordering — rendering at the actual selected size looked disproportionate at the extremes
  (A0 read as roughly couch-sized against the room photo, which it isn't); the size picker
  only ever changes price and what's ordered now (closes #25)

tag: `v0.4.0`

## [0.3.0] - 2026-09-07

### Added

- Checkout now requires the client's M-Pesa confirmation code, validated server-side and
  included in the order email — previously the modal only displayed payment instructions with
  no capture of proof of payment (closes #21)

tag: `v0.3.0`

## [0.2.3] - 2026-09-07

### Changed

- Apparel hidden from the nav and home page — the `/apparel` route, template, and e2e coverage
  stay in place, only the visible links are removed — while its approach gets more thought
  (closes #18)

tag: `v0.2.3`

## [0.2.2] - 2026-09-06

### Changed

- Full name attribution ("Eric Gitonga Mbaya") in the footer, README, and homepage copy —
  M-Pesa payee name stays "Eric Mbaya" — and a new homepage hero title/sub-title (closes #15)

tag: `v0.2.2`

## [0.2.1] - 2026-09-06

### Changed

- Coasters hidden from the nav and home page — the `/coasters` route, template, and e2e
  coverage stay wired up, it's just not discoverable in the UI yet (closes #14)

## [0.2.0] - 2026-09-06

### Added

- Catalogue photo library: 116 hash-verified photos (`static/images/catalogue/`, thumb + full
  sizes, `manifest.json`) — the only source of photos clients can pick from (closes #3)
- Home page with Prints/Apparel/Coasters selector (closes #4)
- Prints page: catalogue picker, A4–A0 size picker, live living-room wall mockup scaled to real
  paper dimensions, add-to-cart (closes #5, closes #10)
- Apparel page: catalogue picker, adult/child sizing, 14-colour shirt swatch, live SVG t-shirt
  mockup — the same silhouette/chest-placement geometry as `merch-mockup`'s `_make_mockup`,
  ported to client-side SVG (closes #6)
- Coasters placeholder page (closes #7)
- Cart (Flask session, no database) shared across Prints and Apparel (closes #8)
- Checkout modal on `/cart`: M-Pesa payment instructions, delivery form, order submitted via
  Resend to the site owner (closes #9, closes #11)

tag: `v0.2.0`

## [0.1.0] - 2026-09-06

### Added

- Initial project scaffold: repo, branch protection, CI (e2e gate on every PR), versioning and
  issue-first workflow (closes #1)

tag: `v0.1.0`
