from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase
from unittest.mock import patch


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

    def test_non_storable_product_cannot_be_tracked(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].create({
                "name": "AutoStock Test Service",
                "type": "service",
                "autostock_enabled": True,
            })

    def test_dashboard_empty_state_data(self):
        data = self.env["autostock.dashboard"].get_dashboard_data()
        self.assertEqual(data["kpis"], {"total": 0, "healthy": 0, "low": 0, "out": 0})
        self.assertEqual(data["rows"], [])
        self.assertEqual(data["ai_status"], "not_integrated")

    def test_dashboard_stock_statuses_use_on_hand_and_manual_threshold(self):
        templates = self.env["product.template"].create([
            {"name": "AutoStock Test 01 Out", "is_storable": True, "autostock_enabled": True,
             "autostock_safety_stock": 3},
            {"name": "AutoStock Test 02 Low", "is_storable": True, "autostock_enabled": True,
             "autostock_safety_stock": 3},
            {"name": "AutoStock Test 03 Healthy", "is_storable": True, "autostock_enabled": True,
             "autostock_safety_stock": 3},
        ])
        out_product, low_product, healthy_product = templates.product_variant_id
        stock_location = self.env.ref("stock.stock_location_stock")
        self.env["stock.quant"]._update_available_quantity(low_product, stock_location, 2)
        self.env["stock.quant"]._update_available_quantity(healthy_product, stock_location, 5)

        data = self.env["autostock.dashboard"].get_dashboard_data()
        rows = {row["id"]: row for row in data["rows"]}
        self.assertEqual(data["kpis"]["total"], 3)
        self.assertEqual(data["kpis"]["out"], 1)
        self.assertEqual(data["kpis"]["low"], 1)
        self.assertEqual(data["kpis"]["healthy"], 1)
        self.assertEqual(rows[out_product.id]["status"], "out")
        self.assertEqual(rows[low_product.id]["status"], "low")
        self.assertEqual(rows[healthy_product.id]["status"], "healthy")
        self.assertEqual(rows[low_product.id]["on_hand"], 2)

    def test_dashboard_one_product_reads_current_stock(self):
        template = self.env["product.template"].create({
            "name": "AutoStock Test Single Product",
            "is_storable": True,
            "autostock_enabled": True,
            "autostock_safety_stock": 2,
        })
        product = template.product_variant_id
        self.env["stock.quant"]._update_available_quantity(
            product, self.env.ref("stock.stock_location_stock"), 7
        )

        data = self.env["autostock.dashboard"].get_dashboard_data()
        self.assertEqual(data["kpis"]["total"], 1)
        self.assertEqual(data["kpis"]["healthy"], 1)
        self.assertEqual(data["rows"][0]["id"], product.id)
        self.assertEqual(data["rows"][0]["on_hand"], 7)

    def test_dashboard_sample_cap_marks_large_catalog_incomplete(self):
        self.env["product.template"].create([
            {"name": f"AutoStock Test Sample {index:02d}", "is_storable": True,
             "autostock_enabled": True}
            for index in range(5)
        ])
        with patch("odoo.addons.autostock_ai.models.dashboard.MAX_TRACKED_PRODUCTS", 3):
            data = self.env["autostock.dashboard"].get_dashboard_data()
        self.assertEqual(data["total_tracked"], 5)
        self.assertTrue(data["summary_incomplete"])
        self.assertEqual(data["kpis"]["total"], 3)
        self.assertEqual(len(data["rows"]), 3)

    def test_dashboard_table_preview_is_capped_for_large_catalog(self):
        self.env["product.template"].create([
            {"name": f"AutoStock Test Preview {index:02d}", "is_storable": True,
             "autostock_enabled": True}
            for index in range(13)
        ])
        data = self.env["autostock.dashboard"].get_dashboard_data()
        self.assertEqual(data["kpis"]["total"], 13)
        self.assertEqual(len(data["rows"]), 12)

    def test_dashboard_rejects_user_without_inventory_group(self):
        user = self.env["res.users"].create({
            "name": "AutoStock no inventory test",
            "login": "autostock-no-inventory-test",
            "group_ids": [Command.set([self.env.ref("base.group_user").id])],
        })
        with self.assertRaises(AccessError):
            self.env["autostock.dashboard"].with_user(user).get_dashboard_data()
