from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestIneProvinceCode(TransactionCase):
    def setUp(self):
        super().setUp()
        self.spain = self.env.ref("base.es")
        self.state = self.env["res.country.state"].create({
            "name": "INE test province", "code": "INE_TEST",
            "country_id": self.spain.id, "ine_code": "ES_TEST",
        })

    def _city(self, name, state=None, country=None):
        return self.env["res.city"].create({
            "name": name, "state_id": (state or self.state).id,
            "country_id": (country or self.spain).id,
        })

    def _postal(self, city, code):
        return self.env["res.city.zip"].create({"city_id": city.id, "name": code})

    def test_no_postal_codes_leaves_pending(self):
        self._city("Uncoded locality")
        self.assertFalse(self.state.ine_province_code)
        self.assertIn("postal code", self.state.ine_province_error)
        self.assertEqual(self.state.ine_code, "ES_TEST")

    def test_barcelona_preserves_leading_zero_without_municipal_ine(self):
        city = self._city("Barcelona")
        self._postal(city, "08000")
        self.assertFalse(city.ine_municipality_code)
        self.assertEqual(self.state.ine_province_code, "08")
        self.assertFalse(self.state.ine_province_error)
        self.assertEqual(self.state.ine_code, "ES_TEST")

    def test_lleida_postal_prefix(self):
        self._postal(self._city("Lleida"), "25000")
        self.assertEqual(self.state.ine_province_code, "25")

    def test_first_city_and_first_postal_only(self):
        first = self._city("Z first created city")
        self._postal(first, "25001")
        self._postal(first, "08000")
        self._postal(self._city("A second created city"), "01000")
        self.assertEqual(self.state.ine_province_code, "08")
        self.assertFalse(self.state.ine_province_error)

    def test_invalid_codes_skipped_until_first_valid(self):
        city = self._city("Invalid postals")
        for code in ["008000", "8000", "0800X", " 08000", "99000", "00000"]:
            self._postal(city, code)
        self.assertFalse(self.state.ine_province_code)
        self.assertTrue(self.state.ine_province_error)
        self._postal(self._city("First usable city"), "01000")
        self.assertEqual(self.state.ine_province_code, "01")

    def test_postal_edit_move_delete_recomputes(self):
        city = self._city("Postal source")
        postal = self._postal(city, "08000")
        self.assertEqual(self.state.ine_province_code, "08")
        postal.name = "25000"
        self.assertEqual(self.state.ine_province_code, "25")
        other_state = self.env["res.country.state"].create({
            "name": "Second province", "code": "INE_TEST_2",
            "country_id": self.spain.id, "ine_code": "ES_TEST_2",
        })
        destination = self._city("Destination", state=other_state)
        postal.city_id = destination
        self.assertFalse(self.state.ine_province_code)
        self.assertEqual(other_state.ine_province_code, "25")
        postal.unlink()
        self.assertFalse(other_state.ine_province_code)
        self.assertTrue(other_state.ine_province_error)

    def test_moving_and_deleting_city_recomputes_states(self):
        other_state = self.env["res.country.state"].create({
            "name": "Second province", "code": "INE_TEST_2",
            "country_id": self.spain.id, "ine_code": "ES_TEST_2",
        })
        city = self._city("Movable")
        self._postal(city, "01000")
        self.assertEqual(self.state.ine_province_code, "01")
        city.state_id = other_state
        self.assertFalse(self.state.ine_province_code)
        self.assertEqual(other_state.ine_province_code, "01")
        city.unlink()
        self.assertFalse(other_state.ine_province_code)
        self.assertTrue(other_state.ine_province_error)

    def test_wrong_country_skipped(self):
        city = self._city("Country mismatch", country=self.env.ref("base.fr"))
        self._postal(city, "08000")
        self.assertFalse(self.state.ine_province_code)
        city.country_id = self.spain
        self.assertEqual(self.state.ine_province_code, "08")

    def test_country_change_clears_code(self):
        self._postal(self._city("Spanish municipality"), "08000")
        self.assertEqual(self.state.ine_province_code, "08")
        self.state.country_id = self.env.ref("base.fr")
        self.assertFalse(self.state.ine_province_code)
        self.assertFalse(self.state.ine_province_error)
