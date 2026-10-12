# Issue #36 — Phase A Moroccan Atlas showroom proposal

**Decision:** build a fresh, one-company Moroccan Atlas Auto Distribution showroom with MAD as its actual base currency in a separate database and runtime. The owner recorded this decision in [PR #39](https://github.com/MouhssineElBoumshouli/autostock-ai/pull/39#issuecomment-6120933420).

**Phase A status:** proposal and inspectable manifest only. This document does not provision a database, create records, run a seed, or change the running application. The approved architecture replaces the former extension/clone alternatives.

## Decision and legacy showroom boundary

The existing USD showroom and the new Moroccan showroom are separate products of the local demo setup:

- Keep the existing autostock_showroom_demo database, original PostgreSQL and filestore volumes, credentials, containers, compose project, and launch path available without changes.
- Do not clone, restore, migrate, merge, relabel, or import any legacy business record into the Moroccan database. The old database remains useful as a read-only reference and can still be launched separately.
- Create the Moroccan environment from a fresh Odoo database. It receives new Odoo IDs, its own company and partners, its own PostgreSQL data volume and Odoo filestore, its own network, Compose project, config, ignored credentials file, and local port.
- The main application continues to point to the old environment until the new one passes backend, API, browser, and owner review and the owner separately approves a cutover. This implementation PR does not provision, seed, or switch the application.

The Phase A read-only audit below records the old environment only so future checks can explicitly protect it. Its records are not inputs to the target manifest or generator.

## Read-only audit of the existing environment

These are workstation observations captured on 12 October 2026, not a migration contract. Future tooling must remeasure its actual environment and fail closed on drift.

| Item | Observed existing environment |
|---|---|
| Database/runtime | autostock_showroom_demo, about 61 MB; Odoo 19 and PostgreSQL 16 |
| Compose resources | project autostock-showroom-demo; containers autostock-showroom-demo-odoo-1, autostock-showroom-demo-db-1; volumes autostock_ai_showroom_postgres, autostock_ai_showroom_filestore |
| Existing company | Atlas Auto Distribution, Marrakech, Morocco; base currency USD; MAD inactive |
| Existing records | 64 products, 2 warehouses, 4 suppliers, 3 customers, 174 sales and completed pickings |
| Existing activity limits | no completed customer returns, vendor receipts, internal transfers, or open outbound moves |
| Forecasts | 13 completed saved runs, 12 reviewed; history spans 13 April–9 October 2026 |
| Ledger quality | the legacy quant balances did not reconcile to the complete signed move ledger for all 64 products; preserve as observed and do not claim reconciliation |

Existing sale-order and completed-picking timestamps also do not align with the historical stock-move dates. The original seed used quant helpers to set snapshot balances without a complete movement ledger. These are known fixture-history limitations, not a reason to rewrite or delete any legacy row. No legacy ID, saved forecast, currency amount, or movement is carried into the target.

## Target Moroccan showroom

The human-reviewable [YAML manifest](issue-36-moroccan-atlas-manifest.yaml) describes fictional data and stable fixture keys. It is documentation, not an executable seed file.

| Area | Selected target |
|---|---|
| Company | Atlas Auto Distribution, Marrakech, Morocco; one company; Africa/Casablanca; MAD configured as company currency before prices, stock valuation, or sale records are created |
| Warehouses | Atlas Central Warehouse and South Service Depot; created as new records in the new database with newly generated IDs |
| Products | 150 distinct automotive-parts SKUs across filters/service, brakes, suspension/steering, electrical/batteries, cooling/belts/drivetrain, and ignition/sensors/fluids |
| Suppliers and customers | 8 fictional Moroccan suppliers and 18 fictional garages, retail counters, and fleet customers; no real phone, email, street address, tax ID, login, or business identity |
| Commercial terms | Illustrative MAD prices, supplier codes, native MOQ and price tiers, and lead-time assumptions; no market research or tax advice is claimed |
| Sales and operations | About 350 completed order/delivery pairs in the 1 July–10 October 2026 focus window, 30 incoming receipts, 12 linked customer returns, 18 internal transfer journeys, and 20 confirmed open orders to exercise reservations |
| Forecast source window | For 24 designated representative products, a separate, explicit fictional business-effective coverage period from 13 April through 10 October 2026 (181 calendar days). The additional April–June history supports chronological 30/60-day holdouts; it is not presented as real business evidence. Long-tail products may remain intermittent or have insufficient history. |
| Languages | One language-independent record per SKU. Draft EN/FR/AR names and aliases are review data; UI localization and RTL remain in Issue #37. |

No purchase orders or vendor bills are proposed because Purchase is not required for this scope and may not be installed. Receipts use native Odoo stock workflows. Do not invent vehicle fitment, OEM matching, supplier performance, lost sales, savings, forecast accuracy, or business validation.

All amounts in the manifest are fictional, illustrative MAD values with a provisional tax-exclusive display assumption. The import must not create an unapproved Moroccan tax mapping or imply that prices are verified quotations. Each supplier price tier retains its own currency, MOQ, ordering unit, and vendor code.

## Historical Odoo records and forecast provenance

Odoo audit timestamps remain truthful:

- Every product, partner, order, picking, move, and forecast record receives its real create_date and create_uid from the actual ORM import time.
- Business-effective event dates are pinned in the versioned manifest. The importer may set dates on newly created demo orders, pickings, and stock moves only after validating them through Odoo, using supported ORM writes within the same transaction. It must never edit a pre-existing record because none is imported.
- The product's creation timestamp is never backdated. The proposed April–October business history predates the eventual import time, so the ordinary production forecast guard must not be weakened or silently bypassed.

The current forecast request validates requested history against product.create_date. Before any importer is allowed to create historical dated moves, a narrowly scoped demo-history provenance path must be implemented and reviewed. It must require all of the following: a separately provisioned Moroccan target UUID and demo marker; a matching company/product history profile tied to the approved dataset version; a covered business-effective date range; a digest/count of the qualifying Odoo delivery source; and actual qualifying completed delivery moves in the target database. The worker must still build the observations from normal Odoo sale-linked completed moves, not from generator totals. Outside the explicitly marked demo database and matching product profile, the existing create_date guard remains unchanged.

Forecast runs must preserve source cutoff, source digest, dataset/provenance label, date coverage, evaluation window, method and baseline metrics. Forecasting/evaluation does not imply manager review. New runs remain unreviewed until a permitted manager reviews them in the application. Old review state is never copied or fabricated. A change to the dated source history must make older runs ineligible for current restock guidance through a tested history-revision barrier, while keeping their saved snapshots immutable. If these boundaries cannot be implemented and tested, the importer must refuse historical forecast data and the QA report must say those forecasts are unavailable.

Forecasts describe completed fictional deliveries in this demo dataset, not unconstrained market demand. Stockouts can censor completed sales. The configured coverage profile is an explicit demo assertion verified against the imported move population; it is not evidence about a real business.

## Genuine stock movement and reconciliation rules

All physical changes must be represented by native Odoo stock operations and resultant moves. Direct SQL writes, direct quant manipulation, and snapshot-forcing helpers are prohibited.

1. Each new product/location begins with a native opening inventory adjustment dated on or after that product's recorded creation time, unless the separately reviewed demo-history provenance contract explicitly covers its declared effective history. The adjustment and later events must have stable fixture keys.
2. Receipts use a validated incoming picking from a supplier location. Customer deliveries use confirmed sale orders and completed outgoing pickings linked to their sale lines. Returns use Odoo's return workflow and completed reverse moves linked to the original delivery. Transfers use internal pickings between the two warehouses; neither transfer leg counts as customer demand.
3. Reserved/open customer deliveries remain separate from physical on-hand. Reconcile on-hand from stock moves per product, location, and inventory UoM; calculate available and reserved using Odoo's native reservation data.
4. For each product/location ledger, verify opening adjustment + incoming receipts + returned units + transfer-in − completed deliveries − transfer-out ± later adjustments equals physical stock. Verify intermediate balances never go negative and verify that every return is linked to a real completed delivery in the generated fixture.
5. Report forecast-eligible products separately from all 150 catalog products. Report stock reconciliation by new target records and location. Do not claim the old database or one global catalog population reconciles.

The front brake-pad story is deliberately linked: an order created on 5 August is fulfilled from the same order after a receipt on 10 August, with delivery on 12 August. The order is not duplicated and the unfulfilled interval is not a completed sale or a lost sale. Call an event a stockout only when the chronological location ledger proves zero available quantity.

## Deterministic data and idempotency design

The generator uses a pinned dataset version, pinned date window, explicit random seed, stable fixture keys, and no today() dependency. Repeating generation with the same version and seed must produce byte-identical canonical output and the same counts/digests.

Each Odoo record is matched by a model-specific stable external key in the new database. The importer must fail on duplicate keys, ambiguous matches, mismatched SKU/company scope, unexpected pre-existing records, or conflicting completed events. It must not match by old database-local numeric IDs. Re-running an unchanged plan must yield no creates or writes. Changing a completed transaction requires a new dataset version and a restored disposable target, not editing the prior event in place.

A dry run is read-only from preflight through report generation. It must not allocate Odoo sequences, create XML IDs, write chatter, change a marker, create stock moves, queue forecasts, or call ORM create/write/unlink. Tests must prove no database state change around dry-run. Apply must require an explicit, separate approval and exact target identity; it is not run in this task.

## Environment isolation, backup, and rollback plan

The future Moroccan local environment uses a new name such as autostock_atlas_morocco_demo, a distinct Compose project, network, Odoo/PostgreSQL services, generated ignored credentials, and newly created uniquely named PostgreSQL and filestore volumes. Only the Odoo web port is exposed to localhost on a port that does not conflict with the old showroom. PostgreSQL remains private to the new network.

Before any future approved import:

- Independently verify the new Compose project/service labels, database host and PostgreSQL cluster system identifier, exact database name, target UUID marker, and actual volume mounts.
- Confirm that none of the existing Atlas project, containers, endpoint, or volumes is attached. A database name alone is never sufficient evidence.
- Take a matching database and filestore backup of the new target before import; write sizes and SHA-256 digests to a private, ignored backup manifest. Test restoring that backup to a separate disposable environment.
- Keep a checked, separate launch command for the existing USD showroom. Rollback means relaunching that untouched old environment; never reuse or delete its storage.

No down-v, volume prune, WSL reset, source-database restore, or generic cleanup command is allowed in the setup flow. Any later Apply requires explicit owner approval after independent review. This implementation PR only prepares tooling and tests; it does not start the new Compose project, initialize its database, run a dry-run against Odoo, import records, or change the app's database.

## Stage B acceptance gates

Before seeking approval to import:

- Fresh MAD database installation and configuration verified from code, with no inherited company, partner, product, or transaction IDs.
- Odoo ORM workflow tests for company currency, timezone conversion, actual audit timestamps, event chronology, sale/delivery linkage, receipts, linked returns, transfers, open reservations, UoM conversions, no-negative intermediate stock, and reconciled per-location quantities.
- Deterministic generator tests for stable output, every target count, same SKU identity across language labels, no invented fitment, and dated events pinned to the manifest.
- Safety tests for original project/volume/endpoint denial, target UUID mismatch, duplicate identity, missing modules/currency, changed manifest, unapproved Apply, idempotent repeat, and true no-write dry-run.
- Forecast source tests proving that only the marked Moroccan demo target and matching covered profiles can use declared demo-effective dates, while an ordinary database retains the actual product-create-date limit. Validate coverage, source digest and revision invalidation; keep new forecasts unreviewed.
- After separately authorized provisioning/import, run the complete backend/API/frontend/browser suite and document actual Atlas screenshots at desktop, tablet, and mobile. No screenshot or report may claim that those future checks have already passed.

## Scope boundary

PR #39 remains the documentation-only Phase A review. The separate implementation PR starts from latest main and contains the provisioning/generator/safety/dry-run preparation. Neither PR authorizes import, switching the app, deleting the old showroom, merging, or deploying.
