import datetime
import os
import sys
import time
import tracemalloc
import pymysql

# Add app to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from employee360.seed.config import SeedConfig
from employee360.seed.generator import (
    generate_all_employees,
    generate_shift_data,
    generate_all_leave_applications,
    stream_activity_log_batches,
)

DB_CONFIG = {
    "host": os.environ.get("MARIADB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("MARIADB_PORT", 3306)),
    "user": os.environ.get("MARIADB_USER", "root"),
    "password": os.environ.get("MARIADB_PASSWORD", "root"),
    "database": os.environ.get("MARIADB_DATABASE", "employee360"),
    "autocommit": False,
    "charset": "utf8mb4",
    "connect_timeout": 3,
    "read_timeout": 3,
    "write_timeout": 3
}


def get_db_connection():
    """
    Dynamically connects using Frappe site_config if present,
    falling back to environment / DB_CONFIG.
    """
    try:
        import frappe
        site = os.environ.get("FRAPPE_SITE", os.environ.get("FRAPPE_SITE_NAME", "employee360.localhost"))
        sites_path = os.environ.get("SITES_PATH", "/home/frappe/frappe-bench/sites" if os.path.exists("/home/frappe/frappe-bench/sites") else None)
        if not getattr(frappe, "conf", None) or not frappe.conf.get("db_name"):
            frappe.init(site=site, sites_path=sites_path)

        if frappe.conf and frappe.conf.get("db_name"):
            return pymysql.connect(
                host=frappe.conf.get("db_host") or os.environ.get("MARIADB_HOST", "mariadb"),
                port=int(frappe.conf.get("db_port") or os.environ.get("MARIADB_PORT", 3306)),
                user=frappe.conf.get("db_name"),
                password=frappe.conf.get("db_password"),
                database=frappe.conf.get("db_name"),
                autocommit=False,
                charset="utf8mb4",
                connect_timeout=5
            )
    except Exception:
        pass

    return pymysql.connect(**DB_CONFIG)


def seed_shifts(cursor):
    """Inserts default shift schedule."""
    shift = generate_shift_data()
    sql = """
    INSERT INTO `tabShift` (
        `name`, `creation`, `modified`, `modified_by`, `owner`, `docstatus`,
        `shift_name`, `start_time`, `end_time`, `grace_period_mins`,
        `expected_working_hours`, `weekly_off_days`, `applicable_departments`
    ) VALUES (
        %(name)s, NOW(), NOW(), 'Administrator', 'Administrator', 0,
        %(shift_name)s, %(start_time)s, %(end_time)s, %(grace_period_mins)s,
        %(expected_working_hours)s, %(weekly_off_days)s, %(applicable_departments)s
    ) ON DUPLICATE KEY UPDATE `shift_name` = VALUES(`shift_name`);
    """
    cursor.execute(sql, shift)


def seed_demo_users(cursor=None, conn=None):
    """Creates demo users and ensures standard credentials using genuine Frappe User APIs."""
    import frappe
    from frappe.utils.password import update_password

    if not getattr(frappe, "db", None) or not frappe.db:
        site = os.environ.get("FRAPPE_SITE_NAME", "employee360.localhost")
        sites_path = "/home/frappe/frappe-bench/sites" if os.path.exists("/home/frappe/frappe-bench/sites") else None
        frappe.init(site=site, sites_path=sites_path)
        frappe.connect()

    demo_password = (
        os.environ.get("DEMO_USER_PASSWORD")
        or os.environ.get("ADMIN_PASSWORD")
        or "Admin123!"
    )

    print("[*] Seeding demo user authentication accounts via genuine Frappe User API...")

    # Ensure default shift exists
    if not frappe.db.exists("Shift", "General Shift"):
        s = frappe.new_doc("Shift")
        s.shift_name = "General Shift"
        s.name = "General Shift"
        s.start_time = "09:00:00"
        s.end_time = "18:00:00"
        s.grace_period_mins = 15
        s.expected_working_hours = 8.0
        s.weekly_off_days = "Saturday, Sunday"
        s.flags.ignore_permissions = True
        s.insert()

    mgr_map = {
        "EMP-00001": None,
        "EMP-00012": "EMP-00001",
        "EMP-00013": "EMP-00001",
        "EMP-01362": "EMP-00012",
        "EMP-01363": "EMP-00012",
        "EMP-01364": "EMP-00013"
    }

    for u in SeedConfig.DEMO_USERS:
        emp_id = u["employee_id"]
        emp_idx = int(emp_id.split("-")[1])
        if emp_idx > SeedConfig.TOTAL_EMPLOYEES:
            continue

        email = u["email"]
        parts = u["name"].split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""
        role = u["role"]
        emp_id = u["employee_id"]

        # 1. Create or update User
        if not frappe.db.exists("User", email):
            user = frappe.new_doc("User")
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.send_welcome_email = 0
            user.flags.ignore_permissions = True
            user.insert()
        else:
            user = frappe.get_doc("User", email)

        # 2. Add application role
        if role not in frappe.get_roles(email):
            user.add_roles(role)

        # 3. Set password securely
        try:
            update_password(user=email, pwd=demo_password)
        except Exception as e:
            print(f"    Notice updating password for {email}: {e}")

        # 4. Link demo Employee record
        if not frappe.db.exists("Employee", emp_id):
            emp = frappe.new_doc("Employee")
            emp.name = emp_id
            emp.employee_id = emp_id
            emp.employee_name = u["name"]
            emp.user_id = email
            emp.department = u["department"]
            emp.designation = u["designation"]
            emp.manager = mgr_map.get(emp_id)
            emp.date_of_joining = "2020-01-01"
            emp.employment_status = "Active"
            emp.shift = "General Shift"
            emp.flags.ignore_permissions = True
            emp.insert()
        else:
            frappe.db.set_value(
                "Employee",
                emp_id,
                {
                    "user_id": email,
                    "manager": mgr_map.get(emp_id),
                    "department": u["department"],
                    "designation": u["designation"],
                    "employment_status": "Active",
                    "shift": "General Shift"
                }
            )

    frappe.db.commit()
    print("[+] Demo user accounts seeded and linked to Employee records.")


def seed_employees(cursor, conn):
    """
    Seeds all employees with safe parameterized batch SQL.
    """
    employees = generate_all_employees(SeedConfig.TOTAL_EMPLOYEES)
    total_emps = len(employees)
    print(f"[*] Seeding {total_emps:,} Employee records...")

    sql = """
    INSERT INTO `tabEmployee` (
        `name`, `creation`, `modified`, `modified_by`, `owner`, `docstatus`,
        `employee_id`, `employee_name`, `user_id`, `manager`,
        `department`, `designation`, `date_of_joining`, `employment_status`, `shift`
    ) VALUES (
        %s, NOW(), NOW(), 'Administrator', 'Administrator', 0,
        %s, %s, %s, %s,
        %s, %s, %s, %s, %s
    ) ON DUPLICATE KEY UPDATE
        `employee_name` = VALUES(`employee_name`),
        `manager` = VALUES(`manager`),
        `department` = VALUES(`department`),
        `designation` = VALUES(`designation`),
        `shift` = VALUES(`shift`);
    """

    chunk_size = 2000
    rows = [
        (
            e["name"],
            e["employee_id"],
            e["employee_name"],
            e["user_id"],
            e["manager"],
            e["department"],
            e["designation"],
            e["date_of_joining"],
            e["employment_status"],
            e["shift"]
        )
        for e in employees
    ]

    for i in range(0, len(rows), chunk_size):
        cursor.executemany(sql, rows[i:i + chunk_size])
    conn.commit()
    print(f"[+] All {total_emps:,} Employee records committed successfully.")


def seed_leave_applications(cursor, conn):
    """
    Seeds comprehensive Leave Applications across all employees using parameterized batch SQL.
    Guarantees every 'On Leave' day has an approved leave application covering the date.
    """
    employees = generate_all_employees(SeedConfig.TOTAL_EMPLOYEES)
    print(f"[*] Generating approved and historical Leave Applications for {len(employees):,} employees...")
    all_leaves = generate_all_leave_applications(employees)
    print(f"[*] Inserting {len(all_leaves):,} Leave Application records...")

    sql = """
    INSERT IGNORE INTO `tabLeave Application` (
        `name`, `creation`, `modified`, `modified_by`, `owner`, `docstatus`,
        `employee`, `leave_type`, `from_date`, `to_date`, `total_leave_days`,
        `reason`, `status`, `approver`, `approval_comments`, `applied_at`, `decision_at`
    ) VALUES (
        %s, NOW(), NOW(), 'Administrator', 'Administrator', 0,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s
    );
    """

    rows = [
        (
            l["name"],
            l["employee"],
            l["leave_type"],
            l["from_date"],
            l["to_date"],
            l["total_leave_days"],
            l["reason"],
            l["status"],
            l["approver"],
            l["approval_comments"],
            l["applied_at"],
            l["decision_at"]
        )
        for l in all_leaves
    ]

    chunk_size = 2000
    for i in range(0, len(rows), chunk_size):
        cursor.executemany(sql, rows[i:i + chunk_size])
    conn.commit()
    print(f"[+] {len(all_leaves):,} Leave Application records committed successfully.")


def drop_secondary_indexes(cursor, conn):
    """Drops secondary non-unique indexes on tabEmployee Activity Log for high-speed bulk insertion."""
    if SeedConfig.TOTAL_ACTIVITY_RECORDS < 100000:
        return  # No need for small datasets

    print("[*] Optimizing table: dropping secondary indexes for raw ingestion speed...")
    t0 = time.time()
    indexes = [
        "idx_eal_emp_date",
        "idx_eal_date_emp",
        "idx_eal_status_date",
        "idx_eal_date_status"
    ]
    for idx in indexes:
        try:
            cursor.execute(f"ALTER TABLE `tabEmployee Activity Log` DROP INDEX `{idx}`;")
            conn.commit()
        except Exception:
            pass
    print(f"[+] Dropped secondary indexes in {time.time() - t0:.2f}s")


def recreate_secondary_indexes(cursor, conn):
    """Rebuilds secondary indexes post bulk insertion."""
    if SeedConfig.TOTAL_ACTIVITY_RECORDS < 100000:
        return

    print("[*] Rebuilding secondary composite indexes on `tabEmployee Activity Log`...")
    t0 = time.time()
    indexes = [
        ("idx_eal_emp_date", "`employee`, `activity_date`"),
        ("idx_eal_date_emp", "`activity_date`, `employee`"),
        ("idx_eal_status_date", "`attendance_status`, `activity_date`"),
        ("idx_eal_date_status", "`activity_date`, `attendance_status`")
    ]
    for idx_name, cols in indexes:
        t_sub = time.time()
        print(f"    -> Creating index `{idx_name}` on ({cols})...")
        try:
            cursor.execute(f"CREATE INDEX `{idx_name}` ON `tabEmployee Activity Log` ({cols});")
            conn.commit()
            print(f"       Index `{idx_name}` built in {time.time() - t_sub:.2f}s")
        except Exception as e:
            print(f"       Index `{idx_name}` notice: {e}")

    print(f"[+] All secondary indexes rebuilt in {time.time() - t0:.2f}s")


def get_actual_activity_log_count(cursor) -> int:
    cursor.execute("SELECT COUNT(*) FROM `tabEmployee Activity Log`;")
    row = cursor.fetchone()
    return row[0] if row else 0


def get_or_create_checkpoint(cursor, conn) -> int:
    """
    Inspects checkpoint AND verifies with actual database COUNT query.
    Prevents false completion declarations.
    """
    actual_count = get_actual_activity_log_count(cursor)

    cursor.execute("""
    SELECT `last_completed_batch`, `total_records_inserted`, `status`
    FROM `tabSeed Checkpoint`
    WHERE `seed_key` = 'attendance_seed';
    """)
    row = cursor.fetchone()

    if row:
        last_batch, meta_rec, status = row
        # Strictly verify with actual row count!
        if status == 'Completed' and actual_count >= SeedConfig.TOTAL_ACTIVITY_RECORDS:
            return -1  # Genuinely complete

        # Calculate resume batch based on actual verified rows
        resumed_batch = actual_count // SeedConfig.BATCH_SIZE
        return resumed_batch
    else:
        cursor.execute("""
        INSERT INTO `tabSeed Checkpoint` (
            `name`, `seed_key`, `last_completed_batch`, `total_records_inserted`, `target_records`, `status`
        ) VALUES ('attendance_seed', 'attendance_seed', 0, %(actual)s, %(target)s, 'Pending')
        ON DUPLICATE KEY UPDATE `total_records_inserted` = %(actual)s;
        """, {
            "actual": actual_count,
            "target": SeedConfig.TOTAL_ACTIVITY_RECORDS
        })
        conn.commit()
        return actual_count // SeedConfig.BATCH_SIZE


def update_checkpoint(cursor, conn, batch_idx: int, records_inserted: int):
    cursor.execute("""
    UPDATE `tabSeed Checkpoint`
    SET `last_completed_batch` = %(batch)s,
        `total_records_inserted` = %(inserted)s,
        `status` = 'In Progress',
        `updated_at` = NOW()
    WHERE `seed_key` = 'attendance_seed';
    """, {"batch": batch_idx, "inserted": records_inserted})


def mark_checkpoint_complete(cursor, conn, actual_count: int):
    cursor.execute("""
    UPDATE `tabSeed Checkpoint`
    SET `last_completed_batch` = %(batch)s,
        `total_records_inserted` = %(total)s,
        `status` = 'Completed',
        `updated_at` = NOW()
    WHERE `seed_key` = 'attendance_seed';
    """, {
        "batch": (actual_count + SeedConfig.BATCH_SIZE - 1) // SeedConfig.BATCH_SIZE,
        "total": actual_count
    })
    conn.commit()


def run_seed():
    """Main execution orchestrator for synthetic database seeding."""
    print("=" * 80)
    print("Employee360 — Production Synthetic Database Seeding Engine")
    print(f"Target Scale: {SeedConfig.TOTAL_EMPLOYEES:,} Employees | {SeedConfig.TOTAL_ACTIVITY_RECORDS:,} Activity Logs")
    print(f"Evaluation Window: {SeedConfig.START_DATE} to {SeedConfig.END_DATE} ({SeedConfig.DAYS_PER_EMPLOYEE} days)")
    print(f"Batch Size: {SeedConfig.BATCH_SIZE:,} | SQL Chunk: {SeedConfig.SQL_CHUNK_SIZE:,}")
    print(f"Generate Raw Punches: {SeedConfig.GENERATE_RAW_PUNCHES}")
    print("=" * 80)

    tracemalloc.start()
    start_total_time = time.time()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Ensure active_seconds is nullable
        try:
            cursor.execute("ALTER TABLE `tabEmployee Activity Log` MODIFY `active_seconds` INT NULL DEFAULT NULL;")
            conn.commit()
        except Exception:
            pass

        # Step 1: Shifts & Employees
        seed_shifts(cursor)
        conn.commit()
        seed_employees(cursor, conn)
        seed_demo_users(cursor, conn)

        # Step 2: Leave Applications (Must precede activity logs for consistency)
        seed_leave_applications(cursor, conn)

        # Step 3: Checkpoint & Actual Count Inspection
        last_batch = get_or_create_checkpoint(cursor, conn)
        actual_count = get_actual_activity_log_count(cursor)

        if last_batch == -1 or actual_count >= SeedConfig.TOTAL_ACTIVITY_RECORDS:
            print(f"[+] Seeding already completed! Verified database count: {actual_count:,} records.")
            return

        if last_batch > 0:
            print(f"[*] Resuming attendance seeding from batch {last_batch + 1} (already committed: {actual_count:,} records)...")
        else:
            print(f"[*] Starting fresh attendance seeding for {SeedConfig.TOTAL_ACTIVITY_RECORDS:,} records...")

        # Step 4: Temporary index optimization
        drop_secondary_indexes(cursor, conn)

        # Step 5: Safe Parameterized Stream and Batch Insert
        total_batches = (SeedConfig.TOTAL_ACTIVITY_RECORDS + SeedConfig.BATCH_SIZE - 1) // SeedConfig.BATCH_SIZE
        records_so_far = actual_count
        t_start_logs = time.time()

        insert_log_sql = """
        INSERT IGNORE INTO `tabEmployee Activity Log` (
            `name`, `creation`, `modified`, `modified_by`, `owner`, `docstatus`,
            `employee`, `activity_date`, `attendance_status`,
            `first_login`, `last_logout`, `total_work_seconds`,
            `active_seconds`, `total_sessions`, `calculated_at`,
            `is_regularized`, `regularization_exception`, `is_synthetic`
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        );
        """

        insert_exc_sql = """
        INSERT IGNORE INTO `tabAttendance Exception` (
            `name`, `creation`, `modified`, `modified_by`, `owner`, `docstatus`,
            `employee`, `activity_date`, `exception_type`, `status`,
            `assigned_manager`, `description`, `original_status`
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s
        );
        """

        insert_punch_sql = """
        INSERT IGNORE INTO `tabEmployee Checkin` (
            `name`, `creation`, `modified`, `modified_by`, `owner`, `docstatus`,
            `employee`, `time`, `log_type`, `source`,
            `source_record_id`, `device_info`, `ip_address`, `gps_accuracy`
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s
        );
        """

        chunk_size = SeedConfig.SQL_CHUNK_SIZE

        for batch_num, act_rows, exc_rows, punch_rows in stream_activity_log_batches(
            start_batch_idx=last_batch,
            batch_size=SeedConfig.BATCH_SIZE,
            total_employees=SeedConfig.TOTAL_EMPLOYEES
        ):
            # 1. Parameterized insert for activity logs
            for i in range(0, len(act_rows), chunk_size):
                cursor.executemany(insert_log_sql, act_rows[i:i + chunk_size])

            # 2. Parameterized insert for attendance exceptions (Missing Check-out)
            if exc_rows:
                for i in range(0, len(exc_rows), chunk_size):
                    cursor.executemany(insert_exc_sql, exc_rows[i:i + chunk_size])

            # 3. Parameterized insert for raw checkins if enabled
            if punch_rows:
                for i in range(0, len(punch_rows), chunk_size):
                    cursor.executemany(insert_punch_sql, punch_rows[i:i + chunk_size])

            records_so_far += len(act_rows)
            update_checkpoint(cursor, conn, batch_num, records_so_far)
            conn.commit()

            # Reporting
            if batch_num % 10 == 0 or records_so_far >= SeedConfig.TOTAL_ACTIVITY_RECORDS:
                now_t = time.time()
                elapsed_sec = now_t - t_start_logs
                rate = (records_so_far - actual_count) / elapsed_sec if elapsed_sec > 0 else 0
                pct = min(100.0, (records_so_far / SeedConfig.TOTAL_ACTIVITY_RECORDS) * 100)
                remaining_sec = (SeedConfig.TOTAL_ACTIVITY_RECORDS - records_so_far) / rate if rate > 0 else 0
                print(
                    f"    [Batch {batch_num:>3}/{total_batches}] "
                    f"Records: {records_so_far:>10,}/{SeedConfig.TOTAL_ACTIVITY_RECORDS:,} ({pct:5.1f}%) | "
                    f"Speed: {rate:7.0f} rows/s | "
                    f"ETA: {remaining_sec/60:4.1f}m"
                )

        t_end_logs = time.time()
        print(f"\n[+] Raw insertion of activity records finished in {t_end_logs - t_start_logs:.1f}s")

        # Step 6: Rebuild secondary indexes
        recreate_secondary_indexes(cursor, conn)

        # Step 7: Verify final actual count from DB and complete checkpoint
        final_count = get_actual_activity_log_count(cursor)
        mark_checkpoint_complete(cursor, conn, final_count)

        # Step 8: Final Benchmark & Metrics
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        total_time = time.time() - start_total_time

        cursor.execute("""
        SELECT table_name, round(((data_length + index_length) / 1024 / 1024), 2) `size_mb`
        FROM information_schema.TABLES 
        WHERE table_schema = DATABASE() AND table_name = 'tabEmployee Activity Log';
        """)
        table_size = cursor.fetchone()
        size_mb = table_size[1] if table_size else "N/A"

        print("=" * 80)
        print("SEED BENCHMARK REPORT")
        print("=" * 80)
        print(f"Total Seeding Duration:       {total_time:.1f} seconds ({total_time/60:.2f} minutes)")
        print(f"Verified Records Inserted:    {final_count:,}")
        print(f"Overall Throughput:           {final_count / total_time:.1f} records/sec" if total_time > 0 else "N/A")
        print(f"Peak Process Memory:          {peak_mem / 1024 / 1024:.2f} MB")
        print(f"Database Table + Index Size:  {size_mb} MB")
        print("=" * 80)

    except Exception as e:
        conn.rollback()
        print(f"\n[!] Error during seed execution: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run_seed()
