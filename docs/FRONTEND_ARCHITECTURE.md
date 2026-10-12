# React frontend architecture

The React 19 + TypeScript client in [`frontend/`](../frontend/) is AutoStock AI's new UI direction. It uses Vite, Tailwind CSS 4, Shadcn/Radix primitives and TanStack Router. Selected foundations from [`satnaing/shadcn-admin`](https://github.com/satnaing/shadcn-admin) retain the MIT notice in [`frontend/LICENSES/`](../frontend/LICENSES/); its demo pages are not used.

## Issue #22 visual reset: Gates 1 and 2

The Dashboard in Gate 1 is a visual replica built against [`design/dashboard-concept.png`](../design/dashboard-concept.png). It renders from the typed development-only fixture in [`frontend/src/data/development-dashboard-fixture.ts`](../frontend/src/data/development-dashboard-fixture.ts). The fixture values are illustrative, are not Odoo records or evaluated business results, and appear with a visible preview label. The Dashboard does not import the Odoo API client, make network requests, or depend on the backend's response shape.

Gate 1 locked the visual composition. Gate 2 adds working interactions using typed local fixtures only: global keyboard search and product quick view, forecast product and horizon controls, chart hover and keyboard inspection, inventory-health details, insight actions, restock risk/category filters, recommendation details, sample loading/empty/error recovery, and responsive navigation. The available Inventory and Forecasts links move to Dashboard sections; they are not separate screens. Unsupported areas show a clear preview message. No purchase is created and no fixture is sent to Odoo.

Gate 1's responsive screenshots and reference comparison are stored in [`docs/qa/screenshots/issue-22-gate-1/`](qa/screenshots/issue-22-gate-1/), with its review notes in [`docs/qa/issue-22-gate-1.md`](qa/issue-22-gate-1.md). Gate 2 interaction screenshots and checks are recorded in [`docs/qa/issue-24-gate-2.md`](qa/issue-24-gate-2.md) and [`docs/qa/screenshots/issue-24-gate-2/`](qa/screenshots/issue-24-gate-2/).

## Gate 3 authenticated Odoo data boundaries

The approved Dashboard and shell use an authenticated Odoo session and purpose-built `/autostock/api/v1/` routes. The data flow is:

```text
Browser ── Odoo session cookie ──> /web/session/authenticate
   │
   └── credentials: include ─────> /autostock/api/v1/*
                                       ├─ current user and authorized companies
                                       ├─ dashboard, forecast and restock previews
                                       ├─ permission-aware product search and quick view
                                       ├─ inventory catalog and product details
                                       ├─ warehouse summaries, detail and inventory
                                       └─ supplier catalog, vendor terms and missing-supplier parts
```

The browser holds only the Odoo session cookie. API routes use `auth="user"` and ORM access without `sudo()`, validate a selected company against `request.env.companies`, and narrow company context with `with_company()` and `allowed_company_ids=[company.id]`. Warehouse filters are validated against the selected company so Odoo ACLs and record rules stay in force.

The API client and Zod contracts describe the live routes. Fixture-only Gate 1 and Gate 2 browser journeys remain available for isolated visual and interaction regression checks; the current Dashboard and Inventory routes use authenticated Odoo data.

| Planned route | Source | Purpose |
| --- | --- | --- |
| `GET /autostock/api/v1/session` | Odoo session and company records | User identity, permissions, active/authorized companies, demo label |
| `GET /autostock/api/v1/dashboard` | `autostock.dashboard` | KPI counts and inventory health |
| `GET /autostock/api/v1/dashboard/restock-preview` | `autostock.inventory.risk` | Read-only priority positions, warehouse scope and scan coverage |
| `GET /autostock/api/v1/dashboard/forecast-preview` | `autostock.forecast.run` | Eligible saved forecast or a truthful unavailable/restricted state |
| `GET /autostock/api/v1/search/products` | `product.product` ORM search | Permission-aware product search |
| `GET /autostock/api/v1/products/{id}/quick-view` | `product.product` and scoped inventory services | Dashboard product quick view |
| `GET /autostock/api/v1/inventory/options` | Product, category, warehouse and permitted supplier records | Filter choices for the Inventory route |
| `GET /autostock/api/v1/inventory` | Product catalog and Odoo stock quantities | Server-side search, filters, sorting, paging, and company/warehouse stock values |
| `GET /autostock/api/v1/products/{id}/inventory-detail` | Product, stock, supplier, movement, forecast and risk services | Read-only product detail with warehouse balances and available history |
| `GET /autostock/api/v1/warehouses` | Company warehouses and existing inventory/risk services | Scoped warehouse summary, truthful attention counts, server-side search/sort/paging |
| `GET /autostock/api/v1/warehouses/{id}` | Warehouse locations, inventory/risk services and stock moves | Warehouse-specific counts, attention, reorder guidance and recent activity |
| `GET /autostock/api/v1/warehouses/{id}/inventory` | Existing `get_inventory_page` catalog method | Existing server-side stock quantities, filters and paging scoped to the warehouse |
| `GET /autostock/api/v1/suppliers` | Scoped partners, supplierinfo, inventory catalog and existing risk service | Supplier and parts coverage, server-side search/filter/sort/paging, current restock links |
| `GET /autostock/api/v1/suppliers/{id}` | Scoped partner, supplier terms and optional Purchase/receipt models | Supplier contact, lead-time range, reorder context and visible recent activity |
| `GET /autostock/api/v1/suppliers/{id}/parts` | Existing `get_inventory_page` and risk service | Paged supplied parts, stock positions, and current restock locations |
| `GET /autostock/api/v1/suppliers/{id}/parts/{product_id}/terms` | Company-scoped `product.supplierinfo` records | Separate vendor price tiers, currencies, MOQ, lead times, dates and term scope |
| `GET /autostock/api/v1/supplier-gaps` | Inventory catalog supplier-domain filter and existing risk service | Paged active parts without any configured supplier term |
| `GET /autostock/api/v1/forecasts` | Company-scoped `autostock.forecast.run` search | Exact server counts, bounded paging, and run/warehouse/horizon/state/review/source filters |
| `GET /autostock/api/v1/forecasts/{run_id}` | Exact saved forecast run, snapshot serializer, and existing `autostock.inventory.risk` service | Stored history and forecast details, provenance/evaluation explanations, and current restock eligibility |

The React client must map server values for display rather than calculate stock, coverage, reorder quantities, lead time, forecast or evaluation metrics. Incomplete coverage and unavailable forecasts must be disclosed plainly.

## Gate 4 Inventory route

Inventory is a real, read-only route within the approved application shell. It keeps server work on the Odoo side: product name, SKU, OEM reference and permitted supplier searches; category, warehouse, status, monitoring and active/archive filters; sorting and pagination; and quantity summaries all come from the authenticated catalog service. Catalog paging is validated with more than 1,000 products so a part beyond the initial page remains searchable and reachable.

The list shows company-wide on-hand, available, reserved and incoming amounts. Selecting a warehouse scopes the stock-status view and provides that warehouse's quantities while preserving a clear label for company totals. The product detail view presents stock by warehouse, permitted supplier terms, meaningful recent stock activity in plain language, and forecast/reorder information only when existing services provide it. Supplier restrictions, incomplete coverage, absent history, and service failures have explicit states. No product edits, receipts, adjustments, or purchasing actions are exposed.

Gate 4 browser evidence and test results are recorded in [`docs/qa/issue-28-gate-4.md`](qa/issue-28-gate-4.md) with real showroom screenshots in [`docs/qa/screenshots/issue-28-gate-4/`](qa/screenshots/issue-28-gate-4/).

## Gate 5 Warehouses route

Warehouses is a read-only route that reuses the approved shell and the Inventory catalog's quantity calculation. Overview cards count warehouse locations and distinct part positions; they do not add quantities measured in different units. Each warehouse detail aggregates its view location and child locations, labels physical on-hand separately from available (not reserved) stock, and presents reserved, incoming and outgoing values in each part's unit. Search, sorting, warehouse inventory filters and pagination run in Odoo. Completed and expected stock activity is translated into plain business language. No transfer or stock-write actions are exposed.

The routes use the authenticated request environment, ordinary Odoo ACLs and record rules, and the selected-company context already used by the Inventory service. A warehouse ID must belong to the selected company. Summary and risk scans have explicit safe limits; when a complete summary cannot be calculated within those limits, the service returns a disclosed unavailable state instead of an incomplete total. A 1,001-part integration scenario verifies that the warehouse catalog remains searchable and paginated beyond the first page.

Gate 5 implementation details, test evidence and live Atlas Auto Distribution screenshots are recorded in [`docs/qa/issue-30-gate-5.md`](qa/issue-30-gate-5.md) and [`docs/qa/screenshots/issue-30-gate-5/`](qa/screenshots/issue-30-gate-5/).

## Gate 6 Suppliers route

Suppliers is a read-only company-scoped screen. Supplier search, attention and term filters, sorting and pagination run through Odoo. Summary counts disclose unavailable coverage rather than inferring a value from a partial scan. Company-shared vendor contacts appear only when the selected company has supplier terms for them; company-owned supplier records can also be listed locally. Company-specific products, supplier terms and stock are filtered through the selected company while standard Odoo ACLs and record rules remain in force.

Supplier parts reuse the Inventory catalog quantity logic, and current reorder links reuse `autostock.inventory.risk`. Lead times are shown as a range. Each vendor term keeps its own currency, native price-break minimum quantity, separate AutoStock minimum order quantity, vendor code, date validity and company/shared scope. Prices are never aggregated across currencies, and no vendor score or savings metric is presented. Purchase orders and receipts are read only when the module and the user's access make them available; otherwise the screen gives a clear unavailable message. Parts without any configured supplier term have their own server-filtered view. No purchase action is exposed.

Gate 6 Odoo integration, frontend/browser checks and live showroom screenshot evidence are recorded in [`docs/qa/issue-32-gate-6.md`](qa/issue-32-gate-6.md) and [`docs/qa/screenshots/issue-32-gate-6/`](qa/screenshots/issue-32-gate-6/).

## Gate 7 Forecasts workspace

`/forecasts` is a server-paged view of stored forecast runs; `/forecasts/$runId` opens the exact selected run. Filters and exact totals come from Odoo. The page displays stored delivery history, separate return events, forecast horizon, company/warehouse scope, source cutoff, review state, selected method, baseline, chronological holdout length, and MAE with units. Solid historical values and a dashed future segment are separated by a labeled “Forecast starts” marker. Explanations retain the fulfilled-sales and heuristic-range limitations, and no MAE-derived accuracy percentage is shown.

The frontend uses the authenticated session and Zod contracts for the two read-only endpoints. It displays server-provided access, coverage, synthetic provenance, evaluation, and current restock-guidance states. Forecast and inventory calculations stay in Odoo; no API request writes or queues a run. The `/forecasts` navigation entry routes to this workspace from the approved shell and completed live-data screens.

## Local frontend development

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/`. The fixture-only Gate 1 and Gate 2 journeys can run without Odoo. To use live Dashboard, Inventory, Warehouses, Suppliers and Forecasts routes, run the local Odoo showroom on `127.0.0.1:8177` (or set `ODOO_PROXY_TARGET` in a local Vite environment file), then sign in with a permitted user. Gate 1 and Gate 2 fixture states can be reviewed with `?fixtureState=loading`, `?fixtureState=empty`, or `?fixtureState=error`.

The frontend gates are `npm run lint`, `npm run typecheck`, `npm run test:unit`, `npm run test:contract`, `npm run test:browser`, and `npm run build`. Browser journeys verify responsive fit at 1440, 1024 and 390 CSS pixels, keyboard and reduced-motion behavior, zero browser errors, and server-side catalog interactions. Fixture-only journeys explicitly assert zero `/autostock/api/` requests; live showroom smoke checks exercise the authenticated API. Screenshot evidence is kept with the corresponding gate QA report.
