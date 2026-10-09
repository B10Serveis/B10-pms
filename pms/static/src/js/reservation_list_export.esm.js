/** @odoo-module **/
/* License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). */

import {ListController} from "@web/views/list/list_controller";
import {download} from "@web/core/network/download";
import {patch} from "@web/core/utils/patch";

patch(ListController.prototype, "pms.reservation_list_export", {
    async downloadExport(fields, importCompat, format) {
        const root = this.model.root;
        if (root.resModel !== "pms.reservation") {
            return this._super(...arguments);
        }

        let ids = false;
        if (!this.isDomainSelected) {
            const selectedIds = await this.getSelectedResIds();
            ids = selectedIds.length > 0 && selectedIds;
        }
        const exportedFields = fields.map((field) => ({
            name: field.name || field.id,
            label: field.label || field.string,
            store: field.store,
            type: field.field_type || field.type,
        }));
        if (importCompat) {
            exportedFields.unshift({name: "id", label: this.env._t("External ID")});
        }
        return download({
            url: `/web/export/${format}`,
            data: {
                data: JSON.stringify({
                    import_compat: importCompat,
                    context: {
                        ...this.props.context,
                        pms_export_order: root.orderBy,
                    },
                    domain: root.domain,
                    fields: exportedFields,
                    groupby: root.groupBy,
                    ids,
                    model: root.resModel,
                }),
            },
        });
    },
});
