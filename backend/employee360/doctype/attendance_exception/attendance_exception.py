import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

class AttendanceException(Document):
    def validate(self):
        self.set_assigned_manager()
        self.handle_resolution()

    def set_assigned_manager(self):
        if not self.assigned_manager and self.employee:
            self.assigned_manager = frappe.db.get_value("Employee", self.employee, "manager")

    def handle_resolution(self):
        if self.status in ["Resolved", "Ignored"] and not self.resolved_at:
            self.resolved_at = now_datetime()
            self.resolved_by = frappe.session.user

