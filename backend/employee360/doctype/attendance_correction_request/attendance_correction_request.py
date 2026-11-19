import datetime
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate, now_datetime


class AttendanceCorrectionRequest(Document):
    def validate(self):
        self.validate_employee_reference()
        self.validate_dates_and_times()
        self.enforce_ownership_and_status()

    def validate_employee_reference(self):
        if not self.employee:
            frappe.throw(_("Employee reference is mandatory"), frappe.MandatoryError)
        if not frappe.db.exists("Employee", self.employee):
            frappe.throw(_("Employee {0} does not exist").format(self.employee), frappe.DoesNotExistError)

    def validate_dates_and_times(self):
        if not self.activity_date:
            frappe.throw(_("Activity Date is mandatory"), frappe.MandatoryError)

        if getdate(self.activity_date) > getdate(nowdate()):
            frappe.throw(_("Activity Date cannot be in the future"), frappe.ValidationError)

        if self.requested_in_time and self.requested_out_time:
            # Parse times to verify in_time < out_time
            t_in = str(self.requested_in_time)
            t_out = str(self.requested_out_time)
            if t_out <= t_in:
                frappe.throw(
                    _("Requested OUT time ({0}) must be chronologically after requested IN time ({1})").format(t_out, t_in),
                    frappe.ValidationError
                )

    def enforce_ownership_and_status(self):
        if getattr(frappe.flags, "in_seed", False):
            return

        user = frappe.session.user
        roles = frappe.get_roles(user)
        is_privileged = "CEO" in roles or "System Manager" in roles or "Administrator" in roles or user == "Administrator"

        if self.is_new():
            if not is_privileged:
                linked_emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
                if not linked_emp or linked_emp != self.employee:
                    frappe.throw(
                        _("Unauthorized: You cannot submit an attendance correction request for another employee"),
                        frappe.PermissionError
                    )
                if self.status != "Pending":
                    frappe.throw(
                        _("Unauthorized: New correction requests must be submitted with 'Pending' status"),
                        frappe.ValidationError
                    )
            # Ensure assigned_manager is populated if missing
            if not self.assigned_manager:
                manager = frappe.db.get_value("Employee", self.employee, "manager")
                self.assigned_manager = manager or "EMP-00001"
        else:
            old_doc = self.get_doc_before_save()
            if old_doc and old_doc.status != self.status:
                if self.status in ("Approved", "Rejected"):
                    if not is_privileged and "Manager" not in roles:
                        frappe.throw(
                            _("Unauthorized: Only an authorized manager or administrator can approve/reject correction requests"),
                            frappe.PermissionError
                        )
                    if not is_privileged:
                        from employee360.api.auth_utils import assert_can_manage_employee, get_current_employee_id
                        current_emp = get_current_employee_id()
                        if current_emp == self.employee:
                            frappe.throw(
                                _("Unauthorized: You cannot approve or reject your own attendance correction request"),
                                frappe.PermissionError
                            )
                        assert_can_manage_employee(self.employee)
