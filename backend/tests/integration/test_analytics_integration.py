import os
import sys
import unittest
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
    site = os.environ.get("FRAPPE_SITE", "employee360.localhost")
    sites_path = os.environ.get("SITES_PATH", "/home/frappe/frappe-bench/sites" if os.path.exists("/home/frappe/frappe-bench/sites") else None)
    if not getattr(frappe, "db", None) or not frappe.db:
        frappe.init(site=site, sites_path=sites_path)
        frappe.connect()
    frappe.flags.in_test = True
    if not getattr(frappe.local, "session", None):
        frappe.local.session = frappe._dict(user="Administrator")

if frappe is not None:
    from employee360.api import ceo, employee

class TestAnalyticsIntegration(unittest.TestCase):
    def setUp(self):
        # Authenticate as CEO for access across all employees and company metrics
        self.ceo_user = "ceo@employee360.local"
        self.emp_id = "EMP-01362"  # Elena Rostova
        frappe.set_user(self.ceo_user)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_01_average_daily_duration(self):
        """Test calculation of average daily working duration in Employee Summary."""
        summary = employee.get_employee_attendance_summary(self.emp_id)
        self.assertIn("avg_daily_work_seconds", summary)
        self.assertIn("avg_daily_work_formatted", summary)
        avg_sec = summary["avg_daily_work_seconds"]
        self.assertGreaterEqual(avg_sec, 0)
        self.assertLessEqual(avg_sec, 86400)
        self.assertIn("h", summary["avg_daily_work_formatted"])

    def test_02_average_monthly_duration(self):
        """Test calculation of average monthly working duration in Employee Summary."""
        summary = employee.get_employee_attendance_summary(self.emp_id)
        self.assertIn("avg_monthly_work_seconds", summary)
        self.assertIn("avg_monthly_work_formatted", summary)
        monthly_sec = summary["avg_monthly_work_seconds"]
        self.assertGreaterEqual(monthly_sec, 0)
        self.assertIn("h", summary["avg_monthly_work_formatted"])

    def test_03_first_login_averages(self):
        """Test average first-login time calculation across attended days."""
        summary = employee.get_employee_attendance_summary(self.emp_id)
        self.assertIn("avg_first_login", summary)
        avg_login = summary["avg_first_login"]
        if avg_login:
            parts = avg_login.split(":")
            self.assertTrue(len(parts) in (2, 3))
            self.assertTrue(0 <= int(parts[0]) <= 23)
            self.assertTrue(0 <= int(parts[1]) <= 59)

    def test_04_last_logout_averages(self):
        """Test average last-logout time calculation across attended days."""
        summary = employee.get_employee_attendance_summary(self.emp_id)
        self.assertIn("avg_last_logout", summary)
        avg_logout = summary["avg_last_logout"]
        if avg_logout:
            parts = avg_logout.split(":")
            self.assertTrue(len(parts) in (2, 3))
            self.assertTrue(0 <= int(parts[0]) <= 23)
            self.assertTrue(0 <= int(parts[1]) <= 59)

    def test_05_attendance_percentages(self):
        """Test attendance percentage calculation formula and bounded range (0-100%)."""
        summary = employee.get_employee_attendance_summary(self.emp_id)
        self.assertIn("attendance_percentage", summary)
        rate = summary["attendance_percentage"]
        self.assertGreaterEqual(rate, 0.0)
        self.assertLessEqual(rate, 100.0)

    def test_06_date_range_filtering(self):
        """Test date range filtering on activity logs: bounds strictly within [from_date, to_date]."""
        from_date = "2026-05-01"
        to_date = "2026-05-15"
        res = employee.get_employee_activity(
            employee_id=self.emp_id,
            from_date=from_date,
            to_date=to_date,
            page=1,
            page_size=50
        )
        self.assertTrue(len(res["records"]) > 0)
        for r in res["records"]:
            act_date = str(r["activity_date"])
            self.assertTrue(from_date <= act_date <= to_date, f"Date {act_date} outside range [{from_date}, {to_date}]")

    def test_07_pagination(self):
        """Test pagination: page size, offsets, total pages calculation, and non-overlapping slices."""
        page1 = employee.get_employee_activity(employee_id=self.emp_id, page=1, page_size=10)
        page2 = employee.get_employee_activity(employee_id=self.emp_id, page=2, page_size=10)

        self.assertEqual(len(page1["records"]), 10)
        self.assertEqual(len(page2["records"]), 10)
        self.assertGreaterEqual(page1["total"], 365)
        expected_pages = (page1["total"] + 10 - 1) // 10
        self.assertEqual(page1["total_pages"], expected_pages)

        # Ensure slices are distinct
        page1_dates = [r["activity_date"] for r in page1["records"]]
        page2_dates = [r["activity_date"] for r in page2["records"]]
        overlap = set(page1_dates).intersection(set(page2_dates))
        self.assertEqual(len(overlap), 0, "Pages 1 and 2 must not overlap")

    def test_08_department_wise_summaries(self):
        """Test department-wise analytics across all 30,000 employees."""
        # Query on a fully seeded historical date
        analytics = ceo.get_department_analytics(target_date="2026-11-10")
        self.assertTrue(len(analytics) > 0)
        
        # Verify key department metrics exist on every item
        departments_seen = set()
        for dept in analytics:
            departments_seen.add(dept["department"])
            self.assertIn("total_headcount", dept)
            self.assertIn("present_count", dept)
            self.assertIn("attendance_rate", dept)
            self.assertIn("avg_work_formatted", dept)
            self.assertGreater(dept["total_headcount"], 0)
            self.assertGreaterEqual(dept["attendance_rate"], 0.0)
            self.assertLessEqual(dept["attendance_rate"], 100.0)

        # Confirm major departments exist across company
        for expected_dept in ["Engineering", "Product", "Sales", "Marketing", "Human Resources", "Finance"]:
            self.assertIn(expected_dept, departments_seen)

if __name__ == "__main__":
    unittest.main()
