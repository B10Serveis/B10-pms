# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    # Existing stored values also need the new postal-code calculation.
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["res.country.state"].search([])._compute_ine_province_code()
