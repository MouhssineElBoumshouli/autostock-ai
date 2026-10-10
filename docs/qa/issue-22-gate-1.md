# Issue #22 — Gate 1 visual replica QA

**Date:** 2026-10-10
**Branch:** `rebuild/reference-first-ui`
**Scope:** Dashboard visual replica only, backed by typed local development fixtures.

## Result

The Dashboard has been rebuilt as a fixture-only React screen against [`design/dashboard-concept.png`](../../design/dashboard-concept.png). Its composition follows the reference's compact branded sidebar, global search/header, title and date/report controls, five KPI cards, two-column forecast and inventory-health area, three insight cards, and dense reorder table. No Odoo session or API call is made by this Dashboard. The browser regression records and rejects any `/autostock/api/` request.

The owner-approved Gate 1 visual direction received a focused readability pass after review: small labels, supporting copy, chart legends/captions, and table metadata increased by one or two pixels where appropriate. Headings, KPI values, card dimensions, spacing, proportions, and responsive composition were preserved. Playwright now checks representative computed text sizes at all three target widths.

The visible `Visual preview · fixture data` label and the footer note identify the numbers as development fixtures. In particular, `92.4%` is an illustrative value only; it is not a forecast accuracy result or a business validation claim. The fixture source is [`frontend/src/data/development-dashboard-fixture.ts`](../../frontend/src/data/development-dashboard-fixture.ts).

## Screenshots

| Browser viewport | Actual Playwright capture |
| --- | --- |
| Desktop, 1440 × 1080 | [dashboard-1440.png](screenshots/issue-22-gate-1/dashboard-1440.png) |
| Tablet, 1024 × 768 | [dashboard-1024.png](screenshots/issue-22-gate-1/dashboard-1024.png) |
| Mobile, 390 × 844 | [dashboard-390.png](screenshots/issue-22-gate-1/dashboard-390.png) |
| Reference compared side-by-side with desktop capture | [reference-vs-dashboard-1440.png](screenshots/issue-22-gate-1/reference-vs-dashboard-1440.png) |

The screenshots show full-page layout at the stated viewport width. Playwright verified that each page has no horizontal overflow and that the forecast SVG uses more than 200 pixels of available plot width.

## Reference comparison and remaining differences

- Desktop preserves the approved navigation density, five-card KPI strip, wide-to-narrow analytics split, insights row, and full reorder table. Typography uses the same restrained navy/slate and violet hierarchy with light card strokes and soft shadows.
- The small `Visual preview · fixture data` label and the final table footnote are additions to the reference so no illustrated metric can be mistaken for validated business data.
- The chart and donut are static fixture visualizations. The chart tooltip and controls are present for composition only and do not respond to input in Gate 1.
- Product thumbnails use local line icons rather than the concept's small product photos.
- At tablet width the sidebar remains visible and the analytics stay side by side; compact trend badges and the confidence column are reduced to preserve the page density.
- At mobile width the sidebar becomes a menu mark, analytics and insights stack, and each reorder row becomes a compact product-and-quantity card. This is a responsive adaptation rather than a pixel-for-pixel crop.
- Navigation destinations and visible actions are inert, visual-only elements. No Inventory, Forecasts, Restock, Reports, Assistant, purchasing, or other screen/workflow was added.

## Checks

| Check | Result |
| --- | --- |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm run test:unit` | Passed, 3 tests |
| `npm run test:contract` | Passed, 5 tests |
| `npm run test:browser` | Passed, 1 Playwright test covering 1440, 1024, and 390 px; 5 KPIs, 3 insights, 5 reorder rows, computed readability sizes, chart width, no overflow, no page errors, and no Odoo API requests |
| Playwright screenshot capture | Passed; all three responsive screenshots and the desktop side-by-side comparison refreshed after the readability pass |
| `npm run build` | Passed; Vite production build completed |

No Odoo installation, integration, data, or business workflow was exercised for this visual gate by design. Gate 1 is not evidence of live inventory or forecasting correctness. Odoo wiring remains gated on owner approval of the visual and interaction gates.
