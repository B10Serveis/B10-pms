from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMossosPayment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env["res.company"].create({"name": "Mossos accounting tests"})
        cls.env.user.company_ids |= company
        cls.env = cls.env["res.company"].with_company(company).env
        accounts = {}
        for key, code, account_type, reconcile in [
            ("receivable", "430000", "asset_receivable", True),
            ("payable", "400000", "liability_payable", True),
            ("bank", "572000", "asset_cash", False),
            ("cash", "570000", "asset_cash", False),
            ("suspense", "555000", "asset_current", True),
            ("receipts", "572100", "asset_current", True),
            ("payments", "572200", "asset_current", True),
        ]:
            accounts[key] = cls.env["account.account"].create({
                "name": key, "code": code, "account_type": account_type,
                "reconcile": reconcile, "company_id": company.id,
            })
        company.write({
            "account_journal_payment_debit_account_id": accounts["receipts"].id,
            "account_journal_payment_credit_account_id": accounts["payments"].id,
        })
        cls.company_data = {}
        for key in ["bank", "cash"]:
            cls.company_data["default_journal_" + key] = cls.env["account.journal"].create({
                "name": key, "code": key.upper(), "type": key,
                "company_id": company.id, "default_account_id": accounts[key].id,
                "suspense_account_id": accounts["suspense"].id,
            })
        cls.partner_a = cls.env["res.partner"].create({
            "name": "Mossos payment customer",
            "property_account_receivable_id": accounts["receivable"].id,
            "property_account_payable_id": accounts["payable"].id,
        })
        cls.env.user.groups_id |= cls.env.ref("pms.group_pms_manager")
        plan = cls.env["pms.availability.plan"].create({"name": "Mossos payment plan"})
        pricelist = cls.env["product.pricelist"].create({
            "name": "Mossos payment prices", "availability_plan_id": plan.id,
            "is_pms_available": True,
        })
        cls.hotel = cls.env["pms.property"].create({
            "name": "Mossos payment property", "company_id": cls.env.company.id,
            "default_pricelist_id": pricelist.id, "mossos_enabled": True,
            "tz": "Europe/Madrid",
        })
        cls.env.user.pms_property_ids |= cls.hotel
        cls.bank = cls.company_data["default_journal_bank"]
        cls.cash = cls.company_data["default_journal_cash"]
        cls.method = cls.bank.inbound_payment_method_line_ids[0]
        cls.method.allowed_on_pms = True
        cls.cash_mode = cls._mode("Cash mapping", "EFECT")
        cls.card_mode = cls._mode("Card mapping", "TARJT")
        cls.provider = cls.env["payment.provider"].create({
            "name": "Mossos online test", "code": "none", "state": "test",
            "company_id": cls.env.company.id, "journal_id": cls.bank.id,
            "pms_property_ids": [(6, 0, cls.hotel.ids)],
        })

    @classmethod
    def _mode(cls, name, code=False, journal=None):
        journal = journal or cls.bank
        return cls.env["account.payment.mode"].create({
            "name": name, "company_id": cls.env.company.id,
            "bank_account_link": "fixed", "fixed_journal_id": journal.id,
            "payment_method_id": journal.inbound_payment_method_line_ids[0].payment_method_id.id,
            "mossos_payment_type": code,
        })

    def setUp(self):
        super().setUp()
        self.folio = self.env["pms.folio"].create({
            "pms_property_id": self.hotel.id, "partner_id": self.partner_a.id,
        })

    def _payment(self, mode=False, date="2026-01-02", posted=True, outbound=False):
        method = self.bank.outbound_payment_method_line_ids[0] if outbound else self.method
        payment = self.env["account.payment"].create({
            "journal_id": self.bank.id, "payment_method_line_id": method.id,
            "payment_type": "outbound" if outbound else "inbound",
            "partner_type": "customer", "partner_id": self.partner_a.id,
            "amount": 50, "date": date, "folio_ids": [(6, 0, self.folio.ids)],
            "payment_mode_id": mode.id if mode else False,
        })
        if posted:
            payment.action_post()
        return payment

    def _transaction(self, payment=False):
        return self.env["payment.transaction"].create({
            "provider_id": self.provider.id, "reference": "MOSSOS-TX",
            "partner_id": self.partner_a.id, "amount": 50,
            "currency_id": self.env.company.currency_id.id,
            "operation": "online_direct", "state": "done",
            "last_state_change": "2026-01-01 10:00:00",
            "folio_ids": [(6, 0, self.folio.ids)],
            "payment_id": payment.id if payment else False,
        })

    def test_missing_default_is_visible(self):
        result = self.folio._mossos_payment_values()
        self.assertFalse(result["payment_type"])
        self.assertIn("Configure a Mossos payment type", result["error"])

    def test_default_without_receipt_or_invoice(self):
        self.hotel.mossos_default_payment_type = "DESTI"
        result = self.folio._mossos_payment_values()
        self.assertEqual(result["payment_type"], "DESTI")
        self.assertEqual(result["source"], "default")
        self.assertFalse(result["error"])
        self.assertFalse(self.folio.move_ids)
        self.assertFalse(self.folio.payment_ids)

    def test_oldest_payment_date_wins_for_mixed_payments(self):
        self.hotel.mossos_default_payment_type = "PLATF"
        self._payment(self.card_mode, "2026-01-03")
        older = self._payment(self.cash_mode, "2026-01-02")
        result = self.folio._mossos_payment_values()
        self.assertEqual(result["payment_type"], "EFECT")
        self.assertEqual(result["source"], "payment")
        self.assertEqual(result["reference"], older.display_name)

    def test_same_day_uses_creation_timestamp(self):
        first = self._payment(self.cash_mode)
        older = self._payment(self.card_mode)
        for record, timestamp in [(first, "2026-01-03 10:00:00"), (older, "2026-01-03 09:00:00")]:
            self.cr.execute("UPDATE account_payment SET create_date=%s WHERE id=%s", (timestamp, record.id))
            record.invalidate_recordset(["create_date"])
        self.assertEqual(self.folio._mossos_payment_values()["payment_type"], "TARJT")

    def test_unmapped_oldest_uses_default_before_later_mapping(self):
        self.hotel.mossos_default_payment_type = "TRANS"
        self._payment(False, "2026-01-01")
        self._payment(self.card_mode, "2026-01-02")
        result = self.folio._mossos_payment_values()
        self.assertEqual(result["payment_type"], "TRANS")
        self.assertEqual(result["source"], "default")

    def test_mode_without_mapping_uses_default(self):
        self.hotel.mossos_default_payment_type = "TREG"
        self._payment(self._mode("No mapping"))
        self.assertEqual(self.folio._mossos_payment_values()["payment_type"], "TREG")

    def test_draft_cancelled_and_refund_are_ignored(self):
        self.hotel.mossos_default_payment_type = "DESTI"
        self._payment(self.cash_mode, posted=False)
        cancelled = self._payment(self.card_mode)
        cancelled.action_cancel()
        self._payment(outbound=True)
        self.assertEqual(self.folio._mossos_payment_values()["payment_type"], "DESTI")

    def test_statement_receipt_uses_explicit_mode(self):
        self.env["account.bank.statement.line"].create({
            "journal_id": self.cash.id, "amount": 75, "payment_ref": "Cash receipt",
            "partner_id": self.partner_a.id, "date": "2026-01-01",
            "folio_ids": [(6, 0, self.folio.ids)],
            "payment_mode_id": self._mode("Cash journal mapping", "EFECT", self.cash).id,
        })
        self.assertEqual(self.folio._mossos_payment_values()["payment_type"], "EFECT")

    def test_statement_linked_payment_is_not_counted_twice(self):
        payment = self._payment(self.cash_mode)
        self.env["account.bank.statement.line"].create({
            "journal_id": self.bank.id, "amount": 50, "payment_ref": "Reconciliation",
            "partner_id": self.partner_a.id, "date": "2026-01-01",
            "folio_ids": [(6, 0, self.folio.ids)],
            "payment_ids": [(6, 0, payment.ids)], "payment_mode_id": self.card_mode.id,
        })
        self.assertEqual(self.folio._mossos_payment_values()["payment_type"], "EFECT")

    def test_done_transaction_without_payment_uses_default(self):
        self.hotel.mossos_default_payment_type = "PLATF"
        self._transaction()
        result = self.folio._mossos_payment_values()
        self.assertEqual(result["payment_type"], "PLATF")
        self.assertEqual(result["source"], "default")

    def test_done_transaction_uses_linked_account_payment(self):
        self.hotel.mossos_default_payment_type = "PLATF"
        self._transaction(self._payment(self.card_mode))
        self.assertEqual(self.folio._mossos_payment_values()["payment_type"], "TARJT")

    def test_pms_wizard_assigns_mode_to_created_receipt(self):
        wizard = self.env["wizard.payment.folio"].create({
            "folio_id": self.folio.id, "journal_id": self.bank.id,
            "payment_method_line_id": self.method.id, "amount": 50,
            "partner_id": self.partner_a.id, "payment_mode_id": self.card_mode.id,
        })
        wizard.button_payment()
        self.assertEqual(len(self.folio.payment_ids), 1)
        self.assertEqual(self.folio.payment_ids.payment_mode_id, self.card_mode)
        self.assertEqual(self.folio._mossos_payment_values()["payment_type"], "TARJT")

    def test_pms_wizard_rejects_incompatible_mode(self):
        wizard = self.env["wizard.payment.folio"].create({
            "folio_id": self.folio.id, "journal_id": self.bank.id,
            "payment_method_line_id": self.method.id, "amount": 50,
            "partner_id": self.partner_a.id,
            "payment_mode_id": self._mode("Wrong journal", "EFECT", self.cash).id,
        })
        with self.assertRaises(ValidationError):
            wizard.button_payment()
        self.assertFalse(self.folio.payment_ids)
