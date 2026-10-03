from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import TestPms


@tagged("post_install", "-at_install")
class TestPmsPricelistMinPrice(TestPms):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.room_type = cls.env["pms.room.type"].create(
            {
                "name": "Minimum price room",
                "default_code": "MIN",
                "class_id": cls.room_type_class1.id,
                "min_price": 50,
                "pms_property_ids": [(6, 0, cls.pms_property1.ids)],
            }
        )
        cls.product = cls.room_type.product_id
        cls.items = cls.env["product.pricelist.item"]

    def _values(self, **kwargs):
        values = {
            "pricelist_id": self.pricelist1.id,
            "pms_property_ids": [(6, 0, self.pms_property1.ids)],
            "compute_price": "fixed",
            "fixed_price": 50,
        }
        values.update(kwargs)
        return values

    def test_global_and_category_fixed_prices_without_product(self):
        rules = self.items.create(
            [
                self._values(applied_on="3_global", fixed_price=10),
                self._values(
                    applied_on="2_product_category",
                    categ_id=self.product.categ_id.id,
                    fixed_price=10,
                ),
            ]
        )
        self.assertEqual(len(rules), 2)
        self.assertFalse(rules.mapped("product_id"))
        rules.write({"fixed_price": 5})

    def test_variant_and_template_minimum_on_create(self):
        for target in (
            {"product_id": self.product.id},
            {"product_tmpl_id": self.product.product_tmpl_id.id},
        ):
            with self.subTest(target=target):
                with self.assertRaises(ValidationError):
                    self.items.create(self._values(fixed_price=49, **target))
                rule = self.items.create(self._values(**target))
                self.assertEqual(rule.fixed_price, 50)

    def test_minimum_on_write_and_target_change(self):
        for target in (
            {"applied_on": "0_product_variant", "product_id": self.product.id},
            {
                "applied_on": "1_product",
                "product_tmpl_id": self.product.product_tmpl_id.id,
            },
        ):
            with self.subTest(target=target):
                rule = self.items.create(self._values(**target))
                with self.assertRaises(ValidationError):
                    rule.write({"fixed_price": 49})
                rule.write({"fixed_price": 60})
                global_rule = self.items.create(self._values(fixed_price=10))
                with self.assertRaises(ValidationError):
                    global_rule.write(target)

    def test_non_fixed_rules_ignore_unused_fixed_price(self):
        rule = self.items.create(
            self._values(
                product_id=self.product.id, compute_price="percentage", fixed_price=0
            )
        )
        rule.write({"fixed_price": 10})
        with self.assertRaises(ValidationError):
            rule.write({"compute_price": "fixed"})

    def test_non_room_products_and_rooms_without_minimum(self):
        product = self.env["product.product"].create({"name": "Ordinary service"})
        self.items.create(self._values(product_id=product.id, fixed_price=0))
        self.items.create(
            self._values(product_tmpl_id=product.product_tmpl_id.id, fixed_price=0)
        )
        self.room_type.min_price = 0
        self.items.create(self._values(product_id=self.product.id, fixed_price=0))

    def test_batch_creation_validates_each_rule(self):
        with self.assertRaises(ValidationError):
            self.items.create(
                [
                    self._values(fixed_price=10),
                    self._values(product_id=self.product.id, fixed_price=49),
                ]
            )
