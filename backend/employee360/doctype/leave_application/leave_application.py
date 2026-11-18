import datetime
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, getdate, now_datetime

class LeaveApplication(Document):
    def validate(self):
        self.validate_dates()
        self.validate_overlap()
        if not self.applied_at:
            self.applied_at = now_datetime()

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

