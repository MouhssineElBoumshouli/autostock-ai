# Issue #24 — Gate 2 interaction QA

**Date:** 2026-10-10
**Branch:** `rebuild/reference-first-interactions`
**Scope:** Interactions on the approved Gate 1 Dashboard, using typed local development fixtures only.

## Result

Added the Gate 2 interaction layer without changing the approved Dashboard composition or connecting to Odoo. Search opens with Ctrl/Cmd+K, filters by part name, SKU, category, supplier, and vehicle, and supports arrow-key selection and Enter to open a product quick view. The search dialog now exposes its title and description through its accessible dialog context and clears its query when closed.

Forecast controls switch among fixture parts and 7/30/60-day views. The chart responds to pointer/touch position and arrow keys and reports the selected point and expected range. Inventory health opens a details sheet. Insight actions navigate to the corresponding Dashboard fixture area. Restock priority/category filters work at desktop and mobile widths; recommendation details include supplier, lead time, current fixture quantities, a plain-language reason, and a disclosure that explains how the illustrative value should be interpreted. Purchase-order actions remain unavailable.

Desktop navigation can collapse and expand. Mobile navigation opens in a sheet and closes after selecting a Dashboard section. Header date range, notification and profile menus have explanatory fixture content. Loading, empty, and error fixture states provide recovery actions. Transitions are subtle and reduced-motion preferences suppress them.

All data remain typed local development fixtures. The `Visual preview · fixture data` label and fixture explanations are retained. Playwright observed **zero** `/autostock/api/` requests and **zero** page or console errors across the journeys. This is interaction-prototype evidence only; it is not evidence of Odoo behavior, real inventory, business accuracy, or purchasing functionality.

## Screenshots

Captured from the running Vite application by Playwright:

| State | Capture |
| --- | --- |
| Search open, desktop 1440 × 1000 | [search-open-1440.png](screenshots/issue-24-gate-2/search-open-1440.png) |
| Forecast product/horizon and chart tooltip, tablet 1024 × 820 | [forecast-interaction-1024.png](screenshots/issue-24-gate-2/forecast-interaction-1024.png) |
| Restock detail drawer with calculation disclosure, desktop 1440 × 1000 | [restock-detail-drawer-1440.png](screenshots/issue-24-gate-2/restock-detail-drawer-1440.png) |
| Mobile navigation open, mobile 390 × 844 | [mobile-navigation-390.png](screenshots/issue-24-gate-2/mobile-navigation-390.png) |

## Checks

| Check | Result |
| --- | --- |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm run test:unit` | Passed, 3 tests |
| `npm run test:contract` | Passed, 5 tests |
| `npm run test:browser -- --workers=2` | Passed, 8 Playwright journeys. Covers 1440, 1024, and 390 CSS-pixel layouts; no horizontal overflow; Ctrl/Cmd+K search and keyboard result selection; quick view; forecast controls, chart hover/keyboard; restock filters and detail disclosure; mobile navigation; health and insight actions; date range, profile, notifications, sidebar collapse; loading/empty/error recovery; reduced motion; zero Odoo API requests and browser errors. |
| Screenshot capture | Passed, all four requested states captured and reviewed. |

The browser checks use Chromium against local fixtures. No Odoo instance, business data, external service, or purchasing workflow was used.

## Remaining scope

- Inventory, Forecasts, Restock, Reports and Assistant are not implemented as separate screens.
- Restock values, chart points, supplier details, notifications, and insights are preset development fixtures, not calculated or validated business results.
- Odoo authentication, permissions, company/warehouse scope, live data, purchasing, and backend/API integration remain for a later approved gate.
