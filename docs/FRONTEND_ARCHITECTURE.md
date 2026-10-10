# React frontend foundation

The React client in [`frontend/`](../frontend/) is the new AutoStock user interface direction. It uses React 19, TypeScript, Vite, Tailwind CSS 4, Shadcn/Radix primitives, TanStack Router and TanStack Query. Selected UI foundations are vendored from [`satnaing/shadcn-admin`](https://github.com/satnaing/shadcn-admin) under the preserved MIT notice in [`frontend/LICENSES/`](../frontend/LICENSES/). Demo pages and mock business records are excluded.

## Scope of this first frontend PR

The only completed application screen is the Dashboard. The shell contains a dashboard link, a product search dialog, an authorized-company selector, the Odoo connection state and account sign-out. Inventory, full Forecasts, Restock, Phase 3B, purchasing, reports and the assistant are future work and are not shown as placeholder destinations.

The existing Owl implementation remains in the addon unchanged during this foundation PR. The new API and React app are developed alongside it so the new client can be reviewed before a later cutover.

## Session and data flow

```text
Browser ── Odoo session cookie ──> /web/session/authenticate
   │
   └── credentials: include ─────> /autostock/api/v1/*
                                      │
                                      ├─ current Odoo user and authorized companies
                                      ├─ autostock.dashboard.get_dashboard_data()
                                      ├─ autostock.inventory.risk.get_risk_data()
                                      └─ autostock.forecast.run.get_forecast_snapshot()
```

The browser holds only the Odoo session cookie. The React app does not store or receive a database password after sign-in. Each API route uses `auth="user"`, ORM access with no `sudo()`, validates the selected company against `request.env.companies`, and creates a company-scoped ORM environment with `with_company()` and `allowed_company_ids=[company.id]`. Warehouse filters are passed to the existing risk service, which validates ownership and continues to enforce Odoo record rules.

All dashboard values come from existing server-side calculations. The frontend maps those responses for display and validates their versioned shape with Zod. It does not calculate on-hand stock, inventory coverage, reorder quantities, supplier lead time, forecasts, or forecast evaluation. Bounded backend data is labeled as partial when the service says its coverage is incomplete. Restock previews are read-only.

The API surface is:

| Route | Source | Purpose |
| --- | --- | --- |
| `GET /autostock/api/v1/session` | Odoo session and company records | User identity, permissions, active/authorized companies and demo-environment label |
| `GET /autostock/api/v1/dashboard` | `autostock.dashboard` | KPI counts and sampled/complete inventory-health summary |
| `GET /autostock/api/v1/dashboard/restock-preview` | `autostock.inventory.risk` | Up to five read-only priority positions, optional company warehouse filter, and scan coverage |
| `GET /autostock/api/v1/dashboard/forecast-preview` | `autostock.forecast.run` | A completed eligible forecast snapshot, or a truthful unavailable/restricted result |
| `GET /autostock/api/v1/search/products` | `product.product` ORM search | Small active-company product search, respecting inventory permissions |

Each response includes `schema_version: 1`. Contract tests run in frontend CI; Odoo `HttpCase` tests exercise the controller contracts and permission boundaries against Odoo 19 and PostgreSQL 16.

## Local development

```powershell
cd frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

The default Vite proxy target is `http://127.0.0.1:8177` and its showroom database is `autostock_showroom_demo`. Override `ODOO_PROXY_TARGET` and `VITE_ODOO_DATABASE` in the ignored `.env.local` file for another local Odoo instance. Sign in using a normal Odoo user account. Do not put passwords in `.env.local`, source control, or screenshots.

The review gates are `npm run lint`, `npm run typecheck`, `npm run test:unit`, `npm run test:contract`, `npm run test:browser`, and `npm run build`. Browser tests run against explicit frontend-only fixtures; the visual QA screenshots are captured separately against the authenticated local Odoo showroom.
