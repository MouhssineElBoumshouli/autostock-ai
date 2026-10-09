from datetime import datetime, time, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import Form
from odoo.tests.common import TransactionCase

from odoo.addons.autostock_ai.models.forecast import REAL_SOURCE


class TestAutoStockInventoryRisk(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.dozen = cls.env.ref("uom.product_uom_dozen")
        cls.partner = cls.env["res.partner"].create(
            {"name": "[SYNTHETIC TEST] Automotive Customer", "company_type": "company"}
        )

    def _warehouse(self, company):
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", company.id)], limit=1
        )
        if not warehouse:
            warehouse = self.env["stock.warehouse"].create(
                {
                    "name": f"AutoStock Risk {company.name}",
                    "code": f"R{company.id:04d}"[-5:],
                    "company_id": company.id,
                }
            )
        return warehouse

    def _product(self, company, sku, *, safety=0, shared=False):
        template = self.env["product.template"].with_company(company).create(
            {
                "name": sku,
                "default_code": sku,
                "company_id": False if shared else company.id,
                "is_storable": True,
                "uom_id": self.unit.id,
                "autostock_enabled": True,
                "autostock_safety_stock": safety,
                "autostock_lead_time_days": 7,
            }
        )
        return template.product_variant_id

    def _set_quantity(self, company, warehouse, product, quantity):
        self.env["stock.quant"].with_company(company)._update_available_quantity(
            product, warehouse.lot_stock_id, quantity
        )

    def _user(self, company, groups, *, allowed_companies=None, login="risk-user"):
        companies = allowed_companies or [company]
        return self.env["res.users"].create(
            {
                "name": f"AutoStock {login}",
                "login": f"{login}-{company.id}-{self.cr.dbname}",
                "company_id": company.id,
                "company_ids": [Command.set([item.id for item in companies])],
                "group_ids": [Command.set([self.env.ref(group).id for group in groups])],
            }
        )

    def _service(self, user, company):
        return (
            self.env["autostock.inventory.risk"]
            .with_user(user)
            .with_company(company)
            .with_context(allowed_company_ids=[company.id])
        )

    def _completed_delivery(self, company, warehouse, product, day):
        order = self.env["sale.order"].with_company(company).create(
            {
                "company_id": company.id,
                "partner_id": self.partner.id,
                "partner_invoice_id": self.partner.id,
                "partner_shipping_id": self.partner.id,
                "warehouse_id": warehouse.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "product_uom_id": product.uom_id.id,
                            "price_unit": 1.0,
                        }
                    )
                ],
            }
        )
        order.action_confirm()
        picking = order.picking_ids
        picking.move_ids.write({"quantity": 1, "picked": True})
        validation = picking.button_validate()
        if isinstance(validation, dict):
            Form.from_action(self.env, validation).save().process()
        picking.move_ids.write(
            {"date": fields.Datetime.to_string(datetime.combine(day, time(10)))}
        )
        return picking

    def _open_delivery(self, company, warehouse, product, quantity, day):
        order = self.env["sale.order"].with_company(company).create(
            {
                "company_id": company.id,
                "partner_id": self.partner.id,
                "partner_invoice_id": self.partner.id,
                "partner_shipping_id": self.partner.id,
                "warehouse_id": warehouse.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": quantity,
                            "product_uom_id": product.uom_id.id,
                            "price_unit": 1.0,
                        }
                    )
                ],
            }
        )
        order.action_confirm()
        order.picking_ids.move_ids.write(
            {"date": fields.Datetime.to_string(datetime.combine(day, time(10)))}
        )
        return order

    def test_inventory_permission_is_required(self):
        user = self._user(self.env.company, ["base.group_user"], login="no-stock")
        with self.assertRaises(AccessError):
            self._service(user, self.env.company).get_risk_data()

    def test_company_and_warehouse_scope_keeps_shared_stock_separate(self):
        company_a, company_b = self.env["res.company"].create(
            [{"name": "AutoStock Risk A"}, {"name": "AutoStock Risk B"}]
        )
        warehouse_a = self._warehouse(company_a)
        warehouse_a_second = self.env["stock.warehouse"].create(
            {
                "name": f"AutoStock Risk A Second {company_a.id}",
                "code": f"S{company_a.id:04d}"[-5:],
                "company_id": company_a.id,
            }
        )
        warehouse_b = self._warehouse(company_b)
        product_a = self._product(company_a, f"AS-RISK-A-{company_a.id}", safety=4)
        product_b = self._product(company_b, f"AS-RISK-B-{company_b.id}", safety=4)
        shared = self._product(company_a, f"AS-RISK-SHARED-{company_a.id}", safety=4, shared=True)
        self._set_quantity(company_a, warehouse_a, product_a, 2)
        self._set_quantity(company_b, warehouse_b, product_b, 17)
        self._set_quantity(company_a, warehouse_a, shared, 3)
        self._set_quantity(company_a, warehouse_a_second, shared, 11)
        self._set_quantity(company_b, warehouse_b, shared, 22)
        user = self._user(
            company_a,
            ["base.group_user", "stock.group_stock_user"],
            allowed_companies=[company_a, company_b],
            login="multi-company",
        )

        snapshot_a = self._service(user, company_a).get_risk_data(warehouse_a.id)
        snapshot_a_second = self._service(user, company_a).get_risk_data(warehouse_a_second.id)
        snapshot_b = self._service(user, company_b).get_risk_data(warehouse_b.id)
        rows_a = {row["sku"]: row for row in snapshot_a["rows"]}
        rows_a_second = {row["sku"]: row for row in snapshot_a_second["rows"]}
        rows_b = {row["sku"]: row for row in snapshot_b["rows"]}

        self.assertIn(product_a.default_code, rows_a)
        self.assertNotIn(product_b.default_code, rows_a)
        self.assertNotIn(product_a.default_code, rows_b)
        self.assertIn(product_b.default_code, rows_b)
        self.assertEqual(rows_a[shared.default_code]["on_hand"], 3)
        self.assertEqual(rows_a_second[shared.default_code]["on_hand"], 11)
        self.assertEqual(rows_a_second[product_a.default_code]["on_hand"], 0)
        self.assertEqual(rows_b[shared.default_code]["on_hand"], 22)
        self.assertTrue(all(row["warehouse_id"] == warehouse_a.id for row in rows_a.values()))
        self.assertTrue(all(row["warehouse_id"] == warehouse_a_second.id for row in rows_a_second.values()))
        self.assertTrue(all(row["warehouse_id"] == warehouse_b.id for row in rows_b.values()))

    def test_supplier_moq_is_distinct_from_price_break_and_native_pack_multiple(self):
        company = self.env.company
        warehouse = self._warehouse(company)
        product = self._product(company, f"AS-RISK-MOQ-{company.id}")
        self._set_quantity(company, warehouse, product, 4)
        vendor = self.env["res.partner"].create(
            {"name": "[SYNTHETIC TEST] Parts Supplier", "supplier_rank": 1}
        )
        self.env["product.supplierinfo"].create(
            {
                "partner_id": vendor.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "company_id": company.id,
                "product_uom_id": self.dozen.id,
                "min_qty": 100,  # Odoo's native field is a price-tier threshold.
                "price": 10,
                "delay": 10,
                "autostock_min_order_qty": 1,
            }
        )
        self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": product.id,
                "location_id": warehouse.lot_stock_id.id,
                "warehouse_id": warehouse.id,
                "company_id": company.id,
                "product_min_qty": 5,
                "product_max_qty": 10,
                "replenishment_uom_id": self.dozen.id,
            }
        )
        user = self._user(
            company,
            ["base.group_user", "stock.group_stock_user", "stock.group_stock_manager"],
            login="supplier-terms",
        )
        before = product.qty_available

        result = self._service(user, company).get_risk_data(warehouse.id)
        row = next(item for item in result["rows"] if item["sku"] == product.default_code)

        self.assertEqual(row["supplier"]["minimum_qty"], 1)
        self.assertEqual(row["supplier"]["minimum_uom"], self.dozen.display_name)
        self.assertEqual(row["supplier"]["price_tier_min_qty"], 100)
        self.assertEqual(row["supplier_minimum_product_qty"], 12)
        self.assertEqual(row["pack_multiple_product_qty"], 12)
        self.assertEqual(row["target_gap"], 6)
        self.assertEqual(row["lead_time_days"], 10)
        self.assertEqual(row["policy_source"], "odoo_reordering_rule")
        self.assertEqual(row["recommended_qty"], 12)
        self.assertEqual(product.qty_available, before)
        self.assertTrue(result["read_only"])

    def test_inventory_only_user_gets_truthful_odoo_policy_fallback(self):
        company = self.env.company
        warehouse = self._warehouse(company)
        product = self._product(company, f"AS-RISK-BASELINE-{company.id}", safety=6)
        self._set_quantity(company, warehouse, product, 2)
        user = self._user(
            company,
            ["base.group_user", "stock.group_stock_user"],
            login="inventory-only",
        )

        result = self._service(user, company).get_risk_data(warehouse.id)
        row = next(item for item in result["rows"] if item["sku"] == product.default_code)

        self.assertFalse(result["sales_access"])
        self.assertFalse(row["forecast"]["used"])
        self.assertEqual(row["calculation_basis"], "odoo_policy_baseline")
        self.assertEqual(row["recommended_qty"], 4)
        self.assertIn("Sales access", row["forecast"]["reason"])

    def test_sales_user_without_forecast_gets_explained_policy_fallback(self):
        company = self.env.company
        warehouse = self._warehouse(company)
        product = self._product(company, f"AS-RISK-NO-FORECAST-{company.id}", safety=8)
        self._set_quantity(company, warehouse, product, 2)
        user = self._user(
            company,
            ["base.group_user", "stock.group_stock_user", "sales_team.group_sale_manager"],
            login="no-reviewed-forecast",
        )

        result = self._service(user, company).get_risk_data(warehouse.id)
        row = next(item for item in result["rows"] if item["sku"] == product.default_code)

        self.assertTrue(result["forecast_access_available"])
        self.assertFalse(row["forecast"]["used"])
        self.assertIn("No completed real delivery forecast", row["forecast"]["reason"])
        self.assertEqual(row["calculation_basis"], "odoo_policy_baseline")
        self.assertEqual(row["recommended_qty"], 6)

    def test_fresh_reviewed_real_forecast_is_used_for_matching_warehouse(self):
        company = self.env.company
        warehouse = self._warehouse(company)
        start = fields.Date.today() - timedelta(days=119)
        company.write({"autostock_history_complete_from": start})
        warehouse.write({"autostock_history_complete_from": start})
        product = self._product(company, f"AS-RISK-FORECAST-{company.id}", safety=30)
        product.write(
            {"create_date": fields.Datetime.to_string(datetime.combine(start, time.min))}
        )
        self._set_quantity(company, warehouse, product, 25)
        for offset in (8, 18, 28, 38, 48, 58, 68):
            self._completed_delivery(
                company, warehouse, product, fields.Date.today() - timedelta(days=offset)
            )

        groups = [
            "base.group_user",
            "stock.group_stock_manager",
            "sales_team.group_sale_manager",
        ]
        manager = self._user(company, groups, login="reviewed-forecast")
        Forecast = (
            self.env["autostock.forecast.run"]
            .with_user(manager)
            .with_company(company)
            .with_context(allowed_company_ids=[company.id])
        )
        queued = Forecast.request_forecast(product.id, 30, start, fields.Date.today(), warehouse.id)
        run = self.env["autostock.forecast.run"].browse(queued["id"])
        run._process_queued_run()
        run.invalidate_recordset()
        self.assertEqual(run.source_type, REAL_SOURCE)
        self.assertEqual(run.state, "completed", run.failure_reason)
        self.assertEqual(run.evaluation_days, 30)
        run.with_user(manager).action_mark_reviewed()
        self._open_delivery(
            company,
            warehouse,
            product,
            3,
            fields.Date.today() + timedelta(days=5),
        )

        snapshot = self._service(manager, company).get_risk_data(warehouse.id)
        row = next(item for item in snapshot["rows"] if item["sku"] == product.default_code)

        self.assertTrue(row["forecast"]["used"], row["forecast"]["reason"])
        self.assertEqual(row["forecast"]["status"], "reviewed_evaluated")
        self.assertGreaterEqual(row["forecast_demand"], 0)
        self.assertIn(row["calculation_basis"], {"odoo_plus_reviewed_forecast", "odoo_policy_baseline"})
        self.assertGreaterEqual(row["committed_customer_outbound"], 3)
        self.assertEqual(
            row["additional_forecast_demand"],
            max(0, row["forecast_demand"] - row["committed_customer_outbound"]),
        )
        self.assertEqual(
            row["projected_after_demand"],
            row["odoo_projected_at_receipt"] - row["additional_forecast_demand"],
        )
        self.assertEqual(row["warehouse_id"], warehouse.id)
