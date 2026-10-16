# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class WizardPaymentFolio(models.TransientModel):
    _inherit = "wizard.payment.folio"
    _check_company_auto = True

    company_id = fields.Many2one(related="folio_id.company_id")
    payment_method_id = fields.Many2one(related="payment_method_line_id.payment_method_id")
    payment_mode_id = fields.Many2one(
        "account.payment.mode", string="Payment mode", check_company=True,
        help="Optional mode assigned to the new receipt, including its Mossos mapping.",
    )

    def button_payment(self):
        self.ensure_one()
        mode = self.payment_mode_id
        if not mode:
            return super().button_payment()
        if (
            mode.company_id != self.folio_id.company_id
            or mode.payment_type != "inbound"
            or mode.payment_method_id != self.payment_method_id
            or (mode.bank_account_link == "fixed" and mode.fixed_journal_id != self.journal_id)
            or (mode.bank_account_link == "variable" and mode.variable_journal_ids
                and self.journal_id not in mode.variable_journal_ids)
        ):
            raise ValidationError(_("The payment mode does not match the company, method or journal."))
        # Standard Odoo default, also passed to the delegated account.move.
        return super(WizardPaymentFolio, self.with_context(
            default_payment_mode_id=mode.id
        )).button_payment()
