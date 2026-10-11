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
| `python scripts/generate_synthetic_sales.py` then `python -m ml.evaluate ml/output/synthetic_daily_sales.csv --days 30 --output "$env:TEMP\autostock-gate7-forecast-evaluation.json"` | Passed: 6 synthetic series evaluated. This is an offline test fixture, not Atlas or customer accuracy evidence. |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm run test:unit` | Passed: 3 tests |
| `npm run test:contract` | Passed: 15 tests |
| `npm run test:browser` | Passed: 29 tests, including Forecasts desktop/tablet/mobile, filters, exact detail, read-only behavior, restricted/no-result states, reduced motion and mobile navigation |
| `npm run build` | Passed: Vite production build |
| Odoo 19 + PostgreSQL 16 integration run in GitHub Actions | **Passed: 57 actual Odoo test cases, 0 failures, 0 errors.** Odoo's broader stats line reports 71 tests; 57 is the actual database-loading test-case count. Run [38155713172](https://github.com/MouhssineElBoumshouli/autostock-ai/actions/runs/38155713172) ran the test suite against a fresh PostgreSQL 16 database and installed the addon successfully. |
| Local Odoo 19 + PostgreSQL 16 integration run | **Blocked before Odoo started.** Docker Desktop returned HTTP 500 from its Linux engine API; after a restart, Docker Desktop remained in `stopping`, and a direct WSL command timed out (`Wsl/Service/WSAETIMEDOUT`). This local setup failure is separate from the successful isolated GitHub Actions run. |

The isolated test command was `docker compose --project-name autostock-gate7-int up --detach --wait db`, followed by `docker compose --project-name autostock-gate7-int run --rm --no-deps odoo odoo --database=autostock_gate7_test --init=autostock_ai --test-enable --test-tags=/autostock_ai --stop-after-init --without-demo=true --log-level=test`. It failed on the first command because Docker Desktop's engine did not respond successfully. No test database was created and the Atlas showroom data volume was not removed.

## Live Atlas browser QA and screenshots

**Blocked; no live screenshots are included.** At capture time, `127.0.0.1:8069` and `127.0.0.1:8177` did not respond, and the local Docker engine could not start or inspect containers. The browser suite above uses isolated typed fixtures and is not presented as a live Atlas check. The successful GitHub Actions run validates the addon and integration tests, but it does not contain the Atlas showroom database or replace visual QA against the live showroom.

The guarded capture script is `frontend/scripts/capture-forecasts-showroom.mjs`, invoked with `npm run capture:forecasts-showroom` after the Atlas showroom and frontend are available. It logs in from the ignored local credential file without printing credentials, requires the live API to identify Atlas Auto Distribution, captures actual server-returned overview/detail states at 1440, 1024 and 390 pixels, checks horizontal overflow, and fails on browser or API errors. It writes images to `docs/qa/screenshots/issue-34-gate-7/`. Run that command and the isolated Odoo test after Docker Desktop/WSL is healthy; do not treat the fixture browser tests or offline evaluation as a substitute.

## Limitations before review completion

- The local addon installation and Atlas live browser screenshots remain blocked by the host Docker/WSL failure described above. The CI addon install and Odoo integration suite passed on the PR head.
- CI also passed the Python job and the React lint, typecheck, unit, API contract, browser, and production build steps. CI does not create the missing live showroom screenshots.
- No real-business forecasting accuracy or commercial-readiness claim is made.
