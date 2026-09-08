# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org) (pre-1.0: MINOR = new features/user-facing
behaviour, PATCH = fixes/docs/housekeeping — see `SKILL.md`).

## [0.13.0] - 2026-09-08

### Added

- 433 new catalogue photos onboarded across every remaining category with a pending, not-yet-
  curated pool: Ants (15), Bees (19), Beetles (15), Butterflies (22), Damselflies (11),
  Dragonflies (8), Flies (184), Mantises (11), Moths (33), Neuroptera (4), Orthoptera (20),
  Spiders (39), True Bugs (39), Wasps (9), and a **new `Stick Insects` category** (prefix `st`,
  4 photos) — every photo found in `extras/`, renamed to the `<prefix>-NNN` convention (Flies
  and Beetles/Butterflies/etc. sat as loose files or, for Flies, an unflattened `x/` staging
  subfolder) and onboarded via `scripts/onboard_catalogue_photos.py`. Catalogue goes from 224 to
  657 photos across 18 categories (closes #95)
- `scripts/onboard_catalogue_photos.py` now auto-scans every category folder for pending
  additions instead of requiring a hand-maintained list, so a whole batch across multiple
  categories onboards in one run

tag: `v0.13.0`

## [0.12.0] - 2026-09-08

### Added

- New `Scorpions` category (prefix `sc`) and 6 new catalogue photos: `sc-002`-`sc-004` and
  `ot-001`/`ot-011`/`ot-012` — onboarded via a new `scripts/onboard_catalogue_photos.py`, which
  resizes source photos into `thumbs/`+`full/` per the established convention (full capped at
  1400px long side, thumb at 420px) and fills in the manifest entry directly (closes #92)

### Fixed

- `ot-001.jpg` was miscategorized as Other — it's a scorpion. Recategorized as `sc-001`, the
  first Scorpions photo (closes #92)

tag: `v0.12.0`

## [0.11.6] - 2026-09-08

### Fixed

- The catalogue picker's auto-selected first photo could intermittently leave the Prints/Apparel
  add-to-cart button permanently disabled — `catalogue-picker.js` triggered it via
  `setTimeout(fn, 0)` so later `<script>` tags (the mockup scripts) had time to attach their
  `"photo-selected"` listener first, but headless Chromium's background-tab timer throttling
  (routine when many pages get created/closed in one shared browser process, as the e2e harness
  does, issue #44) could delay or entirely skip that callback. Traced live with Playwright
  tracing: DOM snapshot at timeout showed no thumbnail ever got `.selected` and the button stayed
  `disabled` — not merely slow, the callback never ran at all. Reproduced a clean 8/45 (~18%)
  failure rate against a real server with no other confound; moving the auto-select trigger into
  each mockup script itself (`prints-mockup.js`/`apparel-mockup.js`, called synchronously right
  after attaching their own listener — no timer involved at all) brought that to 0/45 across two
  independent verification runs (closes #90)

### Maintenance

- `e2e/_common.py`'s shared Chromium instance now launches with
  `--disable-background-timer-throttling`/`--disable-backgrounding-occluded-windows`/
  `--disable-renderer-backgrounding` as defense-in-depth against the same class of issue for any
  future page-level JS timer, even though the actual bug above is fixed at the source

tag: `v0.11.6`

## [0.11.5] - 2026-09-08

### Removed

- Apparel/Coasters functional test coverage (page display, mockup rendering, pricing/colour
  logic) — both sections stay hidden from nav (issues #18, #14) and aren't ready to go live, so
  CI no longer gates on features nobody can reach yet. Nav-hiding guards
  (`test_index_loads_with_nav_links`, `test_no_page_links_to_hidden_apparel`) and any test only
  incidentally using an apparel item (e.g. mixed-cart total/count tests) are unaffected (closes
  #88; restore tracked in #89)

tag: `v0.11.5`

## [0.11.4] - 2026-09-08

### Fixed

- Recategorized `bu-001.jpg` (actually a moth, not a butterfly) — moved to Moths as the next
  unused number (`mo-016`), and closed the numbering gap left behind in Butterflies so it stays
  a contiguous 001..NNN sequence (closes #86)

tag: `v0.11.4`

## [0.11.3] - 2026-09-08

### Fixed

- Recategorized `be-007.jpg` (actually a fly, not a bee) and `f-059.jpg` (moved to Other) —
  moved each to its correct category as the next unused number there (`f-065` then `ot-010`),
  and closed the numbering gap left behind in Bees and Flies so both stay a contiguous 001..NNN
  sequence (closes #84)

tag: `v0.11.3`

## [0.11.2] - 2026-09-08

### Changed

- Renumbered every catalogue photo from a global numeric id (e.g. `169.jpg`) to a per-category,
  letter-prefixed id (e.g. `t-001.jpg` for True Bugs) — filenames in `thumbs/` and `full/` and
  every `manifest.json` entry updated to match, ordered by each photo's previous numeric id
  within its category. Documented the new `<prefix>-NNN` convention in README so future additions
  continue the sequence (closes #82)

tag: `v0.11.2`

## [0.11.1] - 2026-09-08

### Maintenance

- Raised the e2e suite's mockup-enable wait from a hardcoded 5000ms to a shared
  `MOCKUP_ENABLE_TIMEOUT_MS` (15000ms, `e2e/_common.py`) — the wait has nothing to do with
  image loading or network (it reacts to a synchronous DOM update), but a CI runner under
  shared-tenant load can occasionally starve the page's own JS execution past 5s. Flaked 3
  times across 2 unrelated PRs in the same short window, always clean on immediate re-run
  (closes #77)

tag: `v0.11.1`

## [0.11.0] - 2026-09-08

### Added

- Catalogue picker on Prints/Apparel now groups photos by category behind a sidebar with
  jump links (`group_catalogue_by_category()` in `app.py`, `static/js/catalogue-sidebar.js`) —
  clicking a category scrolls the grid to that section and highlights it, tracking manual
  scrolling the same way; chosen over a tabs/dropdown filter via an interactive mockup
  (closes #74)

### Changed

- "Other" (the catch-all for anything that isn't a real taxonomic group) always sorts last in
  the sidebar now, regardless of its count, rather than ranking alongside genuine categories

tag: `v0.11.0`

## [0.10.1] - 2026-09-08

### Fixed

- Catalogue photo `040` was miscategorised as Ants — it's a bee (closes #78)

tag: `v0.10.1`

## [0.10.0] - 2026-09-08

### Added

- Every catalogue entry now carries a `category` (Flies, Spiders, Beetles, Bees, Moths,
  Butterflies, Ants, Damselflies, Dragonflies, Mantises, Wasps, True Bugs, Neuroptera,
  Orthoptera, Caterpillars, Other), assigned by visual review of all photos and validated at
  startup against a new `CATALOGUE_CATEGORIES` set — groundwork for the catalogue sidebar (#72,
  #74)

### Fixed

- Removed catalogue photo `350`, a duplicate of `316` found during the classification review
  (closes #73)

tag: `v0.10.0`

## [0.9.1] - 2026-09-08

### Changed

- The 2-week lead time (`TURNAROUND_TEXT`) was previously only visible inside the checkout
  modal — now also shown on the Prints page intro and directly on the cart page, so customers
  see it while selecting items, not just at the point of payment (closes #70)

tag: `v0.9.1`

## [0.9.0] - 2026-09-08

### Added

- 2 new catalogue photos, ids `377`-`378` (closes #68)

tag: `v0.9.0`

## [0.8.5] - 2026-09-07

### Maintenance

- Merged 4 Dependabot dependency updates: `actions/setup-python` 5→7, `actions/checkout` 4→7,
  `pillow` 10.4.0→12.3.0 (dev-script only), `resend` 2.32.2→2.43.0 (#62-#65)

## [0.8.4] - 2026-09-07

### Security

- Customer-submitted checkout fields (`name`, `contact`, `location`, `notes`) now have control
  characters (`\r`, `\n`, `\0`, etc.) stripped (`strip_control_chars`, `app.py`) before reaching
  the order-confirmation email's subject/body — previously only stripped/length-truncated, so an
  unstripped newline in e.g. `notes` could garble the email's readability. Resend's HTTP API
  (JSON over HTTPS, not raw SMTP) likely insulates against classic header injection already, but
  that's Resend's implementation detail, not this app's own control (closes #53)
- Same fields also get a leading single-quote prefix (`neutralize_formula_injection`, `app.py`)
  if they start with a character (`=`, `+`, `-`, `@`) that triggers formula interpretation in
  Excel/Google Sheets/LibreOffice — this app has no CSV/spreadsheet export today, but the order
  email exists to be read and acted on by a human who may reasonably copy order details into a
  spreadsheet for bookkeeping; the standard OWASP-recommended mitigation costs nothing to apply
  now

tag: `v0.8.4`

## [0.8.3] - 2026-09-07

### Security

- Dependencies fully pinned to their currently-installed, tested versions in
  `requirements.txt`/`requirements-dev.txt` (were entirely unpinned — every fresh `pip install`
  silently grabbed whatever was latest at that moment) — a reproducibility/supply-chain gap, not
  a currently-known vulnerability
- Added `.github/dependabot.yml` (pip + github-actions ecosystems, weekly) so future version
  bumps are proposed as reviewable PRs instead of happening silently (closes #52)

tag: `v0.8.3`

## [0.8.2] - 2026-09-07

### Security

- `/cart/remove/<index>` now has an explicit `60 per minute` rate limit, matching its
  cart-mutation siblings (`/cart/add`, `/cart/qty/<index>`) — previously it only inherited the
  looser app-wide default (200/day, 50/hour). Verified directly: request 61 in a burst returns
  429 (closes #51)

tag: `v0.8.2`

## [0.8.1] - 2026-09-07

### Security

- Checkout now revalidates every cart item's price against the current pricing tables
  (`revalidate_cart_prices`, `app.py`) rather than trusting whatever price was set at add
  time — defense-in-depth against a forged session cookie (compounds with #47's `SECRET_KEY`
  finding). An item whose stored size/age_group no longer resolves to a valid price is dropped
  from the cart rather than crashing checkout (closes #50)

tag: `v0.8.1`

## [0.8.0] - 2026-09-07

### Added

- 100 new catalogue photos from the "Black and White" and "Predator and Prey" collections, ids
  `277`-`376`. Checked both source folders against the existing catalogue first — perceptual-hash
  matching to find candidates, then an actual side-by-side visual comparison of every candidate,
  since filenames aren't unique identifiers across the wider photo library — 16 photos (12 from
  "Black and White", 4 from "Predator and Prey") turned out to already be in the catalogue under
  different ids and were excluded (closes #57)

tag: `v0.8.0`

## [0.7.1] - 2026-09-07

### Security

- Real rate-limit enforcement for cart/checkout write endpoints, via a Vercel Firewall custom
  rule rather than `flask-limiter`'s in-memory storage (which doesn't share counters across
  Vercel's serverless instances) — 20 requests/60s per IP, combined across `POST
  /api/checkout/submit`, `/cart/add`, `/cart/qty/*`, and `/cart/remove/*` (one shared budget,
  since the Hobby plan allows only one `rate_limit`-action rule). Verified directly against
  production: request 21 in a burst returns `429`, access resumes after the window passes.
  Platform config, not tracked in this repo — see README's "Rate limiting" section (closes #49)

tag: `v0.7.1`

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
