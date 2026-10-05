from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import format_datetime


class PmsCheckinRegularization(models.TransientModel):
    _name = "pms.checkin.regularization"
    _description = "Regularize arrival and departure"

    reservation_id = fields.Many2one("pms.reservation", required=True)
    checkin_partner_ids = fields.Many2many(
        "pms.checkin.partner", string="Guests", required=True
    )
    arrival = fields.Datetime(string="Actual arrival", required=True)
    has_departed = fields.Boolean(string="The guests have already left")
    departure = fields.Datetime(string="Actual departure")
    outside_reservation = fields.Boolean(compute="_compute_outside_reservation")

    @api.depends("arrival", "departure", "has_departed", "reservation_id")
    def _compute_outside_reservation(self):
        for wizard in self:
            dates = [date for date in (
                wizard.arrival,
                wizard.departure if wizard.has_departed else False,
            ) if date]
            reservation = wizard.reservation_id
            wizard.outside_reservation = bool(
                reservation.checkin and reservation.checkout and any(
                    not reservation.checkin <= fields.Datetime.context_timestamp(
                        wizard, date
                    ).date() <= reservation.checkout for date in dates
                )
            )

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("pms.group_pms_user"):
            raise ValidationError(_("Only PMS staff can regularize arrivals."))
        reservation = self.reservation_id
        guests = self.checkin_partner_ids.exists()
        if reservation.state not in (
            "draft", "confirm", "arrival_delayed", "onboard", "departure_delayed",
        ) or reservation.reservation_type == "out":
            raise ValidationError(_("This reservation cannot be regularized."))
        if not guests or any(
            guest.reservation_id != reservation or guest.state != "precheckin"
            for guest in guests
        ):
            raise ValidationError(_("Select guests pending arrival from this reservation."))
        now = fields.Datetime.now()
        if not self.arrival or self.arrival > now:
            raise ValidationError(_("Actual arrival must not be in the future."))
        if self.has_departed and (
            not self.departure or self.departure < self.arrival or self.departure > now
        ):
            raise ValidationError(_("Departure must be between arrival and the present."))
        for guest in guests:
            if any(
                not getattr(guest, field)
                for field in guest._checkin_mandatory_fields()
            ):
                raise ValidationError(_("Personal data is missing for check-in"))
        for guest in guests:
            guest.write({
                "arrival": self.arrival,
                "departure": self.departure if self.has_departed else False,
                "state": "done" if self.has_departed else "onboard",
                "identifier": reservation.pms_property_id.checkin_sequence_id._next_do(),
            })
        all_guests = reservation.checkin_partner_ids.filtered(
            lambda guest: guest.state != "cancel"
        )
        if any(guest.state == "onboard" for guest in all_guests):
            reservation.state = (
                "departure_delayed" if reservation.checkout < fields.Date.today()
                else "onboard"
            )
        elif all_guests and all(guest.state == "done" for guest in all_guests):
            reservation.state = "done"
        elif reservation.checkin < fields.Date.today():
            reservation.state = "arrival_delayed"
        reservation.message_post(body=_(
            "Arrival/departure regularized by %(user)s. Guests: %(guests)s. "
            "Actual arrival: %(arrival)s. Actual departure: %(departure)s.",
            user=self.env.user.display_name,
            guests=", ".join(
                name for _, name in guests.with_context(show_guest_name=True).name_get()
            ),
            arrival=format_datetime(self.env, self.arrival),
            departure=format_datetime(self.env, self.departure) if self.has_departed
            else _("Still staying"),
        ))
        return {"type": "ir.actions.act_window_close"}
