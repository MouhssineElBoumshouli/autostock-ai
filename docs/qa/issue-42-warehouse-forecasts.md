# Issue #42 — Moroccan warehouse-specific forecasting QA

## Scope and safety

This milestone adds independently verified, company/product/warehouse/date/version-scoped history for Atlas Central Warehouse and South Service Depot. It does not provision, seed, or connect to a local Moroccan database, modify or switch the existing USD Atlas showroom, expose public Apply, change Docker volumes, or change the application's active database. The Issue #36 importer remains guarded and its ordinary Odoo create dates and users remain intact.

The implementation reuses the existing forecasting worker, inventory-risk eligibility, Odoo ACLs, company record rules, and manager review action. It does not add a second forecasting algorithm or alter freshness/evaluation gates.

## Dataset proposal used by the implementation

- Dataset: `atlas-ma-2026.4`, seed `36036`, SHA-256 `13b0e6ad858cec5c14192785b849c59b86143eb1f785d1c8cb033df3db174880`.
- 24 company-wide product histories remain distinct from six warehouse histories: three sample SKUs at each of two warehouses.
- Warehouse sample products span filtration, braking, and suspension. Each scoped profile covers 13 April–10 October 2026 (181 calendar days), including independent fictional April–June completed sales and the showroom's real Odoo completed sale deliveries from July through 10 October.
- A return qualifies only when its done Odoo stock move links through `origin_returned_move_id` to a qualifying delivery from that exact product and warehouse. Returns do not edit the original delivered quantity.
- The 30 profiles plan 5,430 daily observations and 1,117 qualifying delivery/return move events. The importer compares each profile against actual scoped Odoo move counts, converted quantities, dates, move digest, and complete daily digest before creating the verified profile and queuing 7/30/60-day runs. Profiles queue 90 runs total; all remain unreviewed.
- Odoo `product.create_date` and `create_uid` are not backdated or replaced. Dataset dates are business-effective dates on native Odoo stock movements only.
- Warehouse on-hand reconciliation remains per product, warehouse, and product UoM after stock movements; opening balances are actual Odoo inventory adjustments and all forecast inputs come from completed delivery/return records.

## Implementation and safety behavior

- Profile identity includes dataset version, company, product, optional warehouse, start/end dates, source-move count and digest, daily digest, and delivery/return counts and units.
- Company-wide profiles cannot satisfy a warehouse forecast request. A profile for Atlas Central cannot satisfy a South Depot request, or vice versa.
- The forecast worker verifies the exact profile scope and source digest before saving observations. Risk guidance rechecks the current source history before using a completed run; changed history makes it ineligible while preserving its points and manager review audit.
- A run remains unreviewed until a non-admin inventory manager reviews its completed result. Verified history does not imply human review or forecast accuracy.
- The existing restock gates remain unchanged: exact company/product/warehouse, reviewed completed supported evaluation, full horizon evaluation and future point coverage, at least 90 history days and 7 non-zero days, current source digest, and the ordinary 14-day data/cutoff freshness policy.
- Company and warehouse access use normal Odoo domains, company context, ACLs and record rules. Production paths use no `sudo()`.
- Forecast detail discloses whether a demo history profile is current and exactly scoped, without changing the approved Forecasts composition. Contract and browser checks cover the added provenance disclosure.

## Historical freshness and showroom decision

The fixture's final history date is 10 October 2026. It is potentially current only near the documented 13 October review point; the unchanged 14-day rule makes this history stale as time advances. CI must not freeze Odoo's clock and the application must not relax freshness to keep the showroom's old results eligible.

Before any Moroccan showroom cutover, the owner must choose one of these safe approaches:

1. Keep the current version and label the forecast results as historical examples, withholding all current forecast-based replenishment guidance after the ordinary freshness cutoff. This is the recommended immediate option for demonstrating the existing implementation.
2. Prepare a new reviewed dataset version with genuinely generated and correctly dated Odoo movements for an appropriate current training window, re-run the same integrity checks, and preserve actual Odoo record creation dates. Do not shift old stock-move or product creation dates merely to pass freshness.

Neither option authorizes local import, provisioning, database switching, or cutover in this PR.

## Verification record

Commands and results are updated before the draft PR is opened. CI integration tests use only the disposable Odoo 19/PostgreSQL 16 database and unique Compose project created by GitHub Actions. This branch has not touched a local database or Docker volume.

| Check | Result |
|---|---|
| `python -m pytest -q tests/test_moroccan_showroom.py` | Passed: 26 tests. Windows emitted non-fatal pytest temporary-directory cleanup warnings (`WinError 145`). |
| `python -m compileall -q addons ml scripts tests` | Passed. |
| `python -m scripts.moroccan_showroom.cli --seed 36036` | Passed offline: 7,024 planned fixture identities, 30 profiles, 5,430 daily rows, stock ledger reconciled, 0 mutations, digest above. No Odoo connection. |
| `python -m pytest -q` | Passed: 65 tests. Windows emitted non-fatal pytest temporary-directory cleanup warnings (`WinError 145`). |
| `python -m compileall -q addons ml scripts tests` | Passed. |
| `python -m ml.evaluate ml/output/synthetic_daily_sales.csv --days 30` | Completed for 6 labeled synthetic products. This validates the evaluation pipeline only, not Moroccan or customer forecast accuracy. |
| Frontend lint and typecheck | Passed: `npm run lint`, `npm run typecheck`. |
| Frontend unit/API contract tests | Passed: 10 unit tests and 16 contract tests. |
| Playwright | Passed: 36 tests, including responsive Forecasts, warehouse current/stale disclosure, existing Dashboard/Inventory/Warehouses/Suppliers journeys, keyboard and reduced-motion checks. |
| Frontend production build | Passed: `npm run build`. |
| Odoo 19/PostgreSQL 16 integration tests | Passed in GitHub Actions run #126 at code commit `3f50de92fd62fdd7f50d343fb94e9f8be8c301b5`: 76 actual Odoo test cases passed with 0 failures and 0 errors. The broader Odoo stats line reports 92 test events; that is not the test-case count. The job used only its disposable CI database. |
| Live Atlas browser check/screenshots | Not run by design; the existing showroom must remain untouched and unswitched. |

The completed CI run also passed the Python and React frontend jobs. A follow-up documentation-only commit records those results and does not change application or test code.

## Required Odoo integration coverage

The new disposable-database tests cover actual completed outgoing sale moves, linked native returns and their original delivery warehouse; all six independently scoped profiles; all 18 warehouse forecast runs across 7/30/60 horizons; exact source and daily digest checks; manager review; exact-warehouse risk selection; rejection of company-wide/other-warehouse candidates; user/company/warehouse access; current-source invalidation after a completed/reviewed run; preserved points and review audit; and forecast staleness under the unchanged 14-day rule. A separate pure policy assertion checks the example as-of 13 October and verifies that the same evidence is rejected on 27 October; it does not monkeypatch or freeze Odoo's runtime clock.

The final Odoo run verified that the staleness regression selects a company-wide profile explicitly, warehouse history assertions use the same completed-sale and internal-to-customer source criteria as the forecast engine, and the manager/warehouse regression binds its model and performs the source-drift check before creating a foreign-company fixture.

## Remaining limitations

- The six warehouse examples are fictional showroom data, not business validation or evidence of commercial forecast accuracy.
- Only three products per warehouse have pre-focus scoped history; all other products still require normal configured warehouse coverage and sufficient real history.
- The historical data becomes stale. A future showroom cutover needs the owner's selected demo approach and fresh evidence, even after this implementation is merged.
- Public Apply remains closed pending the separate signed-backup, independent restore-evidence, and authorization gate.
- No local showroom database, browser session, screenshots, database credentials, filestore, or Docker volume were accessed by this milestone.
