# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from datetime import datetime, time, timedelta
import re

import pytz

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..models.res_city import municipality_code_for_postals
from ..models.mossos_payment import MOSSOS_PAYMENT_TYPES, MOSSOS_PAYMENT_SOURCES


class MossosPreview(models.TransientModel):
    _name = "pms.mossos.preview"
    _description = "Mossos pending arrivals preview"

    pms_property_id = fields.Many2one("pms.property", required=True)
    through_date = fields.Date(
        string="Arrival day", required=True, default=fields.Date.context_today
    )
    include_previous_arrivals = fields.Boolean(
        string="Review earlier arrivals too",
        default=False,
        help="For reviewing late regularizations. Until communication history is "
        "available, this also includes arrivals already submitted outside B10 PMS.",
    )
    line_ids = fields.One2many("pms.mossos.preview.line", "wizard_id")
    configuration_errors = fields.Text(readonly=True)

    def action_preview(self):
        self.ensure_one()
        if not self.env.user.has_group("pms.group_pms_user"):
            raise ValidationError(_("Only PMS staff can preview Mossos arrivals."))
        hotel = self.pms_property_id
        hotel.check_access_rights("read")
        hotel.check_access_rule("read")
        if not hotel.mossos_enabled:
            raise ValidationError(_("Enable Mossos for this establishment first."))
        issues = []
        if not re.fullmatch(r"[A-Z0-9]{9,10}", hotel.mossos_property_code or ""):
            issues.append(_("Establishment identifier must contain 9 or 10 uppercase letters/digits."))
        if len(hotel.name.upper()) > 40:
            issues.append(_("Establishment name exceeds 40 characters."))
        if not hotel.tz:
            issues.append(_("Set the establishment timezone."))
        self.configuration_errors = "\n".join(issues)
        # Boundaries are local midnights converted separately to UTC: a day
        # can contain 23 or 25 hours when the establishment changes DST.
        timezone = pytz.timezone(hotel.tz or "UTC")
        day_start = timezone.localize(datetime.combine(self.through_date, time.min))
        day_end = timezone.localize(datetime.combine(
            self.through_date + timedelta(days=1), time.min
        ))
        domain = [
            ("pms_property_id", "=", hotel.id),
            ("state", "in", ["onboard", "done"]),
            ("arrival", "!=", False),
            ("arrival", "<", day_end.astimezone(pytz.utc).replace(tzinfo=None)),
        ]
        if not self.include_previous_arrivals:
            domain.append((
                "arrival", ">=", day_start.astimezone(pytz.utc).replace(tzinfo=None)
            ))
        guests = self.env["pms.checkin.partner"].search(domain, order="arrival, id")
        values = []
        for guest in guests:
            arrival = fields.Datetime.context_timestamp(
                guest.with_context(tz=hotel.tz or "UTC"), guest.arrival
            )
            errors = self._guest_errors(guest, arrival)
            payment = guest.reservation_id.folio_id._mossos_payment_values()
            municipality_code = False
            if guest.country_id.code == "ES":
                municipality_code, _error = municipality_code_for_postals(
                    [guest.zip or ""], guest.state_id.ine_province_code
                )
            values.append((0, 0, {
                "checkin_partner_id": guest.id,
                "arrival_local": arrival.strftime("%Y-%m-%d %H:%M %Z"),
                "ine_municipality_code": municipality_code,
                "mossos_payment_type": payment["payment_type"],
                "mossos_payment_source": payment["source"],
                "mossos_payment_reference": payment["reference"],
                "errors": "\n".join(errors),
                "selected": not errors and not issues,
            }))
        self.line_ids = [(5, 0, 0)] + values
        return {
            "type": "ir.actions.act_window", "res_model": self._name,
            "res_id": self.id, "view_mode": "form", "target": "new",
        }

    def _guest_errors(self, guest, arrival):
        """Read traveller data only; never use the invoice holder as fallback."""
        reservation = guest.reservation_id
        today = fields.Date.context_today(guest.with_context(tz=guest.pms_property_id.tz))
        errors = []
        def issue(message):
            errors.append(message)

        for field, limit in [
            ("firstname", 30), ("lastname", 30), ("lastname2", 30),
            ("document_number", 14), ("email", 100), ("zip", 20), ("city", 100),
        ]:
            value = guest[field] or ""
            if len(value.upper()) > limit:
                issue(_("%s exceeds the maximum length.", guest._fields[field].string))
            if any(c in value for c in "|\r\n"):
                issue(_("%s contains a record separator.", guest._fields[field].string))
        for field in ["firstname", "lastname", "birthdate_date", "country_id", "zip"]:
            if not guest[field]:
                issue(_("Missing: %s", guest._fields[field].string))
        birthdate = guest.birthdate_date
        if birthdate and birthdate > today:
            issue(_("Birthdate is in the future."))
        if birthdate and birthdate > today - relativedelta(years=18) and not guest.ses_partners_relationship:
            issue(_("A minor requires a relationship code."))
        code = guest.document_type.code
        if code and code not in ["D", "N", "P", "O"]:
            issue(_("Document type has no explicit Mossos mapping."))
        if birthdate and birthdate < today - relativedelta(years=14):
            if not code or not guest.document_number or not guest.document_country_id:
                issue(_("Traveller over 14 requires document type, number and issuing country."))
        if guest.document_number:
            number = guest.document_number.upper()
            if "%" in number:
                issue(_("Document number cannot contain %."))
            if code == "D" and guest.document_country_id.code != "ES":
                issue(_("A foreign national ID cannot be mapped to Spanish DNI without an explicit mapping."))
            if code == "D" and not re.fullmatch(r"\d{8}[A-Z]", number):
                issue(_("Invalid DNI format."))
            if code == "N" and not re.fullmatch(r"[XYZ]\d{7}[A-Z]", number):
                issue(_("Invalid NIE format."))
            if code == "D" or (code == "P" and guest.document_country_id.code == "ES"):
                if len(number) > 11:
                    issue(_("Spanish document exceeds 11 characters."))
        if code == "D" and birthdate and birthdate < today - relativedelta(years=14) and not guest.lastname2:
            issue(_("DNI requires a second surname."))
        if code in ["D", "N"] and len(guest.support_number or "") != 9:
            issue(_("DNI/NIE support number requires exactly 9 characters."))
        if guest.document_expedition_date and guest.document_expedition_date > today:
            issue(_("Document issue date is in the future."))
        phone = guest.mobile or guest.phone or ""
        if len(phone) > 20 or any(c in phone for c in "|\r\n"):
            issue(_("Invalid telephone length or separator."))
        if not phone and not guest.email:
            issue(_("Telephone or email is required."))
        if guest.email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", guest.email):
            issue(_("Invalid email address."))
        address = " ".join(filter(None, [guest.street, guest.street2]))
        if not address or len(address.upper()) > 100 or any(c in address for c in "|\r\n"):
            issue(_("Postal address is missing, too long or contains a separator."))
        if guest.country_id.code == "ES":
            if not re.fullmatch(r"\d{5}", guest.zip or ""):
                issue(_("Spanish postal code requires five digits."))
            if not guest.state_id:
                issue(_("Missing postal province."))
            elif not guest.state_id.ine_province_code:
                issue(_(
                    "Postal province INE code pending: %s",
                    guest.state_id.ine_province_error or _("No verified province prefix."),
                ))
            _code, municipality_error = municipality_code_for_postals(
                [guest.zip or ""], guest.state_id.ine_province_code
            )
            if municipality_error:
                issue(municipality_error)
        elif not guest.city:
            issue(_("Foreign postal address requires a locality."))
        if not guest.country_id.code_alpha3:
            issue(_("Postal country requires an ISO alpha-3 code."))
        if not reservation.checkout or not reservation.departure_hour:
            issue(_("Missing planned departure."))
        else:
            departure = datetime.strptime(
                "%s %s" % (reservation.checkout, reservation.departure_hour), "%Y-%m-%d %H:%M"
            )
            if departure < arrival.replace(tzinfo=None):
                issue(_("Planned departure precedes actual arrival."))
        if not reservation.date_order:
            issue(_("Missing contract date."))
        elif fields.Datetime.context_timestamp(
            reservation.with_context(tz=guest.pms_property_id.tz), reservation.date_order
        ).date() > today:
            issue(_("Contract date is in the future."))
        if len(reservation.name or "") > 20:
            issue(_("Contract number exceeds 20 characters."))
        count = reservation.adults + reservation.children
        if not 1 <= count <= 999 or count != len(reservation.checkin_partner_ids.filtered(lambda g: g.state != "cancel")):
            issue(_("Traveller count differs from the reservation or is outside 1–999."))
        payment = reservation.folio_id._mossos_payment_values()
        if payment["error"]:
            issue(payment["error"])
        return errors


class MossosPreviewLine(models.TransientModel):
    _name = "pms.mossos.preview.line"
    _description = "Mossos traveller preview line"

    wizard_id = fields.Many2one("pms.mossos.preview", required=True, ondelete="cascade")
    selected = fields.Boolean()
    checkin_partner_id = fields.Many2one("pms.checkin.partner", required=True, readonly=True)
    reservation_id = fields.Many2one(related="checkin_partner_id.reservation_id", compute_sudo=False)
    firstname = fields.Char(related="checkin_partner_id.firstname", compute_sudo=False)
    lastname = fields.Char(related="checkin_partner_id.lastname", compute_sudo=False)
    document_number = fields.Char(related="checkin_partner_id.document_number", compute_sudo=False)
    arrival_local = fields.Char(readonly=True)
    ine_municipality_code = fields.Char(string="INE municipality code", readonly=True)
    mossos_payment_type = fields.Selection(MOSSOS_PAYMENT_TYPES, readonly=True)
    mossos_payment_source = fields.Selection(MOSSOS_PAYMENT_SOURCES, readonly=True)
    mossos_payment_reference = fields.Char(string="Selected receipt", readonly=True)
    errors = fields.Text(readonly=True)

    @api.constrains("checkin_partner_id", "wizard_id")
    def _check_guest_access(self):
        for line in self:
            guest = line.checkin_partner_id
            guest.check_access_rights("read")
            guest.check_access_rule("read")
            if guest.pms_property_id != line.wizard_id.pms_property_id:
                raise ValidationError(_("The traveller must belong to the selected establishment."))
