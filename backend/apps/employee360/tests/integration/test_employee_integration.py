import os
import sys
import unittest
import uuid
import datetime

# Setup path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
APP_DIR = os.path.join(BACKEND_DIR, "apps", "employee360")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import frappe_bridge
frappe_bridge.install_frappe_compat()
import frappe
from employee360.employee360.doctype.employee.employee import Employee

class TestEmployeeIntegration(unittest.TestCase):
    def setUp(self):
        self.created_employees = []

    def tearDown(self):
        # Cleanup any test employees created
        if self.created_employees:
            names = "', '".join(self.created_employees)
            frappe.db.sql(f"DELETE FROM `tabEmployee` WHERE `name` IN ('{names}');")

    def test_employee_creation_and_fields(self):
        """Test employee creation with all required fields."""
        emp_id = f"TEST-EMP-{uuid.uuid4().hex[:6]}"
        doc = Employee({
            "doctype": "Employee",
            "name": emp_id,
            "employee_id": emp_id,
            "employee_name": "Test Engineer",
            "department": "Engineering",
            "designation": "Software Engineer",
            "date_of_joining": "2024-01-15",
            "employment_status": "Active",
            "shift": "General Shift"
        })
        doc.validate()
        doc.insert()
        self.created_employees.append(emp_id)

        # Verify persisted
        db_emp = frappe.db.sql(
            "SELECT employee_id, employee_name, department, designation, employment_status FROM `tabEmployee` WHERE name = %s",
            (emp_id,),
            as_dict=True
        )
        self.assertTrue(len(db_emp) == 1)
        self.assertEqual(db_emp[0]["employee_id"], emp_id)
        self.assertEqual(db_emp[0]["employee_name"], "Test Engineer")
        self.assertEqual(db_emp[0]["department"], "Engineering")
        self.assertEqual(db_emp[0]["employment_status"], "Active")

    def test_unique_employee_ids(self):
        """Test unique employee IDs: Duplicate employee ID must be rejected."""
        # Alex Mercer EMP-00001 already exists
        doc = Employee({
            "doctype": "Employee",
            "name": f"TEST-DUP-{uuid.uuid4().hex[:6]}",
            "employee_id": "EMP-00001",
            "employee_name": "Duplicate Mercer",
            "department": "Executive"
        })
        with self.assertRaises(frappe.DuplicateEntryError):
            doc.validate_employee_id()

    def test_manager_validation_valid_manager(self):
        """Test valid manager reference in tabEmployee."""
        emp_id = f"TEST-EMP-{uuid.uuid4().hex[:6]}"
        doc = Employee({
            "doctype": "Employee",
            "name": emp_id,
            "employee_id": emp_id,
            "employee_name": "Team Member",
            "manager": "EMP-00001",  # Alex Mercer (CEO) exists
            "department": "Engineering"
        })
        # Should validate without error
        doc.validate_manager()

    def test_manager_validation_nonexistent_manager(self):
        """Test manager reference must point to a real employee."""
        emp_id = f"TEST-EMP-{uuid.uuid4().hex[:6]}"
        doc = Employee({
            "doctype": "Employee",
            "name": emp_id,
            "employee_id": emp_id,
            "employee_name": "Ghost Manager Member",
            "manager": "EMP-NONEXISTENT-99999",
            "department": "Engineering"
        })
        with self.assertRaises(frappe.DoesNotExistError):
            doc.validate_manager()

    def test_prevention_of_self_management(self):
        """Test rule: An employee cannot be their own manager."""
        emp_id = f"TEST-EMP-{uuid.uuid4().hex[:6]}"
        doc = Employee({
            "doctype": "Employee",
            "name": emp_id,
            "employee_id": emp_id,
            "employee_name": "Self Boss",
            "manager": emp_id,
            "department": "Engineering"
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.validate_manager()
        self.assertIn("cannot be their own manager", str(ctx.exception).lower())

    def test_prevention_of_circular_manager_hierarchy(self):
        """Test rule: Prevent circular manager hierarchies (A -> B -> A)."""
        # Create temp employee A managed by B, then test B managed by A
        emp_a = f"TEST-CYC-A-{uuid.uuid4().hex[:4]}"
        emp_b = f"TEST-CYC-B-{uuid.uuid4().hex[:4]}"
        
        # Insert A with manager = B
        frappe.db.sql(f"""
            INSERT INTO `tabEmployee` (name, employee_id, employee_name, manager, department, designation, date_of_joining, employment_status, shift)
            VALUES ('{emp_a}', '{emp_a}', 'Employee A', '{emp_b}', 'Engineering', 'Developer', '2024-01-01', 'Active', 'General Shift');
        """)
        self.created_employees.append(emp_a)

        # Now validate B trying to have manager = A (Cycle!)
        doc_b = Employee({
            "doctype": "Employee",
            "name": emp_b,
            "employee_id": emp_b,
            "employee_name": "Employee B",
            "manager": emp_a,
            "department": "Engineering"
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc_b.validate_manager()
        self.assertIn("circular manager relationship detected", str(ctx.exception).lower())

    def test_employee_without_manager_allowed(self):
        """Test rule: Root employee (e.g., CEO) can have manager = None."""
        emp_id = f"TEST-CEO-{uuid.uuid4().hex[:6]}"
        doc = Employee({
            "doctype": "Employee",
            "name": emp_id,
            "employee_id": emp_id,
            "employee_name": "New Chief Executive",
            "manager": None,
            "department": "Executive"
        })
        # Should not raise any exception
        doc.validate_manager()

if __name__ == "__main__":
    unittest.main()
