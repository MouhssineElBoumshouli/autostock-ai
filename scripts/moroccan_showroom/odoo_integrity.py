"""Read-only audit of live Odoo records against the Moroccan fixture plan.

Registry payload hashes describe the planned fixture. This module separately
checks current business fields, workflows, and physical stock before a repeat
preview is treated as unchanged.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timezone

from odoo import fields

from .catalog import CATEGORIES, CATEGORY_LABELS
from .generator import FOCUS_START, LOCAL_ZONE, Dataset


def audit_fixture_state(env, company, dataset: Dataset, rows, error_type) -> None:
    """Raise ``error_type`` on any material drift; perform reads only."""
    audit = _FixtureAudit(env, company, dataset, rows, error_type)
    audit.run()


class _FixtureAudit:
    def __init__(self, env, company, dataset, rows, error_type):
        self.env = env
        self.company = company
        self.dataset = dataset
        self.rows = rows
        self.error_type = error_type
        self.by_identity = {}
        self.by_model = defaultdict(dict)
        self.registered_ids = defaultdict(set)
        ids_by_model = defaultdict(set)

        for row in rows:
            identity = (row.entity, row.fixture_key.partition(":")[2])
            self.by_identity[identity] = row
            self.registered_ids[row.record_model].add(row.record_id)
            ids_by_model[row.record_model].add(row.record_id)

        for model, ids in ids_by_model.items():
            records = env[model].with_context(active_test=False).browse(sorted(ids)).exists()
            self.by_model[model] = {record.id: record for record in records}

        self.products = {
            item.sku: self.record("product", item.key)
            for item in dataset.products
        }
        self.warehouses = {
            item["key"]: self.record("warehouse", item["key"])
            for item in dataset.warehouses
        }
        self.suppliers = {
            item["key"]: self.record("supplier", item["key"])
            for item in dataset.suppliers
        }
        self.customers = {
            item["key"]: self.record("customer", item["key"])
            for item in dataset.customers
        }
        self.movements = {item.key: item for item in dataset.movements}
        self.sale_lines = {
            line.key: (order, line)
            for order in dataset.orders
            for line in order.lines
        }
        self.lines_by_movement = {
            line.movement_key: (order, line)
            for order in dataset.orders
            for line in order.lines
        }
        self.orders = {order.key: order for order in dataset.orders}
        self.open_orders = {order.key: order for order in dataset.open_orders}

    def run(self):
        # Existing keys and registry hashes were already checked by plan().
        # Every returned record must still exist before any field access.
        for identity, row in self.by_identity.items():
            if row.record_id not in self.by_model[row.record_model]:
                self.fail(identity, "registered Odoo record is missing")

        self._company()
        self._reference_records()
        self._products_and_terms()
        self._orderpoints()
        self._sales()
        self._movements()
        self._history_profiles()
        self._forecast_requests()
        self._stock_ledger()
        self._unregistered_records()

    def fail(self, identity, detail):
        entity, key = identity
        raise self.error_type(
            f"Actual Odoo state drift for fixture {entity}:{key}: {detail}."
        )

    def record(self, entity, key):
        row = self.by_identity.get((entity, key))
        if not row:
            self.fail((entity, key), "the expected registry entry is absent")
        return self.by_model[row.record_model].get(row.record_id)

    @staticmethod
    def _utc(value):
        if not value:
            return None
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    @staticmethod
    def _effective_utc(day):
        return datetime.combine(day, time(12, 0), tzinfo=LOCAL_ZONE).astimezone(
            timezone.utc
        ).replace(tzinfo=None)

    @staticmethod
    def _same_number(actual, expected, rounding=0.01):
        return abs(float(actual or 0.0) - float(expected or 0.0)) <= (rounding / 2) + 1e-9

    def _expect_number(self, identity, actual, expected, detail, rounding=0.01):
        if not self._same_number(actual, expected, rounding):
            self.fail(identity, f"{detail} changed (expected {expected!r}, found {actual!r})")

    def _expect_date(self, identity, actual, expected, detail):
        if fields.Date.to_date(actual) != fields.Date.to_date(expected):
            self.fail(identity, f"{detail} changed (expected {expected!s}, found {actual!s})")

    def _expect_datetime(self, identity, actual, expected, detail):
        if self._utc(actual) != self._utc(expected):
            self.fail(identity, f"{detail} changed (expected {expected!s}, found {actual!s})")

    def _company(self):
        identity = ("company_configuration", "company_atlas_morocco")
        record = self.record(*identity)
        expected = {
            "name": "Atlas Auto Distribution",
            "country": "MA",
            "city": "Marrakech",
            "currency": "MAD",
            "history_start": FOCUS_START,
        }
        if (
            record != self.company
            or record.name != expected["name"]
            or record.country_id.code != expected["country"]
            or record.partner_id.city != expected["city"]
            or record.currency_id.name != expected["currency"]
            or record.autostock_history_complete_from != expected["history_start"]
            or not record.autostock_demo_environment
            or record.autostock_demo_dataset_version != self.dataset.version
        ):
            self.fail(identity, "company identity, currency, or history coverage changed")
        admin = self.env.ref("base.user_admin")
        if admin.tz != "Africa/Casablanca":
            self.fail(identity, "fixture administrator timezone changed")

    def _reference_records(self):
        country = self.env["res.country"].search([("code", "=", "MA")], limit=1)
        for category in CATEGORIES:
            key = f"category_{category['key']}"
            record = self.record("product_category", key)
            if record.name != CATEGORY_LABELS[category["key"]]:
                self.fail(("product_category", key), "category name changed")

        for entity, items, expected_rank in (
            ("supplier", self.dataset.suppliers, "supplier_rank"),
            ("customer", self.dataset.customers, "customer_rank"),
        ):
            for item in items:
                record = self.record(entity, item["key"])
                if (
                    record.name != item["name"]
                    or record.city != item["city"]
                    or record.country_id != country
                    or record.company_id != self.company
                    or record.company_type != "company"
                    or getattr(record, expected_rank) <= 0
                ):
                    self.fail((entity, item["key"]), "partner identity or company scope changed")

        for item in self.dataset.warehouses:
            record = self.record("warehouse", item["key"])
            if (
                record.name != item["name"]
                or record.code != item["code"]
                or record.company_id != self.company
            ):
                self.fail(("warehouse", item["key"]), "warehouse identity or company changed")

    def _products_and_terms(self):
        currency_rounding = self.company.currency_id.rounding
        expected_term_ids = set()
        for item in self.dataset.products:
            identity = ("product", item.key)
            product = self.products[item.sku]
            template = product.product_tmpl_id
            category_name = CATEGORY_LABELS[item.category]
            expected_cost = (
                item.supplier_terms[0].price_tiers[0][1]
                if item.supplier_terms
                else 0.0
            )
            expected_lead = min((term.lead_days for term in item.supplier_terms), default=7)
            if (
                template.name != item.name
                or product.default_code != item.sku
                or template.company_id != self.company
                or template.categ_id.name != category_name
                or not product.is_storable
                or not product.sale_ok
                or not product.purchase_ok
                or not template.autostock_enabled
                or template.autostock_lead_time_days != expected_lead
            ):
                self.fail(identity, "product name, SKU, category, company, or stock settings changed")
            self._expect_number(identity, product.with_company(self.company).list_price,
                                item.sale_price_mad, "sale price", currency_rounding)
            if item.supplier_terms:
                self._expect_number(identity, product.with_company(self.company).standard_price,
                                    expected_cost, "standard cost", currency_rounding)

            for term_index, term in enumerate(item.supplier_terms, start=1):
                for tier_index, (minimum, price) in enumerate(term.price_tiers, start=1):
                    key = f"{item.key}_supplier_term_{term_index:02d}_{tier_index:02d}"
                    identity = ("supplier_term", key)
                    info = self.record(*identity)
                    expected_term_ids.add(info.id)
                    if (
                        info.product_tmpl_id != template
                        or info.product_id
                        or info.partner_id != self.suppliers[term.supplier_key]
                        or info.company_id != self.company
                        or info.product_code != term.vendor_code
                        or info.product_name != item.name
                        or info.currency_id.name != term.currency
                        or info.delay != term.lead_days
                        or info.sequence != 10 * term_index + tier_index
                    ):
                        self.fail(identity, "vendor identity, currency, code, or lead time changed")
                    self._expect_number(identity, info.min_qty, minimum,
                                        "price-break minimum", product.uom_id.rounding)
                    self._expect_number(identity, info.price, price,
                                        "vendor price", info.currency_id.rounding)
                    self._expect_number(identity, info.autostock_min_order_qty, term.moq,
                                        "supplier minimum order quantity", product.uom_id.rounding)

        self.expected_supplierinfo_ids = expected_term_ids

    def _orderpoints(self):
        for product_data in self.dataset.products:
            for warehouse_data in self.dataset.warehouses:
                key = f"orderpoint_{product_data.key}_{warehouse_data['key']}"
                identity = ("reordering_rule", key)
                if product_data.reorder_minimum is None or product_data.reorder_maximum is None:
                    if ("reordering_rule", key) in self.by_identity:
                        self.fail(identity, "an unconfigured reorder policy was added")
                    continue
                rule = self.record(*identity)
                warehouse = self.warehouses[warehouse_data["key"]]
                if (
                    rule.product_id != self.products[product_data.sku]
                    or rule.location_id != warehouse.lot_stock_id
                    or rule.warehouse_id != warehouse
                    or rule.company_id != self.company
                ):
                    self.fail(identity, "reorder rule product, location, or company changed")
                self._expect_number(identity, rule.product_min_qty, product_data.reorder_minimum,
                                    "reorder minimum", rule.product_id.uom_id.rounding)
                self._expect_number(identity, rule.product_max_qty, product_data.reorder_maximum,
                                    "reorder maximum", rule.product_id.uom_id.rounding)

    def _order_record(self, entity, key, order, *, open_order=False):
        record = self.record(entity, key)
        identity = (entity, key)
        customer = self.customers[order.customer_key]
        warehouse = self.warehouses[order.warehouse_key]
        effective = self._effective_utc(order.day)
        if (
            record.client_order_ref != order.key
            or record.company_id != self.company
            or record.partner_id != customer
            or record.warehouse_id != warehouse
            or record.state not in {"sale", "done"}
        ):
            self.fail(identity, "sale identity, customer, warehouse, or confirmed state changed")
        self._expect_datetime(identity, record.date_order, effective, "business order date")

        if open_order:
            item = next(product for product in self.dataset.products if product.sku == order.sku)
            expected_lines = [(order.sku, order.quantity, item.sale_price_mad)]
        else:
            expected_lines = sorted(
                (
                    line.sku,
                    line.quantity,
                    next(product.sale_price_mad for product in self.dataset.products if product.sku == line.sku),
                )
                for line in order.lines
            )
        actual_lines = sorted(
            (
                line.product_id.default_code,
                line.product_uom_qty,
                line.price_unit,
            )
            for line in record.order_line.filtered(lambda line: not line.display_type)
        )
        if len(actual_lines) != len(expected_lines):
            self.fail(identity, "sale line count changed")
        for expected, actual in zip(expected_lines, actual_lines):
            if expected[0] != actual[0] or not self._same_number(actual[1], expected[1], 1.0) or not self._same_number(actual[2], expected[2], self.company.currency_id.rounding):
                self.fail(identity, "sale product, quantity, or unit price changed")

        if open_order:
            pickings = record.picking_ids.filtered(lambda row: row.picking_type_code == "outgoing")
            if len(pickings) != 1:
                self.fail(identity, "open sale no longer has one outgoing picking")
            picking = self.record("open_sale_picking", f"out_{order.key}")
            if picking != pickings or picking.state in {"done", "cancel"}:
                self.fail(("open_sale_picking", f"out_{order.key}"), "open delivery was completed, canceled, or replaced")
            self._expect_datetime(("open_sale_picking", f"out_{order.key}"), picking.scheduled_date,
                                  effective, "scheduled delivery date")
            moves = picking.move_ids
            if len(moves) != len(expected_lines):
                self.fail(("open_sale_picking", f"out_{order.key}"), "open delivery move count changed")
            for move in moves:
                expected_line = next(
                    (line for line in expected_lines if line[0] == move.product_id.default_code),
                    None,
                )
                if (
                    not expected_line
                    or not self._same_number(move.product_uom_qty, expected_line[1], 1.0)
                    or move.state in {"done", "cancel"}
                ):
                    self.fail(("open_sale_picking", f"out_{order.key}"), "open delivery product or quantity changed")
        else:
            pickings = record.picking_ids.filtered(lambda row: row.picking_type_code == "outgoing")
            if len(pickings) != 1:
                self.fail(identity, "completed sale no longer has one outgoing picking")
            picking_key = f"out_{order.key}"
            picking = self.record("completed_sale_picking", picking_key)
            if picking != pickings or picking.state != "done" or picking.company_id != self.company:
                self.fail(("completed_sale_picking", picking_key), "completed delivery is missing, canceled, or replaced")
            if picking.picking_type_id.warehouse_id != warehouse:
                self.fail(("completed_sale_picking", picking_key), "delivery warehouse changed")
            self._expect_datetime(("completed_sale_picking", picking_key), picking.date_done,
                                  effective, "completed delivery date")

    def _sales(self):
        for order in self.dataset.orders:
            self._order_record("completed_sale_order", order.key, order)
        for order in self.dataset.open_orders:
            self._order_record("open_sale_order", order.key, order, open_order=True)

        for line_key, (order, line_data) in self.sale_lines.items():
            identity = ("completed_sale_line", line_key)
            line = self.record(*identity)
            expected_order = self.record("completed_sale_order", order.key)
            product = self.products[line_data.sku]
            price = next(item.sale_price_mad for item in self.dataset.products if item.sku == line_data.sku)
            if (
                line.order_id != expected_order
                or line.product_id != product
                or line.state not in {"sale", "done"}
                or line.product_uom != product.uom_id
            ):
                self.fail(identity, "sale line order, product, UoM, or confirmed state changed")
            self._expect_number(identity, line.product_uom_qty, line_data.quantity,
                                "sale line quantity", product.uom_id.rounding)
            self._expect_number(identity, line.price_unit, price,
                                "sale line unit price", self.company.currency_id.rounding)

    def _expected_location(self, value, move, source, identity):
        location = move.location_id if source else move.location_dest_id
        if value in self.warehouses:
            expected = self.warehouses[value].lot_stock_id
            if location != expected:
                self.fail(identity, f"movement {'source' if source else 'destination'} warehouse changed")
        else:
            expected_usage = {
                "supplier_location": "supplier",
                "customer_location": "customer",
                "inventory_adjustment": "inventory",
            }.get(value)
            if not expected_usage or location.usage != expected_usage:
                self.fail(identity, f"movement {'source' if source else 'destination'} location usage changed")

    def _movements(self):
        entity_by_kind = {
            "opening_adjustment": "opening_adjustment",
            "vendor_receipt": "incoming_receipt",
            "customer_return": "linked_return",
            "internal_transfer": "internal_transfer",
            "sale_delivery": "sale_delivery_move_plan",
        }
        delivered_moves = {}
        returned_by_delivery = defaultdict(float)
        for expected in self.dataset.movements:
            entity = entity_by_kind[expected.kind]
            identity = (entity, expected.key)
            move = self.record(*identity)
            product = self.products[expected.sku]
            if move.company_id != self.company or move.product_id != product or move.state != "done":
                self.fail(identity, "movement product, company, or completed state changed")
            if move.product_uom != product.uom_id:
                self.fail(identity, "movement unit of measure changed")
            self._expect_number(identity, move.product_uom_qty, expected.quantity,
                                "planned movement quantity", product.uom_id.rounding)
            actual_done = move.product_uom._compute_quantity(move.quantity, product.uom_id, round=False)
            self._expect_number(identity, actual_done, expected.quantity,
                                "completed movement quantity", product.uom_id.rounding)
            self._expect_datetime(identity, move.date, self._utc(expected.effective_at_utc),
                                  "business movement date")
            self._expected_location(expected.source, move, True, identity)
            self._expected_location(expected.destination, move, False, identity)

            if expected.kind == "sale_delivery":
                order, line = self.lines_by_movement[expected.key]
                sale_line = self.record("completed_sale_line", line.key)
                if move.sale_line_id != sale_line or move.picking_id.state != "done" or move.picking_id.picking_type_code != "outgoing":
                    self.fail(identity, "delivery lost its confirmed sale line or completed outgoing picking")
                if move.picking_id.picking_type_id.warehouse_id != self.warehouses[order.warehouse_key]:
                    self.fail(identity, "delivery movement warehouse changed")
                delivered_moves[expected.key] = move
            elif expected.kind == "customer_return":
                original = delivered_moves.get(expected.original_movement_key)
                if not original:
                    original = self.record("sale_delivery_move_plan", expected.original_movement_key)
                if (
                    move.origin_returned_move_id != original
                    or not move.picking_id
                    or move.picking_id.state != "done"
                    or move.picking_id.picking_type_code != "incoming"
                ):
                    self.fail(identity, "return link or completed return workflow changed")
                if expected.partner_key and move.picking_id.partner_id != self.customers[expected.partner_key]:
                    self.fail(identity, "return customer changed")
                returned_by_delivery[original.id] += actual_done
            elif expected.kind == "vendor_receipt":
                if (
                    not move.picking_id
                    or move.picking_id.state != "done"
                    or move.picking_id.picking_type_code != "incoming"
                    or move.picking_id.origin != expected.key
                    or move.picking_id.partner_id != self.suppliers[expected.partner_key]
                ):
                    self.fail(identity, "supplier receipt workflow or supplier changed")
            elif expected.kind == "internal_transfer":
                if (
                    not move.picking_id
                    or move.picking_id.state != "done"
                    or move.picking_id.picking_type_code != "internal"
                    or move.picking_id.origin != expected.journey_key
                ):
                    self.fail(identity, "internal transfer workflow or journey changed")
            elif expected.kind == "opening_adjustment":
                if move.picking_id:
                    self.fail(identity, "opening inventory adjustment was replaced by a picking")

        for original_id, returned in returned_by_delivery.items():
            original = self.env["stock.move"].browse(original_id)
            if returned - original.quantity > original.product_uom.rounding / 2:
                self.fail(("linked_return", str(original_id)), "linked returns exceed the delivered quantity")

    def _history_profiles(self):
        for planned in self.dataset.history_profiles:
            identity = ("history_profile_plan", planned["key"])
            profile = self.record(*identity)
            product = self.products[planned["sku"]]
            if (
                profile.name != f"{planned['sku']} · {self.dataset.version}"
                or profile.profile_key != planned["key"]
                or profile.dataset_version != self.dataset.version
                or profile.company_id != self.company
                or profile.product_id != product
                or profile.state != "verified"
                or profile.calendar_days != planned["calendar_days"]
                or profile.planned_daily_sha256 != planned["planned_daily_rows_sha256"]
            ):
                self.fail(identity, "verified source profile identity or planned coverage changed")
            self._expect_date(identity, profile.history_start_date,
                              planned["business_effective_start"], "history start")
            self._expect_date(identity, profile.history_end_date,
                              planned["business_effective_end"], "history end")
            if (
                profile.source_move_count != planned["planned_qualifying_move_count"]
                or profile.source_delivery_count != planned["planned_delivery_move_count"]
                or profile.source_return_count != planned["planned_return_move_count"]
            ):
                self.fail(identity, "source event counts changed")
            self._expect_number(identity, profile.source_delivery_units,
                                planned["planned_delivery_units"], "delivered history units",
                                product.uom_id.rounding)
            self._expect_number(identity, profile.source_return_units,
                                planned["planned_returned_units"], "returned history units",
                                product.uom_id.rounding)
            if not profile._matches_history(
                self.company,
                product,
                profile.history_start_date,
                profile.history_end_date,
            ):
                self.fail(identity, "current qualifying Odoo delivery/return history no longer matches its digest")

    def _forecast_requests(self):
        for planned in self.dataset.history_profiles:
            profile = self.record("history_profile_plan", planned["key"])
            for horizon in (7, 30, 60):
                key = f"{planned['key']}_{horizon}d"
                identity = ("forecast_request", key)
                run = self.record(*identity)
                if (
                    run.company_id != self.company
                    or run.product_id != profile.product_id
                    or run.demo_history_profile_id != profile
                    or run.demo_dataset_version != self.dataset.version
                    or run.source_type != "completed_deliveries"
                    or run.warehouse_id
                    or int(run.horizon_days) != horizon
                    or run.state not in {"queued", "completed"}
                    or run.review_status != "unreviewed"
                ):
                    self.fail(identity, "forecast source, scope, horizon, state, or review status changed")
                self._expect_date(identity, run.history_start_date,
                                  planned["business_effective_start"], "forecast history start")
                self._expect_date(identity, run.history_end_date,
                                  planned["business_effective_end"], "forecast history end")

    def _stock_ledger(self):
        expected = {
            (row["sku"], row["warehouse_key"]): row["on_hand"]
            for row in self.dataset.ending_on_hand
        }
        product_ids = [product.id for product in self.products.values()]
        Product = self.env["product.product"].with_company(self.company).with_context(
            allowed_company_ids=[self.company.id], active_test=False
        )
        for key, warehouse in self.warehouses.items():
            scoped = Product.with_context(warehouse_id=warehouse.id).browse(product_ids)
            actual = {product.id: product.qty_available for product in scoped}
            for sku, product in self.products.items():
                target = expected[(sku, key)]
                if not self._same_number(actual.get(product.id), target, product.uom_id.rounding):
                    self.fail(
                        ("product", next(item.key for item in self.dataset.products if item.sku == sku)),
                        f"stock ledger drift in {warehouse.display_name} (expected {target:g}, found {actual.get(product.id)!r})",
                    )

    def _assert_same_ids(self, model, domain, expected_ids, description):
        actual_ids = set(
            self.env[model].with_context(active_test=False).search(domain).ids
        )
        expected_ids = set(expected_ids)
        if actual_ids != expected_ids:
            extras = len(actual_ids - expected_ids)
            missing = len(expected_ids - actual_ids)
            raise self.error_type(
                f"Fixture target contains unregistered or missing {description} "
                f"(unregistered={extras}, missing={missing}); restore or review the isolated target."
            )

    def _unregistered_records(self):
        company_id = self.company.id
        product_ids = {product.id for product in self.products.values()}
        template_ids = {product.product_tmpl_id.id for product in self.products.values()}
        fixture_orders = [self.record("completed_sale_order", key) for key in self.orders]
        fixture_orders += [self.record("open_sale_order", key) for key in self.open_orders]
        order_ids = {order.id for order in fixture_orders}
        picking_ids = set(self.registered_ids["stock.picking"])
        for order in fixture_orders:
            picking_ids.update(order.picking_ids.ids)

        self._assert_same_ids(
            "product.product",
            [("company_id", "in", [False, company_id]), ("default_code", "like", "AT-MA-%")],
            self.registered_ids["product.product"],
            "fixture-prefixed products",
        )
        partner_names = [item["name"] for item in self.dataset.suppliers + self.dataset.customers]
        self._assert_same_ids(
            "res.partner",
            [("company_id", "in", [False, company_id]), ("name", "in", partner_names)],
            self.registered_ids["res.partner"],
            "fixture partners",
        )
        self._assert_same_ids(
            "stock.warehouse",
            [("company_id", "=", company_id), ("code", "in", [row["code"] for row in self.dataset.warehouses])],
            self.registered_ids["stock.warehouse"],
            "fixture warehouses",
        )
        self._assert_same_ids(
            "product.category",
            [("name", "in", list(CATEGORY_LABELS.values()))],
            self.registered_ids["product.category"],
            "fixture categories",
        )
        self._assert_same_ids(
            "product.supplierinfo",
            [("product_tmpl_id", "in", sorted(template_ids)), ("company_id", "in", [False, company_id])],
            self.expected_supplierinfo_ids,
            "fixture supplier terms",
        )
        self._assert_same_ids(
            "stock.warehouse.orderpoint",
            [("product_id", "in", sorted(product_ids)), ("company_id", "in", [False, company_id])],
            self.registered_ids["stock.warehouse.orderpoint"],
            "fixture reorder rules",
        )
        self._assert_same_ids(
            "sale.order",
            [("company_id", "=", company_id), ("client_order_ref", "like", "SO-MA-%")],
            self.registered_ids["sale.order"],
            "fixture sales orders",
        )
        self._assert_same_ids(
            "sale.order.line",
            [("order_id", "in", sorted(order_ids))],
            self.registered_ids["sale.order.line"] | self._open_order_line_ids(),
            "fixture sales lines",
        )
        self._assert_same_ids(
            "stock.move",
            [("company_id", "=", company_id), ("product_id", "in", sorted(product_ids))],
            self.registered_ids["stock.move"] | self._open_order_move_ids(),
            "fixture stock moves",
        )
        prefixed_receipt_transfer_picking_ids = set()
        for movement in self.dataset.movements:
            if movement.kind == "vendor_receipt":
                key = f"picking_{movement.key.lower()}"
            elif movement.kind == "internal_transfer":
                key = f"picking_{movement.journey_key.lower()}"
            else:
                continue
            prefixed_receipt_transfer_picking_ids.add(self.record("stock_picking", key).id)
        self._assert_same_ids(
            "stock.picking",
            [("company_id", "=", company_id), ("move_ids.product_id", "in", sorted(product_ids))],
            picking_ids,
            "fixture stock pickings",
        )
        self._assert_same_ids(
            "stock.picking",
            [
                ("company_id", "=", company_id),
                "|", ("origin", "like", "IN-MA-%"), ("origin", "like", "TRANSFER-MA-%"),
            ],
            prefixed_receipt_transfer_picking_ids,
            "fixture-prefixed receipt/transfer pickings",
        )
        self._assert_same_ids(
            "autostock.morocco.history.profile",
            [("company_id", "=", company_id), ("dataset_version", "=", self.dataset.version)],
            self.registered_ids["autostock.morocco.history.profile"],
            "fixture history profiles",
        )
        self._assert_same_ids(
            "autostock.forecast.run",
            [("company_id", "=", company_id), ("demo_dataset_version", "=", self.dataset.version)],
            self.registered_ids["autostock.forecast.run"],
            "fixture forecast runs",
        )

    def _sale_pickings(self):
        pickings = []
        for order in list(self.orders.values()):
            record = self.record("completed_sale_order", order.key)
            pickings.extend(record.picking_ids.filtered(lambda row: row.picking_type_code == "outgoing"))
        for order in self.open_orders.values():
            record = self.record("open_sale_order", order.key)
            pickings.extend(record.picking_ids.filtered(lambda row: row.picking_type_code == "outgoing"))
        return pickings

    def _open_order_move_ids(self):
        return set(
            self.env["stock.move"].search(
                [
                    ("company_id", "=", self.company.id),
                    ("picking_id", "in", [self.record("open_sale_picking", f"out_{key}").id for key in self.open_orders]),
                ]
            ).ids
        )

    def _open_order_line_ids(self):
        return {
            line.id
            for key in self.open_orders
            for line in self.record("open_sale_order", key).order_line
        }
