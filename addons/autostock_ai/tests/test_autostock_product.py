from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestAutoStockProduct(TransactionCase):
    def test_negative_safety_stock_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].create({
                "name": "Test Brake Pad", "autostock_safety_stock": -1,
            })

    def test_negative_lead_time_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].create({
                "name": "Test Oil Filter", "autostock_lead_time_days": -1,
            })

    def test_dashboard_returns_only_real_values(self):
        data = self.env["autostock.dashboard"].get_dashboard_data()
        self.assertEqual(data["ai_status"], "not_integrated")
        self.assertIn("kpis", data)
