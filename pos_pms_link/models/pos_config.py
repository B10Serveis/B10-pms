##############################################################################
#    License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
#    Copyright (C) 2023 Comunitea Servicios Tecnológicos S.L. All Rights Reserved
#    Vicente Ángel Gutiérrez <vicente@comunitea.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = "pos.config"

    pay_on_reservation = fields.Boolean("Pay on reservation", default=False)
    pay_on_reservation_method_id = fields.Many2one(
        "pos.payment.method", string="Pay on reservation method"
    )
    reservation_allowed_propertie_ids = fields.Many2many(
        "pms.property", string="Reservation allowed properties"
    )
    close_session_allowed = fields.Boolean("Close session allowed", default=False)

    cash_in_out_allowed = fields.Boolean("Cash in/out allowed", default=False)

    cash_move_partner = fields.Boolean("Use partner in cash moves", default=False)

    @api.constrains(
        "pay_on_reservation", "pay_on_reservation_method_id", "company_id",
        "reservation_allowed_propertie_ids",
    )
    def _check_reservation_configuration(self):
        for config in self:
            method = config.pay_on_reservation_method_id
            # Odoo validates every constraint when opening the POS. A legacy
            # or incomplete reservation payment setup must not block cash sales.
            # The deferred method requirement is checked when charging a stay.
            if method and method.company_id != config.company_id:
                raise ValidationError(_(
                    "The reservation payment method must belong to the POS company."
                ))
            if any(
                prop.company_id != config.company_id
                for prop in config.reservation_allowed_propertie_ids
            ):
                raise ValidationError(_(
                    "Allowed properties must belong to the POS company."
                ))
