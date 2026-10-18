# AutoStock AI — Plan

Each step ends with something the owner can open and click. The owner approves before the next step starts.

## Step 1 — Foundation
- [x] 1a. Project runs: `docker compose up` starts the database, the server and the website. Website shows a styled "AutoStock AI" page. A health check endpoint answers.
- [x] 1b. Design system: colors, Inter font, buttons, cards, inputs, tables, badges, empty/loading/error states. One page that shows them all.
- [x] 1c. Accounts: organization, users, roles (owner / manager / staff), login, logout, first-owner setup screen.
- [ ] 1d. App shell: sidebar, top bar, page layout, works on phone. Audit log in place.

## Step 2 — Smart import + stock
- Parts, warehouses/branches, suppliers, stock levels, sales history tables.
- Upload an Excel/CSV file. AI suggests which column is which; the user confirms. Duplicates flagged. Preview before saving.
- Stock screen: search, filter, low / out / dead stock, part detail.

## Step 3 — Part search
- Search by name, SKU, OEM reference, in French, Arabic or English, with typos.
- Equivalent parts from other brands that fit the same car.

## Step 4 — Forecasting
- 7 / 30 / 60-day demand per part and per branch.
- Measured against a simple baseline on past data; the result is shown honestly per part.
- Slow-moving parts handled with methods made for them.

## Step 5 — What to order
- Suggestions from forecast + stock + supplier delivery time + budget limit.
- One-sentence reason per line. Manager approves, edits or rejects.
- Approved lines become a purchase order PDF per supplier.

## Step 6 — Dashboard + alerts
- One screen: stock health, what to order, forecast highlights.
- Alerts for unusual sales spikes, drops, and stock that doesn't match sales.

## Step 7 — Ask your shop
- Questions in plain language, answered from the shop's real data, with the numbers shown.

## Step 8 — Polish and launch
- French and Arabic (right-to-left). Realistic Moroccan demo shop. Backups. Speed check. Presentation.
