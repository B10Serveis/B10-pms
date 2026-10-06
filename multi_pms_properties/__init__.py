# Copyright 2021 Dario Lodeiros
# Copyright 2021 Eric Antones
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging

from odoo import fields
from odoo.tools import config

from . import models


def _description_domain(self, env):
    if self.check_company and not self.domain:
        return _original_description_domain(self, env)

    if self.check_pms_properties and not self.domain:
        record = env[self.model_name]
        # Skip company_id domain to avoid domain multiproperty error in inherited views
        if (
            self.check_pms_properties
            and not self.domain
            and self.name not in ["company_id"]
        ):
            if self.model_name == "pms.property":
                prop1 = "id"
                prop2 = f"[{prop1}]"
            elif "pms_property_id" in record._fields:
                prop1 = "pms_property_id"
                prop2 = f"[{prop1}]"
            else:
                prop1 = prop2 = "pms_property_ids"
            coprop = (
                "pms_property_id"
                if "pms_property_id" in env[self.comodel_name]._fields
                else "pms_property_ids"
            )
            return f"['|', '|', \
                (not {prop1}, '=', True), \
                ('{coprop}', 'in', {prop2}), \
                ('{coprop}', '=', False)]"

    return _original_description_domain(self, env)


if "multi_pms_properties" in config.get("server_wide_modules"):
    _logger = logging.getLogger(__name__)
    _logger.info("monkey patching fields._Relational")

    _original_description_domain = fields._Relational._description_domain
    fields._Relational.check_pms_properties = False
    fields._Relational._description_domain = _description_domain
