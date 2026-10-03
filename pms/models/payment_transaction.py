from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Command


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"
    _check_pms_properties_auto = True

    folio_ids = fields.Many2many(
        string="Folios",
        comodel_name="pms.folio",
        ondelete="cascade",
        relation="payment_transaction_folio_rel",
        column1="payment_transaction_id",
        column2="folio_id",
    )
    folio_ids_nbr = fields.Integer(
        compute="_compute_folio_ids_nbr", string="# of Folios"
    )

    def _create_payment(self, **extra_create_values):
        self.ensure_one()
        extra_create_values["folio_ids"] = [Command.set(self.folio_ids.ids)]
        return super()._create_payment(**extra_create_values)

    @api.constrains(
        "folio_ids", "invoice_ids", "provider_id", "partner_id", "currency_id", "token_id"
    )
    def _check_pms_payment_documents(self):
        for tx in self:
            properties = (
                tx.folio_ids.mapped("pms_property_id")
                | tx.invoice_ids.mapped("pms_property_id")
            )
            if not properties:
                continue
            provider = tx.provider_id
            if any(
                prop.company_id != provider.company_id
                or (provider.pms_property_ids and prop not in provider.pms_property_ids)
                for prop in properties
            ):
                raise ValidationError(
                    _("The payment provider is not available for these documents.")
                )
            if any(folio.currency_id != tx.currency_id for folio in tx.folio_ids):
                raise ValidationError(
                    _("The transaction and folios must use the same currency.")
                )
            for folio in tx.folio_ids:
                partner = folio.partner_id or self.env.ref("pms.various_pms_partner")
                if partner.commercial_partner_id != tx.partner_id.commercial_partner_id:
                    raise ValidationError(
                        _("The transaction partner does not match the folio customer.")
                    )
            if tx.token_id and (
                tx.token_id.provider_id != provider
                or tx.token_id.partner_id.commercial_partner_id
                != tx.partner_id.commercial_partner_id
                or not tx.token_id.active
            ):
                raise ValidationError(
                    _("The payment token does not match the transaction.")
                )

    @api.model
    def _compute_reference_prefix(self, provider_code, separator, **values):
        if provider_code == "redsys" and "reference" in values:
            values["reference"] = values["reference"][-8:]
        reference = super()._compute_reference_prefix(
            provider_code, separator=separator, **values
        )
        return reference

    @api.depends("folio_ids")
    def _compute_folio_ids_nbr(self):
        for trans in self:
            trans.folio_ids_nbr = len(trans.folio_ids)

    def action_view_folios(self):
        action = {
            "name": _("Folio(s)"),
            "type": "ir.actions.act_window",
            "res_model": "pms.folio",
            "target": "current",
        }
        folio_ids = self.folio_ids.ids
        if len(folio_ids) == 1:
            action["res_id"] = folio_ids[0]
            action["view_mode"] = "form"
        else:
            action["view_mode"] = "tree,form"
            action["domain"] = [("id", "in", folio_ids)]
        return action
