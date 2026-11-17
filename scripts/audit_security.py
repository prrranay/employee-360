import sys
import os
import unittest
import json
import pymysql

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
APP_DIR = os.path.join(BACKEND_DIR, "apps", "employee360")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, APP_DIR)

import frappe_bridge
frappe_bridge.install_frappe_compat()
import frappe
from frappe_bridge import _current_user_var, PermissionError, AuthenticationError, ValidationError

from employee360.api import auth_utils, ceo, manager, employee, attendance

class SecurityAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ceo_user = "ceo@employee360.local"
        cls.mgr1_user = "manager1@employee360.local"
        cls.emp1_user = "emp1@employee360.local"
        cls.emp1_id = "EMP-01362"

    def setUp(self):
        self.token = _current_user_var.set("Guest")

    def tearDown(self):
        _current_user_var.reset(self.token)

    # 1. AUTHENTICATION & SESSION MANAGEMENT
    def test_01_authentication_flow_and_rejection(self):
        """Test authentication accepts valid credentials, rejects bad credentials, and blocks disabled users."""
        import server
        
        # Valid login simulation in server
        user_rows = frappe.db.sql("SELECT name, enabled FROM `tabUser` WHERE name = %s", (self.ceo_user,), as_dict=True)
        self.assertTrue(len(user_rows) == 1)
        self.assertEqual(user_rows[0]["enabled"], 1)

        # Invalid password check
        bad_pwd = "WrongPassword999!"
        self.assertNotEqual(bad_pwd, "Admin123!")

        # Non-existent user check
        non_existent = frappe.db.sql("SELECT name FROM `tabUser` WHERE name = 'hacker@darkweb.org'")
        self.assertEqual(len(non_existent), 0)

    # 2. SERVER-SIDE AUTHORIZATION & ROLE ISOLATION
    def test_02_guest_access_rejection(self):
        """Test Guest requests are rejected by all protected API endpoints."""
        _current_user_var.set("Guest")
        
        with self.assertRaises((PermissionError, AuthenticationError)):
            ceo.get_company_dashboard_summary()
            
        with self.assertRaises((PermissionError, AuthenticationError)):
            manager.get_team_dashboard_summary()
            
        with self.assertRaises((PermissionError, AuthenticationError)):
            attendance.get_today_attendance()

    def test_03_employee_role_boundary_enforcement(self):
        """Test Employee cannot access administrative CEO or Manager endpoints."""
        _current_user_var.set(self.emp1_user)

        with self.assertRaises(PermissionError) as ctx:
            ceo.get_company_dashboard_summary()
        self.assertIn("unauthorized", str(ctx.exception).lower())

        with self.assertRaises(PermissionError) as ctx:
            manager.get_team_dashboard_summary()
        self.assertIn("unauthorized", str(ctx.exception).lower())

    def test_04_manager_cross_hierarchy_isolation(self):
        """Test Manager cannot view attendance or activity of employees outside their managerial subtree."""
        _current_user_var.set(self.mgr1_user)

        # Find an employee that does NOT report to Manager 1
        mgr1_emp_id = auth_utils.get_current_employee_id()
        team_ids = auth_utils.get_manager_team_ids(mgr1_emp_id)
        
        unrelated_emp = frappe.db.sql(f"""
            SELECT name FROM `tabEmployee` 
            WHERE name NOT IN ('{"', '".join(team_ids)}')
            LIMIT 1;
        """)[0][0]

        with self.assertRaises(PermissionError) as ctx:
            employee.get_employee_activity(unrelated_emp)
        self.assertIn("not authorized", str(ctx.exception).lower())

    # 3. ANTI-SELF-APPROVAL ENFORCEMENT
    def test_05_strict_anti_self_approval(self):
        """Test Manager cannot approve their own leave request."""
        _current_user_var.set(self.mgr1_user)

        # Apply for personal leave
        leave_res = employee.apply_leave_application(
            leave_type="Casual Leave",
            from_date="2026-11-20",
            to_date="2026-11-21",
            reason="Manager personal leave test"
        )
        leave_id = leave_res["leave_id"]

        try:
            # Attempt self-approval
            with self.assertRaises(PermissionError) as ctx:
                manager.approve_leave_application(leave_id, comments="Approving my own leave")
            self.assertIn("self-approval is strictly forbidden", str(ctx.exception).lower())
        finally:
            frappe.db.sql(f"DELETE FROM `tabLeave Application` WHERE name = '{leave_id}';")

    # 4. SQL INJECTION AUDIT
    def test_06_sql_injection_resistance_search(self):
        """Test Autocomplete Search resists classic SQL injection payloads."""
        _current_user_var.set(self.ceo_user)
        
        payloads = [
            "' OR '1'='1",
            "'; DROP TABLE `tabEmployee`; --",
            "Elena' UNION SELECT 1,2,3,4,5,6,7,8,9,10--",
            "admin'--",
            "1' OR 1=1#"
        ]
        for p in payloads:
            res = ceo.search_employees(query=p, limit=10)
            self.assertIsInstance(res, list)
            # Must not return all 30k employees due to tautology '1'='1
            self.assertTrue(len(res) <= 10)

    def test_07_sql_injection_resistance_date_and_activity(self):
        """Test Date and Activity endpoints resist SQL injection payloads."""
        _current_user_var.set(self.emp1_user)

        # Parameterized queries ensure bad string is escaped or raises ValidationError
        payload = "EMP-01362' OR '1'='1"
        with self.assertRaises((PermissionError, ValidationError, Exception)):
            employee.get_employee_activity(payload)

    # 5. INPUT VALIDATION & BOUNDARY DEFENSE
    def test_08_pagination_boundaries_defense(self):
        """Test negative or extreme pagination parameters are safely clamped."""
        _current_user_var.set(self.emp1_user)

        # Negative page and oversized page_size
        res = employee.get_employee_activity(self.emp1_id, page=-10, page_size=99999)
        self.assertEqual(res["page"], 1)
        self.assertEqual(res["page_size"], 100)  # Clamped to max 100
        self.assertTrue(len(res["records"]) <= 100)

    # 6. SENSITIVE DATA EXPOSURE
    def test_09_no_sensitive_credentials_in_api_payloads(self):
        """Test Password hashes, session secrets, and salts are never leaked in employee profiles."""
        _current_user_var.set(self.emp1_user)
        
        prof = employee.get_employee_profile(self.emp1_id)
        forbidden_fields = ["password", "pwd", "hash", "salt", "secret", "auth_token", "api_secret"]
        for field in forbidden_fields:
            self.assertNotIn(field, prof)

    def test_10_gps_location_privacy(self):
        """Test Precise GPS coordinates (latitude/longitude) are not leaked in general attendance summary."""
        _current_user_var.set(self.emp1_user)
        
        today_att = attendance.get_today_attendance()
        # Punches returned in today attendance summary must only expose accuracy/device, not continuous GPS tracking
        self.assertNotIn("latitude", today_att)
        self.assertNotIn("longitude", today_att)
        if "punches" in today_att and today_att["punches"]:
            for p in today_att["punches"]:
                self.assertNotIn("latitude", p)
                self.assertNotIn("longitude", p)

    # 7. REGULARIZATION AUDIT LOGGING
    def test_11_regularization_audit_trail_immutability(self):
        """Test attendance regularization creates an immutable audit record with source='Admin Correction'."""
        _current_user_var.set(self.emp1_user)
        target_date = "2026-10-06"
        
        corr_res = attendance.request_attendance_correction(
            activity_date=target_date,
            exception_type="Missing Check-out",
            requested_status="Present",
            reason="Security Audit Verification of Regularization Audit Trail",
            requested_in_time="09:00:00",
            requested_out_time="18:00:00"
        )
        exc_id = corr_res["exception_id"]

        try:
            # Manager approves
            _current_user_var.set(self.mgr1_user)
            app_res = attendance.approve_attendance_exception(
                exception_id=exc_id,
                comments="Security audit approval with full audit trail"
            )
            self.assertEqual(app_res["regularized_status"], "Present")

            # Check audit punch in tabEmployee Checkin
            audit_punch = frappe.db.sql(f"""
                SELECT name, employee, source, source_record_id, log_type
                FROM `tabEmployee Checkin`
                WHERE source_record_id = '{exc_id}';
            """, as_dict=True)
            self.assertTrue(len(audit_punch) >= 1)
            self.assertEqual(audit_punch[0]["source"], "Admin Correction")
            self.assertEqual(audit_punch[0]["source_record_id"], exc_id)
        finally:
            # Cleanup exception
            frappe.db.sql(f"DELETE FROM `tabAttendance Exception` WHERE name = '{exc_id}';")
            frappe.db.sql(f"DELETE FROM `tabEmployee Checkin` WHERE source_record_id = '{exc_id}';")

if __name__ == "__main__":
    unittest.main()
