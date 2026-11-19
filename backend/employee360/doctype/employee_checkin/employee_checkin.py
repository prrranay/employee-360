import datetime
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime


class EmployeeCheckin(Document):
    def validate(self):
        self.validate_employee_reference()
        self.enforce_authorization()
        self.enforce_server_timestamp()
        self.validate_timestamp_order()

    def prevent_duplicate_events(self):
        return self.validate_timestamp_order()

    def validate_employee_reference(self):
        if not self.employee:
            frappe.throw(_("Employee reference is mandatory"), frappe.MandatoryError)
        if not frappe.db.exists("Employee", self.employee):
            frappe.throw(_("Employee {0} does not exist").format(self.employee), frappe.DoesNotExistError)

    def enforce_authorization(self):
        # 1. Allow internal server-side seed script execution
        if getattr(frappe.flags, "in_seed", False):
            return

        # 2. Allow internal server-side regularization approval handler
        if getattr(frappe.flags, "in_regularization_approval", False):
            return

        user = frappe.session.user
        roles = frappe.get_roles(user)

        # 3. Prevent client bypass via special source values ('Admin Correction', 'Regularization')
        #    A client cannot simply specify source='Admin Correction' to skip validation.
        if self.source in ["Regularization", "Admin Correction"]:
            if not self.source_record_id:
                frappe.throw(
                    _("Unauthorized: Administrative corrections must be processed through the authorized approval workflow"),
                    frappe.PermissionError
                )
            exc = frappe.db.get_value(
                "Attendance Exception",
                self.source_record_id,
                ["employee", "status", "assigned_manager"],
                as_dict=True
            )
            if not exc or exc["status"] != "Resolved" or exc["employee"] != self.employee:
                frappe.throw(
                    _("Unauthorized: Invalid or unapproved regularization reference"),
                    frappe.PermissionError
                )

        # 4. System Managers, Administrators, and CEOs have company-wide attendance logging privileges
        if "System Manager" in roles or "Administrator" in roles or "CEO" in roles:
            return

        # 5. Resolve the employee record linked to the authenticated user
        linked_employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
        if not linked_employee:
            frappe.throw(
                _("No active Employee profile linked to your user account"),
                frappe.PermissionError
            )

        # 6. Managers: live punches can be for self, or for managed team members via managerial action
        if "Manager" in roles:
            if self.employee == linked_employee:
                return  # Self punch
            from employee360.api.auth_utils import get_manager_team_ids
            team_ids = get_manager_team_ids(linked_employee, include_indirect=True)
            if self.employee in team_ids:
                return  # Authorized team member
            frappe.throw(
                _("Unauthorized: Manager cannot log attendance for an employee outside their team"),
                frappe.PermissionError
            )

        # 7. Regular individual contributor: CAN ONLY punch for their own linked Employee record
        if not self.employee or self.employee != linked_employee:
            frappe.throw(
                _("Unauthorized: You cannot log attendance for another employee"),
                frappe.PermissionError
            )

        self.employee = linked_employee

    def enforce_server_timestamp(self):
        # Force server-generated timestamps for live events if missing
        if not self.time:
            self.time = now_datetime()

    def validate_timestamp_order(self):
        if not self.employee or not self.time:
            return

        current_time = get_datetime(self.time)
        now_time = now_datetime()

        # Reject timestamps in the future (allowing 10 seconds tolerance for clock skew)
        if current_time > now_time + datetime.timedelta(seconds=10):
            frappe.throw(
                _("Invalid timestamp: Cannot record attendance events in the future ({0})").format(current_time),
                frappe.ValidationError
            )

        # Check for duplicate events at identical timestamp
        identical = frappe.db.sql(
            """
            SELECT name, time, log_type FROM `tabEmployee Checkin`
            WHERE employee = %(employee)s
              AND time = %(time)s
              AND name != %(name)s
            LIMIT 1
            """,
            {"employee": self.employee, "time": current_time, "name": self.name or ""},
            as_dict=True
        )
        if identical:
            frappe.throw(
                _("A punch was already recorded for employee {0} at {1}").format(self.employee, current_time),
                frappe.DuplicateEntryError
            )

        # Bypass sequential state transition enforcement ONLY during verified server-side seed or regularization
        if getattr(frappe.flags, "in_seed", False) or getattr(frappe.flags, "in_regularization_approval", False):
            return

        # Fetch the most recent punch prior to or at this one on the same day (using locking read)
        day_start = datetime.datetime.combine(current_time.date(), datetime.time.min)
        last_punch = frappe.db.sql(
            """
            SELECT name, time, log_type FROM `tabEmployee Checkin`
            WHERE employee = %(employee)s
              AND time >= %(day_start)s
              AND time <= %(time)s
              AND name != %(name)s
            ORDER BY time DESC
            LIMIT 1
            FOR UPDATE
            """,
            {
                "employee": self.employee,
                "day_start": day_start,
                "time": self.time,
                "name": self.name or ""
            },
            as_dict=True
        )

        if self.log_type == "IN":
            if last_punch and last_punch[0].get("log_type") == "IN":
                frappe.throw(
                    _("You are already checked in. Please check out before checking in again."),
                    frappe.ValidationError
                )
        elif self.log_type == "OUT":
            if not last_punch or last_punch[0].get("log_type") != "IN":
                frappe.throw(
                    _("Cannot check out: No active open check-in session found for today. Please check in first."),
                    frappe.ValidationError
                )
            last_in_time = get_datetime(last_punch[0].get("time"))
            if current_time <= last_in_time:
                frappe.throw(
                    _("Check-out time ({0}) must be after the check-in time ({1})").format(current_time, last_in_time),
                    frappe.ValidationError
                )

    def on_update(self):
        self.trigger_daily_summary_recalculation()

    def trigger_daily_summary_recalculation(self):
        if not self.employee or not self.time:
            return

        activity_date = get_datetime(self.time).date()
        from employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary
        recalculate_daily_summary(self.employee, activity_date)


def on_checkin_update(doc, method=None):
    if hasattr(doc, "trigger_daily_summary_recalculation"):
        doc.trigger_daily_summary_recalculation()

