/* License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). */
odoo.define("pms.ReservationTimelineView", function (require) {
    "use strict";

    const TimelineView = require("web_timeline.TimelineView");
    const TimelineRenderer = require("web_timeline.TimelineRenderer");
    const viewRegistry = require("web.view_registry");

    const ReservationTimelineRenderer = TimelineRenderer.extend({
        template: "pms.ReservationTimeline",
        init: function (parent, state, params) {
            this._super.apply(this, arguments);
            const labels = new Map(this.fields.state.selection);
            this.stateLegend = this.colors
                .filter((color) => color.field === "state")
                .map((color) => ({
                    value: color.value,
                    label: labels.get(color.value),
                    color: color.color,
                }));
        },
    });

    const ReservationTimelineView = TimelineView.extend({
        config: Object.assign({}, TimelineView.prototype.config, {
            Renderer: ReservationTimelineRenderer,
        }),
        init: function () {
            this._super.apply(this, arguments);
            // TimelineView disables the panel after AbstractView creates it.
            // Restore it only when the search view and action allow a panel.
            this.withSearchPanel = Boolean(this.controllerParams.searchPanel);
        },
    });

    viewRegistry.add("pms_reservation_timeline", ReservationTimelineView);
    return ReservationTimelineView;
});
