import base64

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from ..models.mossos_format import TRAVELLER_LENGTHS, v24_record
from .common import TestPms


@tagged("post_install", "-at_install")
class TestMossosExport(TestPms):
    def setUp(self):
        super().setUp()
        self.hotel = self.pms_property1
        self.hotel.write({
            "name": "Hostal Àncora", "mossos_enabled": True,
            "mossos_property_code": "08043AAR02", "tz": "Europe/Madrid",
            "mossos_internet": "S", "mossos_default_payment_type": "DESTI",
        })
        room_type = self.env["pms.room.type"].create({
            "name": "Export room", "default_code": "EXP",
            "class_id": self.room_type_class1.id,
        })
        self.env["pms.room"].create({
            "name": "Export 1", "pms_property_id": self.hotel.id,
            "room_type_id": room_type.id, "capacity": 2,
        })
        channel = self.env["pms.sale.channel"].create({"name": "Direct", "channel_type": "direct"})
        self.reservation = self.env["pms.reservation"].create({
            "pms_property_id": self.hotel.id, "room_type_id": room_type.id,
            "checkin": "2026-01-01", "checkout": "2026-01-03", "adults": 1,
            "date_order": "2026-01-01 23:45:00", "departure_hour": "11:00",
            "sale_channel_origin_id": channel.id, "partner_name": "Export traveller",
        })
        self.guest = self.reservation.checkin_partner_ids[0]
        self._fill_guest(self.guest)
        self.wizard = self.env["pms.mossos.preview"].create({
            "pms_property_id": self.hotel.id, "through_date": "2026-01-02",
        })

    def _fill_guest(self, guest, number="FR1234567"):
        france = self.env.ref("base.fr")
        guest.write({
            "firstname": "José", "lastname": "Muñoz", "birthdate_date": "1980-01-01",
            "gender": "male", "nationality_id": france.id,
            "document_type": self.env.ref("pms_partner_identification.document_type_passport").id,
            "document_country_id": france.id, "document_number": number,
            "document_expedition_date": "2015-01-01",
            "street": "Rue École 1", "city": "Paris", "zip": "75001",
            "mobile": "+33123456789", "country_id": france.id,
        })
        guest.country_id = france
        guest.write({"state": "done", "arrival": "2026-01-01 23:30:00"})

    def _generate(self):
        self.wizard.action_preview()
        self.assertFalse(self.wizard.line_ids.errors)
        self.assertTrue(self.wizard.line_ids.selected)
        self.wizard.action_generate()
        return self.wizard.batch_id

    def _records(self, batch):
        payload = base64.b64decode(batch.file_data)
        return payload, [line.split("|") for line in payload.decode("utf-8").split("\r\n")]

    def test_file_structure_utf8_and_local_dates(self):
        batch = self._generate()
        payload, records = self._records(batch)
        self.assertEqual(batch.filename, "08043AAR02.001.txt")
        self.assertEqual([len(row) for row in records], [7, 32])
        self.assertEqual(records[0][0:3], ["1", "08043AAR02", "HOSTAL ÀNCORA"])
        self.assertEqual(records[0][5:], ["1", "V24"])
        line = records[1]
        self.assertEqual(line[0:4], ["2", "", "FR1234567", "P"])
        self.assertEqual(line[5:9], ["MUÑOZ", "", "JOSÉ", "M"])
        self.assertEqual(line[11:17], ["20260102", "0030", "20260103", "1100", "20260102", "C"])
        self.assertEqual(line[18:22], ["1", "1", "S", "DESTI"])
        self.assertEqual(line[27:29], ["", ""])
        self.assertEqual(line[29:], ["PARIS", "FRA", "75001"])
        self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))
        self.assertFalse(payload.endswith(b"\r\n"))
        self.assertNotIn(b"\n", payload.replace(b"\r\n", b""))
        self.assertEqual(batch.state, "generated")
        self.assertFalse(batch.presented_at)
        self.assertFalse(self.reservation.folio_id.move_ids)

    def test_selected_travellers_only_and_header_count(self):
        self.reservation.adults = 2
        other = self.reservation.checkin_partner_ids - self.guest
        self._fill_guest(other, "FR7654321")
        self.wizard.action_preview()
        self.wizard.line_ids.filtered(lambda row: row.checkin_partner_id == other).selected = False
        self.wizard.action_generate()
        _, records = self._records(self.wizard.batch_id)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0][5], "1")
        self.assertEqual(records[1][18], "2")
        self.assertEqual(self.wizard.batch_id.line_ids.checkin_partner_id, self.guest)

    def test_repeat_generation_and_download_reuse_snapshot(self):
        batch = self._generate()
        original = batch.file_data
        self.assertEqual(self.hotel.mossos_next_file_number, 2)
        self.guest.firstname = "Changed after generation"
        self.wizard.action_generate()
        self.assertEqual(self.wizard.batch_id, batch)
        self.assertEqual(batch.file_data, original)
        self.assertEqual(self.hotel.mossos_next_file_number, 2)
        self.assertEqual(batch.action_download()["type"], "ir.actions.act_url")
        self.assertEqual(batch.state, "generated")
        self.assertFalse(batch.presented_at)

    def test_stale_wizard_recovers_same_pending_batch(self):
        batch = self._generate()
        other = self.env["pms.mossos.preview"].create({
            "pms_property_id": self.hotel.id, "through_date": "2026-01-02",
            "line_ids": [(0, 0, {"selected": True, "checkin_partner_id": self.guest.id})],
        })
        other.action_generate()
        self.assertEqual(other.batch_id, batch)
        self.assertEqual(self.hotel.mossos_next_file_number, 2)

    def test_generated_and_presented_stays_excluded(self):
        batch = self._generate()
        self.wizard.action_preview()
        self.assertFalse(self.wizard.line_ids)
        batch.receipt_file = base64.b64encode(b"Test portal receipt")
        batch.action_confirm_presented()
        self.assertEqual(batch.state, "presented")
        self.assertTrue(batch.presented_at)
        self.assertEqual(batch.presented_by, self.env.user)
        self.wizard.action_preview()
        self.assertFalse(self.wizard.line_ids)
        with self.assertRaises(ValidationError):
            batch.action_cancel()

    def test_cancel_pending_keeps_history_and_releases_stay(self):
        batch = self._generate()
        batch.cancellation_reason = "Correct traveller data before submission"
        batch.action_cancel()
        self.assertEqual(len(batch.line_ids), 1)
        self.wizard.action_preview()
        self.assertEqual(self.wizard.line_ids.checkin_partner_id, self.guest)
        self.wizard.action_generate()
        self.assertNotEqual(self.wizard.batch_id, batch)
        self.assertEqual(self.wizard.batch_id.filename, "08043AAR02.002.txt")
        self.wizard.action_preview()
        self.assertFalse(self.wizard.line_ids)

    def test_sequence_wraps_after_999(self):
        self.hotel.mossos_next_file_number = 999
        batch = self._generate()
        self.assertEqual(batch.filename, "08043AAR02.999.txt")
        self.assertEqual(self.hotel.mossos_next_file_number, 1)

    def test_revalidates_data_after_preview_without_consuming_number(self):
        self.wizard.action_preview()
        self.guest.firstname = "A" * 31
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.wizard.action_generate()
        self.assertEqual(self.hotel.mossos_next_file_number, 1)
        self.assertFalse(self.wizard.batch_id)

    def test_empty_selection_and_duplicate_lines_rejected(self):
        with self.assertRaises(ValidationError):
            self.wizard.action_generate()
        self.wizard.action_preview()
        self.env["pms.mossos.preview.line"].create({
            "wizard_id": self.wizard.id, "selected": True,
            "checkin_partner_id": self.guest.id,
        })
        with self.assertRaises(ValidationError):
            self.wizard.action_generate()

    def test_wizard_day_change_requires_matching_actual_arrival(self):
        self.wizard.action_preview()
        self.wizard.through_date = "2026-02-01"
        with self.assertRaises(ValidationError):
            self.wizard.action_generate()
        self.wizard.include_previous_arrivals = True
        self.wizard.action_generate()
        self.assertTrue(self.wizard.batch_id)

    def test_spanish_passport_and_dni_foreign_document_exclusive(self):
        spain = self.env.ref("base.es")
        self.guest.partner_id.id_numbers.filtered(
            lambda document: document.category_id == self.guest.document_type
        ).country_id = spain
        self.guest.document_country_id = spain
        batch = self._generate()
        _, records = self._records(batch)
        self.assertEqual(records[1][1:4], ["FR1234567", "", "P"])

    def test_dni_and_nie_require_support_and_valid_control(self):
        spain = self.env.ref("base.es")
        self.guest.write({
            "document_type": self.env.ref("pms_partner_identification.document_type_national_id").id,
            "document_country_id": spain.id, "document_number": "12345678Z",
            "lastname2": "García", "support_number": "ABC123456",
        })
        self.wizard.action_preview()
        self.assertFalse(self.wizard.line_ids.errors)
        self.guest.with_context(id_no_validate=True).document_number = "12345678A"
        self.wizard.action_preview()
        self.assertIn("check letter", self.wizard.line_ids.errors)
        self.guest.write({
            "document_type": self.env.ref("pms_l10n_es.document_type_spanish_residence").id,
            "document_number": "X1234567L",
        })
        self.wizard.action_preview()
        self.assertFalse(self.wizard.line_ids.errors)
        self.wizard.action_generate()
        _, records = self._records(self.wizard.batch_id)
        self.assertEqual(records[1][1:4], ["", "X1234567L", "N"])
        self.assertEqual(records[1][25], "ABC123456")

    def test_minor_without_document_exports_empty_slots_and_relationship(self):
        self.guest.with_context(skip_set_partner_data=True).write({
            "partner_id": False, "birthdate_date": "2016-01-01",
            "document_type": False, "document_number": False,
            "document_country_id": False, "document_expedition_date": False,
            "support_number": False, "ses_partners_relationship": "HJ",
        })
        self.guest.country_id = self.env.ref("base.fr")
        batch = self._generate()
        _, records = self._records(batch)
        self.assertEqual(records[1][1:5], ["", "", "", ""])
        self.assertEqual(records[1][23], "HJ")

    def test_same_contact_new_stay_requires_new_communication(self):
        batch = self._generate()
        batch.action_confirm_presented()
        values = {
            "pms_property_id": self.hotel.id, "room_type_id": self.reservation.room_type_id.id,
            "checkin": "2026-02-01", "checkout": "2026-02-03", "adults": 1,
            "date_order": "2026-02-01 10:00:00", "departure_hour": "11:00",
            "sale_channel_origin_id": self.reservation.sale_channel_origin_id.id,
            "partner_name": "New stay",
        }
        reservation = self.env["pms.reservation"].create(values)
        guest = reservation.checkin_partner_ids[0]
        self._fill_guest(guest)
        self.assertEqual(guest.partner_id, self.guest.partner_id)
        guest.arrival = "2026-02-01 23:30:00"
        self.wizard.through_date = "2026-02-02"
        self.wizard.action_preview()
        self.assertEqual(self.wizard.line_ids.checkin_partner_id, guest)

    def test_file_and_membership_cannot_be_edited(self):
        batch = self._generate()
        with self.assertRaises(AccessError):
            batch.write({"file_data": base64.b64encode(b"tampered")})
        with self.assertRaises(AccessError):
            batch.write({"state": "presented"})
        with self.assertRaises(AccessError):
            batch.unlink()

    def test_serialization_rejects_separators_controls_and_length_expansion(self):
        values = [""] * 32
        values[5] = "NAME|OTHER"
        with self.assertRaises(ValidationError):
            v24_record(values, TRAVELLER_LENGTHS)
        values[5] = "NAME\nOTHER"
        with self.assertRaises(ValidationError):
            v24_record(values, TRAVELLER_LENGTHS)
        values[5] = "ß" * 16
        with self.assertRaises(ValidationError):
            v24_record(values, TRAVELLER_LENGTHS)
        values[5] = "NAME"
        values[26] = "Carrer Major 1, 2º 1ª"
        self.assertEqual(v24_record(values, TRAVELLER_LENGTHS).split("|")[26], "CARRER MAJOR 1, 2º 1ª")

    def test_file_access_is_limited_to_property(self):
        batch = self._generate()
        user = self.env["res.users"].create({
            "name": "Mossos other property", "login": "mossos_other_property",
            "company_id": self.company1.id, "company_ids": [(6, 0, self.company1.ids)],
            "pms_property_ids": [(6, 0, self.pms_property2.ids)],
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id, self.env.ref("pms.group_pms_user").id])],
        })
        scoped = batch.with_user(user).with_context(allowed_company_ids=self.company1.ids)
        with self.assertRaises(AccessError):
            scoped.read(["file_data"])
        with self.assertRaises(AccessError):
            scoped.action_confirm_presented()

    def test_pms_staff_generates_and_downloads_with_scoped_access(self):
        user = self.env["res.users"].create({
            "name": "Mossos reception", "login": "mossos_reception",
            "company_id": self.company1.id, "company_ids": [(6, 0, self.company1.ids)],
            "pms_property_ids": [(6, 0, self.hotel.ids)],
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id, self.env.ref("pms.group_pms_user").id])],
        })
        model = self.env["pms.mossos.preview"].with_user(user).with_context(
            allowed_company_ids=self.company1.ids
        )
        wizard = model.create({"pms_property_id": self.hotel.id, "through_date": "2026-01-02"})
        wizard.action_preview()
        self.assertTrue(wizard.line_ids.selected)
        wizard.action_generate()
        batch = wizard.batch_id
        self.assertEqual(batch.generated_by, user)
        self.assertTrue(batch.file_data)
        self.assertEqual(batch.action_download()["type"], "ir.actions.act_url")
        with self.assertRaises(AccessError):
            batch.line_ids.write({"record_data": "tampered"})
        with self.assertRaises(AccessError):
            batch.copy()

    def test_generation_cannot_inherit_submitted_state_from_context(self):
        self.wizard.action_preview()
        self.wizard.with_context(
            default_state="presented", default_file_encoding="UTF-16",
            default_presented_at="2026-01-01 00:00:00",
        ).action_generate()
        batch = self.wizard.batch_id
        self.assertEqual(batch.state, "generated")
        self.assertEqual(batch.file_encoding, "UTF-8")
        self.assertFalse(batch.presented_at)
        self.assertFalse(batch.presented_by)
