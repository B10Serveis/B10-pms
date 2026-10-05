from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval

from ..wizards.traveller_report import TravellerReport, clean_string_only_letters


class TestTravellerReport(TransactionCase):
    def test_names_preserve_accents(self):
        self.assertEqual(clean_string_only_letters(" José  Muñoz-123 "), "JOSÉ MUÑOZ")
        self.assertEqual(clean_string_only_letters(False), "")

    def test_reservation_report_filters_dates_and_room(self):
        model = Mock()
        model.search.return_value.mapped.return_value = [42]
        wizard = SimpleNamespace(
            env={"pms.reservation": model}, generate_xml_reservations=Mock()
        )
        TravellerReport.generate_ses_reservation_list(
            wizard, 1, date(2026, 10, 1), date(2026, 10, 5), room_id=7
        )
        domain = model.search.call_args[0][0]
        self.assertNotIn("|", domain)
        self.assertIn(("date_order", ">=", date(2026, 10, 1)), domain)
        self.assertIn(("date_order", "<", date(2026, 10, 6)), domain)
        self.assertIn(("preferred_room_id", "=", 7), domain)
        wizard.generate_xml_reservations.assert_called_once_with([42])

    def test_traveller_report_filters_room(self):
        model = Mock()
        model.search.return_value.mapped.return_value = [42]
        wizard = SimpleNamespace(
            env={"pms.reservation": model},
            generate_xml_reservations_travellers_report=Mock(),
        )
        TravellerReport.generate_ses_travellers_list(
            wizard, 1, date(2026, 10, 5), room_id=7
        )
        self.assertIn(("preferred_room_id", "=", 7), model.search.call_args[0][0])

    def test_manual_send_selects_communication(self):
        model = Mock()
        model.search.return_value = []
        wizard = SimpleNamespace(env={"pms.ses.communication": model})
        TravellerReport.ses_send_communications(wizard, "RH", 42)
        self.assertIn(("id", "=", 42), model.search.call_args[0][0])
        self.assertEqual(model.search.call_args[1], {"limit": 100})

    def test_room_domain_is_valid(self):
        wizard = self.env["traveller.report.wizard"]
        self.env["pms.room"].search(
            safe_eval(
                wizard._fields["room_id"].domain.strip(), {"pms_property_id": False}
            ),
            limit=1,
        )
