# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import base64
import re

from odoo import _, fields, models
from odoo.exceptions import AccessError, ValidationError

from ..models.mossos_format import (
    HEADER_LENGTHS, TRAVELLER_LENGTHS, v24_record, valid_spanish_document,
)
from ..models.res_city import municipality_code_for_postals


class MossosExport(models.TransientModel):
    _inherit = "pms.mossos.preview"

    batch_id = fields.Many2one("pms.mossos.batch", readonly=True)

    def _guest_errors(self, guest, arrival):
        errors = super()._guest_errors(guest, arrival)
        kind = guest.document_type.code
        if kind in ("D", "N") and guest.document_number and not valid_spanish_document(guest.document_number, kind):
            errors.append(_("Invalid DNI/NIE check letter."))
        if not guest.arrival or guest.arrival > fields.Datetime.now():
            errors.append(_("Actual arrival is missing or is in the future."))
        try:
            self._v24_traveller_record(guest)
        except ValidationError as error:
            errors.append(str(error))
        return errors

    def _v24_traveller_record(self, guest):
        reservation = guest.reservation_id
        hotel = reservation.pms_property_id
        date = lambda value: value.strftime("%Y%m%d") if value else ""
        local = lambda value: fields.Datetime.context_timestamp(guest.with_context(tz=hotel.tz or "UTC"), value) if value else False
        arrival = local(guest.arrival)
        contract = local(reservation.date_order)
        kind = guest.document_type.code or ""
        spanish = kind == "D" or (kind == "P" and guest.document_country_id.code == "ES")
        number = guest.document_number or ""
        if number and (not kind or not guest.document_country_id):
            raise ValidationError(_("A document number requires its type and issuing country."))
        municipality = province = ""
        if guest.country_id.code == "ES":
            province = guest.state_id.ine_province_code or ""
            municipality, error = municipality_code_for_postals([guest.zip or ""], province)
            if error:
                raise ValidationError(error)
            if not re.fullmatch(r"[0-9]{2}", province):
                raise ValidationError(_("A two-digit postal province code is required."))
        payment = reservation.folio_id._mossos_payment_values()
        if payment["error"]:
            raise ValidationError(payment["error"])
        departure = reservation.departure_hour or ""
        if not re.fullmatch(r"[0-9]{2}:[0-9]{2}", departure):
            raise ValidationError(_("Planned departure time must use HH:MM."))
        values = [
            "2", number if spanish else "", number if not spanish else "", kind,
            date(guest.document_expedition_date), guest.lastname or "", guest.lastname2 or "",
            guest.firstname or "", {"male": "M", "female": "F", "other": "O"}.get(guest.gender, ""),
            date(guest.birthdate_date), guest.nationality_id.code_alpha3 or "",
            date(arrival), arrival.strftime("%H%M") if arrival else "",
            date(reservation.checkout), departure.replace(":", ""), date(contract),
            "C", reservation.name or "", str(reservation.adults + reservation.children),
            "1", hotel.mossos_internet or "", payment["payment_type"],
            (guest.mobile or "").strip() or (guest.phone or "").strip(), guest.ses_partners_relationship or "",
            guest.email or "", guest.support_number or "",
            " ".join(filter(None, [guest.street, guest.street2])), province, municipality,
            guest.city or "", guest.country_id.code_alpha3 or "", guest.zip or "",
        ]
        record = v24_record(values, TRAVELLER_LENGTHS)
        normalized = record.split("|")
        for index in (0, 5, 7, 9, 11, 12, 13, 14, 15, 16, 17, 18, 21, 26, 30, 31):
            if not normalized[index]:
                raise ValidationError(_("Required Mossos field %s is empty.", index + 1))
        if not normalized[22] and not normalized[24]:
            raise ValidationError(_("Telephone or email is required."))
        for index in (10, 30):
            if normalized[index] and not re.fullmatch(r"[A-Z]{3}", normalized[index]):
                raise ValidationError(_("Country codes must use three ISO alpha-3 letters."))
        if kind in ("D", "N") and len(normalized[25]) != 9:
            raise ValidationError(_("DNI/NIE support number requires exactly 9 characters."))
        return record

    def _batch_action(self, batch):
        return {
            "type": "ir.actions.act_window", "res_model": "pms.mossos.batch",
            "res_id": batch.id, "view_mode": "form", "target": "current",
        }

    def action_generate(self):
        self.ensure_one()
        if not self.env.user.has_group("pms.group_pms_user"):
            raise AccessError(_("Only PMS staff can generate Mossos files."))
        hotel = self.pms_property_id
        hotel.check_access_rights("read")
        hotel.check_access_rule("read")
        # Serialize numbering and stay reservations for this establishment.
        self.env.cr.execute("SELECT id FROM pms_property WHERE id=%s FOR UPDATE", (hotel.id,))
        self.invalidate_recordset(["batch_id"])
        if self.batch_id and self.batch_id.state != "cancelled":
            return self._batch_action(self.batch_id)
        selected = self.line_ids.filtered("selected")
        guests = selected.checkin_partner_id.exists().sorted("id")
        if not guests or len(guests) != len(selected):
            raise ValidationError(_("Select at least one traveller, without duplicate traveller lines."))
        guests.check_access_rights("read")
        guests.check_access_rule("read")
        self.env.cr.execute("SELECT id FROM pms_checkin_partner WHERE id IN %s ORDER BY id FOR UPDATE", (tuple(guests.ids),))
        guests.invalidate_recordset()
        if not hotel.mossos_enabled or any(guest.pms_property_id != hotel for guest in guests):
            raise ValidationError(_("Select travellers belonging to the enabled Mossos establishment."))
        existing = self.env["pms.mossos.batch.line"].search([
            ("checkin_partner_id", "in", guests.ids),
            ("batch_id.state", "in", ["generated", "presented"]),
        ]).batch_id
        if len(existing) == 1 and existing.state == "generated" and set(existing.line_ids.checkin_partner_id.ids) == set(guests.ids):
            self.batch_id = existing
            return self._batch_action(existing)
        if existing:
            raise ValidationError(_("Some travellers already belong to a generated or submitted file. Open the existing file instead."))
        if len(guests) > 99999:
            raise ValidationError(_("A Mossos file cannot contain more than 99999 travellers."))
        now = fields.Datetime.now()
        local_now = fields.Datetime.context_timestamp(self.with_context(tz=hotel.tz or "UTC"), now)
        if not hotel.tz or not re.fullmatch(r"[A-Z0-9]{9,10}", hotel.mossos_property_code or ""):
            raise ValidationError(_("Configure the establishment timezone and its 9/10-character Mossos identifier."))
        snapshots = []
        for guest in guests:
            if guest.state not in ("onboard", "done") or not guest.arrival:
                raise ValidationError(_("Only travellers with an actual check-in can be exported."))
            arrival = fields.Datetime.context_timestamp(guest.with_context(tz=hotel.tz), guest.arrival)
            if arrival.date() > self.through_date or (not self.include_previous_arrivals and arrival.date() != self.through_date):
                raise ValidationError(_("Refresh the list: a selected traveller no longer matches the arrival day."))
            errors = self._guest_errors(guest, arrival)
            if errors:
                raise ValidationError("%s:\n%s" % (guest.display_name, "\n".join(errors)))
            snapshots.append((0, 0, {
                "checkin_partner_id": guest.id, "firstname": guest.firstname,
                "lastname": guest.lastname, "document_number": guest.document_number,
                "record_data": self._v24_traveller_record(guest),
            }))
        header = v24_record([
            "1", hotel.mossos_property_code, hotel.name, local_now.strftime("%Y%m%d"),
            local_now.strftime("%H%M"), str(len(snapshots)), "V24",
        ], HEADER_LENGTHS)
        payload = "\r\n".join([header] + [line[2]["record_data"] for line in snapshots]).encode("utf-8")
        hotel.invalidate_recordset(["mossos_next_file_number"])
        number = hotel.mossos_next_file_number
        if not 1 <= number <= 999:
            raise ValidationError(_("The next Mossos file number must be between 1 and 999."))
        batch = self.env["pms.mossos.batch"].sudo().create({
            "pms_property_id": hotel.id, "company_id": hotel.company_id.id,
            "filename": "%s.%03d.txt" % (hotel.mossos_property_code, number),
            "file_data": base64.b64encode(payload), "file_number": number,
            "generated_at": now, "generated_by": self.env.user.id,
            "arrival_day": self.through_date, "traveller_count": len(guests),
            "state": "generated", "file_encoding": "UTF-8",
            "presented_at": False, "presented_by": False,
            "receipt_file": False, "receipt_filename": False,
            "cancellation_reason": False, "line_ids": snapshots,
        })
        # Only the technical counter is elevated; traveller access was checked above.
        hotel.sudo().write({"mossos_next_file_number": 1 if number == 999 else number + 1})
        self.batch_id = batch
        return self._batch_action(batch)
