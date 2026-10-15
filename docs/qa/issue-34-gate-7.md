# Issue #34 — Gate 7 Forecasts workspace QA

## Scope

This update keeps the work within Gate 7. Forecasts opens on **By part**, while **Saved run history** remains available for every saved record and all existing evidence. The screen is read-only and reuses saved Odoo forecasts and the current risk/replenishment service. The forecast engine, dashboard, Inventory, Warehouses, and Suppliers are unchanged.

## Employee-usability review follow-up

- Odoo returns the linked product's `display_name` with `display_default_code=False` for the Forecasts overview, history, and detail. SKU remains in its own field, and Odoo still supplies variant-specific names. Saved run IDs and prediction values are unchanged.
- Employee-facing totals say **About … expected** and omit redundant trailing zeroes at the Odoo unit's displayed precision. The saved total in the API stays exact; fractional units keep their useful precision. No reorder quantity or forecast calculation changed.
- The chart description now identifies the gray history line and purple dashed estimate line. The warehouse selector says **All locations** and its accessible help explains that warehouse-specific and company-wide forecasts are included.
- Focused regressions cover Odoo list/group/detail product labels and separate SKUs, fractional and whole-unit display, the chart description, and the warehouse option/help.

## Employee-first behavior and data boundaries

- `GET /autostock/api/v1/forecasts/parts` groups the complete company-visible real forecast set by stable product and warehouse IDs, then applies server-side search, warehouse selection, and pagination. The page shows its result page without implying a catalog-wide total.
- Each 7/30/60-day control selects the latest saved run for that exact part and warehouse. A failed, pending, or unreviewed newest run stays selected; review status does not imply restock eligibility. Older records remain in Saved run history.
- A total and exact future date range are shown only when the selected completed run has a unit of measure and the stored daily predictions cover every expected calendar day. Totals are the sum of those stored values, rounded at the product unit's precision. Missing or partial series show an explanation and no total.
- Synthetic showroom examples remain separate from real product/warehouse groups and appear only in Saved run history. Matching SKUs do not merge synthetic examples with operational records.
- Real delivery forecasts and details require the existing inventory and Sales access. Odoo ACLs, record rules, company scope, and selected warehouse scope remain active; the implementation does not use `sudo()`.
- Forecast detail leads with the part, warehouse, period, unit, saved date range, past deliveries, and a plain-language restock eligibility sentence. Source cutoff, saved history coverage, method, evaluation, assumptions, limitations, and other technical evidence remain available under **How was this estimated?**
- React does not calculate forecasts, accuracy, or reorder quantities. The chart uses saved observations and prediction points; the restock explanation calls the existing Odoo risk service.

## Automated results

| Check | Result |
| --- | --- |
| `python -m pytest -q` | Passed: 38 tests |
| `python -m compileall -q addons ml scripts tests` | Passed |
| Offline forecast evaluation | Passed: 6 labeled synthetic fixture series evaluated for a 30-day holdout. This is test evidence, not Atlas/customer accuracy evidence. |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm run test:unit` | Passed: 10 tests |
| `npm run test:contract` | Passed: 16 tests, including estimate completeness and the saved-parts contract |
| `npm run test:browser` | Passed: 35 tests across Dashboard, Inventory, Warehouses, Suppliers, and Forecasts; includes server filters, company switching, detail evidence, partial-series handling, timezone formatting, employee copy, navigation, and desktop/tablet/mobile layouts |
| `npm run build` | Passed: production Vite build |
| Odoo 19 + PostgreSQL 16 integration suite | Passed: **60 actual test cases, 0 failures, 0 errors**. Odoo's broader statistics counter reports 74 tests. The isolated database ran in a disposable Compose project with no showroom data attached. Its test containers, network, and project-owned volumes were removed; the named showroom volumes remain. |
| GitHub Actions | Passed: [run 38187577308](https://github.com/MouhssineElBoumshouli/autostock-ai/actions/runs/38187577308) on code commit `f8c49f4`; Python, React frontend, and Odoo 19 integration jobs succeeded. |

The Odoo integration coverage includes a 1,002-run grouped catalog, server-side pagination/search, the newest failed/unreviewed run, no history, one-day and missing-day series, exact saved daily totals/date boundaries, ended estimate windows, demo/real separation, Sales-restricted access, and company/warehouse isolation. The >1,000 catalog integration case passed; its warmed API response grouped the 25 requested product/warehouse groups in under 0.1 seconds in the isolated run.

## Live Atlas browser QA and screenshots

The authenticated Atlas Auto Distribution showroom was opened in the React app through the existing Odoo session. The live capture used Atlas part `AT-BRK-001` at **Atlas Central Warehouse**, a completed saved 30-day run for **2026-10-10 through 2026-11-08**. The visible title is `Front Brake Pad Set`, with the SKU shown once beneath it; the total is presented as an estimate with unnecessary zeroes removed. The unfiltered first page returned four company-visible product/warehouse groups; the capture also searched the selected SKU, waited for the matching Odoo response, and verified the exact part/warehouse result and unchanged saved total before opening its detail. Saved run history retained the selected real record.

The capture checked page overflow at 1440px, 1024px, and 390px. It recorded **0 browser page errors, 0 console errors, and 0 failed AutoStock API responses**. Screenshots show the real By part list, exact-run detail, and Saved run history at all three sizes:

| View | Desktop (1440px) | Tablet (1024px) | Mobile (390px) |
| --- | --- | --- | --- |
| By part, live Atlas records | [PNG](screenshots/issue-34-gate-7-employee-first/forecasts-by-part-30-day-1440.png) | [PNG](screenshots/issue-34-gate-7-employee-first/forecasts-by-part-30-day-1024.png) | [PNG](screenshots/issue-34-gate-7-employee-first/forecasts-by-part-30-day-390.png) |
| Saved estimate detail | [PNG](screenshots/issue-34-gate-7-employee-first/forecast-estimate-detail-1440.png) | [PNG](screenshots/issue-34-gate-7-employee-first/forecast-estimate-detail-1024.png) | [PNG](screenshots/issue-34-gate-7-employee-first/forecast-estimate-detail-390.png) |
| Saved run history | [PNG](screenshots/issue-34-gate-7-employee-first/forecast-saved-history-1440.png) | [PNG](screenshots/issue-34-gate-7-employee-first/forecast-saved-history-1024.png) | [PNG](screenshots/issue-34-gate-7-employee-first/forecast-saved-history-390.png) |

## Local Docker and showroom recovery

Docker Desktop had stopped while clearing stale Docker Model Runner and secrets-engine Unix socket endpoints. I preserved the socket files by moving the affected runtime directories aside and disabled Docker AI inference in Docker Desktop settings after saving a settings backup. The preserved items remain under `%LOCALAPPDATA%\Docker\run-recovery-preserved-20261011-215224`, `%LOCALAPPDATA%\Docker\run-recovery-preserved-20261011-215327`, and `%LOCALAPPDATA%\docker-secrets-engine-recovery-preserved-20261011-215327`; the settings backup is `%APPDATA%\Docker\settings-store.json.pre-g7-recovery-20261011-215224`.

Docker Desktop is running. The Atlas showroom Odoo container is running and its PostgreSQL container is healthy. The Atlas Odoo process was restarted to load the updated Forecast response labels; the database and filestore volumes were not changed. `autostock_ai_showroom_filestore` and `autostock_ai_showroom_postgres` remain present. No showroom database, database file, filestore, or named Docker volume was removed, reset, or attached to the isolated test environment. `docker_data.vhdx` remained the same size in the before/after observations: 44,280,315,904 bytes.

## Remaining limitations

The Atlas showroom is demonstration data. These checks do not establish forecast accuracy for a real business, production readiness, or readiness for purchasing automation. A separate restricted Atlas account is not configured for live screenshots; restricted access is covered by Odoo integration and browser contract tests.

## Issue #59 follow-up — current-stock scope in forecast details

For a saved real forecast, the current-stock snapshot now uses the selected warehouse context when the run is warehouse-scoped. A company-wide run continues to use company-wide stock. The disclosure label names the scope as `Current stock — <warehouse>` or `Current stock — company-wide`. Forecast calculations, history, reviews, and freshness rules are unchanged.

The Odoo HTTP regression creates one shared SKU with four units at Atlas Central and eleven at South Depot, then reads both warehouse forecast details and the company-wide detail. It verifies on-hand and projected stock of 4, 11, and 15 respectively. The Playwright regression verifies both scope labels in the detail disclosure.

| Check | Result |
|---|---|
| `python -m pytest -q` | Passed: 105 tests. Windows emitted non-fatal pytest temporary-directory cleanup warnings (`WinError 145`). |
| `python -m compileall -q addons ml scripts tests` | Passed. |
| `npm run lint` / `npm run typecheck` | Passed. |
| `npm run test:unit` / `npm run test:contract` | Passed: 10 unit tests and 16 contract tests. |
| `npm run test:browser` | Passed: 37 tests, including the new company-wide/warehouse scope-label regression. |
| `npm run build` | Passed: production Vite build. |
| Odoo 19 + PostgreSQL 16 focused integration test | Passed: `odoo.tests.result` reports 0 failures, 0 errors of 1 actual test. It ran in a fresh temporary database and isolated network with `--test-tags=/autostock_ai:TestAutoStockForecastApi.test_forecast_detail_current_stock_matches_warehouse_or_company_scope`. |
| Full local Odoo addon suite | Not completed. The run was stopped during the existing Moroccan importer history audit before it reached the forecast API tests; no full-suite pass is claimed. |

The temporary PostgreSQL data used tmpfs. The cached Odoo image declares `/var/lib/odoo` as a Docker volume; two anonymous volumes created by the temporary test containers were confirmed unattached and removed. The final Docker volume inventory matches its recorded pre-test inventory, and no test containers or networks remain. No showroom database, environment credentials, or named showroom volumes were used or changed.
