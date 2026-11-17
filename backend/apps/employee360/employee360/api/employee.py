import datetime
from typing import Optional
import frappe
from frappe import _
from frappe.utils import getdate

from employee360.api.auth_utils import (
    assert_can_access_employee,
    get_current_employee_id,
    get_session_user_and_roles,
)

@frappe.whitelist()
def get_current_employee():
    """Returns the profile of the currently authenticated employee along with their system roles."""
    user, roles = get_session_user_and_roles()
    emp_id = get_current_employee_id()
    if not emp_id:
        return {
            "user_id": user,
            "roles": roles,
            "employee": None,
            "message": "No linked employee record found for this user account"
        }

    emp = frappe.db.get_value(
        "Employee",
        emp_id,
        [
            "name", "employee_id", "employee_name", "department",
            "designation", "manager", "date_of_joining", "employment_status",
            "shift", "user_id"
        ],
        as_dict=True
    )
    if not emp:
        frappe.throw(_("Employee record not found"), frappe.DoesNotExistError)

    if emp.get("manager"):
        emp["manager_name"] = frappe.db.get_value("Employee", emp["manager"], "employee_name")

    return {
        "user_id": user,
        "roles": roles,
        "employee": emp
    }


@frappe.whitelist()
def get_employee_profile(employee_id: str):
    """Returns the full profile for a specific employee if authorized."""
    if not employee_id:
        frappe.throw(_("Employee ID is required"), frappe.MandatoryError)

    assert_can_access_employee(employee_id)

    emp = frappe.db.get_value(
        "Employee",
        employee_id,
        [
            "name", "employee_id", "employee_name", "department",
            "designation", "manager", "date_of_joining", "employment_status",
            "shift", "user_id"
        ],
        as_dict=True
    )
    if not emp:
        frappe.throw(_("Employee {0} does not exist").format(employee_id), frappe.DoesNotExistError)

    if emp.get("manager"):
        emp["manager_name"] = frappe.db.get_value("Employee", emp["manager"], "employee_name")

    if emp.get("shift"):
        emp["shift_details"] = frappe.db.get_value(
            "Shift", emp["shift"],
            ["shift_name", "start_time", "end_time", "grace_period_mins", "expected_working_hours", "weekly_off_days"],
            as_dict=True
        )

    return emp


@frappe.whitelist()
def get_employee_activity(
    employee_id: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    attendance_status: Optional[str] = None,
    page: int = 1,
    page_size: int = 30
):
    """
    Returns server-paginated attendance activity summaries for an employee.
    Strictly authorized to self, authorized manager, or CEO.
    """
    if not employee_id:
        frappe.throw(_("Employee ID is required"), frappe.MandatoryError)

    assert_can_access_employee(employee_id)

    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    offset = (page - 1) * page_size

    conditions = ["employee = %(employee)s"]
    values = {"employee": employee_id}

    if from_date:
        conditions.append("activity_date >= %(from_date)s")
        values["from_date"] = getdate(from_date)
    if to_date:
        conditions.append("activity_date <= %(to_date)s")
        values["to_date"] = getdate(to_date)
    if attendance_status:
        conditions.append("attendance_status = %(status)s")
        values["status"] = attendance_status

    where_clause = " AND ".join(conditions)

    # Total count for pagination
    count_query = f"SELECT COUNT(*) AS total FROM `tabEmployee Activity Log` WHERE {where_clause}"
    total_records = frappe.db.sql(count_query, values, as_dict=True)[0]["total"]

    # Paginated data
    values["limit"] = page_size
    values["offset"] = offset

    data_query = f"""
    SELECT 
        name,
        employee,
        activity_date,
        attendance_status,
        first_login,
        last_logout,
        total_work_seconds,
        active_seconds,
        total_sessions,
        calculated_at
    FROM `tabEmployee Activity Log`
    WHERE {where_clause}
    ORDER BY activity_date DESC
    LIMIT %(limit)s OFFSET %(offset)s;
    """
    records = frappe.db.sql(data_query, values, as_dict=True)

    return {
        "records": records,
        "total": total_records,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_records + page_size - 1) // page_size
    }


@frappe.whitelist()
def get_employee_attendance_summary(
    employee_id: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    """
    Calculates aggregate metrics for an employee over a date range.
    Uses pure database aggregation.
    Excludes absent, leave, weekend, and missing-checkout when calculating average work duration.
    """
    if not employee_id:
        frappe.throw(_("Employee ID is required"), frappe.MandatoryError)

    assert_can_access_employee(employee_id)

    conditions = ["employee = %(employee)s"]
    values = {"employee": employee_id}

    if from_date:
        conditions.append("activity_date >= %(from_date)s")
        values["from_date"] = getdate(from_date)
    if to_date:
        conditions.append("activity_date <= %(to_date)s")
        values["to_date"] = getdate(to_date)

    where_clause = " AND ".join(conditions)

    query = f"""
    SELECT
        COUNT(*) AS total_days,
        SUM(CASE WHEN attendance_status = 'Present' THEN 1 ELSE 0 END) AS present_count,
        SUM(CASE WHEN attendance_status = 'Late' THEN 1 ELSE 0 END) AS late_count,
        SUM(CASE WHEN attendance_status = 'Half Day' THEN 1 ELSE 0 END) AS half_day_count,
        SUM(CASE WHEN attendance_status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
        SUM(CASE WHEN attendance_status = 'On Leave' THEN 1 ELSE 0 END) AS leave_count,
        SUM(CASE WHEN attendance_status = 'Weekly Off' THEN 1 ELSE 0 END) AS weekly_off_count,
        SUM(CASE WHEN attendance_status = 'Holiday' THEN 1 ELSE 0 END) AS holiday_count,
        SUM(CASE WHEN attendance_status = 'Missing Check-out' THEN 1 ELSE 0 END) AS missing_checkout_count,
        -- Average work duration strictly on valid completed work days
        AVG(CASE WHEN attendance_status IN ('Present', 'Late', 'Half Day') AND total_work_seconds > 0 
                 THEN total_work_seconds ELSE NULL END) AS avg_work_seconds,
        -- Average first login time
        SEC_TO_TIME(AVG(CASE WHEN attendance_status IN ('Present', 'Late', 'Half Day') AND first_login IS NOT NULL 
                             THEN TIME_TO_SEC(first_login) ELSE NULL END)) AS avg_first_login,
        -- Average last logout time
        SEC_TO_TIME(AVG(CASE WHEN attendance_status IN ('Present', 'Late', 'Half Day') AND last_logout IS NOT NULL 
                             THEN TIME_TO_SEC(last_logout) ELSE NULL END)) AS avg_last_logout
    FROM `tabEmployee Activity Log`
    WHERE {where_clause};
    """
    res = frappe.db.sql(query, values, as_dict=True)[0]

    total_days = int(res["total_days"] or 0)
    weekly_off = int(res["weekly_off_count"] or 0)
    holiday = int(res["holiday_count"] or 0)
    workable_days = total_days - weekly_off - holiday
    attended_days = float(res["present_count"] or 0) + float(res["late_count"] or 0) + (float(res["half_day_count"] or 0) * 0.5)

    attendance_percentage = 0.0
    if workable_days > 0:
        attendance_percentage = round((attended_days / float(workable_days)) * 100, 2)

    avg_work_sec = int(res["avg_work_seconds"] or 0)
    hours = avg_work_sec // 3600
    minutes = (avg_work_sec % 3600) // 60

    # Monthly projection based on 22 working days
    avg_monthly_sec = int(avg_work_sec * 22)
    m_hours = avg_monthly_sec // 3600
    m_minutes = (avg_monthly_sec % 3600) // 60

    return {
        "employee_id": employee_id,
        "total_days": total_days,
        "present_count": int(res["present_count"] or 0),
        "late_count": int(res["late_count"] or 0),
        "half_day_count": int(res["half_day_count"] or 0),
        "absent_count": int(res["absent_count"] or 0),
        "leave_count": int(res["leave_count"] or 0),
        "weekly_off_count": weekly_off,
        "holiday_count": holiday,
        "missing_checkout_count": int(res["missing_checkout_count"] or 0),
        "attendance_percentage": attendance_percentage,
        "avg_daily_work_seconds": avg_work_sec,
        "avg_daily_work_formatted": f"{hours}h {minutes}m",
        "avg_monthly_work_seconds": avg_monthly_sec,
        "avg_monthly_work_formatted": f"{m_hours}h {m_minutes}m",
        "avg_first_login": str(res["avg_first_login"])[:8] if res["avg_first_login"] else None,
        "avg_last_logout": str(res["avg_last_logout"])[:8] if res["avg_last_logout"] else None
    }


@frappe.whitelist()
def get_employee_attendance_trend(employee_id: str, days: int = 30):
    """Returns day-by-day attendance trends for an employee."""
    if not employee_id:
        frappe.throw(_("Employee ID is required"), frappe.MandatoryError)

    assert_can_access_employee(employee_id)

    days = min(365, max(7, int(days)))
    
    query = """
    SELECT 
        activity_date,
        attendance_status,
        total_work_seconds,
        first_login,
        last_logout,
        total_sessions
    FROM `tabEmployee Activity Log`
    WHERE employee = %(employee)s
    ORDER BY activity_date DESC
    LIMIT %(limit)s;
    """
    records = frappe.db.sql(query, {"employee": employee_id, "limit": days}, as_dict=True)
    records.reverse()  # Return in chronological order
    return records


@frappe.whitelist()
def get_employee_leave_history(employee_id: str, page: int = 1, page_size: int = 20):
    """Returns paginated leave applications for an employee."""
    if not employee_id:
        frappe.throw(_("Employee ID is required"), frappe.MandatoryError)

    assert_can_access_employee(employee_id)

    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    offset = (page - 1) * page_size

    total = frappe.db.sql(
        "SELECT COUNT(*) AS total FROM `tabLeave Application` WHERE employee = %(employee)s",
        {"employee": employee_id},
        as_dict=True
    )[0]["total"]

    records = frappe.db.sql(
        """
        SELECT 
            name, employee, leave_type, from_date, to_date, 
            reason, status, approver, approval_comments, applied_at, decision_at
        FROM `tabLeave Application`
        WHERE employee = %(employee)s
        ORDER BY applied_at DESC
        LIMIT %(limit)s OFFSET %(offset)s;
        """,
        {"employee": employee_id, "limit": page_size, "offset": offset},
        as_dict=True
    )

    return {
        "records": records,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@frappe.whitelist()
def get_employee_leave_balance(employee_id: Optional[str] = None):
    """
    Returns annual leave allocations, used days, and remaining balances per leave type.
    """
    user, roles = get_session_user_and_roles()
    current_emp = get_current_employee_id()
    emp_id = employee_id or current_emp

    if not emp_id:
        frappe.throw(_("Employee ID is required"), frappe.MandatoryError)

    assert_can_access_employee(emp_id)

    entitlements = {
        "Casual Leave": 12,
        "Sick Leave": 10,
        "Earned Leave": 15,
        "Unpaid Leave": 90
    }

    current_year = datetime.date.today().year

    used_rows = frappe.db.sql(
        """
        SELECT 
            leave_type,
            SUM(DATEDIFF(to_date, from_date) + 1) AS used_days
        FROM `tabLeave Application`
        WHERE employee = %(employee)s
          AND status = 'Approved'
          AND YEAR(from_date) = %(year)s
        GROUP BY leave_type;
        """,
        {"employee": emp_id, "year": current_year},
        as_dict=True
    )
    used_map = {r["leave_type"]: int(r["used_days"] or 0) for r in used_rows}

    pending_rows = frappe.db.sql(
        """
        SELECT 
            leave_type,
            SUM(DATEDIFF(to_date, from_date) + 1) AS pending_days
        FROM `tabLeave Application`
        WHERE employee = %(employee)s
          AND status = 'Pending'
          AND YEAR(from_date) = %(year)s
        GROUP BY leave_type;
        """,
        {"employee": emp_id, "year": current_year},
        as_dict=True
    )
    pending_map = {r["leave_type"]: int(r["pending_days"] or 0) for r in pending_rows}

    balance_summary = []
    for ltype, allocated in entitlements.items():
        used = used_map.get(ltype, 0)
        pending = pending_map.get(ltype, 0)
        remaining = max(0, allocated - used)
        balance_summary.append({
            "leave_type": ltype,
            "allocated": allocated,
            "used": used,
            "pending": pending,
            "remaining": remaining
        })

    return balance_summary


@frappe.whitelist()
def apply_leave_application(
    leave_type: str,
    from_date: str,
    to_date: str,
    reason: str,
    employee_id: Optional[str] = None
):
    """
    Submits a leave application with full validation and overlap prevention.
    """
    user, roles = get_session_user_and_roles()
    current_emp = get_current_employee_id()
    from employee360.api.auth_utils import is_ceo
    emp_id = employee_id if (employee_id and is_ceo(roles)) else current_emp

    if not emp_id:
        frappe.throw(_("No employee profile found for user account"), frappe.PermissionError)

    if not leave_type or not from_date or not to_date or not reason or not reason.strip():
        frappe.throw(_("Leave Type, From Date, To Date, and Reason are mandatory"), frappe.MandatoryError)

    valid_types = ("Casual Leave", "Sick Leave", "Earned Leave", "Unpaid Leave")
    if leave_type not in valid_types:
        frappe.throw(_("Invalid leave type '{0}'. Must be one of {1}").format(leave_type, valid_types), frappe.ValidationError)

    from_dt = frappe.utils.getdate(from_date)
    to_dt = frappe.utils.getdate(to_date)

    if to_dt < from_dt:
        frappe.throw(_("To Date ({0}) cannot be before From Date ({1})").format(to_date, from_date), frappe.ValidationError)

    overlap = frappe.db.sql(
        """
        SELECT name, from_date, to_date, status, leave_type
        FROM `tabLeave Application`
        WHERE employee = %(employee)s
          AND status IN ('Approved', 'Pending')
          AND NOT (to_date < %(from_date)s OR from_date > %(to_date)s)
        LIMIT 1;
        """,
        {"employee": emp_id, "from_date": from_dt, "to_date": to_dt},
        as_dict=True
    )
    if overlap:
        frappe.throw(
            _("Overlapping leave application found ({0}) for {1} from {2} to {3} with status '{4}'").format(
                overlap[0]["name"], overlap[0]["leave_type"], overlap[0]["from_date"], overlap[0]["to_date"], overlap[0]["status"]
            ),
            frappe.DuplicateEntryError
        )

    doc = frappe.get_doc({
        "doctype": "Leave Application",
        "employee": emp_id,
        "leave_type": leave_type,
        "from_date": from_dt,
        "to_date": to_dt,
        "reason": reason.strip(),
        "status": "Pending",
        "applied_at": frappe.utils.now_datetime()
    })
    doc.flags.ignore_permissions = True
    doc.insert()

    return {
        "message": "Leave application submitted successfully",
        "leave_id": doc.name,
        "status": "Pending"
    }


@frappe.whitelist()
def cancel_leave_application(leave_id: str):
    """
    Cancels a leave application.
    Enforces that only Pending applications (or future approved leaves) can be cancelled,
    and updates activity logs to restore normal attendance status.
    """
    if not leave_id:
        frappe.throw(_("Leave ID is required"), frappe.MandatoryError)

    user, roles = get_session_user_and_roles()
    current_emp = get_current_employee_id()
    from employee360.api.auth_utils import is_ceo, assert_can_manage_employee

    leave_row = frappe.db.sql(
        "SELECT name, employee, from_date, to_date, status FROM `tabLeave Application` WHERE name = %s",
        (leave_id,),
        as_dict=True
    )
    if not leave_row:
        frappe.throw(_("Leave application {0} not found").format(leave_id), frappe.ValidationError)

    leave_data = leave_row[0]
    target_emp = leave_data["employee"]

    if target_emp != current_emp and not is_ceo(roles):
        assert_can_manage_employee(target_emp)

    if leave_data["status"] == "Cancelled":
        frappe.throw(_("Leave application is already cancelled"), frappe.ValidationError)
    if leave_data["status"] == "Rejected":
        frappe.throw(_("Cannot cancel a rejected leave application"), frappe.ValidationError)

    today = frappe.utils.getdate(frappe.utils.nowdate())
    if leave_data["status"] == "Approved" and leave_data["from_date"] < today:
        frappe.throw(_("Cannot cancel an approved leave application that has already commenced"), frappe.ValidationError)

    frappe.db.set_value(
        "Leave Application",
        leave_id,
        {
            "status": "Cancelled",
            "modified": frappe.utils.now_datetime(),
            "modified_by": current_emp or user
        }
    )

    from employee360.employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary
    curr = frappe.utils.getdate(leave_data["from_date"])
    end = min(today, frappe.utils.getdate(leave_data["to_date"]))
    while curr <= end:
        recalculate_daily_summary(target_emp, curr)
        curr += datetime.timedelta(days=1)

    return {
        "message": "Leave application cancelled successfully",
        "leave_id": leave_id,
        "status": "Cancelled"
    }
