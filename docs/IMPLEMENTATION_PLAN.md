# Feature branch plan

| Stage | Scope | Test gate | Status |
|---|---|---|---|
| P0 | Scaffold Docker, addon, product fields, dashboard, model lab, docs | Static parse & Python tests | Initial package ready for local review |
| P0b | Run Odoo 19, install addon, fix Odoo API/view differences | Actual Odoo integration and browser smoke tests | Pending local Docker / Codex |
| P1 | Historical sales extraction and data provenance, no double counting | Realistic fixtures and records isolation | Not started |
| P2 | ML predictions persisted in Odoo; benchmark vs baselines | Chronological out-of-sample tests | Offline lab only |
| P3 | Stock risk, reordered quantities, human review | Domain and permission tests | Not started |
| P4 | Budget optimizer and what-if simulator | Repeatability and constraint tests | Not started |
| P5 | Permission-aware assistant and report generator | Hallucination, source proof, PDF golden tests | Not started |
| P6 | Premium polish, QA, E2E workflows and packaging | Desktop/mobile/a11y/visual QA | Not started |

## PR discipline

Each feature branch adds tests and screenshots where appropriate. An independent reviewer checks claims and Odoo integration. CI alone is not proof that the addon actually installs in Odoo. Use manual acceptance evidence before merge.

## Presentation integrity

The previous internship ended August 2026. Do not present a later-created module as if it had been completed during the internship; ask the academic supervisor whether this additional project can be presented, and describe the timing clearly.
