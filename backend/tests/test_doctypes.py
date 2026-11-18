import os
import sys
import unittest
import tempfile
from unittest.mock import MagicMock, patch

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

try:
    import frappe
except ImportError:
    import frappe_runtime
    frappe_runtime.install_frappe_compat()
    import frappe

# Setup mock site for Frappe context
tmp_dir = tempfile.gettempdir()
site_dir = os.path.join(tmp_dir, "test_site")
os.makedirs(site_dir, exist_ok=True)
with open(os.path.join(tmp_dir, "apps.txt"), "w") as f:
    f.write("frappe\n")
with open(os.path.join(site_dir, "site_config.json"), "w") as f:
    f.write('{"db_name": "test_db", "db_password": "test"}')

try:
    frappe.init(site="test_site", sites_path=tmp_dir)
except Exception:
    pass

frappe.local = getattr(frappe, "local", frappe._dict())
frappe.local.conf = frappe._dict({"developer_mode": 1})
frappe.local.flags = frappe._dict()

class DummyMeta:
    def get_table_fields(self):
        return []
    def get_valid_columns(self):
        return []
    def get_field(self, fieldname):
        return None

class TestDocTypes(unittest.TestCase):
    def setUp(self):
        self.meta_patcher = patch("frappe.get_meta", return_value=DummyMeta())
        self.meta_patcher.start()
        self.mock_db = MagicMock()
        self.mock_db.get_single_value.return_value = "UTC"
        self.mock_db.get_system_setting.return_value = "UTC"
        frappe.local.db = self.mock_db
        self.orig_db = getattr(frappe, "db", None)
        frappe.db = self.mock_db

    def tearDown(self):
        self.meta_patcher.stop()
        if self.orig_db is not None:
            frappe.db = self.orig_db

    def test_employee_cannot_be_own_manager(self):
        """Test rule: An employee cannot be their own manager."""
        from employee360.doctype.employee.employee import Employee
        
        emp = Employee({"doctype": "Employee", "employee_id": "EMP-001", "name": "EMP-001", "manager": "EMP-001"})
        emp.name = "EMP-001"
        emp.employee_id = "EMP-001"
        
        with self.assertRaises(frappe.ValidationError):
            emp.validate_manager()

    def test_employee_circular_manager_prevention(self):
        """Test rule: Prevent circular manager relationships (A -> B -> A)."""
        from employee360.doctype.employee.employee import Employee
        
        emp2 = Employee({"doctype": "Employee", "employee_id": "EMP-002", "name": "EMP-002", "manager": "EMP-001"})
        emp2.name = "EMP-002"
        emp2.employee_id = "EMP-002"
        emp2.employee_name = "Bob"
        
        self.mock_db.exists.return_value = True
        self.mock_db.get_value.side_effect = lambda dt, name, fld: "EMP-002" if name == "EMP-001" and fld == "manager" else None

        with self.assertRaises(frappe.ValidationError):
            emp2.validate_manager()

    def test_employee_without_manager_allowed(self):
        """Test rule: Employees without managers (e.g. CEO) are permitted."""
        from employee360.doctype.employee.employee import Employee
        
        emp = Employee({"doctype": "Employee", "employee_id": "EMP-000", "name": "EMP-000", "manager": None})
        emp.name = "EMP-000"
        emp.employee_id = "EMP-000"
        
        # Should not raise any error
        emp.validate_manager()

    def test_checkin_duplicate_prevention(self):
        """Test rule: Prevent duplicate punches within threshold."""
        from employee360.doctype.employee_checkin.employee_checkin import EmployeeCheckin
        
        checkin = EmployeeCheckin({
            "doctype": "Employee Checkin",
            "employee": "EMP-001",
            "log_type": "IN",
            "time": "2026-11-17 09:00:00"
        })
        checkin.name = "chk2"
        checkin.employee = "EMP-001"
        checkin.log_type = "IN"
        checkin.time = "2026-11-17 09:00:00"
        
        self.mock_db.sql.return_value = [{"name": "chk1", "time": "2026-11-17 09:00:10"}]
        with self.assertRaises(frappe.DuplicateEntryError):
            checkin.prevent_duplicate_events()

    def test_leave_application_date_validation(self):
        """Test rule: To Date cannot be before From Date."""
        from employee360.doctype.leave_application.leave_application import LeaveApplication
        
        leave = LeaveApplication({
            "doctype": "Leave Application",
            "employee": "EMP-001",
            "from_date": "2026-11-20",
            "to_date": "2026-11-18"
        })
        
        with self.assertRaises(frappe.ValidationError):
            leave.validate_dates()

    def test_shift_expected_hours_validation(self):
        """Test rule: Expected working hours must be greater than zero."""
        from employee360.doctype.shift.shift import Shift
        
        shift = Shift({
            "doctype": "Shift",
            "shift_name": "General",
            "start_time": "09:00:00",
            "end_time": "18:00:00",
            "expected_working_hours": -2.0
        })
        
        with self.assertRaises(frappe.ValidationError):
            shift.validate_times()

if __name__ == "__main__":
    unittest.main()
