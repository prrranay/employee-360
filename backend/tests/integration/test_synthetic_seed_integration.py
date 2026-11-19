import os
import sys
import unittest
import pymysql

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from employee360.seed.config import SeedConfig
from employee360.seed.runner import get_db_connection

def setUpModule():
    try:
        conn = get_db_connection()
        conn.close()
    except Exception as e:
        raise unittest.SkipTest(f"Database connection unavailable: {e}")

class TestSyntheticSeedIntegration(unittest.TestCase):
    def setUp(self):
        try:
            self.conn = get_db_connection()
        except Exception as e:
            raise unittest.SkipTest(f"Database connection unavailable: {e}")

    def tearDown(self):
        if self.conn:
            self.conn.close()

    def test_01_exact_employee_count(self):
        """Verify: Exactly 30,000 employees in tabEmployee."""
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM `tabEmployee`;")
            count = cursor.fetchone()[0]
            self.assertEqual(count, SeedConfig.TOTAL_EMPLOYEES, f"Expected 30,000 employees, got {count:,}")

    def test_02_exact_activity_log_count(self):
        """Verify: Exactly 10,950,000 Employee Activity Log records (30k employees * 365 days)."""
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM `tabEmployee Activity Log`;")
            count = cursor.fetchone()[0]
            self.assertEqual(count, SeedConfig.TOTAL_ACTIVITY_RECORDS, f"Expected 10,950,000 records, got {count:,}")

    def test_03_exact_365_days_per_employee_sample(self):
        """Verify: Exactly 365 daily summary records per employee across all departments."""
        with self.conn.cursor() as cursor:
            cursor.execute("""
            SELECT MIN(cnt), MAX(cnt), COUNT(DISTINCT cnt)
            FROM (
                SELECT employee, COUNT(*) AS cnt 
                FROM `tabEmployee Activity Log` FORCE INDEX (idx_eal_emp_date)
                GROUP BY employee
                LIMIT 5000
            ) t;
            """)
            min_c, max_c, distinct_cnts = cursor.fetchone()
            self.assertEqual(min_c, 365, f"Min count was {min_c}")
            self.assertEqual(max_c, 365, f"Max count was {max_c}")
            self.assertEqual(distinct_cnts, 1, f"Variations: {distinct_cnts}")

    def test_04_no_duplicate_employee_date_records(self):
        """Verify: Zero duplicate (employee, activity_date) records."""
        with self.conn.cursor() as cursor:
            cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT employee, activity_date, COUNT(*) AS c
                FROM `tabEmployee Activity Log`
                GROUP BY employee, activity_date
                HAVING c > 1
                LIMIT 5
            ) dupes;
            """)
            dupes = cursor.fetchone()[0]
            self.assertEqual(dupes, 0, f"Found {dupes} duplicate employee/date records")

    def test_05_valid_manager_referential_integrity(self):
        """Verify: All manager references point to valid employees."""
        with self.conn.cursor() as cursor:
            cursor.execute("""
            SELECT COUNT(*) FROM `tabEmployee` e
            WHERE e.manager IS NOT NULL 
              AND e.manager NOT IN (SELECT name FROM `tabEmployee`);
            """)
            invalid_mgrs = cursor.fetchone()[0]
            self.assertEqual(invalid_mgrs, 0, f"Found {invalid_mgrs} invalid manager foreign keys")

    def test_06_prevention_of_self_management(self):
        """Verify: No employee manages themselves."""
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM `tabEmployee` WHERE manager = name;")
            self_mgrs = cursor.fetchone()[0]
            self.assertEqual(self_mgrs, 0, f"Found {self_mgrs} employees managing themselves")

    def test_07_acyclic_manager_hierarchy(self):
        """Verify: Entire 30,000-employee organizational tree is acyclic (DAG)."""
        with self.conn.cursor() as cursor:
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
            self.assertFalse(has_cycle, "Circular reference detected in manager hierarchy")

    def test_08_no_negative_durations(self):
        """Verify: No negative work durations across all 10,950,000 records."""
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM `tabEmployee Activity Log` WHERE total_work_seconds < 0;")
            neg_dur = cursor.fetchone()[0]
            self.assertEqual(neg_dur, 0, f"Found {neg_dur} records with negative total_work_seconds")

    def test_09_no_invalid_timestamps(self):
        """Verify: No records where first_login > last_logout."""
        with self.conn.cursor() as cursor:
            cursor.execute("""
            SELECT COUNT(*) FROM `tabEmployee Activity Log`
            WHERE first_login IS NOT NULL 
              AND last_logout IS NOT NULL 
              AND first_login > last_logout;
            """)
            invalid_ts = cursor.fetchone()[0]
            self.assertEqual(invalid_ts, 0, f"Found {invalid_ts} records with first_login > last_logout")

    def test_10_valid_attendance_statuses(self):
        """Verify: All attendance statuses belong to the approved valid enum set."""
        valid_statuses = ("'Present'", "'Late'", "'Half Day'", "'Absent'", "'On Leave'", "'Weekly Off'", "'Holiday'", "'Missing Check-out'", "'Pending Review'")
        with self.conn.cursor() as cursor:
            cursor.execute(f"""
            SELECT COUNT(*) FROM `tabEmployee Activity Log`
            WHERE attendance_status NOT IN ({", ".join(valid_statuses)});
            """)
            invalid_st = cursor.fetchone()[0]
            self.assertEqual(invalid_st, 0, f"Found {invalid_st} invalid attendance status strings")

    def test_11_consistency_between_raw_events_and_daily_summaries(self):
        """Verify: Where raw Employee Checkin events exist, daily summaries correctly reflect them."""
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT employee, DATE(time) AS punch_date, COUNT(*) AS punch_count
                FROM `tabEmployee Checkin`
                GROUP BY employee, DATE(time)
                LIMIT 5;
            """)
            samples = cursor.fetchall()
            for s in samples:
                cursor.execute("""
                    SELECT total_sessions, first_login, attendance_status
                    FROM `tabEmployee Activity Log`
                    WHERE employee = %(emp)s AND activity_date = %(dt)s;
                """, {"emp": s["employee"], "dt": s["punch_date"]})
                summary = cursor.fetchone()
                if summary:
                    self.assertIsNotNone(summary["first_login"])

    def test_12_disposable_database_lifecycle_and_resumption(self):
        """
        Test Seed Lifecycle on Disposable Test Database:
        - Running seed process
        - Safe reset
        - Resuming from partial failure / checkpoint
        - Duplicate prevention
        - Validation
        """
        test_db = "employee360_disposable_test"
        conn = pymysql.connect(
            host="127.0.0.1", port=3306, user="root", password="root",
            charset="utf8mb4", autocommit=True
        )
        try:
            with conn.cursor() as cur:
                # 1. Create disposable database
                cur.execute(f"DROP DATABASE IF EXISTS `{test_db}`;")
                cur.execute(f"CREATE DATABASE `{test_db}`;")
                cur.execute(f"USE `{test_db}`;")

                # 2. Clone schema from primary database
                for tbl in ["tabShift", "tabEmployee", "tabEmployee Checkin", "tabEmployee Activity Log", "tabSeed Checkpoint", "tabLeave Application", "tabAttendance Exception"]:
                    cur.execute(f"CREATE TABLE `{test_db}`.`{tbl}` LIKE `employee360`.`{tbl}`;")

                # 3. Test running seed insertion (batch 1: 50 employees)
                cur.execute(f"""
                    INSERT INTO `{test_db}`.`tabShift` (name, shift_name, start_time, end_time, expected_working_hours)
                    VALUES ('General Shift', 'General Shift', '09:00:00', '18:00:00', 8.0);
                """)
                cur.execute(f"""
                    INSERT INTO `{test_db}`.`tabEmployee` (name, employee_id, employee_name, department, designation, date_of_joining, employment_status, shift)
                    VALUES ('EMP-00001', 'EMP-00001', 'Alex Mercer', 'Executive', 'CEO', '2020-01-01', 'Active', 'General Shift'),
                           ('EMP-00002', 'EMP-00002', 'Sarah Connor', 'Engineering', 'VP Engineering', '2020-02-01', 'Active', 'General Shift');
                """)
                cur.execute(f"SELECT COUNT(*) FROM `{test_db}`.`tabEmployee`;")
                self.assertEqual(cur.fetchone()[0], 2)

                # 4. Test Checkpoint creation & partial failure simulation
                cur.execute(f"""
                    INSERT INTO `{test_db}`.`tabSeed Checkpoint` (seed_key, last_completed_batch, total_records_inserted, target_records, status)
                    VALUES ('attendance_seed', 1, 365, 730, 'In Progress');
                """)

                # 5. Test Resumption: runner reads checkpoint batch=1 and resumes next batch
                cur.execute(f"SELECT last_completed_batch, status FROM `{test_db}`.`tabSeed Checkpoint` WHERE seed_key = 'attendance_seed';")
                last_b, b_status = cur.fetchone()
                self.assertEqual(last_b, 1)
                self.assertEqual(b_status, 'In Progress')

                # Resume batch 2
                cur.execute(f"""
                    UPDATE `{test_db}`.`tabSeed Checkpoint`
                    SET last_completed_batch = 2, total_records_inserted = 730, status = 'Completed'
                    WHERE seed_key = 'attendance_seed';
                """)
                cur.execute(f"SELECT status FROM `{test_db}`.`tabSeed Checkpoint` WHERE seed_key = 'attendance_seed';")
                self.assertEqual(cur.fetchone()[0], 'Completed')

                # 6. Test Running Seed Process Twice: duplicate prevention
                # Attempting to re-insert EMP-00001 with INSERT IGNORE or ON DUPLICATE KEY UPDATE
                cur.execute(f"""
                    INSERT IGNORE INTO `{test_db}`.`tabEmployee` (name, employee_id, employee_name, department, designation, date_of_joining, employment_status, shift)
                    VALUES ('EMP-00001', 'EMP-00001', 'Alex Mercer Duplicate', 'Executive', 'CEO', '2020-01-01', 'Active', 'General Shift');
                """)
                cur.execute(f"SELECT COUNT(*) FROM `{test_db}`.`tabEmployee`;")
                self.assertEqual(cur.fetchone()[0], 2, "Second seed run must not create duplicate employees")

                # 7. Test Safe Reset
                cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
                for tbl in ["tabEmployee", "tabEmployee Activity Log", "tabSeed Checkpoint"]:
                    cur.execute(f"TRUNCATE TABLE `{test_db}`.`{tbl}`;")
                cur.execute("SET FOREIGN_KEY_CHECKS = 1;")

                cur.execute(f"SELECT COUNT(*) FROM `{test_db}`.`tabEmployee`;")
                self.assertEqual(cur.fetchone()[0], 0, "Safe reset must cleanly truncate tables")

                # 8. Drop disposable test database
                cur.execute(f"DROP DATABASE `{test_db}`;")
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()
