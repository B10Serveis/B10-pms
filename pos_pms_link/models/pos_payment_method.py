# Copyright 2026 Batista10
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    @api.model
    def _create_default_hotel_payment_methods(self):
        """Provision one usable hotel charge method per existing company.

        Called by module data on installation and upgrade. Never change an
        existing payment method, which may already be in use by a session.
        POS assignment remains an explicit configuration choice.
        """
        methods = self.sudo().with_context(lang=None, active_test=False)
        for company in self.env["res.company"].sudo().search([]):
            existing = methods.search([
                ("company_id", "=", company.id),
                ("name", "=", "Càrrec Hotel"),
                ("split_transactions", "=", True),
                ("journal_id", "=", False),
                ("active", "=", True),
            ], limit=1)
            if not existing:
                methods.create({
                    "name": "Càrrec Hotel",
                    "company_id": company.id,
                    "split_transactions": True,
                    "journal_id": False,
                })
