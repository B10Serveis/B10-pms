import re

from odoo import _, api, fields, models


class ResCountryState(models.Model):
    _inherit = "res.country.state"

    ine_code = fields.Char(string="INE State Code")

    ine_municipality_ids = fields.One2many(
        "res.city", "state_id", string="Municipalities", readonly=True
    )
    ine_province_code = fields.Char(
        string="INE province code",
        compute="_compute_ine_province_code",
        store=True,
        help="First two digits of the first valid Spanish postal code in the "
        "linked cities. Cities are ordered by ID, postal codes by code and ID.",
    )
    ine_province_error = fields.Text(
        string="INE province validation",
        compute="_compute_ine_province_code",
        store=True,
    )

    @api.depends(
        "country_id.code",
        "ine_municipality_ids.zip_ids.name",
        "ine_municipality_ids.country_id",
    )
    def _compute_ine_province_code(self):
        for state in self:
            state.ine_province_code = False
            state.ine_province_error = False
            if state.country_id.code != "ES":
                continue
            # Use a stable order, independent of translated city names.
            cities = state.with_context(active_test=False).ine_municipality_ids.sorted("id")
            for city in cities:
                if city.country_id != state.country_id:
                    continue
                for postal in city.zip_ids.sorted(lambda record: (record.name, record.id)):
                    code = postal.name or ""
                    if re.fullmatch(r"[0-9]{5}", code) and 1 <= int(code[:2]) <= 52:
                        state.ine_province_code = code[:2]
                        break
                if state.ine_province_code:
                    break
            if not state.ine_province_code:
                state.ine_province_error = _(
                    "No linked Spanish city has a valid five-digit postal code."
                )

    @api.constrains("ine_code")
    def _check_ine_code(self):
        for record in self:
            if record.country_id.code == "ES" and not record.ine_code:
                raise models.ValidationError(
                    _("The state {state} of {country} must have an INE code").format(
                        state=record.name, country=record.country_id.name
                    )
                )
