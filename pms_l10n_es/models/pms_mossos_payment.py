# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, fields, models


class PmsFolio(models.Model):
    _inherit = "pms.folio"

    def _mossos_receipt_order_key(self, record, event_time=False):
        """Accounting date first; creation timestamp breaks same-day ties."""
        self.ensure_one()
        timestamp = fields.Datetime.to_datetime(event_time or record.create_date)
        local_day = fields.Datetime.context_timestamp(
            self.with_context(tz=self.pms_property_id.tz or "UTC"), timestamp
        ).date()
        day = record.date if "date" in record._fields else local_day
        return (day or local_day, timestamp, record._name, record.id)

    def _mossos_payment_values(self):
        """Resolve the oldest actual receipt, independently of invoices.

        No journal/provider/payment-term inference. When the selected receipt
        has no mapped mode, use the explicitly configured establishment type.
        """
        self.ensure_one()
        transactions = self.transaction_ids.filtered(
            lambda tx: tx.state == "done" and tx.amount > 0 and tx.operation != "refund"
        )
        statements = self.statement_line_ids.filtered(
            lambda line: line.state == "posted" and line.amount > 0
        )
        payments = (
            self.payment_ids | transactions.payment_id | statements.payment_ids
        ).filtered(
            lambda pay: pay.state == "posted"
            and pay.payment_type == "inbound"
            and pay.partner_type == "customer"
            and pay.amount > 0
            and not pay.is_internal_transfer
        )
        receipts = [
            (self._mossos_receipt_order_key(pay), pay, pay.move_id.payment_mode_id)
            for pay in payments
        ]
        for line in statements:
            # A bank statement may reconcile an already counted payment.
            if not line.payment_ids & payments:
                receipts.append((
                    self._mossos_receipt_order_key(line), line,
                    line.move_id.payment_mode_id,
                ))
        for transaction in transactions:
            if transaction.payment_id not in payments:
                receipts.append((
                    self._mossos_receipt_order_key(
                        transaction, transaction.last_state_change or transaction.create_date
                    ),
                    transaction, self.env["account.payment.mode"],
                ))
        selected = min(receipts, key=lambda item: item[0]) if receipts else None
        receipt = selected[1] if selected else False
        mode = selected[2] if selected else self.env["account.payment.mode"]
        if receipt and receipt.company_id != self.company_id:
            return {
                "payment_type": False, "source": False,
                "reference": receipt.display_name,
                "error": _("The oldest receipt belongs to another company."),
            }
        mapped_type = mode.mossos_payment_type
        code = mapped_type or self.pms_property_id.mossos_default_payment_type
        return {
            "payment_type": code,
            "source": "payment" if mapped_type else "default",
            "reference": receipt.display_name if receipt else False,
            "error": False if code else _(
                "Configure a Mossos payment type on the oldest receipt's payment "
                "mode or a default in the establishment's Mossos settings."
            ),
        }
