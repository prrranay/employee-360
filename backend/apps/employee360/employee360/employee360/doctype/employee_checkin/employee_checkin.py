import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime

class EmployeeCheckin(Document):
    def validate(self):
        self.enforce_authorization()
        self.enforce_server_timestamp()
        self.prevent_duplicate_events()
        self.validate_timestamp_order()

    def enforce_authorization(self):
        user = frappe.session.user
        roles = frappe.get_roles(user)
        
        # System Managers and Admins can create punches on behalf of others
        if "System Manager" in roles or "Administrator" in roles or "HR Manager" in roles:
            return

        # Regular users can only punch for their own linked Employee profile
        employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
        if not employee:
            frappe.throw(_("No active Employee profile linked to your user account"), frappe.PermissionError)

        if self.employee and self.employee != employee:
            frappe.throw(_("Unauthorized: You cannot log attendance for another employee"), frappe.PermissionError)

        self.employee = employee

    def enforce_server_timestamp(self):
        # Force server-generated timestamps for live events
        if self.source in ["Web", "Mobile"] or not self.time:
            self.time = now_datetime()

    def prevent_duplicate_events(self):
        if not self.employee or not self.time:
            return

        current_time = get_datetime(self.time)
        # Check if an identical punch occurred within 30 seconds
        duplicate = frappe.db.sql(
            """
            SELECT name, time, log_type FROM `tabEmployee Checkin`
            WHERE employee = %(employee)s
              AND log_type = %(log_type)s
              AND ABS(TIMESTAMPDIFF(SECOND, time, %(time)s)) < 30
              AND name != %(name)s
            LIMIT 1
            """,
            {
                "employee": self.employee,
                "log_type": self.log_type,
                "time": current_time,
                "name": self.name or ""
            },
            as_dict=True
        )

        if duplicate:
            dup_time = duplicate[0].get("time") if isinstance(duplicate[0], dict) else getattr(duplicate[0], "time", "")
            frappe.throw(
                _("Duplicate punch detected: A {0} punch was already recorded at {1}").format(
                    self.log_type, dup_time
                ),
                frappe.DuplicateEntryError
            )

    def validate_timestamp_order(self):
        # Fetch the most recent punch prior to this one
        last_punch = frappe.db.sql(
            """
            SELECT name, time, log_type FROM `tabEmployee Checkin`
            WHERE employee = %(employee)s
              AND time <= %(time)s
              AND name != %(name)s
            ORDER BY time DESC
            LIMIT 1
            """,
            {
                "employee": self.employee,
                "time": self.time,
                "name": self.name or ""
            },
            as_dict=True
        )

        if last_punch:
            # If consecutive identical log types occur without paired punch, log a warning or flag
            # (Multiple sessions per day allowed: IN -> OUT -> IN -> OUT)
            pass

    def on_update(self):
        self.trigger_daily_summary_recalculation()

    def trigger_daily_summary_recalculation(self):
        if not self.employee or not self.time:
            return

        activity_date = get_datetime(self.time).date()
        try:
            from employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary
        except ImportError:
            from employee360.employee360.doctype.employee_activity_log.employee_activity_log import recalculate_daily_summary
        recalculate_daily_summary(self.employee, activity_date)

