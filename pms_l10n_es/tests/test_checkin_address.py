from odoo.tests import Form, tagged

from .common import TestPms


@tagged("post_install", "-at_install")
class TestCheckinAddress(TestPms):
    def setUp(self):
        super().setUp()
        self.spain = self.env.ref("base.es")
        self.province = self.env["res.country.state"].create({
            "name": "Address test Barcelona", "code": "ADDR08",
            "country_id": self.spain.id,
        })
        city = self.env["res.city"].create({
            "name": "Barcelona", "state_id": self.province.id,
            "country_id": self.spain.id,
        })
        self.location = self.env["res.city.zip"].create({
            "name": "08001", "city_id": city.id,
        })
        channel = self.env["pms.sale.channel"].create({
            "name": "Direct", "channel_type": "direct",
        })
        room_type = self.env["pms.room.type"].create({
            "name": "Address room", "default_code": "ADDR",
            "class_id": self.room_type_class1.id,
        })
        self.env["pms.room"].create({
            "name": "Address room", "room_type_id": room_type.id,
            "pms_property_id": self.pms_property1.id, "capacity": 2,
        })
        self.reservation = self.env["pms.reservation"].create({
            "pms_property_id": self.pms_property1.id, "room_type_id": room_type.id,
            "checkin": "2026-01-01", "checkout": "2026-01-03", "adults": 2,
            "sale_channel_origin_id": channel.id, "partner_name": "Address test",
        })
        self.guest, self.other_guest = self.reservation.checkin_partner_ids

    def _assert_location(self, guest):
        self.assertEqual(guest.zip_id, self.location)
        self.assertEqual(guest.zip, "08001")
        self.assertEqual(guest.city, "Barcelona")
        self.assertEqual(guest.state_id, self.province)
        self.assertEqual(guest.country_id, self.spain)

    def test_form_completes_all_residence_fields(self):
        with Form(self.guest) as form:
            form.zip_id = self.location
            self.assertEqual(form.city, "Barcelona")
            self.assertEqual(form.zip, "08001")
            self.assertEqual(form.state_id, self.province)
            self.assertEqual(form.country_id, self.spain)
        self._assert_location(self.guest)

    def test_orm_selection_replaces_inconsistent_values(self):
        self.guest.write({
            "zip_id": self.location.id, "city": "Incorrect", "zip": "99999",
            "country_id": self.env.ref("base.fr").id,
        })
        self._assert_location(self.guest)

    def test_create_completes_dummy_guest(self):
        guest = self.env["pms.checkin.partner"].create({
            "reservation_id": self.reservation.id, "zip_id": self.location.id,
        })
        self._assert_location(guest)

    def test_manual_edit_detaches_only_changed_guest(self):
        self.guest.write({"zip_id": self.location.id})
        self.other_guest.write({"zip": "28001", "city": "Madrid"})
        (self.guest | self.other_guest).write({"city": "Manual city"})
        self.assertFalse(self.guest.zip_id)
        self.assertFalse(self.other_guest.zip_id)
        self.assertEqual(self.guest.zip, "08001")
        self.assertEqual(self.other_guest.zip, "28001")
        self.assertEqual(self.guest.city, "Manual city")
        self.assertEqual(self.other_guest.city, "Manual city")

    def test_form_manual_edit_detaches_location(self):
        self.guest.write({"zip_id": self.location.id})
        with Form(self.guest) as form:
            form.city = "Manual city"
            self.assertFalse(form.zip_id)
        self.assertEqual(self.guest.city, "Manual city")

    def test_same_values_and_clearing_selector_preserve_address(self):
        self.guest.write({"zip_id": self.location.id})
        self.guest.write({"zip": "08001"})
        self._assert_location(self.guest)
        self.guest.write({"zip_id": False})
        self.assertFalse(self.guest.zip_id)
        self.assertEqual(self.guest.city, "Barcelona")
        self.assertEqual(self.guest.zip, "08001")

    def test_foreign_manual_address_remains_available(self):
        self.guest.write({"zip_id": self.location.id})
        self.guest.write({
            "country_id": self.env.ref("base.fr").id, "state_id": False,
            "zip": "75001", "city": "Paris",
        })
        self.assertFalse(self.guest.zip_id)
        self.assertEqual(self.guest.zip, "75001")
        self.assertEqual(self.guest.city, "Paris")

    def test_completion_preserves_conflicting_partner_address(self):
        partner = self.env["res.partner"].create({
            "name": "Existing guest", "zip": "28001", "city": "Madrid",
            "country_id": self.spain.id,
        })
        self.guest.partner_id = partner
        self.guest.write({"zip_id": self.location.id})
        self._assert_location(self.guest)
        self.assertEqual(partner.zip, "28001")
        self.assertEqual(partner.city, "Madrid")
        self.assertFalse(self.other_guest.zip_id)
