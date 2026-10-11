# Issue #34 — Gate 7 Forecasts workspace QA

## Scope

This branch adds the real, authenticated Forecasts workspace and exact-run detail. It uses stored Odoo forecast runs and existing risk/replenishment calculations. The screen is read-only; it does not create, queue, review, approve, or purchase. The approved dashboard design system and completed Dashboard, Inventory, Warehouses and Suppliers screens remain intact apart from routing their Forecasts navigation item to the new route.

## Implementation and data boundaries

- `GET /autostock/api/v1/forecasts` returns exact company-scoped counts, filters and bounded server-side pages; users can search by saved part name or SKU and filter by warehouse, horizon, run status, review state and source.
- `GET /autostock/api/v1/forecasts/{run_id}` returns the exact saved run with source dates, cutoff, company/warehouse scope, stored observations and returns, forecast points, UoM, method, baseline, holdout and evaluation details.
- Real delivery history requires inventory and Sales access. Stock-only users see synthetic showroom examples only, with no real-run count or metadata. Standard Odoo ACLs and record rules remain active; the implementation does not call `sudo()`.
- Current restock eligibility is explained by calling the existing `autostock.inventory.risk.get_risk_data` service for the exact part and warehouse. React does not calculate forecasts, evaluation values or reorder quantities.
- The chart separates completed deliveries, returned units and future estimates, marks “Forecast starts”, and labels its range as heuristic. The copy explains that fulfilled sales are not unconstrained demand and MAE is not an accuracy percentage.
- The detail keeps synthetic examples visibly separate from operational history. No buying or forecast-write actions are exposed.

## Automated results

| Check | Result |
| --- | --- |
| `python -m pytest -q` | Passed: 38 tests |
| `python -m compileall -q addons ml scripts tests` | Passed |
| Synthetic forecast evaluation | Passed: 6 labeled offline fixture series evaluated. These are test fixtures, not Atlas or customer accuracy evidence. |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm run test:unit` | Passed: 8 tests, including first forecast point/range preservation and Odoo/ISO/date-only date handling |
| `npm run test:contract` | Passed: 15 tests |
| `npm run test:browser` | Passed: 31 tests. Includes chart data bound to the first API prediction, desktop/mobile Saved date formatting, tablet table-header wrapping, read-only behavior, server filters, permission/no-result/error states and responsive navigation. |
| `npm run build` | Passed: production Vite build |
| Local Odoo 19 + PostgreSQL 16 integration run | Passed against a fresh `autostock_gate7_pr35_test` database: **57 actual Odoo test cases, 0 failures, 0 errors**. Odoo's broader stats line reports 71 tests. The isolated PostgreSQL data directory used `tmpfs`; the test-only container and network were removed afterward, and no named volumes were created. |
| GitHub Actions | The required Python, frontend and Odoo integration jobs run for every PR update; use PR #35's check status for the current commit-specific result. |

Forecast chart regression coverage verifies that the final observed point anchors the line while the first future point retains its saved units and heuristic bounds. Browser tests verify those first future values against the Forecasts detail API. Date regression coverage handles Odoo's UTC-naive datetime string, ISO values with and without offsets, timezone conversion, stable date-only labels, and invalid values.

## Local Docker and showroom recovery

Docker Desktop was stopped because startup failed while clearing stale Docker Model Runner and secrets-engine Unix socket endpoints. I preserved the socket files by moving the affected runtime directories aside and disabled Docker AI inference in Docker Desktop settings after saving a settings backup. The preserved items remain under `%LOCALAPPDATA%\Docker\run-recovery-preserved-20261011-215224`, `%LOCALAPPDATA%\Docker\run-recovery-preserved-20261011-215327`, and `%LOCALAPPDATA%\docker-secrets-engine-recovery-preserved-20261011-215327`; the settings backup is `%APPDATA%\Docker\settings-store.json.pre-g7-recovery-20261011-215224`.

Docker Desktop now reports `running`. The Atlas showroom Odoo container is running and its PostgreSQL container is healthy. The existing Atlas showroom filestore and PostgreSQL volumes remain present. All pre-existing AutoStock containers and volumes remained visible after recovery and after the isolated integration run. `docker_data.vhdx` remained the same size in the before/after observations: 44,280,315,904 bytes. No showroom database, database file, filestore, or pre-existing Docker volume was removed, reset, or used by the isolated integration tests.

## Live Atlas browser QA and screenshots

The authenticated Atlas Auto Distribution showroom was verified through the live React browser and Odoo API. The capture selected completed, reviewed forecast run `12` for Engine Oil Filter, opened its exact run detail, and verified the rendered chart's first future day, prediction and heuristic bounds against the API response. Saved timestamps were checked in the authenticated user's `Africa/Casablanca` timezone. Captures checked page overflow and recorded **0 browser page errors, 0 console errors and 0 failed AutoStock API responses**.

Actual live screenshots are committed under `docs/qa/screenshots/issue-34-gate-7/`:

| View | Screenshot |
| --- | --- |
| Forecast list, desktop (1440px) | [forecasts-overview-1440.png](screenshots/issue-34-gate-7/forecasts-overview-1440.png) |
| Forecast list, tablet (1024px) | [forecasts-overview-1024.png](screenshots/issue-34-gate-7/forecasts-overview-1024.png) |
| Forecast list, mobile (390px) | [forecasts-overview-390.png](screenshots/issue-34-gate-7/forecasts-overview-390.png) |
| Completed and reviewed run with evaluation disclosure open, desktop | [forecast-reviewed-detail-evaluation-open-1440.png](screenshots/issue-34-gate-7/forecast-reviewed-detail-evaluation-open-1440.png) |
| Same run detail, tablet | [forecast-reviewed-detail-evaluation-open-1024.png](screenshots/issue-34-gate-7/forecast-reviewed-detail-evaluation-open-1024.png) |
| Same run detail, mobile | [forecast-reviewed-detail-evaluation-open-390.png](screenshots/issue-34-gate-7/forecast-reviewed-detail-evaluation-open-390.png) |
| Live no-results state, desktop | [forecasts-no-results-1440.png](screenshots/issue-34-gate-7/forecasts-no-results-1440.png) |
| Live unreviewed forecast state, desktop | [forecasts-real-unreviewed-1440.png](screenshots/issue-34-gate-7/forecasts-real-unreviewed-1440.png) |

Two live states were unavailable: Atlas currently has no real completed-delivery forecast with insufficient history, and no separate restricted Atlas account is configured for browser capture. The browser suite still covers restricted access using isolated API fixtures; that fixture is not represented as a live screenshot.

## Remaining review note

No real-business forecasting accuracy or commercial-readiness claim is made.
