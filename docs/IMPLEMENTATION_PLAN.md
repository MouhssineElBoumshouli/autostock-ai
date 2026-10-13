# Feature branch plan

## Gate 7 — Forecasts workspace

### Data and access plan

- Add authenticated, read-only API endpoints for an exactly counted, server-filtered/paginated forecast-run list and exact-run detail. Validate the selected company and optional warehouse, preserve ACLs and record rules, and never use `sudo()`.
- Keep real delivery history restricted to users who have both inventory and Sales access. A stock-only user may see only the isolated synthetic showroom examples and must not learn real-run counts or metadata.
- Serialize saved run observations, return events, forecast points, coverage dates, evaluation facts, provenance, and review metadata. For detail, reuse the existing inventory-risk service to report whether the selected run is currently used for restock guidance; do not reproduce forecast or reorder calculations in React.

### UX and verification plan

- Preserve the approved AutoStock shell and readability baseline. Provide a filterable Forecasts workspace, exact-run detail, clear delivered-sales versus returns charting, a “Forecast starts” marker, an accessible method/MAE explanation, and explicit loading, empty, restricted, error, stale, insufficient-history, and synthetic states.
- Keep the workspace read-only: no queue, review, approve, purchase, or report actions. Never translate MAE into an accuracy percentage or describe fulfilled deliveries as unconstrained demand.
- Verify company and warehouse isolation, a catalog of more than 1,000 saved runs, detail side effects, role restrictions, API contracts, responsive browser behavior, and actual Atlas showroom evidence. Record exact commands, outcomes, screenshots, and limitations in `docs/qa/issue-34-gate-7.md`.

## Cross-phase quality requirements

The [commercial-readiness charter](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/7) and [premium UX acceptance criteria](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/8) apply throughout all phases. They define release gates for correctness, security, operations, maintainability, usability, accessibility, and visual evidence. Phase completion does not imply commercial readiness; release status requires the full documented evidence described in issue #7.

| Stage | Scope | Test gate | Status |
|---|---|---|---|
| P0 | Odoo addon scaffold, product fields, inventory dashboard, offline ML lab | Static parse and Python tests | Complete in PR #1 |
| P0b | Install and validate the addon in Odoo 19 | Fresh-database addon integration and browser checks | Complete in PR #1 |
| P1 | Verified sales-history scope, demand definition, provenance and company boundaries | Delivery/return, cutoff, UoM, multi-company and ACL tests | Implemented with Phase 2 |
| P2 | Persisted 7/30/60-day forecasts; chronological comparison with simple baselines; scheduled work; reviewed result UI | Python evaluation, Odoo integration suite and browser checks | Implemented with Phase 2; see [QA report](qa/phase2-demand-forecast.md) |
| P2.5 | Premium Odoo dashboard shell, responsive navigation, readable forecast charts and useful inventory states | Odoo integration tests, live browser interactions and desktop/tablet/mobile screenshots | Merged into `main` in PR #10; see [QA report](qa/phase2-5-premium-dashboard.md) |
| P3A | Company/warehouse-scoped stock-risk analysis and explainable, read-only reorder guidance | Calculation, forecast eligibility, multi-company, Odoo access and browser scenario tests | Implemented on `codex/phase3a-stock-risk-recommendations`; draft PR and QA evidence in [Phase 3A report](qa/phase3a-risk-replenishment.md) |
| Frontend foundation | React 19 + TypeScript client, approved shell/interactions, authenticated Odoo Dashboard | Python/Odoo HttpCase, frontend lint/typecheck/unit/API-contract/browser tests, live showroom screenshots | Gates 1–3 approved and merged; see [frontend QA report](qa/react-dashboard-foundation.md) |
| Gate 4 (Issue #28) | Real read-only Inventory route, server-side catalog operations, product details | Odoo integration, 1,000+ product paging/search, responsive live showroom browser checks and screenshots | Approved and merged; see [Inventory QA report](qa/issue-28-gate-4.md) |
| Gate 5 (Issue #30) | Real read-only Warehouses route, scoped stock summaries, warehouse inventory and activity | Odoo integration, child-location aggregation, 1,000+ product warehouse catalog, responsive live showroom browser checks and screenshots | Implemented on `product/warehouses-screen`, draft PR; see [Warehouses QA report](qa/issue-30-gate-5.md) |
| Gate 6 (Issue #32) | Real read-only Suppliers route, vendor terms, current restock context and missing-supplier discovery | Odoo company/access/tier tests, large supplier/term coverage, frontend/API/browser checks and live showroom screenshots | Implemented and tested on `product/suppliers-screen`; awaiting owner review in a draft PR; see [Suppliers QA report](qa/issue-32-gate-6.md) |
| Gate 7 (Issue #34) | Authenticated, read-only Forecasts workspace with exact run history, evaluation explanation and current guidance eligibility | Odoo company/warehouse/ACL and 1,001-run paging tests, frontend/API/browser checks and live Atlas screenshots | Implemented on `product/forecasts-screen`; local Odoo and live screenshot QA blocked by Docker Desktop engine failure; see [Gate 7 QA report](qa/issue-34-gate-7.md) |
| Moroccan warehouse-forecast gate (Issue #42) | Independently verified company/product/warehouse/date/version histories; exact warehouse evidence for restock; source-change invalidation and manager review | Odoo 19 integration tests against native delivery/return/stock records, exact-scope risk checks, frontend/API contracts and browser regressions | In progress on `product/issue-42-warehouse-forecasts`; draft PR and QA evidence in [Issue #42 report](qa/issue-42-warehouse-forecasts.md). Historical fixture expires under the existing 14-day policy and is not a showroom cutover dataset. |
| P3B / P3C | Remaining Phase 3 milestones | Their own issue scope, domain tests and browser evidence | Planned; not included in Phase 3A |
| P4 | Budget optimizer and what-if simulator | Repeatability and constraint tests | Planned |
| P5 | Permission-aware assistant and report generator | Source-grounding and PDF rendering tests | Planned |
| P6 | Premium polish, accessibility, end-to-end workflows and packaging | Desktop/tablet/mobile and accessibility QA | Planned |

## Phase 2 scope boundary

Forecast output is decision support. It does not create purchase orders, alter inventory, estimate hidden demand during stockouts, or claim calibrated confidence. Only completed customer deliveries and linked returns are used for real Odoo history. An administrator must configure the earliest date from which that source is known complete. The UI labels synthetic demo runs and keeps them separate from Odoo sales and stock records.

## PR discipline

Each feature branch adds relevant tests and screenshot evidence where export is available. CI is not a substitute for checking the installed addon in Odoo and exercising the interface. Document exact checks, results, and limitations before review.

## Presentation integrity

AutoStock AI was created after the Bounaim Auto internship that ended August 2026. Do not present later work as internship deliverables; confirm academic eligibility and disclose dates clearly.
