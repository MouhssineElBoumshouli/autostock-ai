# Instructions for Codex — AutoStock AI

You are working on an Odoo 19 Community custom addon for an automotive company. **Start by inspecting the entire repository, not by rewriting it.** The original internship SmartImport is an unrelated, completed project; do not import its code.

## Non-negotiable requirements

1. Work in a feature branch with small commits/PRs. Never merge, deploy, contact anyone, or touch production data without explicit approval.
2. Use only official Odoo Community APIs and existing models unless a custom model is truly needed. Do not modify upstream Odoo source code.
3. Follow `docs/PRODUCT_SPEC.md`, `docs/DESIGN_SYSTEM.md`, `docs/ARCHITECTURE.md` and the concept screenshot. The screenshot is a reference, not an implemented UI, not evidence of metrics.
4. Respect Odoo authentication, existing ACLs, allowed companies and record rules. No `sudo()` to bypass business permissions. Never use arbitrary LLM-produced SQL or unrestricted Odoo method execution.
5. Never show fake accuracy or demand data as real. Track dataset origin, model version, chronological evaluation, baseline metrics, uncertainty and limitations.
6. Financial calculations, forecast metadata persistence, safety stock policy, PO creation and spending constraints are authoritative server-side rules. AI explains/suggests but never executes purchasing unaided.
7. Desktop UI must feel premium: refined purple accent on warm white/light gray, restrained typography, consistent cards, accessible keyboard states, mobile fallback, graceful loading/empty/error states. Avoid copying competitor branding.
8. Report generation must be exceptional: plain-language summary PLUS detailed tables, charts, evidence, assumptions and technical appendix. No invented numbers.
9. Do not assert Odoo integration works until it is actually installed and exercised in a real Odoo 19 runtime. Distinguish static tests, Odoo integration tests, and browser QA.

## First coding assignment

**Review and harden the current foundation before adding more features.**

- Run `python -m pytest -q` and `python -m compileall -q addons ml scripts tests`.
- Start `docker compose up -d`, create a demo Odoo 19 database, install the custom AutoStock addon and fix actual install/import/view/asset errors. No fake test statuses.
- Verify correct product access permissions, company isolation, correct stock metrics and safe behavior with zero tracked products, one product, large catalog and user with no inventory rights.
- Check Odoo 19 field naming/API for the product model, inherited view and embedded Owl client action; fix mismatches.
- Compare the initial implemented dashboard with the concept image, improve consistent typography, spacing, real charts and responsive behavior without pretending AI is integrated.
- Capture desktop/mobile screenshots, write a concise QA report, and open a DRAFT PR. Do not merge.

## Next assignment after review

Integrate the offline ML lab safely: map done customer deliveries to daily SKU demand after inspecting the actual business flow, document returns and corrections, avoid data leakage, evaluate on real consented or labeled synthetic histories, store forecasts with model version/dataset timestamp, then show real forecast charts with clearly labeled uncertainty. Do not skip the evaluation and review gates.
