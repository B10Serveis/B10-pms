# Copyright 2021 Eric Antones
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class PropertyTester(models.Model):
    _name = "pms.property.tester"
    _description = "Property consistency test property"

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True)


class ParentTester(models.Model):
    _name = "pms.parent.tester"
    _description = "Property consistency test parent"
    _check_pms_properties_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company")
    pms_property_ids = fields.Many2many("pms.property.tester")
    child_ids = fields.One2many(
        "pms.child.tester", "parent_id", check_pms_properties=True
    )
    linked_ids = fields.Many2many("pms.child.tester", check_pms_properties=True)


class ChildTester(models.Model):
    _name = "pms.child.tester"
    _description = "Property consistency test child"
    _check_pms_properties_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company")
    pms_property_ids = fields.Many2many("pms.property.tester")
    parent_id = fields.Many2one("pms.parent.tester", check_pms_properties=True)
    standard_company_id = fields.Many2one("res.company", check_company=True)
    explicit_parent_id = fields.Many2one(
        "pms.parent.tester", check_pms_properties=True, domain=[("name", "=", "A")]
    )
    callable_parent_id = fields.Many2one(
        "pms.parent.tester",
        check_pms_properties=True,
        domain=lambda record: [("name", "=", record._name)],
    )


class CompanyTester(models.Model):
    _name = "pms.company.tester"
    _description = "Property consistency without checked relations"
    _check_pms_properties_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company")
    pms_property_id = fields.Many2one("pms.property.tester")
