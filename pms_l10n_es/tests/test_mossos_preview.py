from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import TestPms


@tagged("post_install", "-at_install")
class TestMossosPreview(TestPms):
    def setUp(self):
        super().setUp()
        self.pms_property1.write({
            "mossos_enabled": True,
            "mossos_property_code": "08043AAR02",
            "tz": "Europe/Madrid",
        })
        channel = self.env["pms.sale.channel"].create({
            "name": "Direct", "channel_type": "direct",
        })
        room_type = self.env["pms.room.type"].create({
            "name": "Test", "default_code": "MOS", "class_id": self.room_type_class1.id,
        })
        self.env["pms.room"].create({
            "name": "Mossos test room", "room_type_id": room_type.id,
            "pms_property_id": self.pms_property1.id, "capacity": 2,
        })
        self.reservation = self.env["pms.reservation"].create({
            "pms_property_id": self.pms_property1.id,
            "room_type_id": room_type.id,
            "checkin": "2026-01-01", "checkout": "2026-01-03", "adults": 1,
            "sale_channel_origin_id": channel.id, "partner_name": "Preview traveller",
        })
        self.guest = self.reservation.checkin_partner_ids[0]
        self.guest.write({"arrival": "2026-01-01 23:30:00", "state": "done"})
        self.wizard = self.env["pms.mossos.preview"].create({
            "pms_property_id": self.pms_property1.id, "through_date": "2026-01-02",
        })

    def test_arrival_local_day_and_refresh(self):
        self.wizard.through_date = "2026-01-01"
        self.wizard.action_preview()
        self.assertFalse(self.wizard.line_ids)
        self.wizard.through_date = "2026-01-02"
        self.wizard.action_preview()
        self.assertEqual(self.wizard.line_ids.checkin_partner_id, self.guest)
        self.assertEqual(self.wizard.line_ids.arrival_local, "2026-01-02 00:30 CET")
        self.wizard.action_preview()
        self.assertEqual(len(self.wizard.line_ids), 1)
        self.assertFalse(self.wizard.line_ids.selected)
        self.assertFalse(self.reservation.folio_id.move_ids)

    def test_disabled_property(self):
        self.pms_property1.mossos_enabled = False
        with self.assertRaises(ValidationError):
            self.wizard.action_preview()

    def test_minor_errors_and_no_truncation(self):
        self.guest.write({
            "birthdate_date": fields.Date.today() - relativedelta(years=10),
            "firstname": "A" * 31,
        })
        self.wizard.action_preview()
        errors = self.wizard.line_ids.errors
        self.assertIn("relationship code", errors)
        self.assertIn("maximum length", errors)
        self.assertEqual(self.guest.firstname, "A" * 31)

    def test_document_mapping_and_support(self):
        self.guest.write({
            "birthdate_date": "1980-01-01",
            "document_type": self.env.ref("pms_partner_identification.document_type_national_id").id,
            "document_number": "12345678Z",
            "document_country_id": self.env.ref("base.es").id,
            "support_number": "123",
        })
        self.wizard.action_preview()
        self.assertIn("exactly 9", self.wizard.line_ids.errors)
        self.assertIn("second surname", self.wizard.line_ids.errors)

    def test_foreign_national_id_not_silently_spanish(self):
        self.guest.with_context(id_no_validate=True).write({
            "birthdate_date": "1980-01-01",
            "document_type": self.env.ref("pms_partner_identification.document_type_national_id").id,
            "document_country_id": self.env.ref("base.fr").id,
            "document_number": "12345678Z",
        })
        arrival = fields.Datetime.context_timestamp(
            self.guest.with_context(tz="Europe/Madrid"), datetime(2026, 1, 1, 23, 30)
        )
        self.assertTrue(any("foreign national ID" in e for e in self.wizard._guest_errors(self.guest, arrival)))

    def test_regularized_arrival_after_checkout(self):
        france = self.env.ref("base.fr")
        self.guest.write({
            "state": "precheckin", "arrival": False,
            "birthdate_date": "1980-01-01", "gender": "male",
            "nationality_id": france.id, "country_id": france.id,
            "firstname": "Jean", "lastname": "Dupont",
            "street": "Rue de Paris", "city": "Paris", "zip": "75001",
            "document_type": self.env.ref("pms_partner_identification.document_type_passport").id,
            "document_number": "FR1234567", "document_country_id": france.id,
        })
        self.guest.country_id = france
        self.assertEqual(self.guest.state, "precheckin", str([
            field for field in self.guest._checkin_mandatory_fields()
            if not self.guest[field]
        ]))
        regularization = self.env["pms.checkin.regularization"].create({
            "reservation_id": self.reservation.id,
            "checkin_partner_ids": [(6, 0, self.guest.ids)],
            "arrival": "2026-01-01 23:30:00",
            "has_departed": True, "departure": "2026-01-03 08:00:00",
        })
        regularization.action_apply()
        self.wizard.through_date = "2026-02-01"
        self.wizard.action_preview()
        self.assertFalse(self.wizard.line_ids)
        self.wizard.include_previous_arrivals = True
        self.wizard.action_preview()
        self.assertEqual(self.wizard.line_ids.checkin_partner_id, self.guest)
        self.assertEqual(self.wizard.line_ids.arrival_local, "2026-01-02 00:30 CET")
        self.assertEqual(self.guest.state, "done")

    def test_summer_timezone_ignores_user_timezone(self):
        self.guest.arrival = "2026-07-01 22:30:00"
        self.wizard.through_date = "2026-07-02"
        self.wizard.with_context(tz="America/New_York").action_preview()
        self.assertEqual(self.wizard.line_ids.arrival_local, "2026-07-02 00:30 CEST")

    def test_preview_rejects_guest_of_another_property(self):
        other = self.env["pms.mossos.preview"].create({
            "pms_property_id": self.pms_property2.id,
        })
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["pms.mossos.preview.line"].create({
                "wizard_id": other.id, "checkin_partner_id": self.guest.id,
            })

    def test_previous_departed_guest_excluded_by_default(self):
        self.wizard.through_date = "2026-02-01"
        self.wizard.action_preview()
        self.assertFalse(self.wizard.include_previous_arrivals)
        self.assertFalse(self.wizard.line_ids)

    def test_previous_onboard_guest_excluded_by_default(self):
        self.guest.state = "onboard"
        self.wizard.through_date = "2026-02-01"
        self.wizard.action_preview()
        self.assertFalse(self.wizard.line_ids)

    def test_day_interval_includes_start_excludes_next_midnight(self):
        self.guest.arrival = "2026-01-01 23:00:00"
        self.wizard.action_preview()
        self.assertEqual(self.wizard.line_ids.checkin_partner_id, self.guest)
        self.guest.arrival = "2026-01-02 23:00:00"
        self.wizard.action_preview()
        self.assertFalse(self.wizard.line_ids)

    def test_dst_day_uses_next_local_midnight(self):
        self.wizard.through_date = "2026-03-29"
        self.guest.arrival = "2026-03-28 23:00:00"
        self.wizard.action_preview()
        self.assertEqual(self.wizard.line_ids.checkin_partner_id, self.guest)
        self.guest.arrival = "2026-03-29 21:59:59"
        self.wizard.action_preview()
        self.assertEqual(self.wizard.line_ids.checkin_partner_id, self.guest)
        self.guest.arrival = "2026-03-29 22:00:00"
        self.wizard.action_preview()
        self.assertFalse(self.wizard.line_ids)

    def test_preview_resolves_municipality_from_traveller_zip(self):
        self.guest.write({
            "country_id": self.env.ref("base.es").id,
            "state_id": self.env.ref("base.state_es_b").id,
            "zip": "08001",
        })
        self.wizard.action_preview()
        self.assertEqual(self.wizard.line_ids.ine_municipality_code, "080193")
        self.assertNotIn("No ZIP-to-INE", self.wizard.line_ids.errors)
        self.guest.zip = "08000"
        self.wizard.action_preview()
        self.assertFalse(self.wizard.line_ids.ine_municipality_code)
        self.assertIn("No ZIP-to-INE", self.wizard.line_ids.errors)

    def test_preview_shows_payment_fallback_and_missing_configuration(self):
        self.pms_property1.mossos_default_payment_type = "DESTI"
        self.wizard.action_preview()
        self.assertEqual(self.wizard.line_ids.mossos_payment_type, "DESTI")
        self.assertEqual(self.wizard.line_ids.mossos_payment_source, "default")
        self.assertNotIn("Configure a Mossos payment type", self.wizard.line_ids.errors)
        self.pms_property1.mossos_default_payment_type = False
        self.wizard.action_preview()
        self.assertFalse(self.wizard.line_ids.mossos_payment_type)
        self.assertIn("Configure a Mossos payment type", self.wizard.line_ids.errors)
