# Issue #36 — Moroccan showroom implementation preparation QA

## Scope

This draft prepares a separate Atlas Auto Distribution showroom with MAD as company currency. It adds Compose and PowerShell setup files, a deterministic Python fixture planner, identity and signed-backup gates, an idempotent read-only import preview, and unit tests.

No Moroccan showroom service or database was provisioned, and no Moroccan fixture was imported. The existing `autostock_showroom_demo` database, containers, credentials, PostgreSQL volume, filestore volume, and app connection were not operated on. A disposable Odoo CI test project was started and removed under its own random Compose project name; the legacy container IDs/status and volume names matched before and after.

## Data and forecast integrity

- Generated plan: one company, two warehouses, 150 products, 8 fictional suppliers, 18 fictional customers, 350 completed focus-window orders, 30 incoming receipts, 12 linked returns, 18 internal transfers, and 20 open orders.
- The focus window is pinned to 1 July–10 October 2026. A separately labeled April–June fictional effective-history extension yields 181 planned calendar observations for 24 product profiles.
- Product creation timestamps are not generated or backdated. The current Odoo forecast guard remains unchanged. Until a reviewed Odoo-side provenance path validates actual qualifying delivery moves and coverage, historical forecast runs are explicitly unavailable.
- The dry-run report is an offline fixture preview, not a live Odoo import dry-run. It validates stable plan keys and generated stock-ledger arithmetic without database connections or writes.
- New-record stock ledgers are checked per product, warehouse/location, and unit. Legacy ledger state is reference-only and excluded.

## Checks

- `python -m pytest -q`: **51 passed**. Windows pytest emitted temporary-directory cleanup warnings (`WinError 145`) after test completion; pytest exited successfully.
- `python -m pytest -q tests/test_moroccan_showroom.py`: **13 passed** after adding fail-closed target-identity checks to the signed backup gate. Windows temporary-directory cleanup warnings also occurred after this successful test exit.
- `python -m compileall -q addons ml scripts tests`: passed.
- `python -m scripts.moroccan_showroom.cli --seed 36036`: passed as an offline preview. Counts include 150 products, 8 suppliers, and 18 customers; plan SHA-256 is `a62c1424bbd38403a127b20cbd545f11c466089f4cc163e2895ce0ce00c434e5`; reported database mutations are 0. History is still explicitly unavailable for forecasts.
- Odoo 19/PostgreSQL 16 integration suite in disposable project `autostock-ci-morocco-8f92e01a59`: **0 failures, 0 errors across 60 test cases**. Odoo's broader stats line reported 74 tests; these are different counters. The temporary project and its volumes were removed after the run.
- Existing labeled synthetic forecast evaluation completed successfully for 6 fixture products. No accuracy score is claimed for the Moroccan plan.
- `docker compose --file compose.morocco.yml config --format json` with placeholder environment values: passed. Confirmed the dedicated project, named Moroccan volumes, private PostgreSQL, Odoo bound to `127.0.0.1:8070`, and no `.showroom` mount. This only parsed configuration; it did not start the Moroccan services.
- PowerShell setup script parser check, `git check-ignore .env.atlas-morocco`, and staged whitespace check: passed.

## Not performed

- The Moroccan `Prepare` or `Start` actions were not run; no Moroccan credentials file was created. No Moroccan database initialization, seed/import, app cutover, or browser session occurred.
- No Moroccan data-writer integration test; this PR has no Apply path.
- No live Moroccan UI/browser screenshots. Those require the approved showroom to be provisioned and populated in a later reviewed step.
- No claim that fixture moves, MAD setup, forecast profiles, or screenshots have been validated in a running Moroccan database.

## Remaining review boundary

The current preview generates and reconciles a deterministic Odoo-neutral movement plan. It does not write native Odoo sale orders, deliveries, receipts, returns, inventory adjustments, or transfers, and it does not compare the plan to a live Odoo snapshot. A native record-writing workflow, Odoo-side source-provenance verification, database backup/restore evidence, and Atlas browser walkthrough require independent review and separate owner authorization before import.
