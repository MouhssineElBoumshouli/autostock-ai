from datetime import datetime, time, timedelta
import math

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import Form
from odoo.tests.common import TransactionCase
from odoo.tools.float_utils import float_round

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

    def _replace_quantity(self, company, warehouse, product, quantity):
        scoped_product = product.with_company(company).with_context(
            allowed_company_ids=[company.id], location=warehouse.lot_stock_id.id
        )
        current = scoped_product.qty_available
        self._set_quantity(company, warehouse, product, quantity - current)

    def _two_step_warehouse(self, company):
        return self.env["stock.warehouse"].create(
            {
                "name": f"AutoStock Two Step {company.id}",
                "code": f"T{company.id:04d}"[-5:],
                "company_id": company.id,
                "delivery_steps": "pick_ship",
            }
        )

    def _orderpoint(self, company, warehouse, product, minimum, target):
        return self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": product.id,
                "location_id": warehouse.lot_stock_id.id,
                "warehouse_id": warehouse.id,
                "company_id": company.id,
                "product_min_qty": minimum,
                "product_max_qty": target,
            }
        )

    def _open_receipt(self, company, warehouse, product, quantity, day):
        picking_type = warehouse.in_type_id
        scheduled = fields.Datetime.to_string(datetime.combine(day, time(10)))
        picking = self.env["stock.picking"].with_company(company).create(
            {
                "picking_type_id": picking_type.id,
                "partner_id": self.partner.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
                "scheduled_date": scheduled,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom": product.uom_id.id,
                            "product_uom_qty": quantity,
                            "location_id": picking_type.default_location_src_id.id,
                            "location_dest_id": picking_type.default_location_dest_id.id,
                            "company_id": company.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.move_ids.write({"date": scheduled})
        return picking

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

    def _completed_delivery(self, company, warehouse, product, day, *, quantity=1):
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
        for _attempt in range(4):
            pending = order.picking_ids.filtered(
                lambda picking: picking.state not in ("done", "cancel")
            )
            if not pending:
                break
            for picking in pending:
                picking.action_assign()
                for move in picking.move_ids:
                    move.write({"quantity": move.product_uom_qty, "picked": True})
                validation = picking.button_validate()
                if isinstance(validation, dict):
                    Form.from_action(self.env, validation).save().process()
        else:
            self.fail("The completed delivery did not finish all native warehouse steps.")
        order.picking_ids.move_ids.write(
            {"date": fields.Datetime.to_string(datetime.combine(day, time(10)))}
        )
        return order.picking_ids

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

    def test_catalog_pages_filter_supplier_and_status_across_all_products_and_warehouses(self):
        company = self.env.company
        warehouse_a = self._warehouse(company)
        warehouse_b = self.env["stock.warehouse"].create(
            {
                "name": f"ZZZ AutoStock Catalog Second {company.id}",
                "code": f"C{company.id:04d}"[-5:],
                "company_id": company.id,
            }
        )
        prefix = f"AS-RISK-CATALOG-{company.id}"
        templates = self.env["product.template"].with_company(company).create(
            [
                {
                    "name": f"{prefix}-{index:03d}",
                    "default_code": f"{prefix}-{index:03d}",
                    "company_id": company.id,
                    "is_storable": True,
                    "uom_id": self.unit.id,
                    "autostock_enabled": True,
                    "autostock_safety_stock": 1 if index == 250 else 0,
                }
                for index in range(251)
            ]
        )
        target = templates[-1]
        vendor = self.env["res.partner"].create(
            {"name": "[SYNTHETIC TEST] Beyond-page supplier", "supplier_rank": 1}
        )
        self.env["product.supplierinfo"].create(
            {
                "partner_id": vendor.id,
                "product_tmpl_id": target.id,
                "company_id": company.id,
                "product_uom_id": self.unit.id,
                "delay": 7,
                "autostock_min_order_qty": 1,
            }
        )
        manager = self._user(
            company,
            ["base.group_user", "stock.group_stock_manager", "sales_team.group_sale_manager"],
            login="catalog-pagination",
        )
        service = self._service(manager, company)

        first_page = service.get_risk_data(search=prefix, risk_filter="out", offset=0)
        self.assertEqual(first_page["total_products"], 251)
        self.assertEqual(first_page["total_pairs"], 502)
        self.assertEqual(first_page["row_count"], 100)
        self.assertTrue(first_page["pagination"]["has_next"])
        self.assertEqual(first_page["pagination"]["page_count"], 6)
        self.assertEqual(first_page["pagination"]["summary_scope"], "current_page_after_supplier_and_history_filters")
        self.assertEqual(first_page["pagination"]["summary_row_count"], 100)
        self.assertEqual(first_page["summary"]["out"], 100)
        self.assertEqual(first_page["recommendation_count"], 0)
        self.assertNotIn(target.product_variant_id.default_code, {row["sku"] for row in first_page["rows"]})
        self.assertIn(vendor.id, {item["id"] for item in first_page["suppliers"]})

        status_page = service.get_risk_data(
            search=prefix, risk_filter="out", offset=200
        )
        target_row = next(
            row for row in status_page["rows"]
            if row["sku"] == target.product_variant_id.default_code
        )
        self.assertEqual(target_row["risk"], "out")
        self.assertEqual(target_row["warehouse_id"], first_page["warehouses"][0]["id"])
        self.assertEqual(target_row["recommended_qty"], 1)
        self.assertEqual(status_page["pagination"]["page_number"], 3)
        self.assertEqual(status_page["summary"]["out"], 100)
        self.assertEqual(status_page["recommendation_count"], 1)

        vendor_rows = service.get_risk_data(
            search=prefix,
            supplier_id=vendor.id,
            risk_filter="out",
            offset=0,
        )
        self.assertEqual(vendor_rows["total_products"], 1)
        self.assertEqual(vendor_rows["total_pairs"], 2)
        self.assertEqual(vendor_rows["row_count"], 2)
        self.assertEqual({row["warehouse_id"] for row in vendor_rows["rows"]}, {warehouse_a.id, warehouse_b.id})
        self.assertEqual({row["supplier"]["id"] for row in vendor_rows["rows"]}, {vendor.id})
        self.assertEqual(vendor_rows["pagination"]["summary_row_count"], 2)
        self.assertEqual(vendor_rows["summary"]["out"], 2)
        self.assertEqual(vendor_rows["recommendation_count"], 2)

        second_warehouse_page = service.get_risk_data(
            search=prefix, risk_filter="out", offset=500
        )
        second_warehouse_target = next(
            row for row in second_warehouse_page["rows"]
            if row["sku"] == target.product_variant_id.default_code
        )
        self.assertEqual(second_warehouse_target["warehouse_id"], first_page["warehouses"][1]["id"])
        self.assertFalse(second_warehouse_page["pagination"]["has_next"])

    def test_confirmed_inbound_before_and_after_supplier_receipt_date(self):
        company = self.env.company
        warehouse = self._warehouse(company)
        product_before = self._product(company, f"AS-RISK-INBOUND-BEFORE-{company.id}")
        product_after = self._product(company, f"AS-RISK-INBOUND-AFTER-{company.id}")
        self._set_quantity(company, warehouse, product_before, 2)
        self._set_quantity(company, warehouse, product_after, 2)
        self._orderpoint(company, warehouse, product_before, 5, 10)
        self._orderpoint(company, warehouse, product_after, 5, 10)
        today = fields.Date.today()
        receipt_before = self._open_receipt(
            company, warehouse, product_before, 4, today + timedelta(days=3)
        )
        receipt_after = self._open_receipt(
            company, warehouse, product_after, 4, today + timedelta(days=10)
        )
        self.assertIn(receipt_before.move_ids.state, ("confirmed", "assigned", "partially_available"))
        self.assertIn(receipt_after.move_ids.state, ("confirmed", "assigned", "partially_available"))

        manager = self._user(
            company,
            ["base.group_user", "stock.group_stock_manager", "sales_team.group_sale_manager"],
            login="inbound-projection",
        )
        result = self._service(manager, company).get_risk_data(warehouse.id)
        rows = {row["sku"]: row for row in result["rows"]}
        before = rows[product_before.default_code]
        after = rows[product_after.default_code]

        self.assertEqual(before["on_hand"], 2)
        self.assertEqual(before["incoming_at_receipt"], 4)
        self.assertEqual(before["outgoing_at_receipt"], 0)
        self.assertEqual(before["odoo_projected_at_receipt"], 6)
        self.assertEqual(before["risk"], "low")
        self.assertFalse(before["reorder_needed"])
        self.assertEqual(before["recommended_qty"], 0)

        self.assertEqual(after["on_hand"], 2)
        self.assertEqual(after["incoming_at_receipt"], 0)
        self.assertEqual(after["outgoing_at_receipt"], 0)
        self.assertEqual(after["odoo_projected_at_receipt"], 2)
        self.assertEqual(after["risk"], "shortage")
        self.assertTrue(after["reorder_needed"])
        self.assertEqual(after["target_gap"], 8)
        self.assertEqual(after["recommended_qty"], 8)

    def test_one_step_fully_and_partially_reserved_customer_deliveries(self):
        company = self.env.company
        warehouse = self._warehouse(company)
        product = self._product(company, f"AS-RISK-RESERVED-{company.id}", safety=5)
        self._set_quantity(company, warehouse, product, 6)
        today = fields.Date.today()

        fully_reserved_order = self._open_delivery(
            company, warehouse, product, 2, today + timedelta(days=5)
        )
        fully_reserved_picking = fully_reserved_order.picking_ids
        fully_reserved_picking.action_assign()
        partially_reserved_order = self._open_delivery(
            company, warehouse, product, 6, today + timedelta(days=5)
        )
        partially_reserved_picking = partially_reserved_order.picking_ids
        partially_reserved_picking.action_assign()

        fully_reserved_move = fully_reserved_picking.move_ids
        partially_reserved_move = partially_reserved_picking.move_ids
        self.assertEqual(fully_reserved_picking.picking_type_id.code, "outgoing")
        self.assertEqual(fully_reserved_move.location_dest_id.usage, "customer")
        self.assertEqual(fully_reserved_move.state, "assigned")
        self.assertEqual(fully_reserved_move.product_qty, 2)
        self.assertEqual(fully_reserved_move.quantity, 2)
        self.assertEqual(partially_reserved_move.location_dest_id.usage, "customer")
        self.assertEqual(partially_reserved_move.state, "partially_available")
        self.assertEqual(partially_reserved_move.product_qty, 6)
        self.assertEqual(partially_reserved_move.quantity, 4)

        manager = self._user(
            company,
            ["base.group_user", "stock.group_stock_manager", "sales_team.group_sale_manager"],
            login="reserved-customer-deliveries",
        )
        result = self._service(manager, company).get_risk_data(warehouse.id)
        row = next(item for item in result["rows"] if item["sku"] == product.default_code)

        auto_receipts = self.env["stock.move"].search(
            [
                ("company_id", "=", company.id),
                ("product_id", "=", product.id),
                ("state", "in", ["waiting", "confirmed", "assigned", "partially_available"]),
                ("location_id.usage", "=", "supplier"),
                ("location_dest_id", "child_of", warehouse.lot_stock_id.id),
            ]
        )
        self.assertFalse(auto_receipts)
        self.assertEqual(row["on_hand"], 6)
        self.assertEqual(row["free_qty"], 0)
        self.assertEqual(row["reserved_qty"], 6)
        self.assertEqual(row["incoming_at_receipt"], 0)
        self.assertEqual(row["outgoing_at_receipt"], 8)
        self.assertEqual(row["odoo_projected_at_receipt"], -2)
        self.assertEqual(row["committed_customer_outbound"], 8)
        self.assertFalse(row["forecast"]["used"])
        self.assertEqual(row["additional_forecast_demand"], 0)
        self.assertEqual(row["projected_after_demand"], -2)
        self.assertEqual(row["target_gap"], 7)
        self.assertEqual(row["recommended_qty"], 7)

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
        self._set_quantity(company, warehouse, product, 300)
        for offset in range(1, 112, 10):
            self._completed_delivery(
                company,
                warehouse,
                product,
                fields.Date.today() - timedelta(days=offset),
                quantity=20,
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
        warehouse.write({"delivery_steps": "pick_ship"})
        self._replace_quantity(company, warehouse, product, 6)
        fully_reserved_order = self._open_delivery(
            company,
            warehouse,
            product,
            2,
            fields.Date.today() + timedelta(days=5),
        )
        fully_reserved_picking = fully_reserved_order.picking_ids
        fully_reserved_picking.action_assign()
        partially_reserved_order = self._open_delivery(
            company,
            warehouse,
            product,
            6,
            fields.Date.today() + timedelta(days=5),
        )
        partially_reserved_picking = partially_reserved_order.picking_ids
        partially_reserved_picking.action_assign()

        fully_reserved_move = fully_reserved_picking.move_ids
        partially_reserved_move = partially_reserved_picking.move_ids
        self.assertEqual(fully_reserved_picking.picking_type_id.code, "internal")
        self.assertEqual(fully_reserved_move.location_id, warehouse.lot_stock_id)
        self.assertEqual(fully_reserved_move.location_dest_id.usage, "internal")
        self.assertEqual(fully_reserved_move.state, "assigned")
        self.assertEqual(fully_reserved_move.product_qty, 2)
        self.assertEqual(fully_reserved_move.quantity, 2)
        self.assertEqual(partially_reserved_move.location_dest_id.usage, "internal")
        self.assertEqual(partially_reserved_move.state, "partially_available")
        self.assertEqual(partially_reserved_move.product_qty, 6)
        self.assertEqual(partially_reserved_move.quantity, 4)

        snapshot = self._service(manager, company).get_risk_data(warehouse.id)
        row = next(item for item in snapshot["rows"] if item["sku"] == product.default_code)

        self.assertTrue(row["forecast"]["used"], row["forecast"]["reason"])
        self.assertEqual(row["forecast"]["status"], "reviewed_evaluated")
        forecast_demand = sum(
            point.units
            for point in run.point_ids
            if fields.Date.today() < point.day <= fields.Date.today() + timedelta(days=7)
        )
        self.assertGreater(forecast_demand, 8)
        additional_forecast = max(0, forecast_demand - 8)
        self.assertGreater(additional_forecast, 0)
        expected_at_receipt = -2 - additional_forecast
        target_gap = max(0, 30 - expected_at_receipt)
        self.assertEqual(row["on_hand"], 6)
        self.assertEqual(row["free_qty"], 0)
        self.assertEqual(row["reserved_qty"], 6)
        self.assertEqual(row["incoming_at_receipt"], 0)
        self.assertEqual(row["outgoing_at_receipt"], 8)
        self.assertEqual(row["odoo_projected_at_receipt"], -2)
        self.assertEqual(row["committed_customer_outbound"], 8)
        self.assertEqual(row["forecast_demand"], float_round(forecast_demand, precision_rounding=self.unit.rounding))
        self.assertEqual(row["additional_forecast_demand"], float_round(additional_forecast, precision_rounding=self.unit.rounding))
        self.assertEqual(row["projected_after_demand"], float_round(expected_at_receipt, precision_rounding=self.unit.rounding))
        self.assertEqual(row["target_gap"], float_round(target_gap, precision_rounding=self.unit.rounding))
        replenishment_step = product.uom_id.rounding
        expected_recommendation = math.ceil(target_gap / replenishment_step) * replenishment_step
        self.assertEqual(
            row["recommended_qty"],
            float_round(expected_recommendation, precision_rounding=replenishment_step),
        )
        self.assertEqual(row["warehouse_id"], warehouse.id)
        self.assertEqual(row["warehouse_id"], warehouse.id)
