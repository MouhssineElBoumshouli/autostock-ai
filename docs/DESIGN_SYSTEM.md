# Visual design contract

Approved direction: a blend of three supplied SaaS dashboards, weighted most toward the clean purple-white third reference. The generated concept is stored at `design/dashboard-concept.png` and is **not** a functioning app screenshot.

## Visual language

- Surface: off-white/light gray `#f7f8fc`, cards white `#fff`, delicate strokes `#e9eaf1`.
- Primary action: violet `#7847ee` used sparingly for active states, key actions, forecast emphasis.
- Text: deep navy `#1b2340`, muted slate `#7d8394`.
- Semantics: green healthy, amber caution, red risk; never rely on color alone.
- Cards: 14–16px rounded corners, subtle 1px strokes, barely visible shadows.
- Typography: modern system/UI font, 14px normal copy, strong visual hierarchy, tabular numerals.
- Layout: left Odoo navigation and custom main content, narrow header, four KPI cards, 2-column analytics area, insights, data table. Responsive down to mobile.

## Required states

- Loading skeleton/spinner, empty product selection, empty prediction history, permission error, network error, validation warning, report generation pending/error, AI unavailable.
- UI never uses made-up numbers to fill space. Concept screenshot data is illustrative only.
- Charts show timeframe and true source, differences between observed/forecasted, model validation status and clearly explained uncertainty.
- Accessible focus styles, readable contrast, keyboard actions, screen reader tables, reduced motion.

## Report identity

Consistent typography, violet headers, small clear KPI summaries, thoughtful chart colors, readable tables, explicit methodology and assumptions, page numbers and dates. The report should feel as carefully designed as the dashboard.

## Design review

At each UI milestone: compare real screenshot with reference on 1440px desktop, 1024px tablet and 390px mobile. Check spacing, legibility, overflow, state consistency and accessibility. Prefer fewer, excellent screens over many visually inconsistent ones.
