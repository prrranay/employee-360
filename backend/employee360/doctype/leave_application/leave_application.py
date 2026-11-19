import datetime
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, getdate, now_datetime

class LeaveApplication(Document):
    def validate(self):
        self.validate_employee_reference()
        self.validate_dates()
        self.validate_overlap()
        self.enforce_ownership_and_status()
        if not self.applied_at:
            self.applied_at = now_datetime()

    def validate_employee_reference(self):
        if not self.employee:
            frappe.throw(_("Employee reference is mandatory"), frappe.MandatoryError)
        if not frappe.db.exists("Employee", self.employee):
            frappe.throw(_("Employee {0} does not exist").format(self.employee), frappe.DoesNotExistError)

    def validate_dates(self):
        if not self.from_date or not self.to_date:
            frappe.throw(_("From Date and To Date are required"), frappe.MandatoryError)

        if getdate(self.to_date) < getdate(self.from_date):
            frappe.throw(_("To Date cannot be before From Date"), frappe.ValidationError)

    def validate_overlap(self):
        overlap = frappe.db.sql(
            """
            SELECT name, from_date, to_date, status FROM `tabLeave Application`
            WHERE employee = %(employee)s
              AND status IN ('Approved', 'Pending')
              AND name != %(name)s
              AND NOT (to_date < %(from_date)s OR from_date > %(to_date)s)
            LIMIT 1
            """,
            {
                "employee": self.employee,
                "name": self.name or "",
                "from_date": self.from_date,
                "to_date": self.to_date
            },
            as_dict=True
        )

        if overlap:
            frappe.throw(
                _("Overlapping leave application found ({0}) from {1} to {2} with status {3}").format(
                    overlap[0].name, overlap[0].from_date, overlap[0].to_date, overlap[0].status
                ),
                frappe.DuplicateEntryError
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
                        _("Unauthorized: You cannot submit a leave application for another employee"),
                        frappe.PermissionError
                    )
                if self.status != "Pending":
                    frappe.throw(
                        _("Unauthorized: New leave applications must be submitted with 'Pending' status"),
                        frappe.ValidationError
                    )
        else:
            old_doc = self.get_doc_before_save()
            if old_doc and old_doc.status != self.status:
                if self.status in ("Approved", "Rejected"):
                    if not is_privileged and "Manager" not in roles:
                        frappe.throw(
                            _("Unauthorized: Only an authorized manager or administrator can approve/reject leaves"),
                            frappe.PermissionError
                        )
                    if not is_privileged:
                        from employee360.api.auth_utils import assert_can_manage_employee, get_current_employee_id
                        current_emp = get_current_employee_id()
                        if current_emp == self.employee:
                            frappe.throw(
                                _("Unauthorized: You cannot approve or reject your own leave application"),
                                frappe.PermissionError
                            )
                        assert_can_manage_employee(self.employee)

    def on_update(self):
        if self.status == "Approved":
            self.update_activity_logs()

    def update_activity_logs(self):
        # Recalculate each date in range to reflect On Leave
        try:
            from employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary
        except ImportError:
            from employee360.employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary
        curr = getdate(self.from_date)
        end = getdate(self.to_date)
        while curr <= end:
            recalculate_daily_summary(self.employee, curr)
            curr += datetime.timedelta(days=1)

