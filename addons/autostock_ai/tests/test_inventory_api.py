from datetime import timedelta
import secrets

from odoo import Command, fields
from odoo.tests import Form, tagged
from odoo.tests.common import HttpCase


@tagged("post_install", "-at_install")
class TestAutoStockInventoryApi(HttpCase):
    def setUp(self):
        super().setUp()
        self.test_password = secrets.token_urlsafe(24)
        admin = self.env.ref("base.user_admin")
        admin.write({"password": self.test_password})
        self.authenticate(admin.login, self.test_password)

    def _get_json(self, path, expected_status=200):
        response = self.url_open(path, allow_redirects=False)
        self.assertEqual(response.status_code, expected_status, response.text[:500])
        self.assertIn("application/json", response.headers.get("Content-Type", ""))
        return response.json()

    def _warehouse(self, company):
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", company.id)], limit=1
        )
        if not warehouse:
            warehouse = self.env["stock.warehouse"].create(
                {
                    "name": f"AutoStock Inventory {company.name}",
                    "code": f"I{company.id:04d}"[-5:],
                    "company_id": company.id,
                }
            )
        return warehouse

    def test_catalog_filters_and_server_pagination_reach_product_1001(self):
        company = self.env.company
        category = self.env["product.category"].create(
            {"name": "Gate 4 Catalog Test Category"}
        )
        templates = self.env["product.template"].create(
            [
                {
                    "name": f"Gate4 Catalog Part {index:04d}",
                    "default_code": f"G4-LARGE-{index:04d}",
                    "company_id": company.id,
                    "categ_id": category.id,
                    "is_storable": True,
                }
                for index in range(1001)
            ]
        )
        final_template = templates[-1]
        final_template.write(
            {
                "autostock_enabled": True,
                "autostock_safety_stock": 4,
                "autostock_oem_reference": "G4-OEM-1001",
            }
        )
        product = final_template.product_variant_id
        warehouse = self._warehouse(company)
        self.env["stock.quant"].with_company(company)._update_available_quantity(
            product, warehouse.lot_stock_id, 2
        )
        supplier = self.env["res.partner"].create(
            {
                "name": "Gate4 Needle Supplier",
                "company_type": "company",
                "supplier_rank": 1,
            }
        )
        self.env["product.supplierinfo"].create(
            {
                "partner_id": supplier.id,
                "product_tmpl_id": final_template.id,
                "company_id": company.id,
                "delay": 12,
                "autostock_min_order_qty": 1,
                "price": 10,
                "currency_id": company.currency_id.id,
            }
        )

        first_page = self._get_json(
            "/autostock/api/v1/inventory?q=Gate4%20Catalog%20Part&page=1&page_size=25"
        )
        middle_page = self._get_json(
            "/autostock/api/v1/inventory?q=Gate4%20Catalog%20Part&page=21&page_size=50"
        )
        last_page = self._get_json(
            "/autostock/api/v1/inventory?q=Gate4%20Catalog%20Part&page=41&page_size=25"
        )

        self.assertEqual(first_page["pagination"]["total_count"], 1001)
        self.assertEqual(len(first_page["items"]), 25)
        self.assertEqual(middle_page["pagination"]["page"], 21)
        self.assertEqual(len(middle_page["items"]), 1)
        self.assertEqual(last_page["pagination"]["total_count"], 1001)
        self.assertEqual(last_page["pagination"]["page"], 41)
        self.assertEqual(len(last_page["items"]), 1)
        self.assertEqual(last_page["items"][0]["product_id"], product.id)

        sku_search = self._get_json(
            "/autostock/api/v1/inventory?q=G4-LARGE-1000"
        )
        self.assertEqual(sku_search["pagination"]["total_count"], 1)
        self.assertEqual(sku_search["items"][0]["product_id"], product.id)

        supplier_name_search = self._get_json(
            "/autostock/api/v1/inventory?q=Gate4%20Needle%20Supplier"
        )
        self.assertEqual(supplier_name_search["pagination"]["total_count"], 1)
        self.assertEqual(
            supplier_name_search["items"][0]["product_id"], product.id
        )

        supplier_filtered = self._get_json(
            "/autostock/api/v1/inventory?supplier_q=Gate4%20Needle%20Supplier"
        )
        self.assertEqual(supplier_filtered["pagination"]["total_count"], 1)
        self.assertEqual(supplier_filtered["items"][0]["product_id"], product.id)

        sorted_page = self._get_json(
            "/autostock/api/v1/inventory?q=Gate4%20Catalog%20Part"
            "&sort=sku&direction=desc&page_size=3"
        )
        self.assertEqual(
            [item["sku"] for item in sorted_page["items"]],
            ["G4-LARGE-1000", "G4-LARGE-0999", "G4-LARGE-0998"],
        )

        exact_search = self._get_json(
            "/autostock/api/v1/inventory?q=G4-OEM-1001&category_id="
            f"{category.id}&warehouse_id={warehouse.id}&status=low_stock"
        )
        self.assertEqual(exact_search["pagination"]["total_count"], 1)
        item = exact_search["items"][0]
        self.assertEqual(item["product_id"], product.id)
        self.assertEqual(item["status"], "low_stock")
        self.assertEqual(item["on_hand"], 2)
        self.assertEqual(item["available"], 2)
        self.assertEqual(item["supplier"]["name"], supplier.display_name)

        options = self._get_json(
            "/autostock/api/v1/inventory/options?supplier_q=Gate4%20Needle"
        )
        self.assertTrue(options["supplier_access"])
        self.assertIn(supplier.id, [row["id"] for row in options["suppliers"]])

        detail = self._get_json(
            f"/autostock/api/v1/products/{product.id}/inventory-detail"
            f"?warehouse_id={warehouse.id}"
        )
        self.assertTrue(detail["read_only"])
        self.assertEqual(detail["company_stock"]["on_hand"], 2)
        self.assertEqual(detail["warehouses"][0]["on_hand"], 2)
        self.assertEqual(detail["supplier"]["lead_time_days"], 12)
        self.assertIn("movements_available", detail)
        self.assertIsInstance(detail["movements"], list)

        warehouse_inventory = self._get_json(
            f"/autostock/api/v1/warehouses/{warehouse.id}/inventory"
            "?q=G4-LARGE-1000&page=1&page_size=10"
        )
        self.assertEqual(warehouse_inventory["pagination"]["total_count"], 1)
        self.assertEqual(warehouse_inventory["filters"]["warehouse_id"], warehouse.id)
        self.assertEqual(warehouse_inventory["items"][0]["product_id"], product.id)
        self.assertEqual(warehouse_inventory["items"][0]["on_hand"], 2)

        large_warehouse_page = self._get_json(
            f"/autostock/api/v1/warehouses/{warehouse.id}/inventory"
            "?q=Gate4%20Catalog%20Part&page=41&page_size=25"
        )
        self.assertEqual(large_warehouse_page["pagination"]["total_count"], 1001)
        self.assertEqual(large_warehouse_page["pagination"]["page"], 41)
        self.assertEqual(len(large_warehouse_page["items"]), 1)
        self.assertEqual(large_warehouse_page["items"][0]["product_id"], product.id)
        warehouse_detail = self._get_json(
            f"/autostock/api/v1/warehouses/{warehouse.id}"
        )
        self.assertGreaterEqual(warehouse_detail["summary"]["catalog_parts"], 1001)
        self.assertTrue(warehouse_detail["read_only"])
        first_warehouse_page = self._get_json(
            f"/autostock/api/v1/warehouses/{warehouse.id}/inventory"
            "?q=Gate4%20Catalog%20Part&page=1&page_size=25"
        )
        self.assertEqual(first_warehouse_page["pagination"]["total_count"], 1001)
        self.assertEqual(len(first_warehouse_page["items"]), 25)
        sorted_warehouse_page = self._get_json(
            f"/autostock/api/v1/warehouses/{warehouse.id}/inventory"
            "?q=Gate4%20Catalog%20Part&sort=sku&direction=desc&page_size=3"
        )
        self.assertEqual(
            [row["sku"] for row in sorted_warehouse_page["items"]],
            ["G4-LARGE-1000", "G4-LARGE-0999", "G4-LARGE-0998"],
        )

    def test_inventory_company_and_warehouse_scopes_preserve_isolation(self):
        company_a, company_b = self.env["res.company"].create(
            [{"name": "AutoStock Gate 4 A"}, {"name": "AutoStock Gate 4 B"}]
        )
        warehouse_a = self._warehouse(company_a)
        warehouse_a_second = self.env["stock.warehouse"].create(
            {
                "name": "AutoStock Gate 5 A Secondary",
                "code": "G5A2",
                "company_id": company_a.id,
            }
        )
        warehouse_b = self._warehouse(company_b)
        unit = self.env.ref("uom.product_uom_unit")

        def create_product(name, sku, company):
            template = self.env["product.template"].with_company(company).create(
                {
                    "name": name,
                    "default_code": sku,
                    "company_id": company.id,
                    "is_storable": True,
                    "uom_id": unit.id,
                }
            )
            template.write(
                {"autostock_enabled": True, "autostock_safety_stock": 5}
            )
            return template.product_variant_id

        product_a = create_product("Gate4 A Filter", "G4-A-001", company_a)
        product_b = create_product("Gate4 B Filter", "G4-B-001", company_b)
        shared = create_product("Gate4 Shared Filter", "G4-SHARED-001", company_a)
        shared.product_tmpl_id.company_id = False
        child_location = self.env["stock.location"].with_company(company_a).create(
            {
                "name": "Gate 5 child pick face",
                "location_id": warehouse_a.lot_stock_id.id,
                "usage": "internal",
                "company_id": company_a.id,
            }
        )
        quant = self.env["stock.quant"]
        quant.with_company(company_a)._update_available_quantity(
            product_a, child_location, 4
        )
        quant.with_company(company_b)._update_available_quantity(
            product_b, warehouse_b.lot_stock_id, 9
        )
        quant.with_company(company_a)._update_available_quantity(
            shared, child_location, 3
        )
        quant.with_company(company_a)._update_available_quantity(
            shared, warehouse_a_second.lot_stock_id, 8
        )
        quant.with_company(company_b)._update_available_quantity(
            shared, warehouse_b.lot_stock_id, 14
        )

        user = self.env["res.users"].create(
            {
                "name": "AutoStock Gate 4 Multi-company User",
                "login": "autostock-gate4-multi-company",
                "company_id": company_a.id,
                "company_ids": [Command.set([company_a.id, company_b.id])],
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("stock.group_stock_user").id,
                        ]
                    )
                ],
            }
        )
        user.write({"password": self.test_password})
        self.authenticate(user.login, self.test_password)

        page_a = self._get_json(
            f"/autostock/api/v1/inventory?company_id={company_a.id}"
        )
        page_b = self._get_json(
            f"/autostock/api/v1/inventory?company_id={company_b.id}"
        )
        rows_a = {item["sku"]: item for item in page_a["items"]}
        rows_b = {item["sku"]: item for item in page_b["items"]}
        self.assertIn(product_a.default_code, rows_a)
        self.assertIn(shared.default_code, rows_a)
        self.assertNotIn(product_b.default_code, rows_a)
        self.assertIn(product_b.default_code, rows_b)
        self.assertIn(shared.default_code, rows_b)
        self.assertNotIn(product_a.default_code, rows_b)
        self.assertEqual(rows_a[shared.default_code]["on_hand"], 11)
        self.assertEqual(rows_b[shared.default_code]["on_hand"], 14)
        self.assertTrue(
            all(
                row["id"] != warehouse_b.id
                for item in rows_a.values()
                for row in item["warehouses"]
            )
        )
        self.assertTrue(
            all(
                row["id"] != warehouse_a.id
                for item in rows_b.values()
                for row in item["warehouses"]
            )
        )

        scoped_a = self._get_json(
            f"/autostock/api/v1/inventory?company_id={company_a.id}"
            f"&warehouse_id={warehouse_a.id}"
        )
        self.assertEqual(scoped_a["items"][0]["warehouse_count"], 1)
        self.assertEqual(scoped_a["items"][0]["warehouses"][0]["id"], warehouse_a.id)

        warehouse_page_a = self._get_json(
            f"/autostock/api/v1/warehouses?company_id={company_a.id}"
        )
        visible_warehouse_ids = {row["id"] for row in warehouse_page_a["warehouses"]}
        self.assertIn(warehouse_a.id, visible_warehouse_ids)
        self.assertIn(warehouse_a_second.id, visible_warehouse_ids)
        self.assertNotIn(warehouse_b.id, visible_warehouse_ids)
        warehouse_page_b = self._get_json(
            f"/autostock/api/v1/warehouses?company_id={company_b.id}"
        )
        visible_warehouse_ids_b = {row["id"] for row in warehouse_page_b["warehouses"]}
        self.assertIn(warehouse_b.id, visible_warehouse_ids_b)
        self.assertNotIn(warehouse_a.id, visible_warehouse_ids_b)
        self.assertNotIn(warehouse_a_second.id, visible_warehouse_ids_b)
        searched_warehouse = self._get_json(
            f"/autostock/api/v1/warehouses?company_id={company_a.id}&q=G5A2"
        )
        self.assertEqual(searched_warehouse["pagination"]["total_count"], 1)
        self.assertEqual(searched_warehouse["warehouses"][0]["id"], warehouse_a_second.id)
        sorted_warehouses = self._get_json(
            f"/autostock/api/v1/warehouses?company_id={company_a.id}"
            "&sort=name&direction=desc&page_size=1"
        )
        self.assertEqual(sorted_warehouses["pagination"]["total_count"], 2)
        self.assertEqual(sorted_warehouses["pagination"]["page_size"], 1)
        self.assertEqual(sorted_warehouses["warehouses"][0]["id"], warehouse_a_second.id)

        warehouse_a_detail = self._get_json(
            f"/autostock/api/v1/warehouses/{warehouse_a.id}?company_id={company_a.id}"
        )
        self.assertGreaterEqual(warehouse_a_detail["summary"]["low_stock_parts"], 1)
        self.assertIn(
            product_a.id,
            [part["product_id"] for part in warehouse_a_detail["attention_parts"]],
        )
        self.assertNotIn(
            product_b.default_code,
            [move["sku"] for move in warehouse_a_detail["activity"]],
        )
        warehouse_a_stock = self._get_json(
            f"/autostock/api/v1/warehouses/{warehouse_a.id}/inventory"
            f"?company_id={company_a.id}&q=G4-A-001"
        )
        self.assertEqual(warehouse_a_stock["pagination"]["total_count"], 1)
        self.assertEqual(warehouse_a_stock["items"][0]["on_hand"], 4)
        self.assertEqual(warehouse_a_stock["items"][0]["available"], 4)
        self.assertEqual(warehouse_a_stock["filters"]["warehouse_id"], warehouse_a.id)

        shared_stock_a = self._get_json(
            f"/autostock/api/v1/warehouses/{warehouse_a.id}/inventory"
            f"?company_id={company_a.id}&q=G4-SHARED-001"
        )
        shared_stock_b = self._get_json(
            f"/autostock/api/v1/warehouses/{warehouse_b.id}/inventory"
            f"?company_id={company_b.id}&q=G4-SHARED-001"
        )
        self.assertEqual(shared_stock_a["items"][0]["on_hand"], 3)
        self.assertEqual(shared_stock_b["items"][0]["on_hand"], 14)
        self.assertEqual(
            self._get_json(
                f"/autostock/api/v1/warehouses/{warehouse_a_second.id}/inventory"
                f"?company_id={company_a.id}&q=G4-SHARED-001"
            )["items"][0]["on_hand"],
            8,
        )
        denied_cross_company_warehouse = self._get_json(
            f"/autostock/api/v1/warehouses/{warehouse_b.id}?company_id={company_a.id}",
            expected_status=403,
        )
        self.assertEqual(denied_cross_company_warehouse["error"]["code"], "forbidden")

    def test_inventory_routes_keep_the_odoo_inventory_access_gate(self):
        user = self.env["res.users"].create(
            {
                "name": "AutoStock Gate 4 User Without Inventory",
                "login": "autostock-gate4-no-stock",
                "company_id": self.env.company.id,
                "company_ids": [Command.set([self.env.company.id])],
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        user.write({"password": self.test_password})
        self.authenticate(user.login, self.test_password)

        for path in (
            "/autostock/api/v1/inventory",
            "/autostock/api/v1/inventory/options",
            "/autostock/api/v1/products/1/inventory-detail",
            "/autostock/api/v1/warehouses",
            "/autostock/api/v1/warehouses/1",
            "/autostock/api/v1/warehouses/1/inventory",
        ):
            data = self._get_json(path, expected_status=403)
            self.assertEqual(data["error"]["code"], "forbidden")

    def test_detail_uses_completed_receipts_and_current_reserved_deliveries_as_activity(self):
        company = self.env.company
        warehouse = self._warehouse(company)
        child_location = self.env["stock.location"].with_company(company).create(
            {
                "name": "Gate 5 receiving child location",
                "location_id": warehouse.lot_stock_id.id,
                "usage": "internal",
                "company_id": company.id,
            }
        )
        template = self.env["product.template"].create(
            {
                "name": "Gate4 Movement History Part",
                "default_code": "G4-MOVEMENT-001",
                "company_id": company.id,
                "is_storable": True,
            }
        )
        product = template.product_variant_id
        vendor = self.env["res.partner"].create(
            {
                "name": "Gate4 Movement Supplier",
                "company_type": "company",
                "supplier_rank": 1,
            }
        )
        receipt_type = warehouse.in_type_id
        receipt = self.env["stock.picking"].with_company(company).create(
            {
                "picking_type_id": receipt_type.id,
                "partner_id": vendor.id,
                "location_id": receipt_type.default_location_src_id.id,
                "location_dest_id": child_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom": product.uom_id.id,
                            "product_uom_qty": 30,
                            "location_id": receipt_type.default_location_src_id.id,
                            "location_dest_id": child_location.id,
                            "company_id": company.id,
                        }
                    )
                ],
            }
        )
        receipt.action_confirm()
        receipt.action_assign()
        for move in receipt.move_ids:
            move.write({"quantity": move.product_uom_qty, "picked": True})
        validation = receipt.button_validate()
        if isinstance(validation, dict):
            Form.from_action(self.env, validation).save().process()
        receipt.move_ids.write(
            {
                "date": fields.Datetime.to_string(
                    fields.Datetime.now() - timedelta(days=2)
                )
            }
        )

        dozen = self.env.ref("uom.product_uom_dozen")
        planned_receipt = self.env["stock.picking"].with_company(company).create(
            {
                "picking_type_id": receipt_type.id,
                "partner_id": vendor.id,
                "location_id": receipt_type.default_location_src_id.id,
                "location_dest_id": receipt_type.default_location_dest_id.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom": dozen.id,
                            "product_uom_qty": 2,
                            "location_id": receipt_type.default_location_src_id.id,
                            "location_dest_id": receipt_type.default_location_dest_id.id,
                            "company_id": company.id,
                        }
                    )
                ],
            }
        )
        planned_receipt.action_confirm()
        planned_receipt.move_ids.write(
            {
                "date": fields.Datetime.to_string(
                    fields.Datetime.now() + timedelta(days=5)
                )
            }
        )

        customer = self.env["res.partner"].create(
            {
                "name": "Gate4 Movement Customer",
                "company_type": "company",
                "customer_rank": 1,
            }
        )
        sale = self.env["sale.order"].with_company(company).create(
            {
                "company_id": company.id,
                "partner_id": customer.id,
                "partner_invoice_id": customer.id,
                "partner_shipping_id": customer.id,
                "warehouse_id": warehouse.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": 2,
                            "product_uom_id": dozen.id,
                            "price_unit": 1,
                        }
                    )
                ],
            }
        )
        sale.action_confirm()
        delivery = sale.picking_ids.filtered(
            lambda picking: picking.state not in ("done", "cancel")
        )[:1]
        self.assertTrue(delivery, "The customer order must create a delivery.")
        delivery.action_assign()
        delivery.move_ids.write(
            {
                "date": fields.Datetime.to_string(
                    fields.Datetime.now() + timedelta(days=2)
                )
            }
        )

        detail = self._get_json(
            f"/autostock/api/v1/products/{product.id}/inventory-detail"
        )

        self.assertEqual(detail["company_stock"]["on_hand"], 30)
        self.assertEqual(detail["company_stock"]["available"], 6)
        self.assertEqual(detail["company_stock"]["reserved"], 24)
        self.assertEqual(detail["company_stock"]["incoming"], 24)
        activity = {row["kind"]: row for row in detail["movements"]}
        self.assertIn("received", activity)
        self.assertEqual(activity["received"]["label"], "Received")
        self.assertEqual(activity["received"]["quantity"], 30)
        self.assertIn("incoming_purchase", activity)
        self.assertEqual(activity["incoming_purchase"]["quantity"], 24)
        self.assertIn("reserved_delivery", activity)
        self.assertEqual(
            activity["reserved_delivery"]["label"],
            "Reserved for customer orders",
        )
        self.assertEqual(activity["reserved_delivery"]["quantity"], 24)
        self.assertIn("Expected moves", detail["movement_note"])

        warehouse_inventory = self._get_json(
            f"/autostock/api/v1/warehouses/{warehouse.id}/inventory"
            "?q=G4-MOVEMENT-001"
        )
        movement_row = warehouse_inventory["items"][0]
        self.assertEqual(movement_row["on_hand"], 30)
        self.assertEqual(movement_row["available"], 6)
        self.assertEqual(movement_row["reserved"], 24)
        self.assertEqual(movement_row["incoming"], 24)
        self.assertEqual(movement_row["outgoing"], 24)
        self.assertEqual(movement_row["warehouse_count"], 1)

        warehouse_detail = self._get_json(
            f"/autostock/api/v1/warehouses/{warehouse.id}"
        )
        self.assertGreaterEqual(
            warehouse_detail["summary"]["parts_with_incoming_stock"], 1
        )
        self.assertGreaterEqual(
            warehouse_detail["summary"]["parts_with_outgoing_stock"], 1
        )
        warehouse_activity = {
            row["kind"]: row for row in warehouse_detail["activity"]
        }
        self.assertIn("received", warehouse_activity)
        self.assertIn("incoming_purchase", warehouse_activity)
        self.assertIn("reserved_delivery", warehouse_activity)
