# Issue #36 — Phase A Atlas Morocco dataset proposal

**Status:** proposal and sample manifest only. The manifest is not an importer. No database, filestore, credential, Docker volume, or business record was changed or cloned.

**Scope:** design the fictional Moroccan Atlas Auto Distribution dataset and a safe later migration plan. Phase A does not implement a seed script, import data, install optional modules, or change the UI.

Sources: [Issue #36](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/36) and its [Phase A planning comment](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/36#issuecomment-6115760700).

## Read-only audit — 12 October 2026

Database reads ran in read-only transactions that were rolled back. No secret file or container password was opened or printed.

| Item | Observed state |
|---|---|
| Branch base | Fetched origin/main at 29266ac26ecabc7d23082f5c8d9c89bf5e736c27 |
| Atlas DB/runtime | autostock_showroom_demo, about 61 MB; Odoo 19 image; PostgreSQL 16 |
| Containers/volumes | autostock-showroom-demo-odoo-1, autostock-showroom-demo-db-1; autostock_ai_showroom_filestore, autostock_ai_showroom_postgres |
| AutoStock | Installed, 19.0.0.1.4; seed marker 2026-10-10.1 |
| Company | ID 1, Atlas Auto Distribution, Marrakech, MA; base currency USD. MAD currency 110 exists but is inactive. |
| Locale | en_US is the only active language; one user profile reports Africa/Casablanca timezone. |
| Products | 64 active tracked products and 64 distinct SKUs. Four product templates were created 13 April; 60 on 10 October. Examples: AT-FLT-001 / template 130, AT-BRK-001 / 131, AT-FLT-002 / 132, AT-ENG-001 / 133. |
| Warehouses | ID 1 Atlas Central Warehouse / ATC; ID 7 South Service Depot / ASD. Both are one-step receipt and ship-only delivery. |
| Partners/terms | Four suppliers (IDs 41–44), three customers (IDs 45–47), 60 supplier terms and 57 reorder rules. Existing partner city fields are empty and will remain unchanged. |
| Sales/deliveries | 174 sale orders and completed pickings. 454 completed internal-to-customer move lines across four products; 240 move lines and 96 linked orders have move dates in July–October. |
| Other moves | No completed customer returns, vendor receipts, internal transfers or open customer-directed moves. |
| Forecasts | 13 completed history runs: four reviewed for each 7/30/60-day horizon plus one unreviewed 30-day run. Saved history spans 13 April–9 October. |
| Optional modules | stock, sale, sale_stock, account and AutoStock are installed. sale_management, contacts, purchase and purchase_stock are not. Do not invent PO or invoice history. |

### Existing-data limitations

All 174 sale orders have date_order on 10 October, and all 174 completed pickings have date_done on 10 October. Their stock.move dates span 13 April–9 October. PR #17 confirms the seed validates pickings at seed time and then writes historical dates to stock moves. Forecast observations use move dates, but those old order/picking timestamps do not describe the same historical days. Preserve legacy rows and forecast snapshots unchanged; do not count these as chronology-verified new events.

A read-only comparison of internal stock.quant balances and signed completed stock.move quantities did not reconcile for 64/64 products. The legacy seed uses Odoo's quant update helper to force opening and closing snapshots without a complete movement ledger. This is a fixture-history limitation, not proof that the database is corrupt. Do not “repair” the original by rewriting quants or finalized moves. New stock must reconcile in a clone through auditable inventory adjustments and movements.

Current main and the checked-out Forecasts branch do not contain scripts/seed_showroom_demo.py, compose.showroom.yml or scripts/start_showroom_demo.ps1. Those files exist in legacy PR #17, which remains open, draft and reported unmergeable due to conflicts. Do not merge it wholesale or copy its seed unchanged. The current main seed_odoo_demo_inventory.py and seed_phase3a_risk_demo.py are allowlisted QA fixtures, not Atlas importers; they use quant APIs, and the latter uses QA-prefixed records.

## Proposed dataset

The companion [sample manifest](issue-36-moroccan-atlas-manifest.yaml) is human-reviewable fictional YAML with stable fixture keys. It is non-executable; none of its proposed records exist in Odoo.

| Area | Proposal |
|---|---|
| Company/warehouses | Retain Atlas and both warehouse IDs, names, codes and routes. Target Morocco / Africa-Casablanca and MAD only after the USD/inactive-MAD issue is resolved in an isolated clone. |
| Products | 150 total: preserve all 64 IDs/SKUs, add 86 across service filters, brakes, suspension/steering, electrical/batteries, cooling/belts/drivetrain, ignition/sensors/fluids. No invented OEM match or exact vehicle fitment. |
| Suppliers/customers | 8 suppliers (retain 4 IDs, add 4 fictional Moroccan distributors) and 18 customers (retain 3 IDs, add 15 fictional workshops, retail desks and fleets). City-level locations only; no real street address, phone, email, tax ID or login. |
| Sales | Add about 350 new, chronologically coherent order/delivery pairs in July 1–October 10, each with 1–5 lines. Preserve old history separately; use deterministic demand and stable event keys. |
| Other activity | 30 vendor receipts, 12 returns linked to original deliveries, 18 internal transfer journeys and 20 confirmed outbound orders left open/assigned to create real reservations. |
| History/forecasts | Preserve 13 snapshots and April–June prehistory. Target 181 complete observations from April 13 to October 10 for selected examples; generate fresh 7/30/60-day runs only through the existing request/worker pipeline. Keep new runs unreviewed until an authorized manager reviews them. |
| Languages | One language-independent SKU/product/price/stock record. Prepare EN/FR/AR names, category labels and aliases for human review; UI localization and RTL stay in Issue #37. |

All manifest prices are **illustrative MAD values**, not verified quotes, market research or tax advice. Keep currency and UoM on each native supplier term; never combine unlike currencies or convert without an approved rate. Tax treatment is unresolved. Do not write prices until the company currency decision is tested in a clone.

All proposed entities and transactions are fictional. No real company, customer, contact detail, fitment, OEM match, sale, invoice, forecast accuracy or business validation is asserted. Keep the discreet Demo indicator and administrator-visible provenance; product names remain natural.

### Example business stories

1. **Engine oil filter, Central:** opening count 24 on July 1; deliver 5 July 6; receive 12 July 12; deliver 7 July 20; return 2 August 3 linked to that delivery; transfer 6 to South September 9; reserve 3 on an unshipped October 8 order. Example arithmetic: Central 20 on hand / 3 reserved / 17 available; South 6 on hand. These are proposal values, not live stock.
2. **Front brake pad set:** open with 4; deliver all 4 July 30; leave a five-unit confirmed order unfulfilled August 5 while stock is zero; receive 24 August 10; deliver 5 August 12. Do not count the unfulfilled order as a delivery or invent lost sales. Mark delivered-sales history stockout-censored.
3. **Battery/suspension:** slower irregular deliveries, varied lead times and pack sizes, and a return linked to a completed delivery. No supplier reliability or savings score.
4. **South depot:** true internal transfer plus lower local deliveries. Transfer legs are not demand and must not be double-counted.
5. **Data gaps:** one missing supplier term and one insufficient-history product remain honest empty states.

### Odoo source mapping

| Fact | Source |
|---|---|
| Product identity | product.template / product.product; stable SKU, UoM and company/shared scope. Translation never creates another SKU. |
| Supplier currency, terms and tiers | res.partner / product.supplierinfo; preserve currency, min_qty tiers, ordering UoM, delay and AutoStock MOQ separately. |
| Customer demand | sale.order / sale.order.line confirmed through installed sale_stock. Only completed stock.move with sale_line_id, internal source and customer destination enters delivery history. |
| Receipt | Native incoming stock.picking and stock.move from supplier to internal location with supplier partner. Purchase is uninstalled; do not invent purchase.order or vendor bills. |
| Return | stock.return.picking workflow and completed reverse stock.move linked by origin_returned_move_id. Record the return on its event date; do not edit past deliveries or use negative sales. |
| Transfer | Internal stock.picking/moves between warehouse locations. If transit is configured, retain both legs under one journey key; neither is customer demand. |
| Opening stock/reservations | Native inventory adjustment creates moves. Read stock from stock.quant plus Odoo reservations/open moves. No SQL quant writes or quant helper to force balances. |
| Forecast | autostock.forecast.run, observation and point through validated request, worker and source snapshot. React does not calculate demand or accuracy. |

## Historical dates and forecasting

The focus window is July 1–October 10 inclusive (102 days). The engine requires at least 90 complete observations and 28 training days. Retained history April 13–October 10 is 181 days; a 60-day chronological holdout leaves 121 training days. Zero-delivery dates count only when the source is known complete.

Odoo stock completion sets stock.move.date to the current time. For new fictional rows only, validate with Odoo, then set predeclared event dates on the newly created order, picking and move through ORM in the same transaction before commit. Keep create_date/create_uid as actual import audit metadata. Test date fields, reservations, valuation and Forecasts/Inventory/Warehouses screens in the clone. Never edit existing completed rows; abort if dates cannot be maintained or presented truthfully.

New forecastable fixture products may receive a simulated April 13 create_date on their initial ORM create in the isolated clone. Odoo 19 create preparation defaults create_date only when omitted, but the product/forecast path has not been tested with an explicit date. Stage B must prove provenance is clear and the existing forecast guard accepts history beginning then. No SQL update or production guard relaxation. Leave the 60 existing products created October 10 untouched and without earlier history.

Pin dates; never derive them from today(). Convert explicit Africa/Casablanca times away from midnight to Odoo's UTC-naive storage and test the engine UTC-day bucket. Order <= picking completion/move time; returns happen later and link to their delivery. One event key maps to one transaction. Never rewrite old observations, cutoffs or review statuses. New forecasts stay unreviewed; stockout-censored deliveries are not treated as unconstrained demand.

## Preservation and clone plan

Nothing here has been executed. After approval to implement:

1. Record DB name, addon/seed versions, company/warehouse IDs, baseline counts, named volumes and filestore path. Verify the exact DB guard; leave ignored credentials unchanged.
2. Back up only autostock_showroom_demo and its matching filestore directory: PostgreSQL custom-format dump plus archive of /var/lib/odoo/filestore/autostock_showroom_demo. Save under an ignored private path, record sizes/checksums and verify restore. Do not replace an entire Docker volume or commit backups.
3. Restore database and filestore to separate Odoo/PostgreSQL services with a distinct project/network/volumes and generated credentials. The clone may use the same internal DB name to satisfy the exact guard; isolation comes from separate services and volumes. Never attach either original named volume.
4. Run a no-write dry-run. Check seed version, company, original SKU/partner/warehouse identities, modules, currency/language preconditions and key collisions. Report create/reuse counts and projected per-product/location/UoM deltas. Abort on mismatch.
5. After explicit owner approval, apply additively to the clone. Match existing records by verified keys; assign stable external IDs to new records. Conflicting keys abort. Never unlink or rewrite existing products, partners, orders, pickings, quants or forecast runs.
6. Repeat dry-run/apply. Second apply creates zero records and changes zero finalized values. A changed completed event requires a new version and restored clone.
7. Only after clone forecast and browser QA pass may the owner separately authorize the original Atlas. Verify backup/restore first. This PR does not authorize that action.

### Windows operator flow (future tooling)

Stage B can add a PowerShell command with dry-run default, for example a future prepare_atlas_morocco_clone.ps1 -Mode DryRun. Review its DB/module/key/count report. A future -Mode Apply would still target only the clone and require explicit approval. The PR #17 launcher/seed is not on main; this proposal does not claim those commands exist.

Do not use docker compose down -v, volume prune, WSL unregister, reset switches, or commands targeting the original volumes.

## Review decisions and Stage B acceptance

1. **Currency:** test MAD activation/base-currency change on the clone without relabeling old fictional USD prices/orders. Do not invent an exchange rate; pause if meaning cannot be preserved.
2. **Legacy chronology:** preserve original orders, pickings, moves and forecast runs; decide how the clone's UI explains their limitation.
3. **Fixture dates:** approve disclosed ORM-only simulated dates for new fictional product/event rows. If unsupported, stop rather than use SQL or weaken the forecast guard.
4. **Scope:** approve 150/8/18 catalogue, 350 new dated deliveries, 30 receipts, 12 returns, 18 transfers and 20 open reservations, subject to runtime.
5. **Language readiness:** review draft EN/FR/AR labels. No language switch, RTL UI, or Issue #37 implementation.

Stage B tests: DB/module guards, no-write dry-run, deterministic/idempotent apply, creation/history boundary, chronological sale/receipt/return/transfer links, quant-to-move reconciliation by location/UoM, no duplicate transfer demand, reservation totals, company/warehouse permissions, truthful 7/30/60 evaluation and stockout/insufficient-history states. Then run frontend/API checks and actual Dashboard, Inventory, Warehouses, Suppliers and Forecasts browser journeys on the clone at desktop/tablet/mobile. Verify no browser errors, overflow or seed records after October 10.

Planning estimate: several minutes to about 15 minutes for 350 orders, stock workflows and selected forecasts on healthy local Docker. This is unmeasured; benchmark clone dry-run, apply and forecasts separately.

## Phase A boundary

- Read Issue #36, its planning comment, project docs, forecasting rules, seed scripts and legacy PR #17.
- Created this proposal and non-executable manifest only.
- No import, backup, clone, module install, service shutdown, browser run or screenshot.
- Original Atlas DB, filestore, credentials and named volumes remain untouched.
- No business validation, real-world forecast accuracy or production-readiness claim.
