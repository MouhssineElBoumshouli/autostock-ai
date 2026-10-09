# AutoStock AI

**An Odoo 19 Community addon for automotive inventory intelligence.**

Built as a new project concept for Bounaim Auto, separate from SmartImport. This repository is a **foundation release**, not a completed AI ERP. The dashboard reads real Odoo stock; the forecasting experiment works offline and is **not yet connected** to Odoo.

![Approved UI direction](design/dashboard-concept.png)

> The screenshot is an AI-generated **design concept**, not a capture of the running implementation. Its sample figures and claimed accuracy are illustrative and must not be treated as measured results. The working dashboard intentionally shows empty AI states until integration.

## What is included now

- Local-only Docker Compose Odoo 19 + PostgreSQL environment.
- Custom installable Odoo module `autostock_ai`, separate from Odoo core.
- Automotive product metadata: OEM reference, priority, safety stock, planning lead time, enable/disable tracking.
- Read-only **Owl dashboard** based on Odoo stock, with four KPI cards, inventory health summary, and product table.
- Explicit `not_integrated` empty states for AI features (no fake predictions).
- Offline **scikit-learn demand forecasting experiment**, with chronological evaluation, naive baseline comparison, reproducible results and labeled heuristic error bands.
- Synthetic-only CSV sales generator for ML testing.
- Product model tests (for Odoo runtime), offline tests, GitHub Actions configuration, product/design/architecture docs.

**Not implemented:** ML-to-Odoo sync, report generator, assistant, simulator, budget optimizer, full mockup-matching visual polish, production deployment, and comprehensive security review. These are planned milestones, not completed features.

## Start Odoo on Windows (Docker Desktop + WSL2)

1. Install **Docker Desktop** and enable the WSL2 backend. Open a terminal in the project folder.
2. Create `.env`: PowerShell `Copy-Item .env.example .env` (or bash `cp .env.example .env`). **Edit `.env` to set a strong unique POSTGRES_PASSWORD**. Do not commit this file.
3. Start services: `docker compose up -d`
4. Open **http://localhost:8069** (the port binds to `127.0.0.1` only). Create an Odoo database and choose your own database administrator credentials.
5. In **Apps**, use *Update Apps List* (enable developer mode if needed). Search for **AutoStock AI — Inventory Intelligence** and install. Odoo's Inventory app will be installed as a dependency.
6. Open **AutoStock AI → Automotive Inventory**, then create/edit products and enable **Track in AutoStock AI** on the product's **AutoStock AI** tab. Return to **AutoStock AI → Dashboard** and refresh.

Useful commands: `docker compose ps`, `docker compose logs -f odoo`, `docker compose down`. **Do not** run `docker compose down -v` unless you mean to erase local database and filestore volumes.

**Security:** This is local development only. Never deploy the container ports publicly or import Bounaim Auto's confidential records without explicit permission and security review. Odoo's web administrator, master DB password, permissions, secure sessions and backups must all be configured before production use. The Compose file is not a hardened production deployment.

## Run the offline AI research

With Python 3.11+ installed:

```bash
python -m venv .venv
# Activate the environment for your OS
python -m pip install -r ml/requirements.txt
python scripts/generate_synthetic_sales.py
python -m ml.evaluate ml/output/synthetic_daily_sales.csv --days 30
python -m pytest -q
```

Check `ml/output/forecast.json` for, per SKU: selected approach, chronological holdout MAE for the ML model and baseline, and daily predictions. This is **synthetic-data evaluation only**; the result is not a real business forecast. The ML code intentionally declines to forecast with under 90 days of history. Error bands are heuristic, not calibrated confidence intervals. A single holdout and a tiny synthetic generator are insufficient proof of real-world accuracy.

## Milestones

1. **Foundation (this package):** Odoo project setup, secure read-only dashboard, product metadata, offline ML experiment, tests, design/spec.
2. **Data & ML:** explicit review of Odoo sales histories, daily sales aggregation, source provenance, leakage-free backtests against seasonality and intermittency, permission-aware forecast storage and a forecast chart.
3. **Decision tools:** stockout risk, human-approved replenishment quantities, constraint-based budget optimizer, what-if simulation.
4. **AI explanations & reports:** controlled read-only natural-language queries; print-quality PDF management report with executive summary, evidence, tables, forecasts, assumptions, and a technical appendix.
5. **Experience & release quality:** implement the full approved design consistently throughout Odoo; keyboard/mobile/accessibility checks, end-to-end tests, backup and operational documentation.

See [CODEX_START_HERE.md](CODEX_START_HERE.md), [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md), and [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).

## Source references

- [Odoo 19 developer documentation](https://www.odoo.com/documentation/19.0/developer.html)
- [Odoo 19 client actions](https://www.odoo.com/documentation/19.0/developer/howtos/javascript_client_action.html)
- [Odoo 19 replenishment (existing native behavior)](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/warehouses_storage/replenishment.html)
- [Official Odoo Docker image / addon mounts](https://github.com/odoo/docker-docs/blob/master/odoo/content.md)

## Academic and business integrity

SmartImport was completed during the Bounaim Auto internship from **1 July to 26 August 2026**. AutoStock AI is a **new, later project**. Its work and dates must be accurately disclosed in any university presentation; confirm that new work is eligible for inclusion. Synthetic reports and model results must be labeled as such. Do not claim Bounaim Auto adopted or approved the software without authorization.
