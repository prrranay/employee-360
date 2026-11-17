import datetime
from typing import Optional
import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from employee360.api.auth_utils import (
    get_session_user_and_roles,
    is_ceo,
)

def require_ceo():
    user, roles = get_session_user_and_roles()
    if not is_ceo(roles):
        frappe.throw(_("Unauthorized: CEO or System Manager privileges required"), frappe.PermissionError)


@frappe.whitelist()
def get_company_dashboard_summary(target_date: Optional[str] = None):
    """
    Company-wide attendance KPI card metrics for a single calendar date.
    Pure database aggregation across all 30,000 employees.
    """
    require_ceo()
    if target_date:
        date_val = getdate(target_date)
    else:
        has_today = frappe.db.sql("SELECT 1 FROM `tabEmployee Activity Log` WHERE activity_date = %s LIMIT 1", (nowdate(),))
        if has_today:
            date_val = getdate(nowdate())
        else:
            latest_row = frappe.db.sql("SELECT MAX(activity_date) FROM `tabEmployee Activity Log`")
            date_val = latest_row[0][0] if (latest_row and latest_row[0][0]) else getdate(nowdate())

    # Total active employees
    total_employees = frappe.db.sql(
        "SELECT COUNT(*) AS total FROM `tabEmployee` WHERE employment_status = 'Active'",
        as_dict=True
    )[0]["total"]

    # Attendance distribution for the target date
    status_counts = frappe.db.sql(
        """
        SELECT 
            attendance_status,
            COUNT(*) AS count,
            AVG(CASE WHEN total_work_seconds > 0 THEN total_work_seconds ELSE NULL END) AS avg_work_sec
        FROM `tabEmployee Activity Log`
        WHERE activity_date = %(date)s
        GROUP BY attendance_status;
        """,
        {"date": date_val},
        as_dict=True
    )

    counts_map = {r["attendance_status"]: r["count"] for r in status_counts}
    present = counts_map.get("Present", 0)
    late = counts_map.get("Late", 0)
    half_day = counts_map.get("Half Day", 0)
    absent = counts_map.get("Absent", 0)
    on_leave = counts_map.get("On Leave", 0)
    weekly_off = counts_map.get("Weekly Off", 0)
    missing_checkout = counts_map.get("Missing Check-out", 0)

    workable = total_employees - weekly_off
    attended = present + late + (half_day * 0.5)
    attendance_rate = round((attended / workable) * 100, 2) if workable > 0 else 0.0

    # Calculate average daily work duration across completed sessions
    avg_sec_row = frappe.db.sql(
        """
        SELECT AVG(total_work_seconds) AS avg_sec
        FROM `tabEmployee Activity Log`
        WHERE activity_date = %(date)s
          AND attendance_status IN ('Present', 'Late', 'Half Day')
          AND total_work_seconds > 0;
        """,
        {"date": date_val},
        as_dict=True
    )
    avg_seconds = int(avg_sec_row[0]["avg_sec"] or 0) if avg_sec_row else 0
    avg_hours = avg_seconds // 3600
    avg_mins = (avg_seconds % 3600) // 60

    return {
        "date": str(date_val),
        "total_employees": total_employees,
        "present": present,
        "late": late,
        "half_day": half_day,
        "absent": absent,
        "on_leave": on_leave,
        "weekly_off": weekly_off,
        "missing_checkout": missing_checkout,
        "attendance_rate": attendance_rate,
        "avg_work_seconds": avg_seconds,
        "avg_work_formatted": f"{avg_hours}h {avg_mins}m"
    }


@frappe.whitelist()
def search_employees(query: str, limit: int = 10):
    """
    Autocomplete search supporting employee name or employee ID.
    Capped at 10 results for high-speed debounced client requests.
    """
    require_ceo()
    if not query or len(query.strip()) < 1:
        return []

    limit = min(10, max(1, int(limit)))
    cleaned_query = f"%{query.strip()}%"

    results = frappe.db.sql(
        """
        SELECT 
            name,
            employee_id,
            employee_name,
            department,
            designation,
            employment_status
        FROM `tabEmployee`
        WHERE employee_id LIKE %(query)s
           OR employee_name LIKE %(query)s
        ORDER BY employee_name ASC
        LIMIT %(limit)s;
        """,
        {"query": cleaned_query, "limit": limit},
        as_dict=True
    )
    return results


@frappe.whitelist()
def get_employee_overview(
    employee_id: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    shift: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    search: Optional[str] = None
):
    """
    CEO drill-down overview or paginated company employee directory.
    """
    require_ceo()
    if employee_id:
        from employee360.api.employee import (
            get_employee_attendance_summary,
            get_employee_attendance_trend,
            get_employee_profile,
        )
        profile = get_employee_profile(employee_id)
        summary = get_employee_attendance_summary(employee_id)
        recent_trend = get_employee_attendance_trend(employee_id, days=14)
        return {
            "profile": profile,
            "summary": summary,
            "recent_trend": recent_trend
        }

    # Paginated company directory
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    offset = (page - 1) * page_size

    conditions = ["1=1"]
    values = {}
    if department:
        conditions.append("e.department = %(department)s")
        values["department"] = department
    if status:
        conditions.append("e.employment_status = %(status)s")
        values["status"] = status
    if shift:
        conditions.append("e.shift = %(shift)s")
        values["shift"] = shift
    if search:
        conditions.append("(e.employee_id LIKE %(search)s OR e.employee_name LIKE %(search)s)")
        values["search"] = f"%{search.strip()}%"

    where_sql = " AND ".join(conditions)
    total = frappe.db.sql(f"SELECT COUNT(*) AS total FROM `tabEmployee` e WHERE {where_sql}", values, as_dict=True)[0]["total"]

    values["limit"] = page_size
    values["offset"] = offset

    records = frappe.db.sql(f"""
        SELECT 
            e.name,
            e.employee_id,
            e.employee_name,
            e.department,
            e.designation,
            e.manager,
            m.employee_name AS manager_name,
            e.date_of_joining,
            e.employment_status,
            e.shift
        FROM `tabEmployee` e
        LEFT JOIN `tabEmployee` m ON e.manager = m.name
        WHERE {where_sql}
        ORDER BY e.employee_name ASC
        LIMIT %(limit)s OFFSET %(offset)s;
    """, values, as_dict=True)

    return {
        "records": records,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@frappe.whitelist()
def get_department_analytics(target_date: Optional[str] = None):
    """
    Department-wise attendance breakdown and statistics for a given date.
    Uses pure database aggregation joining Employee and Activity Log.
    """
    require_ceo()
    if target_date:
        date_val = getdate(target_date)
    else:
        has_today = frappe.db.sql("SELECT 1 FROM `tabEmployee Activity Log` WHERE activity_date = %s LIMIT 1", (nowdate(),))
        if has_today:
            date_val = getdate(nowdate())
        else:
            latest_row = frappe.db.sql("SELECT MAX(activity_date) FROM `tabEmployee Activity Log`")
            date_val = latest_row[0][0] if (latest_row and latest_row[0][0]) else getdate(nowdate())

    query = """
    SELECT 
        e.department,
        COUNT(e.name) AS total_headcount,
        SUM(CASE WHEN al.attendance_status = 'Present' THEN 1 ELSE 0 END) AS present_count,
        SUM(CASE WHEN al.attendance_status = 'Late' THEN 1 ELSE 0 END) AS late_count,
        SUM(CASE WHEN al.attendance_status = 'Half Day' THEN 1 ELSE 0 END) AS half_day_count,
        SUM(CASE WHEN al.attendance_status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
        SUM(CASE WHEN al.attendance_status = 'On Leave' THEN 1 ELSE 0 END) AS leave_count,
        SUM(CASE WHEN al.attendance_status = 'Missing Check-out' THEN 1 ELSE 0 END) AS missing_checkout_count,
        AVG(CASE WHEN al.attendance_status IN ('Present', 'Late', 'Half Day') AND al.total_work_seconds > 0 
                 THEN al.total_work_seconds ELSE NULL END) AS avg_work_seconds
    FROM `tabEmployee Activity Log` al FORCE INDEX (idx_eal_date_emp)
    JOIN `tabEmployee` e ON e.name = al.employee
    WHERE al.activity_date = %(date)s AND e.employment_status = 'Active'
    GROUP BY e.department
    ORDER BY total_headcount DESC;
    """
    departments = frappe.db.sql(query, {"date": date_val}, as_dict=True)

    for dept in departments:
        total = dept["total_headcount"] or 0
        attended = float(dept["present_count"] or 0) + float(dept["late_count"] or 0) + (float(dept["half_day_count"] or 0) * 0.5)
        dept["attendance_rate"] = round((attended / total) * 100, 2) if total > 0 else 0.0
        sec = int(dept["avg_work_seconds"] or 0)
        dept["avg_work_formatted"] = f"{sec // 3600}h {(sec % 3600) // 60}m"

    return departments


@frappe.whitelist()
def get_company_attendance_trend(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    days: int = 30
):
    """
    Aggregated daily attendance trends across the whole company.
    Uses indexed (activity_date, attendance_status) for high-speed response.
    """
    require_ceo()
    
    if to_date:
        end_date = getdate(to_date)
    else:
        end_date = getdate(nowdate())

    if from_date:
        start_date = getdate(from_date)
    else:
        start_date = end_date - datetime.timedelta(days=max(7, min(365, int(days))))

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
    WHERE activity_date BETWEEN %(start_date)s AND %(end_date)s
    GROUP BY activity_date
    ORDER BY activity_date ASC;
    """
    trend = frappe.db.sql(query, {"start_date": start_date, "end_date": end_date}, as_dict=True)
    return trend


@frappe.whitelist()
def get_company_attendance_exceptions(
    target_date: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 25
):
    """
    Paginated company-wide attendance exceptions for CEO review.
    """
    require_ceo()
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    offset = (page - 1) * page_size

    conditions = ["1=1"]
    values = {}

    if target_date:
        conditions.append("activity_date = %(date)s")
        values["date"] = getdate(target_date)
    if status:
        conditions.append("status = %(status)s")
        values["status"] = status

    where_clause = " AND ".join(conditions)

    count_query = f"SELECT COUNT(*) AS total FROM `tabAttendance Exception` WHERE {where_clause}"
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
        ae.assigned_manager,
        m.employee_name AS manager_name
    FROM `tabAttendance Exception` ae
    JOIN `tabEmployee` e ON ae.employee = e.name
    LEFT JOIN `tabEmployee` m ON ae.assigned_manager = m.name
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
def get_company_leave_overview(
    target_date: Optional[str] = None,
    status: Optional[str] = None,
    department: Optional[str] = None,
    page: Optional[int] = None,
    page_size: int = 25
):
    """
    Company-wide leave overview: metrics, department summaries, and paginated logs.
    """
    require_ceo()
    if target_date:
        date_val = getdate(target_date)
    else:
        has_today = frappe.db.sql("SELECT 1 FROM `tabEmployee Activity Log` WHERE activity_date = %s LIMIT 1", (nowdate(),))
        if has_today:
            date_val = getdate(nowdate())
        else:
            latest_row = frappe.db.sql("SELECT MAX(activity_date) FROM `tabEmployee Activity Log`")
            date_val = latest_row[0][0] if (latest_row and latest_row[0][0]) else getdate(nowdate())

    # Pending applications count
    pending_count = frappe.db.sql(
        "SELECT COUNT(*) AS total FROM `tabLeave Application` WHERE status = 'Pending'",
        as_dict=True
    )[0]["total"]

    # Active leaves on target date
    active_leaves_today = frappe.db.sql(
        """
        SELECT COUNT(*) AS total FROM `tabLeave Application`
        WHERE status = 'Approved'
          AND %(date)s BETWEEN from_date AND to_date;
        """,
        {"date": date_val},
        as_dict=True
    )[0]["total"]

    # Leave type breakdown
    types_breakdown = frappe.db.sql(
        """
        SELECT leave_type, COUNT(*) AS count
        FROM `tabLeave Application`
        WHERE status = 'Approved'
          AND YEAR(from_date) = YEAR(%(date)s)
        GROUP BY leave_type;
        """,
        {"date": date_val},
        as_dict=True
    )

    # Department breakdown of approved leaves
    dept_breakdown = frappe.db.sql(
        """
        SELECT e.department, COUNT(*) AS count
        FROM `tabLeave Application` la
        JOIN `tabEmployee` e ON la.employee = e.name
        WHERE la.status = 'Approved'
          AND %(date)s BETWEEN la.from_date AND la.to_date
        GROUP BY e.department
        ORDER BY count DESC;
        """,
        {"date": date_val},
        as_dict=True
    )

    # If page is requested, return paginated applications
    records = []
    total_records = 0
    if page is not None:
        p = max(1, int(page))
        ps = min(100, max(1, int(page_size)))
        off = (p - 1) * ps

        conds = ["1=1"]
        vals = {}
        if status:
            conds.append("la.status = %(status)s")
            vals["status"] = status
        if department:
            conds.append("e.department = %(dept)s")
            vals["dept"] = department

        where_str = " AND ".join(conds)
        total_records = frappe.db.sql(
            f"SELECT COUNT(*) AS total FROM `tabLeave Application` la JOIN `tabEmployee` e ON la.employee = e.name WHERE {where_str}",
            vals,
            as_dict=True
        )[0]["total"]

        vals["limit"] = ps
        vals["offset"] = off
        records = frappe.db.sql(
            f"""
            SELECT 
                la.name, la.employee, e.employee_name, e.department,
                la.leave_type, la.from_date, la.to_date, la.reason,
                la.status, la.applied_at, la.decision_at, la.approver, la.approval_comments
            FROM `tabLeave Application` la
            JOIN `tabEmployee` e ON la.employee = e.name
            WHERE {where_str}
            ORDER BY la.applied_at DESC
            LIMIT %(limit)s OFFSET %(offset)s;
            """,
            vals,
            as_dict=True
        )

    return {
        "pending_leave_requests": pending_count,
        "employees_on_leave_today": active_leaves_today,
        "leave_type_distribution": types_breakdown,
        "department_leave_breakdown": dept_breakdown,
        "records": records,
        "total": total_records,
        "page": page or 1,
        "page_size": page_size,
        "total_pages": (total_records + page_size - 1) // page_size if total_records else 0
    }


@frappe.whitelist()
def get_manager_performance(target_date: Optional[str] = None):
    """
    Returns aggregated team performance metrics for key managers on target_date.
    Includes team size, attendance rate, present count, late arrivals, absent count,
    and average work duration.
    """
    require_ceo()
    if target_date:
        date_val = getdate(target_date)
    else:
        has_today = frappe.db.sql("SELECT 1 FROM `tabEmployee Activity Log` WHERE activity_date = %s LIMIT 1", (nowdate(),))
        if has_today:
            date_val = getdate(nowdate())
        else:
            latest_row = frappe.db.sql("SELECT MAX(activity_date) FROM `tabEmployee Activity Log`")
            date_val = latest_row[0][0] if (latest_row and latest_row[0][0]) else getdate(nowdate())

    query = """
    SELECT 
        m.name AS manager_id,
        m.employee_name AS manager_name,
        m.department,
        m.designation,
        COUNT(e.name) AS team_size,
        SUM(CASE WHEN al.attendance_status = 'Present' THEN 1 ELSE 0 END) AS present_count,
        SUM(CASE WHEN al.attendance_status = 'Late' THEN 1 ELSE 0 END) AS late_count,
        SUM(CASE WHEN al.attendance_status = 'Half Day' THEN 1 ELSE 0 END) AS half_day_count,
        SUM(CASE WHEN al.attendance_status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
        SUM(CASE WHEN al.attendance_status = 'On Leave' THEN 1 ELSE 0 END) AS on_leave_count,
        SUM(CASE WHEN al.attendance_status = 'Missing Check-out' THEN 1 ELSE 0 END) AS missing_checkout_count,
        AVG(CASE WHEN al.total_work_seconds > 0 THEN al.total_work_seconds ELSE NULL END) AS avg_work_sec
    FROM `tabEmployee` m
    JOIN `tabEmployee` e ON e.manager = m.name
    LEFT JOIN `tabEmployee Activity Log` al 
           ON al.employee = e.name AND al.activity_date = %(target_date)s
    WHERE m.designation LIKE '%%Manager%%' 
       OR m.designation LIKE '%%Director%%' 
       OR m.designation LIKE '%%VP%%'
       OR m.name IN ('EMP-00012', 'EMP-00013')
    GROUP BY m.name
    ORDER BY team_size DESC, m.employee_name ASC;
    """
    rows = frappe.db.sql(query, {"target_date": date_val}, as_dict=True)

    results = []
    for r in rows:
        total = int(r["team_size"] or 0)
        present = int(r["present_count"] or 0)
        late = int(r["late_count"] or 0)
        half_day = float(r["half_day_count"] or 0)
        absent = int(r["absent_count"] or 0)
        on_leave = int(r["on_leave_count"] or 0)
        attended = present + late + (half_day * 0.5)
        workable = total - on_leave
        rate = round((attended / workable) * 100, 1) if workable > 0 else (round((attended / total) * 100, 1) if total > 0 else 0.0)
        
        sec = int(r["avg_work_sec"] or 0)
        avg_fmt = f"{sec // 3600}h {(sec % 3600) // 60}m"
        
        status = "Excellent" if rate >= 92 else ("Good" if rate >= 85 else "Needs Review")

        results.append({
            "manager_id": r["manager_id"],
            "manager_name": r["manager_name"],
            "department": r["department"],
            "designation": r["designation"],
            "team_size": total,
            "present_count": present,
            "late_count": late,
            "absent_count": absent,
            "on_leave_count": on_leave,
            "attendance_rate": rate,
            "avg_work_seconds": sec,
            "avg_work_formatted": avg_fmt,
            "performance_status": status
        })

    return {
        "date": str(date_val),
        "managers": results
    }


@frappe.whitelist()
def get_pending_manager_requests():
    """
    Returns pending leave applications and pending attendance correction requests
    submitted by managers for the CEO to review and accept/reject.
    """
    require_ceo()

    # 1. Pending Manager Leaves
    manager_leaves = frappe.db.sql("""
        SELECT 
            la.name,
            la.employee,
            e.employee_name,
            e.department,
            e.designation,
            la.leave_type,
            la.from_date,
            la.to_date,
            la.reason,
            la.status,
            la.applied_at
        FROM `tabLeave Application` la
        JOIN `tabEmployee` e ON la.employee = e.name
        WHERE la.status = 'Pending'
          AND (e.designation LIKE '%%Manager%%' 
            OR e.designation LIKE '%%Director%%' 
            OR e.designation LIKE '%%VP%%'
            OR e.manager = 'EMP-00001'
            OR e.name IN ('EMP-00012', 'EMP-00013'))
        ORDER BY la.applied_at DESC;
    """, as_dict=True)

    # 2. Pending Manager Attendance Correction Requests
    manager_corrections = frappe.db.sql("""
        SELECT 
            ae.name,
            ae.employee,
            e.employee_name,
            e.department,
            e.designation,
            ae.activity_date,
            ae.exception_type,
            ae.description,
            ae.status,
            ae.assigned_manager
        FROM `tabAttendance Exception` ae
        JOIN `tabEmployee` e ON ae.employee = e.name
        WHERE ae.status = 'Pending'
          AND (e.designation LIKE '%%Manager%%' 
            OR e.designation LIKE '%%Director%%' 
            OR e.designation LIKE '%%VP%%'
            OR e.manager = 'EMP-00001'
            OR ae.assigned_manager = 'EMP-00001'
            OR e.name IN ('EMP-00012', 'EMP-00013'))
        ORDER BY ae.activity_date DESC;
    """, as_dict=True)

    return {
        "leaves": manager_leaves,
        "corrections": manager_corrections,
        "total_pending": len(manager_leaves) + len(manager_corrections)
    }
