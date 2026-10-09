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


def test_inventory_action_allows_users_to_choose_untracked_products():
    actions = etree.parse(str(ADDON / "views/dashboard_actions.xml"))
    action = actions.find(".//record[@id='action_autostock_products']")
    assert action is not None
    assert action.find("field[@name='res_model']").text == "product.template"
    domain = action.find("field[@name='domain']")
    assert domain is not None and "is_storable" in domain.text
    assert "autostock_enabled" not in domain.text
