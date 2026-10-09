from datetime import datetime, time, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase

from ml.forecast import Observation, forecast_daily
from odoo.addons.autostock_ai.models.forecast import REAL_SOURCE


class TestAutoStockForecast(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.dozen = cls.env.ref("uom.product_uom_dozen")
        cls.partner = cls.env["res.partner"].create(
            {"name": "AutoStock Forecast Test Customer", "company_type": "company"}
        )
        cls.today = fields.Date.today()

    def _warehouse(self, company):
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", company.id)], limit=1
        )
        if not warehouse:
            code = f"AS{company.id:02d}"[-5:]
            warehouse = self.env["stock.warehouse"].create(
                {"name": f"AutoStock {company.name}", "code": code, "company_id": company.id}
            )
        return warehouse

    def _product(self, company, sku, uom=None):
        template = self.env["product.template"].with_company(company).create(
            {
                "name": sku,
                "default_code": sku,
                "company_id": company.id,
                "is_storable": True,
                "uom_id": (uom or self.unit).id,
                "autostock_enabled": True,
            }
        )
        return template.product_variant_id

    def _sale_order(self, company, warehouse, product, quantity, uom=None, state="confirmed"):
        self.env["stock.quant"].with_company(company)._update_available_quantity(
            product, warehouse.lot_stock_id, quantity * ((uom or product.uom_id)._compute_quantity(1, product.uom_id))
        )
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
                            "product_uom_id": (uom or product.uom_id).id,
                            "price_unit": 1.0,
                        }
                    )
                ],
            }
        )
        if state == "quote":
            return order, self.env["stock.picking"]
        order.action_confirm()
        picking = order.picking_ids
        if state == "cancel":
            order.action_cancel()
            return order, picking
        if state == "confirmed":
            return order, picking
        move_quantity = quantity
        if uom:
            # Odoo normally normalizes sale moves to the product unit. Keep the
            # transfer's alternate but category-compatible UoM here to exercise
            # the forecast source converter against a real completed stock move.
            picking.move_ids.write({"product_uom": uom.id, "product_uom_qty": quantity})
            move_quantity = quantity
        picking.move_ids.write({"quantity": move_quantity, "picked": True})
        validation = picking.button_validate()
        if isinstance(validation, dict):
            Form.from_action(self.env, validation).save().process()
        return order, picking

    def _source_run(self, company, product, warehouse=False, cutoff=None, start=None, end=None):
        return self.env["autostock.forecast.run"].new(
            {
                "company_id": company.id,
                "warehouse_id": warehouse.id if warehouse else False,
                "product_id": product.id,
                "sku": product.default_code,
                "source_type": REAL_SOURCE,
                "history_start_date": start or self.today,
                "history_end_date": end or self.today,
                "source_cutoff": cutoff or fields.Datetime.now() + timedelta(minutes=2),
            }
        )

    def _multi_company_user(self, company_a, company_b):
        groups = [
            self.env.ref("base.group_user"),
            self.env.ref("stock.group_stock_user"),
            self.env.ref("sales_team.group_sale_manager"),
        ]
        return self.env["res.users"].create(
            {
                "name": "AutoStock Forecast Multi Company",
                "login": f"autostock-forecast-multi-{company_a.id}-{company_b.id}",
                "company_id": company_a.id,
                "company_ids": [Command.set([company_a.id, company_b.id])],
                "group_ids": [Command.set([group.id for group in groups])],
            }
        )

    def test_return_is_bounded_by_history_and_kept_on_its_actual_day(self):
        company = self.env.company
        warehouse = self._warehouse(company)
        delivery_day = self.today - timedelta(days=4)
        return_day = delivery_day + timedelta(days=2)
        warehouse.write({"autostock_history_complete_from": delivery_day})
        product = self._product(company, "AS-DOZEN-RETURN", self.unit)
        order, delivery = self._sale_order(
            company, warehouse, product, quantity=2, uom=self.dozen, state="done"
        )
        self.assertEqual(delivery.state, "done")
        delivery.move_ids.write(
            {"date": fields.Datetime.to_string(datetime.combine(delivery_day, time(10)))}
        )

        return_form = Form(
            self.env["stock.return.picking"].with_context(
                active_ids=delivery.ids,
                active_id=delivery.id,
                active_model="stock.picking",
            )
        )
        return_wizard = return_form.save()
        return_line = return_wizard.product_return_moves.filtered(
            lambda line: line.product_id == product
        )
        return_line.quantity = 0.5
        return_result = return_wizard.action_create_returns()
        return_picking = self.env["stock.picking"].browse(return_result["res_id"])
        return_picking.move_ids.write({"quantity": 0.5, "picked": True})
        return_validation = return_picking.button_validate()
        if isinstance(return_validation, dict):
            Form.from_action(self.env, return_validation).save().process()
        return_picking.move_ids.write(
            {"date": fields.Datetime.to_string(datetime.combine(return_day, time(10)))}
        )

        # A quotation and an undelivered confirmed order have no completed demand.
        self._sale_order(company, warehouse, product, quantity=1, state="quote")
        self._sale_order(company, warehouse, product, quantity=1, state="confirmed")
        self._sale_order(company, warehouse, product, quantity=1, state="cancel")

        delivery_only_run = self._source_run(
            company, product, warehouse=warehouse, start=delivery_day, end=delivery_day
        )
        delivery_only, delivery_events = delivery_only_run._completed_sales_snapshot()
        self.assertEqual(delivery_events, 1)
        self.assertEqual(len(delivery_only), 1)
        self.assertEqual(delivery_only[0]["delivered_units"], 24.0)
        self.assertEqual(delivery_only[0]["returned_units"], 0.0)
        self.assertEqual(delivery_only[0]["units"], 24.0)
        self.assertEqual(delivery_only[0]["source_event_count"], 1)

        before_return_cutoff = datetime.combine(return_day, time.min)
        cutoff_run = self._source_run(
            company,
            product,
            warehouse=warehouse,
            cutoff=before_return_cutoff,
            start=delivery_day,
            end=return_day,
        )
        cutoff_snapshot, cutoff_events = cutoff_run._completed_sales_snapshot()
        self.assertEqual(cutoff_events, 1)
        self.assertEqual(cutoff_snapshot[0]["units"], 24.0)
        self.assertEqual(cutoff_snapshot[-1]["returned_units"], 0.0)

        full_run = self._source_run(
            company, product, warehouse=warehouse, start=delivery_day, end=return_day
        )
        full_snapshot, full_events = full_run._completed_sales_snapshot()
        delivery_row = next(item for item in full_snapshot if item["day"] == delivery_day)
        return_row = next(item for item in full_snapshot if item["day"] == return_day)
        self.assertEqual(delivery_row["delivered_units"], 24.0)
        self.assertEqual(delivery_row["returned_units"], 0.0)
        self.assertEqual(delivery_row["units"], 24.0)
        self.assertEqual(return_row["delivered_units"], 0.0)
        self.assertEqual(return_row["returned_units"], 6.0)
        self.assertEqual(return_row["units"], 0.0)
        self.assertEqual(return_row["source_event_count"], 1)
        self.assertEqual(full_events, 2)
        self.assertEqual(order.state, "sale")

    def test_real_forecast_worker_persists_evaluated_odoo_delivery_history(self):
        company = self.env.company
        start = self.today - timedelta(days=119)
        company.write({"autostock_history_complete_from": start})
        warehouse = self._warehouse(company)
        product = self._product(company, "AS-REAL-WORKER")
        product.write({"create_date": fields.Datetime.to_string(datetime.combine(start, time.min))})
        _, delivery = self._sale_order(company, warehouse, product, quantity=4, state="done")
        delivery.move_ids.write(
            {
                "date": fields.Datetime.to_string(
                    datetime.combine(start + timedelta(days=15), time(10))
                )
            }
        )
        return_day = self.today - timedelta(days=2)
        return_form = Form(
            self.env["stock.return.picking"].with_context(
                active_ids=delivery.ids,
                active_id=delivery.id,
                active_model="stock.picking",
            )
        )
        return_wizard = return_form.save()
        return_wizard.product_return_moves.filtered(
            lambda line: line.product_id == product
        ).quantity = 1.0
        return_result = return_wizard.action_create_returns()
        return_picking = self.env["stock.picking"].browse(return_result["res_id"])
        return_picking.move_ids.write({"quantity": 1.0, "picked": True})
        return_validation = return_picking.button_validate()
        if isinstance(return_validation, dict):
            Form.from_action(self.env, return_validation).save().process()
        return_picking.move_ids.write(
            {"date": fields.Datetime.to_string(datetime.combine(return_day, time(10)))}
        )

        forecast_user = self.env["res.users"].create(
            {
                "name": "AutoStock Real Forecast User",
                "login": "autostock-real-forecast-user",
                "company_id": company.id,
                "company_ids": [Command.set([company.id])],
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
        forecast_model = (
            self.env["autostock.forecast.run"]
            .with_user(forecast_user)
            .with_company(company)
            .with_context(allowed_company_ids=[company.id])
        )
        result = forecast_model.request_forecast(product.id, 7, start, self.today, False)
        self.assertEqual(result["state"], "queued")
        run = self.env["autostock.forecast.run"].browse(result["id"])

        run._process_queued_run()

        run.invalidate_recordset()
        self.assertEqual(run.state, "completed", run.failure_reason)
        self.assertEqual(run.source_type, REAL_SOURCE)
        self.assertEqual(run.source_event_count, 2)
        self.assertEqual(run.history_days, 120)
        self.assertEqual(len(run.observation_ids), 120)
        self.assertEqual(len(run.point_ids), 7)
        self.assertEqual(sum(run.observation_ids.mapped("units")), 4.0)
        self.assertEqual(run.evaluation_days, 7)
        self.assertTrue(run.source_snapshot_sha256)
        self.assertEqual(run.model_version, "autostock-demand-v2.1.0")
        self.assertEqual(run.review_status, "unreviewed")

        delivered_day = start + timedelta(days=15)
        delivered_row = run.observation_ids.filtered(lambda item: item.day == delivered_day)
        returned_row = run.observation_ids.filtered(lambda item: item.day == return_day)
        self.assertEqual(delivered_row.units, 4.0)
        self.assertEqual(delivered_row.returned_units, 0.0)
        self.assertEqual(returned_row.units, 0.0)
        self.assertEqual(returned_row.returned_units, 1.0)

        # This return falls inside the final seven-day evaluation window. A
        # snapshot taken before it was completed must have identical demand
        # targets and evaluation results: returns never revise past deliveries.
        before_return = self._source_run(
            company,
            product,
            cutoff=datetime.combine(return_day, time.min),
            start=start,
            end=self.today,
        )
        before_snapshot, before_events = before_return._completed_sales_snapshot()
        after_snapshot = [
            {
                "day": item.day,
                "units": item.units,
            }
            for item in run.observation_ids
        ]
        self.assertEqual(before_events, 1)
        self.assertEqual(
            [(row["day"], row["units"]) for row in before_snapshot],
            [(row["day"], row["units"]) for row in after_snapshot],
        )
        before_evaluation = forecast_daily(
            [Observation(row["day"], row["units"]) for row in before_snapshot], horizon=7
        )
        after_evaluation = forecast_daily(
            [Observation(row["day"], row["units"]) for row in after_snapshot], horizon=7
        )
        self.assertEqual(before_evaluation.evaluation_days, 7)
        self.assertEqual(before_evaluation.baseline_mae, after_evaluation.baseline_mae)
        self.assertEqual(before_evaluation.ml_mae, after_evaluation.ml_mae)
        self.assertEqual(before_evaluation.predictions, after_evaluation.predictions)

    def test_source_cutoff_excludes_moves_completed_after_cutoff(self):
        company = self.env.company
        warehouse = self._warehouse(company)
        warehouse.write({"autostock_history_complete_from": self.today})
        product = self._product(company, "AS-CUTOFF")
        _, delivery = self._sale_order(company, warehouse, product, 4, state="done")
        delivered_at = fields.Datetime.to_datetime(delivery.move_ids.date)
        run = self._source_run(
            company,
            product,
            warehouse=warehouse,
            cutoff=delivered_at - timedelta(seconds=1),
        )

        snapshot, event_count = run._completed_sales_snapshot()

        self.assertEqual(event_count, 0)
        self.assertTrue(all(row["units"] == 0 for row in snapshot))

    def test_real_forecast_requires_sales_access_and_reports_short_history(self):
        company = self.env.company
        company.write({"autostock_history_complete_from": self.today})
        product = self._product(company, "AS-INSUFFICIENT")
        warehouse = self._warehouse(company)
        inventory_user = self.env["res.users"].create(
            {
                "name": "AutoStock Forecast Inventory Only",
                "login": f"autostock-forecast-stock-{product.id}",
                "company_id": company.id,
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
        with self.assertRaises(AccessError):
            self.env["autostock.forecast.run"].with_user(inventory_user).request_forecast(
                product.id, 7, self.today, self.today, False
            )

        result = self.env["autostock.forecast.run"].request_forecast(
            product.id, 7, self.today, self.today, False
        )
        run = self.env["autostock.forecast.run"].browse(result["id"])
        self.assertEqual(run.state, "insufficient_history")
        self.assertEqual(run.evaluation_status, "insufficient_history")
        self.assertFalse(run.point_ids)
        self.assertIn("At least 90", run.failure_reason)

    def test_forecast_run_creation_cannot_bypass_validated_request(self):
        with self.assertRaises(AccessError):
            self.env["autostock.forecast.run"].create({"name": "unvalidated"})

    def test_supported_forecast_horizons_are_validated(self):
        forecast_model = self.env["autostock.forecast.run"]
        for horizon in (7, 30, 60):
            self.assertEqual(forecast_model._validated_horizon(horizon), horizon)
        with self.assertRaises(ValidationError):
            forecast_model._validated_horizon(14)

    def test_multicompany_real_sources_keep_company_products_and_shared_stock_separate(self):
        company_a, company_b = self.env["res.company"].create(
            [{"name": "AutoStock Forecast Company A"}, {"name": "AutoStock Forecast Company B"}]
        )
        warehouse_a = self._warehouse(company_a)
        warehouse_b = self._warehouse(company_b)
        product_a = self._product(company_a, f"AS-A-{company_a.id}")
        product_b = self._product(company_b, f"AS-B-{company_b.id}")
        shared = self._product(self.env.company, f"AS-SHARED-{company_a.id}-{company_b.id}")
        shared.product_tmpl_id.company_id = False
        company_a.write({"autostock_history_complete_from": self.today})
        company_b.write({"autostock_history_complete_from": self.today})
        self._sale_order(company_a, warehouse_a, product_a, 3, state="done")
        self._sale_order(company_b, warehouse_b, product_b, 5, state="done")
        self._sale_order(company_a, warehouse_a, shared, 7, state="done")
        self._sale_order(company_b, warehouse_b, shared, 11, state="done")
        user = self._multi_company_user(company_a, company_b)

        def scoped_run(company, product):
            forecast_model = (
                self.env["autostock.forecast.run"]
                .with_user(user)
                .with_context(allowed_company_ids=[company_a.id, company_b.id])
                .with_company(company)
            )
            return forecast_model.new(
                {
                    "company_id": company.id,
                    "product_id": product.id,
                    "sku": product.default_code,
                    "source_type": REAL_SOURCE,
                    "history_start_date": self.today,
                    "history_end_date": self.today,
                    "source_cutoff": fields.Datetime.now() + timedelta(minutes=2),
                }
            )

        snapshot_a, _ = scoped_run(company_a, shared)._completed_sales_snapshot()
        snapshot_b, _ = scoped_run(company_b, shared)._completed_sales_snapshot()
        company_a_part, _ = scoped_run(company_a, product_a)._completed_sales_snapshot()
        self.assertEqual(snapshot_a[0]["units"], 7.0)
        self.assertEqual(snapshot_b[0]["units"], 11.0)
        self.assertEqual(company_a_part[0]["units"], 3.0)
        with self.assertRaises(AccessError):
            scoped_run(company_a, product_b)._completed_sales_snapshot()

        def scoped_options(company):
            return (
                self.env["autostock.forecast.run"]
                .with_user(user)
                .with_context(allowed_company_ids=[company_a.id, company_b.id])
                .with_company(company)
                .get_forecast_options()
            )

        products_a = {item["id"] for item in scoped_options(company_a)["products"]}
        products_b = {item["id"] for item in scoped_options(company_b)["products"]}
        self.assertEqual(products_a, {product_a.id, shared.id})
        self.assertEqual(products_b, {product_b.id, shared.id})

        # The ordinary record rule still hides Company A runs from a user assigned only to B.
        synthetic = (
            self.env["autostock.forecast.run"]
            .with_company(company_a)
            .seed_synthetic_demo("DEMO-BP-001", 7)
        )
        company_b_only = self.env["res.users"].create(
            {
                "name": "AutoStock Company B Forecast Reader",
                "login": f"autostock-company-b-reader-{company_b.id}",
                "company_id": company_b.id,
                "company_ids": [Command.set([company_b.id])],
                "group_ids": [
                    Command.set(
                        [self.env.ref("base.group_user").id, self.env.ref("stock.group_stock_user").id]
                    )
                ],
            }
        )
        hidden = self.env["autostock.forecast.run"].with_user(company_b_only).search(
            [("id", "=", synthetic["id"])]
        )
        self.assertFalse(hidden)

    def test_synthetic_worker_persists_evaluation_and_provenance_without_stock_events(self):
        stock_user = self.env["res.users"].create(
            {
                "name": "AutoStock Synthetic Forecast User",
                "login": "autostock-synthetic-forecast-user",
                "company_id": self.env.company.id,
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
        result = self.env["autostock.forecast.run"].with_user(stock_user).seed_synthetic_demo(
            "DEMO-OF-203", 7
        )
        run = self.env["autostock.forecast.run"].browse(result["id"])

        run._process_queued_run()

        run.invalidate_recordset()
        self.assertEqual(run.state, "completed", run.failure_reason)
        self.assertEqual(run.source_event_count, 0)
        self.assertEqual(run.source_type, "synthetic_demo")
        self.assertEqual(run.model_version, "autostock-demand-v2.1.0")
        self.assertTrue(run.source_snapshot_sha256)
        self.assertEqual(len(run.observation_ids), 210)
        self.assertEqual(len(run.point_ids), 7)
        self.assertTrue(run.baseline_method)
        self.assertIn("synthetic", run.data_provenance.lower())
        self.assertIn("No customer or business transaction data", run.data_provenance)
        self.assertFalse(run.product_id)

        stock_run = self.env["autostock.forecast.run"].with_user(stock_user).browse(run.id)
        with self.assertRaises(AccessError):
            stock_run.action_mark_reviewed()

        manager = self.env["res.users"].create(
            {
                "name": "AutoStock Forecast Reviewer",
                "login": "autostock-forecast-reviewer",
                "company_id": self.env.company.id,
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("stock.group_stock_manager").id,
                        ]
                    )
                ],
            }
        )
        self.env["autostock.forecast.run"].with_user(manager).browse(run.id).action_mark_reviewed()
        run.invalidate_recordset()
        self.assertEqual(run.review_status, "reviewed")
        self.assertEqual(run.reviewed_by_id, manager)
        self.assertTrue(run.reviewed_at)

    def test_demo_history_below_minimum_is_refused_without_predictions(self):
        start = self.today - timedelta(days=20)
        result = self.env["autostock.forecast.run"].seed_synthetic_demo(
            "DEMO-BP-001", 7, start, self.today
        )
        run = self.env["autostock.forecast.run"].browse(result["id"])
        self.assertEqual(run.state, "insufficient_history")
        self.assertFalse(run.point_ids)
