# Issue #30 — Gate 5 Warehouses QA

**Branch:** `product/warehouses-screen`

**Scope:** the authenticated, read-only Warehouses route and warehouse detail workflow. This report is implementation evidence, not a production-readiness claim.

## What changed

- Added warehouse overview and detail routes to the existing React application shell. The screen keeps the approved sidebar, header, colors, typography and readability scale used by Dashboard and Inventory.
- Added authenticated Odoo endpoints for company-scoped warehouse summaries and details. Warehouse inventory delegates to the existing Inventory catalog method for search, filters, sort, pagination and quantity calculations.
- Warehouse quantities aggregate the warehouse view location and its descendants. Physical on-hand, available-to-use, reserved, incoming and outgoing values remain attached to each part and its unit. Overview totals count warehouse locations and distinct part positions; they do not add unlike units.
- Added warehouse attention states, read-only restock guidance, completed/expected stock activity, responsive inventory cards, permission/error/empty states and links to the existing product detail workflow. No transfer or stock-write action is exposed.
- Kept company validation, Odoo ACLs and record rules active. No `sudo()` calls were added. Oversized/incomplete scans disclose that a summary is unavailable rather than presenting partial counts as complete.

## Odoo integration coverage

The addon was installed in a fresh test database with Odoo 19.0 and PostgreSQL 16. The integration suite exercised both warehouse routes and the shared Inventory path, including:

- two companies, a user permitted for both, company-specific and shared products, warehouse selection and rejection of a warehouse outside the selected company;
- stock held in a warehouse child location, and distinct on-hand, reserved, incoming and outgoing part quantities;
- completed receipts, reserved customer deliveries and plain-language recent movement activity;
- a warehouse catalog containing 1,001 products, including product 1001 through server-side search and pagination;
- a user without inventory access receiving permission-denied responses.

Odoo reported **0 failed and 0 errors of 46 test cases**. Its separate broader `odoo.tests.stats` entry reported 56; that is not the test-case count. The isolated test database was dropped after the run.

## Atlas Auto Distribution showroom

The authenticated live browser run used the existing local Atlas Auto Distribution Odoo showroom with its two actual warehouses. It verified the overview, server-filtered warehouse search, detail and movement views, product details and warehouse-scoped inventory. The capture script awaited the filtered Odoo response and checked that the exact searched SKU was the sole returned and visible row. A no-results search returned zero parts. At 1440, 1024 and 390 CSS pixels, captured pages were checked for horizontal overflow. There were **0 page errors, 0 console errors and 0 failed AutoStock API responses**.

The captured detail snapshot showed 64 catalog part positions, of which 53 had stock; 14 were low and 11 were out of stock. These are live showroom values at capture time, not forecasts or general business claims.

## Automated checks

| Check | Result |
| --- | --- |
| `python -m compileall -q addons/autostock_ai` | Passed |
| Odoo 19.0 + PostgreSQL 16 addon integration suite | Passed; 46 test cases, 0 failures, 0 errors (separate broad stats count: 56) |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm run test:unit` | Passed; 3 tests |
| `npm run test:contract` | Passed; 9 tests |
| `npm run test:browser` | Passed; 22 Playwright tests across Dashboard, Inventory and Warehouses, including 1001st-product paging, deep links, browser back/forward and 1440/1024/390 layouts |
| `npm run build` | Passed |
| `npm run capture:warehouses-showroom` | Passed; 12 scripted live captures plus a separate activity-feed image; no browser/API errors |
| `git diff --check` | Passed |

## Screenshot evidence

All screenshots below are browser captures of authenticated Odoo showroom data, not local frontend fixtures.

| View | Screenshot | What it shows |
| --- | --- | --- |
| Overview, desktop | [warehouses-overview-1440.png](screenshots/issue-30-gate-5/warehouses-overview-1440.png) | Both live showroom warehouses and attention summary |
| Overview, tablet | [warehouses-overview-1024.png](screenshots/issue-30-gate-5/warehouses-overview-1024.png) | Responsive overview at 1024 px |
| Overview, mobile | [warehouses-overview-390.png](screenshots/issue-30-gate-5/warehouses-overview-390.png) | Stacked warehouse cards at 390 px |
| Attention-filtered overview | [warehouses-attention-1440.png](screenshots/issue-30-gate-5/warehouses-attention-1440.png) | Live Odoo status filter, showing the warehouses needing attention |
| Filtered overview | [warehouses-filtered-1440.png](screenshots/issue-30-gate-5/warehouses-filtered-1440.png) | Server-filtered Central warehouse result |
| Detail, desktop | [warehouse-detail-1440.png](screenshots/issue-30-gate-5/warehouse-detail-1440.png) | Warehouse counts, stock table and detail layout |
| Detail, tablet | [warehouse-detail-1024.png](screenshots/issue-30-gate-5/warehouse-detail-1024.png) | Tablet layout with readable inventory content |
| Detail, mobile | [warehouse-detail-390.png](screenshots/issue-30-gate-5/warehouse-detail-390.png) | Mobile part cards and detail content |
| Activity feed | [warehouse-activity-1440.png](screenshots/issue-30-gate-5/warehouse-activity-1440.png) | Actual completed and expected stock activity |
| Product detail | [warehouse-product-detail-1440.png](screenshots/issue-30-gate-5/warehouse-product-detail-1440.png) | Existing product sheet with stock by warehouse |
| Exact SKU filter | [warehouse-filtered-part-1440.png](screenshots/issue-30-gate-5/warehouse-filtered-part-1440.png) | One live API result and one visible matching row |
| No-results state | [warehouse-no-results-1440.png](screenshots/issue-30-gate-5/warehouse-no-results-1440.png) | Clear message after a live search returns no part |
| Mobile navigation | [warehouses-mobile-navigation-390.png](screenshots/issue-30-gate-5/warehouses-mobile-navigation-390.png) | Responsive navigation drawer |

## Reference comparison and remaining limits

The route reuses the accepted Dashboard/Inventory shell and design tokens so the warehouse workflow keeps the same brand and readable type scale. The warehouse overview uses concise location cards; detail uses a clear part list and stock labels rather than introducing a dense Odoo-style table across mobile widths. The responsive screenshots show these layouts at the requested widths. Warehouse-specific values are never combined across products into a misleading stock total.

The issue's optional two-warehouse comparison control was omitted. The overview already presents the company's warehouses together with identical stock, attention and activity fields, allowing a direct comparison without an extra selection mode or a second competing layout. A part-specific comparison can be made by opening the relevant warehouse inventory and searching the same SKU in each.

Summaries deliberately have safe server-side scan limits. The UI discloses when a complete overview or restock count cannot be calculated within those bounds; the paginated warehouse inventory remains available for part-level review. This PR does not add warehouse creation, transfers, adjustments, purchasing, or other write operations.
