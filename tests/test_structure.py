import ast
from pathlib import Path
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "addons" / "autostock_ai"


def test_odoo_manifests_and_views_well_formed():
    manifest = ast.literal_eval(ast.parse((ADDON / "__manifest__.py").read_text(encoding="utf-8")).body[0].value)
    assert manifest["version"].startswith("19.0.")
    assert {"stock", "web", "sale_stock"}.issubset(manifest["depends"])
    for file in list(ADDON.rglob("*.xml")):
        assert etree.parse(str(file)).getroot().tag in {"odoo", "templates"}
    for filename in manifest["data"]:
        assert (ADDON / filename).exists()
    for asset in manifest["assets"]["web.assets_backend"]:
        assert (ROOT / "addons" / asset).exists()


def test_dashboard_never_shows_fake_ai_accuracy():
    xml = (ADDON / "static/src/dashboard/dashboard.xml").read_text(encoding="utf-8")
    assert "Synthetic sample only." in xml
    assert "No numeric forecast was produced" in xml
    assert "Heuristic range" in xml
    assert "not the demand forecast above" in xml
    assert "Forecasts aren't connected yet" not in xml
    assert "AutoStock AI" in xml


def test_dashboard_navigation_and_chart_controls_are_connected():
    xml = (ADDON / "static/src/dashboard/dashboard.xml").read_text(encoding="utf-8")
    javascript = (ADDON / "static/src/dashboard/dashboard.js").read_text(encoding="utf-8")
    forecast = (ADDON / "models/forecast.py").read_text(encoding="utf-8")

    assert 'aria-label="AutoStock AI navigation"' in xml
    assert 't-on-click="openProducts"' in xml
    assert 't-on-click="scrollToForecast"' in xml
    assert 't-on-click="changeChartWindow"' in xml
    assert "chartWindowDays" in javascript
    assert "company_logo_url" in forecast
    assert "Other decision tools" not in xml
    assert "Replenishment review" not in xml


def test_dashboard_full_history_company_switch_and_status_are_truthful():
    xml = (ADDON / "static/src/dashboard/dashboard.xml").read_text(encoding="utf-8")
    javascript = (ADDON / "static/src/dashboard/dashboard.js").read_text(encoding="utf-8")
    odoo_tests = (ADDON / "tests/test_forecast.py").read_text(encoding="utf-8")

    assert 'String(previousCompanyId) !== String(options.company_id)' in javascript
    assert "requestId !== this.forecastSnapshotRequestId" in javascript
    assert 'this.state.filters.productId = demoForecast ? String(demoForecast.product_id) : ""' in javascript
    assert 'this.state.chartWindowDays === "full"' in javascript
    assert '? [0, Math.floor((actual.length - 1) / 2), count - 1]' in javascript
    assert 'this.state.chartWindowDays = "full"' in javascript
    assert "through ${actual.at(-1).day}" in javascript
    assert "this.state.chartWindowDays = 30" in javascript
    assert "this.state.filters.warehouseId = demoForecast?.warehouse_id" in javascript
    assert ': "";' in javascript
    assert 'this.state.filters.horizon = String(demoForecast?.horizon_days || 30)' in javascript
    assert "isSelectedProduct(product)" in javascript
    assert 't-att-selected="isSelectedProduct(product)"' in xml
    assert 't-esc="activeSectionLabel"' in xml
    assert 'risks: "Restock"' in javascript
    assert "aria-live=\"polite\"" in xml
    assert "Odoo connection unavailable" in xml
    assert "Connected to Odoo" in xml
    assert "def test_company_ids_keep_company_specific_forecast_options" in odoo_tests
    assert 'with_company(company_a).get_forecast_options()' in odoo_tests
    assert 'with_company(company_b).get_forecast_options()' in odoo_tests
    assert 'self.assertNotIn(product_a.id, products_b)' in odoo_tests
    assert 'self.assertNotIn(warehouse_a.id, warehouses_b)' in odoo_tests


def test_dashboard_forecast_and_restock_are_distinct_views_with_real_data_preview():
    xml = (ADDON / "static/src/dashboard/dashboard.xml").read_text(encoding="utf-8")
    javascript = (ADDON / "static/src/dashboard/dashboard.js").read_text(encoding="utf-8")
    styles = (ADDON / "static/src/dashboard/dashboard.scss").read_text(encoding="utf-8")

    assert 't-att-data-as-view="state.activeSection"' in xml
    assert 't-on-scroll="updateActiveSection"' not in xml
    assert 't-on-click="scrollToRisks"' in xml
    assert 't-foreach="dashboardAlerts"' in xml
    assert 't-esc="alert.recommended_qty"' in xml
    assert 't-esc="alert.warehouse"' in xml
    assert 'this.navigateWorkspace("dashboard")' in javascript
    assert 'this.navigateWorkspace("forecast")' in javascript
    assert 'this.navigateWorkspace("risks")' in javascript
    assert "updateActiveSection()" not in javascript
    assert 'row.reorder_needed && Number(row.recommended_qty) > 0' in javascript
    assert 't-if="forecastDemandSummary"' in xml
    assert 't-esc="forecastDemandSummary.units"' in xml
    assert 'class="as-model-metrics"' in xml
    assert "get forecastDemandSummary()" in javascript
    assert "numbers.some((value) => !Number.isFinite(value) || value < 0)" in javascript
    assert ".as-app[data-as-view=\"dashboard\"] .as-risk-panel" in styles
    assert ".as-app[data-as-view=\"forecast\"] .as-risk-panel" in styles
    assert ".as-app[data-as-view=\"risks\"] .as-panels" in styles


def test_synthetic_inventory_cleanup_is_a_guarded_non_destructive_reset():
    script = (ROOT / "scripts/seed_odoo_demo_inventory.py").read_text(encoding="utf-8")
    report = (ROOT / "docs/qa/phase2-5-premium-dashboard.md").read_text(encoding="utf-8")

    assert 'ALLOWED_DATABASES = {"autostock_phase2_demo", "autostock_phase2_qa"}' in script
    assert 'elif action == "cleanup"' in script
    assert "does not delete QA products" in script
    assert "non-destructive reset" in report
    assert "products remain in the catalog" in report.lower()
    assert "template.unlink(" not in script


def test_odoo_ci_uses_public_docker_hub_cache_mirror():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "docker pull mirror.gcr.io/library/postgres:16" in workflow
    assert "docker tag mirror.gcr.io/library/postgres:16 postgres:16" in workflow
    assert "docker pull mirror.gcr.io/library/odoo:19.0-20260926" in workflow
    assert "docker tag mirror.gcr.io/library/odoo:19.0-20260926 odoo:19.0" in workflow


def test_showroom_fixture_refuses_every_database_except_its_isolated_demo():
    seed = (ROOT / "scripts/seed_showroom_demo.py").read_text(encoding="utf-8")

    assert 'SHOWROOM_DATABASE = "autostock_showroom_demo"' in seed
    assert "if env.cr.dbname != SHOWROOM_DATABASE" in seed
    assert seed.index("if env.cr.dbname != SHOWROOM_DATABASE") < seed.index(
        'parameters = env["ir.config_parameter"]'
    )


def test_phase3a_browser_fixture_guard_runs_before_browser_setup_and_checks_session_database():
    script = (ROOT / "scripts/qa_phase3a_browser.mjs").read_text(encoding="utf-8")
    guard_call = script.index("assertDisposableQADatabase(database)")
    playwright_load = script.index('require(process.env.PLAYWRIGHT_MODULE || "playwright")')
    screenshot_write = script.index("await mkdir(screenshotDir")
    login_navigation = script.index('await page.goto(`${baseUrl}/web/login?db=')
    session_check = script.index("await authenticatedDatabase()")
    scale_write = script.index('callKw("res.partner", "create"')

    assert guard_call < playwright_load < screenshot_write < login_navigation < session_check < scale_write
    assert 'actualDatabase === database' in script
    assert 'web/session/get_session_info' in script
    assert 'WARNING: QA fixture cleanup was incomplete' in script


def test_inventory_action_allows_users_to_choose_untracked_products():
    actions = etree.parse(str(ADDON / "views/dashboard_actions.xml"))
    action = actions.find(".//record[@id='action_autostock_products']")
    assert action is not None
    assert action.find("field[@name='res_model']").text == "product.template"
    domain = action.find("field[@name='domain']")
    assert domain is not None and "is_storable" in domain.text
    assert "autostock_enabled" not in domain.text
