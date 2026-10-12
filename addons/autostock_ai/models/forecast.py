"""Permission-aware demand forecast requests and bounded cron processing."""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, time, timedelta
from hashlib import sha256

from ml.forecast import MODEL_VERSION, Observation, forecast_daily
from ml.synthetic import DEMO_SKUS, SYNTHETIC_DATASET_VERSION, generate_synthetic_history
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Domain
from odoo.tools.float_utils import float_round

_logger = logging.getLogger(__name__)

MAX_HISTORY_DAYS = 730
MAX_SOURCE_MOVES = 50_000
MAX_RUNS_PER_CRON = 2
SUPPORTED_HORIZONS = {7, 30, 60}
REAL_SOURCE = "completed_deliveries"
SYNTHETIC_SOURCE = "synthetic_demo"

REAL_PROVENANCE = (
    "Completed Odoo 19 stock moves linked to confirmed sale order lines. "
    "Customer deliveries are internal-to-customer moves. Completed linked customer "
    "returns are recorded on their actual UTC return day for audit and are excluded "
    "from the delivered-demand series; they never rewrite the original delivery day. "
    "Only the selected company and optional warehouse are queried."
)
REAL_ASSUMPTIONS = (
    "Daily demand values are gross fulfilled sales in the product inventory unit, dated "
    "by the completed delivery's UTC processing timestamp. Completed returns are kept "
    "as separate audit events on their actual UTC completion date and do not reduce a "
    "past delivery or become negative demand. Returned stock is reflected by Odoo's "
    "inventory movements. A configured history coverage start date is required; days "
    "without completed deliveries are zero fulfilled sales. This is a delivered-sales "
    "proxy, not unconstrained demand."
)
REAL_LIMITATIONS = (
    "Odoo does not provide historical lost-demand or stockout-censoring observations "
    "in this workflow. Stockouts may therefore make fulfilled sales understate demand. "
    "Odoo also does not provide a complete as-of history of later edits to completed "
    "moves. A historical snapshot replays completed delivery dates as currently stored "
    "at its source cutoff; it cannot prove what was known at every past forecast origin. "
    "Do not use this proxy as an automatic purchasing instruction."
)


class ResCompany(models.Model):
    _inherit = "res.company"

    autostock_history_complete_from = fields.Date(
        string="AutoStock complete sales history from",
        help=(
            "Earliest UTC date from which this company's completed delivery and return "
            "records are known to be complete. AutoStock refuses real forecasts before "
            "this date is configured."
        ),
    )


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    autostock_history_complete_from = fields.Date(
        string="AutoStock complete sales history from",
        help=(
            "Earliest UTC date from which this warehouse's completed delivery and return "
            "records are known to be complete. Required for warehouse-specific forecasts."
        ),
    )


class AutoStockForecastRun(models.Model):
    _name = "autostock.forecast.run"
    _description = "AutoStock Evaluated Demand Forecast"
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, readonly=True)
    company_id = fields.Many2one("res.company", required=True, index=True, readonly=True)
    warehouse_id = fields.Many2one("stock.warehouse", index=True, readonly=True)
    product_id = fields.Many2one("product.product", index=True, readonly=True)
    demo_history_profile_id = fields.Many2one(
        "autostock.morocco.history.profile", index=True, readonly=True, ondelete="restrict"
    )
    demo_dataset_version = fields.Char(readonly=True, index=True)
    product_name = fields.Char(readonly=True)
    sku = fields.Char(required=True, index=True, readonly=True)
    uom_id = fields.Many2one("uom.uom", readonly=True)
    source_type = fields.Selection(
        [(REAL_SOURCE, "Completed Odoo deliveries"), (SYNTHETIC_SOURCE, "Synthetic demo")],
        required=True,
        index=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("queued", "Queued"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("insufficient_history", "Insufficient history"),
            ("no_observed_demand", "No observed demand"),
            ("failed", "Failed"),
        ],
        required=True,
        default="queued",
        index=True,
        readonly=True,
    )
    evaluation_status = fields.Char(readonly=True)
    review_status = fields.Selection(
        [("unreviewed", "Not reviewed"), ("reviewed", "Reviewed")],
        default="unreviewed",
        required=True,
        readonly=True,
    )
    reviewed_by_id = fields.Many2one("res.users", readonly=True)
    reviewed_at = fields.Datetime(readonly=True)
    created_by_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user, readonly=True
    )
    horizon_days = fields.Selection(
        [("7", "7 days"), ("30", "30 days"), ("60", "60 days")],
        required=True,
        readonly=True,
    )
    history_start_date = fields.Date(required=True, readonly=True)
    history_end_date = fields.Date(required=True, readonly=True)
    source_cutoff = fields.Datetime(required=True, readonly=True)
    source_timezone = fields.Char(default="UTC", required=True, readonly=True)
    history_days = fields.Integer(readonly=True)
    nonzero_days = fields.Integer(readonly=True)
    source_event_count = fields.Integer(readonly=True)
    source_snapshot_sha256 = fields.Char(readonly=True)
    model_version = fields.Char(readonly=True)
    model_parameters = fields.Text(readonly=True)
    selected_method = fields.Char(readonly=True)
    baseline_method = fields.Char(readonly=True)
    demand_pattern = fields.Char(readonly=True)
    evaluation_days = fields.Integer(readonly=True)
    baseline_mae = fields.Float(readonly=True)
    ml_mae = fields.Float(readonly=True)
    ml_evaluated = fields.Boolean(readonly=True)
    data_provenance = fields.Text(readonly=True)
    assumptions = fields.Text(readonly=True)
    limitations = fields.Text(readonly=True)
    interval_note = fields.Text(readonly=True)
    failure_reason = fields.Text(readonly=True)
    observation_ids = fields.One2many(
        "autostock.forecast.observation", "run_id", readonly=True
    )
    point_ids = fields.One2many("autostock.forecast.point", "run_id", readonly=True)

    @api.model
    def _require_inventory_access(self):
        if not self.env.user.has_group("stock.group_stock_user"):
            raise AccessError(_("Inventory access is required to use demand forecasting."))

    @api.model
    def _require_sales_access(self):
        if not (
            self.env.user.has_group("sales_team.group_sale_salesman")
            or self.env.user.has_group("sales_team.group_sale_manager")
        ):
            raise AccessError(
                _("Sales access is required to forecast from completed customer deliveries.")
            )

    @api.model
    def _validated_horizon(self, value):
        try:
            horizon = int(value)
        except (TypeError, ValueError) as error:
            raise ValidationError(_("Choose a 7, 30, or 60 day forecast horizon.")) from error
        if horizon not in SUPPORTED_HORIZONS:
            raise ValidationError(_("Choose a 7, 30, or 60 day forecast horizon."))
        return horizon

    @api.model
    def get_forecast_page(
        self,
        query="",
        warehouse_id=False,
        horizon_days="all",
        state="all",
        review_status="all",
        source_type="all",
        page=1,
        page_size=25,
    ):
        """Return an exact-count, company-scoped page of saved forecast runs."""
        self._require_inventory_access()
        company = self.env.company
        query = (query or "").strip()[:80]

        def positive_page_value(value, label, *, default, maximum=False):
            try:
                parsed = int(value or default)
            except (TypeError, ValueError) as error:
                raise ValidationError(_("Choose a valid %(label)s.", label=label)) from error
            if parsed <= 0 or (maximum and parsed > maximum):
                if maximum:
                    raise ValidationError(
                        _("Choose a %(label)s between 1 and %(maximum)s.", label=label, maximum=maximum)
                    )
                raise ValidationError(_("Choose a valid %(label)s.", label=label))
            return parsed

        try:
            page = positive_page_value(page, _("page"), default=1)
            page_size = positive_page_value(page_size, _("page size"), default=25, maximum=50)
        except ValidationError:
            raise

        if horizon_days not in (None, "", "all", False):
            horizon = self._validated_horizon(horizon_days)
        else:
            horizon = False

        allowed_states = {
            "queued", "running", "completed", "insufficient_history",
            "no_observed_demand", "failed",
        }
        if state not in (None, "", "all", False, *allowed_states):
            raise ValidationError(_("Choose a supported forecast status."))
        if review_status not in (None, "", "all", False, "reviewed", "unreviewed"):
            raise ValidationError(_("Choose a supported review status."))
        if source_type not in (None, "", "all", False, REAL_SOURCE, SYNTHETIC_SOURCE):
            raise ValidationError(_("Choose a supported forecast source."))

        if warehouse_id not in (None, "", False):
            warehouse = self._scoped_warehouse(
                self._positive_id(warehouse_id, _("warehouse")), company
            )
        else:
            warehouse = self.env["stock.warehouse"]

        sales_access = self.env.user.has_group("sales_team.group_sale_salesman") or self.env.user.has_group(
            "sales_team.group_sale_manager"
        )
        if not sales_access and source_type == REAL_SOURCE:
            raise AccessError(_("Sales access is required to read completed delivery forecast history."))

        domain = [("company_id", "=", company.id)]
        if not sales_access:
            # Stock users may still inspect isolated synthetic showroom examples.
            # Never reveal real-run counts or metadata without sales access.
            domain.append(("source_type", "=", SYNTHETIC_SOURCE))
        elif source_type not in (None, "", "all", False):
            domain.append(("source_type", "=", source_type))
        if warehouse:
            domain.append(("warehouse_id", "=", warehouse.id))
        if horizon:
            domain.append(("horizon_days", "=", str(horizon)))
        if state not in (None, "", "all", False):
            domain.append(("state", "=", state))
        if review_status not in (None, "", "all", False):
            domain.append(("review_status", "=", review_status))
        if query:
            domain.extend([
                "|",
                ("product_name", "ilike", query),
                ("sku", "ilike", query),
            ])

        Run = self.with_company(company).with_context(allowed_company_ids=[company.id])
        total_count = Run.search_count(domain)
        total_pages = (total_count + page_size - 1) // page_size
        page = min(page, max(total_pages, 1))
        runs = Run.search(
            domain,
            order="create_date desc, id desc",
            offset=(page - 1) * page_size,
            limit=page_size,
        )

        Warehouse = self.env["stock.warehouse"].with_company(company).with_context(
            allowed_company_ids=[company.id]
        )
        warehouse_count = Warehouse.search_count([("company_id", "=", company.id)])
        warehouse_options = Warehouse.search(
            [("company_id", "=", company.id)], order="name, id", limit=101
        )
        warehouses_limited = len(warehouse_options) > 100
        warehouse_options = warehouse_options[:100]

        return {
            "filters": {
                "query": query,
                "warehouse_id": warehouse.id if warehouse else False,
                "horizon_days": horizon or "all",
                "state": state or "all",
                "review_status": review_status or "all",
                "source_type": source_type or "all",
            },
            "runs": [
                {
                    "id": run.id,
                    "product_id": run.product_id.id if run.product_id else False,
                    "product_name": (
                        run.product_id.with_context(display_default_code=False).display_name
                        if run.source_type == REAL_SOURCE and run.product_id
                        else run.product_name or run.sku
                    ),
                    "sku": run.sku,
                    "warehouse_id": run.warehouse_id.id if run.warehouse_id else False,
                    "warehouse_name": run.warehouse_id.display_name if run.warehouse_id else False,
                    "horizon_days": int(run.horizon_days),
                    "history_start": run.history_start_date.isoformat(),
                    "history_end": run.history_end_date.isoformat(),
                    "source_cutoff": fields.Datetime.to_string(run.source_cutoff),
                    "created_at": fields.Datetime.to_string(run.create_date),
                    "source_type": run.source_type,
                    "state": run.state,
                    "evaluation_status": run.evaluation_status or False,
                    "review_status": run.review_status,
                }
                for run in runs
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_previous": page > 1,
                "has_next": page < total_pages,
            },
            "warehouse_options": [
                {"id": item.id, "name": item.display_name}
                for item in warehouse_options
            ],
            "warehouse_options_limited": warehouses_limited,
            "warehouse_count": warehouse_count,
            "real_history_access": sales_access,
            "access_note": (
                False if sales_access else _(
                    "Your Odoo role can view synthetic showroom examples, but completed delivery histories require Sales access."
                )
            ),
            "read_only": True,
        }

    @api.model
    def _forecast_estimate_summaries(self, runs):
        """Summarize complete saved daily series without recalculating forecasts."""
        if not runs:
            return {}

        company = self.env.company
        Point = self.env["autostock.forecast.point"].with_company(company).with_context(
            allowed_company_ids=[company.id]
        )
        grouped_points = Point._read_group(
            [
                ("company_id", "=", company.id),
                ("run_id", "in", runs.ids),
            ],
            ["run_id"],
            ["__count", "units:sum", "day:min", "day:max"],
            order="run_id",
        )
        point_stats = {
            run.id: (point_count, units_sum or 0.0, first_day, last_day)
            for run, point_count, units_sum, first_day, last_day in grouped_points
        }
        today = fields.Date.context_today(self)
        summaries = {}

        for run in runs:
            horizon = int(run.horizon_days)
            unit = run.uom_id
            summary = {
                "status": "not_completed" if run.state != "completed" else "incomplete",
                "estimated_units": False,
                "uom": unit.display_name if unit else False,
                "uom_rounding": unit.rounding if unit else False,
                "date_start": False,
                "date_end": False,
                "window_status": False,
            }
            stats = point_stats.get(run.id)
            if run.state == "completed" and stats and unit:
                point_count, units_sum, first_day, last_day = stats
                expected_start = run.history_end_date + timedelta(days=1)
                expected_end = expected_start + timedelta(days=horizon - 1)
                # A run/day uniqueness constraint plus an exact count and these
                # boundaries proves that every expected calendar day exists.
                if (
                    point_count == horizon
                    and first_day == expected_start
                    and last_day == expected_end
                ):
                    summary.update(
                        {
                            "status": "available",
                            "estimated_units": float_round(
                                units_sum, precision_rounding=unit.rounding
                            ),
                            "date_start": first_day.isoformat(),
                            "date_end": last_day.isoformat(),
                            "window_status": (
                                "ended" if last_day < today
                                else "in_progress" if first_day < today
                                else "upcoming"
                            ),
                        }
                    )
            summaries[run.id] = summary
        return summaries

    @api.model
    def get_forecast_part_page(
        self, query="", warehouse_id=False, page=1, page_size=12
    ):
        """Return a server-grouped page of real forecasted product locations.

        Groups are keyed by stable product and warehouse IDs. The most recently
        saved run for each horizon is chosen by create date, with record ID as a
        stable tie-breaker, including pending, failed, or unreviewed runs.
        Synthetic examples remain in exact Saved run history and never merge
        with a real product that happens to share a name or SKU.
        """
        self._require_inventory_access()
        company = self.env.company
        query = (query or "").strip()[:80]

        def positive_page_value(value, label, *, default, maximum=False):
            try:
                parsed = int(value or default)
            except (TypeError, ValueError) as error:
                raise ValidationError(_("Choose a valid %(label)s.", label=label)) from error
            if parsed <= 0 or (maximum and parsed > maximum):
                if maximum:
                    raise ValidationError(
                        _(
                            "Choose a %(label)s between 1 and %(maximum)s.",
                            label=label,
                            maximum=maximum,
                        )
                    )
                raise ValidationError(_("Choose a valid %(label)s.", label=label))
            return parsed

        page = positive_page_value(page, _("page"), default=1)
        page_size = positive_page_value(
            page_size, _("page size"), default=12, maximum=50
        )
        warehouse = (
            self._scoped_warehouse(self._positive_id(warehouse_id, _("warehouse")), company)
            if warehouse_id not in (None, "", False)
            else self.env["stock.warehouse"]
        )
        sales_access = self.env.user.has_group(
            "sales_team.group_sale_salesman"
        ) or self.env.user.has_group("sales_team.group_sale_manager")
        Run = self.with_company(company).with_context(
            allowed_company_ids=[company.id]
        )

        domain = [
            ("company_id", "=", company.id),
            ("source_type", "=", REAL_SOURCE),
            ("product_id", "!=", False),
            ("product_id.company_id", "in", [False, company.id]),
            "|",
            ("warehouse_id", "=", False),
            ("warehouse_id.company_id", "=", company.id),
        ]
        if warehouse:
            domain.append(("warehouse_id", "=", warehouse.id))
        if query:
            domain.extend(
                ["|", ("product_name", "ilike", query), ("sku", "ilike", query)]
            )

        group_rows = []
        if sales_access:
            # `_read_group` applies Odoo record rules and paginates after grouping,
            # so repeated horizons never split a part/warehouse group across pages.
            group_rows = Run._read_group(
                domain,
                ["product_id", "warehouse_id"],
                [],
                offset=(page - 1) * page_size,
                limit=page_size + 1,
                order="product_id, warehouse_id",
            )
        has_next = len(group_rows) > page_size
        page_groups = group_rows[:page_size]
        pair_domains = [
            [
                ("product_id", "=", product.id),
                ("warehouse_id", "=", warehouse_record.id if warehouse_record else False),
            ]
            for product, warehouse_record in page_groups
        ]
        page_buckets = []
        if pair_domains:
            bucket_domain = Domain(domain) & Domain.OR(pair_domains)
            page_buckets = Run._read_group(
                bucket_domain,
                ["product_id", "warehouse_id", "horizon_days"],
                ["__count", "create_date:max"],
                order="product_id, warehouse_id, horizon_days",
            )
        latest_bucket_domains = [
            [
                ("product_id", "=", product.id),
                ("warehouse_id", "=", warehouse_record.id if warehouse_record else False),
                ("horizon_days", "=", horizon),
                ("create_date", "=", latest_created_at),
            ]
            for product, warehouse_record, horizon, _run_count, latest_created_at in page_buckets
        ]
        latest_candidates = Run.search(
            Domain(domain) & Domain.OR(latest_bucket_domains),
            order="create_date desc, id desc",
        ) if latest_bucket_domains else Run.browse()
        latest_by_key = {}
        for latest in latest_candidates:
            key = (
                latest.product_id.id,
                latest.warehouse_id.id if latest.warehouse_id else False,
                int(latest.horizon_days),
            )
            latest_by_key.setdefault(key, latest)
        latest_runs = Run.browse([run.id for run in latest_by_key.values()])
        estimate_by_run_id = self._forecast_estimate_summaries(latest_runs)
        bucket_by_key = {}
        for product, warehouse_record, horizon, run_count, _latest_created_at in page_buckets:
            key = (product.id, warehouse_record.id if warehouse_record else False)
            latest = latest_by_key.get((key[0], key[1], int(horizon)))
            bucket_by_key.setdefault(key, {})[int(horizon)] = {
                "saved_run_count": run_count,
                "latest_run_id": latest.id if latest else False,
            }

        parts = []
        for product, warehouse_record in page_groups:
            key = (product.id, warehouse_record.id if warehouse_record else False)
            horizons = []
            for horizon in sorted(SUPPORTED_HORIZONS):
                bucket = bucket_by_key.get(key, {}).get(horizon)
                latest = latest_by_key.get((key[0], key[1], horizon)) if bucket else False
                latest_data = False
                estimate = {
                    "status": "missing",
                    "estimated_units": False,
                    "uom": False,
                    "uom_rounding": False,
                    "date_start": False,
                    "date_end": False,
                    "window_status": False,
                }
                if latest:
                    estimate = estimate_by_run_id.get(latest.id, estimate)
                    latest_data = {
                        "id": latest.id,
                        "created_at": fields.Datetime.to_string(latest.create_date),
                        "horizon_days": horizon,
                        "source_type": REAL_SOURCE,
                        "state": latest.state,
                        "evaluation_status": latest.evaluation_status or False,
                        "review_status": latest.review_status,
                    }
                horizons.append(
                    {
                        "horizon_days": horizon,
                        "saved_run_count": bucket["saved_run_count"] if bucket else 0,
                        "latest_run": latest_data,
                        "estimate": estimate,
                    }
                )
            parts.append(
                {
                    "product_id": product.id,
                    "product_name": product.with_context(
                        display_default_code=False
                    ).display_name,
                    "sku": product.default_code or str(product.id),
                    "warehouse_id": warehouse_record.id if warehouse_record else False,
                    "warehouse_name": warehouse_record.display_name if warehouse_record else False,
                    "horizons": horizons,
                    "source_type": REAL_SOURCE,
                }
            )
        Warehouse = self.env["stock.warehouse"].with_company(company).with_context(
            allowed_company_ids=[company.id]
        )
        warehouse_count = Warehouse.search_count([("company_id", "=", company.id)])
        warehouse_options = Warehouse.search(
            [("company_id", "=", company.id)], order="name, id", limit=101
        )
        warehouses_limited = len(warehouse_options) > 100
        warehouse_options = warehouse_options[:100]
        return {
            "filters": {
                "query": query,
                "warehouse_id": warehouse.id if warehouse else False,
            },
            "parts": parts,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "has_previous": page > 1,
                "has_next": has_next,
            },
            "warehouse_options": [
                {"id": item.id, "name": item.display_name}
                for item in warehouse_options
            ],
            "warehouse_options_limited": warehouses_limited,
            "warehouse_count": warehouse_count,
            "real_history_access": sales_access,
            "access_note": (
                False if sales_access else _(
                    "Completed delivery forecasts require Sales access. Synthetic examples remain available in Saved run history."
                )
            ),
            "read_only": True,
        }

    @api.model
    def _forecast_estimate_summary(self, run):
        """Return the exact stored-period estimate summary for one saved run."""
        return self._forecast_estimate_summaries(run).get(run.id)

    @api.model
    def _positive_id(self, value, label):
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise ValidationError(_("Choose a valid %(label)s.", label=label)) from error
        if parsed <= 0:
            raise ValidationError(_("Choose a valid %(label)s.", label=label))
        return parsed

    @api.model
    def _validated_date(self, value, label):
        result = fields.Date.to_date(value) if value else False
        if not result:
            raise ValidationError(_("A valid %(label)s date is required.", label=label))
        return result

    @api.model
    def _scoped_product(self, product_id, company):
        Product = (
            self.env["product.product"]
            .with_company(company)
            .with_context(allowed_company_ids=[company.id])
        )
        product = Product.search(
            [
                ("id", "=", int(product_id)),
                ("active", "=", True),
                ("is_storable", "=", True),
                ("autostock_enabled", "=", True),
                ("company_id", "in", [False, company.id]),
            ],
            limit=1,
        )
        if not product:
            raise AccessError(_("That tracked product is not available in the active company."))
        return product

    @api.model
    def _scoped_warehouse(self, warehouse_id, company):
        if not warehouse_id:
            return self.env["stock.warehouse"]
        warehouse = self.env["stock.warehouse"].search(
            [("id", "=", int(warehouse_id)), ("company_id", "=", company.id)],
            limit=1,
        )
        if not warehouse:
            raise AccessError(_("That warehouse is not available in the active company."))
        return warehouse

    @api.model
    def request_forecast(
        self, product_id, horizon_days=30, history_start=None, history_end=None, warehouse_id=False
    ):
        """Queue one real delivered-sales forecast; this RPC never trains a model."""
        self._require_inventory_access()
        self._require_sales_access()
        company = self.env.company
        product = self._scoped_product(product_id, company)
        warehouse = self._scoped_warehouse(warehouse_id, company)
        horizon = self._validated_horizon(horizon_days)
        start = self._validated_date(history_start, _("history start"))
        end = self._validated_date(history_end, _("history end"))
        if start > end:
            raise ValidationError(_("The history start date must be on or before its end date."))
        today_utc = fields.Date.today()
        if end > today_utc:
            raise ValidationError(_("The history end date cannot be in the future."))
        if (end - start).days + 1 > MAX_HISTORY_DAYS:
            raise ValidationError(_("Forecast history is limited to %(days)s days.", days=MAX_HISTORY_DAYS))

        coverage_start = (
            warehouse.autostock_history_complete_from
            if warehouse
            else company.autostock_history_complete_from
        )
        source_cutoff = fields.Datetime.now()
        product_created = fields.Datetime.to_datetime(product.create_date).date()
        demo_profile = self.env["autostock.morocco.history.profile"]
        needs_verified_demo_history = (
            not coverage_start or start < coverage_start or start < product_created
        )
        if needs_verified_demo_history:
            if not warehouse:
                demo_profile = demo_profile.search(
                    [
                        ("company_id", "=", company.id),
                        ("product_id", "=", product.id),
                        ("history_start_date", "=", start),
                        ("history_end_date", "=", end),
                        ("dataset_version", "=", company.autostock_demo_dataset_version),
                        ("state", "=", "verified"),
                    ],
                    limit=2,
                )
            if len(demo_profile) != 1 or not demo_profile._matches_history(
                company, product, start, end
            ):
                if start < product_created:
                    raise UserError(
                        _("The selected history starts before this product existed in Odoo (%(date)s).", date=product_created)
                    )
                if not coverage_start:
                    scope = warehouse.display_name if warehouse else company.display_name
                    raise UserError(
                        _("Set the verified complete sales-history start date for %(scope)s before forecasting.", scope=scope)
                    )
                raise UserError(
                    _("The selected history starts before the configured complete-history date (%(date)s).", date=coverage_start)
                )
            demo_profile = demo_profile[0]

        history_days = (end - start).days + 1
        state = "queued" if history_days >= 90 else "insufficient_history"
        run = super(AutoStockForecastRun, self).create(
            {
                "name": _("%(sku)s · %(days)s days · %(date)s", sku=product.default_code or product.display_name, days=horizon, date=today_utc),
                "company_id": company.id,
                "warehouse_id": warehouse.id if warehouse else False,
                "product_id": product.id,
                "demo_history_profile_id": demo_profile.id if demo_profile else False,
                "demo_dataset_version": demo_profile.dataset_version if demo_profile else False,
                "product_name": product.display_name,
                "sku": product.default_code or str(product.id),
                "uom_id": product.uom_id.id,
                "source_type": REAL_SOURCE,
                "state": state,
                "evaluation_status": "insufficient_history" if state == "insufficient_history" else "pending",
                "horizon_days": str(horizon),
                "history_start_date": start,
                "history_end_date": end,
                "source_cutoff": source_cutoff,
                "source_timezone": "UTC",
                "history_days": history_days,
                "model_version": MODEL_VERSION,
                "model_parameters": json.dumps({"max_source_moves": MAX_SOURCE_MOVES}),
                "data_provenance": REAL_PROVENANCE,
                "assumptions": REAL_ASSUMPTIONS,
                "limitations": REAL_LIMITATIONS,
                "failure_reason": (
                    _("At least 90 complete calendar days are required; no forecast was produced.")
                    if state == "insufficient_history"
                    else False
                ),
            }
        )
        return {"id": run.id, "state": run.state, "source_type": run.source_type}

    @api.model
    def seed_synthetic_demo(
        self,
        sku="DEMO-BP-001",
        horizon_days=30,
        history_start=None,
        history_end=None,
    ):
        """Queue a deterministic demo history without creating Odoo sales or stock moves."""
        self._require_inventory_access()
        if sku not in DEMO_SKUS:
            raise ValidationError(_("Choose one of the provided synthetic demo SKUs."))
        horizon = self._validated_horizon(horizon_days)
        today_utc = fields.Date.today()
        history_end = self._validated_date(history_end or today_utc, _("history end"))
        history_start = self._validated_date(
            history_start or history_end - timedelta(days=209), _("history start")
        )
        if history_start > history_end:
            raise ValidationError(_("The history start date must be on or before its end date."))
        if history_end > today_utc:
            raise ValidationError(_("The history end date cannot be in the future."))
        history_days = (history_end - history_start).days + 1
        if history_days > MAX_HISTORY_DAYS:
            raise ValidationError(_("Forecast history is limited to %(days)s days.", days=MAX_HISTORY_DAYS))
        state = "queued" if history_days >= 90 else "insufficient_history"
        provenance = _(
            "%(dataset)s generated by AutoStock's deterministic synthetic sample builder. "
            "No customer or business transaction data was read or written.",
            dataset=SYNTHETIC_DATASET_VERSION,
        )
        run = super(AutoStockForecastRun, self).create(
            {
                "name": _("Synthetic demo · %(sku)s · %(days)s days · %(date)s", sku=sku, days=horizon, date=today_utc),
                "company_id": self.env.company.id,
                "product_name": _("Synthetic sample %(sku)s", sku=sku),
                "sku": sku,
                "source_type": SYNTHETIC_SOURCE,
                "state": state,
                "evaluation_status": "pending" if state == "queued" else state,
                "horizon_days": str(horizon),
                "history_start_date": history_start,
                "history_end_date": history_end,
                "source_cutoff": fields.Datetime.now(),
                "source_timezone": "UTC",
                "history_days": history_days,
                "model_version": MODEL_VERSION,
                "model_parameters": json.dumps(
                    {"dataset_version": SYNTHETIC_DATASET_VERSION, "max_source_moves": 0}
                ),
                "data_provenance": provenance,
                "assumptions": "Generated daily fulfilled-sales-like values are synthetic and deterministic for this SKU and end date.",
                "limitations": "This demonstration does not model inventory constraints, stockout-censored demand, actual customers, or actual transactions.",
                "failure_reason": (
                    _("At least 90 complete calendar days are required; no forecast was produced.")
                    if state == "insufficient_history"
                    else False
                ),
            }
        )
        return {"id": run.id, "state": run.state, "source_type": run.source_type}

    @api.model
    def get_forecast_options(self):
        self._require_inventory_access()
        company = self.env.company
        Product = (
            self.env["product.product"]
            .with_company(company)
            .with_context(allowed_company_ids=[company.id])
        )
        products = Product.search(
            [
                ("active", "=", True),
                ("is_storable", "=", True),
                ("autostock_enabled", "=", True),
                ("company_id", "in", [False, company.id]),
            ],
            # `display_name` is computed and cannot be used as an SQL order in
            # Odoo 19. `default_code` is stored, so this remains deterministic
            # without bypassing the ORM or record rules.
            order="default_code, id",
            limit=500,
        )
        warehouses = self.env["stock.warehouse"].search(
            [("company_id", "=", company.id)], order="name, id", limit=100
        )
        return {
            "company_id": company.id,
            "company_name": company.display_name,
            "company_logo_url": f"/web/image/res.company/{company.id}/logo_web",
            "today_utc": fields.Date.today().isoformat(),
            "coverage_start": company.autostock_history_complete_from.isoformat()
            if company.autostock_history_complete_from
            else False,
            "products": [
                {
                    "id": product.id,
                    "sku": product.default_code or str(product.id),
                    "name": product.display_name,
                    "uom": product.uom_id.display_name,
                    "created_on": fields.Datetime.to_datetime(product.create_date).date().isoformat(),
                }
                for product in products
            ],
            "warehouses": [
                {
                    "id": warehouse.id,
                    "name": warehouse.display_name,
                    "coverage_start": warehouse.autostock_history_complete_from.isoformat()
                    if warehouse.autostock_history_complete_from
                    else False,
                }
                for warehouse in warehouses
            ],
            "demo_skus": [{"sku": sku, "name": sku.replace("DEMO-", "").replace("-", " ")} for sku in DEMO_SKUS],
            "can_forecast_real": bool(
                self.env.user.has_group("sales_team.group_sale_salesman")
                or self.env.user.has_group("sales_team.group_sale_manager")
            ),
        }

    @api.model
    def get_forecast_snapshot(
        self,
        source_type=REAL_SOURCE,
        product_id=False,
        sku=False,
        horizon_days=30,
        warehouse_id=False,
        chart_start=False,
        chart_end=False,
        history_start=False,
        history_end=False,
        run_id=False,
    ):
        self._require_inventory_access()
        company = self.env.company
        company_run_env = self.with_context(allowed_company_ids=[company.id])
        selected_run = False
        product = self.env["product.product"]
        warehouse = self.env["stock.warehouse"]
        if run_id:
            run_id = self._positive_id(run_id, _("forecast run"))
            selected_run = company_run_env.search(
                [("id", "=", run_id), ("company_id", "=", company.id)], limit=1
            )
            if not selected_run:
                raise AccessError(_("That forecast is not available in the active company."))
            source_type = selected_run.source_type
            horizon = self._validated_horizon(selected_run.horizon_days)
            if source_type == REAL_SOURCE:
                self._require_sales_access()
                Product = self.env["product.product"].with_company(company).with_context(
                    allowed_company_ids=[company.id]
                )
                product = Product.search(
                    [
                        ("id", "=", selected_run.product_id.id),
                        ("company_id", "in", [False, company.id]),
                    ],
                    limit=1,
                )
                if not product:
                    raise AccessError(_("The part for this forecast is no longer available in the active company."))
                warehouse = self._scoped_warehouse(selected_run.warehouse_id.id, company)
            elif selected_run.sku not in DEMO_SKUS:
                raise AccessError(_("This synthetic example is not available."))
        else:
            if source_type not in (REAL_SOURCE, SYNTHETIC_SOURCE):
                raise ValidationError(_("Unknown forecast source."))
            horizon = self._validated_horizon(horizon_days)
            if source_type == REAL_SOURCE:
                self._require_sales_access()
                if not product_id:
                    return {"run": False}
                product = self._scoped_product(product_id, company)
                warehouse = self._scoped_warehouse(warehouse_id, company)
            elif sku not in DEMO_SKUS:
                raise ValidationError(_("Choose one of the provided synthetic demo SKUs."))

        domain = [
            ("company_id", "=", company.id),
            ("source_type", "=", source_type),
            ("horizon_days", "=", str(horizon)),
        ]
        if source_type == REAL_SOURCE:
            domain.append(("product_id", "=", product.id))
            domain.append(("warehouse_id", "=", warehouse.id if warehouse else False))
        else:
            domain.append(("sku", "=", selected_run.sku if selected_run else sku))
            domain.append(("warehouse_id", "=", False))

        history_start = fields.Date.to_date(history_start) if history_start else False
        history_end = fields.Date.to_date(history_end) if history_end else False
        if history_start:
            domain.append(("history_start_date", "=", history_start))
        if history_end:
            domain.append(("history_end_date", "=", history_end))

        run = selected_run or company_run_env.search(
            domain, order="create_date desc, id desc", limit=1
        )
        if not run:
            return {"run": False}

        start = fields.Date.to_date(chart_start) if chart_start else run.history_start_date
        end = fields.Date.to_date(chart_end) if chart_end else run.history_end_date
        if start and end and start > end:
            raise ValidationError(_("The chart start date must be on or before its end date."))
        observations = run.observation_ids
        if start:
            observations = observations.filtered(lambda item: item.day >= start)
        if end:
            observations = observations.filtered(lambda item: item.day <= end)

        current_stock = False
        if source_type == REAL_SOURCE:
            scoped_product = (
                self.env["product.product"]
                .with_company(company)
                .with_context(allowed_company_ids=[company.id])
                .browse(product.id)
            )
            current_stock = {
                "on_hand": scoped_product.qty_available,
                "odoo_projected": scoped_product.virtual_available,
                "uom": scoped_product.uom_id.display_name,
            }

        return {
            "run": {
                "id": run.id,
                "name": run.name,
                "company_id": run.company_id.id,
                "company_name": run.company_id.display_name,
                "product_id": run.product_id.id if run.product_id else False,
                "warehouse_id": run.warehouse_id.id if run.warehouse_id else False,
                "warehouse_name": run.warehouse_id.display_name if run.warehouse_id else False,
                "uom": run.uom_id.display_name if run.uom_id else False,
                "created_at": fields.Datetime.to_string(run.create_date),
                "state": run.state,
                "evaluation_status": run.evaluation_status,
                "failure_reason": run.failure_reason or False,
                "source_type": run.source_type,
                "source_label": _("Synthetic demo")
                if run.source_type == SYNTHETIC_SOURCE
                else _("Completed deliveries, with returns recorded separately"),
                "sku": run.sku,
                "product_name": (
                    product.with_context(display_default_code=False).display_name
                    if source_type == REAL_SOURCE and product
                    else run.product_name or run.sku
                ),
                "horizon_days": int(run.horizon_days),
                "history_start": run.history_start_date.isoformat(),
                "history_end": run.history_end_date.isoformat(),
                "source_cutoff": fields.Datetime.to_string(run.source_cutoff),
                "source_timezone": run.source_timezone,
                "history_days": run.history_days,
                "nonzero_days": run.nonzero_days,
                "source_event_count": run.source_event_count,
                "source_snapshot_sha256": run.source_snapshot_sha256,
                "model_version": run.model_version,
                "selected_method": run.selected_method or False,
                "baseline_method": run.baseline_method or False,
                "demand_pattern": run.demand_pattern or False,
                "evaluation_days": run.evaluation_days,
                "baseline_mae": run.baseline_mae if run.baseline_method else False,
                "ml_mae": run.ml_mae if run.ml_evaluated else False,
                "ml_evaluated": run.ml_evaluated,
                "review_status": run.review_status,
                "reviewed_by": run.reviewed_by_id.display_name if run.reviewed_by_id else False,
                "reviewed_at": fields.Datetime.to_string(run.reviewed_at) if run.reviewed_at else False,
                "data_provenance": run.data_provenance,
                "assumptions": run.assumptions,
                "limitations": run.limitations,
                "interval_note": run.interval_note or False,
                "current_stock": current_stock,
                "observations": [
                    {
                        "day": item.day.isoformat(),
                        "delivered_units": item.delivered_units,
                        "returned_units": item.returned_units,
                        "units": item.units,
                        "source_event_count": item.source_event_count,
                    }
                    for item in observations
                ],
                "predictions": [
                    {
                        "day": point.day.isoformat(),
                        "units": point.units,
                        "lower_heuristic": point.lower_heuristic,
                        "upper_heuristic": point.upper_heuristic,
                    }
                    for point in run.point_ids
                ],
            }
        }

    @api.model
    def get_forecast_detail(self, run_id):
        """Return one exact saved run and the current risk service's eligibility reason."""
        self._require_inventory_access()
        company = self.env.company
        scoped = self.with_company(company).with_context(allowed_company_ids=[company.id])
        run_id = self._positive_id(run_id, _("forecast run"))
        run = scoped.search(
            [("id", "=", run_id), ("company_id", "=", company.id)], limit=1
        )
        if not run:
            raise AccessError(_("That forecast is not available in the active company."))

        snapshot = scoped.get_forecast_snapshot(run_id=run.id)
        run_data = snapshot.get("run")
        if not run_data:
            raise AccessError(_("That forecast is not available in the active company."))

        if run.source_type == SYNTHETIC_SOURCE:
            guidance = {
                "status": "not_applicable",
                "usable": False,
                "reason": _(
                    "This is a synthetic showroom example. It is separate from Odoo deliveries and is never used for real stock or restock guidance."
                ),
            }
            coverage_start = False
            coverage_configured = False
            covered_from_start = False
        else:
            coverage_start = (
                run.warehouse_id.autostock_history_complete_from
                if run.warehouse_id
                else company.autostock_history_complete_from
            )
            coverage_configured = bool(coverage_start)
            covered_from_start = bool(
                coverage_start and run.history_start_date >= coverage_start
            )
            if not run.warehouse_id:
                guidance = {
                    "status": "not_eligible",
                    "usable": False,
                    "reason": _(
                        "This run covers the whole company, while restock guidance checks one warehouse at a time. A warehouse-specific forecast is needed."
                    ),
                }
            elif not coverage_configured:
                guidance = {
                    "status": "not_eligible",
                    "usable": False,
                    "reason": _(
                        "A verified start date for complete delivery history is not currently configured for this warehouse."
                    ),
                }
            elif not covered_from_start:
                guidance = {
                    "status": "not_eligible",
                    "usable": False,
                    "reason": _(
                        "This run starts before the warehouse's currently configured complete-history date."
                    ),
                }
            elif run.state != "completed":
                guidance = {
                    "status": "not_eligible",
                    "usable": False,
                    "reason": run.failure_reason or _(
                        "Only completed forecasts can be considered for current restock guidance."
                    ),
                }
            elif not run.product_id:
                guidance = {
                    "status": "not_eligible",
                    "usable": False,
                    "reason": _(
                        "The forecast no longer has an available Odoo part, so it cannot be matched to current stock."
                    ),
                }
            else:
                risk = self.env["autostock.inventory.risk"].with_company(company).with_context(
                    allowed_company_ids=[company.id]
                ).get_risk_data(
                    warehouse_id=run.warehouse_id.id,
                    product_id=run.product_id.id,
                    offset=0,
                )
                risk_row = next(
                    (
                        row for row in risk.get("rows", [])
                        if row.get("product_id") == run.product_id.id
                        and row.get("warehouse_id") == run.warehouse_id.id
                    ),
                    False,
                )
                if not risk.get("forecast_access_available"):
                    guidance = {
                        "status": "restricted",
                        "usable": False,
                        "reason": risk.get("forecast_access_reason") or _(
                            "Your Odoo role cannot verify whether this forecast is usable for restock guidance."
                        ),
                    }
                elif not risk_row:
                    guidance = {
                        "status": "unavailable",
                        "usable": False,
                        "reason": _(
                            "Current stock guidance could not match this part to the selected warehouse."
                        ),
                    }
                else:
                    selected = risk_row.get("forecast", {})
                    is_selected = selected.get("run_id") == run.id
                    guidance = {
                        "status": "eligible" if is_selected and selected.get("used") else "not_eligible",
                        "usable": bool(is_selected and selected.get("used")),
                        "reason": (
                            selected.get("reason")
                            if is_selected
                            else _(
                                "Current restock guidance selected a different saved forecast for this part and warehouse."
                            ) if selected.get("run_id") else selected.get("reason") or _(
                                "This forecast is not currently used by restock guidance."
                            )
                        ),
                    }

        return {
            "run": run_data,
            "estimate": self._forecast_estimate_summary(run),
            "history_coverage": {
                "configured": coverage_configured,
                "complete_from": coverage_start.isoformat() if coverage_start else False,
                "run_starts_within_coverage": covered_from_start,
            },
            "restock_guidance": guidance,
            "read_only": True,
        }

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_("Use a validated AutoStock forecast request to create a run."))

    def write(self, vals):
        if set(vals) != {"review_status"} or vals.get("review_status") != "reviewed":
            raise AccessError(_("Forecast result metadata is managed by the background worker."))
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise AccessError(_("Inventory manager access is required to review forecasts."))
        if any(run.state != "completed" for run in self):
            raise UserError(_("Only completed forecasts can be marked as reviewed."))
        vals = {
            **vals,
            "reviewed_by_id": self.env.user.id,
            "reviewed_at": fields.Datetime.now(),
        }
        return super().write(vals)

    def action_mark_reviewed(self):
        self.ensure_one()
        return self.write({"review_status": "reviewed"})

    def _write_worker(self, values):
        return super(AutoStockForecastRun, self).write(values)

    @api.model
    def _cron_process_queued_runs(self):
        runs = self.search(
            [("state", "=", "queued")], order="create_date, id", limit=MAX_RUNS_PER_CRON
        )
        for run in runs:
            run._process_queued_run()
        return True

    def _process_queued_run(self):
        self.ensure_one()
        if self.state != "queued":
            return
        self._write_worker({"state": "running", "failure_reason": False})
        try:
            actor = self.created_by_id
            if not actor or not actor.active:
                raise AccessError(_("The requester is no longer an active Odoo user."))
            scoped_run = self.with_user(actor).with_company(self.company_id).with_context(
                allowed_company_ids=[self.company_id.id]
            )
            if not actor.has_group("stock.group_stock_user"):
                raise AccessError(_("The requester no longer has inventory access."))

            if self.source_type == SYNTHETIC_SOURCE:
                snapshot = scoped_run._synthetic_snapshot()
                source_event_count = 0
                provenance = _(
                    "%(dataset)s generated by AutoStock's deterministic synthetic sample builder. "
                    "No customer or business transaction data was read or written.",
                    dataset=SYNTHETIC_DATASET_VERSION,
                )
                assumptions = "Generated daily fulfilled-sales-like values are synthetic and deterministic for this SKU and end date."
                limitations = "This demonstration does not model inventory constraints, stockout-censored demand, actual customers, or actual transactions."
            else:
                scoped_run._require_sales_access()
                snapshot, source_event_count = scoped_run._completed_sales_snapshot()
                provenance = REAL_PROVENANCE
                if self.demo_history_profile_id:
                    provenance = _(
                        "Fictional Moroccan showroom fixture %(version)s. The history uses completed Odoo delivery and linked return moves; Odoo create dates and users remain their actual import values. Source profile digest: %(digest)s. %(standard)s",
                        version=self.demo_dataset_version,
                        digest=self.demo_history_profile_id.source_move_sha256,
                        standard=REAL_PROVENANCE,
                    )
                    limitations = _(
                        "This history is generated fictional showroom activity, not evidence from a real business. It represents completed fulfilled sales, not unconstrained demand; stockouts may censor sales. The source profile is checked against current Odoo moves before processing. %(standard)s",
                        standard=REAL_LIMITATIONS,
                    )
                else:
                    limitations = REAL_LIMITATIONS
                assumptions = REAL_ASSUMPTIONS

            normalized_input = [Observation(row["day"], row["units"]) for row in snapshot]
            digest_payload = [
                [row["day"].isoformat(), row["delivered_units"], row["returned_units"], row["units"]]
                for row in snapshot
            ]
            digest = sha256(
                json.dumps(digest_payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            ).hexdigest()
            self.env["autostock.forecast.observation"].create(
                [
                    {
                        "run_id": self.id,
                        "day": row["day"],
                        "delivered_units": row["delivered_units"],
                        "returned_units": row["returned_units"],
                        "units": row["units"],
                        "source_event_count": row["source_event_count"],
                    }
                    for row in snapshot
                ]
            )
            result = forecast_daily(
                normalized_input, horizon=int(self.horizon_days)
            )
            if result.status == "insufficient_history":
                self._write_worker(
                    {
                        "state": "insufficient_history",
                        "evaluation_status": result.status,
                        "history_days": result.history_days,
                        "nonzero_days": result.nonzero_days,
                        "source_event_count": source_event_count,
                        "source_snapshot_sha256": digest,
                        "data_provenance": provenance,
                        "assumptions": assumptions,
                        "limitations": limitations,
                        "failure_reason": _("At least 90 complete calendar days are required; no forecast was produced."),
                    }
                )
                return
            if result.status == "no_observed_demand":
                self._write_worker(
                    {
                        "state": "no_observed_demand",
                        "evaluation_status": result.status,
                        "history_days": result.history_days,
                        "nonzero_days": 0,
                        "source_event_count": source_event_count,
                        "source_snapshot_sha256": digest,
                        "data_provenance": provenance,
                        "assumptions": assumptions,
                        "limitations": limitations,
                        "interval_note": result.interval_note,
                        "failure_reason": _("No completed demand was observed in this complete history window; no numeric forecast was produced."),
                    }
                )
                return

            product_rounding = self.uom_id.rounding if self.uom_id else 0.01
            point_values = []
            for prediction in result.predictions:
                forecast_units = float_round(prediction.units, precision_rounding=product_rounding)
                lower = float_round(prediction.lower_heuristic, precision_rounding=product_rounding)
                upper = float_round(prediction.upper_heuristic, precision_rounding=product_rounding)
                point_values.append(
                    {
                        "run_id": self.id,
                        "day": fields.Date.to_date(prediction.day),
                        "units": forecast_units,
                        "lower_heuristic": min(lower, forecast_units),
                        "upper_heuristic": max(upper, forecast_units),
                    }
                )
            self.env["autostock.forecast.point"].create(point_values)
            self._write_worker(
                {
                    "state": "completed",
                    "evaluation_status": result.status,
                    "history_days": result.history_days,
                    "nonzero_days": result.nonzero_days,
                    "source_event_count": source_event_count,
                    "source_snapshot_sha256": digest,
                    "model_version": MODEL_VERSION,
                    "model_parameters": json.dumps(
                        {
                            "ml_seed": 42,
                            "ml_trees": 96,
                            "max_depth": 6,
                            "max_source_moves": MAX_SOURCE_MOVES,
                            "max_history_days": MAX_HISTORY_DAYS,
                        },
                        separators=(",", ":"),
                    ),
                    "selected_method": result.selected_method,
                    "baseline_method": result.baseline_method,
                    "demand_pattern": result.demand_pattern,
                    "evaluation_days": result.evaluation_days,
                    "baseline_mae": result.baseline_mae or 0.0,
                    "ml_mae": result.ml_mae or 0.0,
                    "ml_evaluated": result.ml_mae is not None,
                    "data_provenance": provenance,
                    "assumptions": assumptions,
                    "limitations": limitations,
                    "interval_note": result.interval_note,
                    "failure_reason": False,
                }
            )
        except (AccessError, UserError, ValidationError) as error:
            self._write_worker(
                {
                    "state": "failed",
                    "evaluation_status": "unsupported_source",
                    "failure_reason": str(error),
                    "selected_method": False,
                }
            )
        except Exception:
            _logger.exception("AutoStock forecast worker failed for run %s", self.id)
            self._write_worker(
                {
                    "state": "failed",
                    "evaluation_status": "failed",
                    "failure_reason": _("The bounded forecast job failed. No forecast was stored; check the Odoo server log."),
                    "selected_method": False,
                }
            )

    def _synthetic_snapshot(self):
        self.ensure_one()
        observations = generate_synthetic_history(
            self.sku, end_day=self.history_end_date, days=self.history_days
        )
        return [
            {
                "day": item.day,
                "delivered_units": item.units,
                "returned_units": 0.0,
                "units": item.units,
                "source_event_count": 0,
            }
            for item in observations
        ]

    def _completed_sales_snapshot(self):
        self.ensure_one()
        if self.source_type != REAL_SOURCE:
            raise UserError(_("This forecast is not using Odoo sales history."))
        company = self.company_id
        company_coverage = (
            self.warehouse_id.autostock_history_complete_from
            if self.warehouse_id
            else company.autostock_history_complete_from
        )
        profile_verified = False
        if not company_coverage or self.history_start_date < company_coverage:
            if self.demo_history_profile_id:
                self.demo_history_profile_id._verify_for_run(self)
                profile_verified = True
            else:
                raise UserError(_("Verified complete sales-history coverage changed after the forecast was queued."))
        Product = self.env["product.product"].with_company(company).with_context(
            allowed_company_ids=[company.id]
        )
        product = Product.search(
            [
                ("id", "=", self.product_id.id),
                ("active", "=", True),
                ("is_storable", "=", True),
                ("autostock_enabled", "=", True),
                ("company_id", "in", [False, company.id]),
            ],
            limit=1,
        )
        if not product:
            raise AccessError(_("The selected tracked product is no longer available in the active company."))
        product_created = fields.Datetime.to_datetime(product.create_date).date()
        if self.history_start_date < product_created:
            if not self.demo_history_profile_id:
                raise UserError(
                    _("The selected history starts before this product existed in Odoo (%(date)s).", date=product_created)
                )
            if not profile_verified:
                self.demo_history_profile_id._verify_for_run(self)

        summary = self._morocco_source_summary(
            company,
            product,
            self.history_start_date,
            self.history_end_date,
            self.source_cutoff,
            warehouse=self.warehouse_id,
        )
        return summary["snapshot"], summary["source_move_count"]

    @api.model
    def _morocco_source_summary(self, company, product, start, end, cutoff, warehouse=False):
        """Read qualifying Odoo deliveries/linked returns and digest their exact scope."""
        start_utc = datetime.combine(fields.Date.to_date(start), time.min)
        end_date = fields.Date.to_date(end)
        end_exclusive_utc = datetime.combine(end_date + timedelta(days=1), time.min)
        cutoff = fields.Datetime.to_datetime(cutoff)
        warehouse_domain = (
            [("picking_id.picking_type_id.warehouse_id", "=", warehouse.id)]
            if warehouse
            else []
        )
        base_domain = [
            ("state", "=", "done"),
            ("company_id", "=", company.id),
            ("product_id", "=", product.id),
            ("date", ">=", start_utc),
            ("date", "<", end_exclusive_utc),
            ("date", "<=", cutoff),
            *warehouse_domain,
        ]
        Move = self.env["stock.move"].with_company(company).with_context(
            allowed_company_ids=[company.id]
        )
        deliveries = Move.search(
            [
                *base_domain,
                ("sale_line_id.order_id.state", "in", ["sale", "done"]),
                ("location_id.usage", "=", "internal"),
                ("location_dest_id.usage", "=", "customer"),
            ],
            order="date, id",
            limit=MAX_SOURCE_MOVES + 1,
        )
        if len(deliveries) > MAX_SOURCE_MOVES:
            raise UserError(_("This SKU exceeds the bounded 50,000-move history limit; narrow the date range."))
        returned_moves = Move.search(
            [
                ("state", "=", "done"),
                ("company_id", "=", company.id),
                ("product_id", "=", product.id),
                ("date", ">=", start_utc),
                ("date", "<", end_exclusive_utc),
                ("date", "<=", cutoff),
                ("location_id.usage", "=", "customer"),
                ("location_dest_id.usage", "=", "internal"),
                ("origin_returned_move_id", "in", deliveries.ids),
                *warehouse_domain,
            ],
            order="date, id",
            limit=MAX_SOURCE_MOVES + 1,
        )
        if len(deliveries) + len(returned_moves) > MAX_SOURCE_MOVES:
            raise UserError(_("This SKU exceeds the bounded 50,000-move history limit; narrow the date range."))

        daily = defaultdict(lambda: {"delivered": 0.0, "returned": 0.0, "events": 0})
        original_deliveries = {}
        delivery_units = return_units = 0.0
        for move in deliveries:
            day = fields.Datetime.to_datetime(move.date).date()
            units = move.product_uom._compute_quantity(move.quantity, product.uom_id, round=False)
            daily[day]["delivered"] += units
            daily[day]["events"] += 1
            delivery_units += units
            original_deliveries[move.id] = {"units": units, "returned": 0.0}
        for move in returned_moves:
            original = original_deliveries.get(move.origin_returned_move_id.id)
            if not original:
                continue
            units = move.product_uom._compute_quantity(move.quantity, product.uom_id, round=False)
            original["returned"] += units
            if original["returned"] - original["units"] > product.uom_id.rounding / 2:
                raise UserError(_("A completed return exceeds its linked delivery; this SKU's history needs review."))
            day = fields.Datetime.to_datetime(move.date).date()
            daily[day]["returned"] += units
            daily[day]["events"] += 1
            return_units += units

        snapshot = []
        current = fields.Date.to_date(start)
        while current <= end_date:
            totals = daily[current]
            snapshot.append(
                {
                    "day": current,
                    "delivered_units": totals["delivered"],
                    "returned_units": totals["returned"],
                    "units": totals["delivered"],
                    "source_event_count": totals["events"],
                }
            )
            current += timedelta(days=1)

        move_payload = [
            [
                move.id,
                move.company_id.id,
                move.product_id.id,
                fields.Datetime.to_string(move.date),
                move.quantity,
                move.product_uom.id,
                move.sale_line_id.id,
                move.origin_returned_move_id.id,
                move.location_id.id,
                move.location_dest_id.id,
            ]
            for move in (deliveries | returned_moves).sorted(key=lambda row: (row.date, row.id))
        ]
        daily_payload = [
            [
                row["day"].isoformat(),
                row["delivered_units"],
                row["returned_units"],
                row["units"],
                row["source_event_count"],
            ]
            for row in snapshot
        ]
        return {
            "snapshot": snapshot,
            "source_move_count": len(deliveries) + len(returned_moves),
            "delivery_count": len(deliveries),
            "return_count": len(returned_moves),
            "delivery_units": delivery_units,
            "return_units": return_units,
            "move_sha256": sha256(
                json.dumps(move_payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            ).hexdigest(),
            "daily_sha256": sha256(
                json.dumps(daily_payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            ).hexdigest(),
        }


class AutoStockForecastObservation(models.Model):
    _name = "autostock.forecast.observation"
    _description = "AutoStock Forecast Input Snapshot"
    _order = "day, id"

    run_id = fields.Many2one("autostock.forecast.run", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="run_id.company_id", store=True, index=True, readonly=True)
    day = fields.Date(required=True, index=True)
    delivered_units = fields.Float(digits="Product Unit")
    returned_units = fields.Float(digits="Product Unit")
    units = fields.Float(digits="Product Unit")
    source_event_count = fields.Integer()

    _run_day_unique = models.Constraint(
        "unique(run_id, day)", "A run can store only one observation per day."
    )


class AutoStockForecastPoint(models.Model):
    _name = "autostock.forecast.point"
    _description = "AutoStock Forecast Point"
    _order = "day, id"

    run_id = fields.Many2one("autostock.forecast.run", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="run_id.company_id", store=True, index=True, readonly=True)
    day = fields.Date(required=True, index=True)
    units = fields.Float(digits="Product Unit")
    lower_heuristic = fields.Float(digits="Product Unit")
    upper_heuristic = fields.Float(digits="Product Unit")

    _run_day_unique = models.Constraint(
        "unique(run_id, day)", "A run can store only one forecast point per day."
    )
