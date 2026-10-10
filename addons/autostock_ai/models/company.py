from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    autostock_demo_environment = fields.Boolean(
        string="AutoStock demo environment",
        default=False,
        copy=False,
        help=(
            "Show a discreet demo indicator in AutoStock AI. Records in this company may be "
            "fictional and generated; forecast results are workflow examples, not a claim of "
            "real-world accuracy."
        ),
    )
