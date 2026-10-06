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
from odoo import _, api, models
from odoo.exceptions import ValidationError


class PosPayment(models.Model):
    _inherit = "pos.payment"

    @api.constrains("payment_method_id", "pos_order_id")
    def _check_payment_method_id(self):
        for payment in self:
            if (
                payment.session_id.config_id.pay_on_reservation
                and payment.session_id.config_id.pay_on_reservation_method_id
                == payment.payment_method_id
            ):
                if not payment.pos_order_id.paid_on_reservation:
                    raise ValidationError(_("This payment method requires a reservation charge."))
                continue
            else:
                super(PosPayment, payment)._check_payment_method_id()
        return
