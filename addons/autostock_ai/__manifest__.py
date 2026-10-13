{
    "name": "AutoStock AI — Inventory Intelligence",
    "author": "AutoStock AI",
    "version": "19.0.0.1.5",
    "summary": "Automotive inventory intelligence, reviewed forecasts, and read-only risk guidance",
    "description": """A company-aware inventory dashboard and explainable demand forecasts.

Forecast jobs use gross completed customer deliveries as demand; linked returns
are separately timestamped for audit and never revise an earlier demand value.
Synthetic demonstrations remain isolated from Odoo sales and stock transactions.
Stock-risk calculations use permission-scoped Odoo quantities and policy; reviewed,
fresh, exact-scope delivery forecasts are optional evidence. Reorder guidance is
read-only and never creates a purchase order or stock movement.
""",
    "category": "Inventory/Inventory",
    "license": "Other proprietary",
    "depends": ["stock", "web", "sale_stock"],
    "external_dependencies": {
        "python": ["numpy>=1.26,<3", "scikit-learn>=1.5,<2"]
    },
    "data": [
        "security/ir.model.access.csv",
        "security/forecast_rules.xml",
        "views/product_template_views.xml",
        "views/supplierinfo_views.xml",
        "views/forecast_configuration_views.xml",
        "views/dashboard_actions.xml",
        "views/menus.xml",
        "data/forecast_cron.xml",
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
