# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["res.city"].with_context(active_test=False).search([])._compute_ine_municipality_code()
