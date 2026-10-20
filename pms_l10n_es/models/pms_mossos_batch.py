# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import _, fields, models
from odoo.exceptions import AccessError, ValidationError


class PmsMossosBatch(models.Model):
    _name = "pms.mossos.batch"
    _description = "Mossos generated traveller file"
    _rec_name = "filename"
    _order = "generated_at desc, id desc"

    pms_property_id = fields.Many2one("pms.property", required=True, readonly=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True, readonly=True, ondelete="restrict")
    filename = fields.Char(required=True, readonly=True)
    file_data = fields.Binary(required=True, readonly=True, attachment=False)
    file_encoding = fields.Char(default="UTF-8", required=True, readonly=True)
    file_number = fields.Integer(required=True, readonly=True)
    generated_at = fields.Datetime(required=True, readonly=True)
    generated_by = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    arrival_day = fields.Date(required=True, readonly=True)
    traveller_count = fields.Integer(required=True, readonly=True)
    line_ids = fields.One2many("pms.mossos.batch.line", "batch_id", readonly=True)
    state = fields.Selection([
        ("generated", "Generated — awaiting submission"),
        ("presented", "Manually confirmed as submitted"),
        ("cancelled", "Cancelled before submission"),
    ], default="generated", required=True, readonly=True)
    presented_at = fields.Datetime(readonly=True)
    presented_by = fields.Many2one("res.users", readonly=True, ondelete="restrict")
    receipt_file = fields.Binary(string="Submission receipt", attachment=False)
    receipt_filename = fields.Char(string="Receipt filename")
    cancellation_reason = fields.Text()

    def write(self, vals):
        if set(vals) - {"receipt_file", "receipt_filename", "cancellation_reason"}:
            raise AccessError(_("Generated Mossos files and their traveller snapshots cannot be changed."))
        if "cancellation_reason" in vals and any(batch.state != "generated" for batch in self):
            raise ValidationError(_("The cancellation reason can only be edited before submission."))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_("Mossos file history cannot be deleted. Cancel an unsubmitted file instead."))

    def _check_staff_access(self, operation="read"):
        self.ensure_one()
        if not self.env.user.has_group("pms.group_pms_user"):
            raise AccessError(_("Only PMS staff can manage Mossos files."))
        self.check_access_rights(operation)
        self.check_access_rule(operation)

    def action_download(self):
        self._check_staff_access()
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content?model=pms.mossos.batch&id=%s&field=file_data&filename_field=filename&download=true" % self.id,
            "target": "self",
        }

    def action_confirm_presented(self):
        self._check_staff_access("write")
        if self.state != "generated":
            raise ValidationError(_("Only a generated file can be confirmed as submitted."))
        return super(PmsMossosBatch, self).write({
            "state": "presented", "presented_at": fields.Datetime.now(),
            "presented_by": self.env.user.id,
        })

    def action_cancel(self):
        self._check_staff_access("write")
        if self.state != "generated" or not (self.cancellation_reason or "").strip():
            raise ValidationError(_("Only an unsubmitted file can be cancelled; enter a reason."))
        # Keep the snapshot and membership history; release the stay for correction.
        return super(PmsMossosBatch, self).write({"state": "cancelled"})


class PmsMossosBatchLine(models.Model):
    _name = "pms.mossos.batch.line"
    _description = "Mossos exported traveller snapshot"
    _order = "id"

    batch_id = fields.Many2one("pms.mossos.batch", required=True, readonly=True, ondelete="cascade")
    checkin_partner_id = fields.Many2one("pms.checkin.partner", required=True, readonly=True, ondelete="restrict")
    firstname = fields.Char(readonly=True)
    lastname = fields.Char(readonly=True)
    document_number = fields.Char(readonly=True)
    record_data = fields.Text(required=True, readonly=True)

    _sql_constraints = [(
        "batch_guest_unique", "unique(batch_id, checkin_partner_id)",
        "A traveller can only appear once in a Mossos file.",
    )]


class PmsCheckinPartner(models.Model):
    _inherit = "pms.checkin.partner"

    mossos_batch_line_ids = fields.One2many("pms.mossos.batch.line", "checkin_partner_id", readonly=True)
