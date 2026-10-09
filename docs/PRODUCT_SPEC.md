# Product specification — AutoStock AI

## Problem

An automotive parts seller faces changing demand, many product references, uncertain delivery lead times and limited purchasing budgets. Odoo already manages inventory, confirmed stock forecasts and replenishment; AutoStock AI must ADD evaluated future-demand predictions, interpretable prioritization and business simulations, rather than duplicating built-in features.

## Users

- Inventory clerk: can review stock, part references, incoming/outgoing movements, and basic alerts.
- Inventory manager: can view model findings, explore trade-offs, approve (not silently execute) suggested actions and create draft purchase orders through native Odoo.
- Business manager: can generate understandable comprehensive reports and review decision evidence.

## Approved essential functionality (target scope, not necessarily built)

1. Inventory overview using actual Odoo products, warehouse moves, confirmed receipts and deliveries.
2. 7/30/60-day demand forecasts with reproducible backtesting, non-trivial ML-vs-baseline comparison and uncertainty labels.
3. Stockout and slow-moving-item detection using predicted demand, on-hand/forecasted Odoo stock, lead times and open orders.
4. Proposed replenishment quantities and the reasons for each; users must approve draft RFQs/POs.
5. What-if simulator for demand spikes, lead-time changes and spending limits, without touching live inventory.
6. Budget-constrained reorder optimizer: deterministic solver using verified forecasts and supplied costs/constraints.
7. AI business assistant limited to permission-aware read-only retrieval and source-backed explanations.
8. Professional full report generator with a short plain-language executive summary and comprehensive evidence.
9. Premium visually coherent UI, including dashboards, tables, charts, states, responsive screens, and report styling.

## Later possible additions

Fuzzy/OEM part lookup and *verified* vehicle fitment, supplier reliability prediction, anomaly detection. **Fitment must never be invented from an LLM.**

## Report requirements

- Select company (from authorized companies), date range and warehouse scope.
- Cover inventory position, movement, risk, forecasts, reorder proposals, budget scenarios, caveats and concrete actions.
- For every financial figure: state currency, source, exchange-rate assumptions and treatment; no guesses.
- Charts match the UI style and include legends, accessible labels and date ranges.
- Present a one-page management summary first, followed by detailed tables, method explanations, data coverage/quality and a technical appendix.
- Make obvious when metrics use synthetic inputs, incomplete coverage, or weak training history.
- Output QWeb PDF; structured spreadsheet export is a later feature. Source references and timestamps should be reproducible where possible.

## Acceptance criteria

- Manager can complete an entire stock-review workflow without leaving Odoo.
- Every AI recommendation links to input data and an explainable formula or evaluated model.
- No purchasing action without user review. No arbitrary AI-generated database action.
- Forecasts have a chronological evaluation and a baseline comparison; weak/no history gives explicit uncertainty/insufficient-data states.
- Print report is simultaneously readable by a non-technical manager and auditable by a technical reviewer.
- UI looks polished on desktop and remains usable on narrower screens.
