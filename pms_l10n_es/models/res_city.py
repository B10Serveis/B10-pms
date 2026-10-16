# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import csv
import re
from functools import lru_cache

from odoo import _, api, fields, models
from odoo.modules.module import get_module_resource


def municipality_code_with_control(base_code):
    """Complete an INE municipal base code, never a postal code.

    Substitution tables follow the original linked implementations. Reduce
    the final result modulo ten too: a nonzero sum divisible by ten gives 0.
    This checks structure and checksum, not the official code assignment.
    """
    if (
        not isinstance(base_code, str)
        or not re.fullmatch(r"[0-9]{5}", base_code)
        or not 1 <= int(base_code[:2]) <= 52
        or base_code[2:] == "000"
    ):
        raise ValueError("Expected a five-digit INE municipality base code.")
    identity = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9)
    triple = (0, 3, 8, 2, 7, 4, 1, 5, 9, 6)
    double = (0, 2, 4, 6, 8, 1, 3, 5, 7, 9)
    tables = (double, triple, identity, double, triple)
    total = sum(table[int(digit)] for table, digit in zip(tables, base_code))
    return base_code + str((-total) % 10)


class ResCity(models.Model):
    _inherit = "res.city"

    ine_municipality_code = fields.Char(
        string="INE municipality code",
        compute="_compute_ine_municipality_code",
        store=True,
        help="Six-digit municipal INE code, resolved through the ZIP-to-INE "
        "mapping. The first five digits are a municipal code, not a ZIP.",
    )
    ine_municipality_error = fields.Text(
        string="INE municipality validation",
        compute="_compute_ine_municipality_code",
        store=True,
    )
    ine_municipality_previous_code = fields.Char(
        string="Previously entered INE municipality code",
        readonly=True,
        copy=False,
        help="Preserved during migration for review; not used as an automatic mapping.",
    )

    @api.depends(
        "zip_ids.name", "country_id.code", "state_id.country_id",
        "state_id.ine_province_code",
    )
    def _compute_ine_municipality_code(self):
        for city in self:
            city.ine_municipality_code = False
            city.ine_municipality_error = False
            if city.country_id.code != "ES":
                continue
            if city.state_id and city.state_id.country_id != city.country_id:
                city.ine_municipality_error = _(
                    "The city and its province belong to different countries."
                )
                continue
            code, error = municipality_code_for_postals(
                city.zip_ids.mapped("name"), city.state_id.ine_province_code
            )
            city.ine_municipality_code = code
            city.ine_municipality_error = error


@lru_cache(maxsize=1)
def municipality_postal_index():
    """Exact ZIP -> municipal INE codes; preserve all ambiguous matches."""
    resource = get_module_resource(
        "pms_l10n_es", "static", "src", "pms.ine.zip.municipality.ine.relation.csv"
    )
    result = {}
    with open(resource, encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            postal = row["codigo_postal"]
            code = row["municipio_id"]
            if (
                not re.fullmatch(r"[0-9]{5}", postal)
                or not re.fullmatch(r"[0-9]{6}", code)
                or municipality_code_with_control(code[:5]) != code
            ):
                raise ValueError("Invalid ZIP/municipality mapping: %s / %s" % (postal, code))
            result.setdefault(postal, set()).add(code)
    return {postal: frozenset(codes) for postal, codes in result.items()}


def municipality_code_for_postals(postals, province=False):
    """Resolve a unique municipal code; an ambiguous ZIP is not a choice."""
    try:
        postal_index = municipality_postal_index()
    except ValueError as error:
        return False, _("Invalid municipal mapping data: %s", str(error))
    candidates = None
    matched_postals = []
    for postal in sorted(set(postals)):
        matches = postal_index.get(postal)
        if matches:
            matched_postals.append(postal)
            candidates = set(matches) if candidates is None else candidates.intersection(matches)
    if candidates is None:
        return False, _("No ZIP-to-INE municipality mapping found for this city.")
    if not candidates:
        return False, _(
            "The postal codes point to conflicting municipalities: %s",
            ", ".join(matched_postals),
        )
    if province:
        candidates = {code for code in candidates if code.startswith(province)}
    if not candidates:
        return False, _("Municipal INE candidates do not match the city province.")
    if len(candidates) != 1:
        return False, _(
            "Ambiguous ZIP-to-INE municipality mapping: %s",
            ", ".join(sorted(candidates)),
        )
    return municipality_code_with_control(next(iter(candidates))[:5]), False
