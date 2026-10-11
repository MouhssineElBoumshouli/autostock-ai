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

    def _get_json(self, path, expected_status=200, timeout=12):
        response = self.url_open(path, allow_redirects=False, timeout=timeout)
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
        history_end=False,
        evaluation_days=0,
        name=False,
    ):
        history_end = (
            fields.Date.to_date(history_end)
            if history_end
            else fields.Date.today() - timedelta(days=1)
        )
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
            "history_start_date": history_end - timedelta(days=history_days - 1),
            "history_end_date": history_end,
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

    def _points(self, run, days=None, units=1.0):
        count_days = int(run.horizon_days) if days is None else days
        start = run.history_end_date + timedelta(days=1)
        return self.env["autostock.forecast.point"].create(
            [
                {
                    "run_id": run.id,
                    "day": start + timedelta(days=offset),
                    "units": units,
                    "lower_heuristic": max(0.0, units - 0.5),
                    "upper_heuristic": units + 0.5,
                }
                for offset in range(count_days)
            ]
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

        parts_a = self._get_json(
            f"/autostock/api/v1/forecasts/parts?company_id={company_a.id}&q=G7-SHARED-ROTOR"
        )
        parts_b = self._get_json(
            f"/autostock/api/v1/forecasts/parts?company_id={company_b.id}&q=G7-SHARED-ROTOR"
        )
        self.assertEqual(parts_a["company"]["id"], company_a.id)
        self.assertEqual([row["product_name"] for row in parts_a["parts"]], [shared_product.display_name])
        self.assertEqual(parts_a["parts"][0]["horizons"][0]["latest_run"]["id"], run_a.id)
        self.assertEqual(parts_b["company"]["id"], company_b.id)
        self.assertEqual(parts_b["parts"][0]["horizons"][0]["latest_run"]["id"], run_b.id)
        self._get_json(
            f"/autostock/api/v1/forecasts/parts?company_id={company_a.id}&warehouse_id={warehouse_b.id}",
            expected_status=403,
        )

    def test_part_forecast_selects_latest_status_and_only_sums_complete_saved_days(self):
        company = self.env.company
        warehouse = self._warehouse(company)
        product = self._product(company, "Gate 7 Complete Brake Rotor", "G7-COMPLETE-ROTOR")
        older_complete = self._run(
            company,
            sku="G7-COMPLETE-ROTOR",
            product=product,
            warehouse=warehouse,
            source_type=REAL_SOURCE,
            state="completed",
            review_status="reviewed",
            horizon=7,
            history_days=90,
            evaluation_days=7,
        )
        self._points(older_complete, units=1.0)
        newest_failed = self._run(
            company,
            sku="G7-COMPLETE-ROTOR",
            product=product,
            warehouse=warehouse,
            source_type=REAL_SOURCE,
            state="failed",
            review_status="unreviewed",
            horizon=7,
            history_days=90,
        )
        one_day_only = self._run(
            company,
            sku="G7-COMPLETE-ROTOR",
            product=product,
            warehouse=warehouse,
            source_type=REAL_SOURCE,
            state="completed",
            review_status="unreviewed",
            horizon=30,
            history_days=90,
            evaluation_days=7,
        )
        self._points(one_day_only, days=1, units=4.0)
        demo = self._run(
            company,
            sku="G7-COMPLETE-ROTOR",
            product=False,
            warehouse=False,
            source_type=SYNTHETIC_SOURCE,
            state="completed",
            review_status="reviewed",
            horizon=30,
            history_days=90,
            evaluation_days=7,
        )
        self._points(demo, units=3.0)

        page = self._get_json(
            f"/autostock/api/v1/forecasts/parts?q=G7-COMPLETE-ROTOR&warehouse_id={warehouse.id}"
        )
        self.assertEqual(len(page["parts"]), 1)
        part = page["parts"][0]
        self.assertEqual(part["product_id"], product.id)
        self.assertEqual(part["warehouse_id"], warehouse.id)
        self.assertEqual(part["source_type"], REAL_SOURCE)
        horizon_7 = next(item for item in part["horizons"] if item["horizon_days"] == 7)
        self.assertEqual(horizon_7["saved_run_count"], 2)
        self.assertEqual(horizon_7["latest_run"]["id"], newest_failed.id)
        self.assertEqual(horizon_7["latest_run"]["state"], "failed")
        self.assertEqual(horizon_7["latest_run"]["review_status"], "unreviewed")
        self.assertEqual(horizon_7["estimate"]["status"], "not_completed")
        self.assertFalse(horizon_7["estimate"]["estimated_units"])
        horizon_30 = next(item for item in part["horizons"] if item["horizon_days"] == 30)
        self.assertEqual(horizon_30["latest_run"]["id"], one_day_only.id)
        self.assertEqual(horizon_30["estimate"]["status"], "incomplete")
        self.assertFalse(horizon_30["estimate"]["estimated_units"])
        self.assertFalse(horizon_30["estimate"]["date_start"])
        horizon_60 = next(item for item in part["horizons"] if item["horizon_days"] == 60)
        self.assertFalse(horizon_60["latest_run"])
        self.assertEqual(horizon_60["estimate"]["status"], "missing")

        exact_detail = self._get_json(f"/autostock/api/v1/forecasts/{older_complete.id}")
        self.assertEqual(exact_detail["run"]["review_status"], "reviewed")
        self.assertEqual(exact_detail["estimate"]["status"], "available")
        self.assertEqual(exact_detail["estimate"]["estimated_units"], 7.0)
        self.assertEqual(
            exact_detail["estimate"]["date_start"],
            (older_complete.history_end_date + timedelta(days=1)).isoformat(),
        )
        self.assertEqual(exact_detail["estimate"]["date_end"], (older_complete.history_end_date + timedelta(days=7)).isoformat())
        self.assertNotEqual(exact_detail["restock_guidance"]["status"], "reviewed")
        self.assertFalse(exact_detail["restock_guidance"]["usable"])

        empty = self._get_json("/autostock/api/v1/forecasts/parts?q=G7-NO-SAVED-PART")
        self.assertEqual(empty["parts"], [])
        history = self._get_json("/autostock/api/v1/forecasts?q=G7-COMPLETE-ROTOR")
        self.assertIn(demo.id, [row["id"] for row in history["runs"]])

    def test_exact_daily_series_keeps_its_truthful_ended_date_window(self):
        company = self.env.company
        run = self._run(
            company,
            sku="DEMO-BP-001",
            product=self._product(company, "Gate 7 Ended Window Rotor", "DEMO-BP-001"),
            source_type=REAL_SOURCE,
            state="completed",
            horizon=7,
            history_days=90,
            history_end=fields.Date.today() - timedelta(days=17),
            evaluation_days=7,
        )
        self._points(run, units=2.0)

        detail = self._get_json(f"/autostock/api/v1/forecasts/{run.id}")
        estimate = detail["estimate"]
        self.assertEqual(estimate["status"], "available")
        self.assertEqual(estimate["window_status"], "ended")
        self.assertEqual(
            estimate["date_start"],
            (run.history_end_date + timedelta(days=1)).isoformat(),
        )
        self.assertEqual(
            estimate["date_end"],
            (run.history_end_date + timedelta(days=7)).isoformat(),
        )
        self.assertEqual(estimate["estimated_units"], 14.0)

    def test_part_forecast_pages_the_full_grouped_catalog_beyond_1001_runs(self):
        company = self.env.company
        today = fields.Date.today()
        templates = self.env["product.template"].with_company(company).create(
            [
                {
                    "name": f"Gate 7 grouped catalog part {index:04d}",
                    "default_code": f"G7-GROUP-{index:04d}",
                    "company_id": company.id,
                    "is_storable": True,
                    "autostock_enabled": True,
                }
                for index in range(334)
            ]
        )
        products = templates.product_variant_id
        run_values = []
        for product in products:
            for horizon in (7, 30, 60):
                run_values.append(
                    {
                        "name": f"{product.default_code} · {horizon} days",
                        "company_id": company.id,
                        "product_id": product.id,
                        "product_name": product.display_name,
                        "sku": product.default_code,
                        "uom_id": product.uom_id.id,
                        "source_type": REAL_SOURCE,
                        "state": "failed",
                        "evaluation_status": "failed",
                        "horizon_days": str(horizon),
                        "history_start_date": today - timedelta(days=90),
                        "history_end_date": today - timedelta(days=1),
                        "source_cutoff": fields.Datetime.now(),
                        "failure_reason": "Integration fixture; no forecast was generated.",
                    }
                )
        models.Model.create(self.env["autostock.forecast.run"], run_values)

        first_page = self._get_json(
            "/autostock/api/v1/forecasts/parts?q=G7-GROUP&page=1&page_size=25",
            timeout=60,
        )
        last_page = self._get_json(
            "/autostock/api/v1/forecasts/parts?q=G7-GROUP&page=14&page_size=25",
            timeout=60,
        )
        self.assertEqual(len(first_page["parts"]), 25)
        self.assertTrue(first_page["pagination"]["has_next"])
        self.assertEqual(len({row["product_id"] for row in first_page["parts"]}), 25)
        self.assertEqual(len(last_page["parts"]), 9)
        self.assertFalse(last_page["pagination"]["has_next"])
        self.assertNotIn("total_count", last_page["pagination"])
        for part in first_page["parts"]:
            self.assertEqual(len(part["horizons"]), 3)
            self.assertEqual([item["saved_run_count"] for item in part["horizons"]], [1, 1, 1])
        searched = self._get_json(
            "/autostock/api/v1/forecasts/parts?q=G7-GROUP-0333&page_size=12",
            timeout=60,
        )
        self.assertEqual(len(searched["parts"]), 1)
        self.assertEqual(searched["parts"][0]["sku"], "G7-GROUP-0333")
        self.assertEqual(searched["parts"][0]["product_id"], products[-1].id)

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
        # The API orders newest IDs first, so the oldest of this batch is
        # the single row on page 41. Searching the newest row below also
        # verifies that a part beyond the first page remains discoverable.
        self.assertEqual(last_page["runs"][0]["sku"], "G7-BULK-0000")

        sku_search = self._get_json(
            "/autostock/api/v1/forecasts?q=G7-BULK-0000&page_size=12"
        )
        self.assertEqual(sku_search["pagination"]["total_count"], 1)
        self.assertEqual(sku_search["runs"][0]["sku"], "G7-BULK-0000")

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
        parts = self._get_json("/autostock/api/v1/forecasts/parts")
        self.assertFalse(parts["real_history_access"])
        self.assertTrue(parts["access_note"])
        self.assertEqual(parts["parts"], [])
        self.assertNotIn("G7-RESTRICTED", str(parts))
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
