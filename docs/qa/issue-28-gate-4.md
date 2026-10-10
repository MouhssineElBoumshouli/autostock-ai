# Issue #28 — Gate 4 Inventory QA

- **Date:** 2026-10-10
- **Branch:** `product/inventory-screen`
- **Scope:** Real, read-only Inventory route and product details. The Dashboard composition remains unchanged; no other business screen or write workflow was added.

## Result

Inventory is available at `/inventory` and uses the shared authenticated Odoo workspace session and approved application shell. The page reads live product, category, supplier, warehouse and stock data from the showroom database. Odoo performs search, filtering, sorting, pagination, company/warehouse scoping and quantity calculations. React only formats API results.

Search supports product name, SKU, OEM reference, and supplier name when supplier records are readable. Catalog filters include stock status, warehouse, category, supplier, AutoStock monitoring and active/archive state. Paging is server-side. The Odoo integration suite creates 1,001 catalog products and verifies the last product remains searchable and page-reachable beyond the initial result batch.

The list presents company-wide on-hand, available, incoming and warehouse stock, with the current stock-status scope identified in the page copy. Product details include company-wide quantities, warehouse balances, supplier terms and lead time when permitted, forecast status only when supported by a real saved forecast, existing read-only restock guidance, and recent completed or expected stock activity in plain business language. Missing, restricted, partial and failed data each has an explicit state. No product edit, receipt, adjustment, purchase, or other write action is exposed.

The mixed-unit Odoo test confirms movement quantities use the product's stock unit correctly: a completed receipt of 30 units, an expected receipt of two dozens (24 units), and a reserved delivery of two dozens (24 units). Company stock remains 30 on hand, 6 available, 24 reserved and 24 incoming in the tested case.

## Live Atlas Auto Distribution showroom

The screenshots use actual Odoo records from the local fictional showroom installation. At capture time its catalog reported 64 tracked parts (58 in stock, 6 low stock, 0 out of stock); the first server page contains 25 rows. These are demo database values, not customer data or business validation. Capture verified no horizontal page overflow at all three target widths, zero failed AutoStock API responses, zero browser page errors and zero console errors.

| Evidence | Screenshot | Result |
| --- | --- | --- |
| Desktop catalog | [inventory-desktop-1440.png](screenshots/issue-28-gate-4/inventory-desktop-1440.png) | 1440 px; real first page with company and warehouse stock, supplier terms and stock states |
| Tablet catalog | [inventory-tablet-1024.png](screenshots/issue-28-gate-4/inventory-tablet-1024.png) | 1024 px; responsive table layout, no page overflow |
| Mobile catalog | [inventory-mobile-390.png](screenshots/issue-28-gate-4/inventory-mobile-390.png) | 390 px; stacked product cards and filters, no page overflow |
| Low-stock filter | [inventory-low-stock-1440.png](screenshots/issue-28-gate-4/inventory-low-stock-1440.png) | Live server-side filter shows low-stock parts |
| SKU search | [inventory-filtered-1440.png](screenshots/issue-28-gate-4/inventory-filtered-1440.png) | Capture waits for the completed Odoo `/inventory?q=<SKU>` response, then verifies a result count of 1 and one visible row containing the searched SKU |
| Product detail, stock | [inventory-product-detail-1440.png](screenshots/issue-28-gate-4/inventory-product-detail-1440.png) | Company totals, warehouse stock, supplier and forecast state |
| Product detail, restock/activity | [inventory-product-detail-lower-1440.png](screenshots/issue-28-gate-4/inventory-product-detail-lower-1440.png) | Existing read-only restock guidance and truthful recent-activity state |
| Product detail, mobile | [inventory-product-detail-390.png](screenshots/issue-28-gate-4/inventory-product-detail-390.png) | Mobile bottom drawer remains within the viewport |
| Mobile navigation | [inventory-mobile-navigation-390.png](screenshots/issue-28-gate-4/inventory-mobile-navigation-390.png) | Shared navigation drawer at 390 px |
| No results | [inventory-no-results-1440.png](screenshots/issue-28-gate-4/inventory-no-results-1440.png) | Clear recovery state for a search with no matches |

The reference comparison uses [`design/dashboard-concept.png`](../../design/dashboard-concept.png). The common shell, AutoStock mark, active sidebar treatment, global search, soft lavender background, rounded white surfaces and restrained shadows follow the approved visual language. Inventory adds a purpose-built catalog, server-side filter controls and a matching detail drawer; it does not reproduce the Dashboard's forecast composition or alter that screen.

## Checks

| Check | Result |
| --- | --- |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm run test:unit` | Passed, 3 tests |
| `npm run test:contract` | Passed, 7 API contract tests |
| `npm run test:browser` | Passed, 17 Playwright journeys. Covers Dashboard regressions, Inventory navigation and back behavior, search and server query parameters, 1440/1024/390 layouts, product detail styling/content, keyboard search, filter/pagination interactions, empty/no-result/restricted/error states, and reduced motion. |
| `npm run build` | Passed |
| `python -m pytest -q` | Passed, 38 tests |
| `python -m compileall -q addons ml scripts tests` | Passed |
| Labeled synthetic forecast evaluation | Passed for 6 labeled fixture products. This is an engineering evaluation run only; no business accuracy claim is made. |
| Odoo 19 with PostgreSQL 16 | Passed in a clean isolated database. Odoo logged 46 `Starting Test` cases and reported 0 failures and 0 errors of 46 tests; the separate broader `odoo.tests.stats` line reports 56. The run includes the 1,001-product case, SKU/name/OEM/supplier search, server-side sorting and paging, category/status/warehouse filters, two-company shared/company-specific products, inventory permissions and mixed-unit stock activity. |
| Local showroom addon upgrade | Passed for the Atlas Auto Distribution database; `/web/login` returned HTTP 200 after the targeted Odoo restart. |
| Authenticated showroom screenshot capture | Passed; 25 visible rows out of 64 tracked showroom parts, 10 screenshots, 0 AutoStock API failures, 0 page errors, 0 console errors, and no horizontal overflow at 1440/1024/390 px. The SKU-search capture waits for the matching filtered Odoo response and asserts the one-result label, exactly one visible row, and matching SKU before saving the screenshot. |

Frontend automated browser tests use controlled API responses to exercise boundary states. The committed screenshots and the showroom capture use the authenticated local Odoo installation. The local credential file is read only by the capture script and is not included in the screenshots or commit.

## Known boundaries

- Showroom visuals use 64 demo products; the separate Odoo integration case validates catalog behavior with 1,001 products.
- Supplier, category and warehouse suggestion lists are bounded and disclose when suggestions are limited; supplier name text search still runs against the full permitted supplier-linked catalog. Very large supplier or stock-status scans stop with a narrowing prompt rather than silently presenting partial matches.
- Existing dashboard-derived summary coverage remains marked when that service reports an incomplete catalog scan. Exact page counts are computed from the matching Odoo catalog domain.
- A product without a matching reviewed real forecast or recent movement shows the corresponding unavailable/empty state; no forecast is fabricated.
- This gate is a read-only Inventory workflow and does not establish production readiness or operational release completion.

## Reproduce the showroom screenshots

Start the configured local Odoo showroom on port 8177 and Vite on port 5173, then run:

```powershell
cd frontend
npm run capture:inventory-showroom
```

The script reads `.showroom/credentials.txt` without printing its contents and writes captures to `docs/qa/screenshots/issue-28-gate-4/`.
