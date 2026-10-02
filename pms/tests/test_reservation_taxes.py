from odoo import Command
from odoo.tests import tagged

from .common import TestPms


@tagged("post_install", "-at_install")
class TestReservationTaxes(TestPms):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company1.account_fiscal_country_id = cls.env.ref("base.es")
        cls.tax = cls.env["account.tax"].create(
            {
                "name": "Included room VAT",
                "amount": 21,
                "price_include": True,
                "company_id": cls.company1.id,
            }
        )
        cls.mapped_tax = cls.env["account.tax"].create(
            {
                "name": "Mapped room VAT",
                "amount": 0,
                "company_id": cls.company1.id,
            }
        )
        cls.position = cls.env["account.fiscal.position"].create(
            {
                "name": "Room tax mapping",
                "company_id": cls.company1.id,
                "tax_ids": [
                    Command.create(
                        {"tax_src_id": cls.tax.id, "tax_dest_id": cls.mapped_tax.id}
                    )
                ],
            }
        )
        cls.partner = cls.env["res.partner"].create({"name": "Room guest"})
        cls.product = cls.env["product.product"].create(
            {"name": "Room", "taxes_id": [Command.set(cls.tax.ids)]}
        )
        cls.room_type = cls.env["pms.room.type"].create(
            {
                "product_id": cls.product.id,
                "class_id": cls.room_type_class1.id,
                "default_code": "TAX_TEST",
            }
        )

    def _reservation(self, **values):
        return self.env["pms.reservation"].new(
            dict(
                {
                    "room_type_id": self.room_type.id,
                    "pms_property_id": self.pms_property1.id,
                    "partner_id": self.partner.id,
                },
                **values,
            )
        )

    def test_taxes_before_folio_creation(self):
        reservation = self._reservation()
        self.assertFalse(reservation.company_id)
        self.assertEqual(reservation.tax_ids._origin, self.tax)

    def test_partner_position_before_folio_creation(self):
        self.partner.with_company(self.company1).property_account_position_id = (
            self.position
        )
        self.assertEqual(self._reservation().tax_ids._origin, self.mapped_tax)

    def test_folio_position_has_priority(self):
        self.partner.with_company(self.company1).property_account_position_id = (
            self.position
        )
        folio = self.env["pms.folio"].create(
            {
                "pms_property_id": self.pms_property1.id,
                "partner_id": self.partner.id,
                "fiscal_position_id": False,
            }
        )
        self.assertEqual(self._reservation(folio_id=folio.id).tax_ids._origin, self.tax)

    def test_explicit_empty_taxes_are_preserved(self):
        self.assertFalse(self._reservation(tax_ids=[Command.clear()]).tax_ids)

    def test_explicit_manual_taxes_are_preserved(self):
        self.assertEqual(
            self._reservation(tax_ids=[Command.set(self.mapped_tax.ids)]).tax_ids._origin,
            self.mapped_tax,
        )

    def test_without_property_does_not_use_current_company(self):
        self.assertFalse(self._reservation(pms_property_id=False).tax_ids)
