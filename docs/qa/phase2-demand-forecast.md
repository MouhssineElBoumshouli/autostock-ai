# Phase 2: demand forecast validation

**Run date:** 2026-10-09
**Branch:** `codex/phase2-demand-forecast`
**Scope:** connect the evaluated forecasting pipeline to Odoo with auditable demand provenance, access control, bounded background work, and a responsive forecast view. This PR addresses linked-return leakage and horizon-aligned evaluation. It does not add purchasing, stock mutation, or other decision tools.

The commercial-readiness charter ([issue #7](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/7)) and premium UI/UX requirements ([issue #8](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/8)) remain cross-phase standards. This PR adds explicit source/evaluation limitations, preserves Odoo company and access scopes, removes the hardcoded customer identity from the dashboard, and exercises the running responsive view. It does not satisfy the complete release gates and must not be described as production-ready.

## Automated checks

| Check | Result | Evidence |
|---|---|---|
| Python tests | **21 passed** | `.\.venv\Scripts\python.exe -m pytest -q` |
| Python compilation | **Passed** | `.\.venv\Scripts\python.exe -m compileall -q addons ml scripts tests` |
| Odoo integration tests | **20 test cases; 0 failures, 0 errors** | Fresh isolated Odoo 19 (`19.0-20260926`) and PostgreSQL 16 Compose project; addon installed with `--test-enable --test-tags=/autostock_ai --stop-after-init --without-demo=true`. Odoo's `odoo.tests.stats` line reports 24 timing entries because it includes setUpClass/tearDownClass buckets for two test classes; `odoo.tests.result` reports the 20 actual test cases. |
| Docker Compose configuration | **Passed** | `docker compose config --quiet` |
| Git whitespace check | **Passed** | `git diff --check`; Git emitted only expected LF-to-CRLF working-copy notices. |
| Synthetic forecast generation | **Passed** | `.\.venv\Scripts\python.exe scripts/generate_synthetic_sales.py` generated the ignored local fixture. |
| Offline forecasting evaluation | **Completed for 6 synthetic SKUs** | Each fixture contains 210 days; requested 30-day horizon was evaluated on a 30-day chronological holdout. Results below are synthetic pipeline measurements, not business-accuracy claims. |
| GitHub Actions | **Configured for each PR update** | Separate Python and isolated Odoo 19/PostgreSQL 16 integration jobs; the latest result is shown in PR #6 checks. |

### Offline synthetic holdout results

MAE is reported in the fixture's generated demand units. Candidate selection and displayed MAE use the same single holdout, so these figures are comparison evidence, not an independent accuracy estimate.

| SKU | Selected method | Baseline MAE | Random-forest MAE |
|---|---|---:|---:|
| `DEMO-AF-331` | `trailing_mean_7` | 2.4525 | 2.4138 |
| `DEMO-BP-001` | `seasonal_naive_7` | 2.8667 | 3.7252 |
| `DEMO-BR-210` | `trailing_mean_7` | 1.2003 | 1.2334 |
| `DEMO-BT-912` | `trailing_mean_7` | 0.8668 | 0.8709 |
| `DEMO-OF-203` | `trailing_mean_7` | 2.7084 | 3.5677 |
| `DEMO-SP-104` | `trailing_mean_7` | 1.3164 | 1.6718 |

Macro mean MAE was 1.90185 for the selected baselines and 2.24713 for the random forest; all six fixtures selected a baseline. This deterministic sample does not establish performance on business data. The forecast band is heuristic, not a calibrated confidence interval.

## Odoo source and return-data checks

The tests use real Odoo stock moves, return pickings, users, companies, and forecast records:

- Demand is gross completed customer delivery quantity in the product inventory UoM. Completed returns linked to deliveries in the selected history are separate audit events on their actual UTC completion day; they never subtract from or rewrite an earlier delivery and never become negative forecast demand.
- Return moves outside the requested history window or after the source cutoff are excluded. A worker integration test places a linked return in the final seven-day holdout and compares the forecast snapshot from before and after that return. Gross delivery targets, baseline/model MAE, and predictions remain identical.
- A completed return in the requested window is recorded on its own day; unit-of-measure conversion is exercised against real Odoo return moves.
- The series remains a fulfilled-sales proxy, not unconstrained demand. Odoo does not record lost demand during stockouts, and this workflow has no complete as-of history of later edits to stock moves. We do not claim point-in-time replay or leakage-free backtests for arbitrary later source-record edits.
- Quotations, confirmed-but-unshipped orders, canceled orders, and moves completed after the source cutoff are excluded.
- Company-specific products, shared products, and users with company and stock/sales access are tested. ORM reads stay scoped to the selected company/optional warehouse and standard Odoo ACLs and record rules remain active.
- Insufficient source coverage produces an explicit state without predictions. Direct run creation cannot bypass the validated request path. Synthetic forecasts retain labeled provenance and do not write sales or inventory events.

The scheduled worker handles at most two queued runs per invocation. Forecast requests queue work; they do not train the model in the interactive RPC.

## Forecast evaluation

The offline suite and Odoo integration suite cover 7-, 30-, and 60-day horizons, including sparse demand. Evaluation holdout length now matches the requested horizon. With the minimum 90-day history and a 60-day horizon, only 30 pre-holdout days remain; the random forest is skipped when its training examples are insufficient, and the baseline evaluation remains horizon-aligned. The UI explains that the same holdout selects the method and supplies MAE.

## Installed Odoo and browser checks

Tested the upgraded addon in the local Odoo 19 demo database at `http://127.0.0.1:8175` (PostgreSQL 16):

- The completed synthetic run displayed SKU `DEMO-BP-001`, 210 observations, a 30-day outlook, `Measured holdout 30 / 30 days`, baseline and random-forest comparison, and the explicit same-holdout limitation. Current inventory is clearly separated from the synthetic forecast.
- The demo database has zero tracked products. The dashboard displays its getting-started empty state and zero stock totals instead of fabricated inventory values. Selecting “Completed Odoo deliveries” with no tracked product leaves evaluation disabled and explains that a complete-history start date must be configured.
- The page was visually inspected against `design/dashboard-concept.png`. It carries the reference's lavender surfaces, purple accent, cards, and forecast/stock-health composition; the Odoo navigation and intentionally smaller Phase 2 workflow remain. Full concept parity and visual sign-off are still open work.
- Desktop viewport **1920×901**, tablet **768×1024**, and mobile **390×844** were checked. All three had no horizontal page overflow; tablet and mobile stack the KPI/forecast controls for their available width.
- Browser console error logs were empty after the checks.

Screenshots were visible during the browser review but the available browser capture did not export persistent files into this repository. Therefore this PR still contains **no screenshot attachments**, and the screenshot-based review required by issue #8 is pending. To add reviewable evidence on Windows:

1. Open `http://127.0.0.1:8175/odoo/action-454` and confirm the synthetic sample, `BP 001`, 30-day horizon, and `Measured holdout 30 / 30 days`.
2. Capture the dashboard at desktop **1440×1000**, tablet **768×1024**, and mobile **390×844**. For responsive sizes, use Chrome DevTools device toolbar with **Ctrl+Shift+M** and enter the dimensions.
3. Use **Win+Shift+S** and save JPEGs as `docs/qa/screenshots/phase2-forecast-desktop.jpg`, `phase2-forecast-tablet.jpg`, and `phase2-forecast-mobile.jpg`. Add them to the PR and retain screenshot-based design review as pending until they are attached.

## Remaining limits and next steps

- Results use deterministic synthetic data, not an approved business dataset. Repeated rolling-origin backtesting, bias/seasonality review, interval calibration, and business evaluation are still required.
- Odoo cannot reconstruct all historical record versions; the source snapshot is not a full as-of replay. Stockouts may also make fulfilled sales understate demand.
- Branding configuration, onboarding beyond current empty states, broader accessibility review, installation/upgrade validation across supported configurations, performance under business-scale load, and backup/restore/operational gates remain open under issues #7 and #8.
- The approved concept includes wider navigation and workflows that are intentionally outside this Phase 2 correction. Keep visual review open until the requested screenshots are attached and reviewed.
- Forecasts must not automatically trigger purchasing or change stock. Do not claim the product is production-ready until all commercial release gates have evidence.
