# Issue #36 — Moroccan Odoo importer QA

## Scope and safety boundary

This review update hardens repeat-import integrity, closes stale forecast evidence, and adds an honest missing-supplier example. It does not provision or seed the local Moroccan showroom, change the app connection, or modify the existing USD Atlas showroom, its database, files, credentials, containers, or volumes. The public Apply path remains disabled behind the existing signed-backup and independent-restore evidence gate.

Odoo integration tests run only in GitHub Actions, against a newly created Odoo 19/PostgreSQL 16 database in a unique CI Compose project. The test transaction rolls back; the workflow removes only that CI project's containers and volumes.

## Dataset and importer integrity

- Deterministic fixture: `atlas-ma-2026.3`, seed `36036`, SHA-256 `e3a31d18253efbc61cac38310fa7d941856271d956fccd78d55096f0b7b3e508`.
- The offline plan has 6,656 fixture identities, 150 products, 8 suppliers, 18 customers, two warehouses, 350 completed customer orders, 30 receipts, 12 linked returns, 18 transfer journeys, 20 open orders, 24 history profiles, and 298 warehouse reorder rules. The generated on-hand ledger reconciles per product/location/UoM.
- A full existing fixture registry is now checked against current Odoo business records, not treated as proof based only on saved payload hashes. Read-only checks cover the company/currency, SKU/name/category/prices and stock settings, supplier price tiers/currency/MOQ/lead time, reorder rules, confirmed sale orders and lines, business dates, completed/open pickings and moves, return-to-delivery links, history profiles, forecast request metadata, and on-hand per warehouse.
- Missing, canceled, changed, and unregistered fixture records fail the preview. Any ledger variance also fails closed. An unchanged repeat import remains a no-write operation and repeats the live audit immediately before returning no-op, including when given a previously generated preview.
- Focused Odoo regressions mutate live product and supplier prices, a dated delivery move, a completed sale line, a return link, and current stock; each must fail as actual-state drift. Other regressions cover an untouched repeat/no-duplicate transaction path, a deleted registered record, and an unregistered fixture-prefixed product. Preview remains read-only.

## Forecast review and timezone preferences

- The live integrity audit treats forecast review as a supported lifecycle change. It accepts a reviewed status only on a completed forecast with both reviewer and review timestamp recorded; an unreviewed forecast must not have review audit fields. A queued forecast with a review, or a completed forecast with missing review metadata, fails closed.
- A completed forecast must retain one result point for every day in its requested horizon, while queued runs must not have result points. This catches missing or incomplete saved results without comparing mutable model output to a fixture hash.
- User timezone preferences are not fixture data. Changing administrator/operator or manager/reviewer timezone after import no longer fails the audit; a dry-run/no-op repeat leaves those preferences unchanged. Fresh-target preparation still sets the bootstrap Odoo administrator timezone to `Africa/Casablanca`.
- Odoo regression coverage completes a forecast, reviews it as a non-admin inventory manager, then verifies dry-run and no-op repeat import succeed with zero mutations or duplicate transactions. The same test confirms forged/incomplete review metadata, an invalid reviewed/queued state, and missing forecast points still fail. A subsequent source-movement change makes the reviewed run ineligible and causes the integrity audit to report drift; its review audit remains intact.

## Missing supplier example

`AT-MA-FLT-132` — Fuel Filter Element (Series 3) — is a slow-moving product with no supplier terms, no supplier price, no reorder policy, no historical sales, no receipts, and no customer deliveries or transfers. It has only opening inventory: 8 units at Atlas Central Warehouse and 5 at South Service Depot. The supplier-gap API test verifies zero supplier terms and no lead time, price, or suggested order. This is a supplier-information gap, not a generated purchasing recommendation.

## Forecast source validity and warehouse cutover blocker

The 72 imported requests remain company-wide (24 products × 7/30/60 days); they are not evidence for either warehouse. Existing restock eligibility requires an exact company/product/warehouse match, so these company-wide runs cannot support warehouse-level restock guidance. No warehouse-level history or forecasts are claimed in this milestone.

**Mandatory before Moroccan showroom cutover:** implement and independently review a follow-up that creates only evidence-backed, product-and-warehouse-scoped histories and forecast runs. Cutover acceptance requires all of the following:

1. Atlas Central Warehouse and South Service Depot each have at least one forecast example whose source deliveries and linked returns are independently verified for that exact product and warehouse over the declared training and holdout windows.
2. Risk/restock results accept only a matching company, product, and warehouse. A company-wide run must never satisfy either warehouse's evidence lookup; a run for one warehouse must never appear as evidence for the other.
3. Forecast UI and restock explanations identify the selected warehouse and withhold forecast-based guidance when qualifying history is missing or insufficient. No accuracy or reviewed-status claim is made without the corresponding evaluation and human review.
4. Odoo integration tests cover real multi-warehouse source records, source changes, permission boundaries, and the exact-match eligibility rules before the app is switched to this database.

Separately, completed or reviewed Moroccan profile runs now recheck their current source-history digest when selected as risk/replenishment evidence. A qualifying dated delivery/return-history edit makes the run ineligible as current evidence without rewriting the saved run state, forecast points, or review audit. A change to an unrelated product's history does not invalidate the profile. Tests verify both cases. This is an eligibility barrier; it does not claim that historical forecast output itself has been recalculated.

## Verification

- Local `python -m pytest -q`: **65 passed**. Windows emitted non-fatal pytest temporary-directory cleanup warnings (`WinError 145`) after the passing run.
- Local `python -m compileall -q addons ml scripts tests`: passed.
- Offline generator/import-plan command `python -m scripts.moroccan_showroom.cli --seed 36036`: passed; generated ledger reconciled, 6,656 identities, zero writes, dataset digest above. It did not connect to or inspect Odoo.
- `python -m ml.evaluate ml/output/synthetic_daily_sales.csv --days 30`: completed for 6 labeled synthetic products. This checks the evaluator pipeline only; it is not a Moroccan or customer accuracy claim.
- GitHub Actions [full-suite run 38315149815](https://github.com/MouhssineElBoumshouli/autostock-ai/actions/runs/38315149815) on implementation commit `efd08000bbaed131ca561f9ce90dfdabce9e43cd`: **all three jobs passed**. Python CI reported **65 passed**, compileall passed, and the labeled synthetic evaluator completed for **6 products**. React lint and typecheck passed; unit tests **10 passed**, API contract tests **16 passed**, Playwright **35 passed**, and the production build passed. Odoo 19 with PostgreSQL 16 reported **74 actual test cases passed, 0 failed, 0 errors**; Odoo's broader module statistics line counted 90 test activities. The Odoo run used its unique disposable CI database and Compose project.
- Local Moroccan showroom import, browser QA, and screenshots: **not run** by design. The showroom remains unprovisioned and unseeded.

## Remaining limitations

- Warehouse-specific forecast provenance and forecast-based restock guidance are a **mandatory blocker before Moroccan showroom cutover**; see the acceptance criteria above.
- Public Apply stays blocked until signed-backup and independent-restore evidence are explicitly approved. No public Apply was enabled or called in this work.
- GitHub Actions proves importer behavior in a disposable CI database only. It does not verify the prepared Windows/Docker environment or a local Odoo snapshot.
- All generated records are fictional demonstration data. Forecasts and inventory outcomes are calculated from the imported Odoo records, but they are not evidence of real-company accuracy or commercial readiness.
