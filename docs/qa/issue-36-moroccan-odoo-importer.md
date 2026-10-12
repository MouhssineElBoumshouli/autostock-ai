# Issue #36 — Moroccan Odoo importer QA

## Scope and safety boundary

This milestone adds an Odoo 19 ORM importer and Odoo-side forecast-history provenance for the pinned `atlas-ma-2026.2` dataset. It does not start the Moroccan Compose project, initialize or seed a local Moroccan database, change the running app connection, or operate on the existing USD Atlas database, credentials, containers, or volumes.

Odoo integration coverage runs in GitHub Actions against a newly created PostgreSQL 16/Odoo 19 database within a random CI Compose project. The test transaction creates actual Odoo records and is rolled back; the workflow removes only that random project's containers and volumes. The prepared local Moroccan showroom remains unprovisioned.

## Import behavior

- Validates the exact target DB name, UUID environment, company marker consistency, single-company clean first-import state, administrator access, and required installed modules before planning writes.
- Reuses the clean database's one bootstrap `res.company`, giving it the fictional Atlas Auto Distribution identity, Morocco country, MAD currency, Marrakech city and Casablanca timezone before commercial records are created. It reuses the untouched main-company `stock.warehouse0` as Atlas Central Warehouse and adds South Service Depot, yielding exactly two warehouses.
- Creates 150 storable automotive products, category records, 8 fictional suppliers, 18 fictional customers, two warehouses, native supplier price/MOQ/lead-time terms and 300 warehouse orderpoints.
- Uses native Odoo stock inventory adjustments for opening balances, Sales orders and validated outbound pickings for completed deliveries, incoming pickings for receipts, the Odoo return wizard for linked returns, native internal transfer pickings, and confirmed but unshipped customer orders.
- Reconciles physical on-hand per product and warehouse with the deterministic ledger before completing the savepoint. Plan keys and payload hashes must be complete and unchanged for a repeat import to return a no-write result. Partial, conflicting, missing-record or dirty-target states fail closed.
- Queues 72 forecast requests (7/30/60 days for 24 products), all unreviewed. No accuracy claim is made and no forecast is auto-approved.

## Historical source integrity

Product and transaction `create_date`/`create_uid` remain Odoo audit values. The importer pins only the business-effective dates of the fictional movements. Company-wide complete history is dated from 1 July 2026, when full-catalog activity begins. The 24 declared profiles have separate 181-day (13 April–10 October) histories; their requests are compared against completed Odoo delivery moves and linked returns for exact event counts, delivered/returned quantities, per-day observations and source digests. Only an exact company/product/date/dataset match in database `autostock_atlas_morocco_demo`, with matching environment/company UUID markers, can pass the existing pre-product-creation guard. This company-scope exception cannot be used for a warehouse-level forecast. Ordinary products and companies retain the original coverage and creation-date rejection. A queued run rechecks its source digest before processing, and later source changes invalidate that profile.

## Verification

- `python -m pytest -q`: **63 passed**. Windows emitted non-fatal pytest temporary-directory cleanup warnings (`WinError 145`) after the passing run.
- `python -m pytest -q tests/test_moroccan_showroom.py`: **25 passed**.
- `python -m compileall -q addons ml scripts tests`: passed.
- `python -m scripts.moroccan_showroom.cli --seed 36036`: passed as an offline plan check; **6,661** stable Odoo fixture identities, ledger reconciled, zero writes. Dataset digest remains `56c832a6e1f05b9b55127e925a2a9263b429f0767f1fc9d0ef12844f7781f839`.
- `python -m ml.evaluate ml/output/synthetic_daily_sales.csv --days 30`: completed for **6 labeled synthetic products**. This is a pipeline check only, not a Moroccan or customer accuracy claim.
- Frontend `lint`, `typecheck`, unit tests (**10 passed**) and API contract tests (**16 passed**): passed locally. No frontend behavior changed in this milestone.
- Local Chromium browser suite: **35 passed**. Local production frontend build: passed. The UI was unchanged in this milestone; PR CI will rerun these checks against the committed branch.
- GitHub Actions Odoo 19/PostgreSQL 16 transaction tests: **pending PR workflow**.
- Local Moroccan showroom/import/browser screenshots: **not run** by design. The showroom has not been provisioned or seeded.

## Remaining limits

- The public `run_import(..., mode="apply")` path stays blocked by the existing signed-backup and independent-restore evidence gate. The private writer also rejects direct calls outside Odoo test mode, and no local Apply command is exposed in this milestone.
- The CI integration writer runs only in its isolated disposable test database; this does not verify the prepared Windows/Docker environment or a local Odoo snapshot.
- The synthetic records are fictional demonstrations. Forecast outputs illustrate workflow behavior and are not evidence of business forecasting accuracy.
