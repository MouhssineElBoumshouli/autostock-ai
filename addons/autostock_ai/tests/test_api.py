from odoo import Command, fields
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.autostock_ai.models.forecast import REAL_SOURCE


@tagged("post_install", "-at_install")
class TestAutoStockApiV1(HttpCase):
    def setUp(self):
        super().setUp()
        admin = self.env.ref("base.user_admin")
        admin.write({"password": "test-password"})
        self.authenticate(admin.login, "test-password")

    def _get_json(self, path, expected_status=200):
        response = self.url_open(path, allow_redirects=False)
        self.assertEqual(response.status_code, expected_status, response.text[:500])
        self.assertIn("application/json", response.headers.get("Content-Type", ""))
        return response.json()

    def test_session_contract_uses_the_authenticated_odoo_identity(self):
        data = self._get_json("/autostock/api/v1/session")

        self.assertEqual(data["schema_version"], 1)
        self.assertTrue(data["authenticated"])
        self.assertEqual(data["user"]["id"], self.env.ref("base.user_admin").id)
        self.assertIn("inventory", data["user"]["permissions"])
        self.assertEqual(
            data["current_company"]["id"], self.env.company.id
        )
        self.assertIn(
            data["current_company"]["id"],
            [company["id"] for company in data["allowed_companies"]],
        )
        self.assertIn("demo_environment", data["current_company"])

    def test_unavailable_company_is_rejected_as_a_json_permission_error(self):
        data = self._get_json(
            "/autostock/api/v1/session?company_id=2147483647", expected_status=403
        )

        self.assertEqual(data["error"]["code"], "forbidden")

    def test_dashboard_keeps_the_standard_odoo_inventory_access_gate(self):
        user = self.env["res.users"].create(
            {
                "name": "AutoStock API read-only test user",
                "login": "autostock-api-readonly-test",
                "email": "autostock-api-readonly-test@example.invalid",
                "company_id": self.env.company.id,
                "company_ids": [Command.set([self.env.company.id])],
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        user.write({"password": "test-password"})
        self.authenticate(user.login, "test-password")

        data = self._get_json("/autostock/api/v1/dashboard", expected_status=403)

        self.assertEqual(data["error"]["code"], "forbidden")
        self.assertIn("inventory access", data["error"]["message"].lower())
        search = self._get_json("/autostock/api/v1/search/products?q=part", expected_status=403)
        self.assertEqual(search["error"]["code"], "forbidden")

    def test_dashboard_contract_exposes_backend_summary_scope(self):
        data = self._get_json("/autostock/api/v1/dashboard")

        self.assertEqual(data["schema_version"], 1)
        self.assertIn("tracked_products", data["kpis"])
        self.assertIn("in_stock", data["kpis"])
        self.assertIn("complete", data["inventory_health"])
        self.assertLessEqual(
            data["inventory_health"]["sampled_products"],
            data["inventory_health"]["total_tracked"],
        )
        self.assertEqual(len(data["inventory_health"]["categories"]), 3)
        self.assertIn("reviewed_forecasts", data["kpis"])
        self.assertIn("reviewed_forecasts_available", data["kpis"])
        self.assertTrue(all("percent" in row for row in data["inventory_health"]["categories"]))

    def test_restock_preview_contract_is_read_only_and_bounded(self):
        template = self.env["product.template"].create(
            {
                "name": "AutoStock API Clean Label Test Part",
                "default_code": "AS-API-CLEAN-001",
                "company_id": self.env.company.id,
                "is_storable": True,
                "autostock_enabled": True,
            }
        )
        product = template.product_variant_id
        data = self._get_json("/autostock/api/v1/dashboard/restock-preview")

        self.assertEqual(data["schema_version"], 1)
        self.assertTrue(data["read_only"])
        self.assertLessEqual(len(data["items"]), 5)
        self.assertIn("complete", data["coverage"])
        self.assertIn("warehouses", data)
        self.assertIn("summary", data)
        self.assertGreaterEqual(data["summary"]["priority_locations"], len(data["items"]))
        self.assertLessEqual(
            data["summary"]["reorder_suggestions"],
            data["summary"]["priority_locations"],
        )
        self.assertEqual(data["summary"]["complete"], data["coverage"]["complete"])
        item = next(row for row in data["items"] if row["product_id"] == product.id)
        self.assertEqual(item["name"], template.name)
        self.assertEqual(item["sku"], product.default_code)
        self.assertNotIn(product.default_code, item["name"])
        self.assertIn("category", item)
        self.assertIn("forecast_used", item)
        self.assertIn("supplier_access_note", item)
        self.assertIn("policy_source_label", item)
        self.assertIn("insights", data)
        self.assertEqual(len(data["insights"]), 3)

    def test_product_quick_view_reuses_company_scoped_replenishment_data(self):
        template = self.env["product.template"].create(
            {
                "name": "AutoStock API Quick View Part",
                "default_code": "AS-API-QUICK-001",
                "company_id": self.env.company.id,
                "is_storable": True,
                "autostock_enabled": True,
                "autostock_safety_stock": 4,
            }
        )
        product = template.product_variant_id
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        self.env["stock.quant"].with_company(self.env.company)._update_available_quantity(
            product, warehouse.lot_stock_id, 2
        )

        data = self._get_json(f"/autostock/api/v1/products/{product.id}/quick-view")

        self.assertTrue(data["read_only"])
        self.assertEqual(data["company"]["id"], self.env.company.id)
        self.assertEqual(data["product"]["name"], template.name)
        self.assertEqual(data["product"]["sku"], product.default_code)
        self.assertTrue(data["product"]["tracked"])
        self.assertEqual(len(data["positions"]), 1)
        self.assertEqual(data["positions"][0]["warehouse_id"], warehouse.id)
        self.assertEqual(data["positions"][0]["current_qty"], 2)

    def test_supplier_name_search_returns_only_company_visible_parts(self):
        template = self.env["product.template"].create(
            {
                "name": "AutoStock API Vendor Match Part",
                "default_code": "AS-API-VENDOR-001",
                "company_id": self.env.company.id,
                "is_storable": True,
            }
        )
        supplier = self.env["res.partner"].create(
            {"name": "AutoStock API Search Supplier", "company_type": "company"}
        )
        self.env["product.supplierinfo"].create(
            {
                "partner_id": supplier.id,
                "product_tmpl_id": template.id,
                "company_id": self.env.company.id,
                "price": 1.0,
                "currency_id": self.env.company.currency_id.id,
            }
        )

        data = self._get_json("/autostock/api/v1/search/products?q=API%20Search%20Supplier")

        self.assertEqual([item["name"] for item in data["results"]], [template.name])
        self.assertEqual(data["results"][0]["supplier_names"], [supplier.display_name])

    def test_forecast_preview_has_a_truthful_empty_state(self):
        data = self._get_json(
            "/autostock/api/v1/dashboard/forecast-preview?horizon_days=60"
        )

        self.assertEqual(data["schema_version"], 1)
        self.assertIn(data["status"], {"available", "unavailable", "restricted"})
        if data["status"] != "available":
            self.assertFalse(data["forecast"])
            self.assertTrue(data["message"])
        else:
            self.assertEqual(data["forecast"]["source_type"], REAL_SOURCE)
            self.assertTrue(data["forecast"]["history"])
            self.assertTrue(data["forecast"]["predictions"])
            self.assertIn("source_label", data["forecast"])

    def test_dashboard_forecast_never_falls_back_to_synthetic_demo_data(self):
        company = self.env.company
        company.autostock_demo_environment = True
        result = self.env["autostock.forecast.run"].seed_synthetic_demo("DEMO-BP-001", 7)
        self.env["autostock.forecast.run"].browse(result["id"])._process_queued_run()

        data = self._get_json("/autostock/api/v1/dashboard/forecast-preview?horizon_days=7")

        if data["status"] == "available":
            self.assertEqual(data["forecast"]["source_type"], REAL_SOURCE)
        else:
            self.assertEqual(data["status"], "unavailable")
            self.assertFalse(data["forecast"])

    def test_multi_company_dashboard_search_restock_and_quick_view_remain_isolated(self):
        company_a, company_b = self.env["res.company"].create(
            [{"name": "AutoStock API Company A"}, {"name": "AutoStock API Company B"}]
        )
        warehouse_model = self.env["stock.warehouse"]
        warehouse_a = warehouse_model.search([("company_id", "=", company_a.id)], limit=1)
        warehouse_b = warehouse_model.search([("company_id", "=", company_b.id)], limit=1)
        unit = self.env.ref("uom.product_uom_unit")

        def create_product(name, company, sku):
            template = self.env["product.template"].with_company(company).create(
                {
                    "name": name,
                    "default_code": sku,
                    "company_id": company.id,
                    "is_storable": True,
                    "uom_id": unit.id,
                    "autostock_enabled": True,
                    "autostock_safety_stock": 20,
                }
            )
            return template.product_variant_id

        product_a = create_product("Company A Brake Rotor", company_a, "AS-API-A-001")
        product_b = create_product("Company B Brake Rotor", company_b, "AS-API-B-001")
        shared = create_product("Shared Brake Rotor", company_a, "AS-API-SHARED-001")
        shared.product_tmpl_id.company_id = False
        quant = self.env["stock.quant"]
        quant.with_company(company_a)._update_available_quantity(product_a, warehouse_a.lot_stock_id, 7)
        quant.with_company(company_b)._update_available_quantity(product_b, warehouse_b.lot_stock_id, 11)
        quant.with_company(company_a)._update_available_quantity(shared, warehouse_a.lot_stock_id, 2)
        quant.with_company(company_b)._update_available_quantity(shared, warehouse_b.lot_stock_id, 13)

        user = self.env["res.users"].create(
            {
                "name": "AutoStock API Company Switch User",
                "login": "autostock-api-company-switch-test",
                "company_id": company_a.id,
                "company_ids": [Command.set([company_a.id, company_b.id])],
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("stock.group_stock_user").id,
                            self.env.ref("sales_team.group_sale_manager").id,
                        ]
                    )
                ],
            }
        )
        user.write({"password": "test-password"})
        self.authenticate(user.login, "test-password")

        session_a = self._get_json(f"/autostock/api/v1/session?company_id={company_a.id}")
        dashboard_a = self._get_json(f"/autostock/api/v1/dashboard?company_id={company_a.id}")
        restock_a = self._get_json(f"/autostock/api/v1/dashboard/restock-preview?company_id={company_a.id}")
        search_a = self._get_json(f"/autostock/api/v1/search/products?q=AS-API-B-001&company_id={company_a.id}")
        shared_a = self._get_json(
            f"/autostock/api/v1/products/{shared.id}/quick-view?company_id={company_a.id}"
        )

        self.assertEqual(session_a["current_company"]["id"], company_a.id)
        self.assertEqual(dashboard_a["company"]["id"], company_a.id)
        self.assertEqual(dashboard_a["kpis"]["tracked_products"], 2)
        self.assertEqual(search_a["results"], [])
        self.assertNotIn(product_b.default_code, [item["sku"] for item in restock_a["items"]])
        shared_position_a = next(row for row in shared_a["positions"] if row["warehouse_id"] == warehouse_a.id)
        self.assertEqual(shared_position_a["current_qty"], 2)
        self.assertNotIn(warehouse_b.id, [row["warehouse_id"] for row in shared_a["positions"]])

        dashboard_b = self._get_json(f"/autostock/api/v1/dashboard?company_id={company_b.id}")
        restock_b = self._get_json(f"/autostock/api/v1/dashboard/restock-preview?company_id={company_b.id}")
        search_b = self._get_json(f"/autostock/api/v1/search/products?q=AS-API-B-001&company_id={company_b.id}")
        shared_b = self._get_json(
            f"/autostock/api/v1/products/{shared.id}/quick-view?company_id={company_b.id}"
        )

        self.assertEqual(dashboard_b["company"]["id"], company_b.id)
        self.assertEqual(dashboard_b["kpis"]["tracked_products"], 2)
        self.assertEqual([item["sku"] for item in search_b["results"]], [product_b.default_code])
        self.assertIn(product_b.default_code, [item["sku"] for item in restock_b["items"]])
        self.assertNotIn(product_a.default_code, [item["sku"] for item in restock_b["items"]])
        shared_position_b = next(row for row in shared_b["positions"] if row["warehouse_id"] == warehouse_b.id)
        self.assertEqual(shared_position_b["current_qty"], 13)
        self.assertNotIn(warehouse_a.id, [row["warehouse_id"] for row in shared_b["positions"]])

    def test_global_search_contract_returns_no_unrequested_catalog_data(self):
        data = self._get_json("/autostock/api/v1/search/products?q=a")

        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["query"], "a")
        self.assertEqual(data["results"], [])
        self.assertFalse(data["limited"])
