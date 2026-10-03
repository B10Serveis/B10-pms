from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.http import Response
from odoo.tests import tagged

from odoo.addons.account_payment.controllers.portal import (
    PortalAccount as AccountPortal,
)
from odoo.addons.account_payment.models.payment_transaction import (
    PaymentTransaction as AccountPaymentTransaction,
)
from odoo.addons.payment import utils as payment_utils
from odoo.addons.pms.controllers.pms_portal import (
    PaymentPortal,
    PortalAccount,
    PortalFolio,
)

from .test_pms_portal_security import TestPmsPortalSecurity


@tagged("post_install", "-at_install")
class TestPmsOnlinePayment(TestPmsPortalSecurity):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folio = cls.own_folios[0]
        cls.other_property = cls.env["pms.property"].create(
            {
                "name": "Other payment property",
                "company_id": cls.company1.id,
                "default_pricelist_id": cls.pricelist1.id,
            }
        )
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Online payment test bank",
                "code": "OPTB",
                "type": "bank",
                "company_id": cls.company1.id,
            }
        )
        cls.providers = cls.env["payment.provider"]
        for name, properties in (
            ("Allowed", cls.pms_property1),
            ("Shared", cls.env["pms.property"]),
            ("Excluded", cls.other_property),
        ):
            cls.providers |= cls.env["payment.provider"].create(
                {
                    "name": name,
                    "code": "none",
                    "state": "test",
                    "is_published": True,
                    "company_id": cls.company1.id,
                    "journal_id": cls.journal.id,
                    "pms_property_ids": [(6, 0, properties.ids)],
                }
            )
        cls.provider, cls.shared_provider, cls.excluded_provider = cls.providers
        cls.tokens = cls.env["payment.token"]
        for provider in cls.providers:
            cls.tokens |= cls.env["payment.token"].create(
                {
                    "provider_id": provider.id,
                    "provider_ref": "test-only-token",
                    "partner_id": cls.contact.id,
                    "payment_details": "Test card",
                }
            )
        cls.token = cls.tokens[0]
        cls.foreign_token = cls.env["payment.token"].create(
            {
                "provider_id": cls.provider.id,
                "provider_ref": "foreign-test-token",
                "partner_id": cls.other_customer.id,
            }
        )

    @contextmanager
    def _request(self, user=None):
        fake = SimpleNamespace(
            env=self.env(user=user or self.portal_user),
            session={},
            render=lambda template, values: Response(
                "Test payment page", qcontext=values
            ),
        )
        with ExitStack() as stack:
            for module in (
                "pms.controllers.pms_portal",
                "portal.controllers.portal",
                "payment.controllers.portal",
                "payment.controllers.post_processing",
                "payment.utils",
            ):
                stack.enter_context(patch(f"odoo.addons.{module}.request", fake))
            yield fake

    def _transaction_values(self, **kwargs):
        values = {
            "payment_option_id": self.provider.id,
            "reference_prefix": "PMS-ONLINE-TEST",
            "amount": self.folio.pending_amount,
            "currency_id": self.folio.currency_id.id,
            "partner_id": self.contact.id,
            "flow": "redirect",
            "tokenization_requested": False,
            "landing_route": "/my",
        }
        values.update(kwargs)
        return values

    def test_folio_payment_context_filters_providers_and_tokens(self):
        controller = PortalFolio()
        with self._request(), patch.object(
            controller,
            "_get_page_view_values",
            side_effect=lambda doc, token, values, *a, **kw: values,
        ):
            values = controller._folio_get_page_view_values(self.folio, None)
        self.assertEqual(
            set(values["providers"].ids),
            set((self.provider | self.shared_provider).ids),
        )
        self.assertEqual(set(values["tokens"].ids), set(self.tokens[:2].ids))
        self.assertEqual(values["partner_id"], self.contact.id)
        self.assertEqual(values["amount"], self.folio.pending_amount)

    def test_public_context_does_not_expose_saved_cards(self):
        self.token.partner_id = self.customer
        controller = PortalFolio()
        with self._request(self.env.ref("base.public_user")), patch.object(
            controller,
            "_get_page_view_values",
            side_effect=lambda doc, token, values, *a, **kw: values,
        ):
            values = controller._folio_get_page_view_values(
                self.folio, self.folio._portal_ensure_token()
            )
        self.assertFalse(values["tokens"])
        self.assertTrue(values["existing_token"])
        self.assertFalse(any(values["show_tokenize_input"].values()))

    def test_invoice_context_filters_tokens_fees_and_tokenization(self):
        invoice = SimpleNamespace(pms_property_id=self.pms_property1)
        parent_values = {
            "providers": self.providers,
            "tokens": self.tokens,
            "fees_by_provider": {provider: 1 for provider in self.providers},
            "show_tokenize_input": {provider.id: True for provider in self.providers},
        }
        with self._request(), patch.object(
            AccountPortal, "_invoice_get_page_view_values", return_value=parent_values
        ):
            values = PortalAccount()._invoice_get_page_view_values(invoice, None)
        self.assertEqual(set(values["tokens"].ids), set(self.tokens[:2].ids))
        self.assertNotIn(self.excluded_provider, values["fees_by_provider"])
        self.assertNotIn(self.excluded_provider.id, values["show_tokenize_input"])

    def test_folio_route_uses_url_id_and_document_values(self):
        with self._request():
            values = PaymentPortal().portal_folio_transaction(
                self.folio.id,
                pms_folio_id=self.other_folio.id,
                **self._transaction_values(
                    currency_id=0, partner_id=self.other_customer.id
                ),
            )
        tx = self.env["payment.transaction"].search(
            [("reference", "=", values["reference"])]
        )
        self.assertEqual(tx.folio_ids, self.folio)
        self.assertEqual(tx.currency_id, self.folio.currency_id)
        self.assertEqual(tx.partner_id, self.contact)

    def test_folio_route_rejects_foreign_documents(self):
        with self._request(), self.assertRaises(ValidationError):
            PaymentPortal().portal_folio_transaction(
                self.other_folio.id, **self._transaction_values()
            )

    def test_token_flow_calls_odoo16_payment_request(self):
        with self._request(), patch.object(
            type(self.env["payment.transaction"]), "_send_payment_request"
        ) as send:
            tx = PaymentPortal()._create_transaction(
                pms_folio_id=self.folio.id,
                **self._transaction_values(
                    payment_option_id=self.token.id, flow="token"
                ),
            )
        send.assert_called_once()
        self.assertEqual(tx.operation, "online_token")
        self.assertEqual(tx.token_id, self.token)
        self.assertEqual(tx.folio_ids, self.folio)

    def test_incompatible_payment_inputs_are_rejected(self):
        for changes in (
            {"payment_option_id": self.excluded_provider.id},
            {"payment_option_id": self.tokens[2].id, "flow": "token"},
            {"payment_option_id": self.foreign_token.id, "flow": "token"},
            {"amount": self.folio.pending_amount + 1},
            {"amount": -1},
            {"amount": float("nan")},
            {"currency_id": self.env.ref("base.USD").id},
            {"partner_id": self.other_customer.id},
            {"is_validation": True},
        ):
            with self.subTest(changes=changes), self._request():
                with self.assertRaises(
                    AccessError
                    if changes.get("payment_option_id") == self.foreign_token.id
                    else ValidationError
                ):
                    PaymentPortal()._create_transaction(
                        pms_folio_id=self.folio.id,
                        **self._transaction_values(**changes),
                    )

    def test_public_token_payment_is_rejected(self):
        with self._request(self.env.ref("base.public_user")), self.assertRaises(
            AccessError
        ):
            PaymentPortal()._create_transaction(
                pms_folio_id=self.folio.id,
                **self._transaction_values(
                    payment_option_id=self.token.id, flow="token"
                ),
            )

    def test_payment_link_keeps_property_filter(self):
        with self._request():
            token = payment_utils.generate_access_token(
                self.customer.id, self.folio.pending_amount, self.folio.currency_id.id
            )
            response = PaymentPortal.payment_pay.__wrapped__(
                PaymentPortal(),
                amount=self.folio.pending_amount,
                pms_folio_id=self.folio.id,
                access_token=token,
            )
        values = response.qcontext
        self.assertNotIn(self.excluded_provider, values["providers"])
        self.assertEqual(values["pms_folio_id"], self.folio.id)

    def test_backend_transaction_uses_token_provider_and_pending_amount(self):
        with patch.object(
            type(self.env["payment.transaction"]), "_send_payment_request"
        ) as send:
            tx = self.folio._create_payment_transaction({"token_id": self.token.id})
        send.assert_called_once()
        self.assertEqual(tx.provider_id, self.provider)
        self.assertEqual(tx.amount, self.folio.pending_amount)
        self.assertEqual(tx.operation, "offline")
        self.assertEqual(tx.token_id, self.token)

    def test_backend_rejects_foreign_or_incompatible_tokens(self):
        for token in (self.foreign_token, self.tokens[2]):
            with self.subTest(token=token.id), self.assertRaises(ValidationError):
                self.folio._create_payment_transaction({"token_id": token.id})

    def test_redirect_form_uses_transaction_processing_api(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "Test payment redirect",
                "type": "qweb",
                "arch": '<t><form action="/test-payment-redirect"/></t>',
            }
        )
        self.provider.redirect_form_view_id = view
        with self._request():
            values = PaymentPortal().portal_folio_transaction(
                self.folio.id, **self._transaction_values()
            )
        self.assertIn("/test-payment-redirect", values["redirect_form_html"])

    def test_generic_payment_link_transaction_keeps_folio(self):
        with self._request():
            values = self._transaction_values()
            token = payment_utils.generate_access_token(
                values["partner_id"], values["amount"], values["currency_id"]
            )
            processing = PaymentPortal().payment_transaction(
                pms_folio_id=self.folio.id, access_token=token, **values
            )
        tx = self.env["payment.transaction"].search(
            [("reference", "=", processing["reference"])]
        )
        self.assertEqual(tx.folio_ids, self.folio)
        self.assertIn("access_token=", tx.landing_route)

    def test_invoice_transaction_rejects_provider_from_other_property(self):
        journal = self.env["account.journal"].create(
            {
                "name": "Test online invoices",
                "code": "OPTS",
                "type": "sale",
                "company_id": self.company1.id,
            }
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "journal_id": journal.id,
                "partner_id": self.customer.id,
                "pms_property_id": self.pms_property1.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["payment.transaction"].create(
                {
                    "provider_id": self.excluded_provider.id,
                    "partner_id": self.customer.id,
                    "amount": 1,
                    "currency_id": self.folio.currency_id.id,
                    "invoice_ids": [(6, 0, invoice.ids)],
                }
            )

    def test_account_payment_receives_folio_commands_and_extra_values(self):
        tx = self.folio._create_payment_transaction({"provider_id": self.provider.id})
        with patch.object(AccountPaymentTransaction, "_create_payment") as create:
            tx._create_payment(ref="Custom payment reference")
        create.assert_called_once_with(
            ref="Custom payment reference", folio_ids=[(6, 0, self.folio.ids)]
        )

    def test_posted_payment_links_folio_and_reduces_pending_balance(self):
        receivable = self.env["account.account"].create(
            {
                "name": "Online test receivable",
                "code": "OPTREC",
                "account_type": "asset_receivable",
                "reconcile": True,
                "company_id": self.company1.id,
            }
        )
        outstanding = self.env["account.account"].create(
            {
                "name": "Online test outstanding",
                "code": "OPTOUT",
                "account_type": "asset_current",
                "reconcile": True,
                "company_id": self.company1.id,
            }
        )
        self.customer.with_company(
            self.company1
        ).property_account_receivable_id = receivable
        method = self.journal.inbound_payment_method_line_ids[0]
        method.write(
            {
                "payment_provider_id": self.provider.id,
                "payment_account_id": outstanding.id,
            }
        )
        balance = self.folio.pending_amount
        tx = self.folio._create_payment_transaction({"provider_id": self.provider.id})
        tx.amount = balance / 2
        payment = tx.with_company(self.company1)._create_payment()
        self.assertEqual(payment.state, "posted")
        self.assertEqual(payment.folio_ids, self.folio)
        self.assertEqual(payment.amount, balance / 2)
        self.assertEqual(self.folio.pending_amount, balance / 2)
        remaining_tx = self.folio._create_payment_transaction(
            {"provider_id": self.provider.id}
        )
        self.assertEqual(remaining_tx.amount, balance / 2)
