/* global moment */
/* License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). */

// Replace web.moment.extensions, retaining Odoo's Catalan parsing fix.
odoo.define("web.moment.extensions", function () {
    "use strict";

    const locale = moment.locale();
    moment.updateLocale("ca", {
        // Moment 2.19 does not add this when updateLocale creates a locale.
        // Without it, fromNow() calls duration.locale(undefined).humanize().
        abbr: "ca",
        preparse: function (string) {
            return string.replace(
                /\b(?:d’|de )(gener|febrer|març|abril|maig|juny|juliol|agost|setembre|octubre|novembre|desembre)/g,
                "$1"
            );
        },
    });
    if (locale !== "ca") {
        moment.locale(locale);
    }
});
