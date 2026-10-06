/** @odoo-module **/

import PaymentScreen from "point_of_sale.PaymentScreen";
import Registries from "point_of_sale.Registries";

const PosPMSLinkPaymentScreen = (PaymentScreen) =>
    class extends PaymentScreen {
        async selectReservation() {
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
                    body: this.env._t(
                        "This operation will add all the products in the order to the reservation. RESERVATION: " +
                            newReservation.name +
                            " PARTNER : " +
                            newReservation.partner_name +
                            " ROOM: " +
                            newReservation.rooms
                    ),
                });
                if (confirmed) {
                    const methodId = self.env.pos.config.pay_on_reservation_method_id[0];
                    const payment_method = self.env.pos.payment_methods.find(
                        (method) => method.id === methodId
                    );
                    if (!payment_method || !this.addNewPaymentLine({detail: payment_method})) {
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
