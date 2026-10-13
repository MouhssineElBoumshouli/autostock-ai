"""Verified provenance for the isolated fictional Moroccan showroom."""

from __future__ import annotations

import os

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


MOROCCO_TARGET_DATABASE = "autostock_atlas_morocco_demo"


class AutoStockMoroccoFixture(models.Model):
    _name = "autostock.morocco.fixture"
    _description = "Moroccan Demo Import Identity"
    _order = "fixture_key, id"

    dataset_version = fields.Char(required=True, readonly=True, index=True)
    fixture_key = fields.Char(required=True, readonly=True, index=True)
    entity = fields.Char(required=True, readonly=True)
    record_model = fields.Char(required=True, readonly=True)
    record_id = fields.Integer(required=True, readonly=True, index=True)
    payload_sha256 = fields.Char(required=True, readonly=True)

    _fixture_key_unique = models.Constraint(
        "unique(fixture_key)", "A Moroccan fixture key can be registered only once."
    )

    @api.constrains("record_model", "record_id", "payload_sha256")
    def _check_fixture_target(self):
        for row in self:
            if row.record_model not in self.env.registry.models or row.record_id <= 0:
                raise ValidationError(_("The fixture registry points to an invalid Odoo record."))
            if len(row.payload_sha256 or "") != 64:
                raise ValidationError(_("Fixture payload digests must be SHA-256 values."))


class AutoStockMoroccoHistoryProfile(models.Model):
    _name = "autostock.morocco.history.profile"
    _description = "Verified Moroccan Demo Sales History"
    _order = "product_id, id"

    name = fields.Char(required=True, readonly=True)
    profile_key = fields.Char(required=True, readonly=True, index=True)
    dataset_version = fields.Char(required=True, readonly=True, index=True)
    company_id = fields.Many2one("res.company", required=True, readonly=True, index=True)
    product_id = fields.Many2one("product.product", required=True, readonly=True, index=True)
    warehouse_id = fields.Many2one("stock.warehouse", index=True, readonly=True, ondelete="restrict")
    history_start_date = fields.Date(required=True, readonly=True)
    history_end_date = fields.Date(required=True, readonly=True)
    calendar_days = fields.Integer(required=True, readonly=True)
    planned_daily_sha256 = fields.Char(required=True, readonly=True)
    source_move_count = fields.Integer(required=True, readonly=True)
    source_delivery_count = fields.Integer(required=True, readonly=True)
    source_return_count = fields.Integer(required=True, readonly=True)
    source_delivery_units = fields.Float(required=True, readonly=True, digits="Product Unit")
    source_return_units = fields.Float(required=True, readonly=True, digits="Product Unit")
    source_move_sha256 = fields.Char(required=True, readonly=True)
    source_daily_sha256 = fields.Char(required=True, readonly=True)
    verified_at = fields.Datetime(required=True, readonly=True)
    state = fields.Selection(
        [("verified", "Verified"), ("invalidated", "Invalidated")],
        required=True,
        readonly=True,
        default="verified",
        index=True,
    )

    _profile_unique = models.Constraint(
        "unique(company_id, dataset_version, profile_key)",
        "A dataset history profile can be recorded only once per company.",
    )

    @api.constrains(
        "company_id", "product_id", "warehouse_id", "history_start_date",
        "history_end_date", "calendar_days", "source_move_sha256", "source_daily_sha256",
    )
    def _check_profile_shape(self):
        for profile in self:
            if profile.product_id.company_id not in (False, profile.company_id):
                raise ValidationError(_("A verified history profile must use a product available to its company."))
            if profile.warehouse_id and profile.warehouse_id.company_id != profile.company_id:
                raise ValidationError(_("A verified history profile must use a warehouse belonging to its company."))
            expected_days = (profile.history_end_date - profile.history_start_date).days + 1
            if profile.calendar_days != expected_days or profile.calendar_days < 90:
                raise ValidationError(_("A verified history profile must cover at least 90 complete days."))
            if len(profile.source_move_sha256 or "") != 64 or len(profile.source_daily_sha256 or "") != 64:
                raise ValidationError(_("Verified history digests must be SHA-256 values."))

    def _target_is_marked(self):
        self.ensure_one()
        company = self.company_id
        target_uuid = os.environ.get("AUTOSTOCK_DEMO_TARGET_UUID", "")
        return bool(
            self.env.cr.dbname == MOROCCO_TARGET_DATABASE
            and target_uuid
            and company.autostock_demo_environment
            and company == self.env.ref("base.main_company")
            and company.autostock_demo_target_uuid == target_uuid
            and company.autostock_demo_dataset_version == self.dataset_version
        )

    def _matches_scope(self, company, product, start, end, warehouse=False):
        """Check the immutable company/product/warehouse/date/dataset binding."""
        self.ensure_one()
        if (
            self.state != "verified"
            or not self._target_is_marked()
            or self.company_id != company
            or self.product_id != product
            or self.warehouse_id != warehouse
            or self.history_start_date != start
            or self.history_end_date != end
        ):
            return False
        return True

    def _matches_history(self, company, product, start, end, warehouse=False):
        """Check exact scope and recompute the source digest using ordinary ORM access."""
        self.ensure_one()
        if not self._matches_scope(company, product, start, end, warehouse=warehouse):
            return False
        summary = self.env["autostock.forecast.run"]._morocco_source_summary(
            company,
            product,
            start,
            end,
            fields.Datetime.now(),
            warehouse=warehouse,
            dataset_version=self.dataset_version,
        )
        return self._summary_matches(summary)

    def _summary_matches(self, summary):
        self.ensure_one()
        return bool(
            summary.get("scope") == {
                "company_id": self.company_id.id,
                "product_id": self.product_id.id,
                "warehouse_id": self.warehouse_id.id if self.warehouse_id else False,
                "dataset_version": self.dataset_version,
                "history_start_date": fields.Date.to_string(self.history_start_date),
                "history_end_date": fields.Date.to_string(self.history_end_date),
            }
            and summary["source_move_count"] == self.source_move_count
            and summary["delivery_count"] == self.source_delivery_count
            and summary["return_count"] == self.source_return_count
            and abs(summary["delivery_units"] - self.source_delivery_units) <= self.product_id.uom_id.rounding / 2
            and abs(summary["return_units"] - self.source_return_units) <= self.product_id.uom_id.rounding / 2
            and summary["move_sha256"] == self.source_move_sha256
            and summary["daily_sha256"] == self.source_daily_sha256
        )

    def _verify_for_run(self, run):
        self.ensure_one()
        if (
            run.demo_history_profile_id != self
            or run.company_id != self.company_id
            or run.product_id != self.product_id
            or run.warehouse_id != self.warehouse_id
            or run.demo_dataset_version != self.dataset_version
            or run.history_start_date != self.history_start_date
            or run.history_end_date != self.history_end_date
            or not self._target_is_marked()
        ):
            raise UserError(_("This demo forecast no longer matches its verified history profile."))
        summary = self.env["autostock.forecast.run"]._morocco_source_summary(
            self.company_id,
            self.product_id,
            self.history_start_date,
            self.history_end_date,
            run.source_cutoff,
            warehouse=self.warehouse_id,
            dataset_version=self.dataset_version,
        )
        if not self._summary_matches(summary):
            raise UserError(
                _("The fictional source history changed after this profile was verified. Re-import a reviewed dataset version before forecasting.")
            )
        return summary

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only an Odoo administrator can register demo history provenance."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only an Odoo administrator can change demo history provenance."))
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only an Odoo administrator can remove demo history provenance."))
        return super().unlink()
