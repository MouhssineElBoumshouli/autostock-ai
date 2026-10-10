# Feature branch plan

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
| P3A.5 | Guarded local fictional automotive showroom for in-person product review | Isolated Odoo/PostgreSQL setup, actual generated sale/delivery records, real forecast worker, permissions, Windows setup, and desktop/tablet/mobile browser evidence | Implemented on a draft PR; see [showroom guide](SHOWROOM_GUIDE.md) and [showroom QA report](qa/showroom-demo.md) |
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
