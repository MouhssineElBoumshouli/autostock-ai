# Issue #36 — Phase A Atlas Morocco dataset proposal

**Status:** proposal and sample manifest only. The manifest is not an importer. No database, filestore, credential, Docker volume, or business record was changed or cloned.

**Scope:** design the fictional Moroccan Atlas Auto Distribution dataset and a safe later migration plan. Phase A does not implement a seed script, import data, install optional modules, or change the UI.

Sources: [Issue #36](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/36) and its [Phase A planning comment](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/36#issuecomment-6115760700).

## Read-only audit — 12 October 2026

Database reads ran in read-only transactions that were rolled back. No secret file or container password was opened or printed.

These figures are a local workstation snapshot from Phase A, not evidence independently reproducible from GitHub. The manifest records observations, not a migration guard or guarantee. A future read-only preflight must remeasure the target machine's database, module versions, IDs, volumes and counts, and stop on any unexpected drift before preparing a backup.

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
| Company/warehouses | Preserve the existing Atlas company and both warehouse IDs, names, codes and routes. Keep its base currency USD by default; only change the company structure or currency after the owner chooses a path below. Morocco / Africa-Casablanca and MAD remain intended new-business settings, subject to that choice. |
| Products | 150 total: preserve all 64 IDs/SKUs, add 86 across service filters, brakes, suspension/steering, electrical/batteries, cooling/belts/drivetrain, ignition/sensors/fluids. No invented OEM match or exact vehicle fitment. |
| Suppliers/customers | 8 suppliers (retain 4 IDs, add 4 fictional Moroccan distributors) and 18 customers (retain 3 IDs, add 15 fictional workshops, retail desks and fleets). City-level locations only; no real street address, phone, email, tax ID or login. |
| Sales | Add about 350 new, chronologically coherent order/delivery pairs in July 1–October 10, each with 1–5 lines. Preserve old history separately; use deterministic demand and stable event keys. |
| Other activity | 30 vendor receipts, 12 returns linked to original deliveries, 18 internal transfer journeys and 20 confirmed outbound orders left open/assigned to create real reservations. |
| History/forecasts | Preserve 13 snapshots and April–June prehistory. Target 181 complete calendar observations from April 13 to October 10 only for eligible pre-existing April-created products; generate fresh 7/30/60-day runs only through the existing request/worker pipeline. Keep new runs unreviewed until an authorized manager reviews them. |
| Languages | One language-independent SKU/product/price/stock record. Prepare EN/FR/AR names, category labels and aliases for human review; UI localization and RTL stay in Issue #37. |

Chronology boundary: July–October example sales, receipts, returns and transfers use only retained product records created by April 13. New catalog products are created at their actual import time and receive no earlier stock or sales events; any opening stock is entered through an Odoo adjustment dated no earlier than creation. This preserves audit dates but limits initial history and forecasts to eligible retained products.

All manifest prices are **illustrative MAD values**, not verified quotes, market research or tax advice. All illustrative product and supplier prices use one provisional **tax-exclusive** display assumption; no tax rate, tax mapping or tax amount is supplied. Confirm the Moroccan tax setup before creating orders. Keep currency and UoM on each native supplier term; never combine unlike currencies or convert without an approved rate.

### Currency compatibility and owner choice

The existing Atlas company uses USD; MAD exists in the database but is inactive. Activating MAD only makes the currency available. It does not convert stored amounts. The same-company target of MAD, preservation of all legacy values/IDs, and a prohibition on inventing exchange rates cannot all be guaranteed by a simple currency switch.

| Odoo data | Currency is stored how? | Safe Phase B treatment |
|---|---|---|
| res.company.currency_id | Company base/reporting currency. | Preserve USD until an owner-selected path is approved. A switch is not a conversion. |
| res.currency | USD is active; MAD is currently inactive. Rates are separate dated records. | Enable MAD only for an approved scenario. Add no rate unless its source and effective date are approved and recorded. |
| product.template.list_price and product.product.standard_price | Product sales price and company-dependent cost are interpreted in the active company currency; these fields do not carry an independent currency code. | Do not relabel or silently reinterpret existing values. On a MAD company, create values only with an approved basis; otherwise leave them unchanged and do not present them as MAD. |
| product.supplierinfo price tiers | Each supplier term has an explicit currency_id; each min_qty row is its own price break. | Preserve the currency of each legacy term. New MAD terms are explicitly MAD. Do not convert or aggregate tiers across currencies. |
| sale.order and sale.order.line | The order has an explicit currency; line prices and totals use that order currency. | Preserve historical orders and their currency. A new order must use an explicitly selected currency and a compatible pricelist/tax setup. |
| account.move and stock valuation | Foreign-currency moves may store currency_id and amount_currency; balance is in the company currency. Stock valuation values are company-currency amounts. | Audit posted moves and valuation layers before any base-currency change. Never relabel, rewrite or “convert” posted history in place. |
| AutoStock API | Session/company metadata reports the selected company currency; supplier-term responses report each term's own currency. | Those fields do not prove that every legacy product, cost or valuation amount is safe to render in MAD. Later API work must label each monetary value or omit mixed/ambiguous totals. |

**Recommended option — preserve the existing Atlas company in USD.** Keep the current company, its IDs, historical orders, products and implicit company-currency values intact. After clone tests, activate MAD for explicitly denominated supplier terms; use a MAD sales pricelist only if Odoo's currency/rate/tax behavior is verified and each order exposes its currency. Keep unlabelled product/cost/accounting figures in USD and omit mixed-currency totals. This preserves current identity and avoids false conversions, but does not provide company-wide MAD accounting or a dashboard whose base currency is MAD. It is the safest default until the owner chooses whether that trade-off is acceptable.

Other choices requiring owner approval:

1. **Add a separate Moroccan company in the isolated clone.** Keep the existing company and all its values in USD; configure MAD on a new company. Use company-specific product records/prices unless the clone audit proves a record is safely shared. This provides a proper MAD company and preserves the legacy company IDs, but creates a two-company showroom. Existing sales history cannot simply be moved to the new company; copied/new products keep actual creation dates and start with insufficient history.
2. **Convert the existing company to MAD in a separately approved accounting migration.** This best preserves a single company identity, but requires an accountant-approved dated FX source and a field-by-field migration/revaluation plan for implicit product prices/costs and any company-currency valuation/accounting balances. Keep explicitly USD orders and vendor terms denominated USD. If historic amounts cannot be preserved and explained, do not choose this path. No rate or conversion is supplied by this proposal.
3. **Create a separate clean Moroccan database/company.** This provides a simple one-company MAD experience, but does not extend the current showroom's record IDs or historical orders.

The owner must choose before importer code is written. If none of these trade-offs is acceptable, keep Phase B paused. No currency decision or setting change is authorized by this PR.

All proposed entities and transactions are fictional. No real company, customer, contact detail, fitment, OEM match, sale, invoice, forecast accuracy or business validation is asserted. Keep the discreet Demo indicator and administrator-visible provenance; product names remain natural.

### Example business stories

1. **Engine oil filter AT-FLT-001, Central:** this retained product existed by April 13. Receive 24 July 1; deliver 5 July 6; receive 12 July 12; deliver 7 July 20; return 2 August 3 linked to that delivery; transfer 6 to South September 9; reserve 3 on an unshipped October 8 order. These proposed events contribute +20 on-hand to Central and +6 to South; the new reservation changes Central available stock by −3. They are movement deltas to be added to the captured legacy baseline, not asserted total stock balances.
2. **Front brake pad set AT-BRK-001:** this retained product existed by April 13. Receive 4 July 1; deliver all 4 July 30; propose a five-unit order August 5; receive 24 August 10; fulfill that same order on August 12. The August 12 delivery links to the August 5 order; it is not a second order or a second five-unit demand event. Keep the order waiting until the receipt, then complete it. Call August 5 a stockout only if a complete, location-scoped reconstruction proves zero available stock; otherwise describe it only as an unfulfilled order with unknown reason. Forecast history counts the completed delivery on August 12, not a made-up August 5 delivery or lost sale.
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
| Opening stock/reservations | Apply opening quantities through Odoo's native inventory-adjustment workflow and retain its resulting stock.move evidence. Read on-hand from stock.quant and reservations/open moves separately. No SQL quant writes or quant helper to force balances. |
| Forecast | autostock.forecast.run, observation and point through validated request, worker and source snapshot. React does not calculate demand or accuracy. |

## Historical dates and forecasting

The focus window is July 1–October 10 inclusive (102 days). The engine requires at least 90 complete observations and 28 training days. Retained history April 13–October 10 is 181 calendar days; a 60-day chronological holdout leaves 121 training days only where that product's source history is complete. Zero-delivery dates count only when the source is known complete.

Odoo stock completion sets stock.move.date to the current time. For new fictional rows only, validate with Odoo, then set predeclared event dates on the newly created order, picking and move through ORM in the same transaction before commit. Keep create_date/create_uid as actual import audit metadata. Test date fields, reservations, valuation and Forecasts/Inventory/Warehouses screens in the clone. Never edit existing completed rows; abort if dates cannot be maintained or presented truthfully.

Do not set or backdate create_date for new products. Keep Odoo's actual ORM creation timestamp and do not attach historical sales or stock history dated before that product existed. The four retained product templates created April 13 are the only current candidates for the full April–October history, subject to per-product source completeness, evaluation, nonzero-day and review checks. The other 60 retained products have October 10 creation dates and must not receive earlier history; newly created products likewise remain in insufficient-history states until they accrue enough real post-creation demo deliveries. Do not weaken the normal forecast guard.

This means the initial showroom cannot truthfully claim 181 days of valid history across all 150 products or produce long-horizon forecasts for the 60 later-created/new products. If the owner wants broad forecast coverage immediately, a separately scoped, explicitly fictional demo-history contract would need a different field and provenance from audit create_date, a clone-only gate, clear UI disclosure and its own review/tests. That alternative is not approved here. Recommended Phase B default: retain actual creation dates and limit evaluated historical forecasts to the four eligible April products; show honest insufficient-history states for the rest.

Pin dates; never derive them from today(). Convert explicit Africa/Casablanca times away from midnight to Odoo's UTC-naive storage and test the engine UTC-day bucket. Order <= picking completion/move time; returns happen later and link to their delivery. One event key maps to one transaction. Never rewrite old observations, cutoffs or review statuses. New forecasts stay unreviewed; stockout-censored deliveries are not treated as unconstrained demand.

### Forecast snapshot invalidation after imported history

The current restock eligibility check looks at run identity, review/evaluation, cutoff age, history-end age and point coverage, but does not compare the stored source_snapshot_sha256 with a newly changed source history. A backfill could therefore leave an old, recently reviewed run eligible even though it predates the imported events.

Before any backfill is enabled, Stage B must add a tested per-company/product/warehouse history revision barrier. A completed run records the source revision used to calculate it. Importing any dated delivery/return change increments the affected scope revision in the same transaction. Replenishment eligibility requires the run's revision to equal the current scope revision, as well as existing freshness and review checks. A revision mismatch makes the run ineligible without changing its saved points, hash, review status or audit fields. Keep old runs available in Saved history. Generate replacement runs through the existing worker and leave them unreviewed until a manager reviews them.

Required regression: start with an old run that is still fresh, fully evaluated and manager-reviewed; add/backfill a source sale in the clone; assert the old run remains unchanged for history but is rejected by current restock eligibility; generate a new run at the new revision and verify it is not eligible before review and is eligible only after a manager reviews it. If the revision barrier cannot be implemented and tested, do not import history or show old forecasts as current replenishment evidence.

### Stock reconciliation boundary

The 64 retained products are already a legacy-unreconciled cohort: the read-only baseline comparison found their existing quant balances did not match a complete signed move ledger. Preserve them as found. Do not claim that adding receipts makes their full lifetime ledger reconcile.

Report two populations separately in clone QA:

1. **New SKU/location ledgers:** each new product/location starts with one native, recorded opening adjustment dated at or after the product's actual creation. For the same product, location and inventory UoM, verify opening adjustment + completed receipts + completed customer returns + incoming transfers − completed customer deliveries − outgoing transfers ± later adjustments equals physical on-hand. No event may precede product creation. Validate using Odoo move/quant records; test reserved and available quantities separately. Transfers are movements between locations, never sales demand.
2. **Retained legacy products:** capture the pre-import quant balance by product/location/UoM and a move-ID/date watermark. Do not reconcile their old lifetime ledger. If a later owner-approved change touches one, compare only the post-watermark movement delta with after-minus-before quant, and report the legacy opening mismatch separately. Never rewrite an old move or quant to make the equation appear to balance.

The Stage B report must state how many new ledgers reconcile and how many legacy ledgers remain unreconciled, with no single global “150 products reconcile” claim. Fail the clone acceptance check if a new ledger does not balance or if an imported write changes an unapproved legacy balance.

## Preservation and clone plan

Nothing here has been executed. After approval to implement:

1. With future owner approval, record the original DB/endpoint identity, addon/seed versions, company/warehouse IDs, baseline counts, original Compose project, container IDs, PostgreSQL system identifier, volume IDs/mounts and filestore path. This is a read-only preflight; do not rely on the database name alone.
2. Back up only autostock_showroom_demo and its matching filestore directory: PostgreSQL custom-format dump plus archive of /var/lib/odoo/filestore/autostock_showroom_demo. Record sizes and SHA-256 hashes for both artifacts in an owner-reviewed, signed backup manifest. Verify a restore before using the backup. Keep backups outside the repo in a private ignored path; never commit them.
3. Restore to a new database named autostock_showroom_demo_morocco_clone under a distinct Compose project such as autostock-atlas-morocco-clone, with a separate network, Odoo/PostgreSQL containers, generated credentials and new named volumes. Verify the actual Compose project label, database endpoint/cluster identity and mounted volume IDs; refuse if either original volume is attached. Do not reuse the original DB name merely to pass a weak name allowlist.
4. Only after restore verification, generate a unique clone UUID and write a clone-identity marker into the clone. Keep an approval manifest outside the repository binding that UUID to the clone DB name, PostgreSQL system identifier, Compose project, separate volume IDs and the signed-off source backup hashes. The marker must not exist in the source database.
5. Use a two-part fail-closed gate. Inside Odoo, the importer checks the exact clone DB name, expected clone UUID/marker, dataset version, selected company and explicit Apply approval; a missing or mismatched value aborts before any business write. The Windows wrapper independently verifies the expected Compose project/service labels, database host/container identity, PostgreSQL system identifier, marker UUID, backup hashes and actual volume mounts against the approved manifest and an explicit denylist of the original endpoint and volume IDs. Odoo cannot verify Docker labels, volume mounts or the backup fingerprint; the wrapper cannot substitute for Odoo's company/record-rule checks.
6. Dry-run is genuinely no-write: the wrapper's endpoint and manifest checks are read-only; Odoo runs the preview in a read-only transaction and uses no create/write/unlink, sequence allocation, chatter, forecast queue or marker mutation. It reports proposed counts and product/location/UoM ledger deltas only. If read-only execution cannot be enforced, abort instead of calling it a dry-run.
7. Apply defaults to refusal. It requires an explicit clone target, exact matching approval manifest and clone UUID confirmation; DB name alone is never sufficient. No override flag may redirect the clone workflow to the original. A later import into the original showroom would need a separate owner approval, separately reviewed backup/restore, endpoint-specific guard and distinct workflow; this PR does not authorize or implement it.
8. Repeat the clone dry-run after apply. A second apply must create zero records and change zero finalized values. A changed completed event requires a new manifest version and a restored clone.

### Windows operator flow (future tooling)

Stage B can add a PowerShell command with dry-run default, for example a future prepare_atlas_morocco_clone.ps1 -Mode DryRun. The wrapper verifies Docker project/service identity, actual mounts, DB cluster identity, clone UUID and approved backup fingerprints before it invokes Odoo. Odoo separately verifies the exact clone DB name and clone-only marker before Apply. Review the DB/module/key/count report. A future -Mode Apply requires explicit clone approval and cannot target the original endpoint. The PR #17 launcher/seed is not on main; this proposal does not claim those commands exist.

Do not use docker compose down -v, volume prune, WSL unregister, reset switches, or commands targeting the original volumes.

## Review decisions and Stage B acceptance

1. **Currency (owner choice before importer code):** recommended—preserve the existing USD company and use only explicit MAD supplier terms/validated MAD pricelists; alternative—add a separate MAD company in the clone; alternative—approve a documented same-company FX/accounting migration using owner-supplied rates; alternative—create a clean Moroccan database without legacy IDs/history.
2. **Forecast breadth:** recommended—keep actual product creation timestamps and initially evaluate only the four eligible April products; show insufficient history for other products. A separately approved demo-history/provenance design is needed to claim broad historical coverage.
3. **Legacy data:** preserve original orders, pickings, moves, quant balances and forecast snapshots; mark the 64 legacy stock ledgers unreconciled and report new controlled ledgers separately.
4. **Scope:** approve the 150/8/18 catalogue and proposed transaction counts, knowing the four existing April-created products are the only initial candidates for 181-day history unless the owner selects another approved provenance path.
5. **Language readiness:** review draft EN/FR/AR labels. No language switch, RTL UI, or Issue #37 implementation.

Stage B tests: clone-marker and endpoint/volume guards, signed backup fingerprint, no-write dry-run, deterministic/idempotent apply, creation/history boundary, linked order fulfillment, chronological sale/receipt/return/transfer links, new-ledger reconciliation, legacy post-watermark delta reconciliation, no duplicate transfer demand, reservation totals, per-scope forecast revision invalidation, company/warehouse permissions, truthful 7/30/60 evaluation and stockout/insufficient-history states. Report new and legacy ledger populations separately. Then run frontend/API checks and actual Dashboard, Inventory, Warehouses, Suppliers and Forecasts browser journeys on the clone at desktop/tablet/mobile. Verify no browser errors, overflow or seed records after October 10.

Planning estimate: several minutes to about 15 minutes for 350 orders, stock workflows and selected forecasts on healthy local Docker. This is unmeasured; benchmark clone dry-run, apply and forecasts separately.

## Phase A boundary

- Read Issue #36, its planning comment, project docs, forecasting rules, seed scripts and legacy PR #17.
- Created this proposal and non-executable manifest only.
- No import, backup, clone, module install, service shutdown, browser run or screenshot.
- Original Atlas DB, filestore, credentials and named volumes remain untouched.
- No business validation, real-world forecast accuracy or production-readiness claim.
