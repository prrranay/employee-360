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
    frappe = None

def setUpModule():
    if frappe is None:
        raise unittest.SkipTest("Frappe Framework is not installed in the current environment. Run tests inside Frappe Bench or the Frappe Docker container.")

# Setup Frappe context: use bench site if available, else temporary test site
if frappe is not None:
    bench_sites = "/home/frappe/frappe-bench/sites"
    if os.path.exists(os.path.join(bench_sites, "employee360.localhost")):
        try:
            frappe.init(site="employee360.localhost", sites_path=bench_sites)
            frappe.connect()
        except Exception:
            pass
    elif not getattr(frappe.local, "site", None):
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

class TestAPISecurity(unittest.TestCase):
    def setUp(self):
        self.meta_patcher = patch("frappe.get_meta", return_value=DummyMeta())
        self.meta_patcher.start()
        self.mock_db = MagicMock()
        self.orig_db = getattr(frappe, "db", None)
        self.orig_local_db = getattr(frappe.local, "db", None) if hasattr(frappe, "local") else None
        self.orig_session = getattr(frappe, "session", None)
        frappe.local.db = self.mock_db
        frappe.db = self.mock_db

    def tearDown(self):
        self.meta_patcher.stop()
        if self.orig_db is not None:
            frappe.db = self.orig_db
        if self.orig_local_db is not None:
            frappe.local.db = self.orig_local_db
        if self.orig_session is not None:
            frappe.session = self.orig_session

    def test_employee_cannot_access_other_employee_activity(self):
        """Security: Regular employee cannot access another employee's records."""
        from employee360.api.employee import get_employee_activity

        frappe.session = frappe._dict({"user": "emp1@example.com"})

        # Mock: logged in user is EMP-001, requesting EMP-002
        with patch("frappe.get_roles", return_value=["Employee"]), \
             patch("frappe.db.get_value", return_value="EMP-001"):
            with self.assertRaises(frappe.PermissionError):
                get_employee_activity("EMP-002")

    def test_manager_cannot_approve_own_leave(self):
        """Security: Manager cannot approve their own leave application."""
        from employee360.api.manager import approve_leave_application

        frappe.session = frappe._dict({"user": "mgr@example.com"})

        mock_leave = MagicMock()
        mock_leave.name = "LEAVE-001"
        mock_leave.employee = "EMP-MGR"
        mock_leave.status = "Pending"

        self.mock_db.sql.return_value = [{"name": "LEAVE-001", "employee": "EMP-MGR", "status": "Pending", "leave_type": "Casual Leave", "total_leave_days": 1}]

        with patch("frappe.get_roles", return_value=["Manager"]), \
             patch("frappe.db.get_value", return_value="EMP-MGR"), \
             patch("frappe.get_doc", return_value=mock_leave):
            with self.assertRaises(frappe.PermissionError):
                approve_leave_application("LEAVE-001")

    def test_manager_cannot_approve_unrelated_employee_leave(self):
        """Security: Manager cannot approve leave for an employee not in their reporting tree."""
        from employee360.api.manager import approve_leave_application

        frappe.session = frappe._dict({"user": "mgr@example.com"})

        mock_leave = MagicMock()
        mock_leave.name = "LEAVE-002"
        mock_leave.employee = "EMP-UNRELATED"
        mock_leave.status = "Pending"

        # Query 1: tabLeave Application lookup; Query 2: get_managed_employee_ids tree
        self.mock_db.sql.side_effect = [
            [{"name": "LEAVE-002", "employee": "EMP-UNRELATED", "status": "Pending", "leave_type": "Casual Leave", "total_leave_days": 1}],
            [{"name": "EMP-TEAM1"}],
            []
        ]

        with patch("frappe.get_roles", return_value=["Manager"]), \
             patch("frappe.db.get_value", return_value="EMP-MGR"), \
             patch("frappe.get_doc", return_value=mock_leave):
            with self.assertRaises(frappe.PermissionError):
                approve_leave_application("LEAVE-002")

    def test_ceo_can_access_any_employee(self):
        """Security: CEO has full access across all employees."""
        from employee360.api.employee import get_employee_activity

        frappe.session = frappe._dict({"user": "ceo@example.com"})

        self.mock_db.sql.side_effect = [
            [{"total": 1}],  # count query
            [{"name": "EAL-1", "employee": "EMP-099", "activity_date": "2026-11-01", "attendance_status": "Present"}]  # data query
        ]

        with patch("frappe.get_roles", return_value=["CEO"]), \
             patch("frappe.db.get_value", return_value="EMP-001"):
            res = get_employee_activity("EMP-099")
            self.assertEqual(res["total"], 1)
            self.assertEqual(len(res["records"]), 1)

    def test_search_employees_requires_ceo(self):
        """Security: search_employees throws PermissionError for non-CEO."""
        from employee360.api.ceo import search_employees

        frappe.session = frappe._dict({"user": "emp@example.com"})

        with patch("frappe.get_roles", return_value=["Employee"]):
            with self.assertRaises(frappe.PermissionError):
                search_employees("John")

if __name__ == "__main__":
    unittest.main()
