import datetime
from typing import Optional
import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, nowdate, get_datetime

from employee360.api.auth_utils import (
    get_current_employee_id,
    get_session_user_and_roles,
    assert_can_manage_employee,
    is_ceo,
    is_manager
)
from employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary


def _parse_time_val(time_val) -> Optional[datetime.time]:
    if not time_val:
        return None
    if isinstance(time_val, datetime.time):
        return time_val
    if isinstance(time_val, datetime.timedelta):
        return (datetime.datetime.min + time_val).time()
    s = str(time_val).strip()
    parts = s.split(":")
    try:
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        sec = int(parts[2].split(".")[0]) if len(parts) > 2 else 0
        return datetime.time(h, m, sec)
    except Exception:
        return datetime.time(9, 0)


def _get_active_employee_or_throw():
    emp_id = get_current_employee_id()
    if not emp_id:
        frappe.throw(_("No employee profile linked to your user account"), frappe.PermissionError)

    status = frappe.db.get_value("Employee", emp_id, "employment_status")
    if status != "Active":
        frappe.throw(
            _("Employment status is '{0}'. Attendance operations are not permitted.").format(status),
            frappe.PermissionError
        )

    return emp_id


@frappe.whitelist(methods=["POST"])
def check_in(
    device_info: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    gps_accuracy: Optional[float] = None,
    ip_address: Optional[str] = None
):
    """
    Records a live IN punch for the authenticated employee with concurrency protection.
    Uses row-level locking on tabEmployee to serialize concurrent check-in requests.
    """
    emp_id = _get_active_employee_or_throw()

    try:
        # Row-level lock on the Employee record to serialize concurrent punch attempts
        frappe.db.sql("SELECT name FROM `tabEmployee` WHERE name = %s FOR UPDATE;", (emp_id,))

        now_time = now_datetime()
        today = now_time.date()

        start_dt = datetime.datetime.combine(today, datetime.time.min)
        end_dt = datetime.datetime.combine(today, datetime.time.max)

        punches = frappe.db.sql(
            """
            SELECT name, time, log_type
            FROM `tabEmployee Checkin`
            WHERE employee = %(employee)s
              AND time BETWEEN %(start_dt)s AND %(end_dt)s
            ORDER BY time ASC;
            """,
            {"employee": emp_id, "start_dt": start_dt, "end_dt": end_dt},
            as_dict=True
        )

        if punches:
            last_punch = punches[-1]
            if last_punch.get("log_type") == "IN":
                frappe.throw(
                    _("You are already checked in. Please check out before checking in again."),
                    frappe.ValidationError
                )

            last_punch_time = get_datetime(last_punch.get("time"))
            delta_seconds = abs((now_time - last_punch_time).total_seconds())
            if delta_seconds < 10:
                frappe.throw(
                    _("A punch was already recorded {0} seconds ago. Please wait before punching again.").format(int(delta_seconds)),
                    frappe.DuplicateEntryError
                )

        # Create Checkin Document
        checkin = frappe.get_doc({
            "doctype": "Employee Checkin",
            "employee": emp_id,
            "time": now_time,
            "log_type": "IN",
            "source": "Web",
            "device_info": device_info or "Web Portal",
            "ip_address": ip_address,
            "latitude": latitude,
            "longitude": longitude,
            "gps_accuracy": gps_accuracy
        })
        checkin.flags.ignore_permissions = True
        checkin.insert()
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        raise

    return get_today_attendance()


@frappe.whitelist(methods=["POST"])
def check_out(
    device_info: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    gps_accuracy: Optional[float] = None,
    ip_address: Optional[str] = None
):
    """
    Records a live OUT punch for the authenticated employee with concurrency protection.
    Requires an active open IN session.
    """
    emp_id = _get_active_employee_or_throw()

    try:
        frappe.db.sql("SELECT name FROM `tabEmployee` WHERE name = %s FOR UPDATE;", (emp_id,))

        now_time = now_datetime()
        today = now_time.date()

        start_dt = datetime.datetime.combine(today, datetime.time.min)
        end_dt = datetime.datetime.combine(today, datetime.time.max)

        punches = frappe.db.sql(
            """
            SELECT name, time, log_type
            FROM `tabEmployee Checkin`
            WHERE employee = %(employee)s
              AND time BETWEEN %(start_dt)s AND %(end_dt)s
            ORDER BY time ASC;
            """,
            {"employee": emp_id, "start_dt": start_dt, "end_dt": end_dt},
            as_dict=True
        )

        if not punches or punches[-1].get("log_type") != "IN":
            frappe.throw(
                _("No active open check-in session found to check out from. Please check in first."),
                frappe.ValidationError
            )

        last_punch = punches[-1]
        last_punch_time = get_datetime(last_punch.get("time"))
        delta_seconds = abs((now_time - last_punch_time).total_seconds())
        if delta_seconds < 10:
            frappe.throw(
                _("Check-in was recorded {0} seconds ago. Please wait before checking out.").format(int(delta_seconds)),
                frappe.DuplicateEntryError
            )

        checkin = frappe.get_doc({
            "doctype": "Employee Checkin",
            "employee": emp_id,
            "time": now_time,
            "log_type": "OUT",
            "source": "Web",
            "device_info": device_info or "Web Portal",
            "ip_address": ip_address,
            "latitude": latitude,
            "longitude": longitude,
            "gps_accuracy": gps_accuracy
        })
        checkin.flags.ignore_permissions = True
        checkin.insert()
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        raise

    return get_today_attendance()


@frappe.whitelist()
def get_today_attendance():
    """
    Returns today's attendance summary and punch history for the authenticated employee.
    """
    emp_id = get_current_employee_id()
    if not emp_id:
        return None

    today = getdate(nowdate())
    recalculate_daily_summary(emp_id, today)

    log = frappe.db.get_value(
        "Employee Activity Log",
        {"employee": emp_id, "activity_date": today},
        [
            "name", "employee", "activity_date", "attendance_status",
            "first_login", "last_logout", "total_work_seconds",
            "active_seconds", "total_sessions", "calculated_at",
            "is_regularized"
        ],
        as_dict=True
    )

    start_dt = datetime.datetime.combine(today, datetime.time.min)
    end_dt = datetime.datetime.combine(today, datetime.time.max)

    punches = frappe.db.sql(
        """
        SELECT name, time, log_type, source, ip_address, device_info, gps_accuracy
        FROM `tabEmployee Checkin`
        WHERE employee = %(employee)s
          AND time BETWEEN %(start_dt)s AND %(end_dt)s
        ORDER BY time ASC;
        """,
        {"employee": emp_id, "start_dt": start_dt, "end_dt": end_dt},
        as_dict=True
    )

    last_punch = punches[-1] if punches else None
    current_state = "Checked In" if (last_punch and last_punch["log_type"] == "IN") else "Checked Out"

    work_sec = int(log.get("total_work_seconds") or 0) if log else 0
    formatted_work = f"{work_sec // 3600}h {(work_sec % 3600) // 60}m"

    return {
        "employee_id": emp_id,
        "date": str(today),
        "current_state": current_state,
        "attendance_status": log.get("attendance_status") if log else "Pending",
        "first_login": str(log.get("first_login")) if (log and log.get("first_login")) else None,
        "last_logout": str(log.get("last_logout")) if (log and log.get("last_logout")) else None,
        "total_work_seconds": work_sec,
        "total_work_formatted": formatted_work,
        "total_sessions": int(log.get("total_sessions") or 0) if log else 0,
        "is_regularized": bool(log.get("is_regularized")) if log else False,
        "punches": punches
    }


@frappe.whitelist(methods=["POST"])
def request_attendance_correction(
    activity_date: str,
    exception_type: str = "Missed Check-out",
    requested_status: str = "Present",
    reason: str = "",
    requested_in_time: Optional[str] = None,
    requested_out_time: Optional[str] = None
):
    """
    Submits an attendance correction request for managerial review.
    Captures complete original values for an immutable audit trail.
    """
    emp_id = _get_active_employee_or_throw()

    if not activity_date or not reason:
        frappe.throw(_("Activity Date and Reason are required for attendance regularization"), frappe.MandatoryError)

    date_val = getdate(activity_date)
    today = getdate(nowdate())

    if date_val > today:
        frappe.throw(_("Cannot request regularization for future dates"), frappe.ValidationError)

    manager = frappe.db.get_value("Employee", emp_id, "manager")
    if not manager:
        manager = "EMP-00001"  # Route to CEO if no direct manager

    orig_log = frappe.db.get_value(
        "Employee Activity Log",
        {"employee": emp_id, "activity_date": date_val},
        ["attendance_status", "first_login", "last_logout", "total_work_seconds"],
        as_dict=True
    )
    orig_status = orig_log.get("attendance_status") if orig_log else "Absent"

    valid_types = {
        "Missed Check-in": "Missing Check-in",
        "Missing Check-in": "Missing Check-in",
        "Missed Check-out": "Missing Check-out",
        "Missing Check-out": "Missing Check-out",
        "Late Arrival": "Late Arrival",
        "Early Departure": "Early Departure",
        "Incorrect Attendance Time": "Unexcused Absence",
        "Unexcused Absence": "Unexcused Absence"
    }
    mapped_type = valid_types.get(exception_type, "Missing Check-out")

    desc = f"Regularization requested to '{requested_status}'. Reason: {reason}"
    if requested_in_time or requested_out_time:
        desc += f" (Times: IN={requested_in_time or 'N/A'}, OUT={requested_out_time or 'N/A'})"

    exception_doc = frappe.get_doc({
        "doctype": "Attendance Exception",
        "employee": emp_id,
        "activity_date": date_val,
        "exception_type": mapped_type,
        "description": desc,
        "status": "Pending Review",
        "assigned_manager": manager,
        "original_status": orig_status,
        "requested_status": requested_status,
        "requested_in_time": requested_in_time,
        "requested_out_time": requested_out_time
    })
    exception_doc.flags.ignore_permissions = True
    exception_doc.insert()

    return {
        "message": "Attendance regularization request submitted successfully",
        "exception_id": exception_doc.name,
        "assigned_manager": manager
    }


@frappe.whitelist(methods=["POST"])
def approve_attendance_exception(exception_id: str, comments: Optional[str] = None):
    """
    Manager or CEO approval of an attendance regularization request.
    Applies the correction with full audit logging and updates the activity log.
    """
    if not exception_id:
        frappe.throw(_("Exception ID is required"), frappe.MandatoryError)

    user, roles = get_session_user_and_roles()
    current_emp = get_current_employee_id()

    exc = frappe.db.get_value(
        "Attendance Exception",
        exception_id,
        [
            "name", "employee", "activity_date", "exception_type",
            "description", "status", "assigned_manager", "requested_status",
            "requested_in_time", "requested_out_time"
        ],
        as_dict=True
    )
    if not exc:
        frappe.throw(_("Attendance exception {0} not found").format(exception_id), frappe.ValidationError)

    target_emp = exc["employee"]
    assert_can_manage_employee(target_emp)

    if exc["status"] in ("Resolved", "Ignored"):
        frappe.throw(_("Exception is already {0}").format(exc["status"]), frappe.ValidationError)

    now = now_datetime()
    resolved_by = current_emp or user
    resolution_comments = comments or "Approved by Manager"

    frappe.db.set_value(
        "Attendance Exception",
        exception_id,
        {
            "status": "Resolved",
            "resolved_by": resolved_by,
            "resolved_at": now,
            "resolution_comments": resolution_comments
        }
    )

    activity_date = exc["activity_date"]
    req_status = exc.get("requested_status") or "Present"

    parsed_in = _parse_time_val(exc.get("requested_in_time"))
    if parsed_in:
        in_dt = datetime.datetime.combine(activity_date, parsed_in)
        existing_in = frappe.db.sql(
            "SELECT name FROM `tabEmployee Checkin` WHERE employee = %(employee)s AND time = %(time)s",
            {"employee": target_emp, "time": in_dt}
        )
        if not existing_in:
            in_punch = frappe.get_doc({
                "doctype": "Employee Checkin",
                "employee": target_emp,
                "time": in_dt,
                "log_type": "IN",
                "source": "Admin Correction",
                "source_record_id": exception_id,
                "device_info": f"Regularization approved by {resolved_by}"
            })
            in_punch.flags.ignore_permissions = True
            in_punch.insert()

    parsed_out = _parse_time_val(exc.get("requested_out_time"))
    if parsed_out:
        out_dt = datetime.datetime.combine(activity_date, parsed_out)
        existing_out = frappe.db.sql(
            "SELECT name FROM `tabEmployee Checkin` WHERE employee = %(employee)s AND time = %(time)s",
            {"employee": target_emp, "time": out_dt}
        )
        if not existing_out:
            out_punch = frappe.get_doc({
                "doctype": "Employee Checkin",
                "employee": target_emp,
                "time": out_dt,
                "log_type": "OUT",
                "source": "Admin Correction",
                "source_record_id": exception_id,
                "device_info": f"Regularization approved by {resolved_by}"
            })
            out_punch.flags.ignore_permissions = True
            out_punch.insert()

    recalculate_daily_summary(target_emp, activity_date)

    eal_name = frappe.db.get_value(
        "Employee Activity Log",
        {"employee": target_emp, "activity_date": activity_date},
        "name"
    )
    if eal_name:
        frappe.db.set_value(
            "Employee Activity Log",
            eal_name,
            {
                "attendance_status": req_status,
                "is_regularized": 1,
                "regularization_exception": exception_id
            }
        )

    frappe.db.commit()

    return {
        "message": "Attendance exception approved and regularized successfully",
        "exception_id": exception_id,
        "regularized_status": req_status
    }


@frappe.whitelist(methods=["POST"])
def reject_attendance_exception(exception_id: str, comments: Optional[str] = None):
    """
    Manager or CEO rejection of an attendance regularization request.
    Preserves audit reason and leaves the daily summary unchanged.
    """
    if not exception_id:
        frappe.throw(_("Exception ID is required"), frappe.MandatoryError)

    user, _ = get_session_user_and_roles()
    current_emp = get_current_employee_id()

    exc = frappe.db.get_value(
        "Attendance Exception",
        exception_id,
        ["name", "employee", "status"],
        as_dict=True
    )
    if not exc:
        frappe.throw(_("Attendance exception {0} not found").format(exception_id), frappe.ValidationError)

    assert_can_manage_employee(exc["employee"])

    if exc["status"] in ("Resolved", "Ignored"):
        frappe.throw(_("Exception is already {0}").format(exc["status"]), frappe.ValidationError)

    now = now_datetime()
    resolved_by = current_emp or user
    resolution_comments = comments or "Rejected by Manager"

    frappe.db.set_value(
        "Attendance Exception",
        exception_id,
        {
            "status": "Ignored",
            "resolved_by": resolved_by,
            "resolved_at": now,
            "resolution_comments": resolution_comments
        }
    )
    frappe.db.commit()

    return {
        "message": "Attendance exception request rejected",
        "exception_id": exception_id
    }
