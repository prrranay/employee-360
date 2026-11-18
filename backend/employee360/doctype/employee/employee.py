import frappe
from frappe import _
from frappe.model.document import Document

class Employee(Document):
    def validate(self):
        self.validate_employee_id()
        self.validate_manager()

    def validate_employee_id(self):
        if not self.employee_id:
            frappe.throw(_("Employee ID is required"), frappe.MandatoryError)
        
        # Check uniqueness if name is not yet set or differs
        existing = frappe.db.get_value("Employee", {"employee_id": self.employee_id}, "name")
        if existing and existing != self.name:
            frappe.throw(_("Employee ID {0} already exists").format(self.employee_id), frappe.DuplicateEntryError)

    def validate_manager(self):
        manager = self.get("manager")
        if not manager:
            return  # Support employees without assigned managers (e.g., CEO)

        emp_id = self.get("employee_id")
        emp_name = self.get("name")

        # An employee cannot be their own manager
        if manager == emp_name or (emp_id and manager == emp_id):
            frappe.throw(_("An employee cannot be their own manager"), frappe.ValidationError)

        # Manager must reference a valid employee
        if not frappe.db.exists("Employee", manager):
            frappe.throw(_("Manager {0} does not exist").format(manager), frappe.DoesNotExistError)

        # Prevent circular manager relationships
        current_manager = manager
        visited = {emp_name, emp_id} if emp_id else {emp_name}
        
        display_label = self.get("employee_name") or emp_name or "Employee"
        while current_manager:
            if current_manager in visited:
                frappe.throw(
                    _("Circular manager relationship detected: {0} cannot be managed by {1}").format(
                        display_label, manager
                    ),
                    frappe.ValidationError
                )
            visited.add(current_manager)
            current_manager = frappe.db.get_value("Employee", current_manager, "manager")
