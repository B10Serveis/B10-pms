/** @odoo-module **/

import PaymentScreen from "point_of_sale.PaymentScreen";
import Registries from "point_of_sale.Registries";

const PosPMSLinkPaymentScreen = (PaymentScreen) =>
    class extends PaymentScreen {
        async assignReservationPartner(reservation) {
            const order = this.currentOrder;
            if (order.get_partner()) return true;
            if (!reservation.partner_id) {
                await this.selectPartner();
                return Boolean(order.get_partner());
            }
            const partnerId = reservation.partner_id[0];
            try {
                if (!this.env.pos.db.get_partner_by_id(partnerId)) {
                    await this.env.pos._loadPartners([partnerId]);
                }
                const partner = this.env.pos.db.get_partner_by_id(partnerId);
                if (!partner) throw new Error(this.env._t(
                    "The reservation customer could not be loaded. Select a customer on the ticket and try again."
                ));
                order.set_partner(partner);
                return true;
            } catch (error) {
                await this.showPopup("ErrorPopup", {
                    title: this.env._t("Unable to load reservation customer"),
                    body: (error.data && error.data.message) || error.message || String(error),
                });
                return false;
            }
        }

        async selectReservation() {
            const configured = this.env.pos.config.pay_on_reservation_method_id;
            const payment_method = this.env.pos.payment_methods.find(
                (method) => configured && method.id === configured[0]
            );
            if (!payment_method || payment_method.type !== "pay_later") {
                await this.showPopup("ErrorPopup", {
                    title: this.env._t("Reservation payment configuration"),
                    body: this.env._t(
                        "In POS settings, select a Customer Account payment method " +
                        "with Identify Customer enabled and no cash or bank journal for Pay on reservation."
                    ),
                });
                return;
            }
            if (this.currentOrder.is_to_invoice()) {
                await this.showPopup("ErrorPopup", {
                    title: this.env._t("Reservation invoicing"),
                    body: this.env._t(
                        "Turn off Invoice to charge this ticket to a reservation. " +
                        "The reservation will be invoiced from PMS."
                    ),
                });
                return;
            }
            const {confirmed, payload: newReservation} = await this.showTempScreen(
                "ReservationListScreen",
                {
                    reservation: null,
                }
            );
            if (confirmed) {
                var self = this;

                const {confirmed} = await this.showPopup("ConfirmPopup", {
                    title: this.env._t("Pay order with reservation ?"),
                    body: _.str.sprintf(this.env._t(
                        "This operation will add all the products in the order to the reservation. " +
                        "RESERVATION: %s PARTNER: %s ROOM: %s"
                    ), newReservation.name, newReservation.partner_name, newReservation.rooms),
                });
                if (confirmed) {
                    if (!await this.assignReservationPartner(newReservation)) return;
                    if (!this.addNewPaymentLine({detail: payment_method})) {
                        return;
                    }
                    this.currentOrder.set_paid_on_reservation(true);
                    this.currentOrder.set_pms_reservation_id(newReservation.id);
                    await self.validateOrder(false);
                }
            }
        }
    };

Registries.Component.extend(PaymentScreen, PosPMSLinkPaymentScreen);
