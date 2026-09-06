# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org) (pre-1.0: MINOR = new features/user-facing
behaviour, PATCH = fixes/docs/housekeeping — see `SKILL.md`).

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
