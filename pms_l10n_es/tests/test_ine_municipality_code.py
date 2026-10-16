from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.res_city import municipality_code_with_control, municipality_postal_index


@tagged("post_install", "-at_install")
class TestIneMunicipalityCode(TransactionCase):
    def setUp(self):
        super().setUp()
        self.spain = self.env.ref("base.es")
        self.state = self.env["res.country.state"].create({
            "name": "Municipal test province", "code": "MUN_TEST",
            "country_id": self.spain.id, "ine_code": "ES_TEST",
        })
        self.city = self.env["res.city"].create({
            "name": "Municipal test city", "country_id": self.spain.id,
            "state_id": self.state.id,
        })

    def _postal(self, code, city=None):
        return self.env["res.city.zip"].create({
            "city_id": (city or self.city).id, "name": code,
        })

    def test_control_matches_all_local_codes(self):
        codes = {code for matches in municipality_postal_index().values() for code in matches}
        self.assertGreater(len(codes), 8000)
        for code in codes:
            self.assertEqual(municipality_code_with_control(code[:5]), code)

    def test_known_control_values_and_zero(self):
        for base, full in [("08019", "080193"), ("25120", "251207"), ("01004", "010040")]:
            self.assertEqual(municipality_code_with_control(base), full)
        for invalid in [False, 8019, "8019", "080193", "0801X", " 08019", "00019", "08000"]:
            with self.assertRaises(ValueError):
                municipality_code_with_control(invalid)

    def test_barcelona_uses_mapping_not_postal_as_base(self):
        self._postal("08001")
        self.assertEqual(self.city.ine_municipality_code, "080193")
        self.assertFalse(self.city.ine_municipality_error)
        self.assertNotEqual(self.city.ine_municipality_code[:5], "08001")

    def test_lleida_mapping_and_zip_edit(self):
        postal = self._postal("25001")
        self.assertEqual(self.city.ine_municipality_code, "251207")
        postal.name = "08001"
        self.assertEqual(self.city.ine_municipality_code, "080193")

    def test_ambiguous_zip_pending_until_disambiguated(self):
        self._postal("01012")
        self.assertFalse(self.city.ine_municipality_code)
        self.assertIn("Ambiguous", self.city.ine_municipality_error)
        self._postal("01001")
        self.assertEqual(self.city.ine_municipality_code, "010590")
        self.assertFalse(self.city.ine_municipality_error)

    def test_conflicting_codes_do_not_select_first(self):
        self._postal("08001")
        self._postal("25001")
        self.assertFalse(self.city.ine_municipality_code)
        self.assertIn("conflicting", self.city.ine_municipality_error)

    def test_no_mapping_never_uses_hotel_or_postal_as_municipality(self):
        self.assertFalse(self.city.ine_municipality_code)
        self._postal("08000")
        self.assertFalse(self.city.ine_municipality_code)
        self.assertIn("No ZIP-to-INE", self.city.ine_municipality_error)

    def test_delete_and_move_postal_recomputes(self):
        postal = self._postal("08001")
        other = self.env["res.city"].create({
            "name": "Postal destination", "country_id": self.spain.id,
            "state_id": self.state.id,
        })
        postal.city_id = other
        self.assertFalse(self.city.ine_municipality_code)
        self.assertEqual(other.ine_municipality_code, "080193")
        postal.unlink()
        self.assertFalse(other.ine_municipality_code)
        self.assertTrue(other.ine_municipality_error)

    def test_foreign_country_and_incompatible_province(self):
        self._postal("08001")
        self.city.country_id = self.env.ref("base.fr")
        self.assertFalse(self.city.ine_municipality_code)
        self.assertFalse(self.city.ine_municipality_error)
        self.city.country_id = self.spain
        self.assertEqual(self.city.ine_municipality_code, "080193")
        # A province whose first city has a different ZIP prefix must be reviewed.
        other_state = self.env["res.country.state"].create({
            "name": "Other municipal province", "code": "MUN_OTHER",
            "country_id": self.spain.id, "ine_code": "ES_OTHER",
        })
        source = self.env["res.city"].create({
            "name": "Province prefix source", "country_id": self.spain.id,
            "state_id": other_state.id,
        })
        self._postal("25001", source)
        misplaced = self.env["res.city"].create({
            "name": "Misplaced city", "country_id": self.spain.id,
            "state_id": other_state.id,
        })
        self._postal("08001", misplaced)
        self.assertFalse(misplaced.ine_municipality_code)
        self.assertIn("do not match", misplaced.ine_municipality_error)
