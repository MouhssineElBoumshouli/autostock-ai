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
    autostock_demo_target_uuid = fields.Char(
        string="AutoStock demo target marker",
        copy=False,
        readonly=True,
        help="Binds imported demo history to its isolated local database target.",
    )
    autostock_demo_dataset_version = fields.Char(
        string="AutoStock demo dataset version",
        copy=False,
        readonly=True,
    )
