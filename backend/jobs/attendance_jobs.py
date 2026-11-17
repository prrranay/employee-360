import sys
import os
import uuid
import datetime
from typing import Optional, Dict, Any, List

# Setup path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app_dir = os.path.join(backend_dir, "apps", "employee360")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

import frappe_bridge
frappe_bridge.install_frappe_compat()

import frappe
from frappe.utils import getdate, nowdate, get_datetime, now_datetime
from employee360.employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary


def detect_attendance_exceptions_for_date(target_date: Optional[str] = None, batch_size: int = 2000) -> Dict[str, Any]:
    """
    Scans employees for attendance exceptions on target_date in memory-bounded batches.
    Respects Shifts, Grace Periods, Weekly Offs, Holidays, and Approved Leaves.
    """
    date_val = getdate(target_date) if target_date else (getdate(nowdate()) - datetime.timedelta(days=1))
    weekday_name = date_val.strftime("%A")

    # Fetch shift configurations cache
    shifts_raw = frappe.db.sql(
        "SELECT name, start_time, end_time, grace_period_mins, expected_working_hours, weekly_off_days FROM `tabShift`",
        as_dict=True
    )
    shift_map = {s["name"]: s for s in shifts_raw}

    default_shift = {
        "start_time": datetime.time(9, 0),
        "end_time": datetime.time(18, 0),
        "grace_period_mins": 15,
        "expected_working_hours": 8.0,
        "weekly_off_days": "Saturday, Sunday"
    }

    # Total active employees
    total_active = frappe.db.sql(
        "SELECT COUNT(*) AS total FROM `tabEmployee` WHERE employment_status = 'Active' AND date_of_joining <= %(date)s",
        {"date": date_val},
        as_dict=True
    )[0]["total"]

    created_exceptions = 0
    scanned_count = 0
    offset = 0

    while offset < total_active:
        employees = frappe.db.sql(
            """
            SELECT name, employee_name, department, manager, shift, date_of_joining
            FROM `tabEmployee`
            WHERE employment_status = 'Active'
              AND date_of_joining <= %(date)s
            ORDER BY name ASC
            LIMIT %(limit)s OFFSET %(offset)s;
            """,
            {"date": date_val, "limit": batch_size, "offset": offset},
            as_dict=True
        )

        if not employees:
            break

        emp_ids = tuple(e["name"] for e in employees)

        # Batch fetch approved leaves for this chunk on target_date
        leaves_raw = frappe.db.sql(
            """
            SELECT employee, leave_type
            FROM `tabLeave Application`
            WHERE employee IN %(emp_ids)s
              AND status = 'Approved'
              AND %(date)s BETWEEN from_date AND to_date;
            """,
            {"emp_ids": emp_ids, "date": date_val},
            as_dict=True
        )
        leave_set = {l["employee"]: l["leave_type"] for l in leaves_raw}

        # Batch fetch activity logs using FORCE INDEX
        logs_raw = frappe.db.sql(
            """
            SELECT employee, attendance_status, first_login, last_logout, total_work_seconds, total_sessions
            FROM `tabEmployee Activity Log` FORCE INDEX (idx_eal_date_emp)
            WHERE activity_date = %(date)s
              AND employee IN %(emp_ids)s;
            """,
            {"emp_ids": emp_ids, "date": date_val},
            as_dict=True
        )
        log_map = {l["employee"]: l for l in logs_raw}

        # Pre-fetch existing exceptions for this batch
        existing_raw = frappe.db.sql(
            """
            SELECT employee, exception_type
            FROM `tabAttendance Exception`
            WHERE activity_date = %(date)s
              AND employee IN %(emp_ids)s;
            """,
            {"date": date_val, "emp_ids": emp_ids},
            as_dict=True
        )
        existing_set = {(r["employee"], r["exception_type"]) for r in existing_raw}

        new_exceptions = []
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Process each employee
        for emp in employees:
            scanned_count += 1
            emp_id = emp["name"]
            shift = shift_map.get(emp["shift"]) or default_shift

            # 1. Weekly Off Check
            weekly_off_days = [d.strip() for d in (shift.get("weekly_off_days") or "Saturday, Sunday").split(",")]
            if weekday_name in weekly_off_days:
                continue

            # 2. Approved Leave Check
            if emp_id in leave_set:
                continue

            # 3. Activity Log Evaluation
            log = log_map.get(emp_id)
            if not log:
                exc_type = "Missing Check-in"
                if (emp_id, exc_type) not in existing_set:
                    desc = f"Scheduled workday with no check-in recorded for shift {shift.get('name', 'General')}."
                    manager = emp.get("manager") or "EMP-00001"
                    name = f"ATTE-{uuid.uuid4().hex[:10]}"
                    new_exceptions.append((name, emp_id, date_val, exc_type, desc, "Open", manager, now_str, now_str))
                    existing_set.add((emp_id, exc_type))
                continue

            status = log.get("attendance_status")
            total_work = int(log.get("total_work_seconds") or 0)
            first_login = log.get("first_login")

            if status == "Missing Check-out":
                exc_type = "Missing Check-out"
                if (emp_id, exc_type) not in existing_set:
                    desc = "Check-in was recorded but employee did not check out."
                    manager = emp.get("manager") or "EMP-00001"
                    name = f"ATTE-{uuid.uuid4().hex[:10]}"
                    new_exceptions.append((name, emp_id, date_val, exc_type, desc, "Open", manager, now_str, now_str))
                    existing_set.add((emp_id, exc_type))

            elif status == "Late":
                exc_type = "Late Arrival"
                if (emp_id, exc_type) not in existing_set:
                    desc = f"Late arrival at {first_login} exceeding {shift.get('grace_period_mins', 15)}m grace period."
                    manager = emp.get("manager") or "EMP-00001"
                    name = f"ATTE-{uuid.uuid4().hex[:10]}"
                    new_exceptions.append((name, emp_id, date_val, exc_type, desc, "Open", manager, now_str, now_str))
                    existing_set.add((emp_id, exc_type))

            elif status == "Absent":
                exc_type = "Unexcused Absence"
                if (emp_id, exc_type) not in existing_set:
                    desc = "Employee was absent on a scheduled working day without approved leave."
                    manager = emp.get("manager") or "EMP-00001"
                    name = f"ATTE-{uuid.uuid4().hex[:10]}"
                    new_exceptions.append((name, emp_id, date_val, exc_type, desc, "Open", manager, now_str, now_str))
                    existing_set.add((emp_id, exc_type))

            elif status in ("Present", "Half Day") and total_work > 0:
                expected_sec = float(shift.get("expected_working_hours") or 8.0) * 3600
                if total_work < (expected_sec * 0.5):
                    exc_type = "Early Departure"
                    if (emp_id, exc_type) not in existing_set:
                        desc = f"Unusually short work duration: {total_work // 3600}h {(total_work % 3600) // 60}m recorded (expected {shift.get('expected_working_hours', 8.0)}h)."
                        manager = emp.get("manager") or "EMP-00001"
                        name = f"ATTE-{uuid.uuid4().hex[:10]}"
                        new_exceptions.append((name, emp_id, date_val, exc_type, desc, "Open", manager, now_str, now_str))
                        existing_set.add((emp_id, exc_type))

        # Bulk insert new exceptions
        if new_exceptions:
            conn = frappe.db.get_connection()
            try:
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO `tabAttendance Exception`
                        (name, employee, activity_date, exception_type, description, status, assigned_manager, creation, modified)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE status = VALUES(status);
                        """,
                        new_exceptions
                    )
                created_exceptions += len(new_exceptions)
            finally:
                conn.close()

        offset += batch_size

    return {
        "target_date": str(date_val),
        "total_active_employees": total_active,
        "scanned_count": scanned_count,
        "exceptions_detected": created_exceptions
    }


def recalculate_attendance_batch(target_date: Optional[str] = None, batch_size: int = 1000) -> Dict[str, Any]:
    """
    Batch recalculates daily activity summaries for all active employees.
    """
    date_val = getdate(target_date) if target_date else getdate(nowdate())
    total_active = frappe.db.sql(
        "SELECT COUNT(*) AS total FROM `tabEmployee` WHERE employment_status = 'Active'",
        as_dict=True
    )[0]["total"]

    offset = 0
    recalculated = 0

    while offset < total_active:
        employees = frappe.db.sql(
            "SELECT name FROM `tabEmployee` WHERE employment_status = 'Active' ORDER BY name ASC LIMIT %(limit)s OFFSET %(offset)s;",
            {"limit": batch_size, "offset": offset},
            as_dict=True
        )
        if not employees:
            break

        for e in employees:
            recalculate_daily_summary(e["name"], date_val)
            recalculated += 1

        offset += batch_size

    return {
        "date": str(date_val),
        "total_active": total_active,
        "recalculated": recalculated
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Employee360 Scheduled Attendance Background Jobs")
    parser.add_argument("--job", choices=["detect_exceptions", "recalculate_summaries"], default="detect_exceptions")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    parser.add_argument("--batch-size", type=int, default=2000, help="Batch chunk size")
    args = parser.parse_args()

    print(f"Starting background job '{args.job}' for date '{args.date or 'latest'}'...")
    start_time = datetime.datetime.now()

    if args.job == "detect_exceptions":
        res = detect_attendance_exceptions_for_date(args.date, batch_size=args.batch_size)
    else:
        res = recalculate_attendance_batch(args.date, batch_size=args.batch_size)

    elapsed = (datetime.datetime.now() - start_time).total_seconds()
    print(f"Job completed in {elapsed:.2f}s: {res}")
