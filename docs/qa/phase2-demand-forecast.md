# Phase 2: demand forecast validation

**Run date:** 2026-10-09
**Branch:** `codex/phase2-demand-forecast`
**Scope:** connect the evaluated forecasting pipeline to Odoo with auditable demand provenance, access control, bounded background work, and a responsive forecast view. No purchasing, stock mutation, or other decision-tool features were added.

## Automated checks

| Check | Result | Evidence |
|---|---|---|
| Python tests | **17 passed** | `.\.venv\Scripts\python.exe -m pytest -q` |
| Python compilation | **Passed** | `.\.venv\Scripts\python.exe -m compileall -q addons ml scripts tests` |
| Odoo integration tests | **23 tests; 0 failures, 0 errors** | Fresh `autostock_phase2_ci` database; Odoo 19 (`19.0-20260926`) and PostgreSQL 16; addon installed with `--test-enable --test-tags=/autostock_ai --stop-after-init --without-demo=true`. The temporary Compose project, volumes, and generated database credentials were removed after the run. |
| Docker Compose configuration | **Passed** | `docker compose config --quiet` |
| Git whitespace check | **Passed** | `git diff --check` (Git printed expected LF-to-CRLF working-copy notices only.) |
| Synthetic forecast generation | **Passed** | `.\.venv\Scripts\python.exe scripts/generate_synthetic_sales.py` generated the ignored local fixture. |
| Offline forecasting evaluation | **Completed for 6 synthetic SKUs** | A 28-day chronological holdout was evaluated for each 210-day fixture. Results below are synthetic-only measurements, not business accuracy claims. |

### Offline synthetic holdout results

MAE is reported in each fixture's generated demand units. The single holdout is a pipeline check, not evidence of production model performance.

| SKU | Selected method | Baseline method | Baseline MAE | Random-forest MAE |
|---|---|---|---:|---:|
| `DEMO-AF-331` | `trailing_mean_7` | `trailing_mean_7` | 2.4434 | 2.5067 |
| `DEMO-BP-001` | `seasonal_naive_7` | `seasonal_naive_7` | 3.3929 | 3.6367 |
| `DEMO-BR-210` | `seasonal_naive_7` | `seasonal_naive_7` | 0.8929 | 1.2886 |
| `DEMO-BT-912` | `random_forest` | `trailing_mean_7` | 1.0548 | 0.9529 |
| `DEMO-OF-203` | `trailing_mean_7` | `trailing_mean_7` | 3.2985 | 3.6746 |
| `DEMO-SP-104` | `trailing_mean_7` | `trailing_mean_7` | 1.5135 | 1.7308 |

The simple macro averages are 2.0993 baseline MAE and 2.2984 random-forest MAE. Five fixtures selected their listed baseline; one selected the random forest. The forecast range remains heuristic, not a calibrated confidence interval.

## Odoo data and permission checks

The Odoo integration suite exercises actual Odoo records and stock workflows:

- A completed customer delivery is counted; a linked completed return is netted against its delivery day. The test changes the sale UoM and verifies conversion into the product inventory UoM.
- Quotations, confirmed-but-unshipped orders, canceled orders, and moves completed after the run cutoff are excluded.
- Requests require the expected inventory and sales permissions. Insufficient covered history persists an explicit state without predictions, and direct forecast-run creation cannot bypass the validated request path.
- Two companies have separate products and stock histories plus a shared product. A user enabled for both receives the right company-specific demand and the shared product's company-specific delivery total; each company's forecast choices contain only its own product and the shared product. A user restricted to Company B cannot see Company A forecast runs. Standard Odoo ACLs and record rules remain enabled.
- Synthetic work persists observations, forecast points, model/baseline metrics, and labeled provenance without creating Odoo sales or stock events.
- A regular stock user cannot mark a run reviewed. An inventory manager can mark a completed run reviewed, and the reviewer and timestamp are stored.

The scheduled worker handles at most two queued runs in one invocation. Forecast requests queue work; they do not train the model in the interactive RPC. Real source reads use Odoo's ORM and remain scoped to the selected company and optional warehouse.

## Browser and visual checks

Tested the running Odoo 19 addon in the local demo database at `http://127.0.0.1:8175`:

- Desktop viewport: **1440×1000**. The evaluated synthetic forecast displayed its 210 daily observations, 30-day seasonal-naive forecast, baseline/model MAE, heuristic range label, and provenance/limitations. Inventory health remained separately labeled as current Odoo stock. The empty product catalog showed the intended getting-started state.
- Mobile viewport: **390×844**. Forecast controls stack vertically, the chart and evaluation cards remain readable, and page width remains 390px with no horizontal page overflow. The `.as-app` container scrolls vertically so the forecast and inventory sections remain reachable.
- The completed-delivery source showed the no-tracked-products / history-coverage setup state; its evaluate action remained disabled until a valid product and covered history are configured.
- Browser console error logs were empty on the checked desktop and mobile dashboard tabs after the installed asset reload.

Desktop and mobile screenshots were captured during the browser review and shown in the task session. They could not be exported from the browser tool into repository files, so **this PR contains no Phase 2 screenshot image attachments**. This is a known evidence gap; the viewports, displayed state, and browser error checks are recorded above.

## Synthetic demo cleanup

Synthetic demo runs are stored as `autostock.forecast.run` records with `source_type="synthetic_demo"`; their observations and forecast points cascade with the run. The demo has no `product_id` and does not read or write sale orders, stock moves, stock quants, or supplier records.

To remove only synthetic forecast runs from a local development database, open the Odoo shell for that database (replace the example database name when needed):

```powershell
docker compose exec odoo odoo shell -d autostock_phase2_demo --no-http
```

Then inspect the matching count and delete that exact domain:

```python
runs = env["autostock.forecast.run"].search([("source_type", "=", "synthetic_demo")])
len(runs)  # inspect the count first
runs.unlink()
```

This removes synthetic forecast runs and their dependent forecast observations and points. It does not match real `completed_deliveries` runs or alter native Odoo sales/inventory records.

## Remaining limits and next steps

- Real forecasts are based on fulfilled sales. Odoo does not currently supply lost demand during stockouts, so these totals may understate demand. The configured history start is an administrator assertion of coverage.
- The single chronological holdout and deterministic synthetic fixtures are not a substitute for an approved business dataset, repeated backtesting, or interval calibration.
- The heuristic range is not a confidence interval. Forecasts must not automatically create orders or change stock.
- Phase 2 does not implement stockout recommendations, reorder proposals, budgets, reports, or the planned premium redesign.
- Commit persistent screenshot files in a follow-up QA pass when screenshot export is available; review GitHub Actions results on the draft PR before merge.
