# Architecture and trust boundaries

```text
Odoo 19 Community
  ├─ native sale / stock / product / warehouse / company records
  ├─ autostock_ai addon
  │    ├─ product metadata and read-only inventory dashboard
  │    ├─ validated forecast request and source snapshot
  │    ├─ forecast run, daily observations, forecast points, review metadata
  │    └─ bounded scheduled worker using the shared Python forecaster
  └─ standard Odoo ACLs, record rules, active company and warehouse scope

Offline laboratory
  ├─ deterministic synthetic dataset generator
  └─ chronological evaluation against simple forecasting baselines
```

## Cross-phase product standards

Commercial readiness and premium UX are continuous requirements, tracked in [issue #7](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/7) and [issue #8](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/8). Each phase must preserve these standards while keeping its implementation scope small. A passing PR or screenshot does not establish commercial readiness; see the issues for the full release gates.

## Inventory dashboard

1. A stock user opens the AutoStock AI client action.
2. Owl loads dashboard data through Odoo's authenticated ORM RPC.
3. The server checks the user's inventory permission, scopes product and stock reads to the active company, and returns live Odoo values.
4. The UI distinguishes physical on-hand stock and Odoo's `virtual_available` projection from demand forecast output.

No unrestricted SQL or `sudo()` is used to read business data. Odoo ACLs and record rules remain in force.

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

The chronological evaluation window matches the requested 7-, 30-, or 60-day horizon when enough observations exist. Candidate selection and displayed MAE use the same single holdout, so those metrics are comparison evidence for that series, not an independent accuracy estimate. A completed return in the holdout is recorded separately and cannot change training or target delivery values. Odoo does not retain a complete as-of history for later edits to completed stock moves, so a snapshot replays the records as currently stored at its cutoff and cannot prove what was known at every historical forecast origin.

The scheduled worker uses the same forecasting code as the offline lab. The request path does not fit a model. Data from Odoo is not used to train global model parameters, and synthetic data is never mixed with sale or stock records.

## Synthetic demo separation and cleanup

The synthetic demo creates a forecast run with `source_type=synthetic_demo`, no Odoo product relation, and generated daily observations. It does not read or write sale orders, stock moves, quants, or supplier records. Synthetic runs remain clearly labeled in the UI and may be deleted with the scoped ORM cleanup documented in [Phase 2 QA](qa/phase2-demand-forecast.md).

## Next milestone

- Stockout and slow-moving analysis that separates fulfilled-sales forecasts from Odoo's projected inventory.
- Human-reviewed replenishment proposals with explicit lead-time, open-order, budget, and approval constraints.
- Additional real-data evaluation only after a consented dataset and evaluation protocol are approved.

## Production blockers

No consented real-business evaluation dataset, calibrated uncertainty interval, lost-demand/stockout-censoring signal, backup/restore verification, hardened production deployment, or comprehensive independent security review is included in this development milestone.
