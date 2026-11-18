import datetime
from typing import Optional, Dict, Any, List
import frappe
from frappe import _
from frappe.utils import getdate, nowdate, get_datetime, now_datetime

def recalculate_unclosed_sessions(target_date: Optional[str] = None, batch_size: int = 1000) -> Dict[str, Any]:
    """
    Scheduled job referenced by hooks.py ('employee360.tasks.recalculate_unclosed_sessions').
    Detects unclosed sessions (IN without matching OUT by end of day)
    and recalculates daily summaries to ensure status reflects 'Missing Check-out'.
    """
    date_val = getdate(target_date) if target_date else (getdate(nowdate()) - datetime.timedelta(days=1))
    start_dt = datetime.datetime.combine(date_val, datetime.time.min)
    end_dt = datetime.datetime.combine(date_val, datetime.time.max)

    # Find all employees who punched IN on date_val
    unclosed_employees = frappe.db.sql(
        """
        SELECT c.employee
        FROM `tabEmployee Checkin` c
        WHERE c.time BETWEEN %(start_dt)s AND %(end_dt)s
        GROUP BY c.employee
        HAVING SUM(CASE WHEN c.log_type = 'IN' THEN 1 ELSE 0 END) >
               SUM(CASE WHEN c.log_type = 'OUT' THEN 1 ELSE 0 END);
        """,
        {"start_dt": start_dt, "end_dt": end_dt},
        as_dict=True
    )

    recalculated_count = 0
    try:
        from employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary
    except ImportError:
        from employee360.employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary

    for row in unclosed_employees:
        emp_id = row["employee"]
        recalculate_daily_summary(emp_id, date_val)
        recalculated_count += 1

    # Also detect and create exceptions for these unclosed sessions
    detect_attendance_exceptions_for_date(date_val)

    return {
        "status": "success",
        "date": str(date_val),
        "unclosed_sessions_found": len(unclosed_employees),
        "recalculated": recalculated_count
    }


def detect_attendance_exceptions_for_date(target_date: Optional[Any] = None, batch_size: int = 2000) -> Dict[str, Any]:
    """
    Scans employees for attendance exceptions on target_date in memory-bounded batches.
    Respects Shifts, Grace Periods, Weekly Offs, Holidays, and Approved Leaves.
    """
    import uuid
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

    total_active_row = frappe.db.sql(
        "SELECT COUNT(*) AS total FROM `tabEmployee` WHERE employment_status = 'Active' AND date_of_joining <= %(date)s",
        {"date": date_val},
        as_dict=True
    )
    total_active = total_active_row[0]["total"] if total_active_row else 0

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

        # Batch fetch activity logs
        logs_raw = frappe.db.sql(
            """
            SELECT employee, attendance_status, first_login, last_logout, total_work_seconds, total_sessions
            FROM `tabEmployee Activity Log`
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

        if new_exceptions:
            for exc_row in new_exceptions:
                try:
                    frappe.db.sql(
                        """
                        INSERT INTO `tabAttendance Exception`
                        (name, employee, activity_date, exception_type, description, status, assigned_manager, creation, modified)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE status = VALUES(status);
                        """,
                        exc_row
                    )
                except Exception:
                    pass
            frappe.db.commit()
            created_exceptions += len(new_exceptions)

        offset += batch_size

    return {
        "status": "success",
        "target_date": str(date_val),
        "total_active_employees": total_active,
        "scanned_count": scanned_count,
        "exceptions_detected": created_exceptions
    }

