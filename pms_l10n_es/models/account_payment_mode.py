# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models

from .mossos_payment import MOSSOS_PAYMENT_TYPES


class AccountPaymentMode(models.Model):
    _inherit = "account.payment.mode"

    mossos_payment_type = fields.Selection(
        MOSSOS_PAYMENT_TYPES,
        string="Mossos payment type",
        help="Manual correspondence used for receipts linked to this payment mode.",
    )
