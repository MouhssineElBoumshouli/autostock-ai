# How AutoStock AI got here

AutoStock AI was built twice. This page tells the story, so it can be shown in a presentation.

## Version 1 — built on Odoo (9–17 October 2026)

**The idea:** Odoo is a big open-source business system (stock, sales, purchasing, accounting).
Building AutoStock AI as an Odoo add-on meant getting stock and purchasing for free, and adding the AI on top.

**What it had:**
- Odoo 19 + PostgreSQL in Docker, with a custom `autostock_ai` module
- Demand forecasts for 7, 30 and 60 days (random forest compared against simple baselines and Croston's method for slow-moving parts)
- Stock-risk warnings and read-only reorder suggestions
- A React website on top of Odoo with Dashboard, Inventory, Warehouses, Suppliers and Forecasts screens
- A realistic Moroccan demo shop: 150 parts, 2 warehouses, 90 forecasts

**What we learned:**

| | Odoo version |
|---|---|
| Time | 9 days |
| GitHub issues and pull requests | 63 |
| Lines of code | about 35,500 |
| Lines just to load demo data into Odoo | about 5,800 |
| Documentation files | 131 |

- **Odoo was heavy to work with.** Most of the effort went into fighting the platform, not building the product. About 25 pull requests were only about loading demo data into Odoo safely and fixing Windows setup problems.
- **Odoo is heavy to sell.** A shop would have to adopt a whole business system just to use our app. Most small Moroccan parts shops run on Excel, not Odoo.
- **The design suffered.** Odoo's rules pulled the screens away from the design we chose. The owner rejected the result as too complicated for a normal employee.
- **Main features never arrived.** Purchase orders, budget planning, the AI assistant, PDF reports and French/Arabic were still missing.

**The decision (17 October 2026):** keep what worked (the forecasting ideas, the design, what we learned about users) and rebuild lean.

The full Odoo version is kept, untouched, on the
[`archive/odoo-v0`](https://github.com/MouhssineElBoumshouli/autostock-ai/tree/archive/odoo-v0) branch.
Screenshots of it running:
[Inventory](https://github.com/MouhssineElBoumshouli/autostock-ai/blob/archive/odoo-v0/docs/qa/screenshots/issue-28-gate-4/inventory-desktop-1440.png) ·
[Forecasts](https://github.com/MouhssineElBoumshouli/autostock-ai/blob/archive/odoo-v0/docs/qa/screenshots/issue-34-gate-7-employee-first/forecasts-by-part-30-day-1440.png) ·
[All screenshots](https://github.com/MouhssineElBoumshouli/autostock-ai/tree/archive/odoo-v0/docs/qa/screenshots)

## Version 2 — lean (from 17 October 2026)

React website + FastAPI server + PostgreSQL database. One command starts everything: `docker compose up`.
No outside business system. The shop's data comes in from an Excel file.

The comparison above is not fair yet: version 2 is just starting.
Update this section as each step of `PLAN.md` is finished, so the final presentation can compare the two versions feature for feature.

- **Step 1a — project runs (17 October 2026):** `docker compose up` starts the database, the server and the website; the website shows a card with a live "Connected" badge from the server's health check, and code changes reload by themselves.
- **Step 1b — design system (18 October 2026):** every building block (buttons, inputs, cards, stat cards, badges, a table that becomes cards on phones, dialog, toast, tabs, loading/empty/error states) on one `/design` page, with all colors and sizes defined once and a right-to-left preview for Arabic.

## The design we kept

The approved design direction, used for both versions:

![Approved design concept](../design/dashboard-concept.png)

It is a concept image, not real data. The rules that come from it are in `CLAUDE.md` under "Design".
