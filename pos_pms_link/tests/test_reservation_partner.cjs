/* Run: node pos_pms_link/tests/test_reservation_partner.cjs */
const assert = require('assert/strict');
const fs = require('fs');
const vm = require('vm');
const path = require('path');
class PaymentScreen {}
let Screen;
vm.runInNewContext(fs.readFileSync(path.join(__dirname,
    '../static/src/js/Screens/PaymentScreen/PaymentScreen.esm.js'), 'utf8')
    .replace(/^import .*;$/gm, ''), {
    PaymentScreen,
    Registries: {Component: {extend(base, extension) {Screen = extension(base);}}},
});
(async () => {
    const screen = new Screen();
    let customer = null;
    const contact = {id: 4, name: 'Guest'};
    const loaded = new Map();
    let fetches = 0;
    let errors = 0;
    screen.currentOrder = {get_partner: () => customer, set_partner: partner => {customer = partner;}};
    screen.env = {_t: text => text, pos: {
        db: {get_partner_by_id: id => loaded.get(id)},
        _loadPartners: async ids => {fetches++; loaded.set(ids[0], contact);},
    }};
    screen.showPopup = async () => {errors++;};
    assert.equal(await screen.assignReservationPartner({partner_id: [4, 'Guest']}), true);
    assert.equal(customer, contact);
    assert.equal(fetches, 1);
    customer = null;
    assert.equal(await screen.assignReservationPartner({partner_id: [4, 'Guest']}), true);
    assert.equal(fetches, 1);
    const other = {id: 8};
    customer = other;
    await screen.assignReservationPartner({partner_id: [4, 'Guest']});
    assert.equal(customer, other);
    customer = null;
    screen.selectPartner = async () => {};
    assert.equal(await screen.assignReservationPartner({partner_id: false}), false);
    screen.selectPartner = async () => {customer = other;};
    assert.equal(await screen.assignReservationPartner({partner_id: false}), true);
    customer = null;
    screen.env.pos._loadPartners = async () => {};
    assert.equal(await screen.assignReservationPartner({partner_id: [99, 'Unavailable']}), false);
    assert.equal(customer, null);
    assert.equal(errors, 1);
    console.log('Reservation customer: loaded, fetched, preserved, manual selection and failure checks passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
