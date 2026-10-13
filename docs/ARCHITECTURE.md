# Architecture and trust boundaries

```text
Odoo 19 Community
  ├─ native sale / stock / product / warehouse / company records
  ├─ autostock_ai addon
  │    ├─ product metadata and read-only inventory dashboard
  │    ├─ validated forecast request and source snapshot
  │    ├─ forecast run, daily observations, forecast points, review metadata
  │    ├─ bounded scheduled worker using the shared Python forecaster
  │    └─ company/warehouse-scoped, read-only inventory-risk analysis and reorder guidance
  └─ standard Odoo ACLs, record rules, active company and warehouse scope

React 19 client (`frontend/`)
  ├─ Odoo-authenticated session and company selection
  ├─ Dashboard, Inventory, Warehouses, and Suppliers backed by purpose-built Odoo API routes
  └─ TanStack Query and Router; no business calculations are duplicated client-side

Offline laboratory
  ├─ deterministic synthetic dataset generator
  └─ chronological evaluation against simple forecasting baselines
```

## Cross-phase product standards

Commercial readiness and premium UX are continuous requirements, tracked in [issue #7](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/7) and [issue #8](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/8). Each phase must preserve these standards while keeping its implementation scope small. A passing PR or screenshot does not establish commercial readiness; see the issues for the full release gates.

## Existing Odoo dashboard

The legacy Owl client action remains unchanged while the React client is reviewed. It is not the foundation for new screens or UI work.

No unrestricted SQL or `sudo()` is used to read business data. Odoo ACLs and record rules remain in force.

## React dashboard foundation

The current React scope and API/security boundaries are described in [Frontend architecture](FRONTEND_ARCHITECTURE.md). The Dashboard calls `GET /autostock/api/v1/session`, `/dashboard`, `/dashboard/restock-preview`, `/dashboard/forecast-preview`, and `/search/products` using the authenticated Odoo session cookie. Routes check inventory permissions, validate requested companies against the user's allowed companies, narrow ORM contexts to the selected company, and call existing Odoo services. Dashboard counts, forecasts and reorder quantities remain server-calculated. The restock preview is read-only; API pagination limits are disclosed in the response and interface.

## Phase 3A stock-risk analysis and reorder guidance

1. The dashboard calls `autostock.inventory.risk.get_risk_data` through the authenticated Odoo ORM. The service requires inventory access, narrows the environment to the active company, and validates any selected warehouse against that company.
2. Tracked products are limited to shared products and products owned by the active company. Stock quantities are read with Odoo's warehouse/location and receipt-date context; inventory reservations are shown separately and are not subtracted a second time from `virtual_available`.
3. Odoo reordering rules supply the trigger, target, location and replenishment multiple. Multiple rules for one product/warehouse, unreadable rules, missing triggers/targets, invalid policy and bounded lookups withhold numeric advice.
4. A selected active vendor term supplies lead time; otherwise the product planning assumption is labeled and used. `product.supplierinfo.min_qty` remains a native price break; a separate AutoStock MOQ field is used as the contractual minimum. Both MOQ and the native replenishment multiple are converted to the product inventory unit before round-up.
5. Only completed, real, manager-reviewed forecasts can add demand through the vendor lead-time window. Company, product and warehouse must match exactly; source and history must be fresh; the complete daily horizon must exist; and the holdout evaluation must cover the full forecast horizon. Synthetic runs, stale results, partial history and unsupported evaluations are excluded with a stated reason.
6. Odoo's projected stock already includes confirmed outgoing stock moves. The service reconciles future sale-linked outbound quantities and subtracts only forecast demand not already represented in those moves. If required access or bounded data is unavailable, the numeric recommendation is withheld or falls back to explicitly labeled visible Odoo policy only.

The result is read-only planning evidence. Phase 3A does not create purchase quotations, purchase orders, supplier commitments, stock moves or quants. It never presents a forecast as guaranteed accuracy. See the [Phase 3A QA report](qa/phase3a-risk-replenishment.md) for test and browser evidence.

## Supplier screen data

The Suppliers interface is built on the selected company's partner and `product.supplierinfo` records, existing Inventory quantity methods, and the existing risk/reorder service. Current-company and shared supplier terms are kept separate; shared supplier contacts without a term for the selected company are not exposed in its supplier list. Native price-break quantities, separate minimum order quantities, price currencies, sequence and validity dates are shown per term. No supplier performance score or cross-currency total is derived. Purchase history is an optional read-only section and reports when the Purchase model or access is unavailable.

## Forecast request and data source

1. A stock user selects a tracked product, a 7/30/60-day horizon, a covered history range, and optionally a warehouse. Real forecasts also require sales access and a configured complete-history start date.
2. The request validates the product, company, warehouse, horizon, date range, 90-day minimum, 730-day maximum, and a snapshot cutoff. Interactive RPC only queues work.
3. The scheduled worker processes at most two queued runs per invocation. It reads completed Odoo stock moves through the ORM, capped at 50,000 source moves.
4. A move counts as demand only when it is linked to a confirmed sale order line and transfers product from internal stock to a customer. Quotes, cancelled or unshipped orders, receipts, and internal transfers are excluded. Completed customer returns linked to deliveries are separate audit events on their actual completion date; they never revise the original delivery day's demand.
5. Move quantities are converted to the product's inventory UoM. Daily demand is gross completed delivery quantity dated using the delivery move timestamp in UTC. Returns are excluded from the nonnegative forecast target and returned stock is reflected by Odoo's inventory movements. Days with no qualifying completed deliveries are zero fulfilled sales for the configured covered period.
6. The run stores its company/warehouse, product/SKU, cutoff, source provenance and digest, history coverage, model version, selected approach, baseline and model metrics, assumptions, status, observations, forecast points, and review metadata.

The active company is applied both with `with_company()` and a narrowed `allowed_company_ids` context. Product choices include only the selected company's products and shared products. Warehouse choices are restricted to the selected company. ORM product ACLs and record rules still apply. A user's access to multiple companies does not merge their histories.

## Forecast selection and limitations

The forecaster compares a random-forest model with trailing-mean, seasonal-naive, and Croston SBA baselines using a chronological holdout and selects a measured method for each series. Intermittent series use their baseline rather than an unsuitable random forest. Fewer than 90 history days produces an insufficient-history result; no observed positive demand produces an explicit no-demand state.

The source represents **gross fulfilled sales**, not unconstrained customer demand or net sales. Stockouts can censor sales, and the current Odoo history has no lost-demand signal. A configured coverage start date is an administrator assertion, not an automated proof of completeness. The reported range is heuristic and is not a calibrated confidence interval. These forecasts must not automatically trigger purchasing.

For the isolated Moroccan showroom, a verified demo-history profile binds dataset version, company, product, optional warehouse, history dates, completed delivery/linked-return move digest, and the full daily observation digest. A company-wide profile cannot stand in for warehouse history. Warehouse profiles use actual done sale-linked deliveries picked from that warehouse; a return is attributed only through its `origin_returned_move_id` link to one of those exact scoped deliveries. Odoo product creation audit fields are never backdated. Each queued run remains unreviewed until an inventory manager explicitly reviews its completed result. Before it can inform restock guidance, AutoStock rechecks that the source digest remains current and applies the normal 14-day freshness, full-horizon evaluation, point-coverage, exact warehouse, and manager-review gates. See the [Issue #42 QA report](qa/issue-42-warehouse-forecasts.md) for the showroom's three-product-per-warehouse sample and its dated-demo limitation.

The chronological evaluation window matches the requested 7-, 30-, or 60-day horizon when enough observations exist. Candidate selection and displayed MAE use the same single holdout, so those metrics are comparison evidence for that series, not an independent accuracy estimate. A completed return in the holdout is recorded separately and cannot change training or target delivery values. Odoo does not retain a complete as-of history for later edits to completed stock moves, so a snapshot replays the records as currently stored at its cutoff and cannot prove what was known at every historical forecast origin.

The scheduled worker uses the same forecasting code as the offline lab. The request path does not fit a model. Data from Odoo is not used to train global model parameters, and synthetic data is never mixed with sale or stock records.

## Synthetic demo separation and cleanup

The synthetic demo creates a forecast run with `source_type=synthetic_demo`, no Odoo product relation, and generated daily observations. It does not read or write sale orders, stock moves, quants, or supplier records. Synthetic runs remain clearly labeled in the UI and may be deleted with the scoped ORM cleanup documented in [Phase 2 QA](qa/phase2-demand-forecast.md).

## Later milestones

- Further decision tools, budget constraints and simulation remain outside Phase 3A and follow their own reviewed issues.
- Phase 3A's reorder guidance remains human-reviewed and read-only until later approved purchasing work.
- Additional real-data evaluation only after a consented dataset and evaluation protocol are approved.

## Production blockers

No consented real-business evaluation dataset, calibrated uncertainty interval, lost-demand/stockout-censoring signal, backup/restore verification, hardened production deployment, or comprehensive independent security review is included in this development milestone.

## Gate 7 Forecasts workspace

The Forecasts workspace reads saved runs through `/autostock/api/v1/forecasts` and `/autostock/api/v1/forecasts/{run_id}`. Odoo performs exact-count filtering and bounded pagination in the active company's ORM context; the browser does not reconstruct counts, forecast values, coverage, evaluation metrics, or restock quantities. Detail uses the selected saved run and the existing `autostock.inventory.risk.get_risk_data` service to explain whether that exact run is currently used for restock guidance.

Real completed-delivery history is available only to users with both inventory access and Sales access. Stock-only users receive synthetic examples only, with real-run counts and metadata excluded. Company and warehouse filters are validated through normal Odoo permissions and record rules; no `sudo()` is used. The screen is read-only and does not create, queue, review, or modify forecast runs or purchasing records. Synthetic Atlas showroom examples are visibly separated from operational history.

The workspace explains that its input is completed fulfilled sales, not unconstrained demand; returns are separate events and do not revise delivered quantities. It displays stored holdout MAE with units and baseline context, never as an accuracy percentage. Coverage dates, heuristic ranges, stale or incomplete records, and any reason the selected run cannot inform current warehouse restock guidance are disclosed in plain language. See the [Gate 7 QA report](qa/issue-34-gate-7.md) for implementation evidence and remaining limitations.
