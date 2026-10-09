/* License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). */
// Run: node moment_locale_regression.cjs /path/to/web/static/lib/moment
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const momentDirectory = process.argv[2];
if (!momentDirectory) {
    throw new Error("Pass the Odoo web/static/lib/moment directory");
}
const momentSource = fs.readFileSync(path.join(momentDirectory, "moment.js"), "utf8");
const catalanSource = fs.readFileSync(path.join(momentDirectory, "locale/ca.js"), "utf8");
const extensionSource = fs.readFileSync(
    path.join(__dirname, "../src/js/moment_locale.js"),
    "utf8"
);

for (const loadCatalanFirst of [false, true]) {
    for (const activeLocale of ["en", "ca"]) {
        const context = vm.createContext({odoo: {define: (name, factory) => factory()}});
        vm.runInContext(momentSource, context);
        if (loadCatalanFirst) {
            vm.runInContext(catalanSource, context);
        }
        context.moment.locale(activeLocale);
        const previousLocale = context.moment.locale();
        vm.runInContext(extensionSource, context);
        assert.equal(context.moment.locale(), previousLocale);
        assert.equal(context.moment.localeData("ca")._abbr, "ca");
        context.moment.locale("ca");
        // Matches mail's MessageView.dateFromNow computation for older messages.
        assert.equal(typeof context.moment().subtract(2, "days").fromNow(), "string");
        assert.equal(typeof context.moment().add(2, "days").fromNow(), "string");
        assert.equal(context.moment.localeData("ca").preparse("2 de gener"), "2 gener");
        assert.equal(context.moment.localeData("ca").preparse("2 d’abril"), "2 abril");
        if (!loadCatalanFirst) {
            vm.runInContext(catalanSource, context);
        }
        assert.equal(context.moment().subtract(2, "days").fromNow(), "fa 2 dies");
        assert.equal(context.moment("2 de gener 2026", "D MMMM YYYY", true).isValid(), true);
    }
}
console.log("Passed: Catalan locale before/after initialization, active language, relative times and parsing");
