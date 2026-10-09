# Coding-agent instructions — AutoStock AI

**Read `CODEX_START_HERE.md` and `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN_SYSTEM.md`, and `docs/IMPLEMENTATION_PLAN.md` before editing.**

- Odoo target: 19.0 Community. Keep the addon isolated under `addons/autostock_ai/`.
- Do not alter SmartImport or any other project.
- Do not invent inventory values, forecast accuracy, pricing, supplier records, or business claims.
- Do not bypass Odoo ACLs/record rules, use sudo to fetch business data, or allow LLM-generated purchasing actions.
- Never merge, deploy or send company data outside the local environment without user approval.
- Keep the screenshot as a **design reference**, not a screenshot of running software.
- Work in small feature branches and open draft PRs for review.
- Always document actual checks completed and distinguish static/unit checks from live Odoo install and browser tests.
- Start with the foundation validation task in `CODEX_START_HERE.md`.
