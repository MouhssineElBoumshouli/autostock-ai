"""Odoo 19 integration coverage for the isolated Moroccan fixture writer."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

from ml.inventory_risk import forecast_eligibility
from scripts.moroccan_showroom.generator import FOCUS_START, MISSING_SUPPLIER_SKU, generate_dataset
from scripts.moroccan_showroom.odoo_importer import OdooImportError, OdooMoroccoImporter, run_import
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

    def _warehouse(self, key):
        warehouse_data = next(row for row in self.dataset.warehouses if row["key"] == key)
        return self.env["stock.warehouse"].search(
            [("company_id", "=", self.company.id), ("code", "=", warehouse_data["code"])],
            limit=1,
        )

    def _review_manager(self):
        manager = self.env["res.users"].create(
            {
                "name": "Moroccan warehouse forecast reviewer",
                "login": f"morocco-warehouse-reviewer-{self.cr.dbname}",
                "company_id": self.company.id,
                "company_ids": [Command.set([self.company.id])],
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("stock.group_stock_manager").id,
                            self.env.ref("sales_team.group_sale_manager").id,
                        ]
                    )
                ],
            }
        )
        self.assertFalse(manager.with_user(manager).has_group("base.group_system"))
        return manager

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
            warehouse = (
                Warehouse.search(
                    [
                        ("company_id", "=", self.company.id),
                        ("code", "=", next(
                            row["code"] for row in self.dataset.warehouses
                            if row["key"] == profile_data["warehouse_key"]
                        )),
                    ],
                    limit=1,
                )
                if profile_data["warehouse_key"]
                else self.env["stock.warehouse"]
            )
            profile = self.profile_model.search(
                [
                    ("company_id", "=", self.company.id),
                    ("product_id", "=", product.id),
                    ("warehouse_id", "=", warehouse.id if warehouse else False),
                    ("profile_key", "=", profile_data["key"]),
                ],
                limit=1,
            )
            self.assertTrue(profile)
            self.assertEqual(profile.state, "verified")
            self.assertEqual(profile.warehouse_id, warehouse)
            product_created = fields.Datetime.to_datetime(product.create_date).date()
            self.assertGreater(product_created, profile.history_start_date)
            self.assertEqual(profile.calendar_days, 181)
            self.assertEqual(profile.source_move_count, profile.source_delivery_count + profile.source_return_count)
            self.assertEqual(len(profile.source_move_sha256), 64)
            summary = self.env["autostock.forecast.run"]._morocco_source_summary(
                self.company,
                product,
                profile.history_start_date,
                profile.history_end_date,
                fields.Datetime.now(),
                warehouse=warehouse,
                dataset_version=self.dataset.version,
            )
            self.assertEqual(summary["scope"]["warehouse_id"], warehouse.id if warehouse else False)
            self.assertEqual(summary["source_move_count"], profile.source_move_count)
            self.assertEqual(summary["return_count"], profile.source_return_count)
            self.assertEqual(summary["delivery_count"], profile.source_delivery_count)
            self.assertTrue(profile._matches_history(
                self.company,
                product,
                profile.history_start_date,
                profile.history_end_date,
                warehouse=warehouse,
            ))

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
            self.assertEqual(fields.Datetime.to_datetime(record.date_order).date(), order.day)
            self.assertEqual(fields.Datetime.to_datetime(picking.date_done).date(), order.day)
            self.assertGreater(fields.Datetime.to_datetime(record.create_date).date(), order.day)

    def test_missing_supplier_example_is_visible_without_vendor_or_order_claims(self):
        product = self.env["product.product"].search(
            [("company_id", "=", self.company.id), ("default_code", "=", MISSING_SUPPLIER_SKU)],
            limit=1,
        )
        self.assertTrue(product)
        self.assertFalse(product.product_tmpl_id.seller_ids)
        self.assertFalse(
            self.env["sale.order.line"].search_count(
                [("company_id", "=", self.company.id), ("product_id", "=", product.id)]
            )
        )
        moves = self.env["stock.move"].search(
            [("company_id", "=", self.company.id), ("product_id", "=", product.id), ("state", "=", "done")]
        )
        self.assertEqual(len(moves), 2)
        self.assertTrue(all(move.location_id.usage == "inventory" for move in moves))
        self.assertFalse(
            moves.filtered(lambda move: move.location_id.usage == "supplier" or move.origin_returned_move_id)
        )

        gaps = self.env["autostock.supplier.catalog"].get_supplier_gaps(
            query=MISSING_SUPPLIER_SKU, page=1, page_size=10
        )
        self.assertEqual(gaps["pagination"]["total_count"], 1)
        row = gaps["items"][0]
        self.assertEqual(row["sku"], MISSING_SUPPLIER_SKU)
        self.assertEqual(row["supplier_terms_count"], 0)
        self.assertFalse(row["lead_time_min_days"])
        self.assertFalse(row["reorder_parts"])
        self.assertEqual(row["reorder_locations"], [])
        self.assertNotIn("price", row)

    def test_reviewed_forecast_allows_repeat_preview_but_stales_after_source_change(self):
        run = self.env["autostock.forecast.run"].search(
            [
                ("company_id", "=", self.company.id),
                ("demo_history_profile_id", "!=", False),
                ("warehouse_id", "=", False),
                ("state", "=", "queued"),
            ],
            limit=1,
        )
        self.assertTrue(run)
        run._process_queued_run()
        run.invalidate_recordset()
        self.assertEqual(run.state, "completed", run.failure_reason)
        manager = self.env["res.users"].create(
            {
                "name": "Moroccan fixture forecast reviewer",
                "login": f"morocco-forecast-reviewer-{self.cr.dbname}",
                "company_id": self.company.id,
                "company_ids": [Command.set([self.company.id])],
                "tz": "Europe/Paris",
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("stock.group_stock_manager").id,
                            self.env.ref("sales_team.group_sale_manager").id,
                        ]
                    )
                ],
            }
        )
        self.assertFalse(manager.with_user(manager).has_group("base.group_system"))
        scoped_run = run.with_user(manager).with_company(self.company).with_context(
            allowed_company_ids=[self.company.id]
        )
        scoped_run.action_mark_reviewed()
        scoped_run.invalidate_recordset()
        reviewed_at = scoped_run.reviewed_at
        self.assertEqual(scoped_run.review_status, "reviewed")
        self.assertTrue(scoped_run._demo_source_history_is_current())
        self.assertEqual(scoped_run.reviewed_by_id, manager)
        manager.write({"tz": "America/New_York"})

        # A manager review and normal user timezone preferences are legitimate
        # lifecycle changes, not mutations of the pinned showroom fixture.
        administrator = self.env.ref("base.user_admin")
        administrator.write({"tz": "America/Toronto"})
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
        preview_report = run_import(self.env, self.dataset, mode="dry-run")
        registry_count = self.env["autostock.morocco.fixture"].search_count([])
        self.assertEqual(preview_report["database_mutations"], 0)
        self.assertEqual(preview_report["forecast_runs_created"], 0)
        self.assertEqual(preview_report["entry_actions"]["create"], 0)
        self.assertEqual(preview_report["planned_entries"], registry_count)
        self.assertEqual(preview_report["entry_actions"]["unchanged"], registry_count)

        importer = OdooMoroccoImporter(self.env)
        repeat_preview = importer.plan(self.dataset)
        no_op = importer._apply_dataset(self.dataset, repeat_preview)
        self.assertEqual(no_op["mode"], "apply-noop")
        self.assertEqual(no_op["database_mutations"], 0)
        self.assertEqual(no_op["unchanged"], registry_count)
        self.assertEqual(
            {
                model: self._model_count(model)
                for model in counts_before
            },
            counts_before,
        )
        self.assertEqual(administrator.tz, "America/Toronto")
        scoped_run.invalidate_recordset()
        self.assertEqual(scoped_run.review_status, "reviewed")
        self.assertEqual(scoped_run.reviewed_at, reviewed_at)
        self.assertEqual(scoped_run.reviewed_by_id, manager)

        # The audit still rejects forged or incomplete review/result state.
        with self.assertRaisesRegex(
            OdooImportError, "reviewed forecast is missing its manager audit metadata"
        ):
            with self.cr.savepoint():
                run._write_worker({"reviewed_by_id": False, "reviewed_at": False})
                OdooMoroccoImporter(self.env).plan(self.dataset)
        self.env.invalidate_all()
        scoped_run = run.with_user(manager).with_company(self.company).with_context(
            allowed_company_ids=[self.company.id]
        )
        with self.assertRaisesRegex(OdooImportError, "only a completed forecast can be reviewed"):
            with self.cr.savepoint():
                run._write_worker({"state": "queued"})
                OdooMoroccoImporter(self.env).plan(self.dataset)
        self.env.invalidate_all()
        scoped_run = run.with_user(manager).with_company(self.company).with_context(
            allowed_company_ids=[self.company.id]
        )
        with self.assertRaisesRegex(
            OdooImportError, "completed forecast result points are missing or incomplete"
        ):
            with self.cr.savepoint():
                run.point_ids[:1].unlink()
                OdooMoroccoImporter(self.env).plan(self.dataset)
        self.env.invalidate_all()
        scoped_run = run.with_user(manager).with_company(self.company).with_context(
            allowed_company_ids=[self.company.id]
        )
        self.assertEqual(scoped_run.review_status, "reviewed")
        self.assertEqual(scoped_run.reviewed_at, reviewed_at)
        self.assertEqual(manager.tz, "America/New_York")

        def eligible_with_current_source(source_current):
            today = fields.Date.to_date(scoped_run.history_end_date) + timedelta(days=1)
            run_snapshot = {
                "company_id": scoped_run.company_id.id,
                "product_id": scoped_run.product_id.id,
                "warehouse_id": 0,
                "source_type": scoped_run.source_type,
                "state": scoped_run.state,
                "evaluation_status": scoped_run.evaluation_status,
                "review_status": scoped_run.review_status,
                "horizon_days": int(scoped_run.horizon_days),
                "evaluation_days": scoped_run.evaluation_days,
                "history_days": scoped_run.history_days,
                "nonzero_days": scoped_run.nonzero_days,
                "history_end_date": scoped_run.history_end_date,
                "source_cutoff": scoped_run.source_cutoff,
            }
            return forecast_eligibility(
                run_snapshot,
                company_id=scoped_run.company_id.id,
                product_id=scoped_run.product_id.id,
                warehouse_id=0,
                lead_time_days=0,
                today=today,
                now=fields.Datetime.to_datetime(scoped_run.source_cutoff),
                point_dates=[],
                source_current=source_current,
            )

        current_ok, current_reason = eligible_with_current_source(
            scoped_run._demo_source_history_is_current()
        )
        self.assertTrue(current_ok, current_reason)

        unrelated_product = self.env["product.product"].search(
            [
                ("company_id", "=", self.company.id),
                ("autostock_enabled", "=", True),
                ("id", "!=", scoped_run.product_id.id),
            ],
            limit=1,
        )
        unrelated_move = self.env["stock.move"].search(
            [
                ("company_id", "=", self.company.id),
                ("product_id", "=", unrelated_product.id),
                ("state", "=", "done"),
                ("sale_line_id", "!=", False),
            ],
            limit=1,
        )
        self.assertTrue(unrelated_move)
        old_unrelated_date = unrelated_move.date
        unrelated_move.write(
            {"date": fields.Datetime.to_string(fields.Datetime.to_datetime(old_unrelated_date) + timedelta(days=1))}
        )
        self.assertTrue(scoped_run._demo_source_history_is_current())
        unrelated_move.write({"date": old_unrelated_date})

        source_move = self.env["stock.move"].search(
            [
                ("company_id", "=", self.company.id),
                ("product_id", "=", scoped_run.product_id.id),
                ("state", "=", "done"),
                ("sale_line_id", "!=", False),
                ("sale_line_id.order_id.state", "in", ["sale", "done"]),
                ("location_id.usage", "=", "internal"),
                ("location_dest_id.usage", "=", "customer"),
                ("date", ">=", fields.Datetime.to_datetime(scoped_run.history_start_date)),
                (
                    "date",
                    "<",
                    fields.Datetime.to_datetime(scoped_run.history_end_date) + timedelta(days=1),
                ),
                ("date", "<=", fields.Datetime.to_datetime(scoped_run.source_cutoff)),
            ],
            order="date, id",
            limit=1,
        )
        self.assertTrue(source_move)
        source_move.write(
            {"date": fields.Datetime.to_string(fields.Datetime.to_datetime(source_move.date) + timedelta(days=1))}
        )
        current_ok, current_reason = eligible_with_current_source(
            scoped_run._demo_source_history_is_current()
        )
        self.assertFalse(current_ok)
        self.assertIn("saved history no longer matches", current_reason)
        with self.assertRaisesRegex(OdooImportError, "Actual Odoo state drift"):
            OdooMoroccoImporter(self.env).plan(self.dataset)
        self.assertEqual(scoped_run.state, "completed")
        self.assertEqual(scoped_run.review_status, "reviewed")
        self.assertEqual(scoped_run.reviewed_at, reviewed_at)

    def test_repeat_import_detects_live_odoo_field_drift(self):
        importer = OdooMoroccoImporter(self.env)
        clean_preview = importer.plan(self.dataset)

        product_data = self.dataset.products[0]
        product = self.env["product.product"].search(
            [("company_id", "=", self.company.id), ("default_code", "=", product_data.sku)],
            limit=1,
        )
        original_price = product.list_price
        product.write({"list_price": original_price + 1})
        with self.assertRaisesRegex(OdooImportError, "Actual Odoo state drift.*sale price"):
            importer.plan(self.dataset)
        with self.assertRaisesRegex(OdooImportError, "Actual Odoo state drift.*sale price"):
            importer._apply_dataset(self.dataset, clean_preview)
        product.write({"list_price": original_price})

        term = product.product_tmpl_id.seller_ids[:1]
        original_vendor_price = term.price
        term.write({"price": original_vendor_price + 1})
        with self.assertRaisesRegex(OdooImportError, "Actual Odoo state drift.*vendor price"):
            importer.plan(self.dataset)
        term.write({"price": original_vendor_price})

        focus_movement = next(
            item for item in self.dataset.movements
            if item.kind == "sale_delivery" and item.sku not in {row["sku"] for row in self.dataset.history_profiles}
        )
        move = self.env["stock.move"].browse(
            self.env["autostock.morocco.fixture"].search(
                [("entity", "=", "sale_delivery_move_plan"), ("fixture_key", "=", f"sale_delivery_move_plan:{focus_movement.key}")],
                limit=1,
            ).record_id
        )
        original_move_date = move.date
        move.write({"date": fields.Datetime.to_string(fields.Datetime.to_datetime(original_move_date) + timedelta(days=1))})
        with self.assertRaisesRegex(OdooImportError, "Actual Odoo state drift.*business movement date"):
            importer.plan(self.dataset)
        move.write({"date": original_move_date})

        sale_line = self.env["sale.order.line"].browse(
            self.env["autostock.morocco.fixture"].search(
                [("entity", "=", "completed_sale_line")], limit=1
            ).record_id
        )
        original_quantity = sale_line.product_uom_qty
        sale_line.write({"product_uom_qty": original_quantity + 1})
        with self.assertRaisesRegex(OdooImportError, "Actual Odoo state drift.*sale product, quantity"):
            importer.plan(self.dataset)
        sale_line.write({"product_uom_qty": original_quantity})

    def test_repeat_import_detects_broken_return_link(self):
        importer = OdooMoroccoImporter(self.env)
        return_move = self.env["stock.move"].browse(
            self.env["autostock.morocco.fixture"].search(
                [("entity", "=", "linked_return")], limit=1
            ).record_id
        )
        original_delivery = return_move.origin_returned_move_id
        self.assertTrue(original_delivery)
        return_move.write({"origin_returned_move_id": False})
        with self.assertRaisesRegex(OdooImportError, "Actual Odoo state drift.*return link"):
            importer.plan(self.dataset)
        # The isolated TransactionCase rolls this deliberate workflow mutation back.

    def test_repeat_import_detects_current_stock_quant_drift(self):
        product = self.env["product.product"].search(
            [("company_id", "=", self.company.id), ("default_code", "=", self.dataset.products[0].sku)],
            limit=1,
        )
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company.id), ("code", "=", self.dataset.warehouses[0]["code"])],
            limit=1,
        )
        self.env["stock.quant"].with_company(self.company)._update_available_quantity(
            product, warehouse.lot_stock_id, 1
        )
        with self.assertRaisesRegex(OdooImportError, "Actual Odoo state drift.*stock ledger drift"):
            OdooMoroccoImporter(self.env).plan(self.dataset)

    def test_repeat_import_detects_unregistered_fixture_prefixed_records(self):
        self.env["product.template"].with_company(self.company).create(
            {
                "name": "Unregistered Moroccan fixture conflict",
                "default_code": "AT-MA-ORPHAN-999",
                "company_id": self.company.id,
                "is_storable": True,
            }
        )
        with self.assertRaisesRegex(OdooImportError, "unregistered or missing fixture-prefixed products"):
            OdooMoroccoImporter(self.env).plan(self.dataset)

        self.env["product.template"].create(
            {
                "name": "Unregistered shared fixture conflict",
                "default_code": "AT-MA-ORPHAN-SHARED-998",
                "company_id": False,
                "is_storable": True,
            }
        )
        with self.assertRaisesRegex(OdooImportError, "unregistered or missing fixture-prefixed products"):
            OdooMoroccoImporter(self.env).plan(self.dataset)

    def test_repeat_import_detects_missing_registered_odoo_record(self):
        registry = self.env["autostock.morocco.fixture"].search(
            [("entity", "=", "supplier_term")], limit=1
        )
        self.env[registry.record_model].browse(registry.record_id).unlink()
        with self.assertRaisesRegex(OdooImportError, "Actual Odoo state drift.*registered Odoo record is missing"):
            OdooMoroccoImporter(self.env).plan(self.dataset)

    def test_saved_7_30_60_forecasts_use_verified_delivery_moves_and_stay_unreviewed(self):
        profile = self.profile_model.search(
            [
                ("company_id", "=", self.company.id),
                ("warehouse_id", "=", False),
            ],
            order="product_id",
            limit=1,
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
            self.assertEqual(run.created_by_id, self.env.ref("base.user_admin"))
            self.assertTrue(run.created_by_id.active)
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
        scoped_product_ids = self.profile_model.search(
            [("company_id", "=", self.company.id), ("warehouse_id", "!=", False)]
        ).mapped("product_id").ids
        company_only_profile = self.profile_model.search(
            [
                ("company_id", "=", self.company.id),
                ("warehouse_id", "=", False),
                ("product_id", "not in", scoped_product_ids),
            ],
            limit=1,
        )
        self.assertTrue(company_only_profile)
        warehouse = self._warehouse("warehouse_atlas_central")
        with self.assertRaisesRegex(UserError, "before this product existed in Odoo"):
            Forecast.request_forecast(
                company_only_profile.product_id.id,
                horizon_days=7,
                history_start=company_only_profile.history_start_date,
                history_end=company_only_profile.history_end_date,
                warehouse_id=warehouse.id,
            )

    def test_warehouse_profiles_are_verified_against_exact_native_deliveries_and_returns(self):
        profiles = self.profile_model.search(
            [("company_id", "=", self.company.id), ("warehouse_id", "!=", False)],
            order="product_id, warehouse_id",
        )
        self.assertEqual(len(profiles), self.dataset.counts["warehouse_history_profiles"])
        expected_profiles = {row["key"]: row for row in self.dataset.history_profiles}
        expected_warehouses = {
            self._warehouse("warehouse_atlas_central").id,
            self._warehouse("warehouse_south_depot").id,
        }
        self.assertEqual(set(profiles.mapped("warehouse_id").ids), expected_warehouses)

        Forecast = self.env["autostock.forecast.run"]
        StockMove = self.env["stock.move"]
        observations_by_scope = {}
        for profile in profiles:
            planned = expected_profiles[profile.profile_key]
            warehouse = profile.warehouse_id
            product = profile.product_id
            self.assertEqual(profile.company_id, self.company)
            self.assertEqual(profile.dataset_version, self.dataset.version)
            self.assertEqual(profile.history_start_date, date(2026, 4, 13))
            self.assertEqual(profile.history_end_date, date(2026, 10, 10))
            self.assertEqual(profile.calendar_days, 181)

            summary = Forecast._morocco_source_summary(
                self.company,
                product,
                profile.history_start_date,
                profile.history_end_date,
                fields.Datetime.now(),
                warehouse=warehouse,
                dataset_version=self.dataset.version,
            )
            self.assertEqual(summary["scope"]["company_id"], self.company.id)
            self.assertEqual(summary["scope"]["product_id"], product.id)
            self.assertEqual(summary["scope"]["warehouse_id"], warehouse.id)
            self.assertEqual(summary["scope"]["dataset_version"], self.dataset.version)
            self.assertEqual(summary["source_move_count"], planned["planned_qualifying_move_count"])
            self.assertEqual(summary["delivery_count"], planned["planned_delivery_move_count"])
            self.assertEqual(summary["return_count"], planned["planned_return_move_count"])
            self.assertTrue(
                profile._matches_history(
                    self.company,
                    product,
                    profile.history_start_date,
                    profile.history_end_date,
                    warehouse=warehouse,
                )
            )

            start_utc = fields.Datetime.to_datetime(profile.history_start_date)
            end_utc = start_utc + timedelta(days=profile.calendar_days)
            deliveries = StockMove.search(
                [
                    ("company_id", "=", self.company.id),
                    ("product_id", "=", product.id),
                    ("state", "=", "done"),
                    ("sale_line_id", "!=", False),
                    ("picking_id.picking_type_id.warehouse_id", "=", warehouse.id),
                    ("sale_line_id.order_id.state", "in", ["sale", "done"]),
                    ("location_id.usage", "=", "internal"),
                    ("location_dest_id.usage", "=", "customer"),
                    ("date", ">=", start_utc),
                    ("date", "<", end_utc),
                ],
                order="date, id",
            )
            self.assertEqual(len(deliveries), profile.source_delivery_count)
            self.assertTrue(
                all(
                    move.picking_id.picking_type_id.warehouse_id == warehouse
                    and move.location_id.usage == "internal"
                    and move.location_dest_id.usage == "customer"
                    for move in deliveries
                )
            )
            returns = StockMove.search(
                [
                    ("company_id", "=", self.company.id),
                    ("product_id", "=", product.id),
                    ("state", "=", "done"),
                    ("origin_returned_move_id", "in", deliveries.ids),
                    ("date", ">=", start_utc),
                    ("date", "<", end_utc),
                ],
                order="date, id",
            )
            self.assertEqual(len(returns), profile.source_return_count)
            for returned in returns:
                original = returned.origin_returned_move_id
                self.assertIn(original, deliveries)
                self.assertEqual(original.picking_id.picking_type_id.warehouse_id, warehouse)
                self.assertEqual(returned.location_id.usage, "customer")
                self.assertEqual(returned.location_dest_id, original.location_id)
                self.assertEqual(returned.picking_id.state, "done")

            runs = Forecast.search(
                [
                    ("company_id", "=", self.company.id),
                    ("product_id", "=", product.id),
                    ("warehouse_id", "=", warehouse.id),
                    ("demo_history_profile_id", "=", profile.id),
                ],
                order="horizon_days, id",
            )
            self.assertEqual({int(run.horizon_days) for run in runs}, {7, 30, 60})
            self.assertEqual(len(runs), 3)
            for run in runs:
                self.assertEqual(run.company_id, self.company)
                self.assertEqual(run.product_id, product)
                self.assertEqual(run.warehouse_id, warehouse)
                self.assertEqual(run.demo_dataset_version, self.dataset.version)
                self.assertEqual(run.review_status, "unreviewed")
                run._process_queued_run()
                run.invalidate_recordset()
                self.assertEqual(run.state, "completed", run.failure_reason)
                self.assertIn(
                    run.evaluation_status,
                    {"evaluated", "baseline_only", "intermittent_baseline"},
                )
                self.assertEqual(run.history_days, 181)
                self.assertEqual(run.nonzero_days, planned["planned_nonzero_delivery_days"])
                self.assertEqual(len(run.observation_ids), 181)
                self.assertEqual(len(run.point_ids), int(run.horizon_days))
                self.assertEqual(run.point_ids[0].day, date(2026, 10, 11))
                self.assertEqual(
                    run.point_ids[-1].day,
                    date(2026, 10, 10) + timedelta(days=int(run.horizon_days)),
                )
                self.assertEqual(run.review_status, "unreviewed")
                self.assertIn("Fictional Moroccan showroom fixture", run.data_provenance)
                if int(run.horizon_days) == 30:
                    observations_by_scope[(product.default_code, warehouse.id)] = run.source_snapshot_sha256

        for sku in {row["sku"] for row in expected_profiles.values() if row["warehouse_key"]}:
            atc = self._warehouse("warehouse_atlas_central")
            asd = self._warehouse("warehouse_south_depot")
            self.assertNotEqual(
                observations_by_scope[(sku, atc.id)],
                observations_by_scope[(sku, asd.id)],
            )

    def test_manager_review_and_risk_evidence_remain_warehouse_exact_and_freshness_bounded(self):
        sku = "AT-MA-FLT-101"
        product = self.env["product.product"].search(
            [("company_id", "=", self.company.id), ("default_code", "=", sku)], limit=1
        )
        atc = self._warehouse("warehouse_atlas_central")
        asd = self._warehouse("warehouse_south_depot")
        company_profile = self.profile_model.search(
            [
                ("company_id", "=", self.company.id),
                ("product_id", "=", product.id),
                ("warehouse_id", "=", False),
            ],
            limit=1,
        )
        profiles = {
            False: company_profile,
            atc.id: self.profile_model.search(
                [("company_id", "=", self.company.id), ("product_id", "=", product.id), ("warehouse_id", "=", atc.id)],
                limit=1,
            ),
            asd.id: self.profile_model.search(
                [("company_id", "=", self.company.id), ("product_id", "=", product.id), ("warehouse_id", "=", asd.id)],
                limit=1,
            ),
        }
        self.assertTrue(all(profiles.values()))

        Forecast = self.env["autostock.forecast.run"]
        runs = {}
        for warehouse_id, profile in profiles.items():
            run = Forecast.search(
                [
                    ("company_id", "=", self.company.id),
                    ("product_id", "=", product.id),
                    ("warehouse_id", "=", warehouse_id or False),
                    ("demo_history_profile_id", "=", profile.id),
                    ("horizon_days", "=", "30"),
                ],
                limit=1,
            )
            self.assertTrue(run)
            if run.state == "queued":
                run._process_queued_run()
                run.invalidate_recordset()
            self.assertEqual(run.state, "completed", run.failure_reason)
            runs[warehouse_id] = run

        manager = self._review_manager()
        for run in runs.values():
            run.with_user(manager).with_company(self.company).with_context(
                allowed_company_ids=[self.company.id]
            ).action_mark_reviewed()
            run.invalidate_recordset()
            self.assertEqual(run.review_status, "reviewed")
            self.assertEqual(run.reviewed_by_id, manager)
            self.assertTrue(run.reviewed_at)
            self.assertTrue(run._demo_source_history_is_current())

        StockMove = self.env["stock.move"]
        manager_forecast_service = Forecast.with_user(manager).with_company(self.company).with_context(
            allowed_company_ids=[self.company.id]
        )
        current_detail = manager_forecast_service.get_forecast_detail(runs[atc.id].id)
        self.assertEqual(current_detail["run"]["warehouse_id"], atc.id)
        self.assertTrue(current_detail["history_coverage"]["verified_demo_profile_scoped"])
        self.assertTrue(current_detail["history_coverage"]["verified_demo_profile_current"])

        Risk = self.env["autostock.inventory.risk"].with_user(manager).with_company(self.company).with_context(
            allowed_company_ids=[self.company.id]
        )
        today = fields.Date.today()
        now = fields.Datetime.to_datetime(fields.Datetime.now())
        for warehouse in (atc, asd):
            exact_run = runs[warehouse.id].with_user(manager).with_company(self.company).with_context(
                allowed_company_ids=[self.company.id]
            )
            selected, points, usable, reason = Risk._forecast_for_pair(
                exact_run,
                company=self.company,
                product=product,
                warehouse=warehouse,
                lead_days=7,
                today=today,
                now=now,
            )
            history_age = (today - exact_run.history_end_date).days
            history_fresh = 0 <= history_age <= 14
            cutoff_age = now - fields.Datetime.to_datetime(exact_run.source_cutoff)
            point_days = set(points.mapped("day"))
            required_days = {
                today + timedelta(days=offset)
                for offset in range(1, 8)
            }
            result_window_covered = required_days <= point_days
            should_be_usable = (
                history_fresh
                and timedelta(0) <= cutoff_age <= timedelta(days=14)
                and result_window_covered
            )
            self.assertEqual(usable, should_be_usable, reason)
            self.assertEqual(selected, exact_run)
            if usable:
                self.assertEqual(selected.warehouse_id, warehouse)
                self.assertEqual(len(points), 30)
            else:
                self.assertFalse(usable)

            risk_snapshot = Risk.get_risk_data(
                warehouse_id=warehouse.id,
                product_id=product.id,
            )
            risk_row = next(
                row for row in risk_snapshot["rows"]
                if row["product_id"] == product.id and row["warehouse_id"] == warehouse.id
            )
            self.assertEqual(risk_row["forecast"]["run_id"], exact_run.id)
            self.assertEqual(risk_row["forecast"]["used"], should_be_usable)

            wrong_runs = Forecast.browse(
                [runs[False].id, runs[asd.id if warehouse == atc else atc.id].id]
            ).with_user(manager).with_company(self.company).with_context(
                allowed_company_ids=[self.company.id]
            )
            wrong, _wrong_points, wrong_usable, mismatch_reason = Risk._forecast_for_pair(
                wrong_runs,
                company=self.company,
                product=product,
                warehouse=warehouse,
                lead_days=7,
                today=today,
                now=now,
            )
            self.assertFalse(wrong_usable)
            self.assertIn("does not match the selected company, product, and warehouse", mismatch_reason)
            self.assertIn(wrong, wrong_runs)

        # The freshness gate is evaluated as of the signed dataset's stated
        # 13 October 2026 review point. It uses the real policy function and
        # explicit example instants; it does not freeze or patch Odoo's clock.
        reviewed_run = runs[atc.id]
        example_as_of = {
            "company_id": self.company.id,
            "product_id": product.id,
            "warehouse_id": atc.id,
            "source_type": reviewed_run.source_type,
            "state": "completed",
            "evaluation_status": reviewed_run.evaluation_status,
            "review_status": "reviewed",
            "horizon_days": 30,
            "evaluation_days": 30,
            "history_days": 181,
            "nonzero_days": 7,
            "history_end_date": date(2026, 10, 10),
            "source_cutoff": datetime(2026, 10, 13, 12, 0),
        }
        example_points = [date(2026, 10, 10) + timedelta(days=offset) for offset in range(1, 31)]
        eligible_at_as_of, reason_at_as_of = forecast_eligibility(
            example_as_of,
            company_id=self.company.id,
            product_id=product.id,
            warehouse_id=atc.id,
            lead_time_days=7,
            today=date(2026, 10, 13),
            now=datetime(2026, 10, 13, 12, 1),
            point_dates=example_points,
            source_current=True,
        )
        self.assertTrue(eligible_at_as_of, reason_at_as_of)
        stale_example, stale_reason = forecast_eligibility(
            example_as_of,
            company_id=self.company.id,
            product_id=product.id,
            warehouse_id=atc.id,
            lead_time_days=7,
            today=date(2026, 10, 27),
            now=datetime(2026, 10, 27, 12, 1),
            point_dates=example_points,
            source_current=True,
        )
        self.assertFalse(stale_example)
        self.assertIn("older than 14 days", stale_reason)

        points_before_change = [(point.day, point.units) for point in runs[asd.id].point_ids]
        review_time_before_change = runs[asd.id].reviewed_at
        source_move = StockMove.search(
            [
                ("company_id", "=", self.company.id),
                ("product_id", "=", product.id),
                ("state", "=", "done"),
                ("sale_line_id", "!=", False),
                ("sale_line_id.order_id.state", "in", ["sale", "done"]),
                ("picking_id.picking_type_id.warehouse_id", "=", asd.id),
                ("location_id.usage", "=", "internal"),
                ("location_dest_id.usage", "=", "customer"),
                ("date", ">=", fields.Datetime.to_datetime(runs[asd.id].history_start_date)),
                (
                    "date",
                    "<",
                    fields.Datetime.to_datetime(runs[asd.id].history_end_date) + timedelta(days=1),
                ),
                ("date", "<=", fields.Datetime.to_datetime(runs[asd.id].source_cutoff)),
            ],
            order="date, id",
            limit=1,
        )
        self.assertTrue(source_move)
        source_move.write(
            {"date": fields.Datetime.to_string(fields.Datetime.to_datetime(source_move.date) + timedelta(days=1))}
        )
        self.assertFalse(runs[asd.id]._demo_source_history_is_current())
        stale_selected, _stale_points, stale_usable, stale_reason = Risk._forecast_for_pair(
            runs[asd.id].with_user(manager).with_company(self.company).with_context(
                allowed_company_ids=[self.company.id]
            ),
            company=self.company,
            product=product,
            warehouse=asd,
            lead_days=7,
            today=today,
            now=now,
        )
        self.assertEqual(stale_selected, runs[asd.id])
        self.assertFalse(stale_usable)
        self.assertIn("saved history no longer matches", stale_reason)
        self.assertEqual([(point.day, point.units) for point in runs[asd.id].point_ids], points_before_change)
        self.assertEqual(runs[asd.id].review_status, "reviewed")
        self.assertEqual(runs[asd.id].reviewed_by_id, manager)
        self.assertEqual(runs[asd.id].reviewed_at, review_time_before_change)
        stale_detail = manager_forecast_service.get_forecast_detail(runs[asd.id].id)
        self.assertTrue(stale_detail["history_coverage"]["verified_demo_profile_scoped"])
        self.assertFalse(stale_detail["history_coverage"]["verified_demo_profile_current"])
        self.assertFalse(stale_detail["restock_guidance"]["usable"])
        with self.assertRaisesRegex(OdooImportError, "Actual Odoo state drift"):
            OdooMoroccoImporter(self.env).plan(self.dataset)

        foreign_company = self.env["res.company"].create(
            {"name": "Separate company for warehouse scope test"}
        )
        foreign_warehouse = self.env["stock.warehouse"].create(
            {
                "name": "Foreign warehouse scope test",
                "code": f"X{foreign_company.id:04d}"[-5:],
                "company_id": foreign_company.id,
            }
        )
        scoped_forecast = Forecast.with_user(manager).with_company(self.company).with_context(
            allowed_company_ids=[self.company.id]
        )
        with self.assertRaises(AccessError):
            scoped_forecast._scoped_warehouse(foreign_warehouse.id, self.company)
        visible_profiles = self.profile_model.with_user(manager).with_context(
            allowed_company_ids=[self.company.id]
        ).search([])
        self.assertTrue(visible_profiles)
        self.assertTrue(all(profile.company_id == self.company for profile in visible_profiles))

    def test_history_revision_invalidates_a_queued_profile_snapshot(self):
        run = self.env["autostock.forecast.run"].search(
            [
                ("company_id", "=", self.company.id),
                ("demo_history_profile_id", "!=", False),
                ("warehouse_id", "=", False),
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
