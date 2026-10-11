"""Purpose-built, session-authenticated API for the React AutoStock client.

Each route returns a small, versioned contract. Business values come from the
existing ORM services, which continue to enforce Odoo ACLs and record rules.
"""

from datetime import timedelta

from odoo import _, http
from odoo.fields import Domain
from odoo.addons.autostock_ai.models.forecast import REAL_SOURCE
from odoo.addons.autostock_ai.models.inventory_risk import RISK_ORDER
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request


RESTOCK_PREVIEW_LIMIT = 5
RESTOCK_SCAN_LIMIT = 500
FORECAST_HISTORY_WINDOW_DAYS = 60
SUPPORTED_EVALUATIONS = {"evaluated", "baseline_only", "intermittent_baseline"}


class AutoStockApiV1(http.Controller):
    @staticmethod
    def _json(payload, status=200):
        return request.make_json_response(payload, status=status)

    def _dispatch(self, callback):
        try:
            return self._json(callback())
        except AccessError as error:
            return self._json(
                {"error": {"code": "forbidden", "message": str(error)}}, status=403
            )
        except (ValidationError, UserError) as error:
            return self._json(
                {"error": {"code": "invalid_request", "message": str(error)}}, status=422
            )

    @staticmethod
    def _positive_int(value, label):
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise ValidationError(_("Choose a valid %(label)s.", label=label)) from error
        if parsed <= 0:
            raise ValidationError(_("Choose a valid %(label)s.", label=label))
        return parsed

    def _selected_company(self):
        requested_id = request.httprequest.args.get("company_id")
        if requested_id in (None, ""):
            return request.env.company
        company_id = self._positive_int(requested_id, _("company"))
        company = request.env.companies.filtered(lambda item: item.id == company_id)
        if not company:
            raise AccessError(_("That company is not available in your Odoo session."))
        return company[:1]

    @staticmethod
    def _scoped_model(model_name, company):
        return (
            request.env[model_name]
            .with_company(company)
            .with_context(allowed_company_ids=[company.id])
        )

    @staticmethod
    def _has_sales_access(user):
        return user.has_group("sales_team.group_sale_salesman") or user.has_group(
            "sales_team.group_sale_manager"
        )

    @staticmethod
    def _can_read(model):
        try:
            model.check_access("read")
        except AccessError:
            return False
        return True

    @staticmethod
    def _company_contract(company):
        currency = company.currency_id
        return {
            "id": company.id,
            "name": company.display_name,
            "logo_url": f"/web/image/res.company/{company.id}/logo_web",
            "currency": {
                "code": currency.name,
                "symbol": currency.symbol,
                "decimal_places": currency.decimal_places,
            },
            "demo_environment": bool(company.autostock_demo_environment),
            "demo_environment_note": (
                _(
                    "Fictional business records and generated forecast examples; "
                    "no real-world accuracy claim."
                )
                if company.autostock_demo_environment
                else False
            ),
        }

    @http.route(
        "/autostock/api/v1/session",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def session(self, **_kwargs):
        return self._dispatch(self._session_payload)

    def _session_payload(self):
        company = self._selected_company()
        user = request.env.user
        allowed_companies = sorted(
            request.env.companies, key=lambda item: item.name.casefold()
        )
        return {
            "schema_version": 1,
            "user": {
                "id": user.id,
                "name": user.display_name,
                "locale": user.lang or "en_US",
                "timezone": user.tz or "UTC",
                "permissions": {
                    "inventory": user.has_group("stock.group_stock_user"),
                    "sales": self._has_sales_access(user),
                    "inventory_manager": user.has_group("stock.group_stock_manager"),
                },
            },
            "current_company": self._company_contract(company),
            "allowed_companies": [self._company_contract(item) for item in allowed_companies],
            "authenticated": True,
        }

    @http.route(
        "/autostock/api/v1/dashboard",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def dashboard(self, **_kwargs):
        return self._dispatch(self._dashboard_payload)

    def _dashboard_payload(self):
        company = self._selected_company()
        dashboard = self._scoped_model("autostock.dashboard", company).get_dashboard_data()
        sample = dashboard["kpis"]
        complete = not dashboard["summary_incomplete"]
        reviewed_forecasts = False
        reviewed_forecasts_available = False
        if self._has_sales_access(request.env.user):
            ForecastRun = self._scoped_model("autostock.forecast.run", company)
            if self._can_read(ForecastRun):
                reviewed_forecasts = ForecastRun.search_count(
                    [
                        ("company_id", "=", company.id),
                        ("source_type", "=", REAL_SOURCE),
                        ("state", "=", "completed"),
                        ("review_status", "=", "reviewed"),
                        ("evaluation_status", "in", list(SUPPORTED_EVALUATIONS)),
                    ]
                )
                reviewed_forecasts_available = True
        sampled_products = sample["total"]
        return {
            "schema_version": 1,
            "company": self._company_contract(company),
            "snapshot_at": dashboard["as_of"],
            "kpis": {
                "tracked_products": dashboard["total_tracked"],
                "in_stock": sample["healthy"],
                "low_stock": sample["low"],
                "out_of_stock": sample["out"],
                "reviewed_forecasts": reviewed_forecasts,
                "reviewed_forecasts_available": reviewed_forecasts_available,
            },
            "inventory_health": {
                "total_tracked": dashboard["total_tracked"],
                "sampled_products": sampled_products,
                "complete": complete,
                "categories": [
                    {
                        "key": "healthy",
                        "label": _("In stock"),
                        "count": sample["healthy"],
                        "percent": round(sample["healthy"] * 100 / sampled_products) if sampled_products else 0,
                    },
                    {
                        "key": "low",
                        "label": _("Low stock"),
                        "count": sample["low"],
                        "percent": round(sample["low"] * 100 / sampled_products) if sampled_products else 0,
                    },
                    {
                        "key": "out",
                        "label": _("Out of stock"),
                        "count": sample["out"],
                        "percent": round(sample["out"] * 100 / sampled_products) if sampled_products else 0,
                    },
                ],
            },
            "empty": dashboard["total_tracked"] == 0,
        }

    @http.route(
        "/autostock/api/v1/dashboard/restock-preview",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def restock_preview(self, **_kwargs):
        return self._dispatch(self._restock_preview_payload)

    @staticmethod
    def _restock_reason(row):
        if row.get("policy_issue"):
            return row["policy_issue"]
        if row["risk"] == "out":
            return _("No stock is on hand at this warehouse.")
        if row["risk"] == "shortage":
            return _("Projected stock is below the configured reorder point.")
        if row["risk"] == "low":
            return _("Stock has reached the configured reorder trigger.")
        if row["risk"] == "policy_missing":
            return row.get("policy_source_label") or _(
                "A reorder trigger or target needs to be reviewed."
            )
        return _("This part location needs a review.")

    @staticmethod
    def _dashboard_priority(row):
        return row["reorder_needed"] or row["risk"] in {
            "out",
            "shortage",
            "low",
            "policy_missing",
        }

    @classmethod
    def _risk_item_payload(cls, row):
        forecast_used = bool(row["forecast"].get("used"))
        supplier = row.get("supplier") or {}
        return {
            "key": row["key"],
            "product_id": row["product_id"],
            "template_id": row["template_id"],
            "name": row["product_name"],
            "sku": row["sku"],
            "reference": row["reference"],
            "category": row["category"],
            "warehouse_id": row["warehouse_id"],
            "warehouse": row["warehouse"],
            "status": row["risk"],
            "status_label": row["risk_label"],
            "current_qty": row["on_hand"],
            "free_qty": row["free_qty"],
            "reserved_qty": row["reserved_qty"],
            "incoming_qty": row["incoming_at_receipt"],
            "outgoing_qty": row["outgoing_at_receipt"],
            "projected_qty": row["odoo_projected_at_receipt"],
            "projected_after_demand": row["projected_after_demand"],
            "forecast_demand": row["forecast_demand"] if forecast_used else False,
            "forecast_used": forecast_used,
            "forecast_reason": row["forecast"].get("reason") or False,
            "forecast_horizon_days": row["forecast"].get("horizon_days") or False,
            "forecast_review_status": row["forecast"].get("review_status") or False,
            "uom": row["uom"],
            "recommended_qty": (
                row["recommended_qty"]
                if row["reorder_needed"] and row["recommended_qty"] > 0
                else False
            ),
            "reorder_needed": bool(row["reorder_needed"]),
            "supplier_name": supplier.get("name") or False,
            "supplier": supplier or False,
            "supplier_access_note": row.get("supplier_access_note") or False,
            "reason": cls._restock_reason(row),
            "basis_note": row["calculation_note"],
            "lead_time_days": row["lead_time_days"],
            "lead_time_source": row["lead_time_source"],
            "lead_time_label": row["lead_time_label"],
            "minimum_threshold": row["minimum_threshold"],
            "target_stock": row["target_stock"],
            "policy_source": row["policy_source"],
            "policy_source_label": row["policy_source_label"],
            "policy_issue": row["policy_issue"],
            "calculation_basis": row["calculation_basis"],
        }

    def _restock_preview_payload(self):
        company = self._selected_company()
        raw_warehouse_id = request.httprequest.args.get("warehouse_id")
        warehouse_id = (
            self._positive_int(raw_warehouse_id, _("warehouse"))
            if raw_warehouse_id not in (None, "")
            else False
        )
        risk_service = self._scoped_model("autostock.inventory.risk", company)
        snapshot = risk_service.get_risk_data(warehouse_id=warehouse_id, offset=0)
        rows = list(snapshot["rows"])
        pagination = snapshot["pagination"]
        candidate_count = pagination["candidate_pair_count"]
        scanned_count = pagination["evaluated_pair_count"]
        incomplete_flags = {
            "warehouse_scope_limited": snapshot["warehouse_scope_limited"],
            "supplier_filter_limited": snapshot["supplier_filter_limited"],
            "forecast_lookup_limited": snapshot["forecast_lookup_limited"],
        }

        while pagination["has_next"] and scanned_count < min(
            candidate_count, RESTOCK_SCAN_LIMIT
        ):
            next_offset = pagination["next_offset"]
            if next_offset is False:
                break
            snapshot = risk_service.get_risk_data(
                warehouse_id=warehouse_id, offset=next_offset
            )
            rows.extend(snapshot["rows"])
            pagination = snapshot["pagination"]
            scanned_count += pagination["evaluated_pair_count"]
            for key in incomplete_flags:
                incomplete_flags[key] |= snapshot[key]

        priority_rows = [row for row in rows if self._dashboard_priority(row)]
        priority_rows.sort(
            key=lambda row: (
                RISK_ORDER.get(row["risk"], 9),
                not row["reorder_needed"],
                row["name"].casefold(),
                row["warehouse"].casefold(),
            )
        )
        complete = scanned_count >= candidate_count and not any(incomplete_flags.values())
        preview_items = [
            self._risk_item_payload(row)
            for row in priority_rows[:RESTOCK_PREVIEW_LIMIT]
        ]

        reorder_suggestions = sum(
            1
            for row in priority_rows
            if row["reorder_needed"] and row["recommended_qty"] > 0
        )
        out_of_stock = sum(1 for row in priority_rows if row["risk"] == "out")
        if reorder_suggestions == 0:
            reorder_description = _("No part locations have a suggested order ready for review.")
        elif reorder_suggestions == 1:
            reorder_description = _("1 part location has a suggested order ready for review.")
        else:
            reorder_description = _(
                "%(count)s part locations have a suggested order ready for review.",
                count=reorder_suggestions,
            )

        review_count = len(priority_rows)
        if review_count == 0:
            review_description = _("No part locations need review.")
        elif review_count == 1:
            review_description = _(
                "1 part location needs review because stock is low or empty, or its reorder rule needs attention."
            )
        else:
            review_description = _(
                "%(count)s part locations need review because stock is low or empty, or their reorder rules need attention.",
                count=review_count,
            )

        if out_of_stock == 0:
            out_of_stock_description = _("No part locations currently have zero stock.")
        elif out_of_stock == 1:
            out_of_stock_description = _(
                "1 part location currently has zero stock. This part may still have stock in another warehouse."
            )
        else:
            out_of_stock_description = _(
                "%(count)s part locations currently have zero stock. Some of those parts may still have stock in another warehouse.",
                count=out_of_stock,
            )
        limited_note = (
            _(" More part locations may need review beyond this scan.")
            if not complete
            else ""
        )
        insights = [
            {
                "id": "reorder-suggestions",
                "title": _("Reorder suggestions"),
                "description": reorder_description + limited_note,
                "icon": "reorder",
                "action": "view-reorder",
                "action_label": _("View top 5"),
            },
            {
                "id": "stock-review",
                "title": _("Part locations to review"),
                "description": review_description + limited_note,
                "icon": "trend",
                "action": "review-parts",
                "action_label": _("Review parts"),
            },
            {
                "id": "out-of-stock",
                "title": _("Warehouse stockouts"),
                "description": out_of_stock_description + limited_note,
                "icon": "vehicle",
                "action": "view-reorder",
                "action_label": _("View top 5"),
            },
        ]
        return {
            "schema_version": 1,
            "company": self._company_contract(company),
            "warehouse_id": warehouse_id or False,
            "warehouses": snapshot["warehouses"],
            "as_of": snapshot["as_of"],
            "read_only": True,
            "summary": {
                "priority_locations": len(priority_rows),
                "reorder_suggestions": reorder_suggestions,
                "complete": complete,
            },
            "items": preview_items,
            "insights": insights,
            "coverage": {
                "complete": complete,
                "scanned_locations": min(scanned_count, RESTOCK_SCAN_LIMIT),
                "candidate_locations": candidate_count,
                "scan_limit": RESTOCK_SCAN_LIMIT,
                "flags": incomplete_flags,
            },
        }

    @http.route(
        "/autostock/api/v1/dashboard/forecast-preview",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def forecast_preview(self, **_kwargs):
        return self._dispatch(self._forecast_preview_payload)

    def _forecast_preview_payload(self):
        company = self._selected_company()
        user = request.env.user
        forecast_service = self._scoped_model("autostock.forecast.run", company)
        horizon = forecast_service._validated_horizon(
            request.httprequest.args.get("horizon_days", "30")
        )
        raw_product_id = request.httprequest.args.get("product_id")
        raw_warehouse_id = request.httprequest.args.get("warehouse_id")
        product = False
        warehouse = False
        if raw_product_id not in (None, ""):
            product = forecast_service._scoped_product(
                self._positive_int(raw_product_id, _("product")), company
            )
        if raw_warehouse_id not in (None, ""):
            warehouse = forecast_service._scoped_warehouse(
                self._positive_int(raw_warehouse_id, _("warehouse")), company
            )

        sales_access = self._has_sales_access(user)
        forecast_access = sales_access and self._can_read(forecast_service)
        run = False
        forecast_options = []
        forecast_options_limited = False
        if forecast_access:
            options_domain = [
                ("company_id", "=", company.id),
                ("source_type", "=", REAL_SOURCE),
                ("state", "=", "completed"),
                ("evaluation_status", "in", list(SUPPORTED_EVALUATIONS)),
                ("horizon_days", "=", str(horizon)),
            ]
            option_runs = forecast_service.search(
                options_domain,
                order="source_cutoff desc, id desc",
                limit=101,
            )
            forecast_options_limited = len(option_runs) > 100
            seen_options = set()
            for option_run in option_runs[:100]:
                option_product = option_run.product_id
                if (
                    not option_product
                    or not option_product.active
                    or not option_product.is_storable
                    or not option_product.autostock_enabled
                    or (
                        option_product.company_id
                        and option_product.company_id.id != company.id
                    )
                ):
                    continue
                key = (option_product.id, option_run.warehouse_id.id or False)
                if key in seen_options:
                    continue
                seen_options.add(key)
                forecast_options.append(
                    {
                        "key": f"{key[0]}-{key[1] or 0}",
                        "product_id": key[0],
                        "name": option_product.product_tmpl_id.name,
                        "sku": option_product.default_code or "—",
                        "warehouse_id": key[1],
                        "warehouse": option_run.warehouse_id.display_name or False,
                    }
                )

            real_domain = list(options_domain)
            if product:
                real_domain.append(("product_id", "=", product.id))
            if warehouse:
                real_domain.append(("warehouse_id", "=", warehouse.id))

            if company.autostock_demo_environment and horizon == 30:
                run = forecast_service.search(
                    real_domain + [("review_status", "=", "reviewed")],
                    order="source_cutoff desc, id desc",
                    limit=1,
                )
            if not run:
                run = forecast_service.search(
                    real_domain, order="source_cutoff desc, id desc", limit=1
                )

        if not run:
            if not forecast_access:
                reason_code = "sales_access_required"
                message = _(
                    "Your Odoo role does not include access to completed delivery history."
                )
                status = "restricted"
            else:
                reason_code = "no_evaluated_forecast"
                message = _(
                    "No completed, evaluated forecast is available for this company and horizon."
                )
                status = "unavailable"
            return {
                "schema_version": 1,
                "company": self._company_contract(company),
                "status": status,
                "reason_code": reason_code,
                "message": message,
                "options": forecast_options,
                "options_limited": forecast_options_limited,
                "forecast": False,
            }

        end_date = run.history_end_date
        start_date = end_date - timedelta(days=FORECAST_HISTORY_WINDOW_DAYS - 1)
        source_type = run.source_type
        snapshot = forecast_service.get_forecast_snapshot(
            source_type=source_type,
            product_id=run.product_id.id if source_type == REAL_SOURCE else False,
            sku=False,
            horizon_days=horizon,
            warehouse_id=(
                run.warehouse_id.id if source_type == REAL_SOURCE and run.warehouse_id else False
            ),
            chart_start=start_date,
            chart_end=end_date,
        )
        data = snapshot.get("run")
        if not data:
            return {
                "schema_version": 1,
                "company": self._company_contract(company),
                "status": "unavailable",
                "reason_code": "forecast_changed",
                "message": _("The selected forecast is no longer available. Refresh to try again."),
                "options": forecast_options,
                "options_limited": forecast_options_limited,
                "forecast": False,
            }

        return {
            "schema_version": 1,
            "company": self._company_contract(company),
            "status": "available",
            "reason_code": False,
            "message": False,
            "options": forecast_options,
            "options_limited": forecast_options_limited,
            "forecast": {
                "id": data["id"],
                "product_name": data["product_name"],
                "sku": data["sku"],
                "warehouse_name": run.warehouse_id.display_name or False,
                "horizon_days": data["horizon_days"],
                "uom": (run.uom_id.display_name if run.uom_id else _("units")),
                "source_type": data["source_type"],
                "source_label": data["source_label"],
                "review_status": data["review_status"],
                "evaluation_status": data["evaluation_status"],
                "history_start": data["history_start"],
                "history_end": data["history_end"],
                "history": [
                    {"date": item["day"], "units": item["units"]}
                    for item in data["observations"]
                ],
                "predictions": [
                    {
                        "date": item["day"],
                        "units": item["units"],
                        "lower": item["lower_heuristic"],
                        "upper": item["upper_heuristic"],
                    }
                    for item in data["predictions"]
                ],
                "limitations": data["limitations"],
            },
        }

    @http.route(
        "/autostock/api/v1/search/products",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def search_products(self, **_kwargs):
        return self._dispatch(self._search_products_payload)

    def _search_products_payload(self):
        company = self._selected_company()
        query = (request.httprequest.args.get("q") or "").strip()[:80]
        if not request.env.user.has_group("stock.group_stock_user"):
            raise AccessError(_("Inventory access is required to search the product catalog."))
        if len(query) < 2:
            return {"schema_version": 1, "query": query, "results": [], "limited": False}

        Product = self._scoped_model("product.product", company)
        catalog_domain = [
            ("active", "=", True),
            ("is_storable", "=", True),
            ("company_id", "in", [False, company.id]),
        ]
        matching_domains = [
            Domain.OR([
                Domain([("name", "ilike", query)]),
                Domain([("default_code", "ilike", query)]),
                Domain([("autostock_oem_reference", "ilike", query)]),
            ])
        ]
        SupplierInfo = self._scoped_model("product.supplierinfo", company)
        supplier_lines = SupplierInfo.browse()
        supplier_lookup_limited = False
        if self._can_read(SupplierInfo):
            supplier_lines = SupplierInfo.search(
                [
                    ("company_id", "in", [False, company.id]),
                    ("partner_id.name", "ilike", query),
                ],
                order="id",
                limit=2001,
            )
            supplier_lookup_limited = len(supplier_lines) > 2000
            supplier_lines = supplier_lines[:2000]
            template_ids = supplier_lines.mapped("product_tmpl_id").ids
            variant_ids = supplier_lines.mapped("product_id").ids
            if template_ids or variant_ids:
                matching_domains.append(
                    Domain.OR(
                        [
                            Domain([("product_tmpl_id", "in", template_ids)]) if template_ids else Domain([("id", "=", 0)]),
                            Domain([("id", "in", variant_ids)]) if variant_ids else Domain([("id", "=", 0)]),
                        ]
                    )
                )
        domain = Domain(catalog_domain) & Domain.OR(matching_domains)
        products = Product.search(domain, order="default_code, id", limit=9)
        limited = len(products) > 8 or supplier_lookup_limited

        def matching_supplier_names(product):
            return sorted(
                {
                    line.partner_id.display_name
                    for line in supplier_lines
                    if line.product_tmpl_id == product.product_tmpl_id
                    and (not line.product_id or line.product_id == product)
                },
                key=str.casefold,
            )

        return {
            "schema_version": 1,
            "query": query,
            "limited": limited,
            "results": [
                {
                    "id": product.id,
                    "template_id": product.product_tmpl_id.id,
                    "name": product.product_tmpl_id.name,
                    "sku": product.default_code or "—",
                    "reference": product.autostock_oem_reference or False,
                    "category": product.categ_id.display_name or _("Uncategorized"),
                    "supplier_names": matching_supplier_names(product),
                }
                for product in products[:8]
            ],
        }

    @http.route(
        "/autostock/api/v1/products/<int:product_id>/quick-view",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def product_quick_view(self, product_id, **_kwargs):
        return self._dispatch(lambda: self._product_quick_view_payload(product_id))

    def _product_quick_view_payload(self, product_id):
        company = self._selected_company()
        if not request.env.user.has_group("stock.group_stock_user"):
            raise AccessError(_("Inventory access is required to view product details."))
        Product = self._scoped_model("product.product", company)
        product = Product.search(
            [
                ("id", "=", product_id),
                ("active", "=", True),
                ("is_storable", "=", True),
                ("company_id", "in", [False, company.id]),
            ],
            limit=1,
        )
        if not product:
            raise AccessError(_("That part is not available in the selected company."))

        positions = []
        coverage = {
            "complete": True,
            "candidate_locations": 0,
            "scanned_locations": 0,
        }
        tracked = bool(product.autostock_enabled)
        if tracked:
            risk_data = self._scoped_model("autostock.inventory.risk", company).get_risk_data(
                product_id=product.id,
                offset=0,
            )
            rows = list(risk_data["rows"])
            rows.sort(
                key=lambda row: (
                    RISK_ORDER.get(row["risk"], 9),
                    not row["reorder_needed"],
                    row["warehouse"].casefold(),
                )
            )
            positions = [self._risk_item_payload(row) for row in rows]
            pagination = risk_data["pagination"]
            coverage = {
                "complete": not risk_data["warehouse_scope_limited"]
                and not pagination["has_next"],
                "candidate_locations": pagination["candidate_pair_count"],
                "scanned_locations": pagination["evaluated_pair_count"],
            }
        return {
            "schema_version": 1,
            "company": self._company_contract(company),
            "read_only": True,
            "product": {
                "id": product.id,
                "template_id": product.product_tmpl_id.id,
                "name": product.product_tmpl_id.name,
                "sku": product.default_code or "—",
                "reference": product.autostock_oem_reference or False,
                "category": product.categ_id.display_name or _("Uncategorized"),
                "tracked": tracked,
            },
            "positions": positions,
            "coverage": coverage,
        }

    @http.route(
        "/autostock/api/v1/inventory/options",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def inventory_options(self, **_kwargs):
        return self._dispatch(self._inventory_options_payload)

    def _inventory_options_payload(self):
        company = self._selected_company()
        supplier_query = (request.httprequest.args.get("supplier_q") or "").strip()[:80]
        result = self._scoped_model("autostock.inventory.catalog", company).get_options(
            supplier_query=supplier_query
        )
        return {"schema_version": 1, "company": self._company_contract(company), **result}

    @http.route(
        "/autostock/api/v1/inventory",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def inventory(self, **_kwargs):
        return self._dispatch(self._inventory_payload)

    def _inventory_payload(self):
        company = self._selected_company()
        args = request.httprequest.args
        result = self._scoped_model("autostock.inventory.catalog", company).get_inventory_page(
            query=args.get("q", ""),
            supplier_query=args.get("supplier_q", ""),
            status=args.get("status", "all"),
            warehouse_id=args.get("warehouse_id"),
            category_id=args.get("category_id"),
            supplier_id=args.get("supplier_id"),
            tracked=args.get("tracked", "all"),
            active=args.get("active", "active"),
            sort=args.get("sort", "name"),
            direction=args.get("direction", "asc"),
            page=args.get("page", 1),
            page_size=args.get("page_size", 25),
        )
        return {"schema_version": 1, "company": self._company_contract(company), **result}

    @http.route(
        "/autostock/api/v1/products/<int:product_id>/inventory-detail",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def product_inventory_detail(self, product_id, **_kwargs):
        return self._dispatch(
            lambda: self._product_inventory_detail_payload(product_id)
        )

    def _product_inventory_detail_payload(self, product_id):
        company = self._selected_company()
        warehouse_id = request.httprequest.args.get("warehouse_id")
        result = self._scoped_model(
            "autostock.inventory.catalog", company
        ).get_product_detail(product_id, warehouse_id=warehouse_id)
        recommendations = [
            self._risk_item_payload(row)
            for row in result.pop("recommendation_rows")
        ]
        return {
            "schema_version": 1,
            "company": self._company_contract(company),
            **result,
            "recommendations": recommendations,
        }

    @http.route(
        "/autostock/api/v1/warehouses",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def warehouses(self, **_kwargs):
        return self._dispatch(self._warehouses_payload)

    def _warehouses_payload(self):
        company = self._selected_company()
        args = request.httprequest.args
        result = self._scoped_model(
            "autostock.inventory.catalog", company
        ).get_warehouse_page(
            query=args.get("q", ""),
            status=args.get("status", "all"),
            sort=args.get("sort", "name"),
            direction=args.get("direction", "asc"),
            page=args.get("page", 1),
            page_size=args.get("page_size", 12),
        )
        return {"schema_version": 1, "company": self._company_contract(company), **result}

    @http.route(
        "/autostock/api/v1/warehouses/<int:warehouse_id>",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def warehouse_detail(self, warehouse_id, **_kwargs):
        return self._dispatch(lambda: self._warehouse_detail_payload(warehouse_id))

    def _warehouse_detail_payload(self, warehouse_id):
        company = self._selected_company()
        result = self._scoped_model(
            "autostock.inventory.catalog", company
        ).get_warehouse_detail(warehouse_id)
        return {"schema_version": 1, "company": self._company_contract(company), **result}

    @http.route(
        "/autostock/api/v1/warehouses/<int:warehouse_id>/inventory",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def warehouse_inventory(self, warehouse_id, **_kwargs):
        return self._dispatch(
            lambda: self._warehouse_inventory_payload(warehouse_id)
        )

    def _warehouse_inventory_payload(self, warehouse_id):
        company = self._selected_company()
        args = request.httprequest.args
        result = self._scoped_model(
            "autostock.inventory.catalog", company
        ).get_inventory_page(
            query=args.get("q", ""),
            supplier_query=args.get("supplier_q", ""),
            status=args.get("status", "all"),
            warehouse_id=warehouse_id,
            category_id=args.get("category_id"),
            supplier_id=args.get("supplier_id"),
            tracked=args.get("tracked", "all"),
            active=args.get("active", "active"),
            sort=args.get("sort", "name"),
            direction=args.get("direction", "asc"),
            page=args.get("page", 1),
            page_size=args.get("page_size", 25),
        )
        return {"schema_version": 1, "company": self._company_contract(company), **result}
