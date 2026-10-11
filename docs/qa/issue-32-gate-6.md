# Issue #32 — Gate 6 Suppliers QA

Gate 6 adds a read-only Suppliers route backed by authenticated Odoo records. Supplier data, stock, and reorder context follow the selected company and the requesting user's standard Odoo access rules. Vendor prices remain attached to their configured currencies and price-break rows; the screen does not calculate cross-currency totals or supplier scores.

## Live Atlas showroom captures

The captures below came from the running Atlas Auto Distribution Odoo showroom using real demo database records. The demo label is present in the UI. The capture contains no credentials.

| Screen | Viewport | Capture |
| --- | ---: | --- |
| Supplier overview | 1440 px desktop | [suppliers-overview-1440.png](screenshots/issue-32-gate-6/suppliers-overview-1440.png) |
| Supplier overview | 1024 px tablet | [suppliers-overview-1024.png](screenshots/issue-32-gate-6/suppliers-overview-1024.png) |
| Supplier overview | 390 px mobile | [suppliers-overview-390.png](screenshots/issue-32-gate-6/suppliers-overview-390.png) |
| Supplier search result | 1440 px desktop | [suppliers-search-1440.png](screenshots/issue-32-gate-6/suppliers-search-1440.png) |
| Reorder-attention filter result | 1440 px desktop | [suppliers-reorder-filter-1440.png](screenshots/issue-32-gate-6/suppliers-reorder-filter-1440.png) |
| Supplier detail and supplied parts | 1440 px desktop | [supplier-detail-1440.png](screenshots/issue-32-gate-6/supplier-detail-1440.png) |
| Supplier detail and supplied parts | 1024 px tablet | [supplier-detail-1024.png](screenshots/issue-32-gate-6/supplier-detail-1024.png) |
| Supplier detail and supplied parts | 390 px mobile | [supplier-detail-390.png](screenshots/issue-32-gate-6/supplier-detail-390.png) |
| Server-filtered supplier part | 1440 px desktop | [supplier-parts-search-1440.png](screenshots/issue-32-gate-6/supplier-parts-search-1440.png) |
| Native vendor price tiers and terms | 1440 px desktop | [supplier-vendor-terms-1440.png](screenshots/issue-32-gate-6/supplier-vendor-terms-1440.png) |
| Native vendor price tiers and terms | 390 px mobile | [supplier-vendor-terms-390.png](screenshots/issue-32-gate-6/supplier-vendor-terms-390.png) |
| Parts without a supplier | 1440 px desktop | [supplier-gaps-1440.png](screenshots/issue-32-gate-6/supplier-gaps-1440.png) |
| Parts without a supplier | 1024 px tablet | [supplier-gaps-1024.png](screenshots/issue-32-gate-6/supplier-gaps-1024.png) |
| Parts without a supplier | 390 px mobile | [supplier-gaps-390.png](screenshots/issue-32-gate-6/supplier-gaps-390.png) |

Playwright checked for horizontal overflow at every captured viewport. The capture run made live supplier-name and reorder-attention requests plus a supplier-part SKU search, then reported zero page errors, zero browser console errors, and zero failed AutoStock API responses. The company-wide Active suppliers KPI remained four while both supplier-name search and reorder-attention filtering narrowed the visible list. The missing-supplier page was captured after its live response rendered four matching parts. There are 14 screenshots total.

## Checks

| Check | Result |
| --- | --- |
| `python -m pytest -q` | Passed: 38 tests |
| `python -m compileall -q addons/autostock_ai` | Passed |
| Odoo 19 + PostgreSQL 16 addon suite (`/autostock_ai`) | Passed: 52 actual test cases, 0 failures, 0 errors. Odoo's broader stats line reports 64 tests. |
| Odoo supplier API cases | Covered price/currency tiers, sequence, MOQ, lead time, optional Purchase access, 500 suppliers and 1,000 vendor terms, restock calculations, missing supplier results, user access, and two-company isolation for shared/company records and stock. |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm run test:unit` | Passed: 3 tests |
| `npm run test:contract` | Passed: 13 tests |
| `npm run test:browser` | Passed: 26 Playwright tests across Dashboard, Inventory, Warehouses, and Suppliers. |
| `npm run build` | Passed |
| `git diff --check` | Passed |

The first Odoo test run exposed two test/setup issues: an optional `False` filter value was rejected when the supplier detail reused the inventory catalog service, and a bulk-search fixture omitted a zero-padded digit. Live response validation also caught missing supplier-term metadata in the missing-supplier payload. The inventory parser now treats its documented `False` default as empty, the fixture searches its stored supplier name, and the missing-supplier rows carry explicit zero-term/no-lead-time values. The final addon suite and live response contract pass.

## Data and permission behavior

- Shared vendor contacts are shown only when the selected company has a scoped supplier term for them; company-owned supplier records are available within that company.
- Product search, supplier terms, inventory quantities, and current reorder suggestions use the selected-company context and existing Odoo services. No `sudo` is used.
- The **Active suppliers** KPI is company-wide and does not shrink when the result list is searched or filtered. If the safe company-wide term scan is incomplete, the KPI is shown as unavailable with an explanation.
- The missing-supplier view treats expired/future terms as configured terms, so it reports parts without a configured term rather than implying a currently purchasable supplier exists.
- Vendor price-break quantities, MOQ, currency, lead time, term sequence, validity dates, and company/shared scope stay separate in the detail sheet.
- The Atlas showroom does not have the Purchase module installed. The supplier detail therefore shows the truthful “Purchase order history is not available in this setup” state while supplier, stock, and vendor-term data continue to work.
- All supplier routes remain read-only. Creating suppliers, editing vendor terms, and purchasing are outside Gate 6.

## Reproduce the live captures

Start the local Vite app with its showroom Odoo proxy configured, then run `npm run capture:suppliers-showroom` from `frontend/`. The script signs into the local Atlas showroom using `.showroom/credentials.txt` without printing its contents and writes the 14 captures to `docs/qa/screenshots/issue-32-gate-6/`.
