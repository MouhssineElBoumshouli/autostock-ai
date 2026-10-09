{
    "name": "AutoStock AI — Inventory Intelligence",
    "version": "19.0.0.1.0",
    "summary": "Automotive inventory intelligence foundation for Odoo",
    "description": """A secure inventory dashboard and automotive parts metadata.

This foundation does not claim to have integrated AI predictions yet.
""",
    "category": "Inventory/Inventory",
    "license": "Other proprietary",
    "depends": ["stock", "web"],
    "data": [
        "views/product_template_views.xml",
        "views/dashboard_actions.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "autostock_ai/static/src/dashboard/dashboard.js",
            "autostock_ai/static/src/dashboard/dashboard.xml",
            "autostock_ai/static/src/dashboard/dashboard.scss",
        ],
    },
    "application": True,
    "installable": True,
}
