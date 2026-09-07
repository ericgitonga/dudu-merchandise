# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org) (pre-1.0: MINOR = new features/user-facing
behaviour, PATCH = fixes/docs/housekeeping — see `SKILL.md`).

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
