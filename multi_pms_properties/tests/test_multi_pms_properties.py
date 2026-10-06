# Copyright 2021 Eric Antones
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import common

from .common import setup_test_model, teardown_test_model
from .multi_pms_properties_tester import (
    ChildTester,
    CompanyTester,
    ParentTester,
    PropertyTester,
)


@common.tagged("-at_install", "post_install")
class TestMultiPMSProperties(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.model_classes = [PropertyTester, ParentTester, ChildTester, CompanyTester]
        setup_test_model(cls.env, cls.model_classes)
        cls.other_company = cls.env["res.company"].create({"name": "Other company"})
        cls.prop_a, cls.prop_b = cls.env["pms.property.tester"].create(
            [
                {"name": "A", "company_id": cls.env.company.id},
                {"name": "B", "company_id": cls.env.company.id},
            ]
        )
        cls.prop_c = cls.env["pms.property.tester"].create(
            {"name": "C", "company_id": cls.other_company.id}
        )

    @classmethod
    def tearDownClass(cls):
        teardown_test_model(cls.env, cls.model_classes)
        super().tearDownClass()

    def _create(self, model, properties, **values):
        return self.env[model].create(
            {
                "name": "Test record",
                "pms_property_ids": [Command.set(properties.ids)],
                **values,
            }
        )

    def test_many2one_subset(self):
        parent = self._create("pms.parent.tester", self.prop_a | self.prop_b)
        self._create("pms.child.tester", self.prop_a, parent_id=parent.id)
        with self.assertRaises(UserError), self.cr.savepoint():
            self._create("pms.child.tester", self.prop_c, parent_id=parent.id)

    def test_shared_many2one(self):
        parent = self._create("pms.parent.tester", self.prop_a)
        with self.assertRaises(UserError), self.cr.savepoint():
            self._create("pms.child.tester", self.prop_a.browse(), parent_id=parent.id)
        shared = self._create("pms.parent.tester", self.prop_a.browse())
        self._create("pms.child.tester", self.prop_a, parent_id=shared.id)

    def test_many2many_checks_each_record(self):
        compatible = self._create("pms.child.tester", self.prop_a)
        incompatible = self._create("pms.child.tester", self.prop_b)
        with self.assertRaises(UserError), self.cr.savepoint():
            self._create(
                "pms.parent.tester",
                self.prop_a,
                linked_ids=[Command.set((compatible | incompatible).ids)],
            )

    def test_one2many_subset(self):
        parent = self._create("pms.parent.tester", self.prop_a | self.prop_b)
        self._create("pms.child.tester", self.prop_a, parent_id=parent.id)
        with self.assertRaises(UserError), self.cr.savepoint():
            parent.write({"pms_property_ids": [Command.set(self.prop_b.ids)]})

    def test_write_checks_properties(self):
        parent = self._create("pms.parent.tester", self.prop_a)
        child = self._create("pms.child.tester", self.prop_a, parent_id=parent.id)
        with self.assertRaises(UserError), self.cr.savepoint():
            child.write({"pms_property_ids": [Command.set(self.prop_b.ids)]})
        child.write({"name": "Compatible rename"})

    def test_company_without_checked_relations(self):
        with self.assertRaises(UserError), self.cr.savepoint():
            self.env["pms.company.tester"].create(
                {
                    "name": "Wrong company",
                    "company_id": self.env.company.id,
                    "pms_property_id": self.prop_c.id,
                }
            )
        record = self.env["pms.company.tester"].create(
            {
                "name": "Correct company",
                "company_id": self.env.company.id,
                "pms_property_id": self.prop_a.id,
            }
        )
        with self.assertRaises(UserError), self.cr.savepoint():
            record.write({"company_id": self.other_company.id})

    def test_multiple_property_companies(self):
        with self.assertRaises(UserError), self.cr.savepoint():
            self._create(
                "pms.parent.tester",
                self.prop_a | self.prop_c,
                company_id=self.env.company.id,
            )

    def test_property_domain(self):
        field = self.env["pms.child.tester"]._fields["parent_id"]
        domain = field._description_domain(self.env)
        self.assertIn("pms_property_ids", domain)
        self.assertIn("'in'", domain)

    def test_standard_domains_preserved(self):
        field = self.env["pms.child.tester"]._fields["standard_company_id"]
        self.assertEqual(
            field._description_domain(self.env),
            "[('company_id', 'in', [company_id, False])]",
        )
        explicit = self.env["pms.child.tester"]._fields["explicit_parent_id"]
        self.assertEqual(explicit._description_domain(self.env), [("name", "=", "A")])
        callable_field = self.env["pms.child.tester"]._fields["callable_parent_id"]
        self.assertEqual(
            callable_field._description_domain(self.env),
            [("name", "=", "pms.child.tester")],
        )
