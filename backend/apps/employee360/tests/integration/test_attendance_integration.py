import os
import sys
import unittest
import uuid
import datetime

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
APP_DIR = os.path.join(BACKEND_DIR, "apps", "employee360")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import frappe_bridge
frappe_bridge.install_frappe_compat()
import frappe
from frappe_bridge import _current_user_var
from employee360.api import attendance, employee
from employee360.employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary

class TestAttendanceIntegration(unittest.TestCase):
    def setUp(self):
        # Demo employee: Elena Rostova EMP-01362 linked to emp1@employee360.local
        self.emp_user = "emp1@employee360.local"
        self.emp_id = "EMP-01362"
        self.manager_user = "manager1@employee360.local"
        self.token = _current_user_var.set(self.emp_user)
        self.clear_debounce()

    def clear_debounce(self):
        frappe.db.sql(f"""
            UPDATE `tabEmployee Checkin`
            SET time = DATE_SUB(NOW(), INTERVAL 35 SECOND)
            WHERE employee = '{self.emp_id}'
              AND time > DATE_SUB(NOW(), INTERVAL 35 SECOND);
        """)

    def tearDown(self):
        _current_user_var.reset(self.token)

    def test_01_checkin_flow(self):
        """Test Check-in records IN punch with server timestamp, trusted IP, and momentary GPS."""
        _current_user_var.set(self.emp_user)
        self.clear_debounce()
        today_att = attendance.get_today_attendance()
        if today_att["current_state"] == "Checked In":
            self.clear_debounce()
            attendance.check_out(device_info="Teardown checkout")
            self.clear_debounce()

        res = attendance.check_in(
            device_info="Integration Test Agent",
            latitude=37.7749,
            longitude=-122.4194,
            gps_accuracy=10.5,
            ip_address="192.168.1.100"
        )
        self.assertEqual(res["current_state"], "Checked In")
        self.assertEqual(res["employee_id"], self.emp_id)
        self.assertTrue(len(res["punches"]) >= 1)
        last_punch = res["punches"][-1]
        self.assertEqual(last_punch["log_type"], "IN")
        self.assertEqual(last_punch["ip_address"], "192.168.1.100")
        self.assertEqual(last_punch["gps_accuracy"], 10.5)

    def test_02_duplicate_checkin_prevention(self):
        """Test Duplicate Check-in: second consecutive IN punch without checkout throws ValidationError."""
        _current_user_var.set(self.emp_user)
        self.clear_debounce()
        today_att = attendance.get_today_attendance()
        if today_att["current_state"] != "Checked In":
            attendance.check_in(device_info="Setup In")
            self.clear_debounce()

        # Second IN punch must be rejected
        with self.assertRaises(frappe.ValidationError) as ctx:
            attendance.check_in(device_info="Duplicate IN")
        self.assertIn("already checked in", str(ctx.exception).lower())

    def test_03_checkout_flow(self):
        """Test Check-out records OUT punch, closes open session, and calculates work duration."""
        _current_user_var.set(self.emp_user)
        self.clear_debounce()
        today_att = attendance.get_today_attendance()
        if today_att["current_state"] != "Checked In":
            attendance.check_in(device_info="Pre-checkout IN")

        self.clear_debounce()
        res = attendance.check_out(
            device_info="Integration Test Agent",
            latitude=37.7749,
            longitude=-122.4194,
            gps_accuracy=10.5,
            ip_address="192.168.1.100"
        )
        self.assertEqual(res["current_state"], "Checked Out")
        self.assertTrue(len(res["punches"]) >= 2)
        last_punch = res["punches"][-1]
        self.assertEqual(last_punch["log_type"], "OUT")
        self.assertIsNotNone(res["last_logout"])

    def test_04_invalid_checkout_prevention(self):
        """Test Invalid Check-out: Attempting to checkout when already checked out throws ValidationError."""
        _current_user_var.set(self.emp_user)
        self.clear_debounce()
        today_att = attendance.get_today_attendance()
        if today_att["current_state"] == "Checked In":
            self.clear_debounce()
            attendance.check_out(device_info="Close session")

        self.clear_debounce()
        # Now attempting another checkout must fail
        with self.assertRaises(frappe.ValidationError) as ctx:
            attendance.check_out(device_info="Invalid OUT")
        self.assertIn("no active open check-in", str(ctx.exception).lower())

    def test_05_multiple_daily_sessions(self):
        """Test multiple sessions per day (e.g. lunch breaks): IN -> OUT -> IN -> OUT."""
        test_emp = "EMP-01362"
        test_date = datetime.date(2026, 10, 5)  # A Monday

        # Clean prior test punches for this date
        frappe.db.sql(f"""
            DELETE FROM `tabEmployee Checkin` 
            WHERE employee = '{test_emp}' AND DATE(time) = '{test_date}';
        """)

        # Insert Session 1: 09:00 to 12:30 (3.5 hours = 12600s)
        frappe.db.sql(f"""
            INSERT INTO `tabEmployee Checkin` (name, employee, log_type, time, source)
            VALUES ('PUNCH-S1-IN', '{test_emp}', 'IN', '{test_date} 09:00:00', 'Web'),
                   ('PUNCH-S1-OUT', '{test_emp}', 'OUT', '{test_date} 12:30:00', 'Web');
        """)
        # Insert Session 2: 13:30 to 18:00 (4.5 hours = 16200s)
        frappe.db.sql(f"""
            INSERT INTO `tabEmployee Checkin` (name, employee, log_type, time, source)
            VALUES ('PUNCH-S2-IN', '{test_emp}', 'IN', '{test_date} 13:30:00', 'Web'),
                   ('PUNCH-S2-OUT', '{test_emp}', 'OUT', '{test_date} 18:00:00', 'Web');
        """)

        # Recalculate summary
        recalculate_daily_summary(test_emp, test_date)

        summary = frappe.db.sql(f"""
            SELECT total_sessions, total_work_seconds, attendance_status, first_login, last_logout
            FROM `tabEmployee Activity Log`
            WHERE employee = '{test_emp}' AND activity_date = '{test_date}';
        """, as_dict=True)[0]

        self.assertEqual(summary["total_sessions"], 2)
        # Total work = 3.5h + 4.5h = 8h = 28,800s
        self.assertEqual(summary["total_work_seconds"], 28800)
        self.assertEqual(summary["attendance_status"], "Present")

    def test_06_missing_checkout_detection(self):
        """Test Missing Check-out: Employee checks in but never checks out."""
        test_emp = "EMP-01362"
        test_date = datetime.date(2026, 10, 6)

        frappe.db.sql(f"DELETE FROM `tabEmployee Checkin` WHERE employee = '{test_emp}' AND DATE(time) = '{test_date}';")
        frappe.db.sql(f"""
            INSERT INTO `tabEmployee Checkin` (name, employee, log_type, time, source)
            VALUES ('PUNCH-MC-IN', '{test_emp}', 'IN', '{test_date} 09:00:00', 'Web');
        """)

        recalculate_daily_summary(test_emp, test_date)

        summary = frappe.db.sql(f"""
            SELECT attendance_status, last_logout
            FROM `tabEmployee Activity Log`
            WHERE employee = '{test_emp}' AND activity_date = '{test_date}';
        """, as_dict=True)[0]

        self.assertEqual(summary["attendance_status"], "Missing Check-out")
        self.assertIsNone(summary["last_logout"])

    def test_07_late_arrival_detection(self):
        """Test Late Arrival: Check-in past shift start (09:00) + grace period (15 min) -> 09:25."""
        test_emp = "EMP-01362"
        test_date = datetime.date(2026, 10, 7)

        frappe.db.sql(f"DELETE FROM `tabEmployee Checkin` WHERE employee = '{test_emp}' AND DATE(time) = '{test_date}';")
        frappe.db.sql(f"""
            INSERT INTO `tabEmployee Checkin` (name, employee, log_type, time, source)
            VALUES ('PUNCH-LA-IN', '{test_emp}', 'IN', '{test_date} 09:25:00', 'Web'),
                   ('PUNCH-LA-OUT', '{test_emp}', 'OUT', '{test_date} 18:00:00', 'Web');
        """)

        recalculate_daily_summary(test_emp, test_date)

        summary = frappe.db.sql(f"""
            SELECT attendance_status
            FROM `tabEmployee Activity Log`
            WHERE employee = '{test_emp}' AND activity_date = '{test_date}';
        """, as_dict=True)[0]

        self.assertEqual(summary["attendance_status"], "Late")

    def test_08_early_departure_and_half_day(self):
        """Test Early Departure: Employee leaves at 13:00 (4 hours work), resulting in Half Day."""
        test_emp = "EMP-01362"
        test_date = datetime.date(2026, 10, 8)

        frappe.db.sql(f"DELETE FROM `tabEmployee Checkin` WHERE employee = '{test_emp}' AND DATE(time) = '{test_date}';")
        frappe.db.sql(f"""
            INSERT INTO `tabEmployee Checkin` (name, employee, log_type, time, source)
            VALUES ('PUNCH-ED-IN', '{test_emp}', 'IN', '{test_date} 09:00:00', 'Web'),
                   ('PUNCH-ED-OUT', '{test_emp}', 'OUT', '{test_date} 13:00:00', 'Web');
        """)

        recalculate_daily_summary(test_emp, test_date)

        summary = frappe.db.sql(f"""
            SELECT attendance_status, total_work_seconds
            FROM `tabEmployee Activity Log`
            WHERE employee = '{test_emp}' AND activity_date = '{test_date}';
        """, as_dict=True)[0]

        self.assertEqual(summary["attendance_status"], "Half Day")
        self.assertEqual(summary["total_work_seconds"], 14400)

    def test_09_weekly_off_classification(self):
        """Test Weekly Off: Sunday with no punches is classified as Weekly Off, not Absent."""
        test_emp = "EMP-01362"
        sunday_date = datetime.date(2026, 10, 11)  # 2026-10-11 is Sunday

        frappe.db.sql(f"DELETE FROM `tabEmployee Checkin` WHERE employee = '{test_emp}' AND DATE(time) = '{sunday_date}';")
        recalculate_daily_summary(test_emp, sunday_date)

        summary = frappe.db.sql(f"""
            SELECT attendance_status
            FROM `tabEmployee Activity Log`
            WHERE employee = '{test_emp}' AND activity_date = '{sunday_date}';
        """, as_dict=True)[0]

        self.assertEqual(summary["attendance_status"], "Weekly Off")

    def test_10_approved_leave_classification(self):
        """Test Approved Leave: Day covered by approved leave is classified as On Leave, not Absent."""
        test_emp = "EMP-01362"
        leave_date = datetime.date(2026, 10, 14)  # Wednesday

        # Clean prior punches
        frappe.db.sql(f"DELETE FROM `tabEmployee Checkin` WHERE employee = '{test_emp}' AND DATE(time) = '{leave_date}';")
        
        # Insert approved leave for this date
        leave_id = f"LEAV-TEST-{uuid.uuid4().hex[:6]}"
        frappe.db.sql(f"""
            INSERT INTO `tabLeave Application` (name, employee, leave_type, from_date, to_date, reason, status)
            VALUES ('{leave_id}', '{test_emp}', 'Casual Leave', '{leave_date}', '{leave_date}', 'Test Leave', 'Approved');
        """)

        recalculate_daily_summary(test_emp, leave_date)

        summary = frappe.db.sql(f"""
            SELECT attendance_status
            FROM `tabEmployee Activity Log`
            WHERE employee = '{test_emp}' AND activity_date = '{leave_date}';
        """, as_dict=True)[0]

        self.assertEqual(summary["attendance_status"], "On Leave")

    def test_11_attendance_correction_and_regularization(self):
        """Test Regularization: Employee requests correction on missed checkout, manager approves with audit trail."""
        # 1. Employee requests correction
        _current_user_var.set(self.emp_user)
        target_date = "2026-10-06"  # The date from test_06 with missing checkout
        corr_res = attendance.request_attendance_correction(
            activity_date=target_date,
            exception_type="Missing Check-out",
            requested_status="Present",
            reason="Badge reader network outage at exit",
            requested_in_time="09:00:00",
            requested_out_time="18:00:00"
        )
        self.assertIn("exception_id", corr_res)
        exc_id = corr_res["exception_id"]

        # 2. Manager reviews and approves exception
        _current_user_var.set(self.manager_user)
        app_res = attendance.approve_attendance_exception(
            exception_id=exc_id,
            comments="Verified against facility access log and approved"
        )
        self.assertEqual(app_res["regularized_status"], "Present")
        db_exc_status = frappe.db.get_value("Attendance Exception", exc_id, "status")
        self.assertEqual(db_exc_status, "Resolved")

        # 3. Verify audit checkin record was created with source = 'Admin Correction'
        audit_punch = frappe.db.sql(f"""
            SELECT source, source_record_id, log_type 
            FROM `tabEmployee Checkin`
            WHERE employee = '{self.emp_id}' AND source_record_id = '{exc_id}';
        """, as_dict=True)
        self.assertTrue(len(audit_punch) >= 1)
        self.assertEqual(audit_punch[0]["source"], "Admin Correction")

        # 4. Verify daily summary now reflects is_regularized = 1 and status = Present
        summary = frappe.db.sql(f"""
            SELECT attendance_status, is_regularized, regularization_exception
            FROM `tabEmployee Activity Log`
            WHERE employee = '{self.emp_id}' AND activity_date = '{target_date}';
        """, as_dict=True)[0]

        self.assertEqual(summary["attendance_status"], "Present")
        self.assertEqual(summary["is_regularized"], 1)
        self.assertEqual(summary["regularization_exception"], exc_id)

    @classmethod
    def tearDownClass(cls):
        # Clean up any test records created for today (2026-11-17) outside the 365-day seed baseline
        frappe.db.sql("""
            DELETE FROM `tabEmployee Checkin`
            WHERE employee = 'EMP-01362' AND DATE(time) > '2026-11-16';
        """)
        try:
            frappe.db.sql("""
                DELETE FROM `tabAttendance Exception`
                WHERE employee = 'EMP-01362' AND activity_date > '2026-11-16';
            """)
        except Exception:
            pass
        frappe.db.sql("""
            DELETE FROM `tabEmployee Activity Log`
            WHERE activity_date > '2026-11-16' OR activity_date < '2025-11-17';
        """)
        frappe.db.sql("""
            DELETE FROM `tabLeave Application`
            WHERE name LIKE 'LEAV-TEST-%';
        """)

if __name__ == "__main__":
    unittest.main()
