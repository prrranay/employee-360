import os
import sys
import unittest
import uuid
import datetime

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

try:
    import frappe
except ImportError:
    frappe = None

def setUpModule():
    if frappe is None:
        raise unittest.SkipTest("Frappe Framework is not installed in the current environment. Run tests inside Frappe Bench or the Frappe Docker container.")

if frappe is not None:
    from employee360.api import ceo, manager, employee, auth_utils

class TestPermissionsIntegration(unittest.TestCase):
    def setUp(self):
        # Demo Users:
        # CEO: ceo@employee360.local (EMP-00001 Alex Mercer)
        # Manager 1: manager1@employee360.local (EMP-00012 Sarah Connor, manages 199 team members)
        # Manager 2: manager2@employee360.local (EMP-00013)
        # Employee 1: emp1@employee360.local (EMP-01362 Elena Rostova, managed by Sarah Connor)
        # Employee 2: emp2@employee360.local (EMP-01400)
        self.ceo_user = "ceo@employee360.local"
        self.mgr1_user = "manager1@employee360.local"
        self.mgr1_emp_id = "EMP-00012"
        self.emp1_user = "emp1@employee360.local"
        self.emp1_id = "EMP-01362"
        self.emp2_user = "emp2@employee360.local"
        self.emp2_id = "EMP-01400"

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_01_ceo_company_wide_access(self):
        """Test CEO Access: CEO can access company-wide summaries, any employee overview, and department analytics."""
        frappe.set_user(self.ceo_user)
        
        # 1. Company dashboard summary
        summary = ceo.get_company_dashboard_summary()
        self.assertIn("total_employees", summary)
        self.assertEqual(summary["total_employees"], 30000)

        # 2. Search employees across the 30k employee base
        search_res = ceo.search_employees(query="Connor", limit=5)
        self.assertTrue(len(search_res) >= 1)
        self.assertTrue(any("Connor" in r["employee_name"] for r in search_res))

        # 3. Access any individual employee overview
        emp_ov = ceo.get_employee_overview(employee_id=self.emp1_id)
        self.assertEqual(emp_ov["profile"]["employee_id"], self.emp1_id)

        # 4. Access department analytics
        dept_analytics = ceo.get_department_analytics()
        self.assertTrue(len(dept_analytics) > 0)

    def test_02_manager_authorized_reports_access(self):
        """Test Manager Access: Manager can access authorized team reports and summaries."""
        frappe.set_user(self.mgr1_user)
        
        # Team summary
        team_summary = manager.get_team_dashboard_summary()
        self.assertGreater(team_summary["team_size"], 0)

        # Team list
        team_list = manager.get_manager_team(include_indirect=1)
        self.assertGreater(len(team_list), 0)
        team_ids = [m["name"] for m in team_list]
        self.assertIn(self.emp1_id, team_ids)

        # Manager can view activity of a team member
        emp_activity = employee.get_employee_activity(self.emp1_id, page=1, page_size=10)
        self.assertTrue(len(emp_activity["records"]) > 0)

    def test_03_manager_cannot_access_unrelated_employees(self):
        """Test Security: Manager cannot access employees outside their reporting hierarchy."""
        frappe.set_user(self.mgr1_user)
        
        # Find an employee NOT in manager1's team
        unrelated = frappe.db.sql(f"""
            SELECT e.name 
            FROM `tabEmployee` e
            WHERE e.name NOT IN (
                SELECT name FROM `tabEmployee` WHERE manager = '{self.mgr1_emp_id}'
            )
            AND e.name != '{self.mgr1_emp_id}'
            AND e.manager != '{self.mgr1_emp_id}'
            LIMIT 1;
        """, as_dict=True)[0]["name"]

        # Manager trying to access this unrelated employee's activity must throw PermissionError
        with self.assertRaises(frappe.PermissionError) as ctx:
            employee.get_employee_activity(unrelated)
        self.assertIn("not authorized", str(ctx.exception).lower())

    def test_04_employee_can_access_only_personal_data(self):
        """Test Security: Individual contributor can only access their own profile and attendance records."""
        frappe.set_user(self.emp1_user)
        
        # 1. Accessing own profile works
        own_prof = employee.get_employee_profile(self.emp1_id)
        self.assertEqual(own_prof["name"], self.emp1_id)

        # 2. Accessing own activity works
        own_act = employee.get_employee_activity(self.emp1_id, page=1, page_size=5)
        self.assertTrue(len(own_act["records"]) > 0)

        # 3. Accessing another employee's records throws PermissionError
        with self.assertRaises(frappe.PermissionError) as ctx:
            employee.get_employee_activity(self.emp2_id)
        self.assertIn("not authorized", str(ctx.exception).lower())

        # 4. Attempting to access CEO company dashboard summary throws PermissionError / AuthenticationError
        with self.assertRaises((frappe.PermissionError, frappe.AuthenticationError)):
            ceo.get_company_dashboard_summary()

    def test_05_employee_cannot_approve_their_own_leave(self):
        """Test Security: Strict enforcement of anti-self-approval rule."""
        frappe.set_user(self.mgr1_user)

        # Manager1 applies for leave
        leave_res = employee.apply_leave_application(
            leave_type="Casual Leave",
            from_date="2026-11-25",
            to_date="2026-11-26",
            reason="Manager family trip"
        )
        leave_id = leave_res["leave_id"]

        # Manager1 attempts to approve own leave
        with self.assertRaises(frappe.PermissionError) as ctx:
            manager.approve_leave_application(leave_id, comments="Self approval")
        self.assertIn("self-approval is strictly forbidden", str(ctx.exception).lower())

        # Cleanup leave application
        frappe.db.sql(f"DELETE FROM `tabLeave Application` WHERE name = '{leave_id}';")

    def test_06_unauthorized_guest_requests_rejected(self):
        """Test Security: Unauthenticated 'Guest' requests to protected endpoints are rejected."""
        frappe.set_user("Guest")

        # 1. Current employee
        with self.assertRaises(frappe.AuthenticationError):
            employee.get_current_employee()

        # 2. CEO dashboard
        with self.assertRaises((frappe.PermissionError, frappe.AuthenticationError)):
            ceo.get_company_dashboard_summary()

        # 3. Manager dashboard
        with self.assertRaises((frappe.PermissionError, frappe.AuthenticationError)):
            manager.get_team_dashboard_summary()

if __name__ == "__main__":
    unittest.main()
