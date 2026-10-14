# Moroccan Atlas showroom preparation and importer

The Moroccan showroom is designed as a separate local Odoo/PostgreSQL environment. It does not use the existing USD showroom's database, containers, credentials, volumes, or launch command.

## Commands

From the repository root in PowerShell, run:

    python -m pip install -r ml/requirements.txt
    pwsh scripts/moroccan_showroom/prepare.ps1 -Action Prepare
    pwsh scripts/moroccan_showroom/prepare.ps1 -Action DryRun

Prepare writes newly generated local credentials and a target UUID to the ignored .env.atlas-morocco file. It refuses to overwrite an existing file. It does not run Docker or connect to either database.

DryRun generates the pinned dataset and checks target counts, stable keys, date windows, event links, import-plan idempotency, and product/location stock arithmetic. It is an offline preview and does not inspect or write an Odoo database. The `odoo_importer` module adds a read-only Odoo preview and the ORM writer. Apply remains fail-closed unless the exact typed target UUID, live target identity, signed backup bytes, and successful independent restore evidence all validate.

The requirements pin IANA timezone data so Windows and the Odoo container use the date-correct `Africa/Casablanca` offset for each planned event timestamp.

After independent review and separate owner authorization, Start can launch only the new Compose project:

    pwsh scripts/moroccan_showroom/prepare.ps1 -Action Start

Start validates the Compose project, bind address, private database service, volume names, dedicated Moroccan Odoo image identity, and existing target-resource labels before starting the separate Odoo and PostgreSQL services. It rebuilds only the dedicated `autostock-ai-odoo-morocco:19.0` web image from the current Dockerfile so stale/shared Atlas images cannot be reused. It does not initialize the database, import fixture records, or change the main app connection. The Odoo preview script is read-only.

## Odoo importer boundary

The Odoo adapter first verifies the exact target database name, administrator session, environment UUID, single clean company, required installed modules, and consistent target markers. It renames the fresh database's bootstrap company to Atlas Auto Distribution and sets its country, currency, and time zone; it does not add another company. It reuses Odoo's untouched main-company bootstrap warehouse as Atlas Central Warehouse and creates the South Service Depot, so the finished database has exactly the two planned warehouses. It then writes versioned fixture identities and uses Odoo ORM operations for catalog records, inventory adjustments, confirmed sales and validated deliveries, receipts, linked customer returns, internal transfers, open orders, orderpoints, and forecast requests. Final stock is reconciled per product and warehouse against the generated ledger before the transaction completes. A conflict, incomplete registry, broken record reference, history mismatch, or stock variance fails the entire savepoint.

Odoo `create_date` and `create_uid` remain actual import audit values. The importer pins only Odoo business-effective dates for fictional movements. Company-wide complete history begins on 1 July 2026, when the full catalog's showroom activity starts. Dataset v2026.4 adds six separate historical profiles, three each for Atlas Central and South Service Depot, for products in filtration, braking, and suspension. Each profile's April–June events are separate dated fictional sales, and its July–October events are the actual completed showroom deliveries for that warehouse. Customer returns are included only when their native Odoo return move links to a delivery in the same product/warehouse history. For each of the 30 total profiles, the importer compares exact company, product, warehouse, version, date range, completed move counts and units, and the complete daily history digest before queuing a run. A company-wide profile cannot satisfy a warehouse request; the two warehouse profiles cannot substitute for one another. The existing before-product-creation guard stays in place for every other product and warehouse scope. Forecast requests are queued as unreviewed and retain fictional-source provenance; nothing in this setup marks them as reviewed or claims business accuracy.

History and forecast freshness rules remain the ordinary 14-day rules. With the fixture's last historical date of 10 October 2026, its results are potentially current only around the explicitly documented 13 October review point; they become stale as time advances. Do not freeze the production clock or relax freshness to keep this old demo populated. Before a later showroom cutover, either present the results as clearly historical examples with no current forecast-based replenishment guidance, or prepare and review a new dataset version with genuine, correctly dated Odoo movements for a current training window. Never change Odoo creation dates to manufacture history.

The guarded `run_import(..., mode="apply")` path requires the exact typed target UUID, cross-checked target identity, signed database + filestore bytes, and successful independent restore evidence before it can reach the ORM writer. Direct writer calls remain restricted outside Odoo test mode. The supported owner-local write path is only `local_target.ps1 -Action Apply`; it stops Moroccan web during the transaction, verifies the complete registry before commit, verifies it again in a separate read-only Odoo process, and restarts Moroccan web only after success.

## Dataset contract

The generator uses a fixed seed and explicit dates. Its canonical digest is stable for the same version and seed. Version `atlas-ma-2026.4` plans 150 SKUs, 8 fictional suppliers, 18 fictional customers, two warehouses, 350 focus-window delivered orders, 30 receipts, 12 linked returns, 18 transfers, 20 open orders, 24 company-wide profiles, and 6 warehouse-specific profiles. All 30 profiles have 181 daily observations (5,430 rows total). The 24 company-wide profiles include four products from each of the six automotive categories, with six examples in each planned demand class. The six warehouse profiles cover one product each from filtration, braking, and suspension at each warehouse. The deterministic dataset SHA-256 is `13b0e6ad858cec5c14192785b849c59b86143eb1f785d1c8cb033df3db174880` for seed `36036`.

The generated movement plan includes native opening adjustments and checks nonnegative intermediate stock and final ledger arithmetic per product/location. Sale deliveries, supplier receipts, customer returns, transfers, and unshipped orders remain distinct event types. Reservations do not change physical on-hand.

Odoo audit dates and users are left to Odoo; business-effective dates are pinned fictional event dates. The importer verifies all 30 history profiles against actual Odoo moves before queuing 90 unreviewed runs (30 profiles × 7/30/60-day horizons). CI integration tests exercise the warehouse profiles against completed Odoo delivery and linked return records. No local forecast request or review status has been created for this milestone.

## Backup and restore proof

Issue #46 adds a separate restore-proof layer before any local import. The CI proof performs a real PostgreSQL dump/restore and matching Odoo filestore archive/restore in disposable Docker resources, then checks the Odoo marker/module/table plus attachment and full filestore hashes. See [the QA note](../../docs/qa/issue-46-backup-restore.md).

The CI proof alone is not owner evidence. The owner's real Windows target backup and independent restore were completed separately before the Apply stage was authorized. The Apply command must point to that exact private backup directory and re-validates both its signed artifacts and restore evidence before any write.

## Local target verification

After explicit owner approval for the local verification stage, use the separate operator script. Do **not** rerun Prepare; it must reuse the existing ignored `.env.atlas-morocco` and target UUID.

From the repository root in PowerShell:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\moroccan_showroom\local_target.ps1 -Action Initialize
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\moroccan_showroom\local_target.ps1 -Action BackupRestore
    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\moroccan_showroom\local_target.ps1 -Action Apply -BackupStamp <yyyyMMdd-HHmmss> -TypedTargetUuid <prepared-uuid>

`Initialize` starts only the isolated Moroccan Compose project, creates the clean Odoo database if it does not already exist, installs AutoStock, stamps the exact prepared target UUID into the database/company markers, and creates one small technical attachment used only to prove filestore recovery. It refuses a mismatched marker, multiple companies, an existing dataset version, or existing fixture records.

`BackupRestore` stops only the Moroccan Odoo web service while taking a consistent database + filestore backup, signs and validates the backup manifest, restores the exact artifacts into unique no-port verifier resources, compares the restored module/marker/table/attachment/file-tree evidence, removes only those verifier resources, and restarts the Moroccan web service. Once cleanup is confirmed, it signs the complete restore-evidence JSON with the same protected HMAC key, using a separate signature domain and binding the evidence to the exact signed manifest. Apply verifies this signature before reading any evidence fields. The private dump, filestore archive, manifest, signing key, and restore evidence stay under the ignored `.showroom/morocco-backups/` directory. Do not share or commit them.

`Apply` requires the exact successful backup stamp and the prepared target UUID typed explicitly. It re-validates the live target identity, signed backup bytes, and restore evidence before and immediately after stopping Moroccan web. It mounts the approved backup read-only, runs the existing Odoo ORM importer, verifies all planned fixture identities and 90 forecast requests before committing, then verifies the committed registry again in a separate read-only Odoo process. On failure, it leaves Moroccan web stopped for inspection/recovery instead of continuing.

`Initialize` and `BackupRestore` still do **not** import `atlas-ma-2026.4`, modify the old USD Atlas showroom, or switch the application connection. After separate owner approval, `Apply` is a third action and remains isolated from application cutover.

## Safety limits

- The source database and volumes are explicit denylist entries. The setup never clones, mounts, starts, stops, or connects to them.
- The new target requires its own database name, Compose project, target UUID, PostgreSQL cluster identity, volume mounts, local endpoint, and matching database marker before any future Apply path can be considered.
- Both offline and live Odoo previews report zero mutations. Duplicate fixture keys, incomplete registries, missing registered records, content drift, and dirty first-import targets fail closed.
- The backup-manifest integrity check verifies an HMAC-SHA256 signature using a private key kept outside Git. It binds the database/project/target UUID, PostgreSQL system identifier, both named volumes, localhost endpoint, and actual dump and filestore sizes/hashes. Restore evidence has its own HMAC-SHA256 over every finalized observation and carries both the manifest HMAC and a canonical digest of the complete signed manifest. Apply additionally requires this authenticated evidence and re-checks the mounted backup bytes before the ORM transaction begins. Evidence from the earlier unsigned format must be regenerated by running BackupRestore again.
- Compose preflight checks the exact PostgreSQL and filestore named-volume mounts, the two expected read-only addon/script bind mounts, target UUID network labeling, and exclusive attachment to the private network. On a later authorized Start/Status, existing containers and network endpoints are re-inspected against the same boundary.
- Application cutover remains a separate gate. A successful dataset Apply does not change the frontend/backend connection and does not affect the independently runnable legacy USD Atlas showroom.
- No secrets, backup archives, target database, or generated data file belongs in Git.
