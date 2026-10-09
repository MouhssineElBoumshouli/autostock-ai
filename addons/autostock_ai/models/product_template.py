from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    autostock_enabled = fields.Boolean(
        string="Track in AutoStock AI",
        help="Include this product in the AutoStock dashboard.",
        default=False,
    )
    autostock_oem_reference = fields.Char(
        string="OEM / Manufacturer Reference",
        help="Reference from a verified parts catalogue. Not proof of vehicle fitment.",
    )
    autostock_priority = fields.Selection(
        [("standard", "Standard"), ("critical", "Critical")],
        string="Inventory Priority",
        default="standard",
        required=True,
    )
    autostock_safety_stock = fields.Float(
        string="Safety Stock (units)",
        default=0.0,
        help="A manually approved threshold; not an AI recommendation.",
    )
    autostock_lead_time_days = fields.Integer(
        string="Planning Lead Time (days)",
        default=7,
        help="Planning assumption. Actual supplier lead times remain in Odoo purchasing.",
    )

    @api.constrains("autostock_safety_stock", "autostock_lead_time_days")
    def _check_autostock_inputs(self):
        for product in self:
            if product.autostock_safety_stock < 0:
                raise ValidationError("Safety stock cannot be negative.")
            if product.autostock_lead_time_days < 0:
                raise ValidationError("Planning lead time cannot be negative.")
