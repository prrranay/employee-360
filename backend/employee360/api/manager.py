import datetime
from typing import Optional
import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, nowdate

from employee360.api.auth_utils import (
    assert_can_manage_employee,
    get_current_employee_id,
    get_manager_team_ids,
    get_session_user_and_roles,
    is_ceo,
    is_manager,
)

def require_manager():
    user, roles = get_session_user_and_roles()
    if not is_manager(roles):
        frappe.throw(_("Unauthorized: Manager privileges required"), frappe.PermissionError)


@frappe.whitelist()
def get_manager_team(include_indirect: int = 1, manager_id: Optional[str] = None):
    """Returns direct and indirect reports for the logged in manager, or target manager if CEO."""
    require_manager()
    user, roles = get_session_user_and_roles()

    if manager_id and is_ceo(roles):
        target_emp = manager_id
    else:
        target_emp = get_current_employee_id()

    if not target_emp:
        frappe.throw(_("No employee profile found for user"), frappe.PermissionError)

    team_ids = get_manager_team_ids(target_emp, include_indirect=bool(int(include_indirect)))
    if not team_ids:
        return []

    team_members = frappe.db.sql(
        """
        SELECT 
            name,
            employee_id,
            employee_name,
            department,
            designation,
            manager,
            employment_status,
            date_of_joining
        FROM `tabEmployee`
        WHERE name IN %(team_ids)s
        ORDER BY employee_name ASC;
        """,
        {"team_ids": tuple(team_ids)},
        as_dict=True
    )
    return team_members


@frappe.whitelist()
def get_team_dashboard_summary(
    target_date: Optional[str] = None,
    include_indirect: int = 1,
    manager_id: Optional[str] = None
):
    """Calculates team attendance KPIs for a given date for logged in manager or target manager."""
    require_manager()
    user, roles = get_session_user_and_roles()

    if manager_id and is_ceo(roles):
        target_emp = manager_id
    else:
        target_emp = get_current_employee_id()

    team_ids = get_manager_team_ids(target_emp, include_indirect=bool(int(include_indirect)))
    
    if not team_ids:
        return {
            "date": str(target_date or nowdate()),
            "team_size": 0,
            "present": 0, "late": 0, "half_day": 0,
            "absent": 0, "on_leave": 0, "weekly_off": 0,
            "missing_checkout": 0, "attendance_rate": 0.0,
            "avg_work_formatted": "0h 0m"
        }

    date_val = getdate(target_date) if target_date else getdate(nowdate())

    query = """
    SELECT 
        attendance_status,
        COUNT(*) AS count
    FROM `tabEmployee Activity Log`
    WHERE employee IN %(team_ids)s
      AND activity_date = %(date)s
    GROUP BY attendance_status;
    """
    rows = frappe.db.sql(query, {"team_ids": tuple(team_ids), "date": date_val}, as_dict=True)
    counts = {r["attendance_status"]: r["count"] for r in rows}

    present = counts.get("Present", 0)
    late = counts.get("Late", 0)
    half_day = counts.get("Half Day", 0)
    absent = counts.get("Absent", 0)
    on_leave = counts.get("On Leave", 0)
    weekly_off = counts.get("Weekly Off", 0)
    missing_checkout = counts.get("Missing Check-out", 0)

    team_size = len(team_ids)
    workable = team_size - weekly_off
    attended = present + late + (half_day * 0.5)
    attendance_rate = round((attended / workable) * 100, 2) if workable > 0 else 0.0

    avg_row = frappe.db.sql(
        """
        SELECT AVG(total_work_seconds) AS avg_sec
        FROM `tabEmployee Activity Log`
        WHERE employee IN %(team_ids)s
          AND activity_date = %(date)s
          AND attendance_status IN ('Present', 'Late', 'Half Day')
          AND total_work_seconds > 0;
        """,
        {"team_ids": tuple(team_ids), "date": date_val},
        as_dict=True
    )
    avg_sec = int(avg_row[0]["avg_sec"] or 0) if avg_row else 0

    return {
        "date": str(date_val),
        "team_size": team_size,
        "present": present,
        "late": late,
        "half_day": half_day,
        "absent": absent,
        "on_leave": on_leave,
        "weekly_off": weekly_off,
        "missing_checkout": missing_checkout,
        "attendance_rate": attendance_rate,
        "avg_work_seconds": avg_sec,
        "avg_work_formatted": f"{avg_sec // 3600}h {(avg_sec % 3600) // 60}m"
    }


@frappe.whitelist()
def get_team_attendance_trend(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    days: int = 14,
    include_indirect: int = 1
):
    """Returns daily attendance trends for the manager's team."""
    require_manager()
    current_emp = get_current_employee_id()
    team_ids = get_manager_team_ids(current_emp, include_indirect=bool(int(include_indirect)))
    
    if not team_ids:
        return []

    if to_date:
        end_date = getdate(to_date)
    else:
        end_date = getdate(nowdate())

    if from_date:
        start_date = getdate(from_date)
    else:
        start_date = end_date - datetime.timedelta(days=max(7, min(60, int(days))))

    query = """
    SELECT 
        activity_date,
        SUM(CASE WHEN attendance_status = 'Present' THEN 1 ELSE 0 END) AS present,
        SUM(CASE WHEN attendance_status = 'Late' THEN 1 ELSE 0 END) AS late,
        SUM(CASE WHEN attendance_status = 'Half Day' THEN 1 ELSE 0 END) AS half_day,
        SUM(CASE WHEN attendance_status = 'Absent' THEN 1 ELSE 0 END) AS absent,
        SUM(CASE WHEN attendance_status = 'On Leave' THEN 1 ELSE 0 END) AS on_leave,
        SUM(CASE WHEN attendance_status = 'Weekly Off' THEN 1 ELSE 0 END) AS weekly_off,
        SUM(CASE WHEN attendance_status = 'Missing Check-out' THEN 1 ELSE 0 END) AS missing_checkout
    FROM `tabEmployee Activity Log`
    WHERE employee IN %(team_ids)s
      AND activity_date BETWEEN %(start_date)s AND %(end_date)s
    GROUP BY activity_date
    ORDER BY activity_date ASC;
    """
    trend = frappe.db.sql(
        query,
        {"team_ids": tuple(team_ids), "start_date": start_date, "end_date": end_date},
        as_dict=True
    )
    return trend


@frappe.whitelist()
def get_team_attendance_exceptions(
    target_date: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    include_indirect: int = 1
):
    """Returns attendance exceptions for the manager's team members."""
    require_manager()
    current_emp = get_current_employee_id()
    team_ids = get_manager_team_ids(current_emp, include_indirect=bool(int(include_indirect)))
    
    if not team_ids:
        return {"records": [], "total": 0, "page": 1, "page_size": page_size, "total_pages": 0}

    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    offset = (page - 1) * page_size

    conditions = ["ae.employee IN %(team_ids)s"]
    values = {"team_ids": tuple(team_ids)}

    if target_date:
        conditions.append("ae.activity_date = %(date)s")
        values["date"] = getdate(target_date)
    if status:
        conditions.append("ae.status = %(status)s")
        values["status"] = status

    where_clause = " AND ".join(conditions)

    count_query = f"SELECT COUNT(*) AS total FROM `tabAttendance Exception` ae WHERE {where_clause}"
    total = frappe.db.sql(count_query, values, as_dict=True)[0]["total"]

    values["limit"] = page_size
    values["offset"] = offset

    data_query = f"""
    SELECT 
        ae.name,
        ae.employee,
        e.employee_name,
        e.department,
        ae.activity_date,
        ae.exception_type,
        ae.description,
        ae.status,
        ae.assigned_manager
    FROM `tabAttendance Exception` ae
    JOIN `tabEmployee` e ON ae.employee = e.name
    WHERE {where_clause}
    ORDER BY ae.activity_date DESC
    LIMIT %(limit)s OFFSET %(offset)s;
    """
    records = frappe.db.sql(data_query, values, as_dict=True)

    return {
        "records": records,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@frappe.whitelist()
def get_team_leave_overview(status: Optional[str] = None, page: int = 1, page_size: int = 25):
    """Returns leave applications submitted by the manager's team members."""
    require_manager()
    current_emp = get_current_employee_id()
    team_ids = get_manager_team_ids(current_emp, include_indirect=True)
    
    if not team_ids:
        return {"records": [], "total": 0, "page": 1, "page_size": page_size, "total_pages": 0}

    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    offset = (page - 1) * page_size

    conditions = ["la.employee IN %(team_ids)s"]
    values = {"team_ids": tuple(team_ids)}

    if status:
        conditions.append("la.status = %(status)s")
        values["status"] = status

    where_clause = " AND ".join(conditions)

    count_query = f"SELECT COUNT(*) AS total FROM `tabLeave Application` la WHERE {where_clause}"
    total = frappe.db.sql(count_query, values, as_dict=True)[0]["total"]

    values["limit"] = page_size
    values["offset"] = offset

    data_query = f"""
    SELECT 
        la.name,
        la.employee,
        e.employee_name,
        e.department,
        la.leave_type,
        la.from_date,
        la.to_date,
        la.reason,
        la.status,
        la.applied_at,
        la.decision_at,
        la.approver,
        la.approval_comments
    FROM `tabLeave Application` la
    JOIN `tabEmployee` e ON la.employee = e.name
    WHERE {where_clause}
    ORDER BY CASE WHEN la.status = 'Pending' THEN 1 ELSE 2 END, la.applied_at DESC
    LIMIT %(limit)s OFFSET %(offset)s;
    """
    records = frappe.db.sql(data_query, values, as_dict=True)

    return {
        "records": records,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@frappe.whitelist()
def approve_leave_application(leave_id: str, comments: Optional[str] = None):
    """
    Approves a team member's leave application.
    Security: Strictly validates managerial hierarchy and prevents self-approval.
    """
    require_manager()
    if not leave_id:
        frappe.throw(_("Leave application ID is required"), frappe.MandatoryError)

    leave_doc = frappe.get_doc("Leave Application", leave_id)
    if not leave_doc:
        frappe.throw(_("Leave application not found"), frappe.DoesNotExistError)

    if leave_doc.status != "Pending":
        frappe.throw(_("Leave application is already {0}").format(leave_doc.status), frappe.ValidationError)

    # Security check: must manage employee and cannot approve self
    assert_can_manage_employee(leave_doc.employee)

    current_emp = get_current_employee_id()
    leave_doc.status = "Approved"
    leave_doc.approver = current_emp
    leave_doc.approval_comments = comments or "Approved"
    leave_doc.decision_at = now_datetime()
    leave_doc.save()

    # Recalculate daily attendance summaries so approved dates reflect 'On Leave'
    curr = getdate(leave_doc.from_date)
    end = getdate(leave_doc.to_date)
    try:
        from employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary
    except ImportError:
        from employee360.employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary
    while curr <= end:
        recalculate_daily_summary(leave_doc.employee, curr)
        curr += datetime.timedelta(days=1)

    return {"message": "Leave application approved successfully", "leave_id": leave_doc.name, "status": "Approved"}


@frappe.whitelist()
def reject_leave_application(leave_id: str, comments: Optional[str] = None):
    """
    Rejects a team member's leave application.
    Security: Strictly validates managerial hierarchy and prevents self-rejection.
    """
    require_manager()
    if not leave_id:
        frappe.throw(_("Leave application ID is required"), frappe.MandatoryError)

    leave_doc = frappe.get_doc("Leave Application", leave_id)
    if not leave_doc:
        frappe.throw(_("Leave application not found"), frappe.DoesNotExistError)

    if leave_doc.status != "Pending":
        frappe.throw(_("Leave application is already {0}").format(leave_doc.status), frappe.ValidationError)

    assert_can_manage_employee(leave_doc.employee)

    current_emp = get_current_employee_id()
    leave_doc.status = "Rejected"
    leave_doc.approver = current_emp
    leave_doc.approval_comments = comments or "Rejected"
    leave_doc.decision_at = now_datetime()
    leave_doc.save()

    return {"message": "Leave application rejected", "leave_id": leave_doc.name, "status": "Rejected"}


@frappe.whitelist()
def get_team_leave_calendar(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    include_indirect: int = 1
):
    """
    Returns team leave schedule calendar events for the manager's hierarchy.
    """
    require_manager()
    current_emp = get_current_employee_id()
    team_ids = get_manager_team_ids(current_emp, include_indirect=bool(int(include_indirect)))

    if not team_ids:
        return []

    if to_date:
        end_date = getdate(to_date)
    else:
        end_date = getdate(nowdate()) + datetime.timedelta(days=30)

    if from_date:
        start_date = getdate(from_date)
    else:
        start_date = getdate(nowdate()) - datetime.timedelta(days=30)

    query = """
    SELECT 
        la.name,
        la.employee,
        e.employee_name,
        e.department,
        la.leave_type,
        la.from_date,
        la.to_date,
        la.status,
        la.reason
    FROM `tabLeave Application` la
    JOIN `tabEmployee` e ON la.employee = e.name
    WHERE la.employee IN %(team_ids)s
      AND la.status IN ('Approved', 'Pending')
      AND NOT (la.to_date < %(start_date)s OR la.from_date > %(end_date)s)
    ORDER BY la.from_date ASC;
    """
    events = frappe.db.sql(
        query,
        {"team_ids": tuple(team_ids), "start_date": start_date, "end_date": end_date},
        as_dict=True
    )
    return events
