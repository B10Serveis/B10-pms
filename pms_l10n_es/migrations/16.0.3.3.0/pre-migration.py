# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo.tools import sql


def migrate(cr, version):
    # Preserve the former free-text field before it becomes computed.
    if not sql.column_exists(cr, "res_city", "ine_municipality_previous_code"):
        sql.create_column(cr, "res_city", "ine_municipality_previous_code", "varchar")
    if sql.column_exists(cr, "res_city", "ine_municipality_code"):
        cr.execute("""
            UPDATE res_city
               SET ine_municipality_previous_code = ine_municipality_code
             WHERE ine_municipality_code IS NOT NULL
               AND ine_municipality_previous_code IS NULL
        """)
