import frappe
from frappe import _
from frappe.model.document import Document

class Shift(Document):
    def validate(self):
        self.validate_times()

    def validate_times(self):
        if not self.start_time or not self.end_time:
            frappe.throw(_("Start Time and End Time are required"), frappe.MandatoryError)
        
        if self.expected_working_hours and self.expected_working_hours <= 0:
            frappe.throw(_("Expected working hours must be greater than zero"), frappe.ValidationError)

