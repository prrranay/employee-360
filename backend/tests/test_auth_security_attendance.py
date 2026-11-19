"""
Employee360: Comprehensive Security, Authentication, and Attendance Test Suite
================================================================================
Covers all 16 required verification targets:
  1. Valid login
  2. Invalid login
  3. Hardcoded-password rejection
  4. Session expiration & logout
  5. CSRF missing token rejection
  6. CSRF invalid token rejection
  7. Unauthorized employee access (role boundary)
  8. Unauthorized manager access (cross-hierarchy isolation)
  9. CEO global access
  10. Employee access to another employee's record
  11. Duplicate concurrent check-ins
  12. Duplicate concurrent check-outs
  13. Invalid punch order (consecutive IN/OUT, future dates)
  14. Multiple daily sessions (IN -> OUT -> IN -> OUT)
  15. Unauthorized regularization & anti-self-approval
  16. Double approval prevention
"""

import os
import sys
import time
import json
import unittest
import datetime
import urllib.request
import urllib.error
import http.cookiejar
from concurrent.futures import ThreadPoolExecutor

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    import frappe
    from frappe.utils import now_datetime, getdate, nowdate
    from frappe.exceptions import PermissionError, AuthenticationError, ValidationError, DuplicateEntryError
except ImportError:
    frappe = None

def setUpModule():
    if frappe is None:
        raise unittest.SkipTest("Frappe Framework is not installed in the current environment.")
    site = os.environ.get("FRAPPE_SITE", os.environ.get("FRAPPE_SITE_NAME", "employee360.localhost"))
    sites_path = os.environ.get("SITES_PATH", "/home/frappe/frappe-bench/sites" if os.path.exists("/home/frappe/frappe-bench/sites") else None)
    if not getattr(frappe, "db", None) or not frappe.db:
        frappe.init(site=site, sites_path=sites_path)
        frappe.connect()
    frappe.flags.in_test = True
    if not getattr(frappe.local, "session", None):
        frappe.local.session = frappe._dict(user="Administrator")

# Ensure site is initialized for direct ORM access
if frappe is not None:
    if not getattr(frappe, "db", None) or not frappe.db:
        site = os.environ.get("FRAPPE_SITE_NAME", "employee360.localhost")
        sites_path = "/home/frappe/frappe-bench/sites" if os.path.exists("/home/frappe/frappe-bench/sites") else None
        frappe.init(site=site, sites_path=sites_path)
        frappe.connect()

    from employee360.api import auth_utils, ceo, manager, employee, attendance
    from employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary

BASE_URL = os.environ.get("FRAPPE_BASE_URL", "http://127.0.0.1:8000")


def http_login(user, password):
    """Logs in via HTTP and returns (opener, cookiejar, csrf_token)."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    login_data = json.dumps({"usr": user, "pwd": password}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/method/login",
        data=login_data,
        headers={"Content-Type": "application/json"}
    )
    resp = opener.open(req)
    if resp.status != 200:
        raise Exception(f"Login failed: status {resp.status}")

    # Fetch CSRF token via get_session_user_and_roles_api
    auth_req = urllib.request.Request(f"{BASE_URL}/api/method/employee360.api.auth_utils.get_session_user_and_roles_api")
    auth_resp = opener.open(auth_req)
    auth_json = json.loads(auth_resp.read().decode("utf-8"))
    csrf_token = auth_json.get("message", {}).get("csrf_token")

    return opener, cj, csrf_token


class TestAuthenticationSecurityAttendance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        site = os.environ.get("FRAPPE_SITE", "employee360.localhost")
        sites_path = os.environ.get("SITES_PATH", "/home/frappe/frappe-bench/sites")
        try:
            frappe.init(site=site, sites_path=sites_path)
            frappe.connect()
        except Exception:
            pass
        frappe.flags.in_test = True

        cls.ceo_user = "ceo@employee360.local"
        cls.ceo_emp_id = "EMP-00001"

        cls.mgr1_user = "manager1@employee360.local"
        cls.mgr1_emp_id = "EMP-00012"  # Sarah Connor (manages emp1, emp2)

        cls.mgr2_user = "manager2@employee360.local"
        cls.mgr2_emp_id = "EMP-00013"  # David Miller (manages emp3)

        cls.emp1_user = "emp1@employee360.local"
        cls.emp1_emp_id = "EMP-01362"  # Elena Rostova (reports to mgr1)

        cls.emp2_user = "emp2@employee360.local"
        cls.emp2_emp_id = "EMP-01363"  # Marcus Vance (reports to mgr1)

        cls.emp3_user = "emp3@employee360.local"
        cls.emp3_emp_id = "EMP-01364"  # Priya Sharma (reports to mgr2)

        cls.valid_pwd = os.environ.get("DEMO_USER_PASSWORD") or os.environ.get("ADMIN_PASSWORD") or "Admin123!"

    def setUp(self):
        site = os.environ.get("FRAPPE_SITE", "employee360.localhost")
        sites_path = os.environ.get("SITES_PATH", "/home/frappe/frappe-bench/sites")
        try:
            frappe.init(site=site, sites_path=sites_path)
            frappe.connect()
        except Exception:
            pass
        frappe.flags.in_test = True
        frappe.set_user("Administrator")
        self._clear_test_records()

    def tearDown(self):
        frappe.set_user("Administrator")
        self._clear_test_records()

    def _clear_test_records(self):
        try:
            today_str = str(getdate(nowdate()))
            frappe.db.sql(
                "DELETE FROM `tabEmployee Checkin` WHERE employee IN (%s, %s, %s, %s) AND DATE(time) = %s;",
                (self.emp1_emp_id, self.emp2_emp_id, self.emp3_emp_id, self.mgr1_emp_id, today_str)
            )
            frappe.db.sql(
                "DELETE FROM `tabAttendance Exception` WHERE employee IN (%s, %s, %s, %s) AND activity_date = %s;",
                (self.emp1_emp_id, self.emp2_emp_id, self.emp3_emp_id, self.mgr1_emp_id, today_str)
            )
            frappe.db.sql(
                "DELETE FROM `tabAttendance Correction Request` WHERE employee IN (%s, %s, %s, %s) AND activity_date = %s;",
                (self.emp1_emp_id, self.emp2_emp_id, self.emp3_emp_id, self.mgr1_emp_id, today_str)
            )
            frappe.db.commit()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 1. VALID LOGIN
    # -------------------------------------------------------------------------
    def test_01_valid_login(self):
        """Test 1: Valid authentication accepts correct credentials and returns 200 with sid."""
        opener, cj, csrf_token = http_login(self.ceo_user, self.valid_pwd)
        cookies = {c.name: c.value for c in cj}
        self.assertIn("sid", cookies)
        self.assertNotEqual(cookies["sid"], "Guest")
        self.assertIsNotNone(csrf_token)

    # -------------------------------------------------------------------------
    # 2. INVALID LOGIN
    # -------------------------------------------------------------------------
    def test_02_invalid_login(self):
        """Test 2: Invalid authentication rejects bad credentials with HTTP 401."""
        req = urllib.request.Request(
            f"{BASE_URL}/api/method/login",
            data=json.dumps({"usr": self.ceo_user, "pwd": "IncorrectPassword999!"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 401)

    # -------------------------------------------------------------------------
    # 3. HARDCODED-PASSWORD REJECTION
    # -------------------------------------------------------------------------
    def test_03_hardcoded_password_rejection(self):
        """Test 3: Verify non-existent users or bad passwords cannot use universal bypass."""
        # Non-existent user
        req = urllib.request.Request(
            f"{BASE_URL}/api/method/login",
            data=json.dumps({"usr": "hacker@darkweb.org", "pwd": "Admin123!"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 401)

    # -------------------------------------------------------------------------
    # 4. SESSION EXPIRATION & LOGOUT
    # -------------------------------------------------------------------------
    def test_04_session_expiration_and_logout(self):
        """Test 4: Verify logout clears session and rejects subsequent protected requests."""
        opener, cj, csrf = http_login(self.emp1_user, self.valid_pwd)

        # Confirm authenticated access works
        auth_req = urllib.request.Request(f"{BASE_URL}/api/method/employee360.api.auth_utils.get_session_user_and_roles_api")
        resp = opener.open(auth_req)
        self.assertEqual(resp.status, 200)

        # Call logout
        logout_req = urllib.request.Request(
            f"{BASE_URL}/api/method/logout",
            data=b"{}",
            headers={"Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf}
        )
        opener.open(logout_req)

        # Subsequent call to protected API must fail with 403 or 401
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(auth_req)
        self.assertIn(ctx.exception.code, (401, 403))

    # -------------------------------------------------------------------------
    # 5. CSRF MISSING TOKEN REJECTION
    # -------------------------------------------------------------------------
    def test_05_csrf_missing_token_rejection(self):
        """Test 5: POST request with active session missing CSRF token is rejected with HTTP 400."""
        opener, cj, csrf = http_login(self.emp1_user, self.valid_pwd)

        post_req = urllib.request.Request(
            f"{BASE_URL}/api/method/employee360.api.attendance.get_today_attendance",
            data=b"{}",
            headers={"Content-Type": "application/json"}  # No CSRF header
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(post_req)
        self.assertEqual(ctx.exception.code, 400)
        body = ctx.exception.read().decode("utf-8")
        self.assertIn("CSRFTokenError", body)

    # -------------------------------------------------------------------------
    # 6. CSRF INVALID TOKEN REJECTION
    # -------------------------------------------------------------------------
    def test_06_csrf_invalid_token_rejection(self):
        """Test 6: POST request with forged/invalid CSRF token is rejected with HTTP 400."""
        opener, cj, csrf = http_login(self.emp1_user, self.valid_pwd)

        post_req = urllib.request.Request(
            f"{BASE_URL}/api/method/employee360.api.attendance.get_today_attendance",
            data=b"{}",
            headers={
                "Content-Type": "application/json",
                "X-Frappe-CSRF-Token": "forged_malicious_token_12345"
            }
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            opener.open(post_req)
        self.assertEqual(ctx.exception.code, 400)
        body = ctx.exception.read().decode("utf-8")
        self.assertIn("CSRFTokenError", body)

    # -------------------------------------------------------------------------
    # 7. UNAUTHORIZED EMPLOYEE ACCESS
    # -------------------------------------------------------------------------
    def test_07_unauthorized_employee_access(self):
        """Test 7: Regular employee is rejected from CEO and Manager endpoints."""
        frappe.set_user(self.emp1_user)

        with self.assertRaises(PermissionError):
            ceo.get_company_dashboard_summary()

        with self.assertRaises(PermissionError):
            manager.get_team_dashboard_summary()

    # -------------------------------------------------------------------------
    # 8. UNAUTHORIZED MANAGER ACCESS (CROSS-HIERARCHY ISOLATION)
    # -------------------------------------------------------------------------
    def test_08_unauthorized_manager_access(self):
        """Test 8: Manager cannot access or manage employees outside their reporting hierarchy."""
        frappe.set_user(self.mgr1_user)

        # emp3 reports to mgr2, NOT mgr1
        with self.assertRaises(PermissionError) as ctx:
            auth_utils.assert_can_access_employee(self.emp3_emp_id)
        self.assertIn("not authorized", str(ctx.exception).lower())

        with self.assertRaises(PermissionError) as ctx:
            auth_utils.assert_can_manage_employee(self.emp3_emp_id)
        self.assertIn("managerial authority", str(ctx.exception).lower())

    # -------------------------------------------------------------------------
    # 9. CEO GLOBAL ACCESS
    # -------------------------------------------------------------------------
    def test_09_ceo_global_access(self):
        """Test 9: CEO has full access to company summary, search, and all employee records."""
        frappe.set_user(self.ceo_user)

        # Company dashboard summary
        summary = ceo.get_company_dashboard_summary()
        self.assertIn("total_employees", summary)

        # Access any employee
        auth_utils.assert_can_access_employee(self.emp1_emp_id)
        auth_utils.assert_can_access_employee(self.emp3_emp_id)

    # -------------------------------------------------------------------------
    # 10. EMPLOYEE ACCESS TO ANOTHER EMPLOYEE'S RECORD
    # -------------------------------------------------------------------------
    def test_10_employee_access_to_another_employee_rejected(self):
        """Test 10: Individual contributor cannot access peer employee records."""
        frappe.set_user(self.emp1_user)

        # Accessing self is permitted
        auth_utils.assert_can_access_employee(self.emp1_emp_id)

        # Accessing peer (emp2) is rejected
        with self.assertRaises(PermissionError):
            auth_utils.assert_can_access_employee(self.emp2_emp_id)

    # -------------------------------------------------------------------------
    # 11. DUPLICATE CONCURRENT CHECK-INS
    # -------------------------------------------------------------------------
    def test_11_duplicate_concurrent_checkins(self):
        """Test 11: Simultaneous check-in HTTP requests are serialized; second check-in is rejected."""
        opener, cj, csrf = http_login(self.emp1_user, self.valid_pwd)

        results = []
        errors = []

        def do_check_in():
            try:
                checkin_req = urllib.request.Request(
                    f"{BASE_URL}/api/method/employee360.api.attendance.check_in",
                    data=json.dumps({"device_info": "Concurrent Test Worker"}).encode("utf-8"),
                    headers={"Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf}
                )
                resp = opener.open(checkin_req)
                results.append(resp.status)
            except urllib.error.HTTPError as e:
                errors.append(e.code)
            except Exception as e:
                errors.append(str(e))

        # Launch 2 simultaneous HTTP requests
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(do_check_in), executor.submit(do_check_in)]
            for f in futures:
                f.result()

        total = len(results) + len(errors)
        self.assertEqual(total, 2)
        # Exactly 1 success (200), and 1 failure (HTTP 417 / 500 with ValidationError)
        self.assertEqual(len(results), 1, f"Expected 1 successful checkin, got: {results}")
        self.assertEqual(len(errors), 1, f"Expected 1 rejected checkin, got: {errors}")

    # -------------------------------------------------------------------------
    # 12. DUPLICATE CONCURRENT CHECK-OUTS
    # -------------------------------------------------------------------------
    def test_12_duplicate_concurrent_checkouts(self):
        """Test 12: Simultaneous check-out HTTP requests are serialized; second checkout is rejected."""
        opener, cj, csrf = http_login(self.emp1_user, self.valid_pwd)

        # Check in first to create an open session
        checkin_req = urllib.request.Request(
            f"{BASE_URL}/api/method/employee360.api.attendance.check_in",
            data=json.dumps({"device_info": "Pre-test Checkin"}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf}
        )
        opener.open(checkin_req)

        # Sleep to avoid debounce limit between check-in and check-out
        time.sleep(6)

        results = []
        errors = []

        def do_check_out():
            try:
                checkout_req = urllib.request.Request(
                    f"{BASE_URL}/api/method/employee360.api.attendance.check_out",
                    data=json.dumps({"device_info": "Concurrent Checkout Worker"}).encode("utf-8"),
                    headers={"Content-Type": "application/json", "X-Frappe-CSRF-Token": csrf}
                )
                resp = opener.open(checkout_req)
                results.append(resp.status)
            except urllib.error.HTTPError as e:
                errors.append(e.code)
            except Exception as e:
                errors.append(str(e))

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(do_check_out), executor.submit(do_check_out)]
            for f in futures:
                f.result()

        # Exactly 1 successful checkout, and 1 rejected checkout
        self.assertEqual(len(results), 1, f"Expected 1 successful checkout, got: {results}")
        self.assertEqual(len(errors), 1, f"Expected 1 rejected checkout, got: {errors}")

    # -------------------------------------------------------------------------
    # 13. INVALID PUNCH ORDER
    # -------------------------------------------------------------------------
    def test_13_invalid_punch_order(self):
        """Test 13: OUT without preceding IN and future timestamps are rejected."""
        frappe.set_user(self.emp2_user)

        # 1. OUT without preceding IN raises ValidationError
        with self.assertRaises(ValidationError) as ctx:
            attendance.check_out(device_info="Invalid OUT")
        self.assertIn("no active open check-in session", str(ctx.exception).lower())

        # 2. Future timestamp punch raises ValidationError
        future_time = now_datetime() + datetime.timedelta(hours=2)
        future_checkin = frappe.get_doc({
            "doctype": "Employee Checkin",
            "employee": self.emp2_emp_id,
            "time": future_time,
            "log_type": "IN",
            "source": "Web"
        })
        with self.assertRaises(ValidationError) as ctx:
            future_checkin.insert()
        self.assertIn("in the future", str(ctx.exception).lower())

    # -------------------------------------------------------------------------
    # 14. MULTIPLE DAILY SESSIONS
    # -------------------------------------------------------------------------
    def test_14_multiple_daily_sessions(self):
        """Test 14: Valid multi-session flow (IN -> OUT -> IN -> OUT) correctly recorded."""
        frappe.set_user(self.emp2_user)
        test_date = getdate(nowdate()) - datetime.timedelta(days=2)

        # Clean emp2 punches
        frappe.db.sql(
            "DELETE FROM `tabEmployee Checkin` WHERE employee = %s AND DATE(time) = %s;",
            (self.emp2_emp_id, str(test_date))
        )
        frappe.db.commit()

        # Session 1: 09:00 -> 12:30
        t1 = datetime.datetime.combine(test_date, datetime.time(9, 0, 0))
        t2 = datetime.datetime.combine(test_date, datetime.time(12, 30, 0))
        # Session 2: 13:30 -> 17:30
        t3 = datetime.datetime.combine(test_date, datetime.time(13, 30, 0))
        t4 = datetime.datetime.combine(test_date, datetime.time(17, 30, 0))

        for p_time, p_type in [(t1, "IN"), (t2, "OUT"), (t3, "IN"), (t4, "OUT")]:
            c = frappe.get_doc({
                "doctype": "Employee Checkin",
                "employee": self.emp2_emp_id,
                "time": p_time,
                "log_type": p_type,
                "source": "Web"
            })
            c.insert()

        recalculate_daily_summary(self.emp2_emp_id, test_date)

        eal = frappe.db.get_value(
            "Employee Activity Log",
            {"employee": self.emp2_emp_id, "activity_date": test_date},
            ["total_sessions", "total_work_seconds", "first_login", "last_logout", "attendance_status"],
            as_dict=True
        )

        # 3.5 hrs (12600s) + 4.0 hrs (14400s) = 7.5 hrs (27000s)
        self.assertEqual(eal["total_sessions"], 2)
        self.assertEqual(eal["total_work_seconds"], 27000)
        self.assertEqual(eal["attendance_status"], "Present")

    # -------------------------------------------------------------------------
    # 15. UNAUTHORIZED REGULARIZATION & ANTI-SELF-APPROVAL
    # -------------------------------------------------------------------------
    def test_15_unauthorized_regularization_and_anti_self_approval(self):
        """Test 15: Self-approval forbidden, cross-manager approval forbidden, client source forge forbidden."""
        # 1. Anti-self-approval: Manager cannot approve their own correction
        frappe.set_user(self.mgr1_user)
        with self.assertRaises(PermissionError) as ctx:
            auth_utils.assert_can_manage_employee(self.mgr1_emp_id)
        self.assertIn("self-approval is strictly forbidden", str(ctx.exception).lower())

        # 2. Cross-manager approval: Manager 2 cannot approve Manager 1's report (emp1)
        frappe.set_user(self.mgr2_user)
        with self.assertRaises(PermissionError) as ctx:
            auth_utils.assert_can_manage_employee(self.emp1_emp_id)
        self.assertIn("managerial authority", str(ctx.exception).lower())

        # 3. Client forged source: Employee cannot insert punch with source='Admin Correction' directly
        frappe.set_user(self.emp1_user)
        fake_punch = frappe.get_doc({
            "doctype": "Employee Checkin",
            "employee": self.emp1_emp_id,
            "time": now_datetime(),
            "log_type": "IN",
            "source": "Admin Correction"
        })
        with self.assertRaises(PermissionError) as ctx:
            fake_punch.insert()
        self.assertIn("administrative corrections must be processed through", str(ctx.exception).lower())

    # -------------------------------------------------------------------------
    # 16. DOUBLE APPROVAL PREVENTION
    # -------------------------------------------------------------------------
    def test_16_double_approval_prevention(self):
        """Test 16: Regularization exception cannot be approved twice; duplicate approval rejected."""
        # Step A: Employee submits regularization request
        frappe.set_user(self.emp1_user)
        req_res = attendance.request_attendance_correction(
            activity_date="2026-11-10",
            exception_type="Missing Check-out",
            requested_status="Present",
            reason="Badge reader hardware fault",
            requested_in_time="09:00:00",
            requested_out_time="18:00:00"
        )
        exc_id = req_res["exception_id"]

        # Step B: Manager 1 approves
        frappe.set_user(self.mgr1_user)
        app_res = attendance.approve_attendance_exception(
            exception_id=exc_id,
            comments="Verified against gate security logs and approved"
        )
        self.assertEqual(app_res["regularized_status"], "Present")

        # Step C: Attempting second approval on the same exception must fail with ValidationError
        with self.assertRaises(ValidationError) as ctx:
            attendance.approve_attendance_exception(
                exception_id=exc_id,
                comments="Second approval attempt"
            )
        self.assertIn("already been processed", str(ctx.exception).lower())

        # Clean up
        frappe.set_user("Administrator")
        frappe.db.sql(f"DELETE FROM `tabAttendance Exception` WHERE name = '{exc_id}';")
        frappe.db.sql(f"DELETE FROM `tabAttendance Correction Request` WHERE name = '{exc_id}';")
        frappe.db.sql(f"DELETE FROM `tabEmployee Checkin` WHERE source_record_id = '{exc_id}';")
        frappe.db.commit()


if __name__ == "__main__":
    unittest.main()
