"""Read-only, company-aware data service for the first dashboard release.

No synthetic or ML-derived data is returned from this model.
"""
from odoo import api, fields, models
from odoo.exceptions import AccessError


class AutoStockDashboard(models.AbstractModel):
    _name = "autostock.dashboard"
    _description = "AutoStock Read-only Dashboard Service"

    @api.model
    def get_dashboard_data(self):
        if not self.env.user.has_group("stock.group_stock_user"):
            raise AccessError("Inventory access is required to view AutoStock AI.")

        # Avoid sudo: respect Odoo product ACLs and record rules.
        Product = self.env["product.product"].with_company(self.env.company)
        domain = [("active", "=", True), ("autostock_enabled", "=", True)]
        total_tracked = Product.search_count(domain)
        # This first version explicitly marks summary incompleteness instead of
        # silently presenting a partial sample as a complete inventory report.
        products = Product.search(domain, order="name, id", limit=5000)
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
            if len(rows) < 12:
                rows.append({
                    "id": product.id,
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
            "kpis": {"total": len(products), **counts},
            "rows": rows,
            "total_tracked": total_tracked,
            "summary_incomplete": incomplete,
            "as_of": fields.Datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
            "ai_status": "not_integrated",
        }
