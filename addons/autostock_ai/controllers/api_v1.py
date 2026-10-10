"""Purpose-built, session-authenticated API for the React AutoStock client.

Each route returns a small, versioned contract. Business values come from the
existing ORM services, which continue to enforce Odoo ACLs and record rules.
"""

from datetime import timedelta

from odoo import _, http
from odoo.addons.autostock_ai.models.forecast import REAL_SOURCE, SYNTHETIC_SOURCE
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
        return {
            "schema_version": 1,
            "company": self._company_contract(company),
            "snapshot_at": dashboard["as_of"],
            "kpis": {
                "tracked_products": dashboard["total_tracked"],
                "in_stock": sample["healthy"],
                "low_stock": sample["low"],
                "out_of_stock": sample["out"],
            },
            "inventory_health": {
                "total_tracked": dashboard["total_tracked"],
                "sampled_products": sample["total"],
                "complete": complete,
                "categories": [
                    {"key": "healthy", "label": _("In stock"), "count": sample["healthy"]},
                    {"key": "low", "label": _("Low stock"), "count": sample["low"]},
                    {"key": "out", "label": _("Out of stock"), "count": sample["out"]},
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
        return _("This stock location needs a review.")

    @staticmethod
    def _dashboard_priority(row):
        return row["reorder_needed"] or row["risk"] in {
            "out",
            "shortage",
            "low",
            "policy_missing",
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
        preview_items = []
        for row in priority_rows[:RESTOCK_PREVIEW_LIMIT]:
            preview_items.append(
                {
                    "key": row["key"],
                    "product_id": row["product_id"],
                    "template_id": row["template_id"],
                    "name": row["product_name"],
                    "sku": row["sku"],
                    "warehouse_id": row["warehouse_id"],
                    "warehouse": row["warehouse"],
                    "status": row["risk"],
                    "status_label": row["risk_label"],
                    "current_qty": row["on_hand"],
                    "uom": row["uom"],
                    "recommended_qty": (
                        row["recommended_qty"]
                        if row["reorder_needed"] and row["recommended_qty"] > 0
                        else False
                    ),
                    "supplier_name": (row["supplier"] or {}).get("name") or False,
                    "reason": self._restock_reason(row),
                    "basis_note": row["calculation_note"],
                }
            )

        reorder_suggestions = sum(
            1
            for row in priority_rows
            if row["reorder_needed"] and row["recommended_qty"] > 0
        )
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
        run = False
        if sales_access:
            real_domain = [
                ("company_id", "=", company.id),
                ("source_type", "=", REAL_SOURCE),
                ("state", "=", "completed"),
                ("evaluation_status", "in", list(SUPPORTED_EVALUATIONS)),
                ("horizon_days", "=", str(horizon)),
            ]
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

        if not run and company.autostock_demo_environment and not product and not warehouse:
            run = forecast_service.search(
                [
                    ("company_id", "=", company.id),
                    ("source_type", "=", SYNTHETIC_SOURCE),
                    ("state", "=", "completed"),
                    ("horizon_days", "=", str(horizon)),
                ],
                order="source_cutoff desc, id desc",
                limit=1,
            )

        if not run:
            if not sales_access and not company.autostock_demo_environment:
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
                "forecast": False,
            }

        end_date = run.history_end_date
        start_date = end_date - timedelta(days=FORECAST_HISTORY_WINDOW_DAYS - 1)
        source_type = run.source_type
        snapshot = forecast_service.get_forecast_snapshot(
            source_type=source_type,
            product_id=run.product_id.id if source_type == REAL_SOURCE else False,
            sku=run.sku if source_type == SYNTHETIC_SOURCE else False,
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
                "forecast": False,
            }

        return {
            "schema_version": 1,
            "company": self._company_contract(company),
            "status": "available",
            "reason_code": False,
            "message": False,
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
        domain = [
            ("active", "=", True),
            ("is_storable", "=", True),
            ("company_id", "in", [False, company.id]),
            "|",
            "|",
            ("name", "ilike", query),
            ("default_code", "ilike", query),
            ("autostock_oem_reference", "ilike", query),
        ]
        products = Product.search(domain, order="default_code, id", limit=9)
        limited = len(products) > 8
        return {
            "schema_version": 1,
            "query": query,
            "limited": limited,
            "results": [
                {
                    "id": product.id,
                    "template_id": product.product_tmpl_id.id,
                    "name": product.display_name,
                    "sku": product.default_code or "—",
                    "reference": product.autostock_oem_reference or False,
                }
                for product in products[:8]
            ],
        }
