import datetime
from types import SimpleNamespace
from unittest.mock import patch

from odoo import fields
from odoo.addons.pms.controllers.pms_portal import PortalFolio, PortalReservation
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .common import TestPms


@tagged("post_install", "-at_install")
class TestPmsPortalSecurity(TestPms):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create(
            {"name": "Portal customer", "is_company": True}
        )
        cls.contact = cls.env["res.partner"].create(
            {"name": "Portal contact", "parent_id": cls.customer.id}
        )
        cls.other_customer = cls.env["res.partner"].create(
            {"name": "Other portal customer", "is_company": True}
        )
        cls.portal_user = new_test_user(
            cls.env,
            login="pms_portal_security_customer",
            groups="base.group_portal",
            partner_id=cls.contact.id,
            company_id=cls.company1.id,
            company_ids=[(6, 0, cls.company1.ids)],
            pms_property_ids=[(6, 0, cls.pms_property1.ids)],
        )
        cls.other_portal_user = new_test_user(
            cls.env,
            login="pms_portal_security_other",
            groups="base.group_portal",
            partner_id=cls.other_customer.id,
            company_id=cls.company1.id,
            company_ids=[(6, 0, cls.company1.ids)],
            pms_property_ids=[(6, 0, cls.pms_property1.ids)],
        )
        cls.staff_user = new_test_user(
            cls.env,
            login="pms_portal_security_staff",
            groups="base.group_user,pms.group_pms_user",
            company_id=cls.company1.id,
            company_ids=[(6, 0, cls.company1.ids)],
            pms_property_ids=[(6, 0, cls.pms_property1.ids)],
        )
        room_type = cls.env["pms.room.type"].create(
            {
                "name": "Portal security room type",
                "default_code": "PORTAL",
                "class_id": cls.room_type_class1.id,
                "pms_property_ids": [(6, 0, cls.pms_property1.ids)],
            }
        )
        room = cls.env["pms.room"].create(
            {
                "name": "Portal security room",
                "capacity": 2,
                "room_type_id": room_type.id,
                "pms_property_id": cls.pms_property1.id,
            }
        )
        channel = cls.env["pms.sale.channel"].create(
            {"name": "Portal security direct", "channel_type": "direct"}
        )
        cls.reservations = cls.env["pms.reservation"]
        partners = (cls.customer, cls.contact, cls.other_customer)
        for index, partner in enumerate(partners):
            checkin = fields.Date.today() + datetime.timedelta(days=10 + index * 2)
            cls.reservations |= cls.env["pms.reservation"].create(
                {
                    "partner_id": partner.id,
                    "checkin": checkin,
                    "checkout": checkin + datetime.timedelta(days=1),
                    "adults": 1,
                    "preferred_room_id": room.id,
                    "room_type_id": room_type.id,
                    "pms_property_id": cls.pms_property1.id,
                    "sale_channel_origin_id": channel.id,
                }
            )
        cls.own_reservations = cls.reservations[:2]
        cls.other_reservation = cls.reservations[2]
        cls.own_folios = cls.own_reservations.mapped("folio_id")
        cls.other_folio = cls.other_reservation.folio_id
        cls.own_checkins = cls.own_reservations.mapped("checkin_partner_ids")
        cls.other_checkins = cls.other_reservation.checkin_partner_ids
        # A guest's identity must not grant access to another customer's booking.
        cls.other_checkins[0].partner_id = cls.contact
        cls.env.flush_all()

    def test_portal_search_is_scoped_to_commercial_partner(self):
        for records, expected in (
            (self.reservations, self.own_reservations),
            (self.reservations.mapped("folio_id"), self.own_folios),
            (self.reservations.mapped("checkin_partner_ids"), self.own_checkins),
            (
                self.customer | self.contact | self.other_customer,
                self.customer | self.contact,
            ),
        ):
            with self.subTest(model=records._name):
                visible = records.with_user(self.portal_user).search(
                    [("id", "in", records.ids)]
                )
                self.assertEqual(set(visible.ids), set(expected.ids))
                expected.with_user(self.portal_user).read(["id"])

    def test_other_customer_cannot_read_records_by_id(self):
        for records in (
            self.own_folios,
            self.own_reservations,
            self.own_checkins,
            self.contact,
        ):
            with self.subTest(model=records._name):
                with self.assertRaises(AccessError):
                    records.with_user(self.other_portal_user).read(["id"])

    def test_portal_cannot_modify_create_or_delete(self):
        for record, create_values in (
            (self.contact, {"name": "Unexpected portal contact"}),
            (self.own_checkins[0], {"reservation_id": self.own_reservations[0].id}),
        ):
            model = self.env[record._name].with_user(self.portal_user)
            write_values = (
                {"partner_id": self.contact.id}
                if record._name == "pms.checkin.partner"
                else {"name": "Changed"}
            )
            with self.subTest(model=record._name):
                with self.assertRaises(AccessError):
                    record.with_user(self.portal_user).write(write_values)
                with self.assertRaises(AccessError):
                    model.create(create_values)
                with self.assertRaises(AccessError):
                    record.with_user(self.portal_user).unlink()

    def test_internal_staff_access_is_preserved(self):
        for records in (
            self.reservations,
            self.reservations.mapped("folio_id"),
            self.reservations.mapped("checkin_partner_ids"),
        ):
            with self.subTest(model=records._name):
                records.with_user(self.staff_user).read(["id"])
                self.assertTrue(
                    records.with_user(self.staff_user).check_access_rights("write")
                )

    def test_portal_counters_include_commercial_partner_bookings(self):
        with patch(
            "odoo.addons.pms.controllers.pms_portal.request",
            SimpleNamespace(env=self.env(user=self.portal_user)),
        ):
            values = PortalFolio()._prepare_home_portal_values(["folio_count"])
            self.assertEqual(values["folio_count"], len(self.own_folios))
            values = PortalReservation()._prepare_home_portal_values(
                ["reservation_count"]
            )
            self.assertEqual(values["reservation_count"], len(self.own_reservations))

    def test_document_access_requires_ownership_or_valid_token(self):
        controller = CustomerPortal()
        for record in (self.other_folio, self.other_reservation, self.other_checkins[0]):
            token = record._portal_ensure_token()
            with self.subTest(model=record._name):
                for user in (self.portal_user, self.env.ref("base.public_user")):
                    with patch(
                        "odoo.addons.portal.controllers.portal.request",
                        SimpleNamespace(env=self.env(user=user)),
                    ):
                        with self.assertRaises(AccessError):
                            controller._document_check_access(record._name, record.id)
                        with self.assertRaises(AccessError):
                            controller._document_check_access(
                                record._name, record.id, "invalid-token"
                            )
                        document = controller._document_check_access(
                            record._name, record.id, token
                        )
                        self.assertEqual(document.id, record.id)
                        self.assertTrue(document.env.su)
