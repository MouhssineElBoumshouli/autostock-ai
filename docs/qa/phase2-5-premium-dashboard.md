# Phase 2.5: premium Odoo dashboard QA

**Run date:** 2026-10-09

**Branch:** `codex/phase2-5-premium-dashboard`

**Scope:** improve the connected inventory and evaluated-forecast dashboard while retaining Odoo navigation, data, company context, and permissions. Purchasing, reporting, and other planned product capabilities remain outside this change.

The commercial-readiness charter ([issue #7](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/7)) and premium UX acceptance criteria ([issue #8](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/8)) continue to apply. This phase brings the live interface closer to the approved [dashboard concept](../../design/dashboard-concept.png); it does not satisfy the full release gates and AutoStock AI is not described as production-ready.

## Changes reviewed

- Added a responsive AutoStock workspace rail and compact context bar inside the Odoo action. Odoo's native top bar, company switcher, user menu, product records, and access controls remain in place.
- Showed the active Odoo company and its company logo through the authenticated Odoo image route.
- Added keyboard-operable mobile navigation with focus entry, focus wrapping, Escape close, and focus return. A live browser check exposed an Owl rerender timing issue; focus now lands after the drawer is rendered.
- Made chart history selection work at 30 days, 90 days, or the full available history. The SVG resizes with its container, exposes a changing accessible label, and keeps date and value ticks visible.
- Replaced the empty health visualization with an explanatory empty state and added next-step guidance when no tracked products exist.
- Removed cards that suggested tools not implemented in Odoo.
- Added an idempotent, database-guarded synthetic automotive inventory seeder and cleanup command. All seeded products are labeled `[SYNTHETIC QA]`; the script writes only those product settings and stock adjustments in the named local demo databases, and creates no customers, suppliers, sales, or purchase orders.
- Added Playwright browser QA for the installed Odoo dashboard and structural checks for connected navigation, chart controls, and absence of future-feature placeholders.

## Automated checks

| Check | Result | Evidence |
|---|---|---|
| Python tests | **22 passed** | `.venv\Scripts\python.exe -m pytest -q` |
| Python compilation | **Passed** | `.venv\Scripts\python.exe -m compileall -q addons ml scripts tests` |
| Odoo integration tests | **21 test cases; 0 failures, 0 errors** | Fresh isolated Compose project, Odoo `19.0-20260926`, PostgreSQL 16; addon installed using `--test-enable --test-tags=/autostock_ai --stop-after-init --without-demo=true`. `odoo.tests.result` reports 21 cases; the stats line includes four class setup/teardown timing entries. The project volumes and container were removed after the run. |
| Synthetic forecast evaluation | **Completed for 6 labeled synthetic SKUs** | Generated 210-day histories and evaluated a 30-day chronological holdout with `python -m ml.evaluate ... --days 30`. This verifies pipeline execution only; it is not evidence of business forecast accuracy. |
| Odoo browser QA | **Passed; 0 console/page errors** | Chromium against the running local Odoo 19 demo database. Checked live Odoo values, synthetic provenance, navigation, 30/90/full chart ranges and accessible labels, inventory detail form and return navigation, mobile keyboard focus behavior, and horizontal overflow. |
| Viewport checks | **Passed** | Desktop 1440×1000, tablet 1024×900, and mobile 390×844. Inventory columns remain available through the labeled horizontal-scroll table on mobile. |
| Docker Compose configuration | **Passed** | `docker compose config --quiet` |

The browser run used only the local demo database `autostock_phase2_demo`. Its five labeled automotive products had on-hand quantities of 48 front brake pads, 8 oil filters, 0 spark plugs, 15 12V batteries, and 4 cabin air filters. These are explicitly synthetic QA records, not business data or demand observations.

## Screenshot evidence

Screenshots were captured directly to this repository using local Playwright/Chromium. Each is an actual authenticated Odoo screen with synthetic demo inventory. No credentials or confidential data appear in the captures.

| View | Dashboard and inventory cards | Completed synthetic forecast and chart | Inventory data details |
|---|---|---|---|
| Desktop, 1440×1000 | [Dashboard](screenshots/phase2-5/phase2-5-dashboard-desktop.jpg) | [Forecast](screenshots/phase2-5/phase2-5-forecast-desktop.jpg) | [Inventory](screenshots/phase2-5/phase2-5-inventory-desktop.jpg) |
| Tablet, 1024×900 | [Dashboard](screenshots/phase2-5/phase2-5-dashboard-tablet.jpg) | [Forecast](screenshots/phase2-5/phase2-5-forecast-tablet.jpg) | [Inventory](screenshots/phase2-5/phase2-5-inventory-tablet.jpg) |
| Mobile, 390×844 | [Dashboard](screenshots/phase2-5/phase2-5-dashboard-mobile.jpg) | [Forecast](screenshots/phase2-5/phase2-5-forecast-mobile.jpg) | [Inventory](screenshots/phase2-5/phase2-5-inventory-mobile.jpg) |

The [mobile navigation capture](screenshots/phase2-5/phase2-5-navigation-mobile.jpg) shows the open drawer and visible keyboard focus state.

## Comparison with the approved design

The updated screens use the concept's light surfaces, restrained violet action color, rounded white panels, status colors, left navigation, KPI cards, forecast chart, stock-health view, and inventory table. The tablet layout now stacks forecast and stock-health panels once the Odoo content area becomes too narrow for two readable columns. On mobile, the side rail becomes a keyboard-accessible drawer, KPI cards reflow, chart controls wrap, and the inventory table keeps all fields available through horizontal scrolling.

The concept is an illustrative target, not an application screen. Its AI recommendation cards, forecast-accuracy KPI, generated report action, supplier/purchasing navigation, and reorder actions are not implemented product behavior and therefore are not shown as if they worked. The current page presents only installed Odoo inventory fields and the existing evaluated forecast pipeline. The native Odoo header also remains visible instead of being replaced by the concept's generic top bar. The demo company currently has Odoo's default logo; the workspace uses the active company's own logo when one is configured.

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
