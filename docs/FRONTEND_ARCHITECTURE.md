# React frontend architecture

The React 19 + TypeScript client in [`frontend/`](../frontend/) is AutoStock AI's new UI direction. It uses Vite, Tailwind CSS 4, Shadcn/Radix primitives and TanStack Router. Selected foundations from [`satnaing/shadcn-admin`](https://github.com/satnaing/shadcn-admin) retain the MIT notice in [`frontend/LICENSES/`](../frontend/LICENSES/); its demo pages are not used.

## Issue #22 visual reset: Gates 1 and 2

The Dashboard in Gate 1 is a visual replica built against [`design/dashboard-concept.png`](../design/dashboard-concept.png). It renders from the typed development-only fixture in [`frontend/src/data/development-dashboard-fixture.ts`](../frontend/src/data/development-dashboard-fixture.ts). The fixture values are illustrative, are not Odoo records or evaluated business results, and appear with a visible preview label. The Dashboard does not import the Odoo API client, make network requests, or depend on the backend's response shape.

Gate 1 locked the visual composition. Gate 2 adds working interactions using typed local fixtures only: global keyboard search and product quick view, forecast product and horizon controls, chart hover and keyboard inspection, inventory-health details, insight actions, restock risk/category filters, recommendation details, sample loading/empty/error recovery, and responsive navigation. The available Inventory and Forecasts links move to Dashboard sections; they are not separate screens. Unsupported areas show a clear preview message. No purchase is created and no fixture is sent to Odoo.

Gate 1's responsive screenshots and reference comparison are stored in [`docs/qa/screenshots/issue-22-gate-1/`](qa/screenshots/issue-22-gate-1/), with its review notes in [`docs/qa/issue-22-gate-1.md`](qa/issue-22-gate-1.md). Gate 2 interaction screenshots and checks are recorded in [`docs/qa/issue-24-gate-2.md`](qa/issue-24-gate-2.md) and [`docs/qa/screenshots/issue-24-gate-2/`](qa/screenshots/issue-24-gate-2/).

## Gate 3 planned session and data boundaries

After owner approval of the visual replica and fixture interaction prototype, the client can be wired to the authenticated Odoo session and purpose-built `/autostock/api/v1/` routes. The intended data flow is:

```text
Browser ── Odoo session cookie ──> /web/session/authenticate
   │
   └── credentials: include ─────> /autostock/api/v1/*
                                       ├─ current Odoo user and authorized companies
                                       ├─ autostock.dashboard.get_dashboard_data()
                                       ├─ autostock.inventory.risk.get_risk_data()
                                       └─ autostock.forecast.run.get_forecast_snapshot()
```

The browser will hold only the Odoo session cookie. API routes must use `auth="user"` and ORM access without `sudo()`, validate a selected company against `request.env.companies`, and narrow company context with `with_company()` and `allowed_company_ids=[company.id]`. Warehouse filters must be validated by the existing risk service so Odoo ACLs and record rules stay in force.

The existing API client and Zod contracts are retained as the Gate 3 integration foundation. Their routes are planned contracts; Gates 1 and 2 do not call them.

| Planned route | Source | Purpose |
| --- | --- | --- |
| `GET /autostock/api/v1/session` | Odoo session and company records | User identity, permissions, active/authorized companies, demo label |
| `GET /autostock/api/v1/dashboard` | `autostock.dashboard` | KPI counts and inventory health |
| `GET /autostock/api/v1/dashboard/restock-preview` | `autostock.inventory.risk` | Read-only priority positions, warehouse scope and scan coverage |
| `GET /autostock/api/v1/dashboard/forecast-preview` | `autostock.forecast.run` | Eligible saved forecast or a truthful unavailable/restricted state |
| `GET /autostock/api/v1/search/products` | `product.product` ORM search | Permission-aware product search |

The React client must map server values for display rather than calculate stock, coverage, reorder quantities, lead time, forecast or evaluation metrics. Incomplete coverage and unavailable forecasts must be disclosed plainly.

## Local frontend development

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/`. No Odoo service, login, database, or `.env.local` file is required for Gates 1 or 2. Fixture states can be reviewed with `?fixtureState=loading`, `?fixtureState=empty`, or `?fixtureState=error`.

The frontend gates are `npm run lint`, `npm run typecheck`, `npm run test:unit`, `npm run test:contract`, `npm run test:browser`, and `npm run build`. The Gate 2 browser journeys verify responsive fit at 1440, 1024 and 390 CSS pixels, keyboard and reduced-motion behavior, zero browser errors, and zero `/autostock/api/` requests. Screenshot evidence is kept with the corresponding gate QA report.
