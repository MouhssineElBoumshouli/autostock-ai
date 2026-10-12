# Issue #36 — Moroccan showroom preparation baseline QA

> This report records the earlier preparation-only milestone. The Odoo writer and its current verification status are tracked in [the importer QA report](issue-36-moroccan-odoo-importer.md).

## Scope

This draft prepares a separate Atlas Auto Distribution showroom with MAD as company currency. It adds Compose and PowerShell setup files, a deterministic Python fixture planner, identity and signed-backup gates, an idempotent read-only import preview, and unit tests.

No Moroccan showroom service or database was provisioned, and no Moroccan fixture was imported. The existing `autostock_showroom_demo` database, containers, credentials, PostgreSQL volume, filestore volume, and app connection were not operated on. A disposable Odoo CI test project was started and removed under its own random Compose project name; the legacy container IDs/status and volume names matched before and after.

## Data and forecast integrity

- Generated plan: one company, two warehouses, 150 products, 8 fictional suppliers, 18 fictional customers, 350 completed focus-window orders, 30 incoming receipts, 12 linked returns, 18 internal transfers, and 20 open orders.
- The focus window is pinned to 1 July–10 October 2026. A separately labeled April–June fictional effective-history extension yields 181 planned calendar observations for 24 product profiles. Four explicitly keyed product examples come from each of the six categories: filtration/service, braking, suspension/steering, electrical/batteries, cooling/belts/drivetrain, and ignition/sensors/fluids. The selected profiles contain six products in each planned demand class (fast, steady, intermittent, slow).
- Product creation timestamps are not generated or backdated. The current Odoo forecast guard remains unchanged. Until a reviewed Odoo-side provenance path validates actual qualifying delivery moves and coverage, historical forecast runs are explicitly unavailable.
- The dry-run report is an offline fixture preview, not a live Odoo import dry-run. It validates stable plan keys and generated stock-ledger arithmetic without database connections or writes.
- New-record stock ledgers are checked per product, warehouse/location, and unit. Legacy ledger state is reference-only and excluded.

## Isolation and restore boundaries

- The resolved Compose contract requires exactly `db` and `web`, both attached only to the private network carrying the target UUID label. PostgreSQL must mount only its dedicated named volume at `/var/lib/postgresql/data`; Odoo must mount only its separate filestore volume and the two exact read-only repository bind mounts.
- A mocked first-Start, post-Start, repeated-Start, and Status sequence validates the same Compose contract and isolated runtime snapshots. Tampered volume sources/targets, extra binds, writable addon binds, extra network attachments, foreign endpoints, or a missing target UUID label are rejected.
- Separate regression checks validate existing Docker container mount names/sources/destinations/access modes, container project/UUID labels, network attachment, and network endpoints. No Moroccan service was started for these tests, so live Docker mounts and repeat Start/Status behavior remain unverified until separately authorized provisioning.
- The HMAC helper validates signed backup metadata and actual database/filestore artifact sizes and hashes only. It does not prove a restore occurred. Unknown modes are rejected and Apply always fails closed until a future reviewed stage adds an independent restore-evidence verifier and an authorized writer.

## Checks

- `python -m pytest -q`: **63 passed**. Windows pytest emitted 49 nonfatal temporary-directory cleanup warnings (`WinError 145`) after successful completion.
- `python -m pytest -q tests/test_moroccan_showroom.py`: **25 passed**. This includes profile distribution and pre-focus deliveries; tampered Compose mounts/network config; runtime database, filestore, read-only bind and network evidence; signed-manifest/artifact integrity; and unknown/Apply mode rejection. Windows pytest emitted 48 nonfatal temporary-directory cleanup warnings after successful completion.
- `python -m compileall -q addons ml scripts tests`: passed.
- `python -m scripts.moroccan_showroom.cli --seed 36036`: passed as an offline preview. Updated dataset version is `atlas-ma-2026.2`; SHA-256 is `56c832a6e1f05b9b55127e925a2a9263b429f0767f1fc9d0ef12844f7781f839`. The preview reports 24 profiles, 181 rows per profile, four products from each of six categories, six profiles per demand class, and zero database mutations. History remains unavailable for forecasts.
- GitHub Actions run [38290212144](https://github.com/MouhssineElBoumshouli/autostock-ai/actions/runs/38290212144) passed on code commit `c073a9aa`: Python, compile, labeled synthetic evaluation, Odoo 19/PostgreSQL 16 integration tests, frontend lint/typecheck/unit/API contract tests, Chromium responsive browser tests, and production build. The Odoo suite reported 0 failures and 0 errors across 60 test cases (Odoo's broader stats line reported 74). The subsequent `52625e3` commit only finalized this QA report. The isolated Odoo CI project and volumes were removed by the workflow.
- Existing labeled synthetic forecast evaluation completed successfully for 6 fixture products. No accuracy score is claimed for the Moroccan plan.
- `docker compose --file compose.morocco.yml config --format json` with `scripts/moroccan_showroom/env.example`: passed. The resolved config includes the network UUID label, the dedicated database/filestore volumes, and the read-only addon/script binds. This parsed configuration only; no service was started.
- PowerShell setup script parser check, `git check-ignore -v .env.atlas-morocco`, and staged `git diff --check`: passed.

## Not performed

- The Moroccan `Prepare` or `Start` actions were not run; no Moroccan credentials file was created. No Moroccan database initialization, seed/import, app cutover, or browser session occurred.
- No Moroccan data-writer integration test; Apply is explicitly disabled. A signed backup-manifest claim is not treated as evidence that an independent restore completed.
- No live Moroccan UI/browser screenshots. Those require the approved showroom to be provisioned and populated in a later reviewed step.
- No claim that fixture moves, MAD setup, forecast profiles, or screenshots have been validated in a running Moroccan database.

## Remaining review boundary

The current preview generates and reconciles a deterministic Odoo-neutral movement plan. It does not write native Odoo sale orders, deliveries, receipts, returns, inventory adjustments, or transfers, and it does not compare the plan to a live Odoo snapshot. A native record-writing workflow, Odoo-side source-provenance verification, independently observed database restore evidence, and Atlas browser walkthrough require independent review and separate owner authorization before import.
