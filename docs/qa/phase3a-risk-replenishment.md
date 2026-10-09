# Phase 3A: stock-risk and reorder guidance

**Branch:** `codex/phase3a-stock-risk-recommendations`
**Scope:** GitHub Issue #11 only. Phase 3B and 3C remain out of scope.
**Product standards:** commercial-readiness Issue #7 and premium UX Issue #8 apply; completing this milestone does not mean AutoStock AI is production-ready.

## What changed

- Added a bounded Odoo ORM service for tracked products, active-company stock, warehouse receipt projections, reordering rules, supplier terms and eligible forecast evidence. Reads use the logged-in user's ACLs and record rules; no business-data `sudo()` is used.
- Added risk states for out of stock, below trigger, at trigger, over target, policy review and slow-moving only when a fresh, reviewed history covers the full 90-day inactivity window.
- Added deterministic, read-only top-up quantities. Odoo's projected stock already includes scheduled moves; confirmed customer deliveries are reconciled so overlapping forecast demand is not subtracted twice. Reorder quantity is the verified target gap, floored by a separately configured supplier MOQ and rounded up to the native replenishment multiple.
- Added an AutoStock MOQ field to supplier terms. Odoo's native `min_qty` remains a supplier price break and is never interpreted as MOQ.
- Forecasts contribute demand only when they are completed, real, manager-reviewed, fully evaluated, fresh, exact-match for company/product/warehouse, and cover every day through the selected lead time. Missing, stale, unsupported, inaccessible or incomplete evidence is explained; synthetic forecast runs are excluded.
- Added company/warehouse, supplier, status, part and history-date filters; evidence disclosure; desktop table and mobile-card layouts; and explicit empty, access, bounded-result, fallback and read-only states.
- Added an idempotent fixture seeder guarded to database `autostock_phase3a_qa`. It creates five `[SYNTHETIC QA]` automotive parts, synthetic supplier terms and Odoo stock/reorder records. It creates no customer sales history and no forecast run.

## Verification

| Check | Result |
|---|---|
| Python tests | **38 passed** (`python -m pytest -q`) |
| Python compilation | **Passed** (`python -m compileall -q addons ml scripts tests`) |
| JavaScript syntax | **Passed** for both browser QA scripts (`node --check`) |
| Fresh Odoo 19 addon install with PostgreSQL 16 integration tests | **Passed**; 0 failures and 0 errors across 28 addon tests |
| Docker Compose configuration | **Passed** (`docker compose config --quiet`) |
| Synthetic offline 30-day forecast evaluation | **6/6 evaluated**; mean baseline MAE **1.90185**, selected-model MAE **2.24713** |
| Actual Odoo browser QA: desktop 1440×1000, tablet 1024×900, mobile 390×844 | **Passed**; all 5 synthetic scenarios and filters verified; no page overflow |
| Forecast-history date controls | **Passed**; rendered input widths 139 px desktop, 337 px tablet, 149 px mobile |
| Browser console and uncaught page errors | **0 errors** across all three viewports |

The offline evaluation uses the repository's labeled synthetic fixture only. Five products selected `trailing_mean_7` and one selected `seasonal_naive_7`. The values are pipeline-check results, not evidence of business accuracy: evaluation uses one chronological 30-day holdout, and heuristic ranges are not calibrated confidence intervals.

The rendered risk scenarios are also synthetic and come from real Odoo stock, reorder rules and supplier terms in the isolated QA database: zero-stock brake pads receive a 12-unit policy top-up; oil filters below trigger receive 24 units after supplier pack rounding; spark plugs at trigger and alternators above target receive no quantity; cabin filters without a reorder policy receive no quantity. No sales history or synthetic forecast run was seeded.

Odoo transaction tests include a user permitted for two companies, company-specific and shared products, and a second warehouse within one company. They verify that company A's selected warehouse, its other warehouse, and company B each return only their own shared-product stock, with no foreign-company products. Another integration case builds and reviews an eligible real delivery forecast and checks that a committed future customer delivery is not deducted twice.

## Browser evidence

All images are screenshots captured from the local Odoo 19 application with Microsoft Edge and Playwright. They show only the database-guarded synthetic fixture; no passwords or confidential records are included.

| Viewport | Dashboard | Risk overview | Open explanation |
|---|---|---|---|
| Desktop, 1440×1000 | [Dashboard](screenshots/phase3a/phase3a-dashboard-desktop.jpg) | [Stock risks](screenshots/phase3a/phase3a-stock-risk-desktop-overview.jpg) | [Calculation and source evidence](screenshots/phase3a/phase3a-stock-risk-desktop.jpg) |
| Tablet, 1024×900 | [Dashboard](screenshots/phase3a/phase3a-dashboard-tablet.jpg) | [Stock risks](screenshots/phase3a/phase3a-stock-risk-tablet-overview.jpg) | [Calculation and source evidence](screenshots/phase3a/phase3a-stock-risk-tablet.jpg) |
| Mobile, 390×844 | [Dashboard](screenshots/phase3a/phase3a-dashboard-mobile.jpg) | [Stock risks](screenshots/phase3a/phase3a-stock-risk-mobile-overview.jpg) | [Calculation and source evidence](screenshots/phase3a/phase3a-stock-risk-mobile.jpg) |

The browser regression also exercises drawer navigation, recommendation/status filtering, supplier filtering, part search, forecast-history date filtering and clear-filter recovery; it checks the rendered width of both date inputs, the synthetic scenario quantities, no horizontal page overflow, and that no purchasing/stock mutation action is exposed.

## Visual comparison and remaining differences

The risk section follows the approved dashboard's off-white canvas, white rounded panels, restrained violet actions, semantic risk badges, active-company identity and left navigation. The existing Odoo header and authenticated client action remain in place. The risk table switches to stacked cards on narrow screens, while evidence remains available through an explicit disclosure rather than being hidden behind color or hover.

Browser inspection initially found that the forecast-history date inputs collapsed to 20 px because the fieldset legend and controls competed in one flex row. The fieldset now uses a responsive grid; browser regression confirms usable widths at desktop, tablet and mobile sizes.

The concept includes forecast-accuracy KPIs, AI recommendation cards, generated reports and purchase-order actions. These are not represented as working Phase 3A capabilities. The new page instead shows live Odoo quantities and policy, explains when forecast evidence is unavailable, and stays read-only. The native Odoo top navigation also remains visible. Full concept parity, report generation and purchasing workflows are separate reviewed work; see Issues #7 and #8 and the implementation plan.

## Boundaries and follow-up

- A missing eligible forecast uses only the configured Odoo policy baseline and does not estimate demand that is not recorded in Odoo. If policy, access, or bounded source data is unresolved, no quantity is shown.
- Forecasts are completed fulfilled-sales histories; stockouts can censor demand. A single holdout does not establish real-world accuracy, and no business accuracy claim is made here.
- Purchase is not installed in the QA database. The interface reports this and does not create an RFQ, purchase order, supplier commitment, stock move or quant.
- The budget optimizer, what-if simulation, Phase 3B/3C work, complete design parity, and the commercial release gates remain unimplemented.
