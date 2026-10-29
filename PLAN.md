# AutoStock AI — Plan

Each step ends with something the owner can open and click. The owner approves before the next step starts.

## Step 1 — Foundation
- [x] 1a. Project runs: `docker compose up` starts the database, the server and the website. Website shows a styled "AutoStock AI" page. A health check endpoint answers.
- [x] 1b. Design system: colors, Inter font, buttons, cards, inputs, tables, badges, empty/loading/error states. One page that shows them all.
- [x] 1c. Accounts: organization, users, roles (owner / manager / staff), login, logout, first-owner setup screen.
- [x] 1d. App shell: sidebar, top bar, page layout, works on phone. Audit log in place.

## Step 2 — Smart import + stock
- Parts, warehouses/branches, suppliers, stock levels, sales history tables.
- Upload an Excel/CSV file. A free local model suggests which column is which; the user confirms. Duplicates flagged. Preview before saving.
- Stock screen: search, filter, low / out / dead stock, part detail.

## Step 3 — Part search
- Search by name, SKU, OEM reference, in French, Arabic or English, with typos.
- Equivalent parts from other brands (same OEM number, manager links, supplier cross-reference files).

## Step 4 — Forecasting
- 7 / 30 / 60-day demand per part and per branch.
- Measured against a simple baseline on past data; the result is shown honestly per part.
- Slow-moving parts handled with methods made for them.

## Step 5 — What to order
- Suggestions from forecast + stock + supplier delivery time + budget limit.
- One-sentence reason per line. Manager approves, edits or rejects.
- Approved lines become a purchase order PDF per supplier.
- [x] 5a. Suggestion math (need, cushion, packs, slow sellers, budget, reasons), stored per run, proven by a 6-month replay against the usual minimum rule. No screens.
- [x] 5b. Screens: manager approves, edits or rejects; purchase orders per supplier; orders on their way count in the next suggestion.

## Step 6 — Dashboard + alerts
- One screen: stock health, what to order, forecast highlights.
- Alerts for unusual sales spikes, drops, and stock that doesn't match sales.
- [x] 6a. Alerts engine (spikes, drops, negative stock, sold at 0, frozen stock), daily limit and no-repeat, "Looked at it" / "Not a problem", measured on problems planted in the demo. No screens.
- [x] 6b. Home becomes "Today": what needs you, what to order, late deliveries, worth a look, this week's sales vs a normal week. New Alerts page with filters. Staff see it all but without money totals or the mark buttons.

## Step 7 — Ask your shop
- Questions in plain language, answered from the shop's real data, with the numbers shown. Runs on a free local model (Ollama); optional.
- [x] 7a. Engine: 10 read-only question types; the rule says "not sure" instead of guessing; rule + local model (qwen2.5:3b) only when unsure, measured on two labeled sets (150 questions, 4 languages); "I understood: ..." before every answer; staff get no money. No screens.
- [ ] 7d. Answers written by the app (en/fr/ar sentences, "why" by rules), the local model only reads; optional Groq cloud writer (owner's switch); each person's last 20 questions kept; sidebar fits the screen. Measured on the 60 questions; side-by-side in `docs/ask-readability.md`.

## Step 8 — Polish and launch
- French and Arabic (right-to-left). Realistic Moroccan demo shop. Backups. Speed check. Presentation.
- **Ready for a real shop:** production mode (no developer features, real password required), a one-page install guide, daily backup with a tested restore, updates without losing data, export all data to Excel, friendly error messages, a short "start here" guide for a new shop.
- [x] 8b-1. Production mode on one shop PC (`docker-compose.prod.yml`, port 8080, several addresses), strong password required, restarts by itself, capped logs, shop time zone; daily checked backups with a tested restore and a backup before every update; forgotten password from the shop PC; `docs/INSTALL.md` (French, English).
- [x] 8b-2. Export all data to Excel (one sheet per kind, in the owner's language, proven by a real round trip through the import screen); friendly error messages everywhere (page not found, page crash, connection lost, server error with a reference code, session expired, no permission); a "Start here" checklist for a brand-new shop with downloadable sample files, and a way to add a supplier with its delivery time; times shown in the shop's own time zone from the server, not the browser's.
