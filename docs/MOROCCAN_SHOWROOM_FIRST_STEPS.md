# Moroccan showroom: first safe checks (Windows)

This is the **preparation stage**. It does not start Odoo, create a database,
import data, change the active AutoStock application, or touch the old USD Atlas
showroom. The Moroccan environment is separate.

## 1. Open the project on your Windows computer

Open **PowerShell** inside your local `autostock-ai` repository. Make sure
Docker Desktop is installed and running if you plan to run the isolation check.

Do not use the original Atlas showroom folder or its launch command.

Check the tools:

```powershell
python --version
docker compose version
```

If Python dependencies are missing, install the project's existing requirements
(preferably in your usual virtual environment):

```powershell
python -m pip install -r ml/requirements.txt
```

## 2. Prepare the *new* Moroccan environment

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\moroccan_showroom\prepare.ps1 -Action Prepare
```

This creates an ignored `.env.atlas-morocco` with new local credentials and a
target identifier. **Run it only once**. It deliberately refuses to overwrite
an existing file; if one exists, do not delete it or regenerate the credentials.

Never paste the contents of `.env.atlas-morocco` in chat, GitHub, screenshots,
or logs. Do not commit it.

## 3. Check the dataset without touching Odoo

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\moroccan_showroom\prepare.ps1 -Action DryRun
```

Look for these values in the JSON output:

- `"mode": "offline-dry-run"`
- `"connected_to_odoo": false`
- `"database_mutations": 0` and `"writes_performed": 0`
- `"planned_stock_ledger_reconciled": true`
- `"dataset_version": "atlas-ma-2026.4"`
- `"dataset_sha256": "13b0e6ad858cec5c14192785b849c59b86143eb1f785d1c8cb033df3db174880"`

The planned dataset contains 150 fictional parts, 8 suppliers, 18 customers,
two Moroccan warehouses, 30 history profiles, and 90 **unreviewed** forecast
requests. This check does **not** verify live Odoo stock, forecasts, or backup
and restore.

## 4. Check Docker isolation (read-only)

Only after Prepare, with Docker Desktop running:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\moroccan_showroom\prepare.ps1 -Action Status
```

Status checks the new target's Compose configuration, localhost-only port
`8070`, labels, volumes, and network. It only **lists** existing old Atlas
containers to ensure we are not mixing environments. It does not start or
modify them. An empty container list is normal before the Moroccan services
have been started.

If any command fails, stop and share the **redacted error** for review. Do
not delete volumes, reset Docker, remove credentials, or bypass safety checks.

## 5. What remains blocked

These are separate future steps, **not** part of this guide:

1. Review a small, independently tested target-only database-and-filestore
   backup and actual restore procedure. The existing signed manifest helper
   verifies hashes, **not** that a restore succeeded.
2. Get separate owner approval before starting/initializing the new Moroccan
   database or importing records. The public `Apply` path is still disabled.
3. Verify imported records, warehouse-specific forecasts, manager review,
   historical-data freshness, and the app on desktop, tablet and mobile.
4. Get explicit owner approval **again** before changing the active app
   connection to the Moroccan database.

Never use `docker compose down -v`, destructive resets or cleanup/prune
commands, or the legacy Atlas database/filestore as an import target.

### Important about forecast dates

The prepared fictional history ends **10 October 2026**. The app's normal
14-day freshness rule stays in place. Once results are stale, display them
as **historical examples** and withhold current forecast-based reorder advice,
unless we deliberately build and verify a newer, correctly dated dataset.

**Useful references:** [Moroccan importer and safety details](../scripts/moroccan_showroom/README.md),
[warehouse forecast acceptance gate](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/42),
and [readable-code requirements](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/38).
