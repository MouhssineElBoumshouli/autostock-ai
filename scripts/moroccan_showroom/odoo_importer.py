"""Odoo ORM writer for the deterministic Atlas Morocco fixture.

This module is called only after the separate host-side target and restore
checks. Importing it has no Odoo side effects. The public runner remains
fail-closed until the independent restore-evidence gate is satisfied.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timezone
import hashlib
import os
from zoneinfo import ZoneInfo

from odoo.tools import config as odoo_config

from .catalog import CATEGORIES
from .generator import Dataset, FOCUS_START, LOCAL_ZONE, canonical_json
from .import_plan import FixtureRecord, ImportPreview, fixture_records, preview_import
from .safety import SafetyError, TARGET_DATABASE, require_apply_approval, validate_uuid


MOROCCO_ZONE = LOCAL_ZONE
CATEGORY_LABELS = {
    "filtration_engine_service": "Filters and service parts",
    "braking": "Brakes",
    "suspension_steering": "Suspension and steering",
    "electrical_batteries": "Electrical and batteries",
    "cooling_belts_drivetrain": "Cooling, belts and drivetrain",
    "ignition_sensors_fluids": "Ignition, sensors and fluids",
}
SUPPORTED_MODELS = {
    "res.company",
    "product.category",
    "stock.warehouse",
    "res.partner",
    "product.product",
    "product.supplierinfo",
    "stock.warehouse.orderpoint",
    "sale.order",
    "sale.order.line",
    "stock.picking",
    "stock.move",
    "autostock.morocco.history.profile",
    "autostock.forecast.run",
}
ENTITY_MODELS = {
    "company_configuration": "res.company",
    "product_category": "product.category",
    "warehouse": "stock.warehouse",
    "supplier": "res.partner",
    "customer": "res.partner",
    "product": "product.product",
    "supplier_term": "product.supplierinfo",
    "reordering_rule": "stock.warehouse.orderpoint",
    "completed_sale_order": "sale.order",
    "completed_sale_picking": "stock.picking",
    "completed_sale_line": "sale.order.line",
    "sale_delivery_move_plan": "stock.move",
    "opening_adjustment": "stock.move",
    "incoming_receipt": "stock.move",
    "linked_return": "stock.move",
    "internal_transfer": "stock.move",
    "stock_picking": "stock.picking",
    "open_sale_order": "sale.order",
    "open_sale_picking": "stock.picking",
    "history_profile_plan": "autostock.morocco.history.profile",
    "forecast_request": "autostock.forecast.run",
}


class OdooImportError(SafetyError):
    """Raised when Odoo does not match the clean, isolated fixture contract."""


_APPROVED_APPLY = object()


def run_import(env, dataset: Dataset, *, mode: str, typed_target_uuid: str | None = None,
               target_identity=None, backup_manifest=None, backup_signing_key=None) -> dict:
    """Safe entrypoint used by an Odoo shell runner; preview never writes."""
    importer = OdooMoroccoImporter(env)
    preview = importer.plan(dataset)
    if mode in {"dry-run", "preview"}:
        return importer.preview_report(dataset, preview)
    require_apply_approval(
        mode=mode,
        typed_target_uuid=typed_target_uuid,
        expected_target_uuid=importer.target_uuid,
        target_identity=target_identity,
        backup_manifest=backup_manifest,
        backup_signing_key=backup_signing_key,
    )
    return importer._apply_dataset(dataset, preview, _approval=_APPROVED_APPLY)


class OdooMoroccoImporter:
    """Apply versioned fixture records using Odoo's supported ORM workflows."""

    def __init__(self, env):
        self.env = env
        if env.uid != 1 and not env.user.has_group("base.group_system"):
            raise OdooImportError("The Moroccan fixture importer requires an Odoo administrator session.")
        if env.cr.dbname != TARGET_DATABASE:
            raise OdooImportError("The active Odoo database is not the isolated Moroccan target.")
        target_uuid = os.environ.get("AUTOSTOCK_DEMO_TARGET_UUID", "")
        try:
            self.target_uuid = validate_uuid(target_uuid, "Moroccan target UUID")
        except SafetyError as error:
            raise OdooImportError(str(error)) from error
        self.company = env.ref("base.main_company")
        self._planned: dict[tuple[str, str], FixtureRecord] = {}
        self._registry_model = env["autostock.morocco.fixture"]

    def _assert_database_target(self, dataset: Dataset) -> None:
        params = self.env["ir.config_parameter"]
        stored_uuid = params.get_param("autostock.morocco.target_uuid")
        company_uuid = self.company.autostock_demo_target_uuid
        if bool(stored_uuid) != bool(company_uuid):
            raise OdooImportError("The database and company target markers are incomplete or inconsistent.")
        if stored_uuid and stored_uuid != self.target_uuid:
            raise OdooImportError("The database target marker does not match this isolated environment.")
        if company_uuid and company_uuid != self.target_uuid:
            raise OdooImportError("The company target marker does not match this isolated environment.")
        if self.company.autostock_demo_dataset_version not in (False, dataset.version):
            raise OdooImportError("The company is already marked for a different Moroccan dataset version.")
        if len(self.env["res.company"].search([])) != 1:
            raise OdooImportError("The Moroccan target must contain exactly one company before import.")

        required_modules = {"stock", "sale_stock", "autostock_ai"}
        installed = set(
            self.env["ir.module.module"].search(
                [("name", "in", list(required_modules)), ("state", "=", "installed")]
            ).mapped("name")
        )
        if installed != required_modules:
            raise OdooImportError("Install the required Stock, Sales/Inventory, and AutoStock modules first.")
        if not self.env["res.country"].search([("code", "=", "MA")], limit=1):
            raise OdooImportError("Morocco country data is missing from the target database.")
        if not self.env["res.currency"].with_context(active_test=False).search(
            [("name", "=", "MAD")], limit=1
        ):
            raise OdooImportError("MAD currency data is missing from the target database.")

        registry = self._registry_model.search([])
        if not registry:
            bootstrap_warehouse = self.env.ref("stock.warehouse0", raise_if_not_found=False)
            existing_warehouses = self.env["stock.warehouse"].search(
                [("company_id", "=", self.company.id)]
            )
            existing_products = self.env["product.product"].search(
                [("company_id", "in", [False, self.company.id])], limit=1
            )
            existing_partners = self.env["res.partner"].search(
                [
                    ("company_id", "=", self.company.id),
                    "|",
                    ("supplier_rank", ">", 0),
                    ("customer_rank", ">", 0),
                ],
                limit=1,
            )
            existing_orders = self.env["sale.order"].search(
                [("company_id", "=", self.company.id)], limit=1
            )
            existing_pickings = self.env["stock.picking"].search(
                [("company_id", "=", self.company.id)], limit=1
            )
            existing_done_moves = self.env["stock.move"].search(
                [("company_id", "=", self.company.id), ("state", "=", "done")], limit=1
            )
            existing_account_moves = self.env["account.move"].search(
                [("company_id", "=", self.company.id)], limit=1
            )
            clean_bootstrap_warehouse = bool(
                bootstrap_warehouse
                and bootstrap_warehouse.company_id == self.company
                and bootstrap_warehouse.code == "WH"
                and existing_warehouses == bootstrap_warehouse
            )
            if (
                not clean_bootstrap_warehouse
                or existing_products
                or existing_partners
                or existing_orders
                or existing_pickings
                or existing_done_moves
                or existing_account_moves
            ):
                raise OdooImportError(
                    "The target is not clean and has no complete fixture registry; restore a reviewed empty target."
                )

    def plan(self, dataset: Dataset) -> ImportPreview:
        self._assert_database_target(dataset)
        planned = fixture_records(dataset)
        existing_rows = self._registry_model.search([], order="fixture_key, id")
        existing_records = []
        for row in existing_rows:
            prefix, separator, key = row.fixture_key.partition(":")
            if (
                not separator
                or prefix != row.entity
                or row.dataset_version != dataset.version
                or ENTITY_MODELS.get(row.entity) != row.record_model
            ):
                raise OdooImportError(f"Fixture registry row {row.fixture_key!r} has inconsistent identity metadata.")
            existing_records.append(FixtureRecord(row.entity, key, row.payload_sha256))
        existing = tuple(existing_records)
        plan = preview_import(dataset, existing)
        self._planned = {(row.entity, row.key): row for row in planned}
        for row in existing_rows:
            if row.record_model not in SUPPORTED_MODELS:
                raise OdooImportError("The fixture registry references an unsupported Odoo model.")
            record = self.env[row.record_model].browse(row.record_id).exists()
            if len(record) != 1:
                raise OdooImportError(f"Registered fixture record {row.fixture_key} is missing or ambiguous.")
        return plan

    def preview_report(self, dataset: Dataset, preview: ImportPreview) -> dict:
        return {
            "mode": "odoo-dry-run",
            "connected_to_odoo": True,
            "database": self.env.cr.dbname,
            "target_uuid_matches_environment": True,
            "dataset_version": dataset.version,
            "dataset_sha256": dataset.digest,
            "counts": dataset.counts,
            "planned_entries": len(preview.actions),
            "entry_actions": preview.counts,
            "target_marker_state": (
                "matched"
                if self.env["ir.config_parameter"].get_param("autostock.morocco.target_uuid")
                else "not_yet_initialized"
            ),
            "database_mutations": 0,
            "forecast_runs_created": 0,
            "limitations": [
                "The dry run reads Odoo state but does not create, write, unlink, queue, or reserve records.",
                "Apply is still gated by signed backup and independent restore evidence.",
            ],
        }

    def _apply_dataset(
        self,
        dataset: Dataset,
        preview: ImportPreview | None = None,
        *,
        _approval=None,
    ) -> dict:
        """Write only after the external approval/restore gate; tested with Odoo ORM in CI."""
        if _approval is not _APPROVED_APPLY and not odoo_config["test_enable"]:
            raise OdooImportError(
                "Direct Odoo writes are restricted to integration tests; use the guarded importer entrypoint."
            )
        preview = preview or self.plan(dataset)
        if preview.counts["unchanged"] == len(preview.actions):
            return {
                "mode": "apply-noop",
                "dataset_version": dataset.version,
                "dataset_sha256": dataset.digest,
                "created": 0,
                "unchanged": len(preview.actions),
                "database_mutations": 0,
            }
        if preview.counts["unchanged"]:
            raise OdooImportError("A partial registry cannot be continued; restore a clean target.")

        self._active_dataset_version = dataset.version
        self._dataset = dataset
        with self.env.cr.savepoint():
            self._configure_company(dataset)
            self.env["ir.config_parameter"].set_param(
                "autostock.morocco.target_uuid", self.target_uuid
            )
            references = self._create_reference_data(dataset)
            products = self._create_products(dataset, references)
            self._apply_opening_inventory(dataset, products, references)
            self._apply_business_activity(dataset, products, references)
            profiles = self._create_history_profiles(dataset, products)
            self._create_forecast_requests(dataset, profiles)
            self._create_reordering_rules(dataset, products, references)
            self._reconcile_stock(dataset, products, references)
        return {
            "mode": "apply",
            "dataset_version": dataset.version,
            "dataset_sha256": dataset.digest,
            "fixture_registry_entries_created": len(preview.actions),
            "unchanged": 0,
            "database_mutations": "Odoo ORM transaction; auxiliary row count not measured",
            "company_id": self.company.id,
            "product_count": len(products),
            "history_profile_count": len(profiles),
            "forecast_requests": 3 * len(profiles),
            "stock_reconciled": True,
        }

    def _register(self, entity: str, key: str, record, record_model: str | None = None):
        planned = self._planned.get((entity, key))
        if not planned:
            raise OdooImportError(f"The writer produced an unplanned fixture identity: {entity}:{key}.")
        model_name = record_model or record._name
        if model_name not in SUPPORTED_MODELS or ENTITY_MODELS.get(entity) != model_name:
            raise OdooImportError(f"Fixture {entity}:{key} has an unsupported Odoo model: {model_name}.")
        self._registry_model.create(
            {
                "dataset_version": self._dataset_version,
                "fixture_key": f"{entity}:{key}",
                "entity": entity,
                "record_model": model_name,
                "record_id": record.id,
                "payload_sha256": planned.payload_sha256,
            }
        )
        return record

    @property
    def _dataset_version(self) -> str:
        return self._active_dataset_version

    def _configure_company(self, dataset: Dataset) -> None:
        company = self.company
        country = self.env["res.country"].search([("code", "=", "MA")], limit=1)
        currency = self.env["res.currency"].with_context(active_test=False).search(
            [("name", "=", "MAD")], limit=1
        )
        if not country or not currency:
            raise OdooImportError("Morocco or MAD localization data is unavailable.")
        if not currency.active:
            currency.write({"active": True})
        if company.currency_id != currency:
            if self.env["account.move"].search_count([("company_id", "=", company.id)]):
                raise OdooImportError("Company currency cannot be changed after accounting entries exist.")
        company.write(
            {
                "name": "Atlas Auto Distribution",
                "country_id": country.id,
                "currency_id": currency.id,
                "autostock_demo_environment": True,
                "autostock_demo_target_uuid": self.target_uuid,
                "autostock_demo_dataset_version": dataset.version,
                "autostock_history_complete_from": FOCUS_START,
            }
        )
        company.partner_id.write(
            {"name": company.name, "city": "Marrakech", "country_id": country.id}
        )
        admin = self.env.ref("base.user_admin")
        admin.write({"tz": "Africa/Casablanca"})
        self._register("company_configuration", "company_atlas_morocco", company)

    def _create_reference_data(self, dataset: Dataset) -> dict:
        country = self.env["res.country"].search([("code", "=", "MA")], limit=1)
        categories = {}
        for row in CATEGORIES:
            key = f"category_{row['key']}"
            category = self.env["product.category"].create(
                {"name": CATEGORY_LABELS[row["key"]]}
            )
            categories[row["key"]] = self._register("product_category", key, category)

        suppliers = {}
        for item in dataset.suppliers:
            partner = self.env["res.partner"].with_company(self.company).create(
                {
                    "name": item["name"],
                    "company_type": "company",
                    "company_id": self.company.id,
                    "city": item["city"],
                    "country_id": country.id,
                    "supplier_rank": 1,
                }
            )
            suppliers[item["key"]] = self._register("supplier", item["key"], partner)

        customers = {}
        for item in dataset.customers:
            partner = self.env["res.partner"].with_company(self.company).create(
                {
                    "name": item["name"],
                    "company_type": "company",
                    "company_id": self.company.id,
                    "city": item["city"],
                    "country_id": country.id,
                    "customer_rank": 1,
                }
            )
            customers[item["key"]] = self._register("customer", item["key"], partner)

        warehouses = {}
        bootstrap_warehouse = self.env.ref("stock.warehouse0", raise_if_not_found=False)
        if not bootstrap_warehouse or bootstrap_warehouse.company_id != self.company:
            raise OdooImportError("The fresh database's main-company bootstrap warehouse is missing.")
        for index, item in enumerate(dataset.warehouses):
            values = {"name": item["name"], "code": item["code"]}
            if index == 0:
                warehouse = bootstrap_warehouse.with_company(self.company)
                warehouse.write(values)
            else:
                warehouse = self.env["stock.warehouse"].with_company(self.company).create(
                    {**values, "company_id": self.company.id}
                )
            warehouses[item["key"]] = self._register("warehouse", item["key"], warehouse)
        return {
            "categories": categories,
            "suppliers": suppliers,
            "customers": customers,
            "warehouses": warehouses,
        }

    def _create_products(self, dataset: Dataset, references: dict) -> dict:
        unit = self.env.ref("uom.product_uom_unit")
        products = {}
        for item in dataset.products:
            first_cost = item.supplier_terms[0].price_tiers[0][1] if item.supplier_terms else 0
            template = self.env["product.template"].with_company(self.company).create(
                {
                    "name": item.name,
                    "default_code": item.sku,
                    "company_id": self.company.id,
                    "categ_id": references["categories"][item.category].id,
                    "is_storable": True,
                    "uom_id": unit.id,
                    "list_price": item.sale_price_mad,
                    "standard_price": first_cost,
                    "sale_ok": True,
                    "purchase_ok": True,
                    "autostock_enabled": True,
                    "autostock_lead_time_days": min(
                        (term.lead_days for term in item.supplier_terms), default=7
                    ),
                }
            )
            product = template.product_variant_id
            products[item.sku] = product
            self._register("product", item.key, product)
            for index, term in enumerate(item.supplier_terms, start=1):
                supplier = references["suppliers"][term.supplier_key]
                for tier_index, (minimum, price) in enumerate(term.price_tiers, start=1):
                    key = f"{item.key}_supplier_term_{index:02d}_{tier_index:02d}"
                    info = self.env["product.supplierinfo"].with_company(self.company).create(
                        {
                            "partner_id": supplier.id,
                            "product_tmpl_id": template.id,
                            "company_id": self.company.id,
                            "product_code": term.vendor_code,
                            "product_name": item.name,
                    "currency_id": self._currency_id(term.currency),
                            "min_qty": minimum,
                            "price": price,
                            "delay": term.lead_days,
                            "autostock_min_order_qty": term.moq,
                            "sequence": 10 * index + tier_index,
                        }
                    )
                    self._register("supplier_term", key, info)
        return products

    def _currency_id(self, currency_code: str) -> int:
        currency = self.env["res.currency"].with_context(active_test=False).search(
            [("name", "=", currency_code)], limit=1
        )
        if not currency:
            raise OdooImportError(f"Supplier price currency {currency_code} is not installed.")
        if not currency.active:
            currency.write({"active": True})
        return currency.id

    def _apply_opening_inventory(self, dataset: Dataset, products: dict, references: dict) -> dict:
        adjustments = [row for row in dataset.movements if row.kind == "opening_adjustment"]
        if not adjustments:
            raise OdooImportError("The deterministic plan has no opening inventory adjustments.")
        quants = []
        location_by_pair = {}
        for item in adjustments:
            product = products[item.sku]
            warehouse = references["warehouses"][item.destination]
            location = warehouse.lot_stock_id
            location_by_pair[(product.id, location.id)] = item
            quants.append(
                {
                    "product_id": product.id,
                    "location_id": location.id,
                    "inventory_quantity": item.quantity,
                }
            )
        Quant = self.env["stock.quant"].with_company(self.company).with_context(
            allowed_company_ids=[self.company.id], inventory_mode=True
        )
        StockMove = self.env["stock.move"].with_company(self.company).with_context(
            allowed_company_ids=[self.company.id]
        )
        old_move_ids = set(StockMove.search([("company_id", "=", self.company.id)]).ids)
        created_quants = Quant.create(quants)
        created_quants.action_apply_inventory()
        new_moves = StockMove.search(
            [
                ("company_id", "=", self.company.id),
                ("id", "not in", list(old_move_ids)),
                ("state", "=", "done"),
                ("location_id.usage", "=", "inventory"),
            ],
            order="id",
        )
        found = set()
        for move in new_moves:
            item = location_by_pair.get((move.product_id.id, move.location_dest_id.id))
            if not item or abs(move.product_qty - item.quantity) > move.product_uom.rounding / 2:
                continue
            if item.key in found:
                raise OdooImportError(f"Opening adjustment {item.key} created ambiguous Odoo moves.")
            self._set_business_date(move, item.effective_at_utc)
            self._register("opening_adjustment", item.key, move)
            found.add(item.key)
        if len(found) != len(adjustments):
            raise OdooImportError("Odoo did not create exactly one native adjustment move per planned opening balance.")
        return {key: True for key in found}

    def _apply_business_activity(self, dataset: Dataset, products: dict, references: dict) -> dict:
        movements = [row for row in dataset.movements if row.kind != "opening_adjustment"]
        orders_by_day = defaultdict(list)
        for order in dataset.orders:
            orders_by_day[order.day].append(order)
        by_day = defaultdict(list)
        for movement in movements:
            by_day[movement.day].append(movement)
        delivery_move_by_fixture = {}

        for day in sorted(set(by_day) | set(orders_by_day)):
            events = by_day[day]
            # Receipts and linked returns are applied before same-day customer
            # dispatches, matching the deterministic plan's event ordering.
            for event in sorted((row for row in events if row.kind == "vendor_receipt"), key=lambda row: row.key):
                picking = self._create_incoming(event, products, references)
                move = picking.move_ids.ensure_one()
                self._set_business_date(move, event.effective_at_utc)
                self._register("incoming_receipt", event.key, move)
                self._register("stock_picking", f"picking_{event.key.lower()}", picking)
            for event in sorted((row for row in events if row.kind == "customer_return"), key=lambda row: row.key):
                original = delivery_move_by_fixture.get(event.original_movement_key)
                if not original or original.state != "done":
                    raise OdooImportError(f"Return {event.key} has no completed original delivery.")
                picking = self._create_return(event, original, products)
                move = picking.move_ids.filtered(lambda row: row.product_id == original.product_id).ensure_one()
                self._set_business_date(move, event.effective_at_utc)
                self._register("linked_return", event.key, move)
                self._register("stock_picking", f"picking_{event.key.lower()}", picking)
            for event in sorted((row for row in events if row.kind == "internal_transfer"), key=lambda row: row.key):
                picking = self._create_transfer(event, products, references)
                move = picking.move_ids.ensure_one()
                self._set_business_date(move, event.effective_at_utc)
                self._register("internal_transfer", event.key, move)
                self._register("stock_picking", f"picking_{event.journey_key.lower()}", picking)
            for order in sorted(orders_by_day[day], key=lambda row: row.key):
                order_record, picking, lines, moves = self._create_delivered_order(
                    order, products, references
                )
                self._register("completed_sale_order", order.key, order_record)
                self._register("completed_sale_picking", f"out_{order.key}", picking)
                for line, order_line, move in zip(order.lines, lines, moves, strict=True):
                    self._register("completed_sale_line", line.key, order_line)
                    self._register("sale_delivery_move_plan", line.movement_key, move)
                    delivery_move_by_fixture[line.movement_key] = move

        for open_order in dataset.open_orders:
            order_record = self._create_open_order(open_order, products, references)
            self._register("open_sale_order", open_order.key, order_record)
            picking = order_record.picking_ids.filtered(lambda row: row.picking_type_code == "outgoing")
            if len(picking) != 1:
                raise OdooImportError(f"Open sale {open_order.key} did not create one customer delivery.")
            picking.scheduled_date = _effective_utc(open_order.day)
            self._register("open_sale_picking", f"out_{open_order.key}", picking)
    def _sale_order_values(self, key: str, day: date, customer, warehouse, line_values: list) -> dict:
        timestamp = _effective_utc(day)
        return {
            "company_id": self.company.id,
            "partner_id": customer.id,
            "partner_invoice_id": customer.id,
            "partner_shipping_id": customer.id,
            "warehouse_id": warehouse.id,
            "date_order": timestamp,
            "order_line": line_values,
            "client_order_ref": key,
        }

    def _create_delivered_order(self, order, products: dict, references: dict):
        from odoo import Command

        customer = references["customers"][order.customer_key]
        warehouse = references["warehouses"][order.warehouse_key]
        line_values = [
            Command.create(
                {
                    "product_id": products[line.sku].id,
                    "product_uom_qty": line.quantity,
                    "product_uom_id": products[line.sku].uom_id.id,
                    "price_unit": next(row.sale_price_mad for row in self._dataset.products if row.sku == line.sku),
                }
            )
            for line in order.lines
        ]
        sale = self.env["sale.order"].with_company(self.company).create(
            self._sale_order_values(order.key, order.day, customer, warehouse, line_values)
        )
        sale.action_confirm()
        pickings = sale.picking_ids.filtered(lambda row: row.picking_type_code == "outgoing")
        if len(pickings) != 1:
            raise OdooImportError(f"Completed sale {order.key} did not produce one outgoing picking.")
        picking = pickings.ensure_one()
        self._validate_picking(picking, fully_reserved=True)
        lines = sale.order_line.sorted(key=lambda row: row.id)
        moves = []
        for line in lines:
            move = picking.move_ids.filtered(lambda row: row.sale_line_id == line)
            if len(move) != 1 or move.state != "done":
                raise OdooImportError(f"Sale line for {line.product_id.default_code} has no unique completed stock move.")
            move = move.ensure_one()
            moves.append(move)
        self._set_business_date(picking.move_ids, _effective_utc(order.day))
        return sale, picking, list(lines), moves

    def _create_open_order(self, order, products: dict, references: dict):
        from odoo import Command

        product = products[order.sku]
        customer = references["customers"][order.customer_key]
        warehouse = references["warehouses"][order.warehouse_key]
        line_values = [
            Command.create(
                {
                    "product_id": product.id,
                    "product_uom_qty": order.quantity,
                    "product_uom_id": product.uom_id.id,
                    "price_unit": next(row.sale_price_mad for row in self._dataset.products if row.sku == order.sku),
                }
            )
        ]
        sale = self.env["sale.order"].with_company(self.company).create(
            self._sale_order_values(order.key, order.day, customer, warehouse, line_values)
        )
        sale.action_confirm()
        return sale

    def _create_incoming(self, event, products: dict, references: dict):
        from odoo import Command

        warehouse = references["warehouses"][event.destination]
        product = products[event.sku]
        operation = warehouse.in_type_id
        picking = self.env["stock.picking"].with_company(self.company).create(
            {
                "company_id": self.company.id,
                "picking_type_id": operation.id,
                "partner_id": references["suppliers"][event.partner_key].id,
                "location_id": operation.default_location_src_id.id,
                "location_dest_id": warehouse.lot_stock_id.id,
                "scheduled_date": event.effective_at_utc,
                "origin": event.key,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom": product.uom_id.id,
                            "product_uom_qty": event.quantity,
                            "location_id": operation.default_location_src_id.id,
                            "location_dest_id": warehouse.lot_stock_id.id,
                            "company_id": self.company.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move.write({"quantity": move.product_uom_qty, "picked": True})
        self._validate_picking(picking, fully_reserved=False)
        return picking

    def _create_transfer(self, event, products: dict, references: dict):
        from odoo import Command

        source = references["warehouses"][event.source]
        destination = references["warehouses"][event.destination]
        product = products[event.sku]
        operation = source.int_type_id
        picking = self.env["stock.picking"].with_company(self.company).create(
            {
                "company_id": self.company.id,
                "picking_type_id": operation.id,
                "location_id": source.lot_stock_id.id,
                "location_dest_id": destination.lot_stock_id.id,
                "scheduled_date": event.effective_at_utc,
                "origin": event.journey_key,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom": product.uom_id.id,
                            "product_uom_qty": event.quantity,
                            "location_id": source.lot_stock_id.id,
                            "location_dest_id": destination.lot_stock_id.id,
                            "company_id": self.company.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move.write({"quantity": move.product_uom_qty, "picked": True})
        self._validate_picking(picking, fully_reserved=True)
        return picking

    def _create_return(self, event, original_move, products: dict):
        original_picking = original_move.picking_id
        context = {
            "active_model": "stock.picking",
            "active_id": original_picking.id,
            "active_ids": original_picking.ids,
        }
        wizard = self.env["stock.return.picking"].with_context(**context).create({})
        line = wizard.product_return_moves.filtered(
            lambda item: item.move_id == original_move
        ).sorted(key=lambda item: item.id)[:1]
        if not line:
            raise OdooImportError(f"Odoo did not offer a return line for {event.key}.")
        already_returned = sum(
            returned.product_uom._compute_quantity(returned.quantity, original_move.product_uom)
            for returned in original_move.returned_move_ids.filtered(
                lambda move: move.state != "cancel"
            )
        )
        remaining = max(0.0, original_move.quantity - already_returned)
        rounding = original_move.product_uom.rounding
        if event.quantity - remaining > rounding / 2:
            raise OdooImportError(f"Return {event.key} exceeds its original delivered quantity.")
        line.write({"quantity": event.quantity})
        action = wizard.action_create_returns()
        picking = self.env["stock.picking"].browse(action.get("res_id", 0)).exists()
        if not picking:
            raise OdooImportError(f"Odoo did not create the linked return picking for {event.key}.")
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move.write({"quantity": event.quantity, "picked": True})
        self._validate_picking(picking, fully_reserved=False)
        if any(move.origin_returned_move_id != original_move for move in picking.move_ids):
            raise OdooImportError(f"Return {event.key} lost its link to the original delivery.")
        return picking

    def _validate_picking(self, picking, *, fully_reserved: bool) -> None:
        if picking.state in {"done", "cancel"}:
            if picking.state != "done":
                raise OdooImportError(f"Picking {picking.origin or picking.name} was cancelled unexpectedly.")
            return
        picking.action_assign()
        for move in picking.move_ids.filtered(lambda item: item.state not in {"done", "cancel"}):
            expected = move.product_uom_qty
            if fully_reserved and expected - move.quantity >= move.product_uom.rounding / 2:
                raise OdooImportError(
                    f"Planned completed movement for {move.product_id.default_code} was not "
                    f"fully reserved ({move.quantity:g} of {expected:g} {move.product_uom.name})."
                )
            if not move.quantity:
                move.write({"quantity": expected})
            move.write({"picked": True})
        action = picking.button_validate()
        if isinstance(action, dict):
            model = action.get("res_model")
            context = action.get("context") or {}
            if isinstance(context, str):
                raise OdooImportError("Odoo returned an unsupported validation context; no wizard was processed.")
            if model not in {"stock.immediate.transfer", "stock.backorder.confirmation"}:
                raise OdooImportError(f"Odoo requested an unapproved validation wizard: {model!r}.")
            wizard = self.env[model].with_context(**context).create(
                {"pick_ids": [(6, 0, picking.ids)]} if model == "stock.backorder.confirmation" else {}
            )
            wizard.process()
        if picking.state != "done" or any(move.state != "done" for move in picking.move_ids):
            raise OdooImportError(f"Odoo did not complete picking {picking.origin or picking.name}.")

    def _set_business_date(self, records, effective_at_utc: str | None) -> None:
        if not effective_at_utc:
            raise OdooImportError("A business movement is missing its pinned effective date.")
        moves = records if records._name == "stock.move" else records.move_ids
        effective = effective_at_utc.replace("T", " ")
        moves.write({"date": effective})
        for move in moves:
            if "date" in move.move_line_ids._fields:
                move.move_line_ids.write({"date": effective})
            if move.picking_id and move.picking_id.state == "done":
                move.picking_id.write({"date_done": effective})

    def _create_history_profiles(self, dataset: Dataset, products: dict) -> dict:
        profiles = {}
        forecast_model = self.env["autostock.forecast.run"].with_company(self.company).with_context(
            allowed_company_ids=[self.company.id]
        )
        Profile = self.env["autostock.morocco.history.profile"].with_company(self.company).with_context(
            allowed_company_ids=[self.company.id]
        )
        daily_by_profile = defaultdict(list)
        for row in dataset.daily_observations:
            daily_by_profile[row["profile_key"]].append(row)
        for planned in dataset.history_profiles:
            product = products[planned["sku"]]
            summary = forecast_model._morocco_source_summary(
                self.company,
                product,
                planned["business_effective_start"],
                planned["business_effective_end"],
                datetime.now(timezone.utc).replace(tzinfo=None),
            )
            if (
                summary["source_move_count"] != planned["planned_qualifying_move_count"]
                or summary["delivery_count"] != planned["planned_delivery_move_count"]
                or summary["return_count"] != planned["planned_return_move_count"]
                or abs(summary["delivery_units"] - planned["planned_delivery_units"]) > product.uom_id.rounding / 2
                or abs(summary["return_units"] - planned["planned_returned_units"]) > product.uom_id.rounding / 2
            ):
                raise OdooImportError(f"Odoo delivery source for {planned['sku']} differs from the pinned dataset plan.")
            actual_rows = [
                {
                    "profile_key": planned["key"],
                    "sku": planned["sku"],
                    "day": row["day"],
                    "delivered_units": _stable_number(row["delivered_units"]),
                    "returned_units": _stable_number(row["returned_units"]),
                    "source_event_count": row["source_event_count"],
                    "coverage_complete": True,
                }
                for row in summary["snapshot"]
            ]
            actual_daily_digest = hashlib.sha256(canonical_json(actual_rows)).hexdigest()
            if actual_daily_digest != planned["planned_daily_rows_sha256"]:
                raise OdooImportError(f"Odoo's full daily history for {planned['sku']} does not match the pinned plan.")
            profile = Profile.create(
                {
                    "name": f"{planned['sku']} · {dataset.version}",
                    "profile_key": planned["key"],
                    "dataset_version": dataset.version,
                    "company_id": self.company.id,
                    "product_id": product.id,
                    "history_start_date": planned["business_effective_start"],
                    "history_end_date": planned["business_effective_end"],
                    "calendar_days": planned["calendar_days"],
                    "planned_daily_sha256": planned["planned_daily_rows_sha256"],
                    "source_move_count": summary["source_move_count"],
                    "source_delivery_count": summary["delivery_count"],
                    "source_return_count": summary["return_count"],
                    "source_delivery_units": summary["delivery_units"],
                    "source_return_units": summary["return_units"],
                    "source_move_sha256": summary["move_sha256"],
                    "source_daily_sha256": summary["daily_sha256"],
                    "verified_at": datetime.now(timezone.utc).replace(tzinfo=None),
                    "state": "verified",
                }
            )
            self._register("history_profile_plan", planned["key"], profile)
            profiles[planned["key"]] = profile
        return profiles

    def _create_forecast_requests(self, dataset: Dataset, profiles: dict) -> None:
        Forecast = self.env["autostock.forecast.run"].with_company(self.company).with_context(
            allowed_company_ids=[self.company.id]
        )
        for profile_data in dataset.history_profiles:
            profile = profiles[profile_data["key"]]
            for horizon in (7, 30, 60):
                result = Forecast.request_forecast(
                    profile.product_id.id,
                    horizon_days=horizon,
                    history_start=profile.history_start_date,
                    history_end=profile.history_end_date,
                )
                run = Forecast.browse(result["id"])
                if run.demo_history_profile_id != profile or run.review_status == "reviewed":
                    raise OdooImportError("The demo history forecast was not queued with truthful, unreviewed provenance.")
                key = f"{profile.profile_key}_{horizon}d"
                self._register("forecast_request", key, run)

    def _create_reordering_rules(self, dataset: Dataset, products: dict, references: dict) -> None:
        Orderpoint = self.env["stock.warehouse.orderpoint"].with_company(self.company).with_context(
            allowed_company_ids=[self.company.id]
        )
        for product_data in dataset.products:
            product = products[product_data.sku]
            for warehouse_data in dataset.warehouses:
                warehouse = references["warehouses"][warehouse_data["key"]]
                rule = Orderpoint.create(
                    {
                        "product_id": product.id,
                        "location_id": warehouse.lot_stock_id.id,
                        "warehouse_id": warehouse.id,
                        "company_id": self.company.id,
                        "product_min_qty": product_data.reorder_minimum,
                        "product_max_qty": product_data.reorder_maximum,
                    }
                )
                self._register(
                    "reordering_rule",
                    f"orderpoint_{product_data.key}_{warehouse_data['key']}",
                    rule,
                )

    def _reconcile_stock(self, dataset: Dataset, products: dict, references: dict) -> None:
        expected = {
            (row["sku"], row["warehouse_key"]): row["on_hand"]
            for row in dataset.ending_on_hand
        }
        for product_data in dataset.products:
            product = products[product_data.sku]
            for warehouse_data in dataset.warehouses:
                warehouse = references["warehouses"][warehouse_data["key"]]
                quantity = product.with_company(self.company).with_context(
                    allowed_company_ids=[self.company.id], warehouse_id=warehouse.id
                ).qty_available
                target = expected[(product_data.sku, warehouse_data["key"])]
                if abs(quantity - target) > product.uom_id.rounding / 2:
                    raise OdooImportError(
                        f"Odoo on-hand does not reconcile for {product_data.sku} in {warehouse.name}: {quantity} vs {target}."
                    )


def _effective_utc(day: date) -> str:
    return datetime.combine(day, time(12, 0), tzinfo=MOROCCO_ZONE).astimezone(
        timezone.utc
    ).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def _stable_number(value: float) -> int | float:
    """Keep integral Odoo float quantities canonical with the generated plan."""
    rounded = round(value)
    return int(rounded) if abs(value - rounded) < 1e-9 else value
