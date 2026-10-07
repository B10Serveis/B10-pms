/* Run: node pos_pms_link/tests/test_frontend.cjs */
const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const path = require('path');
const extensions = new Map();
class Order {
    get_paymentlines() {return this.payments;}
    remove_paymentline(line) {this.payments = this.payments.filter(item => item !== line);}
    add_product(product, options) { this.selected_orderline = {set_pms_service_line_id(id) { this.id = id; }}; }
}
class Orderline {
    get_quantity() {return this.quantity;}
    set_quantity(quantity) {this.quantity = quantity === 'remove' ? 0 : Number(quantity); return true;}
}
class PosGlobalState {}
const context = {
    Order, Orderline, PosGlobalState, setTimeout, clearTimeout, console,
    Registries: {Model: {extend(base, extension) {extensions.set(base, extension(base));}}},
};
const source = fs.readFileSync(path.join(__dirname, '../static/src/js/models.esm.js'), 'utf8')
    .replace(/^import .*;$/gm, '');
vm.runInNewContext(source, context);
const ExtendedOrder = extensions.get(Order);
const order = new ExtendedOrder();
assert.doesNotThrow(() => order.add_product({id: 1}));
order.add_product({id: 1}, {pms_service_line_id: 23});
assert.equal(order.selected_orderline.id, 23);
const paymentOrder = new ExtendedOrder();
const reservationPayment = {payment_method: {id: 7}};
const cardPayment = {payment_method: {id: 8}};
paymentOrder.pos = {config: {pay_on_reservation_method_id: [7, 'Reservation']}};
paymentOrder.payments = [reservationPayment, cardPayment];
paymentOrder.set_paid_on_reservation(true);
paymentOrder.set_pms_reservation_id(4);
paymentOrder.remove_paymentline(cardPayment);
assert.equal(paymentOrder.get_paid_on_reservation(), true);
paymentOrder.remove_paymentline(reservationPayment);
assert.equal(paymentOrder.get_paid_on_reservation(), false);
assert.equal(paymentOrder.get_pms_reservation_id(), false);
const ExtendedLine = extensions.get(Orderline);
const serviceLine = {id: 23, pos_order_lines: [{id: 99, qty: 1}]};
const posForLines = {reservations: [{services: [{service_lines: [serviceLine]}]}]};
const firstLine = new ExtendedLine();
Object.assign(firstLine, {pos: posForLines, cid: 'first', quantity: 0.5});
firstLine.set_pms_service_line_id(23);
const secondLine = new ExtendedLine();
Object.assign(secondLine, {pos: posForLines, cid: 'second', quantity: 0.25});
secondLine.set_pms_service_line_id(23);
assert.equal(serviceLine.pos_order_lines.length, 3);
assert.equal(serviceLine.pos_order_lines[1].qty, 0.5);
firstLine.set_quantity('remove');
assert.equal(serviceLine.pos_order_lines.length, 2);
assert.equal(serviceLine.pos_order_lines[0].id, 99);
secondLine.set_quantity(0.75);
assert.equal(serviceLine.pos_order_lines[1].qty, 0.75);
// Exercise the actual reservation database patch, including local search.
function PosDB() {this.init({});}
PosDB.prototype.init = function () {this.limit = 100;};
context.PosDB = PosDB;
context.unaccent = (value) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
context.patch = (prototype, name, methods) => {
    for (const [key, method] of Object.entries(methods)) {
        const previous = prototype[key];
        prototype[key] = function (...args) {
            this._super = previous && previous.bind(this);
            return method.apply(this, args);
        };
    }
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/src/js/db.esm.js'), 'utf8')
    .replace(/^import .*;$/gm, ''), context);
let startHook;
let ReservationScreen;
context.PosComponent = class {setup() {}};
context.debounce = (method) => Object.assign(method, {cancel() {}});
context.onMounted = (callback) => {startHook = callback;};
context.onWillUnmount = () => {};
context.useRef = () => ({});
context.useAutofocus = () => {};
context.useListener = () => {};
context.useAsyncLockedMethod = (method) => method;
context.isConnectionError = () => false;
context.Registries.Component = {add(component) {ReservationScreen = component;}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,
    '../static/src/js/Screens/ReservationListScreen/ReservationListScreen.esm.js'), 'utf8')
    .replace(/^import .*;$/gm, ''), context);
(async () => {
    const serviceOrder = new ExtendedOrder();
    const products = new Map([[1, {id: 1}]]);
    const additions = [];
    const now = new Date();
    const today = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'),
        String(now.getDate()).padStart(2, '0')].join('-');
    const reservation = {name: 'RES/1', rooms: '101', services: [{service_lines: [
        {id: 1, date: today, day_qty: 1, pos_order_lines: [], product_id: [1, 'Loaded']},
        {id: 2, date: today, day_qty: 0.5, pos_order_lines: [], product_id: [2, 'Missing']},
    ]}]};
    serviceOrder.pos = {
        env: {_t: text => text},
        db: {get_product_by_id: id => products.get(id)},
        _addProducts: async (ids, setAvailable) => {
            assert.equal(setAvailable, false);
            assert.equal(ids[0], 2);
        },
    };
    serviceOrder.add_product = (product, options) => additions.push({product, options});
    serviceOrder.get_last_orderline = () => ({set_note() {}});
    await assert.rejects(serviceOrder.add_reservation_services(reservation), /Missing/);
    assert.equal(additions.length, 0);
    serviceOrder.pos._addProducts = async (ids, setAvailable) => {
        assert.equal(setAvailable, false);
        products.set(2, {id: 2});
    };
    await serviceOrder.add_reservation_services(reservation);
    assert.equal(additions.length, 2);
    assert.equal(additions[1].product.id, 2);
    assert.equal(additions[1].options.quantity, 0.5);
    const pos = new (extensions.get(PosGlobalState))();
    let calls = 0;
    pos.config = {pay_on_reservation: true};
    pos.pos_session = {id: 1};
    pos.db = new PosDB();
    pos.env = {_t: (text) => text, services: {rpc: async (request) => {
        calls++;
        assert.equal(request.args[0][0], 1);
        return [{id: 4, name: 'RES/4', rooms: '101', partner_name: 'Júlia',
            services: [{id: 10, service_lines: [{id: 23, pos_order_lines: []}]}]}];
    }}};
    assert.equal(pos.db.get_reservations_sorted().length, 0);
    const screen = new ReservationScreen();
    screen.env = {pos, _t: (text) => text};
    screen.render = () => {};
    screen.props = {reservation: null};
    screen.setup();
    startHook();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(screen.reservations.length, 1);
    screen.state.query = 'Julia';
    assert.equal(screen.reservations[0].id, 4);
    assert.equal(calls, 1);
    assert.equal(pos.db.get_reservations_sorted().length, 1);
    assert.equal(pos.db.search_reservation('Julia')[0].id, 4);
    assert.equal(pos.db.search_reservation('101')[0].id, 4);
    assert.equal(pos.reservations_by_id[4].name, 'RES/4');
    // Reloading must preserve fractional quantities of unsaved POS lines.
    pos.reservations[0].services[0].service_lines[0].pos_order_lines.push(
        {id: 0, client_id: 'pending', qty: 0.5}
    );
    await pos._loadReservations([]);
    assert.equal(calls, 1);
    await pos._loadReservations([4]);
    assert.equal(calls, 2);
    assert.equal(pos.reservations[0].services[0].service_lines[0].pos_order_lines[0].qty, 0.5);
    assert.equal(pos.db.get_reservations_sorted().length, 1);
    // A rejected RPC must leave a mounted selector and an actionable error.
    pos.env.services.rpc = async () => {throw new Error('Loader failed');};
    const previousError = context.console.error;
    context.console.error = () => {};
    try {
        await screen.refreshReservations();
        assert.equal(screen.state.isLoading, false);
        assert.match(screen.state.loadError, /Loader failed/);
        assert.equal(screen.reservations.length, 1);
        pos.env.services.rpc = async () => ({unexpected: true});
        await screen.refreshReservations();
        assert.equal(screen.state.isLoading, false);
        assert.match(screen.state.loadError, /Invalid reservation response/);
        // Simulate the timeout without waiting ten seconds in the test.
        context.setTimeout = (callback) => {queueMicrotask(callback); return 0;};
        context.clearTimeout = () => {};
        pos.env.services.rpc = () => new Promise(() => {});
        await screen.refreshReservations();
        assert.equal(screen.state.isLoading, false);
        assert.match(screen.state.loadError, /timed out/);
        context.setTimeout = setTimeout;
        context.clearTimeout = clearTimeout;
    } finally {
        context.console.error = previousError;
    }
    console.log('Frontend: product, quantity, refresh and reservation search regressions passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
