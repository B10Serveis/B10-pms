# Copyright 2021 Dario Lodeiros
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, models
from odoo.exceptions import UserError


class BaseModel(models.AbstractModel):
    _inherit = "base"
    _check_pms_properties_auto = False
    """On write and create, call ``_check_pms_properties_auto`` to ensure properties
    consistency on the relational fields having ``check_pms_properties=True``
    as attribute.
    """

    def _valid_field_parameter(self, field, name):
        """Make new field attribute valid for Odoo."""
        return name == "check_pms_properties" or super()._valid_field_parameter(
            field, name
        )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self._check_pms_properties_auto:
            records._check_pms_properties()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not res or not self._check_pms_properties_auto:
            return res
        check_pms_properties = False
        for fname in vals:
            field = self._fields.get(fname)
            if (
                fname == "pms_property_id"
                or fname == "pms_property_ids"
                or fname == "company_id"
                or (
                    field
                    and field.relational
                    and getattr(field, "check_pms_properties", False)
                )
            ):
                check_pms_properties = True
        if check_pms_properties:
            self._check_pms_properties()
        return res

    def _check_pms_properties(self, fnames=None):
        """Check the properties of the values of the given field names.

        :param list fnames: names of relational fields to check
        :raises UserError: if properties or their companies are incompatible.

        A many2one target must cover all properties of its source. One2many
        children must be contained in their parent's properties. Many2many
        links require overlapping properties. Unrestricted targets are shared.
        Company consistency is checked even when there are no marked relations.
        """
        if fnames is None:
            fnames = self._fields

        regular_fields = self._get_regular_fields(fnames)

        inconsistencies = self._check_inconsistencies(regular_fields)

        if inconsistencies:
            lines = [_("Incompatible properties on records:")]
            property_msg = _(
                """- Record is properties %(pms_properties)r and %(field)r
                (%(fname)s: %(values)s) belongs to another properties."""
            )
            record_msg = _(
                """- %(record)r belongs to properties %(pms_properties)r and
                %(field)r (%(fname)s: %(values)s) belongs to another properties."""
            )
            for record, name, corecords in inconsistencies[:5]:
                if record._name == "pms.property":
                    msg, pms_properties = property_msg, record
                else:
                    msg, pms_properties = (
                        record_msg,
                        record.pms_property_id.name
                        if "pms_property_id" in record
                        else ", ".join(repr(p.name) for p in record.pms_property_ids),
                    )
                field = self.env["ir.model.fields"]._get(self._name, name)
                lines.append(
                    msg
                    % {
                        "record": record.display_name,
                        "pms_properties": pms_properties,
                        "field": field.field_description,
                        "fname": field.name,
                        "values": ", ".join(
                            repr(rec.display_name) for rec in corecords
                        ),
                    }
                )
            raise UserError("\n".join(lines))

    def _get_regular_fields(self, fnames):
        regular_fields = []
        for name in fnames:
            field = self._fields[name]
            if (
                field.relational
                and getattr(field, "check_pms_properties", False)
                and (
                    "pms_property_id" in self.env[field.comodel_name]
                    or "pms_property_ids" in self.env[field.comodel_name]
                )
            ):
                regular_fields.append(name)
        return regular_fields

    def _check_inconsistencies(self, regular_fields):
        inconsistencies = []
        for record in self:
            pms_properties = False
            if record._name == "pms.property":
                pms_properties = record
            if "pms_property_id" in record:
                pms_properties = record.pms_property_id
            if "pms_property_ids" in record:
                pms_properties = record.pms_property_ids
            # Check the property & company consistence
            if "company_id" in self._fields:
                if record.company_id and pms_properties:
                    property_companies = pms_properties.mapped("company_id")
                    if (
                        len(property_companies) > 1
                        or property_companies != record.company_id
                    ):
                        raise UserError(
                            _(
                                "You cannot establish a company other than "
                                "the one with the established properties"
                            )
                        )
            # Check verifies that all
            # records linked via relation fields are compatible
            # with the properties of the origin document,
            for name in regular_fields:
                field = self._fields[name]
                # Check each linked record separately. Unioning their properties
                # can hide an incompatible record behind a compatible one.
                corecords = record.sudo()[name]
                for corecord in corecords:
                    co_pms_properties = False
                    if "pms_property_id" in corecord:
                        co_pms_properties = corecord.pms_property_id
                    if "pms_property_ids" in corecord:
                        co_pms_properties = corecord.pms_property_ids
                    if (
                        # Many2many requires overlap; one2many requires the
                        # child's properties to be a subset of the parent's.
                        # Many2one requires the inverse subset relationship.
                        (
                            pms_properties
                            and co_pms_properties
                            and (not pms_properties & co_pms_properties)
                        )
                        or (
                            corecord
                            and field.type == "one2many"
                            and pms_properties
                            and (co_pms_properties - pms_properties)
                        )
                        or (
                            field.type == "many2one"
                            and co_pms_properties
                            and ((pms_properties - co_pms_properties) or not pms_properties)
                        )
                    ):
                        inconsistencies.append((record, name, corecord))
        return inconsistencies
