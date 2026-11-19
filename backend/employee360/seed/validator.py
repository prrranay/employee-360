import datetime
import os
import sys
import time
import pymysql

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from employee360.seed.config import SeedConfig
from employee360.seed.runner import get_db_connection


def validate_all():
    print("=" * 80)
    print("Employee360 — Seed Dataset Validation & Relational Integrity Verification")
    print(f"Target Configuration: {SeedConfig.TOTAL_EMPLOYEES:,} Employees | {SeedConfig.TOTAL_ACTIVITY_RECORDS:,} Activity Logs")
    print("=" * 80)

    t0 = time.time()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
    except Exception as e:
        print(f"  [ERROR] Cannot connect to database: {e}")
        return False

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
        # 1. Total Employee count == SeedConfig.TOTAL_EMPLOYEES
        cursor.execute("SELECT COUNT(*) FROM `tabEmployee`;")
        emp_count = cursor.fetchone()[0]
        check(
            "Employee Count",
            emp_count == SeedConfig.TOTAL_EMPLOYEES,
            f"Found {emp_count:,} (Expected: {SeedConfig.TOTAL_EMPLOYEES:,})"
        )

        # 2. Total Activity Log count == SeedConfig.TOTAL_ACTIVITY_RECORDS
        cursor.execute("SELECT COUNT(*) FROM `tabEmployee Activity Log`;")
        log_count = cursor.fetchone()[0]
        check(
            "Activity Log Count",
            log_count == SeedConfig.TOTAL_ACTIVITY_RECORDS,
            f"Found {log_count:,} (Expected: {SeedConfig.TOTAL_ACTIVITY_RECORDS:,})"
        )

        # 3. Exactly 365 daily activity records per employee
        cursor.execute("""
        SELECT MIN(cnt), MAX(cnt), COUNT(DISTINCT cnt)
        FROM (
            SELECT employee, COUNT(*) AS cnt 
            FROM `tabEmployee Activity Log` 
            GROUP BY employee
        ) t;
        """)
        row = cursor.fetchone()
        min_c = row[0] if row else 0
        max_c = row[1] if row else 0
        distinct_cnts = row[2] if row else 0
        check(
            "365 Records Per Employee",
            (min_c == 365 and max_c == 365 and distinct_cnts == 1),
            f"Min={min_c}, Max={max_c}, Variations={distinct_cnts}"
        )

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

        # 5. Valid Employee references in Activity Log
        cursor.execute("""
        SELECT COUNT(*) FROM `tabEmployee Activity Log` al
        WHERE al.employee NOT IN (SELECT name FROM `tabEmployee`);
        """)
        invalid_emps = cursor.fetchone()[0]
        check("Employee Referential Integrity", invalid_emps == 0, f"Found {invalid_emps} orphaned activity log records")

        # 6. Valid Manager references
        cursor.execute("""
        SELECT COUNT(*) FROM `tabEmployee` e
        WHERE e.manager IS NOT NULL 
          AND e.manager NOT IN (SELECT name FROM `tabEmployee`);
        """)
        invalid_mgrs = cursor.fetchone()[0]
        check("Manager Referential Integrity", invalid_mgrs == 0, f"Found {invalid_mgrs} invalid manager foreign keys")

        # 7. No employee manages themselves
        cursor.execute("SELECT COUNT(*) FROM `tabEmployee` WHERE manager = name;")
        self_mgrs = cursor.fetchone()[0]
        check("Self-Management Prevention", self_mgrs == 0, f"Found {self_mgrs} employees managing themselves")

        # 8. No circular manager cycles
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
        check("Acyclic Hierarchy", not has_cycle, f"All {len(all_emps):,} manager links form a valid directed acyclic graph")

        # 9. No negative work durations
        cursor.execute("SELECT COUNT(*) FROM `tabEmployee Activity Log` WHERE total_work_seconds < 0;")
        neg_work = cursor.fetchone()[0]
        check("Non-negative Work Seconds", neg_work == 0, f"Found {neg_work} negative duration records")

        # 10. No impossible timestamp sequences (first_login <= last_logout)
        cursor.execute("""
        SELECT COUNT(*) FROM `tabEmployee Activity Log`
        WHERE first_login IS NOT NULL 
          AND last_logout IS NOT NULL 
          AND first_login > last_logout;
        """)
        impossible_ts = cursor.fetchone()[0]
        check("Chronological Login/Logout", impossible_ts == 0, f"Found {impossible_ts} records where first_login > last_logout")

        # 11. Work duration does not exceed total elapsed time
        cursor.execute("""
        SELECT COUNT(*) FROM `tabEmployee Activity Log`
        WHERE first_login IS NOT NULL 
          AND last_logout IS NOT NULL 
          AND total_work_seconds > TIME_TO_SEC(TIMEDIFF(last_logout, first_login));
        """)
        exceeded_dur = cursor.fetchone()[0]
        check("Duration Within Elapsed Bounds", exceeded_dur == 0, f"Found {exceeded_dur} records where duration > elapsed interval")

        # 12. Missing checkout has no fabricated completed duration or logout
        cursor.execute("""
        SELECT COUNT(*) FROM `tabEmployee Activity Log`
        WHERE attendance_status = 'Missing Check-out'
          AND (last_logout IS NOT NULL OR total_work_seconds > 0);
        """)
        fabricated = cursor.fetchone()[0]
        check("Missing Checkout Invariants", fabricated == 0, f"Found {fabricated} missing-checkout records with fabricated duration/logout")

        # 13. Missing checkout has a corresponding Attendance Exception
        cursor.execute("""
        SELECT COUNT(*) FROM `tabEmployee Activity Log` al
        WHERE al.attendance_status = 'Missing Check-out'
          AND NOT EXISTS (
            SELECT 1 FROM `tabAttendance Exception` ae
            WHERE ae.employee = al.employee
              AND ae.activity_date = al.activity_date
              AND ae.exception_type = 'Missing Check-out'
          );
        """)
        missing_excs = cursor.fetchone()[0]
        check("Missing Checkout Exception Link", missing_excs == 0, f"Found {missing_excs} missing-checkout records without Attendance Exception")

        # 14. LEAVE INTEGRITY: No 'On Leave' summary without approved leave coverage
        cursor.execute("""
        SELECT COUNT(*) FROM `tabEmployee Activity Log` al
        WHERE al.attendance_status = 'On Leave'
          AND NOT EXISTS (
            SELECT 1 FROM `tabLeave Application` la
            WHERE la.employee = al.employee
              AND la.status = 'Approved'
              AND al.activity_date BETWEEN la.from_date AND la.to_date
          );
        """)
        unbacked_leaves = cursor.fetchone()[0]
        check("Leave Coverage Backing", unbacked_leaves == 0, f"Found {unbacked_leaves} 'On Leave' records without matching approved leave application")

        # 15. LEAVE INTEGRITY: Approved leave working days are reflected as 'On Leave'
        holiday_sql_list = ", ".join([f"'{d.strftime('%Y-%m-%d')}'" for d in SeedConfig.HOLIDAYS.keys()])
        cursor.execute(f"""
        SELECT COUNT(*) FROM `tabLeave Application` la
        JOIN `tabEmployee Activity Log` al
          ON al.employee = la.employee
         AND al.activity_date BETWEEN la.from_date AND la.to_date
        WHERE la.status = 'Approved'
          AND DAYOFWEEK(al.activity_date) NOT IN (1, 7)
          AND al.activity_date NOT IN ({holiday_sql_list})
          AND al.attendance_status != 'On Leave';
        """)
        missing_on_leave = cursor.fetchone()[0]
        check("Approved Leave Attendance Reflection", missing_on_leave == 0, f"Found {missing_on_leave} working days during approved leaves not marked 'On Leave'")

        # 16. LEAVE INTEGRITY: Non-approved leaves (Rejected, Pending) are never treated as approved
        cursor.execute("""
        SELECT COUNT(*) FROM `tabLeave Application` la
        JOIN `tabEmployee Activity Log` al
          ON al.employee = la.employee
         AND al.activity_date BETWEEN la.from_date AND la.to_date
        WHERE la.status != 'Approved'
          AND al.attendance_status = 'On Leave'
          AND NOT EXISTS (
            SELECT 1 FROM `tabLeave Application` la2
            WHERE la2.employee = al.employee
              AND la2.status = 'Approved'
              AND al.activity_date BETWEEN la2.from_date AND la2.to_date
          );
        """)
        invalid_approved = cursor.fetchone()[0]
        check("Non-Approved Leave Isolation", invalid_approved == 0, f"Found {invalid_approved} 'On Leave' records backed only by rejected/pending leaves")

        # 17. LEAVE INTEGRITY: No overlapping approved leaves for the same employee
        cursor.execute("""
        SELECT COUNT(*) FROM `tabLeave Application` l1
        JOIN `tabLeave Application` l2
          ON l1.employee = l2.employee
         AND l1.name < l2.name
         AND l1.status = 'Approved'
         AND l2.status = 'Approved'
         AND NOT (l1.to_date < l2.from_date OR l1.from_date > l2.to_date);
        """)
        overlapping_leaves = cursor.fetchone()[0]
        check("Non-Overlapping Leave Periods", overlapping_leaves == 0, f"Found {overlapping_leaves} overlapping approved leave periods")

        # 18. Valid Attendance Status values
        valid_statuses = ("Present", "Late", "Half Day", "Absent", "On Leave", "Weekly Off", "Holiday", "Missing Check-out", "Pending Review")
        placeholders = ", ".join([f"'{s}'" for s in valid_statuses])
        cursor.execute(f"SELECT COUNT(*) FROM `tabEmployee Activity Log` WHERE attendance_status NOT IN ({placeholders});")
        invalid_statuses = cursor.fetchone()[0]
        check("Valid Attendance Statuses", invalid_statuses == 0, f"Found {invalid_statuses} invalid status values")

        # 19. Weekly Off Schedule Consistency (Weekends are Weekly Off or Holiday)
        cursor.execute("""
        SELECT COUNT(*) FROM `tabEmployee Activity Log`
        WHERE DAYOFWEEK(activity_date) IN (1, 7)
          AND attendance_status NOT IN ('Weekly Off', 'Holiday');
        """)
        mismatched_weekend = cursor.fetchone()[0]
        check("Weekly Off Schedule Consistency", mismatched_weekend == 0, f"Found {mismatched_weekend} weekend records not marked Weekly Off or Holiday")

        # 20. Configured Holidays Consistency
        cursor.execute(f"""
        SELECT COUNT(*) FROM `tabEmployee Activity Log`
        WHERE activity_date IN ({holiday_sql_list})
          AND attendance_status != 'Holiday';
        """)
        mismatched_holidays = cursor.fetchone()[0]
        check("Holiday Consistency", mismatched_holidays == 0, f"Found {mismatched_holidays} holiday dates not marked Holiday")

        # 21. Active computer usage is not presented as measured
        cursor.execute("""
        SELECT COUNT(*) FROM `tabEmployee Activity Log`
        WHERE active_seconds IS NOT NULL 
          AND active_seconds = total_work_seconds 
          AND total_work_seconds > 0;
        """)
        false_active = cursor.fetchone()[0]
        check("Unmeasured Active Seconds", false_active == 0, f"Found {false_active} records falsely presenting work seconds as measured active usage")

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
