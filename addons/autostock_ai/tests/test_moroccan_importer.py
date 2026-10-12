"""Odoo 19 integration coverage for the isolated Moroccan fixture writer."""

from __future__ import annotations

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from scripts.moroccan_showroom.generator import FOCUS_START, generate_dataset
from scripts.moroccan_showroom.odoo_importer import OdooMoroccoImporter, run_import
from scripts.moroccan_showroom.safety import SafetyError


class TestMoroccanOdooImporter(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dataset = generate_dataset()
        importer = OdooMoroccoImporter(cls.env)
        preview = importer.plan(cls.dataset)
        cls.import_result = importer._apply_dataset(cls.dataset, preview)
        cls.company = cls.env.ref("base.main_company")
        cls.profile_model = cls.env["autostock.morocco.history.profile"]

    def _model_count(self, model_name):
        model = self.env[model_name]
        domain = [("company_id", "=", self.company.id)] if "company_id" in model._fields else []
        return model.search_count(domain)

    def test_import_uses_native_company_products_partners_and_workflows(self):
        company = self.company
        self.assertEqual(company.name, "Atlas Auto Distribution")
        self.assertEqual(company.currency_id.name, "MAD")
        self.assertEqual(company.autostock_history_complete_from, FOCUS_START)
        self.assertEqual(company.country_id.code, "MA")
        self.assertTrue(company.autostock_demo_environment)
        self.assertEqual(company.autostock_demo_dataset_version, self.dataset.version)
        self.assertEqual(self.env.ref("base.user_admin").tz, "Africa/Casablanca")

        products = self.env["product.product"].search(
            [("company_id", "=", company.id), ("autostock_enabled", "=", True)]
        )
        warehouses = self.env["stock.warehouse"].search([("company_id", "=", company.id)])
        suppliers = self.env["res.partner"].search(
            [("company_id", "=", company.id), ("supplier_rank", ">", 0)]
        )
        customers = self.env["res.partner"].search(
            [("company_id", "=", company.id), ("customer_rank", ">", 0)]
        )
        self.assertEqual(len(products), self.dataset.counts["products"])
        self.assertEqual(len(warehouses), 2)
        bootstrap_warehouse = self.env.ref("stock.warehouse0")
        self.assertEqual(bootstrap_warehouse.code, "ATC")
        self.assertEqual(bootstrap_warehouse.name, "Atlas Central Warehouse")
        self.assertEqual(len(suppliers), self.dataset.counts["suppliers"])
        self.assertEqual(len(customers), self.dataset.counts["customers"])
        self.assertEqual(len(set(products.mapped("default_code"))), len(products))

        registry = self.env["autostock.morocco.fixture"].search([])
        self.assertEqual(len(registry), self.import_result["fixture_registry_entries_created"])
        for row in registry:
            self.assertTrue(self.env[row.record_model].browse(row.record_id).exists())

        picking_model = self.env["stock.picking"]
        done_outgoing = picking_model.search(
            [("company_id", "=", company.id), ("picking_type_code", "=", "outgoing"), ("state", "=", "done")]
        )
        receipt_rows = self.env["autostock.morocco.fixture"].search(
            [("entity", "=", "incoming_receipt"), ("dataset_version", "=", self.dataset.version)]
        )
        receipt_moves = self.env["stock.move"].browse(receipt_rows.mapped("record_id"))
        receipts = receipt_moves.mapped("picking_id")
        returns = self.env["stock.move"].search(
            [
                ("company_id", "=", company.id),
                ("state", "=", "done"),
                ("origin_returned_move_id", "!=", False),
            ]
        )
        transfers = self.env["stock.move"].search(
            [
                ("company_id", "=", company.id),
                ("state", "=", "done"),
                ("location_id.usage", "=", "internal"),
                ("location_dest_id.usage", "=", "internal"),
                ("picking_id.picking_type_id.code", "=", "internal"),
            ]
        )
        self.assertEqual(len(receipt_moves), self.dataset.counts["receipt_pickings"])
        self.assertEqual(len(receipts), self.dataset.counts["receipt_pickings"])
        self.assertTrue(all(picking.state == "done" for picking in receipts))
        self.assertEqual(len(returns), self.dataset.counts["linked_customer_returns"])
        self.assertEqual(len(transfers), self.dataset.counts["internal_transfer_journeys"])
        for original_move in returns.mapped("origin_returned_move_id"):
            returned_quantity = sum(
                returned.product_uom._compute_quantity(returned.quantity, original_move.product_uom)
                for returned in original_move.returned_move_ids.filtered(
                    lambda move: move.state == "done"
                )
            )
            self.assertLessEqual(
                returned_quantity,
                original_move.quantity + original_move.product_uom.rounding / 2,
            )
        self.assertEqual(
            len(done_outgoing),
            self.dataset.counts["focus_completed_orders"] + self.dataset.counts["history_orders_before_focus"],
        )
        self.assertTrue(all(move.origin_returned_move_id.state == "done" for move in returns))

        open_orders = self.env["sale.order"].search(
            [("company_id", "=", company.id), ("client_order_ref", "like", "SO-MA-OPEN-%"), ("state", "=", "sale")]
        )
        self.assertEqual(len(open_orders), self.dataset.counts["open_customer_orders"])
        self.assertTrue(
            all(
                picking.state != "done"
                for order in open_orders
                for picking in order.picking_ids.filtered(lambda row: row.picking_type_code == "outgoing")
            )
        )

    def test_ledger_reconciles_and_fixture_dates_do_not_rewrite_audit_dates(self):
        Product = self.env["product.product"]
        Warehouse = self.env["stock.warehouse"]
        for profile_data in self.dataset.history_profiles:
            product = Product.search([("default_code", "=", profile_data["sku"])], limit=1)
            profile = self.profile_model.search(
                [("company_id", "=", self.company.id), ("product_id", "=", product.id)], limit=1
            )
            self.assertTrue(profile)
            self.assertEqual(profile.state, "verified")
            product_created = fields.Datetime.to_datetime(product.create_date).date()
            self.assertGreater(product_created, profile.history_start_date)
            self.assertEqual(profile.calendar_days, 181)
            self.assertEqual(profile.source_move_count, profile.source_delivery_count + profile.source_return_count)
            self.assertEqual(len(profile.source_move_sha256), 64)

        expected = {
            (row["sku"], row["warehouse_key"]): row["on_hand"]
            for row in self.dataset.ending_on_hand
        }
        for product_data in self.dataset.products:
            product = Product.search([("default_code", "=", product_data.sku)], limit=1)
            for warehouse_data in self.dataset.warehouses:
                warehouse = Warehouse.search(
                    [("company_id", "=", self.company.id), ("code", "=", warehouse_data["code"])], limit=1
                )
                on_hand = product.with_company(self.company).with_context(
                    allowed_company_ids=[self.company.id], warehouse_id=warehouse.id
                ).qty_available
                self.assertAlmostEqual(
                    on_hand,
                    expected[(product_data.sku, warehouse_data["key"])],
                    delta=product.uom_id.rounding / 2,
                )

        SaleOrder = self.env["sale.order"]
        for order in self.dataset.orders:
            record = SaleOrder.search(
                [("company_id", "=", self.company.id), ("client_order_ref", "=", order.key)], limit=1
            )
            self.assertTrue(record)
            picking = record.picking_ids.filtered(lambda row: row.picking_type_code == "outgoing").ensure_one()
            self.assertLessEqual(record.date_order, picking.date_done)
            self.assertEqual(fields.Datetime.to_datetime(picking.date_done).date(), order.day)
            self.assertGreater(fields.Datetime.to_datetime(record.create_date).date(), order.day)

    def test_saved_7_30_60_forecasts_use_verified_delivery_moves_and_stay_unreviewed(self):
        profile = self.profile_model.search(
            [("company_id", "=", self.company.id)], order="product_id", limit=1
        )
        self.assertTrue(profile)
        Forecast = self.env["autostock.forecast.run"]
        runs = Forecast.search(
            [
                ("company_id", "=", self.company.id),
                ("demo_history_profile_id", "=", profile.id),
            ],
            order="horizon_days, id",
        )
        self.assertEqual({int(run.horizon_days) for run in runs}, {7, 30, 60})
        self.assertEqual(len(runs), 3)
        for run in runs:
            self.assertEqual(run.state, "queued")
            self.assertEqual(run.review_status, "unreviewed")
            self.assertEqual(run.demo_dataset_version, self.dataset.version)
            run._process_queued_run()
            self.assertEqual(run.state, "completed", run.failure_reason)
            self.assertEqual(run.history_days, 181)
            self.assertEqual(len(run.observation_ids), 181)
            self.assertEqual(run.review_status, "unreviewed")
            self.assertIn("Fictional Moroccan showroom fixture", run.data_provenance)

        ordinary_product = self.env["product.product"].search(
            [
                ("company_id", "=", self.company.id),
                ("autostock_enabled", "=", True),
                ("id", "not in", self.profile_model.search([]).mapped("product_id").ids),
            ],
            limit=1,
        )
        self.assertTrue(ordinary_product)
        with self.assertRaisesRegex(UserError, "before this product existed in Odoo"):
            Forecast.request_forecast(
                ordinary_product.id,
                horizon_days=7,
                history_start=profile.history_start_date,
                history_end=profile.history_end_date,
            )
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company.id)], limit=1
        )
        with self.assertRaisesRegex(UserError, "before this product existed in Odoo"):
            Forecast.request_forecast(
                profile.product_id.id,
                horizon_days=7,
                history_start=profile.history_start_date,
                history_end=profile.history_end_date,
                warehouse_id=warehouse.id,
            )

    def test_history_revision_invalidates_a_queued_profile_snapshot(self):
        run = self.env["autostock.forecast.run"].search(
            [
                ("company_id", "=", self.company.id),
                ("demo_history_profile_id", "!=", False),
                ("state", "=", "queued"),
            ],
            limit=1,
        )
        self.assertTrue(run)
        profile = run.demo_history_profile_id
        source_move = self.env["stock.move"].search(
            [
                ("company_id", "=", self.company.id),
                ("product_id", "=", profile.product_id.id),
                ("state", "=", "done"),
                ("sale_line_id", "!=", False),
                ("date", ">=", fields.Datetime.to_datetime(profile.history_start_date)),
            ],
            order="date, id",
            limit=1,
        )
        self.assertTrue(source_move)
        source_move.write(
            {
                "date": fields.Datetime.to_string(
                    fields.Datetime.to_datetime(source_move.date) + timedelta(days=1)
                )
            }
        )
        with self.assertRaisesRegex(UserError, "source history changed"):
            profile._verify_for_run(run)

    def test_repeated_import_is_a_noop_and_does_not_duplicate_transactions(self):
        counts_before = {
            model: self._model_count(model)
            for model in (
                "sale.order",
                "stock.picking",
                "stock.move",
                "autostock.morocco.history.profile",
                "autostock.forecast.run",
                "autostock.morocco.fixture",
            )
        }
        importer = OdooMoroccoImporter(self.env)
        plan = importer.plan(self.dataset)
        self.assertEqual(plan.counts["create"], 0)
        self.assertEqual(plan.counts["unchanged"], len(plan.actions))
        result = importer._apply_dataset(self.dataset, plan)
        self.assertEqual(result["mode"], "apply-noop")
        self.assertEqual(result["database_mutations"], 0)
        counts_after = {
            model: self._model_count(model)
            for model in counts_before
        }
        self.assertEqual(counts_after, counts_before)

    def test_public_apply_stays_fail_closed_and_does_not_write(self):
        counts_before = {
            model: self._model_count(model)
            for model in ("sale.order", "stock.picking", "stock.move", "autostock.morocco.fixture")
        }
        with self.assertRaisesRegex(SafetyError, "typing the exact prepared target UUID"):
            run_import(self.env, self.dataset, mode="apply")
        counts_after = {
            model: self._model_count(model)
            for model in counts_before
        }
        self.assertEqual(counts_after, counts_before)

    def test_odoo_preview_is_read_only_for_an_already_imported_target(self):
        report = run_import(self.env, self.dataset, mode="dry-run")
        self.assertTrue(report["connected_to_odoo"])
        self.assertEqual(report["mode"], "odoo-dry-run")
        self.assertEqual(report["database_mutations"], 0)
        self.assertEqual(report["forecast_runs_created"], 0)
        self.assertEqual(report["entry_actions"]["create"], 0)
        registry_count = self.env["autostock.morocco.fixture"].search_count([])
        self.assertEqual(report["planned_entries"], registry_count)
        self.assertEqual(report["entry_actions"]["unchanged"], registry_count)
