/** @odoo-module **/

import PosComponent from "point_of_sale.PosComponent";
import ProductScreen from "point_of_sale.ProductScreen";
import Registries from "point_of_sale.Registries";

class ReservationSelectionButton extends PosComponent {
    get currentOrder() {
        return this.env.pos.get_order();
    }

    async onClick() {
        const {confirmed, payload: newReservation} = await this.showTempScreen(
            "ReservationListScreen",
            {reservation: null}
        );
        if (confirmed) {
            try {
                await this.currentOrder.add_reservation_services(newReservation);
            } catch (error) {
                await this.showPopup("ErrorPopup", {
                    title: this.env._t("Unable to add reservation services"),
                    body: (error.data && error.data.message) || error.message || String(error),
                });
            }
        }
    }
}

ReservationSelectionButton.template = "ReservationSelectionButton";

ProductScreen.addControlButton({
    component: ReservationSelectionButton,
    condition: function () {
        return this.env.pos.config.pay_on_reservation;
    },
});

Registries.Component.add(ReservationSelectionButton);
