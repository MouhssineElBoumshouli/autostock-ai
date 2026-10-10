# AutoStock AI local showroom guide

This guide opens the current application in a locally hosted fictional automotive parts business. It is for product review and exploration; it is not a production deployment.

## One-command setup on Windows

1. Install Docker Desktop, enable its WSL2 engine, and wait until Docker Desktop reports that it is running.
2. Open PowerShell in the AutoStock AI repository folder.
3. Run:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_showroom_demo.ps1
   ```

The first run builds the Odoo image, creates the dedicated `autostock_showroom_demo` database, installs Odoo Inventory/Sales and AutoStock AI, loads Atlas Auto Distribution's generated business records, evaluates its completed Odoo delivery histories, and opens the sign-in page. It can take several minutes the first time. The command selects an available localhost port from 8177–8190 and prints the URL it selected.

Open `.showroom\credentials.txt` in the repository folder for the generated local login. The login is `admin`; the password is generated locally and is not committed. Enter those values on the opened Odoo page. The company card and a small **Demo environment** chip identify the fictional showroom.

## Five-to-ten-minute walkthrough

1. **Dashboard:** Review the live inventory cards and the on-hand/projected quantities. Counts come from this database's Odoo product, stock quant, move and reorder-policy records.
2. **Inventory:** Choose *View inventory* or *Inventory* to open the normal Odoo product list. Search for `AT-FLT-001` (Engine Oil Filter) or `AT-BRK-001` (Front Brake Pad Set), then open a product to see its category and AutoStock settings.
3. **Forecasts:** The showroom opens on a saved 30-day forecast for completed Odoo deliveries. Inspect the chart and the evaluation summary. Use the 30/90/Full history controls and try the 7-, 30- and 60-day horizons. The four featured products have completed examples for each horizon.
4. Expand **Source and evaluation details** to see the date coverage, source cutoff, model version, provenance and limitations. The badge means that all showroom business records are fictional and generated locally. MAE values are calculated comparisons on this generated history; they are not claims of accuracy for a real parts business.
5. **Stock risks:** Choose *Stock risks*, select Atlas Central Warehouse, and filter to *Recommendations*. Open **Why this status and quantity?** for the actual Odoo stock position, reviewed forecast evidence, supplier MOQ, order policy and quantity calculation. This page is read-only and does not create a purchase order.
6. Change to **South Service Depot** to compare its separate stock records. Try a different risk state, vendor or part search to explore the filters.
7. To compare the separate in-app synthetic forecast sample, return to **Forecasts** and select *Synthetic demo* as the source. That sample uses the existing generated forecasting path and remains separate from the showroom's Odoo sale/delivery records.

The fictitious supplier, customer, part, sales, stock and pricing values exist only to make a coherent local business scenario. The Odoo deliveries and current quants are real records inside the disposable showroom database, and the forecast/risk output is produced by the installed application. Generated histories are not evidence of actual customer demand or forecast accuracy.

## Start, stop and reset

- Start or reopen the showroom: run the same setup command again. It reuses the dedicated database and does not duplicate its seeded records.
- Stop the containers but retain the database: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_showroom_demo.ps1 -Stop`.
- Reset the database: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_showroom_demo.ps1 -Reset`. Type exactly `autostock_showroom_demo` when prompted. This removes only that database from the showroom's own PostgreSQL service, then rebuilds it. It does not remove the dedicated volumes or change any other Compose project or database.
- Keep `.showroom\` private. It contains locally generated PostgreSQL, Odoo master and user passwords and is ignored by Git.

## Troubleshooting

- **Docker is not running:** Start Docker Desktop, confirm its WSL2 engine is ready, then rerun the setup command.
- **A port is busy:** The setup selects another free port from 8177–8190 and saves it for next time. If all are occupied, stop a local service and retry.
- **Odoo does not open:** The setup prints the selected URL and recent Odoo logs. Retry the setup after the service becomes ready; its database and named volumes are retained for diagnosis.
- **Forgot the local password:** Read it from `.showroom\credentials.txt`. A manually changed Odoo password is not replaced on restart. `-Reset` recreates the disposable account and asks before removing the exact showroom database.
- **Setup says credentials are incomplete while a volume exists:** Restore the ignored `.showroom\.env` from a private local backup. The script refuses to rotate a database password or erase the existing volume automatically.

The standard developer Compose stack in `docker-compose.yml` is a separate environment. The showroom uses its own Docker Compose project, private PostgreSQL service, named data/filestore volumes, localhost-only Odoo port and exact Odoo database filter.
