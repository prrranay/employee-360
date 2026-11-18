import os
import sys
import time
import pymysql

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from employee360.seed.config import SeedConfig
from employee360.seed.runner import get_db_connection

def validate_all():
    print("=" * 80)
    print("Employee360 — Seed Dataset Validation & Integrity Verification")
    print("=" * 80)

    t0 = time.time()
    conn = get_db_connection()
    cursor = conn.cursor()

    errors = []
    successes = []

    def check(name: str, passed: bool, message: str):
        if passed:
            print(f"  [PASS] {name:<45} {message}")
            successes.append(name)
        else:
            print(f"  [FAIL] {name:<45} {message}")
            errors.append(f"{name}: {message}")

    try:
        # 1. Total Employee count == 30,000
        cursor.execute("SELECT COUNT(*) FROM `tabEmployee`;")
        emp_count = cursor.fetchone()[0]
        check("Employee Count", emp_count == SeedConfig.TOTAL_EMPLOYEES, f"Found {emp_count:,} (Expected: {SeedConfig.TOTAL_EMPLOYEES:,})")

        # 2. Total Activity Log count == 10,950,000
        cursor.execute("SELECT COUNT(*) FROM `tabEmployee Activity Log`;")
        log_count = cursor.fetchone()[0]
        check("Activity Log Count", log_count == SeedConfig.TOTAL_ACTIVITY_RECORDS, f"Found {log_count:,} (Expected: {SeedConfig.TOTAL_ACTIVITY_RECORDS:,})")

        # 3. Exactly 365 daily activity records per employee
        cursor.execute("""
        SELECT MIN(cnt), MAX(cnt), COUNT(DISTINCT cnt)
        FROM (
            SELECT employee, COUNT(*) AS cnt 
            FROM `tabEmployee Activity Log` 
            GROUP BY employee
        ) t;
        """)
        min_c, max_c, distinct_cnts = cursor.fetchone()
        check("365 Records Per Employee", (min_c == 365 and max_c == 365 and distinct_cnts == 1), f"Min={min_c}, Max={max_c}, Variations={distinct_cnts}")

        # 4. No duplicate employee/date combinations
        cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT employee, activity_date, COUNT(*) AS c
            FROM `tabEmployee Activity Log`
            GROUP BY employee, activity_date
            HAVING c > 1
            LIMIT 5
        ) dupes;
        """)
        dup_count = cursor.fetchone()[0]
        check("Duplicate Detection", dup_count == 0, f"Found {dup_count} duplicate employee/date pairs")

        # 5. Valid Manager references
        cursor.execute("""
        SELECT COUNT(*) FROM `tabEmployee` e
        WHERE e.manager IS NOT NULL 
          AND e.manager NOT IN (SELECT name FROM `tabEmployee`);
        """)
        invalid_mgrs = cursor.fetchone()[0]
        check("Manager Referential Integrity", invalid_mgrs == 0, f"Found {invalid_mgrs} invalid manager foreign keys")

        # 6. No employee manages themselves
        cursor.execute("SELECT COUNT(*) FROM `tabEmployee` WHERE manager = name;")
        self_mgrs = cursor.fetchone()[0]
        check("Self-Management Prevention", self_mgrs == 0, f"Found {self_mgrs} employees managing themselves")

        # 7. No circular manager cycles
        cursor.execute("SELECT name, manager FROM `tabEmployee`;")
        all_emps = cursor.fetchall()
        mgr_map = {r[0]: r[1] for r in all_emps}
        has_cycle = False
        for emp, mgr in mgr_map.items():
            visited = {emp}
            curr = mgr
            while curr:
                if curr in visited:
                    has_cycle = True
                    break
                visited.add(curr)
                curr = mgr_map.get(curr)
            if has_cycle:
                break
        check("Acyclic Hierarchy", not has_cycle, "All 30,000 manager links form a valid directed acyclic tree")

        # 8. No negative work durations
        cursor.execute("SELECT COUNT(*) FROM `tabEmployee Activity Log` WHERE total_work_seconds < 0;")
        neg_work = cursor.fetchone()[0]
        check("Non-negative Work Seconds", neg_work == 0, f"Found {neg_work} negative duration records")

        # 9. No impossible timestamp sequences
        cursor.execute("""
        SELECT COUNT(*) FROM `tabEmployee Activity Log`
        WHERE first_login IS NOT NULL 
          AND last_logout IS NOT NULL 
          AND first_login > last_logout;
        """)
        impossible_ts = cursor.fetchone()[0]
        check("Chronological Login/Logout", impossible_ts == 0, f"Found {impossible_ts} records where first_login > last_logout")

        # 10. Missing checkout has no fabricated completed duration
        cursor.execute("""
        SELECT COUNT(*) FROM `tabEmployee Activity Log`
        WHERE attendance_status = 'Missing Check-out'
          AND (last_logout IS NOT NULL OR total_work_seconds > 0);
        """)
        fabricated = cursor.fetchone()[0]
        check("Missing Checkout Invariants", fabricated == 0, f"Found {fabricated} missing-checkout records with fabricated duration/logout")

        # 11. Attendance Status Validations
        valid_statuses = ("Present", "Late", "Half Day", "Absent", "On Leave", "Weekly Off", "Holiday", "Missing Check-out", "Pending Review")
        placeholders = ", ".join([f"'{s}'" for s in valid_statuses])
        cursor.execute(f"SELECT COUNT(*) FROM `tabEmployee Activity Log` WHERE attendance_status NOT IN ({placeholders});")
        invalid_statuses = cursor.fetchone()[0]
        check("Valid Attendance Statuses", invalid_statuses == 0, f"Found {invalid_statuses} invalid status values")

        # 12. Weekly Off Consistency
        # 12. Weekly Off Schedule Consistency (all weekend days must be Weekly Off or official Holiday)
        cursor.execute("""
        SELECT COUNT(*) FROM `tabEmployee Activity Log`
        WHERE DAYOFWEEK(activity_date) IN (1, 7) -- 1=Sun, 7=Sat
          AND attendance_status NOT IN ('Weekly Off', 'Holiday');
        """)
        mismatched_weekend = cursor.fetchone()[0]
        check("Weekly Off Schedule Consistency", mismatched_weekend == 0, f"Found {mismatched_weekend} weekend records not marked Weekly Off or Holiday")

    except Exception as e:
        print(f"\n[!] Unexpected error during validation: {e}")
        errors.append(str(e))
    finally:
        cursor.close()
        conn.close()

    elapsed = time.time() - t0
    print("=" * 80)
    print(f"Validation Finished in {elapsed:.2f} seconds.")
    print(f"Result: {len(successes)} Passed, {len(errors)} Failed.")
    print("=" * 80)

    if errors:
        sys.exit(1)
    else:
        print("[+] ALL DATASET INTEGRITY CHECKS PASSED PERFECTLY!\n")

if __name__ == "__main__":
    validate_all()

