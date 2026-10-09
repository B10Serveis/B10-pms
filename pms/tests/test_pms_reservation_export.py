# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import datetime
import io
import json
from types import SimpleNamespace
from unittest.mock import patch

import openpyxl

from odoo.addons.web.controllers import export
from odoo.tests import tagged

from .common import TestPms


@tagged("post_install", "-at_install")
class TestPmsReservationExport(TestPms):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        room_type = cls.env["pms.room.type"].create(
            {
                "name": "Export room type",
                "default_code": "EXPORT",
                "class_id": cls.room_type_class1.id,
                "pms_property_ids": [(6, 0, cls.pms_property1.ids)],
            }
        )
        room = cls.env["pms.room"].create(
            {
                "name": "Export room",
                "room_type_id": room_type.id,
                "pms_property_id": cls.pms_property1.id,
                "capacity": 2,
            }
        )
        partner = cls.env["res.partner"].create({"name": "Export guest"})
        channel = cls.env["pms.sale.channel"].create(
            {"name": "Export direct", "channel_type": "direct"}
        )
        cls.reservations = cls.env["pms.reservation"]
        for code, day, adults in (("C", 5, 1), ("A", 1, 2), ("B", 3, 1)):
            checkin = datetime.date(2040, 1, day)
            cls.reservations |= cls.env["pms.reservation"].create(
                {
                    "name": "EXPORT-" + code,
                    "partner_id": partner.id,
                    "checkin": checkin,
                    "checkout": checkin + datetime.timedelta(days=1),
                    "adults": adults,
                    "preferred_room_id": room.id,
                    "room_type_id": room_type.id,
                    "pms_property_id": cls.pms_property1.id,
                    "sale_channel_origin_id": channel.id,
                }
            )
        cls.domain = [("id", "in", cls.reservations.ids)]

    def _xlsx_names(self, order=None, domain=None, ids=False, groupby=None):
        params = {
            "model": "pms.reservation",
            "fields": [{"name": "name", "label": "Reservation"}],
            "ids": ids,
            "domain": self.domain if domain is None else domain,
            "import_compat": False,
            "groupby": groupby or [],
            "context": {"pms_export_order": order or []},
        }
        request = SimpleNamespace(
            env=self.env,
            httprequest=SimpleNamespace(environ={"REMOTE_ADDR": "127.0.0.1"}),
            make_response=lambda data, headers: data,
        )
        with patch.object(export, "request", request):
            data = export.ExcelExport().base(json.dumps(params))
        workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
        try:
            return [
                row[0]
                for row in workbook.active.iter_rows(values_only=True)
                if isinstance(row[0], str) and row[0].startswith("EXPORT-")
            ]
        finally:
            workbook.close()

    def test_xlsx_respects_filters_and_both_sort_directions(self):
        for asc, expected in (
            (True, ["EXPORT-B", "EXPORT-C"]),
            (False, ["EXPORT-C", "EXPORT-B"]),
        ):
            with self.subTest(ascending=asc):
                self.assertEqual(
                    self._xlsx_names(
                        order=[{"name": "checkin", "asc": asc}],
                        domain=self.domain + [("adults", "=", 1)],
                    ),
                    expected,
                )

    def test_selected_ids_keep_their_order(self):
        self.assertEqual(
            self._xlsx_names(
                order=[{"name": "checkin", "asc": True}],
                ids=[self.reservations[0].id, self.reservations[2].id],
            ),
            ["EXPORT-C", "EXPORT-B"],
        )

    def test_multiple_sort_columns(self):
        self.assertEqual(
            self._xlsx_names(
                order=[
                    {"name": "adults", "asc": True},
                    {"name": "checkin", "asc": False},
                ]
            ),
            ["EXPORT-C", "EXPORT-B", "EXPORT-A"],
        )

    def test_grouped_xlsx_orders_records_inside_groups(self):
        self.assertEqual(
            self._xlsx_names(
                order=[{"name": "checkin", "asc": True}], groupby=["adults"]
            ),
            ["EXPORT-B", "EXPORT-C", "EXPORT-A"],
        )

    def test_group_sort_field_need_not_be_exported(self):
        self.assertEqual(
            self._xlsx_names(
                order=[{"name": "adults", "asc": False}], groupby=["adults"]
            )[0],
            "EXPORT-A",
        )

    def test_normal_search_and_explicit_order_are_preserved(self):
        model = self.env["pms.reservation"]
        self.assertEqual(
            self._xlsx_names(), model.search(self.domain).mapped("name")
        )
        exporting = model.with_context(
            pms_export_order=[{"name": "checkin", "asc": True}]
        )
        self.assertEqual(
            exporting.search(self.domain, order="checkin desc").mapped("name"),
            ["EXPORT-C", "EXPORT-B", "EXPORT-A"],
        )
