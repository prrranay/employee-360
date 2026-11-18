import frappe

def execute():
    """
    Applies production performance indexes, composite keys, and constraints
    optimized for 30,000 employees and 10,950,000 activity logs.
    """
    # 1. Employee indexes
    add_index_if_not_exists("tabEmployee", "idx_emp_id", ["employee_id"])
    add_index_if_not_exists("tabEmployee", "idx_emp_manager", ["manager"])
    add_index_if_not_exists("tabEmployee", "idx_emp_department", ["department"])
    add_index_if_not_exists("tabEmployee", "idx_emp_user", ["user_id"])

    # 2. Employee Checkin indexes
    add_index_if_not_exists("tabEmployee Checkin", "idx_checkin_emp_time", ["employee", "time"])

    # 3. Employee Activity Log indexes (10.95M rows)
    add_index_if_not_exists("tabEmployee Activity Log", "idx_eal_emp_date", ["employee", "activity_date"])
    add_index_if_not_exists("tabEmployee Activity Log", "idx_eal_date_emp", ["activity_date", "employee"])
    add_index_if_not_exists("tabEmployee Activity Log", "idx_eal_status_date", ["attendance_status", "activity_date"])
    add_index_if_not_exists("tabEmployee Activity Log", "idx_eal_date_status", ["activity_date", "attendance_status"])

    # 4. Leave Application indexes
    add_index_if_not_exists("tabLeave Application", "idx_leave_emp_status_dates", ["employee", "status", "from_date", "to_date"])

    # 5. Attendance Exception indexes
    add_index_if_not_exists("tabAttendance Exception", "idx_exc_mgr_status", ["assigned_manager", "status", "activity_date"])
    add_index_if_not_exists("tabAttendance Exception", "idx_exc_emp_date", ["employee", "activity_date"])


def add_index_if_not_exists(table_name: str, index_name: str, columns: list):
    try:
        existing = frappe.db.sql(
            f"""
            SHOW INDEX FROM `{table_name}` WHERE Key_name = %(index_name)s
            """,
            {"index_name": index_name}
        )
        if not existing:
            cols_str = ", ".join([f"`{c}`" for c in columns])
            frappe.db.sql(f"CREATE INDEX `{index_name}` ON `{table_name}` ({cols_str})")
            frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Failed to add index {index_name} on {table_name}: {str(e)}")

