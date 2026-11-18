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
    stream_activity_log_batches,
)

DB_CONFIG = {
    "host": os.environ.get("MARIADB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("MARIADB_PORT", 3306)),
    "user": os.environ.get("MARIADB_USER", "root"),
    "password": os.environ.get("MARIADB_PASSWORD", "root"),
    "database": os.environ.get("MARIADB_DATABASE", "employee360"),
    "autocommit": False,
    "charset": "utf8mb4"
}

def get_db_connection():
    return pymysql.connect(**DB_CONFIG)


def seed_shifts(cursor):
    shift = generate_shift_data()
    sql = """
    INSERT INTO `tabShift` (
        `name`, `shift_name`, `start_time`, `end_time`, `grace_period_mins`,
        `expected_working_hours`, `weekly_off_days`, `applicable_departments`
    ) VALUES (
        %(name)s, %(shift_name)s, %(start_time)s, %(end_time)s, %(grace_period_mins)s,
        %(expected_working_hours)s, %(weekly_off_days)s, %(applicable_departments)s
    ) ON DUPLICATE KEY UPDATE `shift_name` = VALUES(`shift_name`);
    """
    cursor.execute(sql, shift)


def seed_demo_users(cursor, conn):
    """Creates the 6 demo users plus Administrator required for testing CEO, Manager, and Employee dashboards."""
    from passlib.hash import pbkdf2_sha256
    print("[*] Seeding demo user authentication accounts with secure PBKDF2-SHA256 hashes...")
    
    # Hash password 'Admin123!' with PBKDF2-SHA256 (Frappe standard password hash)
    pwd_hash = pbkdf2_sha256.hash("Admin123!")

    all_users = list(SeedConfig.DEMO_USERS) + [
        {
            "email": "Administrator",
            "name": "Administrator",
            "role": "Administrator",
            "employee_id": "EMP-00001",
            "department": "Executive",
            "designation": "System Administrator"
        }
    ]

    for u in all_users:
        parts = u["name"].split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""
        
        # Upsert User with secure PBKDF2-SHA256 password hash
        sql_user = """
        INSERT INTO `tabUser` (
            `name`, `email`, `first_name`, `last_name`, `full_name`, `password`, `enabled`, `user_type`
        ) VALUES (
            %(email)s, %(email)s, %(first)s, %(last)s, %(full)s, %(pwd)s, 1, 'System User'
        ) ON DUPLICATE KEY UPDATE `full_name` = VALUES(`full_name`), `password` = VALUES(`password`), `enabled` = 1;
        """
        cursor.execute(sql_user, {
            "email": u["email"],
            "first": first_name,
            "last": last_name,
            "full": u["name"],
            "pwd": pwd_hash
        })

        # Assign Role
        role_id = f"{u['email']}-{u['role']}"
        sql_role = """
        INSERT INTO `tabHas Role` (`name`, `parent`, `role`)
        VALUES (%(name)s, %(parent)s, %(role)s)
        ON DUPLICATE KEY UPDATE `role` = VALUES(`role`);
        """
        cursor.execute(sql_role, {
            "name": role_id,
            "parent": u["email"],
            "role": u["role"]
        })

    conn.commit()
    print("    -> Demo user accounts initialized with PBKDF2-SHA256 password hashes")


def seed_leave_applications(cursor, conn):
    """Seeds approved leave applications to ensure leave calendars and balance summaries agree."""
    cursor.execute("SELECT COUNT(*) FROM `tabLeave Application`;")
    existing_count = cursor.fetchone()[0]
    if existing_count >= 100:
        return

    print("[*] Seeding approved Leave Applications for team leave calendars...")
    from employee360.seed.generator import generate_employee_leave_applications
    leaves = generate_employee_leave_applications()
    for l in leaves:
        sql = """
        INSERT INTO `tabLeave Application` (
            name, employee, leave_type, from_date, to_date, total_leave_days,
            reason, status, approver, approval_comments, applied_at, decision_at
        ) VALUES (
            %(name)s, %(employee)s, %(leave_type)s, %(from_date)s, %(to_date)s, %(total_leave_days)s,
            %(reason)s, %(status)s, %(approver)s, %(approval_comments)s, %(applied_at)s, %(decision_at)s
        ) ON DUPLICATE KEY UPDATE status = VALUES(status);
        """
        cursor.execute(sql, l)
    conn.commit()
    print(f"    -> {len(leaves)} Leave Applications successfully seeded")


def seed_employees(cursor, conn):
    cursor.execute("SELECT COUNT(*) FROM `tabEmployee`;")
    existing_count = cursor.fetchone()[0]
    if existing_count >= SeedConfig.TOTAL_EMPLOYEES:
        print(f"[*] Employees already seeded: {existing_count} records found.")
        return

    print(f"[*] Generating {SeedConfig.TOTAL_EMPLOYEES:,} employee records...")
    t0 = time.time()
    employees = generate_all_employees()

    chunk_size = 2000
    total = len(employees)
    for i in range(0, total, chunk_size):
        chunk = employees[i:i + chunk_size]
        values_clause = []
        for emp in chunk:
            mgr_val = f"'{emp['manager']}'" if emp['manager'] else "NULL"
            user_val = f"'{emp['user_id']}'" if emp['user_id'] else "NULL"
            row_str = (
                f"('{emp['name']}', '{emp['employee_id']}', "
                f"'{pymysql.converters.escape_string(emp['employee_name'])}', "
                f"{user_val}, {mgr_val}, '{emp['department']}', "
                f"'{pymysql.converters.escape_string(emp['designation'])}', "
                f"'{emp['date_of_joining']}', '{emp['employment_status']}', "
                f"'{emp['shift']}')"
            )
            values_clause.append(row_str)

        sql = f"""
        INSERT IGNORE INTO `tabEmployee` (
            `name`, `employee_id`, `employee_name`, `user_id`, `manager`,
            `department`, `designation`, `date_of_joining`, `employment_status`, `shift`
        ) VALUES {', '.join(values_clause)};
        """
        cursor.execute(sql)
        conn.commit()
        inserted_so_far = min(i + chunk_size, total)
        print(f"    -> Employees inserted: {inserted_so_far:,}/{total:,} ({inserted_so_far/total*100:.1f}%)", end="\r")

    t1 = time.time()
    print(f"\n[+] Completed Employee seeding: {SeedConfig.TOTAL_EMPLOYEES:,} rows in {t1 - t0:.2f}s ({SeedConfig.TOTAL_EMPLOYEES / (t1 - t0):.1f} rows/s)")


def drop_secondary_indexes(cursor, conn):
    """Drops secondary indexes on tabEmployee Activity Log to maximize bulk insert speed."""
    print("[*] Optimizing table: dropping nonessential secondary indexes before bulk insertion...")
    indexes = ["idx_eal_emp_date", "idx_eal_date_emp", "idx_eal_status_date", "idx_eal_date_status"]
    for idx in indexes:
        try:
            cursor.execute(f"ALTER TABLE `tabEmployee Activity Log` DROP INDEX `{idx}`;")
        except Exception:
            pass  # Index may not exist
    conn.commit()


def recreate_secondary_indexes(cursor, conn):
    """Rebuilds high-performance composite indexes in a single fast B-Tree pass."""
    print("\n[*] Rebuilding composite secondary indexes on tabEmployee Activity Log (10,950,000 rows)...")
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


def get_or_create_checkpoint(cursor, conn) -> int:
    cursor.execute("""
    SELECT `last_completed_batch`, `total_records_inserted`, `status`
    FROM `tabSeed Checkpoint`
    WHERE `seed_key` = 'attendance_seed';
    """)
    row = cursor.fetchone()
    if row:
        last_batch, total_rec, status = row
        if status == 'Completed' and total_rec >= SeedConfig.TOTAL_ACTIVITY_RECORDS:
            return -1  # Already complete
        return last_batch
    else:
        cursor.execute("""
        INSERT INTO `tabSeed Checkpoint` (
            `seed_key`, `last_completed_batch`, `total_records_inserted`, `target_records`, `status`
        ) VALUES ('attendance_seed', 0, 0, %(target)s, 'Pending');
        """, {"target": SeedConfig.TOTAL_ACTIVITY_RECORDS})
        conn.commit()
        return 0


def update_checkpoint(cursor, conn, batch_idx: int, records_inserted: int):
    cursor.execute("""
    UPDATE `tabSeed Checkpoint`
    SET `last_completed_batch` = %(batch)s,
        `total_records_inserted` = %(inserted)s,
        `status` = 'In Progress',
        `updated_at` = NOW()
    WHERE `seed_key` = 'attendance_seed';
    """, {"batch": batch_idx, "inserted": records_inserted})
    conn.commit()


def mark_checkpoint_complete(cursor, conn):
    cursor.execute("""
    UPDATE `tabSeed Checkpoint`
    SET `last_completed_batch` = %(batch)s,
        `total_records_inserted` = %(total)s,
        `status` = 'Completed',
        `updated_at` = NOW()
    WHERE `seed_key` = 'attendance_seed';
    """, {
        "batch": (SeedConfig.TOTAL_ACTIVITY_RECORDS + SeedConfig.BATCH_SIZE - 1) // SeedConfig.BATCH_SIZE,
        "total": SeedConfig.TOTAL_ACTIVITY_RECORDS
    })
    conn.commit()


def run_seed():
    """Main execution orchestrator for synthetic database seeding."""
    print("=" * 80)
    print("Employee360 — Production Synthetic Database Seeding Engine")
    print(f"Target Scale: {SeedConfig.TOTAL_EMPLOYEES:,} Employees | {SeedConfig.TOTAL_ACTIVITY_RECORDS:,} Activity Logs")
    print(f"Evaluation Window: {SeedConfig.START_DATE} to {SeedConfig.END_DATE} ({SeedConfig.DAYS_PER_EMPLOYEE} days)")
    print(f"Batch Size: {SeedConfig.BATCH_SIZE:,} | SQL Chunk: {SeedConfig.SQL_CHUNK_SIZE:,}")
    print("=" * 80)

    tracemalloc.start()
    start_total_time = time.time()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Step 1: Shifts & Employees
        seed_shifts(cursor)
        conn.commit()
        seed_employees(cursor, conn)
        seed_demo_users(cursor, conn)
        seed_leave_applications(cursor, conn)

        # Step 2: Checkpoint Inspection
        last_batch = get_or_create_checkpoint(cursor, conn)
        if last_batch == -1:
            cursor.execute("SELECT COUNT(*) FROM `tabEmployee Activity Log`;")
            cnt = cursor.fetchone()[0]
            print(f"[+] Seeding already completed! Current count: {cnt:,} records.")
            return

        if last_batch > 0:
            print(f"[*] Resuming attendance seeding from batch {last_batch + 1}...")
        else:
            print("[*] Starting fresh attendance seeding for 10,950,000 records...")

        # Step 3: Temporary index optimization
        drop_secondary_indexes(cursor, conn)

        # Step 4: Stream and insert batches
        total_batches = (SeedConfig.TOTAL_ACTIVITY_RECORDS + SeedConfig.BATCH_SIZE - 1) // SeedConfig.BATCH_SIZE
        records_so_far = last_batch * SeedConfig.BATCH_SIZE
        t_start_logs = time.time()
        last_log_time = t_start_logs

        for batch_num, rows in stream_activity_log_batches(start_batch_idx=last_batch, batch_size=SeedConfig.BATCH_SIZE):
            # Insert in SQL chunks of SQL_CHUNK_SIZE (e.g. 5,000 rows)
            chunk_size = SeedConfig.SQL_CHUNK_SIZE
            for i in range(0, len(rows), chunk_size):
                sub_rows = rows[i:i + chunk_size]
                formatted_values = []
                for r in sub_rows:
                    f_login = f"'{r[4]}'" if r[4] else "NULL"
                    l_logout = f"'{r[5]}'" if r[5] else "NULL"
                    val_str = (
                        f"('{r[0]}', '{r[1]}', '{r[2]}', '{r[3]}', {f_login}, {l_logout}, "
                        f"{r[6]}, {r[7]}, {r[8]}, '{r[9]}')"
                    )
                    formatted_values.append(val_str)

                sql = f"""
                INSERT IGNORE INTO `tabEmployee Activity Log` (
                    `name`, `employee`, `activity_date`, `attendance_status`,
                    `first_login`, `last_logout`, `total_work_seconds`,
                    `active_seconds`, `total_sessions`, `calculated_at`
                ) VALUES {', '.join(formatted_values)};
                """
                cursor.execute(sql)

            conn.commit()
            records_so_far += len(rows)
            update_checkpoint(cursor, conn, batch_num, records_so_far)

            # Performance reporting every 10 batches (~250,000 records)
            if batch_num % 10 == 0 or records_so_far >= SeedConfig.TOTAL_ACTIVITY_RECORDS:
                now_t = time.time()
                elapsed_sec = now_t - t_start_logs
                rate = (records_so_far - (last_batch * SeedConfig.BATCH_SIZE)) / elapsed_sec if elapsed_sec > 0 else 0
                pct = (records_so_far / SeedConfig.TOTAL_ACTIVITY_RECORDS) * 100
                remaining_sec = (SeedConfig.TOTAL_ACTIVITY_RECORDS - records_so_far) / rate if rate > 0 else 0
                print(
                    f"    [Batch {batch_num:>3}/{total_batches}] "
                    f"Records: {records_so_far:>10,}/{SeedConfig.TOTAL_ACTIVITY_RECORDS:,} ({pct:5.1f}%) | "
                    f"Speed: {rate:7.0f} rows/s | "
                    f"ETA: {remaining_sec/60:4.1f}m"
                )

        t_end_logs = time.time()
        print(f"\n[+] Raw insertion of 10,950,000 records finished in {t_end_logs - t_start_logs:.1f}s")

        # Step 5: Rebuild secondary indexes
        recreate_secondary_indexes(cursor, conn)

        # Step 6: Mark checkpoint complete
        mark_checkpoint_complete(cursor, conn)

        # Step 7: Final Benchmark & Metrics
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        total_time = time.time() - start_total_time

        cursor.execute("""
        SELECT table_name, round(((data_length + index_length) / 1024 / 1024), 2) `size_mb`
        FROM information_schema.TABLES 
        WHERE table_schema = 'employee360' AND table_name = 'tabEmployee Activity Log';
        """)
        table_size = cursor.fetchone()
        size_mb = table_size[1] if table_size else "N/A"

        print("=" * 80)
        print("SEED BENCHMARK REPORT")
        print("=" * 80)
        print(f"Total Seeding Duration:       {total_time:.1f} seconds ({total_time/60:.2f} minutes)")
        print(f"Overall Throughput:           {SeedConfig.TOTAL_ACTIVITY_RECORDS / total_time:.1f} records/sec")
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
