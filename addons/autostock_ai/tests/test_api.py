from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import HttpCase


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
        item = next(row for row in data["items"] if row["product_id"] == product.id)
        self.assertEqual(item["name"], template.name)
        self.assertEqual(item["sku"], product.default_code)
        self.assertNotIn(product.default_code, item["name"])

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
            self.assertTrue(data["forecast"]["history"])
            self.assertTrue(data["forecast"]["predictions"])
            self.assertIn("source_label", data["forecast"])

    def test_global_search_contract_returns_no_unrequested_catalog_data(self):
        data = self._get_json("/autostock/api/v1/search/products?q=a")

        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["query"], "a")
        self.assertEqual(data["results"], [])
        self.assertFalse(data["limited"])
