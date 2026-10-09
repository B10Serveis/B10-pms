/** @odoo-module **/
/* License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). */

import "@pms/js/reservation_list_export.esm";
import {patch, unpatch} from "@web/core/utils/patch";
import {ListController} from "@web/views/list/list_controller";
import {download} from "@web/core/network/download";

QUnit.module("PMS reservation export", (hooks) => {
    let payload = null;
    let controller = null;
    hooks.beforeEach(() => {
        patch(download, "pms.export_test", {
            _download(options) {
                payload = JSON.parse(options.data.data);
                return Promise.resolve();
            },
        });
        controller = {
            model: {
                root: {
                    resModel: "pms.reservation",
                    domain: [["state", "=", "confirm"]],
                    orderBy: [
                        {name: "checkin", asc: true},
                        {name: "name", asc: false},
                    ],
                    groupBy: [],
                },
            },
            props: {context: {allowed_company_ids: [3]}},
            env: {_t: (text) => text},
            isDomainSelected: false,
            getSelectedResIds: async () => [],
        };
    });
    hooks.afterEach(() => unpatch(download, "pms.export_test"));

    async function exportList(importCompat = false) {
        await ListController.prototype.downloadExport.call(
            controller,
            [{name: "name", label: "Reservation"}],
            importCompat,
            "xlsx"
        );
    }

    QUnit.test("exports the complete filtered domain with the current order", async (assert) => {
        await exportList();
        assert.deepEqual(payload.domain, controller.model.root.domain);
        assert.deepEqual(payload.context.pms_export_order, controller.model.root.orderBy);
        assert.deepEqual(payload.context.allowed_company_ids, [3]);
        assert.strictEqual(payload.ids, false);
        assert.notOk("pms_export_order" in controller.props.context);
    });

    QUnit.test("keeps a partial selection in its displayed order", async (assert) => {
        controller.getSelectedResIds = async () => [9, 4];
        await exportList();
        assert.deepEqual(payload.ids, [9, 4]);
    });

    QUnit.test("selecting all results is not limited to loaded IDs", async (assert) => {
        controller.isDomainSelected = true;
        controller.getSelectedResIds = async () => {
            throw new Error("Should export by domain");
        };
        await exportList();
        assert.strictEqual(payload.ids, false);
    });

    QUnit.test("preserves grouping and import-compatible exports", async (assert) => {
        controller.model.root.groupBy = ["state"];
        await exportList(true);
        assert.deepEqual(payload.groupby, ["state"]);
        assert.strictEqual(payload.import_compat, true);
        assert.strictEqual(payload.fields[0].name, "id");
    });

    QUnit.test("other models use the standard export", async (assert) => {
        controller.model.root.resModel = "res.partner";
        await exportList();
        assert.notOk("pms_export_order" in payload.context);
        assert.strictEqual(payload.model, "res.partner");
    });
});
