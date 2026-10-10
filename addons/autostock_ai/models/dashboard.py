"""Read-only, company-aware data service for the first dashboard release.

No synthetic or ML-derived data is returned from this model.
"""
from odoo import api, fields, models
from odoo.exceptions import AccessError

MAX_TRACKED_PRODUCTS = 5000
DASHBOARD_TABLE_LIMIT = 12


class AutoStockDashboard(models.AbstractModel):
    _name = "autostock.dashboard"
    _description = "AutoStock Read-only Dashboard Service"

    @api.model
    def get_dashboard_data(self):
        if not self.env.user.has_group("stock.group_stock_user"):
            raise AccessError("Inventory access is required to view AutoStock AI.")

        # Avoid sudo: respect Odoo product ACLs and record rules. with_company
        # moves the active company first but preserves every allowed company,
        # so narrow the context before searching or computing stock quantities.
        company = self.env.company
        Product = (
            self.env["product.product"]
            .with_company(company)
            .with_context(allowed_company_ids=[company.id])
        )
        domain = [
            ("active", "=", True),
            ("is_storable", "=", True),
            ("autostock_enabled", "=", True),
            ("company_id", "in", [False, company.id]),
        ]
        total_tracked = Product.search_count(domain)
        # This first version explicitly marks summary incompleteness instead of
        # silently presenting a partial sample as a complete inventory report.
        products = Product.search(domain, order="name, id", limit=MAX_TRACKED_PRODUCTS)
        incomplete = total_tracked > len(products)
        counts = {"healthy": 0, "low": 0, "out": 0}
        rows = []
        for product in products:
            on_hand = product.qty_available
            forecasted_stock = product.virtual_available
            threshold = product.autostock_safety_stock
            if on_hand <= 0:
                status = "out"
            elif threshold > 0 and on_hand <= threshold:
                status = "low"
            else:
                status = "healthy"
            counts[status] += 1
            if len(rows) < DASHBOARD_TABLE_LIMIT:
                rows.append({
                    "id": product.id,
                    "template_id": product.product_tmpl_id.id,
                    "name": product.display_name,
                    "sku": product.default_code or "—",
                    "reference": product.autostock_oem_reference or "—",
                    "on_hand": round(on_hand, 2),
                    "odoo_projected": round(forecasted_stock, 2),
                    "status": status,
                    "status_label": {
                        "out": "Out of stock",
                        "low": "Low stock",
                        "healthy": "In stock",
                    }[status],
                })

        return {
            "company_id": company.id,
            "company_name": company.display_name,
            "demo_environment": bool(company.autostock_demo_environment),
            "kpis": {"total": len(products), **counts},
            "rows": rows,
            "total_tracked": total_tracked,
            "summary_incomplete": incomplete,
            "as_of": fields.Datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
            "ai_status": "not_integrated",
        }
