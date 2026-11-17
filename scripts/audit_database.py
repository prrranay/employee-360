import sys
import os
import json
import pymysql

conn = pymysql.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="root",
    database="employee360",
    cursorclass=pymysql.cursors.DictCursor
)
cur = conn.cursor()

print("=" * 80)
print("1. TABLE AND INDEX SIZES (IN MARIADB)")
print("=" * 80)

cur.execute("""
    SELECT 
        table_name AS `Table`,
        table_rows AS `Approx Rows`,
        ROUND(data_length / (1024 * 1024), 2) AS `Data MB`,
        ROUND(index_length / (1024 * 1024), 2) AS `Index MB`,
        ROUND((data_length + index_length) / (1024 * 1024), 2) AS `Total MB`
    FROM information_schema.TABLES
    WHERE table_schema = 'employee360'
    ORDER BY (data_length + index_length) DESC;
""")
tables = cur.fetchall()
for t in tables:
    print(f"  {t['Table']:<30} | Rows: {t['Approx Rows']:>10,} | Data: {t['Data MB']:>8.2f} MB | Index: {t['Index MB']:>8.2f} MB | Total: {t['Total MB']:>8.2f} MB")

print("\n" + "=" * 80)
print("2. EXISTING INDEXES PER TABLE")
print("=" * 80)

for t in ["tabEmployee", "tabEmployee Activity Log", "tabEmployee Checkin", "tabAttendance Exception", "tabLeave Application"]:
    cur.execute(f"SHOW INDEX FROM `{t}`")
    indexes = cur.fetchall()
    idx_map = {}
    for idx in indexes:
        name = idx["Key_name"]
        col = idx["Column_name"]
        non_uniq = idx["Non_unique"]
        if name not in idx_map:
            idx_map[name] = {"unique": non_uniq == 0, "columns": []}
        idx_map[name]["columns"].append(col)
    print(f"\nTable: {t}")
    for name, details in idx_map.items():
        uniq_str = "UNIQUE" if details["unique"] else "INDEX "
        cols_str = ", ".join(details["columns"])
        print(f"  - {uniq_str:<7} {name:<30} ({cols_str})")

print("\n" + "=" * 80)
print("3. EXPLAIN PLANS FOR CRITICAL HIGH-VOLUME QUERIES")
print("=" * 80)

queries = [
    ("Employee + Date range seek (Profile History)", 
     "EXPLAIN SELECT * FROM `tabEmployee Activity Log` WHERE employee = 'EMP-01362' AND activity_date BETWEEN '2026-01-01' AND '2026-03-31' ORDER BY activity_date DESC LIMIT 15"),
    
    ("Single Date Company Dashboard Status Aggregation",
     "EXPLAIN SELECT attendance_status, COUNT(*), AVG(total_work_seconds) FROM `tabEmployee Activity Log` WHERE activity_date = '2026-11-16' GROUP BY attendance_status"),
    
    ("Department Analytics Join",
     "EXPLAIN SELECT e.department, COUNT(e.name), SUM(CASE WHEN al.attendance_status='Present' THEN 1 ELSE 0 END) FROM `tabEmployee Activity Log` al JOIN `tabEmployee` e ON e.name = al.employee WHERE al.activity_date = '2026-11-16' GROUP BY e.department"),
    
    ("Employee Autocomplete Search",
     "EXPLAIN SELECT name, employee_name, department FROM `tabEmployee` WHERE employee_name LIKE 'Elena%' OR employee_id LIKE 'EMP-013%' LIMIT 10"),
    
    ("Manager Hierarchy Recursive Lookup / Subtree",
     "EXPLAIN SELECT name, employee_name, department FROM `tabEmployee` WHERE manager = 'EMP-00001'"),
    
    ("Leave Application Overlap Check",
     "EXPLAIN SELECT name FROM `tabLeave Application` WHERE employee = 'EMP-01362' AND status IN ('Approved', 'Pending') AND from_date <= '2026-11-20' AND to_date >= '2026-11-15'"),
    
    ("Checkin Timestamp Lookup (Recent punches / Debounce)",
     "EXPLAIN SELECT name, time, log_type FROM `tabEmployee Checkin` WHERE employee = 'EMP-01362' AND time > '2026-11-16 00:00:00' ORDER BY time DESC"),
    
    ("Company Attendance Trend (30 Days Aggregation)",
     "EXPLAIN SELECT activity_date, SUM(CASE WHEN attendance_status = 'Present' THEN 1 ELSE 0 END) FROM `tabEmployee Activity Log` FORCE INDEX (idx_eal_date_status) WHERE activity_date BETWEEN '2026-10-17' AND '2026-11-16' GROUP BY activity_date")
]

for label, q in queries:
    print(f"\n---> {label}")
    print(f"     Query: {q}")
    cur.execute(q)
    rows = cur.fetchall()
    for r in rows:
        key = r.get("key") or "NULL"
        ref = r.get("ref") or "NULL"
        extra = r.get("Extra") or ""
        print(f"     [Plan] Table: {r.get('table')} | Type: {r.get('type')} | Key: {key} | Key_len: {r.get('key_len')} | Rows: {r.get('rows')} | Filtered: {r.get('filtered')}% | Extra: {extra}")

print("\n" + "=" * 80)
print("4. LOCK CONTENTION & SLOW QUERY STATUS")
print("=" * 80)

status_vars = [
    "Slow_queries", "Table_locks_immediate", "Table_locks_waited", 
    "Innodb_row_lock_current_waits", "Innodb_row_lock_time", "Innodb_row_lock_waits",
    "Innodb_buffer_pool_read_requests", "Innodb_buffer_pool_reads"
]
for var in status_vars:
    cur.execute(f"SHOW STATUS LIKE '{var}'")
    res = cur.fetchone()
    print(f"  {res['Variable_name']:<35}: {res['Value']}")
