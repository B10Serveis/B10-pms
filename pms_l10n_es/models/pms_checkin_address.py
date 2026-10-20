# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class PmsCheckinPartner(models.Model):
    _inherit = "pms.checkin.partner"

    zip_id = fields.Many2one(
        "res.city.zip",
        string="Residence location completion",
        help="Search by postal code or city to fill the residence city, postal code, "
        "province and country together. The address is saved for this stay.",
        ondelete="set null",
    )

    def _residence_location_values(self, location):
        return {
            "zip": location.name,
            "city": location.city_id.name,
            "state_id": location.state_id.id,
            "country_id": location.country_id.id,
        }

    def _residence_matches_location(self, values):
        self.ensure_one()
        expected = self._residence_location_values(self.zip_id)
        return all(
            values.get(name, self[name].id if name.endswith("_id") else self[name])
            == value
            for name, value in expected.items()
        )

    @api.onchange("zip_id")
    def _onchange_residence_zip_id(self):
        for guest in self.filtered("zip_id"):
            guest.update(guest._residence_location_values(guest.zip_id))

    @api.onchange("zip", "city", "state_id", "country_id")
    def _onchange_residence_address(self):
        for guest in self.filtered("zip_id"):
            if not guest._residence_matches_location({}):
                guest.zip_id = False

    @api.model_create_multi
    def create(self, vals_list):
        normalized = []
        for values in vals_list:
            values = dict(values)
            if values.get("zip_id"):
                location = self.env["res.city.zip"].browse(values["zip_id"])
                values.update(self._residence_location_values(location))
            normalized.append(values)
        return super().create(normalized)

    def write(self, values):
        values = dict(values)
        if values.get("zip_id"):
            location = self.env["res.city.zip"].browse(values["zip_id"])
            values.update(self._residence_location_values(location))
        elif "zip_id" not in values and {"zip", "city", "state_id", "country_id"}.intersection(values):
            # Manual edits detach the completion choice without changing other stays
            # or forcing the guest's address back to the selected postal location.
            mismatched = self.filtered(
                lambda guest: guest.zip_id and not guest._residence_matches_location(values)
            )
            if mismatched:
                super(PmsCheckinPartner, mismatched).write(dict(values, zip_id=False))
                return super(PmsCheckinPartner, self - mismatched).write(values)
        return super().write(values)
