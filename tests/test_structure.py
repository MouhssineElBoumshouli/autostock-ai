import ast
from pathlib import Path
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "addons" / "autostock_ai"


def test_odoo_manifests_and_views_well_formed():
    manifest = ast.literal_eval(ast.parse((ADDON / "__manifest__.py").read_text()).body[0].value)
    assert manifest["version"].startswith("19.0.")
    assert {"stock", "web"}.issubset(manifest["depends"])
    for file in list(ADDON.rglob("*.xml")):
        assert etree.parse(str(file)).getroot().tag in {"odoo", "templates"}
    for filename in manifest["data"]:
        assert (ADDON / filename).exists()
    for asset in manifest["assets"]["web.assets_backend"]:
        assert (ROOT / "addons" / asset).exists()


def test_dashboard_never_shows_fake_ai_accuracy():
    xml = (ADDON / "static/src/dashboard/dashboard.xml").read_text()
    assert "Predictions aren't connected yet" in xml
    assert "AutoStock AI" in xml
