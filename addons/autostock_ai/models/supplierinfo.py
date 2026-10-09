from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductSupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    autostock_min_order_qty = fields.Float(
        string="AutoStock minimum order quantity",
        digits="Product Unit",
        default=0.0,
        help=(
            "Supplier's contractual minimum order quantity in the vendor unit shown "
            "above. This is separate from the native minimum quantity price break."
        ),
    )

    @api.constrains("autostock_min_order_qty")
    def _check_autostock_min_order_qty(self):
        if any(line.autostock_min_order_qty < 0 for line in self):
            raise ValidationError("Supplier minimum order quantity cannot be negative.")
