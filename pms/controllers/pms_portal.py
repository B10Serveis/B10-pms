import math

from odoo import _, http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.fields import Command
from odoo.http import request

from odoo.addons.account_payment.controllers.portal import PortalAccount
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.controllers import portal as payment_portal
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager


class PortalFolio(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        partner = request.env.user.partner_id
        values = super()._prepare_home_portal_values(counters)
        Folio = request.env["pms.folio"]
        if "folio_count" in counters:
            values["folio_count"] = (
                Folio.search_count(
                    [
                        ("partner_id", "child_of", partner.commercial_partner_id.id),
                    ]
                )
                if Folio.check_access_rights("read", raise_exception=False)
                else 0
            )
        return values

    def _folio_get_page_view_values(self, folio, access_token, **kwargs):
        logged_in = not request.env.user._is_public()
        partner = request.env.user.partner_id if logged_in else folio.partner_id
        partner = partner or request.env.ref("pms.various_pms_partner")
        providers = request.env["payment.provider"].sudo()._get_compatible_providers(
            folio.company_id.id,
            partner.id,
            folio.pending_amount,
            currency_id=folio.currency_id.id,
            pms_property_id=folio.pms_property_id.id,
        )
        if not payment_portal.PaymentPortal._can_partner_pay_in_company(
            partner, folio.company_id
        ):
            providers = providers.browse([])
        tokens = request.env["payment.token"].sudo().search(
            [("provider_id", "in", providers.ids), ("partner_id", "=", partner.id)]
        )
        values = {
            "folio": folio,
            "token": access_token,
            "providers": providers,
            "tokens": tokens if logged_in else tokens.browse([]),
            "existing_token": bool(tokens) if not logged_in else False,
            "fees_by_provider": {
                provider: provider._compute_fees(
                    folio.pending_amount, folio.currency_id, partner.country_id
                )
                for provider in providers.filtered("fees_active")
            },
            "show_tokenize_input": (
                payment_portal.PaymentPortal._compute_show_tokenize_input_mapping(
                    providers, logged_in=logged_in
                )
            ),
            "amount": folio.pending_amount,
            "currency": folio.currency_id,
            "partner_id": partner.id,
            "access_token": access_token,
            "transaction_route": f"/my/folios/{folio.id}/transaction",
            "landing_route": folio.get_portal_url(),
        }
        return self._get_page_view_values(
            folio, access_token, values, "my_folios_history", False, **kwargs
        )

    @http.route(
        ["/my/folios", "/my/folios/page/<int:page>"],
        type="http",
        auth="public",
        website=True,
    )
    def portal_my_folios(
        self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw
    ):
        partner = request.env.user.partner_id
        values = self._prepare_portal_layout_values()
        PmsFolio = request.env["pms.folio"]
        values["folios"] = PmsFolio.search(
            [
                ("partner_id", "child_of", partner.commercial_partner_id.id),
            ]
        )
        domain = [
            ("partner_id", "child_of", partner.commercial_partner_id.id),
        ]
        searchbar_sortings = {
            "date": {"label": _("Order Date"), "folio": "date_order desc"},
            "name": {"label": _("Reference"), "folio": "name"},
            "stage": {"label": _("Stage"), "folio": "state"},
        }
        if not sortby:
            sortby = "date"
        sort_order = searchbar_sortings[sortby]["folio"]

        if date_begin and date_end:
            domain += [
                ("create_date", ">", date_begin),
                ("create_date", "<=", date_end),
            ]
        folio_count = PmsFolio.search_count(domain)
        pager = portal_pager(
            url="/my/folios",
            url_args={"date_begin": date_begin, "date_end": date_end, "sortby": sortby},
            total=folio_count,
            page=page,
            step=self._items_per_page,
        )
        folios = PmsFolio.search(
            domain, order=sort_order, limit=self._items_per_page, offset=pager["offset"]
        )
        request.session["my_folios_history"] = folios.ids[:100]
        values.update(
            {
                "date": date_begin,
                "folios": folios.sudo(),
                "page_name": "folios",
                "pager": pager,
                "default_url": "/my/folios",
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
            }
        )
        return request.render("pms.portal_my_folio", values)

    @http.route(["/my/folios/<int:folio_id>"], type="http", auth="public", website=True)
    def portal_my_folio_detail(
        self, folio_id, access_token=None, report_type=None, download=False, **kw
    ):
        try:
            folio_sudo = self._document_check_access(
                "pms.folio",
                folio_id,
                access_token=access_token,
            )
        except (AccessError, MissingError):
            return request.redirect("/my")
        if report_type in ("html", "pdf", "text"):
            return self._show_report(
                model=folio_sudo,
                report_type=report_type,
                report_ref="pms.action_report_folio",
                download=download,
            )
        backend_url = (
            f"/web#model={folio_sudo._name}"
            f"&id={folio_sudo.id}"
            f"&action={folio_sudo._get_portal_return_action().id}"
            f"&view_type=form"
        )
        values = {
            "folio": folio_sudo,
            "message": "",
            "report_type": "html",
            "backend_url": backend_url,
            "res_company": folio_sudo.company_id,
        }
        values.update(self._folio_get_page_view_values(folio_sudo, access_token, **kw))
        if "custom_amount" in kw:
            values["custom_amount"] = float(kw["custom_amount"])
        return request.render("pms.folio_portal_template", values)


class PaymentPortal(payment_portal.PaymentPortal):
    @http.route("/my/folios/<int:folio_id>/transaction", type="json", auth="public")
    def portal_folio_transaction(self, folio_id, access_token=None, **kwargs):
        """Create a transaction for an accessible folio using Odoo 16 payment inputs."""
        try:
            folio = self._document_check_access("pms.folio", folio_id, access_token)
        except AccessError as error:
            raise ValidationError(_("The access token is invalid.")) from error
        logged_in = not request.env.user._is_public()
        partner = request.env.user.partner_id if logged_in else folio.partner_id
        partner = partner or request.env.ref("pms.various_pms_partner")
        kwargs.update(
            reference_prefix=None,
            currency_id=folio.currency_id.id,
            partner_id=partner.id,
            pms_folio_id=folio.id,
            is_validation=False,
            landing_route=folio.get_portal_url(),
        )
        kwargs.pop("custom_create_values", None)
        tx = self._create_transaction(
            custom_create_values={"folio_ids": [Command.set(folio.ids)]}, **kwargs
        )
        return tx._get_processing_values()

    # Payment overrides

    @http.route()
    def payment_pay(
        self, *args, amount=None, pms_folio_id=None, access_token=None, **kwargs
    ):
        """Override of payment to replace the missing transaction values
        by that of the folio.

        This is necessary for the reconciliation as all transaction values,
        excepted the amount, need to match exactly that of the folio.

        :param str amount: The (possibly partial) amount to pay used
        to check the access token
        :param str pms_folio_id: The folio for which a payment id made,
        as a `pms.folio` id
        :param str access_token: The access token used to authenticate the partner
        :return: The result of the parent method
        :rtype: str
        :raise: ValidationError if the order id is invalid
        """
        # Cast numeric parameters as int or float and void them if their
        # str value is malformed
        amount = self._cast_as_float(amount)
        pms_folio_id = self._cast_as_int(pms_folio_id)
        if pms_folio_id:
            folio_sudo = request.env["pms.folio"].sudo().browse(pms_folio_id).exists()
            if not folio_sudo:
                raise ValidationError(_("The provided parameters are invalid."))

            # Check the access token against the order values.
            # Done after fetching the order as we
            # need the order fields to check the access token.
            if not payment_utils.check_access_token(
                access_token,
                (
                    folio_sudo.partner_id.id
                    if folio_sudo.partner_id
                    else request.env.ref("pms.various_pms_partner").id
                ),
                amount,
                folio_sudo.currency_id.id,
            ):
                raise ValidationError(_("The provided parameters are invalid."))

            kwargs.update(
                {
                    "currency_id": folio_sudo.currency_id.id,
                    "partner_id": (
                        folio_sudo.partner_id.id
                        if folio_sudo.partner_id
                        else request.env.ref("pms.various_pms_partner").id
                    ),
                    "company_id": folio_sudo.company_id.id,
                    "pms_folio_id": pms_folio_id,
                    "pms_property_id": folio_sudo.pms_property_id.id,
                }
            )
        return super().payment_pay(
            *args, amount=amount, access_token=access_token, **kwargs
        )

    def _get_custom_rendering_context_values(self, pms_folio_id=None, **kwargs):
        """Pass the folio ID to the Odoo 16 checkout form."""
        rendering_context_values = super()._get_custom_rendering_context_values(
            pms_folio_id=pms_folio_id, **kwargs
        )
        if pms_folio_id:
            rendering_context_values["pms_folio_id"] = pms_folio_id

        return rendering_context_values

    def _create_transaction(
        self,
        payment_option_id,
        reference_prefix,
        amount,
        currency_id,
        partner_id,
        flow,
        tokenization_requested,
        landing_route,
        is_validation=False,
        custom_create_values=None,
        pms_folio_id=None,
        **kwargs,
    ):
        if pms_folio_id:
            amount = self._cast_as_float(amount)
            folio = request.env["pms.folio"].sudo().browse(int(pms_folio_id)).exists()
            partner = request.env["res.partner"].sudo().browse(partner_id).exists()
            folio_partner = folio.partner_id or request.env.ref(
                "pms.various_pms_partner"
            )
            if (
                not folio
                or not partner
                or partner.commercial_partner_id != folio_partner.commercial_partner_id
                or currency_id != folio.currency_id.id
                or is_validation
                or folio.state == "cancel"
                or not amount
                or not math.isfinite(amount)
                or folio.currency_id.compare_amounts(amount, 0) <= 0
                or folio.currency_id.compare_amounts(amount, folio.pending_amount) > 0
            ):
                raise ValidationError(_("The provided payment parameters are invalid."))
            if flow == "token":
                if request.env.user._is_public():
                    raise AccessError(_("Sign in to pay with a saved payment method."))
                token = (
                    request.env["payment.token"].sudo()
                    .browse(payment_option_id).exists()
                )
                if not token or not token.active:
                    raise ValidationError(_("The payment token is invalid."))
                provider = token.provider_id
            else:
                provider = (
                    request.env["payment.provider"].sudo().browse(payment_option_id)
                )
            compatible = (
                request.env["payment.provider"].sudo()._get_compatible_providers(
                    folio.company_id.id,
                    partner_id,
                    amount,
                    currency_id=currency_id,
                    pms_property_id=folio.pms_property_id.id,
                )
            )
            if provider not in compatible:
                raise ValidationError(
                    _("The payment provider is not available for this folio.")
                )
            custom_create_values = dict(custom_create_values or {})
            custom_create_values["folio_ids"] = [Command.set(folio.ids)]
            if request.env.user._is_public():
                tokenization_requested = False
        return super()._create_transaction(
            payment_option_id,
            reference_prefix,
            amount,
            currency_id,
            partner_id,
            flow,
            tokenization_requested,
            landing_route,
            is_validation=is_validation,
            custom_create_values=custom_create_values,
            **kwargs,
        )


class PortalReservation(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        partner = request.env.user.partner_id
        values = super()._prepare_home_portal_values(counters)
        Reservation = request.env["pms.reservation"]
        if "reservation_count" in counters:
            values["reservation_count"] = (
                Reservation.search_count(
                    [
                        ("partner_id", "child_of", partner.commercial_partner_id.id),
                    ]
                )
                if Reservation.check_access_rights("read", raise_exception=False)
                else 0
            )
        return values

    def _reservation_get_page_view_values(self, reservation, access_token, **kwargs):
        values = {"reservation": reservation, "token": access_token}
        return self._get_page_view_values(
            reservation,
            access_token,
            values,
            "my_reservations_history",
            False,
            **kwargs,
        )

    @http.route(
        ["/my/reservations", "/my/reservations/page/<int:page>"],
        type="http",
        auth="public",
        website=True,
    )
    def portal_my_reservations(self, page=1, date_begin=None, date_end=None):
        partner = request.env.user.partner_id
        values = self._prepare_portal_layout_values()
        Reservation = request.env["pms.reservation"]
        values["reservations"] = Reservation.search(
            [
                ("partner_id", "child_of", partner.commercial_partner_id.id),
            ]
        )
        domain = [
            ("partner_id", "child_of", partner.commercial_partner_id.id),
        ]
        if date_begin and date_end:
            domain += [
                ("create_date", ">", date_begin),
                ("create_date", "<=", date_end),
            ]
        reservation_count = Reservation.search_count(domain)
        pager = portal_pager(
            url="/my/reservations",
            url_args={"date_begin": date_begin, "date_end": date_end},
            total=reservation_count,
            page=page,
            step=self._items_per_page,
        )
        reservations = Reservation.search(
            domain, limit=self._items_per_page, offset=pager["offset"]
        )
        folios_dict = {}
        for reservation in reservations:
            folio = reservation.folio_id
            folios_dict[folio] = ""

        request.session["my_reservations_history"] = reservations.ids[:100]
        values.update(
            {
                "date": date_begin,
                "reservations": reservations.sudo(),
                "page_name": "reservations",
                "pager": pager,
                "default_url": "/my/reservations",
                "folios_dict": folios_dict,
                "partner": partner,
            }
        )
        return request.render("pms.portal_my_reservation", values)

    @http.route(
        ["/my/reservations/<int:reservation_id>"],
        type="http",
        auth="public",
        website=True,
    )
    def portal_my_reservation_detail(self, reservation_id, access_token=None, **kw):
        try:
            reservation_sudo = self._document_check_access(
                "pms.reservation",
                reservation_id,
                access_token=access_token,
            )
        except (AccessError, MissingError):
            return request.redirect("/my")
        values = self._reservation_get_page_view_values(
            reservation_sudo, access_token, **kw
        )
        return request.render("pms.portal_my_reservation_detail", values)


class PortalAccount(PortalAccount):
    @http.route(
        ["/my/invoices/proforma/<int:invoice_id>"],
        type="http",
        auth="public",
        website=True,
    )
    def portal_proforma_my_invoice_detail(
        self, invoice_id, access_token=None, report_type=None, download=False, **kw
    ):
        try:
            invoice_sudo = self._document_check_access(
                "account.move", invoice_id, access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        if report_type in ("html", "pdf", "text"):
            return self._show_report(
                model=invoice_sudo,
                report_type=report_type,
                report_ref="pms.action_report_pms_pro_forma_invoice",
                download=download,
            )

        invoice_sudo = invoice_sudo.with_context(proforma=True)
        values = self._invoice_get_page_view_values(invoice_sudo, access_token, **kw)
        return request.render("pms.pms_proforma_invoice_template", values)

    def _invoice_get_page_view_values(self, invoice, access_token, **kwargs):
        """
        Override to add the pms property filter
        """
        values = super()._invoice_get_page_view_values(invoice, access_token, **kwargs)
        providers = values.get("providers")
        if providers is not None:
            providers = providers.filtered(
                lambda provider: not provider.pms_property_ids
                or invoice.pms_property_id in provider.pms_property_ids
            )
            values["providers"] = providers
            values["tokens"] = values.get(
                "tokens", request.env["payment.token"]
            ).filtered(
                lambda token: token.provider_id in providers
            )
            values["fees_by_provider"] = {
                provider: fee
                for provider, fee in values.get("fees_by_provider", {}).items()
                if provider in providers
            }
            values["show_tokenize_input"] = {
                provider_id: show
                for provider_id, show in values.get("show_tokenize_input", {}).items()
                if provider_id in providers.ids
            }
            if request.env.user._is_public():
                values["existing_token"] = bool(
                    request.env["payment.token"].sudo().search_count([
                        ("provider_id", "in", providers.ids),
                        ("partner_id", "=", invoice.partner_id.id),
                    ])
                )
        return values
