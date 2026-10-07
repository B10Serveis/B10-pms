##############################################################################
#    License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
#    Copyright (C) 2022 Comunitea Servicios Tecnológicos S.L. All Rights Reserved
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
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    paid_on_reservation = fields.Boolean("Paid on reservation", default=False)
    pms_reservation_id = fields.Many2one("pms.reservation", string="PMS reservation")

    def _export_for_ui(self, order):
        result = super()._export_for_ui(order)
        result.update(
            paid_on_reservation=order.paid_on_reservation,
            pms_reservation_id=order.pms_reservation_id.id,
        )
        return result

    @api.model
    def _order_fields(self, ui_order):
        order_fields = super()._order_fields(ui_order)
        order_fields["paid_on_reservation"] = ui_order.get("paid_on_reservation", False)
        order_fields["pms_reservation_id"] = ui_order.get("pms_reservation_id", False)
        return order_fields

    def _get_fields_for_order_line(self):
        res = super()._get_fields_for_order_line()
        res.append("pms_service_line_id")
        return res

    @api.model
    def _process_order(self, pos_order, draft, existing_order):
        data = pos_order["data"]
        reservation_id = data.get("pms_reservation_id")
        if data.get("paid_on_reservation"):
            session = self.env["pos.session"].browse(data["pos_session_id"]).exists()
            session.check_access_rights("read")
            session.check_access_rule("read")
            config = session.config_id
            if not config.pay_on_reservation or not reservation_id:
                raise UserError(_("Reservation payment is not configured."))
            reservation = self.env["pms.reservation"].sudo().browse(reservation_id).exists()
            if (
                not reservation
                or reservation.company_id != session.company_id
                or reservation.currency_id != session.currency_id
                or reservation.state == "cancel"
                or (
                    config.reservation_allowed_propertie_ids
                    and reservation.pms_property_id
                    not in config.reservation_allowed_propertie_ids
                )
            ):
                raise UserError(_("This reservation is not allowed for this POS."))
            method = config.pay_on_reservation_method_id
            if not method or method.type != "pay_later":
                raise UserError(_(
                    "In POS settings, select a Customer Account payment method "
                    "with Identify Customer enabled and no cash or bank journal for Pay on reservation."
                ))
            if method.company_id != session.company_id:
                raise UserError(_(
                    "The reservation payment method must belong to the POS company."
                ))
            if data.get("to_invoice"):
                raise UserError(_(
                    "Turn off Invoice to charge this ticket to a reservation. "
                    "The reservation will be invoiced from PMS."
                ))
            payments = data.get("statement_ids", [])
            if not draft and (
                not payments
                or any(
                    payment[2].get("payment_method_id") != method.id
                    for payment in payments
                )
                or not session.currency_id.is_zero(
                    sum(payment[2]["amount"] for payment in payments)
                    - data["amount_total"]
                )
            ):
                raise UserError(_("The entire order must be paid on the reservation."))
        elif reservation_id:
            raise UserError(_("A reservation requires reservation payment."))
        result = super()._process_order(pos_order, draft, existing_order)
        if data.get("paid_on_reservation") and not draft:
            self.browse(result).add_order_lines_to_reservation(reservation)
        return result

    def add_order_lines_to_reservation(self, pms_reservation_id):
        self.lines.filtered(lambda x: not x.pms_service_line_id)._generate_pms_service(
            pms_reservation_id
        )


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    pms_service_line_id = fields.Many2one("pms.service.line", string="PMS Service line")

    def _export_for_ui(self, orderline):
        result = super()._export_for_ui(orderline)
        result["pms_service_line_id"] = orderline.pms_service_line_id.id
        result["server_id"] = orderline.id
        return result

    def _generate_pms_service(self, pms_reservation_id):
        for line in self:
            vals = {
                "product_id": line.product_id.id,
                "reservation_id": pms_reservation_id.id,
                "is_board_service": False,
                "tax_ids": [(6, 0, line.tax_ids_after_fiscal_position.ids)],
                "service_line_ids": [
                    (
                        0,
                        False,
                        {
                            "date": datetime.now(),
                            "price_unit": line.price_unit,
                            "discount": line.discount,
                            "day_qty": line.qty,
                        },
                    )
                ],
            }
            service = self.sudo().env["pms.service"].create(vals)

            line.write({"pms_service_line_id": service.service_line_ids.id})
