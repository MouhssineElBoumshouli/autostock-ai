# React Dashboard foundation QA

**Date:** 2026-10-10
**Branch:** `rebuild/react-shadcn`
**Scope:** GitHub Issue #20, React application foundation and the Dashboard only.

## Result

The React Dashboard ran against the separate local Odoo showroom database `autostock_showroom_demo` for the fictional Atlas Auto Distribution business. The page fetched the displayed data through the authenticated `/autostock/api/v1/` routes. The browser capture script verified live product search and a warehouse-filtered restock preview, and found zero page errors, console errors, or API failures. This capture refresh applies the focused readability polish from the latest live review while retaining the accepted layout and visual direction.

The screenshots below are actual browser captures of the Odoo-backed showroom, not frontend fixtures. They show the 64 tracked parts, current inventory-health counts, a saved delivery-based forecast preview, and five warehouse-level priority restock positions. Each restock card puts the part name, stock status, on-hand quantity, warehouse, and suggested quantity in the main scan path; supplier detail is secondary. The human product name and SKU stay separate. Forecast copy says “Next 30 days,” shows the source type, and places detailed provenance and limitations behind a keyboard-accessible information disclosure. The company has one discreet Demo environment indicator, including on mobile. Forecast and reorder values are supplied by Odoo services; the React client does not reimplement those calculations.

## Screenshots

| Viewport | Screenshot | Forecast plot width |
| --- | --- | ---: |
| Desktop, 1440 px | [dashboard-1440.png](screenshots/react-dashboard/dashboard-1440.png) | 700 px |
| Tablet, 1024 px | [dashboard-1024.png](screenshots/react-dashboard/dashboard-1024.png) | 449 px |
| Mobile, 390 px | [dashboard-390.png](screenshots/react-dashboard/dashboard-390.png) | 351 px |

Each capture passed the screenshot script's horizontal-overflow check and verified the chart SVG spans its available plot width. The 1024 px layout places supplier details beneath the part name to preserve room for the warehouse and quantity; mobile stacks the cards and alerts and uses a navigation drawer.

## Design review

The new shell follows the approved `design/dashboard-concept.png` through a compact brand rail, quiet neutral canvas, violet active state, crisp card hierarchy, four glanceable KPIs, a large demand chart, an inventory-health visualization, and prioritized restock guidance. This polish preserves that direction while making restock alerts individual cards rather than a dense row of table fields. The responsive captures keep the chart readable and the product, status, on-hand, warehouse, and suggested quantity easy to scan; supplier detail remains available with less visual weight.

This first PR intentionally has one working Dashboard. It omits the concept's forecast-accuracy claim and future workflow areas such as full Forecasts, Inventory, purchasing, reports, and an assistant. The demo database contains only one authorized company, so company selection is shown but a second live-company switch could not be demonstrated with this showroom. The browser suite tests company-switch refresh behavior with isolated fixtures; Odoo tests exercise authenticated identity, an invalid company rejection, and the standard inventory access gate. No claim of release-grade accessibility or performance audit is made here.

The old Owl/Odoo dashboard was left unchanged. This PR adds the React client alongside it; it does not perform the later cutover.

## Checks

| Check | Result |
| --- | --- |
| `npm ci` (npm 10) | Passed |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm run test:unit` | Passed, 3 tests |
| `npm run test:contract` | Passed, 5 tests |
| `npm run test:browser` | Passed, 3 tests covering 1440, 1024, 390, and 320 px layouts, forecast details, restock hierarchy, chart interaction, mobile navigation, company refresh, and product search |
| `npm run build` | Passed |
| Actual showroom screenshot and interaction capture | Passed at 1440, 1024, and 390 px; 5 live restock alerts; warehouse filter and product search passed; no browser or API errors |
| `python -m pytest -q` | Passed, 38 tests |
| `python -m compileall -q addons ml scripts tests` | Passed |
| Synthetic forecasting evaluation | Passed for 6 labeled fixture products using the existing evaluator; no accuracy claim is made from this run |
| Odoo 19 + PostgreSQL 16 addon install and integration suite | Passed in an isolated database; 38 actual test cases passed, including 7 post-install HTTP cases; the broader Odoo stats count is 46; 0 failures and 0 errors |
| `git diff --check` | Passed |

Frontend browser tests use explicit test fixtures. The three screenshots and the search/warehouse interaction check use the authenticated, locally running Odoo showroom instead. The browser capture reads local showroom credentials without logging them; no credentials are stored in the screenshots or committed.

## Running the Dashboard locally

With the local Odoo showroom running on port 8177:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/` and sign in with the local showroom's Odoo user. The default database and proxy target are listed in `frontend/.env.example`. Use the separate showroom guide for locally held credentials; do not commit those credentials.

## Remaining scope

- Add the later application screens and navigation only in their separately reviewed milestones.
- Verify company switching with a real multi-company showroom when one is available.
- Complete broader accessibility, browser/device, and operational reviews before making any commercial-readiness claim.
