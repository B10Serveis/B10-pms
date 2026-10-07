/** @odoo-module **/

/*
##############################################################################
#    License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
#    Copyright (C) 2022 Comunitea Servicios Tecnológicos S.L. All Rights Reserved
#    Vicente Ángel Gutiérrez <vicente@comunitea.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
*/

import Registries from "point_of_sale.Registries";
import {Order, Orderline, PosGlobalState} from "point_of_sale.models";

const PosPmsGlobalState = (PosGlobalState) =>
    class extends PosGlobalState {
        constructor(obj) {
            super(obj);
        }

        // @override
        async _processData(loadedData) {
            await super._processData(...arguments);
            if (this.config.pay_on_reservation) {
                this.reservations = loadedData["pms.reservation"] || [];
                this.loadPmsReservation();
                this.addReservations(this.reservations);
            }
        }

        loadPmsReservation() {
            if (this.config.pay_on_reservation) {
                this.reservations_by_id = {};
                this.services_by_id = {};
                for (const reservation of this.reservations) {
                    this.reservations_by_id[reservation.id] = reservation;
                    for (const service of reservation.services) {
                        this.services_by_id[service.id] = service;
                        service.reservation = reservation;
                    }
                }
            }
        }

        async refreshReservations(domain = []) {
            let timeoutId;
            const timeout = new Promise((resolve, reject) => {
                timeoutId = setTimeout(() => reject(
                    new Error(this.env._t("Reservation loading timed out. Please try again."))
                ), 10000);
            });
            let reservations;
            try {
                reservations = await Promise.race([
                    this.env.services.rpc({
                        model: "pos.session",
                        method: "get_pos_ui_pms_reservation_by_params",
                        args: [[this.pos_session.id], {domain}],
                    }),
                    timeout,
                ]);
            } finally {
                clearTimeout(timeoutId);
            }
            if (!Array.isArray(reservations)) {
                throw new Error(this.env._t("Invalid reservation response from the server."));
            }
            this.addReservations(reservations);
            return reservations;
        }

        async _loadReservations(reservationIds) {
            if (reservationIds.length > 0) {
                return this.refreshReservations([["id", "in", reservationIds]]);
            }
            return [];
        }

        addReservations(reservations) {
            // Preserve local quantities while refreshing the server snapshot.
            for (const reservation of reservations) {
                const previous = this.db.get_reservation_by_id(reservation.id);
                const pendingByLine = new Map();
                for (const service of (previous && previous.services) || []) {
                    for (const line of service.service_lines) {
                        pendingByLine.set(line.id, line.pos_order_lines.filter(
                            (item) => item.client_id && !item.id
                        ));
                    }
                }
                for (const service of reservation.services || []) {
                    for (const line of service.service_lines) {
                        line.pos_order_lines.push(...(pendingByLine.get(line.id) || []));
                    }
                }
            }
            const count = this.db.add_reservations(reservations);
            this.reservations = this.db.get_reservations_sorted();
            this.loadPmsReservation();
            return count;
        }

    };

Registries.Model.extend(PosGlobalState, PosPmsGlobalState);

const PosPmsOrder = (Order) =>
    class extends Order {
        constructor(obj, options) {
            super(obj, options);
            this.paid_on_reservation = this.paid_on_reservation || null;
            this.pms_reservation_id = this.pms_reservation_id || null;
        }

        get_paid_on_reservation() {
            return this.paid_on_reservation;
        }

        set_paid_on_reservation(value) {
            this.paid_on_reservation = value;
        }

        get_pms_reservation_id() {
            return this.pms_reservation_id;
        }

        set_pms_reservation_id(value) {
            this.pms_reservation_id = value;
        }

        export_as_JSON() {
            var json = super.export_as_JSON();
            json.paid_on_reservation = this.paid_on_reservation;
            json.pms_reservation_id = this.pms_reservation_id;
            return json;
        }

        init_from_JSON(json) {
            super.init_from_JSON(json);
            this.paid_on_reservation = json.paid_on_reservation;
            this.pms_reservation_id = json.pms_reservation_id;
        }

        apply_ms_data(data) {
            if (typeof data.paid_on_reservation !== "undefined") {
                this.set_paid_on_reservation(data.paid_on_reservation);
            }
            if (typeof data.pms_reservation_id !== "undefined") {
                this.set_pms_reservation_id(data.pms_reservation_id);
            }
            this.trigger("change", this);
        }

        async add_reservation_services(reservation) {
            const date = new Date();
            const today = [date.getFullYear(),
                String(date.getMonth() + 1).padStart(2, "0"),
                String(date.getDate()).padStart(2, "0")].join("-");
            const pending = [];
            for (const service of reservation.services || []) {
                for (const line of service.service_lines) {
                    if (line.date !== today) continue;
                    const quantity = line.day_qty - line.pos_order_lines.reduce(
                        (total, item) => total + item.qty, 0
                    );
                    if (quantity > 0) pending.push({line, quantity});
                }
            }
            const missingIds = [...new Set(pending
                .map(({line}) => line.product_id && line.product_id[0])
                .filter((id) => id && !this.pos.db.get_product_by_id(id)))];
            if (missingIds.length) {
                // Fetch through Odoo's product loader without changing availability.
                await this.pos._addProducts(missingIds, false);
            }
            // Validate everything before adding any line to the order.
            const unavailable = pending.filter(({line}) =>
                !line.product_id || !this.pos.db.get_product_by_id(line.product_id[0])
            );
            if (unavailable.length) {
                throw new Error(this.pos.env._t(
                    "These reservation products could not be loaded in POS: "
                ) + unavailable.map(({line}) =>
                    line.product_id ? line.product_id[1] : String(line.id)
                ).join(", "));
            }
            for (const {line, quantity} of pending) {
                this.add_product(this.pos.db.get_product_by_id(line.product_id[0]), {
                    quantity,
                    merge: false,
                    pms_service_line_id: line.id,
                    price: 0.0,
                });
                const lastLine = this.get_last_orderline();
                if (lastLine) {
                    lastLine.set_note(
                        this.pos.env._t("RESERVATION:") + " " + reservation.name + " " +
                        this.pos.env._t("ROOMS:") + " " + reservation.rooms
                    );
                }
            }
        }

        add_product(product, options) {
            super.add_product(...arguments);
            if (options && options.pms_service_line_id) {
                this.selected_orderline.set_pms_service_line_id(
                    options.pms_service_line_id
                );
            }
        }

        remove_paymentline(line) {
            const result = super.remove_paymentline(...arguments);
            const configured = this.pos.config.pay_on_reservation_method_id;
            const hasReservationPayment = configured && this.get_paymentlines().some(
                (payment) => payment.payment_method.id === configured[0]
            );
            if (this.paid_on_reservation && !hasReservationPayment) {
                this.set_paid_on_reservation(false);
                this.set_pms_reservation_id(false);
            }
            return result;
        }

        export_for_printing() {
            var res = super.export_for_printing();
            res.paid_on_reservation = this.paid_on_reservation;
            res.pms_reservation_id = this.pms_reservation_id;
            return res;
        }
    };

Registries.Model.extend(Order, PosPmsOrder);

const PosPmsOrderline = (Orderline) =>
    class extends Orderline {
        constructor(obj, options) {
            super(obj, options);
            this.server_id = this.server_id || null;
            this.pms_service_line_id = this.pms_service_line_id || null;
        }

        get_pms_service_line_id() {
            return this.pms_service_line_id;
        }

        set_pms_service_line_id(value) {
            this.pms_service_line_id = value;
            this._update_service_quantity(this.get_quantity());
        }

        _update_service_quantity(quantity) {
            for (const reservation of this.pos.reservations || []) {
                for (const service of reservation.services) {
                    for (const line of service.service_lines) {
                        if (line.id !== this.pms_service_line_id) continue;
                        const index = line.pos_order_lines.findIndex(
                            (item) => item.client_id === this.cid ||
                                (this.server_id && item.id === this.server_id)
                        );
                        if (quantity === "remove" || Number(quantity) === 0) {
                            if (index !== -1) line.pos_order_lines.splice(index, 1);
                        } else if (index !== -1) {
                            line.pos_order_lines[index].qty = Number(quantity);
                        } else {
                            line.pos_order_lines.push({
                                id: this.server_id || 0,
                                client_id: this.cid,
                                qty: Number(quantity),
                            });
                        }
                    }
                }
            }
        }

        export_as_JSON() {
            var json = super.export_as_JSON();
            json.pms_service_line_id = this.pms_service_line_id;
            json.server_id = this.server_id;
            return json;
        }

        init_from_JSON(json) {
            super.init_from_JSON(json);
            this.pms_service_line_id = json.pms_service_line_id;
            this.server_id = json.server_id || null;
        }

        apply_ms_data(data) {
            if (typeof data.pms_service_line_id !== "undefined") {
                this.set_pms_service_line_id(data.pms_service_line_id);
            }
            this.trigger("change", this);
        }

        set_quantity(quantity, keep_price) {
            const result = super.set_quantity(quantity, keep_price);
            if (result !== false && this.pms_service_line_id) {
                this._update_service_quantity(
                    quantity === "remove" ? "remove" : this.get_quantity()
                );
            }
            return result;
        }

    };

Registries.Model.extend(Orderline, PosPmsOrderline);
