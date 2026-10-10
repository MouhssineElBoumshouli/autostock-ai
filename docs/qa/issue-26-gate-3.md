# Issue #26 — Gate 3 live Dashboard QA

**Date:** 2026-10-10  
**Branch:** `rebuild/reference-first-odoo-dashboard`  
**Scope:** Connect the approved Gate 1/2 Dashboard to authenticated Odoo data. No other screens or purchasing actions were added.

## Result

The Dashboard now reads the signed-in Odoo user, allowed companies, company inventory summary, saved forecast and read-only stock-risk recommendations from `/autostock/api/v1/`. The controller calls the existing Odoo dashboard, forecast and inventory-risk services; React formats their results and does not recalculate stock, forecast or reorder quantities. API routes require an authenticated Odoo session, keep the selected company in scope, and use Odoo ACLs and record rules.

The Atlas Auto Distribution showroom was used for live browser validation. At capture time Odoo reported 64 tracked parts, 58 in stock, 6 low, 0 out of stock in the company summary, and 60 reorder suggestions across 128 stock positions. The Dashboard shows the five highest-priority positions. These are snapshot values from the local demo database, not business validation or production results. The saved forecast uses completed delivery history; returns remain separately recorded. No forecast-accuracy percentage or other accuracy claim is shown, and unavailable forecast evidence produces an explicit empty state instead of synthetic fallback data. Purchasing remains read-only.

The approved shell, card hierarchy, spacing, typography, forecast/health split, insights and recommendation table remain in place. At 390 px, recommendation facts now stack into one readable column so labels and quantities do not overlap. The desktop and tablet layout keeps the full “Reorder Suggestions” label visible. The only demo wording is the discreet “Demo environment” indicator.

## Live showroom screenshots

All captures below came from the authenticated Atlas Auto Distribution Odoo database. Screenshot capture verified no horizontal overflow, a forecast plot filling its container, five real recommendation rows, zero page or console errors, and zero failed AutoStock API responses.

| Evidence | Screenshot | Result |
| --- | --- | --- |
| Desktop | [dashboard-1440.png](screenshots/issue-26-gate-3/dashboard-1440.png) | 1440 px; chart SVG 695 px wide |
| Tablet | [dashboard-1024.png](screenshots/issue-26-gate-3/dashboard-1024.png) | 1024 px; chart SVG 432 px wide |
| Mobile | [dashboard-390.png](screenshots/issue-26-gate-3/dashboard-390.png) | 390 px; chart SVG 307 px wide; recommendation labels and values remain separate |
| Global search | [search-open-1440.png](screenshots/issue-26-gate-3/search-open-1440.png) | Searched a live showroom SKU; keyboard selection opened product details |
| Forecast control | [forecast-interaction-1440.png](screenshots/issue-26-gate-3/forecast-interaction-1440.png) | Switched to 7 days and received the matching Odoo forecast response |
| Recommendation detail | [reorder-detail-1440.png](screenshots/issue-26-gate-3/reorder-detail-1440.png) | Live stock, supplier terms, calculation explanation and read-only state |
| Mobile navigation | [mobile-navigation-390.png](screenshots/issue-26-gate-3/mobile-navigation-390.png) | Navigation drawer opened at 390 px with unavailable sections labeled |

The reference comparison retains the approved sidebar and header proportions, five KPI cards, large forecast chart, health visualization, three insight cards and recommendation table. Truthful live values replace the approved concept’s unsupported trend percentages, synthetic forecast figures and “Forecast Accuracy” card. Remaining visual differences are content-driven: Odoo product/company labels and currently available showroom facts replace concept-only sample labels.

## Checks

| Check | Result |
| --- | --- |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm run test:unit` | Passed, 3 tests |
| `npm run test:contract` | Passed, 5 API contract tests |
| `npm run test:browser` | Passed, 10 Playwright tests; 1440/1024/390 layouts, keyboard search, forecast controls, reorder details, company scope, loading/empty/error states, reduced motion and mobile fact readability |
| `npm run build` | Passed |
| `python -m pytest -q` | Passed, 38 tests |
| `python -m compileall -q addons ml scripts tests` | Passed |
| Labeled synthetic forecast evaluator | Passed for 6 explicitly labeled demo products; this is a development check, not evidence of business forecast accuracy |
| Odoo 19 addon install and tests with PostgreSQL 16 | Passed in a fresh isolated database; Odoo result line reported 0 failures and 0 errors across 42 test cases. The separate broader Odoo statistics line reported 50 tests. The addon ran 11 post-install HTTP tests, including company isolation, search, session, forecast, dashboard and product detail coverage. |
| Authenticated Atlas showroom capture | Passed at 1440/1024/390 px; search, quick view, 7-day forecast, recommendation drawer and mobile navigation all passed; no browser errors or API failures |
| `git diff --check` | Passed; Git reports only its normal LF-to-CRLF conversion notice for edited frontend files on Windows |

Frontend Playwright tests use controlled API responses to check interface behavior. The committed screenshots and the authenticated capture interactions use the local Odoo showroom, and no showroom credentials are included.

## Remaining boundaries

- Only the Dashboard is connected in this gate. Other workspace sections remain unavailable and are labeled as such.
- The local showroom contains one company, so live multi-company switching was not demonstrated in the browser. Odoo integration tests use two companies, a shared product, distinct company products and a user authorized for both; Dashboard, search, restock and product detail results stayed in the selected company and warehouse scope.
- Forecast availability depends on an exact-scope completed, reviewed and evaluated Odoo forecast. The application does not fabricate forecast data or accuracy percentages.
- This validation does not establish production readiness, business forecast accuracy, or release-grade operational/accessibility coverage.

## Reproduce showroom screenshots

Start the configured local showroom on port 8177 and Vite on port 5173, then run:

```powershell
cd frontend
npm run capture:showroom
```

The script reads `.showroom/credentials.txt` locally without printing the contents. It writes screenshots to `docs/qa/screenshots/issue-26-gate-3/`.
