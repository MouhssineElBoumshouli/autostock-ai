# Architecture and trust boundaries

```text
Odoo 19 Community (web login, users, roles, company restrictions)
  ├─ stock/product/purchase/sale models [native Odoo]
  ├─ autostock_ai addon
  │    ├─ product.template metadata [implemented]
  │    ├─ read-only dashboard model [implemented]
  │    └─ Owl dashboard with live Odoo stock [implemented]
  └─ planned next layers
       ├─ reproducible demand aggregation / provenance
       ├─ persisted & reviewed ML forecast runs
       ├─ budget and scenario service (no mutation)
       ├─ AI explanation assistant (read-only, tool-limited)
       └─ QWeb report renderer / PDF export

Offline laboratory (implemented, no live data path)
  └─ Python scikit-learn forecaster and synthetic fixture generator
```

## Foundation: data flow

1. Stock user opens AutoStock AI menu.
2. Odoo client action loads an Owl component from `web.assets_backend`.
3. Owl requests `autostock.dashboard.get_dashboard_data` using Odoo's authenticated ORM RPC.
4. Server checks stock-user permission, uses active Odoo company and record rules, reads opted-in products, and returns an explicit status that ML is not integrated.
5. Browser renders live stock counts and empty AI states.

**Do not** claim `virtual_available` is an ML prediction: it is Odoo's projected stock based on known operations. It is labeled 'Odoo projected' in the UI.

## Forecast research design

The offline model uses daily SKU demand, a calendar timeline, lags and rolling history. It fits a RandomForestRegressor against a naive seven-day mean baseline. Both are evaluated by recursive prediction on the same chronological holdout, then the better approach is selected. Results describe method, metrics and limitations. Missing intra-period dates are treated as zero; this is only valid if data collection covers those dates. Returns, canceled orders, internal transfers and out-of-stock censored demand need separate treatment before real deployment.

The heuristic error band is not calibrated. Do not label it 90% confidence just because its underlying one-fold absolute-error quantile uses 0.90.

## Next milestone: safe integration design

- A forecast run model should store SKU, company/warehouse, training cutoff, horizons, data provenance, selected model ID/version, loss metrics, assumptions, forecast points, created by, and review status.
- Aggregate confirmed completed customer deliveries from stock moves or relevant business records ONLY after verifying operations and business semantics; no double counting, no future leakage.
- Run CPU-bound ML outside interactive Odoo requests via a reviewed scheduled job/worker; enforce time/memory bounds and persist only validated numeric outputs.
- Restrict report/assistant to Odoo-enforced ACL and user-selected company.
- Keep draft purchase actions behind explicit user confirmation and server-side Odoo access checks.

## Production blockers

No production approval, no consented business dataset, no end-to-end Odoo/browser testing in this initial workspace, no backups/restore verification, no hardened deployment, no cross-company security test. This repository is a development starter only.
