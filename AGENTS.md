# Coding-agent instructions — AutoStock AI

**Read `CODEX_START_HERE.md` and `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN_SYSTEM.md`, and `docs/IMPLEMENTATION_PLAN.md` before editing.**

- Odoo target: 19.0 Community. Keep the addon isolated under `addons/autostock_ai/`.
- Do not alter SmartImport or any other project.
- Do not invent inventory values, forecast accuracy, pricing, supplier records, or business claims.
- Do not bypass Odoo ACLs/record rules, use sudo to fetch business data, or allow LLM-generated purchasing actions.
- Never merge, deploy or send company data outside the local environment without user approval.
- Treat [commercial readiness issue #7](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/7) and [premium UX issue #8](https://github.com/MouhssineElBoumshouli/autostock-ai/issues/8) as cross-phase requirements. Keep each PR scoped, state which gates it satisfies and which remain open, and do not call the product production-ready until the full release evidence is complete.
- Keep the screenshot as a **design reference**, not a screenshot of running software.
- Work in small feature branches and open draft PRs for review.

## Simplicity and maintainability — owner requirement

- Write code the owner can read, understand, explain, and safely change. Use clear names, focused functions, and modules with one job.
- Follow the existing Odoo → authenticated API → typed React client → screen flow. Place a rule where it belongs; do not duplicate business decisions in the UI.
- Prefer the smallest working change and plain-language comments for non-obvious business rules. Avoid clever abstractions, unnecessary dependencies, new frameworks, and large rewrites.
- When a file becomes hard to follow, split it at a real responsibility boundary and preserve its behavior, routes, permissions, and tests. Reuse shared UI only for patterns that truly repeat.
- For each meaningful change, explain in simple words what changed, where to find it, how to modify it, and what was actually tested. See issue #38 for focused cleanup work.

- Always document actual checks completed and distinguish static/unit checks from live Odoo install and browser tests.
- Start with the foundation validation task in `CODEX_START_HERE.md`.
