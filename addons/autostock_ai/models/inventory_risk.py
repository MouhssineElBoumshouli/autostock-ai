"""Company/warehouse-scoped read-only stock-risk and reorder guidance."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from ml.inventory_risk import calculate_reorder, forecast_eligibility, recent_delivery_signal
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.float_utils import float_round

from .forecast import REAL_SOURCE

MAX_RISK_WAREHOUSES = 25
MAX_RISK_ROWS = 500
MAX_RISK_PAGE_ROWS = 100
MAX_SUPPLIER_FILTER_LINES = 20000
MAX_RISK_SUPPLIER_OPTIONS = 5000
MAX_FORECAST_CANDIDATES = 2000
MAX_OPEN_OUTBOUND_MOVES = 50000
MAX_PLANNING_LEAD_DAYS = 365
OPEN_MOVE_STATES = ("waiting", "confirmed", "assigned", "partially_available")
RISK_ORDER = {"out": 0, "shortage": 1, "low": 2, "overstock": 3, "slow_moving": 4, "healthy": 5, "policy_missing": 6}
RISK_LABELS = {
    "out": "Out of stock",
    "shortage": "Projected below reorder point",
    "low": "At reorder point",
    "overstock": "Above target",
    "slow_moving": "No recent deliveries",
    "healthy": "Within policy",
    "policy_missing": "No reorder policy",
}


class AutoStockInventoryRisk(models.AbstractModel):
    _name = "autostock.inventory.risk"
    _description = "AutoStock Read-only Inventory Risk Analysis"

    @api.model
    def _require_inventory_access(self):
        if not self.env.user.has_group("stock.group_stock_user"):
            raise AccessError(_("Inventory access is required to view stock-risk analysis."))

    @api.model
    def _company_env(self, company):
        return self.with_company(company).with_context(allowed_company_ids=[company.id])

    @api.model
    def _can_read(self, model):
        try:
            model.check_access("read")
        except AccessError:
            return False
        return True

    @api.model
    def _active_supplier(self, lines, product, company, today, preferred_supplier_id=False):
        relevant = lines.filtered(
            lambda line: line.product_tmpl_id == product.product_tmpl_id
            and (not line.product_id or line.product_id == product)
            and (not line.company_id or line.company_id == company)
            and (not line.date_start or line.date_start <= today)
            and (not line.date_end or line.date_end >= today)
        )
        if preferred_supplier_id:
            requested = relevant.filtered(
                lambda line: line.partner_id.id == preferred_supplier_id
            )
            if requested:
                relevant = requested
        if not relevant:
            return False
        # Prefer variant-specific and company-specific terms; sequence is the
        # native vendor preference. Native min_qty is only a price break.
        return min(
            relevant,
            key=lambda line: (
                not bool(line.product_id),
                not bool(line.company_id),
                line.sequence,
                line.min_qty,
                line.id,
            ),
        )

    @api.model
    def _supplier_domain(self, company, today, partner_id=False):
        domain = [("company_id", "in", [False, company.id])]
        if partner_id:
            domain.append(("partner_id", "=", partner_id))
        domain += [
            "|", ("date_start", "=", False), ("date_start", "<=", today),
            "|", ("date_end", "=", False), ("date_end", ">=", today),
        ]
        return domain

    @api.model
    def _product_warehouse_page(
        self, Product, product_domain, warehouses, total_products, offset, limit
    ):
        """Fetch a bounded slice from the warehouse-major product result set."""
        if not total_products:
            return []
        pairs = []
        page_end = offset + limit
        for warehouse_index, warehouse in enumerate(warehouses):
            warehouse_start = warehouse_index * total_products
            warehouse_end = warehouse_start + total_products
            start = max(offset, warehouse_start)
            end = min(page_end, warehouse_end)
            if start >= end:
                continue
            page_products = Product.search(
                product_domain,
                order="id",
                offset=start - warehouse_start,
                limit=end - start,
            )
            pairs.extend((product, warehouse) for product in page_products)
        return pairs

    @api.model
    def _forecast_for_pair(self, candidates, *, company, product, warehouse, lead_days, today, now):
        inspected = []
        for run in candidates:
            points = run.point_ids.sorted(key=lambda point: point.day)
            eligible, reason = forecast_eligibility(
                {
                    "company_id": run.company_id.id,
                    "product_id": run.product_id.id,
                    "warehouse_id": run.warehouse_id.id,
                    "source_type": run.source_type,
                    "state": run.state,
                    "evaluation_status": run.evaluation_status,
                    "review_status": run.review_status,
                    "horizon_days": int(run.horizon_days),
                    "evaluation_days": run.evaluation_days,
                    "history_days": run.history_days,
                    "nonzero_days": run.nonzero_days,
                    "history_end_date": run.history_end_date,
                    "source_cutoff": run.source_cutoff,
                },
                company_id=company.id,
                product_id=product.id,
                warehouse_id=warehouse.id,
                lead_time_days=lead_days,
                today=today,
                now=now,
                point_dates=[point.day for point in points],
            )
            inspected.append((run, points, eligible, reason))
        usable = [item for item in inspected if item[2]]
        if usable:
            run, points, eligibility_ok, reason = min(
                usable,
                key=lambda item: (
                    int(item[0].horizon_days),
                    -fields.Datetime.to_datetime(item[0].source_cutoff).timestamp(),
                    item[0].id,
                ),
            )
            return run, points, True, reason
        if inspected:
            # Explain the most recent exact-scope candidate rather than quietly
            # treating stale/unreviewed evidence as a usable forecast.
            run, points, eligibility_ok, reason = max(
                inspected,
                key=lambda item: (
                    fields.Datetime.to_datetime(item[0].source_cutoff), item[0].id
                ),
            )
            return run, points, False, reason
        return self.env["autostock.forecast.run"], self.env["autostock.forecast.point"], False, _(
            "No completed real delivery forecast is available for this warehouse."
        )

    @api.model
    def get_risk_data(
        self,
        warehouse_id=False,
        product_id=False,
        search="",
        supplier_id=False,
        risk_filter="all",
        history_from=False,
        history_to=False,
        offset=0,
    ):
        """Return one bounded page of read-only guidance for the active company."""
        self._require_inventory_access()
        company = self.env.company
        Scoped = self._company_env(company)
        Product = Scoped.env["product.product"]
        Warehouse = Scoped.env["stock.warehouse"]
        SupplierInfo = Scoped.env["product.supplierinfo"]
        can_read_suppliers = self._can_read(SupplierInfo)
        today = fields.Date.today()
        now = fields.Datetime.to_datetime(fields.Datetime.now())

        search = (search or "").strip()[:80]
        if risk_filter not in {"all", *RISK_LABELS.keys(), "recommendations"}:
            raise ValidationError(_("Choose a supported stock-risk filter."))
        date_from = fields.Date.to_date(history_from) if history_from else False
        date_to = fields.Date.to_date(history_to) if history_to else False
        if date_from and date_to and date_from > date_to:
            raise ValidationError(_("Forecast history start must be on or before its end."))

        if supplier_id:
            try:
                supplier_id = int(supplier_id)
            except (TypeError, ValueError) as error:
                raise ValidationError(_("Choose a valid supplier.")) from error
            if supplier_id <= 0:
                raise ValidationError(_("Choose a valid supplier."))
            if not can_read_suppliers:
                raise AccessError(_("Your Odoo role cannot read supplier terms for this filter."))
        try:
            offset = max(0, int(offset or 0))
        except (TypeError, ValueError) as error:
            raise ValidationError(_("Choose a valid stock-risk result page.")) from error

        warehouses_domain = [("company_id", "=", company.id)]
        total_warehouses = Warehouse.search_count(warehouses_domain)
        if warehouse_id:
            try:
                warehouse_id = int(warehouse_id)
            except (TypeError, ValueError):
                raise ValidationError(_("Choose a warehouse in the active company."))
            warehouses = Warehouse.search(warehouses_domain + [("id", "=", warehouse_id)], limit=1)
            if not warehouses:
                raise ValidationError(_("Choose a warehouse in the active company."))
        else:
            warehouses = Warehouse.search(warehouses_domain, order="name, id", limit=MAX_RISK_WAREHOUSES)

        product_domain = [
            ("active", "=", True),
            ("is_storable", "=", True),
            ("autostock_enabled", "=", True),
            ("company_id", "in", [False, company.id]),
        ]
        if product_id:
            try:
                product_id = int(product_id)
            except (TypeError, ValueError) as error:
                raise ValidationError(_("Choose a valid product.")) from error
            if product_id <= 0:
                raise ValidationError(_("Choose a valid product."))
            product_domain.append(("id", "=", product_id))
        if search:
            product_domain += [
                "|", "|",
                ("name", "ilike", search),
                ("default_code", "ilike", search),
                ("autostock_oem_reference", "ilike", search),
            ]
        supplier_filter_limited = False
        if supplier_id:
            supplier_filter_lines = SupplierInfo.search(
                self._supplier_domain(company, today, supplier_id),
                order="id",
                limit=MAX_SUPPLIER_FILTER_LINES + 1,
            )
            supplier_filter_limited = len(supplier_filter_lines) > MAX_SUPPLIER_FILTER_LINES
            supplier_filter_lines = supplier_filter_lines[:MAX_SUPPLIER_FILTER_LINES]
            general_templates = supplier_filter_lines.filtered(
                lambda line: not line.product_id
            ).mapped("product_tmpl_id").ids
            variant_products = supplier_filter_lines.filtered(
                lambda line: line.product_id
            ).mapped("product_id").ids
            if general_templates or variant_products:
                product_domain += [
                    "|",
                    ("product_tmpl_id", "in", general_templates),
                    ("id", "in", variant_products),
                ]
            else:
                product_domain.append(("id", "=", 0))
        total_products = Product.search_count(product_domain)

        all_company_warehouses = Warehouse.search(
            warehouses_domain, order="name, id", limit=MAX_RISK_WAREHOUSES
        )
        if warehouse_id and warehouses and warehouses.id not in all_company_warehouses.ids:
            all_company_warehouses |= warehouses
        total_pairs = total_products * len(warehouses)
        page_offset = min(offset, max(0, total_pairs - 1)) if total_pairs else 0
        pairs = self._product_warehouse_page(
            Product,
            product_domain,
            warehouses,
            total_products,
            page_offset,
            MAX_RISK_PAGE_ROWS,
        )
        products = Product.browse(sorted({product.id for product, _warehouse in pairs}))
        warehouse_scope_limited = total_warehouses > len(all_company_warehouses)
        has_next_page = page_offset + len(pairs) < total_pairs

        # Preserve native ACLs. If an account cannot read one source, it is
        # omitted and the result says what was unavailable; no sudo is used.
        Orderpoint = Scoped.env["stock.warehouse.orderpoint"]
        can_read_orderpoints = self._can_read(Orderpoint)
        orderpoints = Orderpoint.browse()
        if can_read_orderpoints and pairs:
            orderpoints = Orderpoint.search(
                [
                    ("company_id", "=", company.id),
                    ("warehouse_id", "in", warehouses.ids),
                    ("product_id", "in", products.ids),
                ],
                order="product_id, warehouse_id, location_id, id",
                limit=MAX_RISK_ROWS * 4,
            )
        orderpoints_lookup_limited = can_read_orderpoints and len(orderpoints) >= MAX_RISK_ROWS * 4
        orderpoints_by_pair = defaultdict(list)
        for rule in orderpoints:
            orderpoints_by_pair[(rule.product_id.id, rule.warehouse_id.id)].append(rule)

        supplier_lines = SupplierInfo.browse()
        if can_read_suppliers and pairs:
            supplier_lines = SupplierInfo.search(
                [
                    ("company_id", "in", [False, company.id]),
                    "|",
                    ("product_tmpl_id", "in", products.mapped("product_tmpl_id").ids),
                    ("product_id", "in", products.ids),
                ],
                order="sequence, min_qty, id",
                limit=MAX_SUPPLIER_FILTER_LINES + 1,
            )
        suppliers_lookup_limited = len(supplier_lines) > MAX_SUPPLIER_FILTER_LINES
        supplier_lines = supplier_lines[:MAX_SUPPLIER_FILTER_LINES]
        supplier_lines_by_template = defaultdict(lambda: SupplierInfo.browse())
        for line in supplier_lines:
            supplier_lines_by_template[line.product_tmpl_id.id] |= line

        sales_access = (
            self.env.user.has_group("sales_team.group_sale_salesman")
            or self.env.user.has_group("sales_team.group_sale_manager")
        )
        ForecastRun = Scoped.env["autostock.forecast.run"]
        ForecastPoint = Scoped.env["autostock.forecast.point"]
        StockMove = Scoped.env["stock.move"]
        can_read_forecasts = sales_access and self._can_read(ForecastRun) and self._can_read(ForecastPoint)
        can_read_moves = self._can_read(StockMove)
        forecast_access_available = can_read_forecasts and can_read_moves
        if not sales_access:
            forecast_access_reason = _(
                "Sales access is required to read delivery-history forecast evidence."
            )
        elif not can_read_forecasts:
            forecast_access_reason = _(
                "Your Odoo role cannot read reviewed delivery forecast records."
            )
        elif not can_read_moves:
            forecast_access_reason = _(
                "Your Odoo role cannot read scheduled customer deliveries, so forecast demand cannot be reconciled safely."
            )
        else:
            forecast_access_reason = _(
                "No completed real delivery forecast is available for this warehouse."
            )
        candidates_by_pair = defaultdict(list)
        forecast_candidates_truncated = False
        if forecast_access_available and pairs:
            candidate_runs = ForecastRun.search(
                [
                    ("company_id", "=", company.id),
                    ("product_id", "in", products.ids),
                    ("warehouse_id", "in", warehouses.ids),
                    ("source_type", "=", REAL_SOURCE),
                    ("state", "=", "completed"),
                ],
                order="source_cutoff desc, id desc",
                limit=MAX_FORECAST_CANDIDATES,
            )
            forecast_candidates_truncated = len(candidate_runs) >= MAX_FORECAST_CANDIDATES
            for run in candidate_runs:
                candidates_by_pair[(run.product_id.id, run.warehouse_id.id)].append(run)

        # Plan one Odoo-quantity scope per product/warehouse pair. A product
        # with overlapping native rules is deliberately ambiguous and does not
        # receive a numeric suggestion.
        work = []
        for product, warehouse in pairs:
            matching_rules = orderpoints_by_pair[(product.id, warehouse.id)]
            if not can_read_orderpoints:
                rule = False
                scope_location = warehouse.lot_stock_id
                policy_issue = _(
                    "Your Odoo role cannot read reordering rules, so a numeric quantity cannot be verified."
                )
            elif len(matching_rules) > 1:
                rule = False
                scope_location = warehouse.lot_stock_id
                policy_issue = _(
                    "Several active reordering rules cover this product and warehouse. "
                    "Review their locations before using one combined quantity."
                )
            elif len(matching_rules) == 1:
                rule = matching_rules[0]
                scope_location = rule.location_id
                policy_issue = False
            else:
                rule = False
                scope_location = warehouse.lot_stock_id
                policy_issue = False

            selected_supplier = self._active_supplier(
                supplier_lines_by_template[product.product_tmpl_id.id],
                product,
                company,
                today,
                preferred_supplier_id=supplier_id,
            ) if can_read_suppliers and not suppliers_lookup_limited else False
            if selected_supplier:
                lead_days = max(0, int(selected_supplier.delay or 0))
                lead_source = "supplier"
                lead_label = _("Supplier lead time")
            else:
                lead_days = max(0, int(product.autostock_lead_time_days or 0))
                lead_source = "manual"
                lead_label = _("Planning assumption")
            receipt_date = today + timedelta(days=lead_days)
            work.append(
                {
                    "product": product,
                    "warehouse": warehouse,
                    "rule": rule,
                    "rule_count": len(matching_rules),
                    "scope_location": scope_location,
                    "policy_issue": policy_issue,
                    "supplier": selected_supplier,
                    "lead_days": lead_days,
                    "lead_source": lead_source,
                    "lead_label": lead_label,
                    "receipt_date": receipt_date,
                }
            )

        # Group stock reads by location/warehouse/date so Odoo computes native
        # quantities in bounded batches with its record rules and company scope.
        move_groups = defaultdict(list)
        for item in work:
            location = item["scope_location"]
            scope_key = (item["warehouse"].id, location.id)
            if can_read_moves and item["lead_days"] <= MAX_PLANNING_LEAD_DAYS and not orderpoints_lookup_limited:
                move_groups[scope_key].append(item)

        committed_by_scope_product = defaultdict(list)
        move_lookup_limited = set()
        for scope_key, group in move_groups.items():
            warehouse = group[0]["warehouse"]
            location = group[0]["scope_location"]
            product_ids = sorted({item["product"].id for item in group})
            latest_receipt = max(item["receipt_date"] for item in group)
            moves = StockMove.search(
                [
                    ("company_id", "=", company.id),
                    ("product_id", "in", product_ids),
                    ("state", "in", list(OPEN_MOVE_STATES)),
                    ("sale_line_id", "!=", False),
                    ("location_id", "child_of", location.id),
                    # On multi-step routes, the sale-linked move that leaves
                    # stock can end at an internal output or transit location.
                    # Odoo's projected quantity already subtracts that move.
                    ("location_dest_id.usage", "in", ["internal", "customer"]),
                    ("date", "<=", fields.Datetime.to_string(datetime.combine(latest_receipt, time.max))),
                ],
                order="date, id",
                limit=MAX_OPEN_OUTBOUND_MOVES,
            )
            if len(moves) >= MAX_OPEN_OUTBOUND_MOVES:
                move_lookup_limited.add(scope_key)
            for move in moves:
                committed_by_scope_product[(scope_key, move.product_id.id)].append(move)

        chosen_runs = {}
        rows = []
        for item in work:
            product = item["product"]
            warehouse = item["warehouse"]
            rule = item["rule"]
            scope_location = item["scope_location"]
            scope_key = (warehouse.id, scope_location.id)
            run, points, forecast_usable, forecast_reason = self._forecast_for_pair(
                candidates_by_pair[(product.id, warehouse.id)],
                company=company,
                product=product,
                warehouse=warehouse,
                lead_days=item["lead_days"],
                today=today,
                now=now,
            ) if forecast_access_available else (
                ForecastRun.browse(), Scoped.env["autostock.forecast.point"].browse(), False,
                forecast_access_reason,
            )
            if forecast_access_available and forecast_candidates_truncated and not run:
                forecast_reason = _(
                    "Forecast lookup reached its result limit; this row could not be matched safely."
                )
            if run:
                chosen_runs[(product.id, warehouse.id)] = run

            quantity_context = {
                "allowed_company_ids": [company.id],
                "warehouse_id": warehouse.id,
                "location": scope_location.id,
            }
            current_product = product.with_context(**quantity_context)
            on_hand = current_product.qty_available
            free_qty = current_product.free_qty
            if item["lead_days"] <= MAX_PLANNING_LEAD_DAYS:
                projected_product = product.with_context(
                    **quantity_context, to_date=item["receipt_date"].isoformat()
                )
                projected_at_receipt = projected_product.virtual_available
                incoming_at_receipt = projected_product.incoming_qty
                outgoing_at_receipt = projected_product.outgoing_qty
            else:
                projected_at_receipt = current_product.virtual_available
                incoming_at_receipt = current_product.incoming_qty
                outgoing_at_receipt = current_product.outgoing_qty

            committed = 0.0
            lookup_limited = scope_key in move_lookup_limited
            for move in committed_by_scope_product[(scope_key, product.id)]:
                move_date = fields.Datetime.to_datetime(move.date).date()
                if move_date <= item["receipt_date"]:
                    committed += move.product_qty
            if lookup_limited and forecast_usable:
                forecast_usable = False
                forecast_reason = _(
                    "The confirmed-delivery lookup reached its safety limit; forecast demand "
                    "was not used because committed sales could not be reconciled safely."
                )

            forecast_demand = 0.0
            forecast_object = {
                "used": False,
                "status": "unavailable",
                "reason": forecast_reason,
                "run_id": run.id if run else False,
                "evaluation_status": run.evaluation_status if run else False,
                "review_status": run.review_status if run else False,
                "horizon_days": int(run.horizon_days) if run else False,
                "history_start": run.history_start_date.isoformat() if run and run.history_start_date else False,
                "history_end": run.history_end_date.isoformat() if run and run.history_end_date else False,
                "source_cutoff": fields.Datetime.to_string(run.source_cutoff) if run else False,
                "method": run.selected_method if run else False,
                "baseline_method": run.baseline_method if run else False,
                "evaluation_days": run.evaluation_days if run else 0,
                "baseline_mae": run.baseline_mae if run and run.baseline_method else False,
            }
            if forecast_usable:
                forecast_demand = sum(
                    point.units
                    for point in points
                    if today < point.day <= item["receipt_date"]
                )
                forecast_object.update(
                    {
                        "used": True,
                        "status": "reviewed_evaluated",
                        "reason": forecast_reason,
                    }
                )

            if item["rule_count"] > 1:
                minimum = target = None
                policy_source = "ambiguous"
            elif rule:
                minimum = rule.product_min_qty
                target = rule.product_max_qty
                policy_source = "odoo_reordering_rule"
            elif product.autostock_safety_stock > 0:
                minimum = target = product.autostock_safety_stock
                policy_source = "manual_safety_stock"
            else:
                minimum = target = None
                policy_source = "missing"
            if orderpoints_lookup_limited or not can_read_orderpoints:
                minimum = target = None
                policy_source = "unknown"

            supplier_minimum = 0.0
            supplier = item["supplier"]
            if supplier:
                supplier_uom = supplier.product_uom_id or product.uom_id
                supplier_minimum = supplier_uom._compute_quantity(
                    supplier.autostock_min_order_qty or 0.0,
                    product.uom_id,
                    round=False,
                )
            pack_multiple = 0.0
            if rule and rule.replenishment_uom_id:
                pack_multiple = rule.replenishment_uom_id._compute_quantity(
                    1.0, product.uom_id, round=False
                )

            calculation = calculate_reorder(
                on_hand=on_hand,
                free_qty=free_qty,
                projected_at_receipt=projected_at_receipt,
                committed_customer_outbound=committed,
                forecast_demand=forecast_demand,
                forecast_usable=forecast_usable,
                minimum_threshold=minimum,
                target_stock=target,
                supplier_minimum=supplier_minimum,
                pack_multiple=pack_multiple,
                product_rounding=product.uom_id.rounding,
            )
            if item["policy_issue"]:
                calculation["status"] = "policy_missing"
                calculation["recommended_qty"] = 0.0
                calculation["reorder_needed"] = False
            if orderpoints_lookup_limited:
                calculation["status"] = "policy_missing"
                calculation["recommended_qty"] = 0.0
                calculation["reorder_needed"] = False

            def rounded(value):
                return float_round(value or 0.0, precision_rounding=product.uom_id.rounding)

            status = calculation["status"]
            row = {
                "key": f"{product.id}-{warehouse.id}",
                "product_id": product.id,
                "template_id": product.product_tmpl_id.id,
                "warehouse_id": warehouse.id,
                "name": product.display_name,
                "product_name": product.product_tmpl_id.name,
                "sku": product.default_code or "—",
                "reference": product.autostock_oem_reference or "—",
                "category": product.categ_id.display_name or _("Uncategorized"),
                "warehouse": warehouse.display_name,
                "scope_location": scope_location.display_name,
                "uom": product.uom_id.display_name,
                "on_hand": rounded(on_hand),
                "free_qty": rounded(free_qty),
                "reserved_qty": rounded(on_hand - free_qty),
                "incoming_at_receipt": rounded(incoming_at_receipt),
                "outgoing_at_receipt": rounded(outgoing_at_receipt),
                "odoo_projected_at_receipt": rounded(projected_at_receipt),
                "projected_after_demand": rounded(calculation["projected_after_demand"]),
                "forecast_demand": rounded(calculation["forecast_demand"]),
                "committed_customer_outbound": rounded(committed),
                "additional_forecast_demand": rounded(calculation["additional_forecast_demand"]),
                "minimum_threshold": rounded(minimum) if minimum is not None else False,
                "target_stock": rounded(target) if target is not None else False,
                "policy_source": policy_source,
                "policy_issue": item["policy_issue"] or False,
                "target_gap": rounded(calculation["target_gap"]),
                "recommended_qty": rounded(calculation["recommended_qty"]),
                "supplier_minimum_product_qty": rounded(calculation["supplier_minimum"]),
                "pack_multiple_product_qty": rounded(calculation["pack_multiple"]),
                "reorder_needed": calculation["reorder_needed"],
                "risk": status,
                "risk_label": _(RISK_LABELS[status]),
                "lead_time_days": item["lead_days"],
                "lead_time_source": item["lead_source"],
                "lead_time_label": item["lead_label"],
                "receipt_date": item["receipt_date"].isoformat(),
                "forecast": forecast_object,
                "supplier": False,
                "slow_mover": False,
                "calculation_basis": "odoo_plus_reviewed_forecast" if forecast_usable else "odoo_policy_baseline",
                "calculation_note": (
                    _("Odoo projected stock at the stated receipt date, less forecast deliveries "
                      "not already represented by confirmed sale-linked outgoing moves.")
                    if forecast_usable
                    else _("Odoo projected stock at the stated receipt date only. Future demand "
                           "not yet recorded in Odoo is unknown and was not estimated.")
                ),
            }
            if supplier:
                row["supplier"] = {
                    "id": supplier.partner_id.id,
                    "name": supplier.partner_id.display_name,
                    "lead_days": max(0, int(supplier.delay or 0)),
                    "minimum_qty": rounded(supplier.autostock_min_order_qty or 0.0),
                    "minimum_uom": (supplier.product_uom_id or product.uom_id).display_name,
                    "price_tier_min_qty": rounded(supplier.min_qty or 0.0),
                    "price_tier_uom": (supplier.product_uom_id or product.uom_id).display_name,
                    "price": supplier.price,
                    "currency": supplier.currency_id.name,
                    "company_specific": bool(supplier.company_id),
                }
            elif not can_read_suppliers:
                row["supplier_access_note"] = _(
                    "Your role cannot read vendor terms. Lead time falls back to the product planning assumption."
                )
            elif suppliers_lookup_limited:
                row["supplier_access_note"] = _(
                    "Vendor lookup reached its result limit; terms could not be verified. "
                    "Lead time falls back to the product planning assumption."
                )
            elif not supplier_lines_by_template[product.product_tmpl_id.id]:
                row["supplier_access_note"] = _(
                    "No matching vendor terms are visible for this part; lead time falls back to the product planning assumption."
                )
            else:
                row["supplier_access_note"] = _(
                    "No matching active vendor terms are visible today; lead time falls back to the product planning assumption."
                )
            if not can_read_orderpoints:
                row["policy_source_label"] = _("Reordering rules unavailable to this role")
            elif item["policy_issue"]:
                row["policy_source_label"] = _("Multiple rules need location review")
            elif orderpoints_lookup_limited:
                row["policy_source_label"] = _("Reordering rules could not be verified")
            elif policy_source == "odoo_reordering_rule":
                row["policy_source_label"] = _("Odoo reordering rule")
            elif policy_source == "manual_safety_stock":
                row["policy_source_label"] = _("Manual product safety stock")
            else:
                row["policy_source_label"] = _("No trigger or target configured")
            if orderpoints_lookup_limited:
                row["policy_issue"] = _(
                    "Reordering-rule lookup reached its result limit; a numeric quantity cannot be verified."
                )
                row["calculation_basis"] = "policy_lookup_limited"
                row["calculation_note"] = row["policy_issue"]
                row["reorder_needed"] = False
                row["recommended_qty"] = 0.0
                row["risk"] = "policy_missing"
                row["risk_label"] = _(RISK_LABELS["policy_missing"])
            if suppliers_lookup_limited:
                row["lead_time_source"] = "manual"
                row["lead_time_label"] = _("Planning assumption; vendor lookup limited")
            if item["lead_days"] > MAX_PLANNING_LEAD_DAYS:
                row["calculation_basis"] = "lead_time_limit"
                row["calculation_note"] = _(
                    "Supplier lead time exceeds the 365-day planning limit; no reorder quantity is calculated."
                )
                row["reorder_needed"] = False
                row["recommended_qty"] = 0.0
                row["risk"] = "policy_missing"
                row["risk_label"] = _(RISK_LABELS["policy_missing"])
            rows.append(row)

        # Read only the selected runs' recent daily observations for a dated
        # inactivity signal. Insufficient coverage never becomes a slow-mover claim.
        used_run_ids = [
            row["forecast"]["run_id"]
            for row in rows
            if row["forecast"]["used"] and row["forecast"]["run_id"]
        ]
        recent_by_run = defaultdict(list)
        latest_delivery_by_run = {}
        Observation = Scoped.env["autostock.forecast.observation"]
        if used_run_ids and self._can_read(Observation):
            observations = Observation.search(
                [
                    ("run_id", "in", used_run_ids),
                    ("day", ">=", today - timedelta(days=89)),
                    ("day", "<=", today),
                ],
                order="run_id, day",
                limit=MAX_RISK_ROWS * 90,
            )
            for observation in observations:
                recent_by_run[observation.run_id.id].append(
                    {"day": observation.day, "delivered_units": observation.delivered_units}
                )
            latest_delivery_by_run = {
                run.id: day
                for run, day in Observation._read_group(
                    [
                        ("run_id", "in", used_run_ids),
                        ("delivered_units", ">", 0),
                        ("day", "<=", today),
                    ],
                    ["run_id"],
                    ["day:max"],
                )
                if day
            }
        for row in rows:
            forecast = row["forecast"]
            if not forecast["used"] or not forecast["run_id"]:
                continue
            run = chosen_runs[(row["product_id"], row["warehouse_id"])]
            signal = recent_delivery_signal(
                recent_by_run[forecast["run_id"]],
                today=today,
                history_start=run.history_start_date,
                history_end=run.history_end_date,
                last_delivery_date=latest_delivery_by_run.get(forecast["run_id"]),
            )
            if signal["available"] and signal["status"] == "no_recent_deliveries":
                row["slow_mover"] = signal
                if row["risk"] in ("healthy", "overstock"):
                    row["risk"] = "slow_moving"
                    row["risk_label"] = _(RISK_LABELS["slow_moving"])

        before_filters = len(rows)
        summary_rows = rows
        if date_from or date_to:
            def in_history_range(row):
                history_end = row["forecast"]["history_end"]
                if not history_end:
                    return False
                value = fields.Date.to_date(history_end)
                return (not date_from or value >= date_from) and (not date_to or value <= date_to)
            summary_rows = [row for row in summary_rows if in_history_range(row)]
        if risk_filter == "recommendations":
            rows = [row for row in summary_rows if row["reorder_needed"]]
        elif risk_filter != "all":
            rows = [row for row in summary_rows if row["risk"] == risk_filter]
        else:
            rows = summary_rows

        rows.sort(
            key=lambda row: (
                RISK_ORDER.get(row["risk"], 9),
                not row["reorder_needed"],
                row["name"].casefold(),
                row["warehouse"].casefold(),
            )
        )

        summary = {key: 0 for key in RISK_LABELS}
        for row in summary_rows:
            summary[row["risk"]] += 1
        supplier_option_lines = SupplierInfo.search(
            self._supplier_domain(company, today)
            + [
                ("product_tmpl_id.active", "=", True),
                ("product_tmpl_id.is_storable", "=", True),
                ("product_tmpl_id.autostock_enabled", "=", True),
                ("product_tmpl_id.company_id", "in", [False, company.id]),
            ],
            order="partner_id, id",
            limit=MAX_RISK_SUPPLIER_OPTIONS + 1,
        ) if can_read_suppliers else SupplierInfo.browse()
        supplier_options_limited = len(supplier_option_lines) > MAX_RISK_SUPPLIER_OPTIONS
        supplier_option_lines = supplier_option_lines[:MAX_RISK_SUPPLIER_OPTIONS]
        supplier_options = {
            partner.id: partner.display_name
            for partner in supplier_option_lines.mapped("partner_id")
        }
        page_count = (total_pairs + MAX_RISK_PAGE_ROWS - 1) // MAX_RISK_PAGE_ROWS
        pagination = {
            "offset": page_offset,
            "page_size": MAX_RISK_PAGE_ROWS,
            "page_number": page_offset // MAX_RISK_PAGE_ROWS + 1 if total_pairs else 0,
            "page_count": page_count,
            "candidate_pair_count": total_pairs,
            "candidate_product_count": total_products,
            "evaluated_pair_count": len(pairs),
            "matching_row_count": len(rows),
            "summary_row_count": len(summary_rows),
            "has_previous": page_offset > 0,
            "has_next": has_next_page,
            "previous_offset": max(0, page_offset - MAX_RISK_PAGE_ROWS) if page_offset else False,
            "next_offset": page_offset + MAX_RISK_PAGE_ROWS if has_next_page else False,
            "summary_scope": "current_page_after_supplier_and_history_filters",
            "supplier_filter_limited": supplier_filter_limited,
            "warehouse_scope_limited": warehouse_scope_limited,
        }
        return {
            "company_id": company.id,
            "company_name": company.display_name,
            "company_logo_url": f"/web/image/res.company/{company.id}/logo_web",
            "warehouse_id": warehouse_id or False,
            "warehouses": [
                {"id": warehouse.id, "name": warehouse.display_name}
                for warehouse in all_company_warehouses
            ],
            "suppliers": [
                {"id": partner_id, "name": name}
                for partner_id, name in sorted(supplier_options.items(), key=lambda item: item[1].casefold())
            ],
            "summary": summary,
            "recommendation_count": sum(1 for row in summary_rows if row["reorder_needed"]),
            "rows": rows,
            "row_count": len(rows),
            "unfiltered_row_count": before_filters,
            "total_products": total_products,
            "total_warehouses": total_warehouses,
            "total_pairs": total_pairs,
            "truncated": has_next_page or supplier_filter_limited or warehouse_scope_limited,
            "pagination": pagination,
            "supplier_filter_limited": supplier_filter_limited,
            "supplier_options_limited": supplier_options_limited,
            "warehouse_scope_limited": warehouse_scope_limited,
            "forecast_lookup_limited": forecast_candidates_truncated,
            "forecast_access_available": bool(forecast_access_available),
            "forecast_access_reason": (
                False if forecast_access_available else forecast_access_reason
            ),
            "supplier_lookup_limited": suppliers_lookup_limited,
            "reordering_rule_lookup_limited": orderpoints_lookup_limited,
            "supplier_terms_available": can_read_suppliers,
            "reordering_rules_available": bool(can_read_orderpoints),
            "sales_access": bool(sales_access),
            "purchase_installed": "purchase.order" in self.env.registry.models,
            "read_only": True,
            "max_lead_days": MAX_PLANNING_LEAD_DAYS,
            "as_of": fields.Datetime.to_string(now),
        }
