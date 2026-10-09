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
    assert 'this.state.filters.productId = ""' in javascript
    assert 'this.state.chartWindowDays === "full"' in javascript
    assert '? [0, Math.floor((actual.length - 1) / 2), count - 1]' in javascript
    assert 'this.state.chartWindowDays = "full"' in javascript
    assert "through ${actual.at(-1).day}" in javascript
    assert "this.state.chartWindowDays = 30" in javascript
    assert "this.state.filters.warehouseId = \"\"" in javascript
    assert "this.state.filters.horizon = \"30\"" in javascript
    assert "<strong>Dashboard</strong>" in xml
    assert "aria-live=\"polite\"" in xml
    assert "Odoo connection unavailable" in xml
    assert "Connected to Odoo" in xml
    assert "def test_company_ids_keep_company_specific_forecast_options" in odoo_tests
    assert 'with_company(company_a).get_forecast_options()' in odoo_tests
    assert 'with_company(company_b).get_forecast_options()' in odoo_tests
    assert 'self.assertNotIn(product_a.id, products_b)' in odoo_tests
    assert 'self.assertNotIn(warehouse_a.id, warehouses_b)' in odoo_tests


def test_synthetic_inventory_cleanup_is_a_guarded_non_destructive_reset():
    script = (ROOT / "scripts/seed_odoo_demo_inventory.py").read_text(encoding="utf-8")
    report = (ROOT / "docs/qa/phase2-5-premium-dashboard.md").read_text(encoding="utf-8")

    assert 'ALLOWED_DATABASES = {"autostock_phase2_demo", "autostock_phase2_qa"}' in script
    assert 'elif action == "cleanup"' in script
    assert "does not delete QA products" in script
    assert "non-destructive reset" in report
    assert "products remain in the catalog" in report.lower()
    assert "template.unlink(" not in script


def test_inventory_action_allows_users_to_choose_untracked_products():
    actions = etree.parse(str(ADDON / "views/dashboard_actions.xml"))
    action = actions.find(".//record[@id='action_autostock_products']")
    assert action is not None
    assert action.find("field[@name='res_model']").text == "product.template"
    domain = action.find("field[@name='domain']")
    assert domain is not None and "is_storable" in domain.text
    assert "autostock_enabled" not in domain.text
