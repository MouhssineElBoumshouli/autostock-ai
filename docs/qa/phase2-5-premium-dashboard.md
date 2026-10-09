# Phase 2.5: premium Odoo dashboard QA

**Run date:** 2026-10-09

**Branch:** `codex/phase2-5-premium-dashboard`

**Scope:** improve the connected inventory and evaluated-forecast dashboard while retaining Odoo navigation, data, company context, and permissions. Purchasing, reporting, and other planned product capabilities remain outside this change.

The commercial-readiness charter ([issue #7](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/7)) and premium UX acceptance criteria ([issue #8](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/8)) continue to apply. This phase brings the live interface closer to the approved [dashboard concept](../../design/dashboard-concept.png); it does not satisfy the full release gates and AutoStock AI is not described as production-ready.

## Changes reviewed

- Added a responsive AutoStock workspace rail and compact context bar inside the Odoo action. Odoo's native top bar, company switcher, user menu, product records, and access controls remain in place.
- Showed the active Odoo company and its company logo through the authenticated Odoo image route.
- Added keyboard-operable mobile navigation with focus entry, focus wrapping, Escape close, and focus return. A live browser check exposed an Owl rerender timing issue; focus now lands after the drawer is rendered.
- Made chart history selection work at 30 days, 90 days, or every observation returned for the selected history, with the accessible date range included in the chart label. The SVG resizes with its container and keeps date and value ticks visible.
- Fixed Full-history plot compression by synchronizing the SVG `viewBox` to the actual rendered SVG width after Owl patches and frame resize events. This prevents SVG's default `xMidYMid meet` behavior from centering a stale 260px viewBox inside a much wider chart.
- Replaced the empty health visualization with an explanatory empty state and added next-step guidance when no tracked products exist.
- Removed cards that suggested tools not implemented in Odoo.
- Added an idempotent, database-guarded synthetic automotive inventory seeder. Its `cleanup` action is a **non-destructive reset**: it zeroes quantities and disables AutoStock tracking on labeled `[SYNTHETIC QA]` products, but the products remain in the catalog and Odoo keeps stock adjustment history. It creates no customers, suppliers, sales, or purchase orders.
- Corrected company-switch detection to compare company IDs, reset company-bound filters and charts, and ignore late forecast snapshots from the previous company. The Odoo regression uses two real companies with separate products and warehouses; the browser regression holds the display name constant while changing the ID. Odoo enforces unique company names, so the backend test does not create duplicate names.
- Made the appbar breadcrumb consistently identify the Dashboard route and made the Odoo connection status reflect loading, successful dashboard RPCs, failures, and recovery.
- Extended Playwright browser QA to measure the SVG, `viewBox`, axes/path bounds, figure width, and plot utilization after 30/Full transitions on desktop, tablet, and mobile, using 400 in-memory synthetic history observations. It also checks accessible date ranges, same-name display with a changed company ID, company-bound state reset, truthful status failure/recovery, navigation, and absence of future-feature placeholders.

## Automated checks

| Check | Result | Evidence |
|---|---|---|
| Python tests | **25 passed** | `python -m pytest -q` |
| Python compilation | **Passed** | `python -m compileall -q addons ml scripts tests` |
| Odoo integration tests | **22 test cases; 0 failures, 0 errors** | Fresh isolated Compose project, Odoo `19.0-20260926`, PostgreSQL 16; addon installed using `--test-enable --test-tags=/autostock_ai --stop-after-init --without-demo=true`. The project volumes and container were removed after the run. |
| GitHub Actions | **Both jobs passed** | Run [37999979826](https://github.com/MouhssineElBoumshouli/autostock-ai/actions/runs/37999979826): Python tests, compilation, and labeled synthetic forecast evaluation passed; Odoo 19 addon installation and all 22 integration tests passed against PostgreSQL 16. |
| Synthetic forecast evaluation | **Completed for 6 labeled synthetic SKUs** | Generated 210-day histories and evaluated a 30-day chronological holdout with `python -m ml.evaluate ... --days 30`. This verifies pipeline execution only; it is not evidence of business forecast accuracy. |
| Odoo browser QA | **Passed; 0 unexpected console/page errors** | Chromium against the running local Odoo 19 demo database. Two expected logs came from the deliberate dashboard-RPC failure used to test unavailable and recovery status. Checked live Odoo values, synthetic provenance, 30/90/full chart ranges, accessible dates, same-name display with a changed company ID, company-bound resets, and rejection of a delayed old forecast snapshot. |
| 400-day plot sizing regression | **Passed at desktop, tablet, and mobile** | After 30↔Full toggles, plot axes used **86%** of figure width on desktop (742.66px panel, 674.66px SVG, 675px viewBox, 602.69px axes), **86%** on tablet (756px panel, 688px SVG/viewBox, 616px axes), and **71%** on mobile (364px panel, 318px SVG/viewBox, 234.82px axes). All exceed the 68% browser assertion. The stale 260px viewBox no longer recurs after range changes. |
| Viewport checks | **Passed** | Desktop 1440×1000, tablet 1024×900, and mobile 390×844. Inventory columns remain available through the labeled horizontal-scroll table on mobile. |
| Static checks and Docker Compose configuration | **Passed** | Python compileall, `node --check scripts/qa_dashboard_browser.mjs`, `docker compose config --quiet`, and `git diff --check` |

The browser run used only the local demo database `autostock_phase2_demo`. Its five labeled automotive products had on-hand quantities of 48 front brake pads, 8 oil filters, 0 spark plugs, 15 12V batteries, and 4 cabin air filters. These are explicitly synthetic QA records, not business data or demand observations. For the 400-point chart regression, Playwright expanded the synthetic RPC response in memory; those additional points were not written to Odoo.

## Screenshot evidence

Screenshots were captured directly to this repository using local Playwright/Chromium. Each is an actual authenticated Odoo screen with synthetic demo inventory. No credentials or confidential data appear in the captures.

| View | Dashboard and inventory cards | Completed synthetic forecast and chart | Inventory data details |
|---|---|---|---|
| Desktop, 1440×1000 | [Dashboard](screenshots/phase2-5/phase2-5-dashboard-desktop.jpg) | [Forecast](screenshots/phase2-5/phase2-5-forecast-desktop.jpg) | [Inventory](screenshots/phase2-5/phase2-5-inventory-desktop.jpg) |
| Tablet, 1024×900 | [Dashboard](screenshots/phase2-5/phase2-5-dashboard-tablet.jpg) | [Forecast](screenshots/phase2-5/phase2-5-forecast-tablet.jpg) | [Inventory](screenshots/phase2-5/phase2-5-inventory-tablet.jpg) |
| Mobile, 390×844 | [Dashboard](screenshots/phase2-5/phase2-5-dashboard-mobile.jpg) | [Forecast](screenshots/phase2-5/phase2-5-forecast-mobile.jpg) | [Inventory](screenshots/phase2-5/phase2-5-inventory-mobile.jpg) |

The [mobile navigation capture](screenshots/phase2-5/phase2-5-navigation-mobile.jpg) shows the open drawer and visible keyboard focus state.

The 400-day Full-history screenshots show the corrected responsive plot width at all tested sizes:

| Viewport | Actual Odoo screenshot |
|---|---|
| Desktop, 1440×1000 | [Full-history chart](screenshots/phase2-5/phase2-5-forecast-full-400-desktop.jpg) |
| Tablet, 1024×900 | [Full-history chart](screenshots/phase2-5/phase2-5-forecast-full-400-tablet.jpg) |
| Mobile, 390×844 | [Full-history chart](screenshots/phase2-5/phase2-5-forecast-full-400-mobile.jpg) |

All 400-observation extensions were applied only to the browser response fixture and were not written to Odoo. The captures also verify that the Full control includes all returned observations and that the date labels remain spaced.

## Comparison with the approved design

The updated screens use the concept's light surfaces, restrained violet action color, rounded white panels, status colors, left navigation, KPI cards, forecast chart, stock-health view, and inventory table. The tablet layout now stacks forecast and stock-health panels once the Odoo content area becomes too narrow for two readable columns. On mobile, the side rail becomes a keyboard-accessible drawer, KPI cards reflow, chart controls wrap, and the inventory table keeps all fields available through horizontal scrolling.

The concept is an illustrative target, not an application screen. Its AI recommendation cards, forecast-accuracy KPI, generated report action, supplier/purchasing navigation, and reorder actions are not implemented product behavior and therefore are not shown as if they worked. The current page presents only installed Odoo inventory fields and the existing evaluated forecast pipeline. The native Odoo header also remains visible instead of being replaced by the concept's generic top bar. The demo company currently has Odoo's default logo; the workspace uses the active company's own logo when one is configured. The Full chart now spaces three date ticks across long histories; the exact history start/end remain available in the chart's accessible label and history details.

## Remaining work and limitations

- The synthetic forecast is labeled and deterministic. These checks do not establish real-world forecasting accuracy, calibrated uncertainty, or business value.
- Mobile inventory uses horizontal scrolling to preserve the full Odoo data table; a narrow screen cannot display every column at once.
- Browser evidence covers Chromium at the listed viewport sizes. Manual assistive-technology, Firefox/Safari, and physical-device review remains outstanding.
- Report generation, purchasing/replenishment proposals, onboarding beyond the empty-state guidance, company branding settings, backup/restore procedures, and other release criteria remain planned or require their own verification.
- Production readiness remains unverified. This PR should be reviewed as a dashboard and usability milestone only.

## Recommended next steps

1. Review the captured screens and approve the dashboard interaction model before Phase 3.
2. Build purchasing/replenishment only against real Odoo records, existing company rules, explicit user review, and permission tests.
3. Continue desktop, tablet, mobile, accessibility, installation/upgrade, and operations checks with every feature phase; track issue #7 release gates separately from phase completion.
