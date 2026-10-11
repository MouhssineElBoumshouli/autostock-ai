import secrets
from datetime import timedelta

from odoo import Command, fields, models
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.autostock_ai.models.forecast import REAL_SOURCE, SYNTHETIC_SOURCE


@tagged("post_install", "-at_install")
class TestAutoStockForecastApi(HttpCase):
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

    def _company(self, name):
        return self.env["res.company"].create({"name": name})

    def _warehouse(self, company):
        return self.env["stock.warehouse"].with_company(company).create(
            {
                "name": f"{company.name} Forecast Depot",
                "code": f"G{company.id:04d}"[-5:],
                "company_id": company.id,
            }
        )

    def _product(self, company, name, sku, *, shared=False):
        template = self.env["product.template"].with_company(company).create(
            {
                "name": name,
                "default_code": sku,
                "company_id": False if shared else company.id,
                "is_storable": True,
                "autostock_enabled": True,
            }
        )
        return template.product_variant_id

    def _run(
        self,
        company,
        *,
        sku,
        product=False,
        warehouse=False,
        source_type=SYNTHETIC_SOURCE,
        state="failed",
        review_status="unreviewed",
        horizon=7,
        history_days=100,
        evaluation_days=0,
        name=False,
    ):
        today = fields.Date.today()
        values = {
            "name": name or f"Gate 7 {sku}",
            "company_id": company.id,
            "warehouse_id": warehouse.id if warehouse else False,
            "product_id": product.id if product else False,
            "product_name": product.display_name if product else f"{sku} sample",
            "sku": sku,
            "uom_id": product.uom_id.id if product else False,
            "source_type": source_type,
            "state": state,
            "evaluation_status": "evaluated" if state == "completed" else state,
            "review_status": review_status,
            "horizon_days": str(horizon),
            "history_start_date": today - timedelta(days=history_days - 1),
            "history_end_date": today - timedelta(days=1),
            "source_cutoff": fields.Datetime.now(),
            "history_days": history_days,
            "nonzero_days": 12 if state == "completed" else 0,
            "source_event_count": 84 if state == "completed" else 0,
            "selected_method": "trailing_mean" if state == "completed" else False,
            "baseline_method": "seasonal_naive" if state == "completed" else False,
            "evaluation_days": evaluation_days,
            "baseline_mae": 1.2 if state == "completed" else 0.0,
            "ml_mae": 0.9 if state == "completed" else 0.0,
            "ml_evaluated": state == "completed",
            "data_provenance": "Gate 7 integration-test fixture; no business transactions.",
            "assumptions": "Test fixture only.",
            "limitations": "Test fixture only.",
            "failure_reason": "Not enough history for this test run." if state == "failed" else False,
        }
        # Fixture creation intentionally bypasses the production create guard;
        # user-facing requests cannot create or alter forecast runs.
        return models.Model.create(
            self.env["autostock.forecast.run"].with_company(company).with_context(
                allowed_company_ids=[company.id]
            ),
            values,
        )

    def _user(self, name, company, companies, *, sales=False):
        groups = [self.env.ref("base.group_user"), self.env.ref("stock.group_stock_user")]
        if sales:
            groups.append(self.env.ref("sales_team.group_sale_manager"))
        login = f"gate7-{name}-{secrets.token_hex(4)}"
        user = self.env["res.users"].create(
            {
                "name": name,
                "login": login,
                "company_id": company.id,
                "company_ids": [Command.set(companies.ids)],
                "group_ids": [Command.set([group.id for group in groups])],
            }
        )
        password = secrets.token_urlsafe(18)
        user.write({"password": password})
        return user, password

    def test_forecasts_are_company_and_warehouse_scoped_for_multi_company_users(self):
        company_a = self.env.company
        company_b = self._company("Gate 7 Second Company")
        warehouse_a = self._warehouse(company_a)
        warehouse_b = self._warehouse(company_b)
        shared_product = self._product(
            company_a, "Gate 7 Shared Brake Rotor", "G7-SHARED-ROTOR", shared=True
        )
        run_a = self._run(
            company_a,
            sku="G7-SHARED-ROTOR",
            product=shared_product,
            warehouse=warehouse_a,
            source_type=REAL_SOURCE,
            state="queued",
        )
        run_b = self._run(
            company_b,
            sku="G7-SHARED-ROTOR",
            product=shared_product,
            warehouse=warehouse_b,
            source_type=REAL_SOURCE,
            state="queued",
        )
        user, password = self._user(
            "Gate 7 Multi Company Forecast User",
            company_a,
            company_a | company_b,
            sales=True,
        )
        self.authenticate(user.login, password)

        page_a = self._get_json(
            f"/autostock/api/v1/forecasts?company_id={company_a.id}&q=G7-SHARED-ROTOR"
        )
        self.assertEqual(page_a["company"]["id"], company_a.id)
        self.assertEqual(page_a["pagination"]["total_count"], 1)
        self.assertEqual([row["id"] for row in page_a["runs"]], [run_a.id])

        page_b = self._get_json(
            f"/autostock/api/v1/forecasts?company_id={company_b.id}&q=G7-SHARED-ROTOR"
        )
        self.assertEqual(page_b["company"]["id"], company_b.id)
        self.assertEqual(page_b["pagination"]["total_count"], 1)
        self.assertEqual([row["id"] for row in page_b["runs"]], [run_b.id])

        self._get_json(
            f"/autostock/api/v1/forecasts?company_id={company_a.id}&warehouse_id={warehouse_b.id}",
            expected_status=403,
        )
        self._get_json(
            f"/autostock/api/v1/forecasts/{run_b.id}?company_id={company_a.id}",
            expected_status=403,
        )

    def test_forecast_search_and_pagination_reach_run_1001(self):
        company = self.env.company
        today = fields.Date.today()
        values = [
            {
                "name": f"Gate 7 bulk forecast {index:04d}",
                "company_id": company.id,
                "product_name": f"Gate 7 catalog part {index:04d}",
                "sku": f"G7-BULK-{index:04d}",
                "source_type": SYNTHETIC_SOURCE,
                "state": "failed",
                "evaluation_status": "failed",
                "horizon_days": "7",
                "history_start_date": today - timedelta(days=100),
                "history_end_date": today - timedelta(days=1),
                "source_cutoff": fields.Datetime.now(),
                "failure_reason": "Test-only run; no forecast was generated.",
            }
            for index in range(1001)
        ]
        models.Model.create(
            self.env["autostock.forecast.run"],
            values,
        )

        last_page = self._get_json(
            "/autostock/api/v1/forecasts?q=G7-BULK&page=41&page_size=25"
        )
        self.assertEqual(last_page["pagination"]["total_count"], 1001)
        self.assertEqual(last_page["pagination"]["page"], 41)
        self.assertEqual(len(last_page["runs"]), 1)
        self.assertEqual(last_page["runs"][0]["sku"], "G7-BULK-1000")

        sku_search = self._get_json(
            "/autostock/api/v1/forecasts?q=G7-BULK-1000&page_size=12"
        )
        self.assertEqual(sku_search["pagination"]["total_count"], 1)
        self.assertEqual(sku_search["runs"][0]["sku"], "G7-BULK-1000")

    def test_forecast_detail_reads_one_exact_run_without_changing_records(self):
        company = self.env.company
        run = self._run(
            company,
            sku="DEMO-BP-001",
            source_type=SYNTHETIC_SOURCE,
            state="completed",
            history_days=120,
            evaluation_days=7,
        )
        observation = self.env["autostock.forecast.observation"].create(
            {
                "run_id": run.id,
                "day": run.history_end_date,
                "delivered_units": 2.0,
                "returned_units": 1.0,
                "units": 2.0,
                "source_event_count": 3,
            }
        )
        point = self.env["autostock.forecast.point"].create(
            {
                "run_id": run.id,
                "day": fields.Date.today() + timedelta(days=1),
                "units": 2.5,
                "lower_heuristic": 1.0,
                "upper_heuristic": 4.0,
            }
        )
        before = (
            self.env["autostock.forecast.run"].search_count([]),
            self.env["autostock.forecast.observation"].search_count([]),
            self.env["autostock.forecast.point"].search_count([]),
            run.state,
            run.review_status,
        )

        detail = self._get_json(f"/autostock/api/v1/forecasts/{run.id}")
        after = (
            self.env["autostock.forecast.run"].search_count([]),
            self.env["autostock.forecast.observation"].search_count([]),
            self.env["autostock.forecast.point"].search_count([]),
            run.state,
            run.review_status,
        )
        self.assertEqual(before, after)
        self.assertTrue(detail["read_only"])
        self.assertEqual(detail["run"]["id"], run.id)
        self.assertEqual(detail["run"]["observations"][0]["returned_units"], 1.0)
        self.assertEqual(detail["run"]["predictions"][0]["units"], point.units)
        self.assertEqual(detail["restock_guidance"]["status"], "not_applicable")
        self.assertFalse(detail["restock_guidance"]["usable"])

    def test_real_delivery_records_are_restricted_without_sales_access(self):
        company = self.env.company
        product = self._product(company, "Gate 7 Restricted Rotor", "G7-RESTRICTED")
        real_run = self._run(
            company,
            sku="G7-RESTRICTED",
            product=product,
            source_type=REAL_SOURCE,
            state="queued",
        )
        self._run(company, sku="DEMO-BP-001", source_type=SYNTHETIC_SOURCE)
        user, password = self._user(
            "Gate 7 Stock-only User", company, company, sales=False
        )
        self.authenticate(user.login, password)

        page = self._get_json("/autostock/api/v1/forecasts")
        self.assertFalse(page["real_history_access"])
        self.assertTrue(page["access_note"])
        self.assertTrue(all(row["source_type"] == SYNTHETIC_SOURCE for row in page["runs"]))
        self.assertNotIn("G7-RESTRICTED", str(page))
        self._get_json(
            "/autostock/api/v1/forecasts?source_type=completed_deliveries",
            expected_status=403,
        )
        self._get_json(
            f"/autostock/api/v1/forecasts/{real_run.id}",
            expected_status=403,
        )

    def test_forecast_filters_reject_invalid_values_and_foreign_warehouses(self):
        company = self.env.company
        other_company = self._company("Gate 7 Filter Isolation")
        other_warehouse = self._warehouse(other_company)

        self._get_json(
            "/autostock/api/v1/forecasts?horizon_days=90",
            expected_status=422,
        )
        self._get_json(
            "/autostock/api/v1/forecasts?state=approved",
            expected_status=422,
        )
        self._get_json(
            "/autostock/api/v1/forecasts?page_size=51",
            expected_status=422,
        )
        self._get_json(
            f"/autostock/api/v1/forecasts?warehouse_id={other_warehouse.id}",
            expected_status=403,
        )
        self._get_json(
            f"/autostock/api/v1/forecasts?company_id={other_company.id}",
            expected_status=403,
        )
