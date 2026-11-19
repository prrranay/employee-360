import datetime
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, getdate, now_datetime


class EmployeeActivityLog(Document):
    def validate(self):
        self.enforce_unique_employee_date()
        if not self.calculated_at:
            self.calculated_at = now_datetime()

    def enforce_unique_employee_date(self):
        if not self.employee or not self.activity_date:
            return

        existing = frappe.db.get_value(
            "Employee Activity Log",
            {"employee": self.employee, "activity_date": self.activity_date},
            "name"
        )
        if existing and existing != self.name:
            frappe.throw(
                _("An activity log already exists for {0} on {1}").format(
                    self.employee, self.activity_date
                ),
                frappe.DuplicateEntryError
            )


def recalculate_daily_summary(employee: str, activity_date):
    """
    Recalculates a single daily summary for an employee on a given calendar date
    from raw Employee Checkin punch events and shift configuration.
    """
    if isinstance(activity_date, str):
        activity_date = getdate(activity_date)

    start_datetime = datetime.datetime.combine(activity_date, datetime.time.min)
    end_datetime = datetime.datetime.combine(activity_date, datetime.time.max)

    # 1. Fetch raw punches for the calendar day
    punches = frappe.db.sql(
        """
        SELECT time, log_type FROM `tabEmployee Checkin`
        WHERE employee = %(employee)s
          AND time BETWEEN %(start_datetime)s AND %(end_datetime)s
        ORDER BY time ASC
        """,
        {
            "employee": employee,
            "start_datetime": start_datetime,
            "end_datetime": end_datetime
        },
        as_dict=True
    )

    # 2. Check for Shift configuration
    shift_name = frappe.db.get_value("Employee", employee, "shift")
    shift = None
    if shift_name:
        shift = frappe.db.get_value(
            "Shift",
            shift_name,
            ["start_time", "end_time", "grace_period_mins", "expected_working_hours", "weekly_off_days"],
            as_dict=True
        )

    # 3. Check for approved Leave Application
    leave = frappe.db.sql(
        """
        SELECT name, leave_type FROM `tabLeave Application`
        WHERE employee = %(employee)s
          AND status = 'Approved'
          AND %(activity_date)s BETWEEN from_date AND to_date
        LIMIT 1
        """,
        {"employee": employee, "activity_date": activity_date},
        as_dict=True
    )

    weekday_name = activity_date.strftime("%A")
    weekly_off_days = (
        [d.strip() for d in (shift.get("weekly_off_days") or "Saturday, Sunday").split(",")]
        if shift else ["Saturday", "Sunday"]
    )
    is_weekly_off = weekday_name in weekly_off_days

    # Initial values
    first_login = None
    last_logout = None
    total_work_seconds = 0
    total_sessions = 0
    missing_checkout = False

    existing_row = frappe.db.get_value(
        "Employee Activity Log",
        {"employee": employee, "activity_date": activity_date},
        ["name", "is_regularized", "attendance_status", "is_synthetic"],
        as_dict=True
    )

    if not punches:
        if existing_row and existing_row.get("is_synthetic"):
            # Preserve seeded historical synthetic summary; do not wipe it out
            return existing_row["name"]
        if leave:
            status = "On Leave"
        elif is_weekly_off:
            status = "Weekly Off"
        else:
            status = "Absent"
    else:
        # Evaluate sessions and durations
        in_time = None
        for p in punches:
            raw_time = p["time"] if isinstance(p, dict) else getattr(p, "time")
            raw_type = p["log_type"] if isinstance(p, dict) else getattr(p, "log_type")
            ptime = get_datetime(raw_time)
            if raw_type == "IN":
                total_sessions += 1
                if first_login is None:
                    first_login = ptime.time()
                in_time = ptime
            elif raw_type == "OUT":
                last_logout = ptime.time()
                if in_time:
                    delta = (ptime - in_time).total_seconds()
                    if delta > 0:
                        total_work_seconds += int(delta)
                    in_time = None

        if in_time is not None:
            # Last punch was IN without a matching OUT
            missing_checkout = True

        # Status determination
        if missing_checkout:
            status = "Missing Check-out"
        elif leave:
            status = "On Leave"
        else:
            # Check for Late Arrival
            is_late = False
            shift_start = shift.get("start_time") if isinstance(shift, dict) else getattr(shift, "start_time", None) if shift else None
            if shift_start and first_login:
                if isinstance(shift_start, datetime.timedelta):
                    shift_start_time = (datetime.datetime.min + shift_start).time()
                elif isinstance(shift_start, datetime.time):
                    shift_start_time = shift_start
                else:
                    shift_start_time = datetime.time(9, 0)

                grace_mins = (
                    shift.get("grace_period_mins") if isinstance(shift, dict)
                    else getattr(shift, "grace_period_mins", 15)
                ) or 15
                expected_start_dt = datetime.datetime.combine(activity_date, shift_start_time)
                grace_limit_dt = expected_start_dt + datetime.timedelta(minutes=grace_mins)
                actual_first_login_dt = datetime.datetime.combine(activity_date, first_login)

                if actual_first_login_dt > grace_limit_dt:
                    is_late = True

            expected_hours = float(
                (shift.get("expected_working_hours") if isinstance(shift, dict)
                 else getattr(shift, "expected_working_hours", 8.0)) or 8.0
            ) if shift else 8.0
            expected_seconds = expected_hours * 3600

            if is_late:
                status = "Late"
            elif total_work_seconds >= (expected_seconds * 0.9):
                status = "Present"
            elif total_work_seconds >= (expected_seconds * 0.45):
                status = "Half Day"
            else:
                status = "Absent"

    # Upsert into tabEmployee Activity Log
    calc_time = now_datetime()
    name = f"EAL-{employee}-{activity_date.strftime('%Y%m%d')}"

    existing_row = frappe.db.get_value(
        "Employee Activity Log",
        {"employee": employee, "activity_date": activity_date},
        ["name", "is_regularized", "attendance_status"],
        as_dict=True
    )

    if existing_row:
        existing_doc = existing_row["name"]
        # Preserve approved regularized status across background recalculations
        final_status = existing_row["attendance_status"] if existing_row.get("is_regularized") else status
        frappe.db.set_value(
            "Employee Activity Log",
            existing_doc,
            {
                "first_login": first_login,
                "last_logout": last_logout,
                "total_work_seconds": total_work_seconds,
                "active_seconds": None,
                "total_sessions": total_sessions,
                "attendance_status": final_status,
                "calculated_at": calc_time
            },
            update_modified=True
        )
        return existing_doc
    else:
        doc = frappe.get_doc({
            "doctype": "Employee Activity Log",
            "name": name,
            "employee": employee,
            "activity_date": activity_date,
            "first_login": first_login,
            "last_logout": last_logout,
            "total_work_seconds": total_work_seconds,
            "active_seconds": None,
            "total_sessions": total_sessions,
            "attendance_status": status,
            "calculated_at": calc_time
        })
        doc.flags.ignore_permissions = True
        doc.flags.ignore_validate = False
        doc.insert()
        return doc.name
