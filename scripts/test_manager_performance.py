import time
import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root', password='root', database='employee360',
    cursorclass=pymysql.cursors.DictCursor
)
cur = conn.cursor()

target_date = "2026-11-16"
t0 = time.time()

# Get all managers with designation containing 'Manager' or 'Director' or 'VP'
cur.execute("""
    SELECT DISTINCT m.name, m.employee_name, m.department, m.designation
    FROM `tabEmployee` m
    WHERE m.designation LIKE '%Manager%' 
       OR m.designation LIKE '%Director%'
       OR m.designation LIKE '%VP%'
       OR m.name IN ('EMP-00012', 'EMP-00013')
    ORDER BY m.department, m.employee_name
    LIMIT 30;
""")
managers = cur.fetchall()
print(f"Found {len(managers)} key managers in {time.time() - t0:.3f}s")

# For each manager, we can calculate their direct + indirect reports' attendance on target_date
manager_stats = []
t1 = time.time()

# Let's test single aggregated query joining Employee reports with Activity Log on target_date
cur.execute("""
    SELECT 
        m.name AS manager_id,
        m.employee_name AS manager_name,
        m.department,
        m.designation,
        COUNT(e.name) AS direct_reports_count,
        SUM(CASE WHEN al.attendance_status = 'Present' THEN 1 ELSE 0 END) AS present_count,
        SUM(CASE WHEN al.attendance_status = 'Late' THEN 1 ELSE 0 END) AS late_count,
        SUM(CASE WHEN al.attendance_status = 'Half Day' THEN 1 ELSE 0 END) AS half_day_count,
        SUM(CASE WHEN al.attendance_status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
        SUM(CASE WHEN al.attendance_status = 'On Leave' THEN 1 ELSE 0 END) AS on_leave_count,
        SUM(CASE WHEN al.attendance_status = 'Missing Check-out' THEN 1 ELSE 0 END) AS missing_out_count,
        AVG(CASE WHEN al.total_work_seconds > 0 THEN al.total_work_seconds ELSE NULL END) AS avg_work_sec
    FROM `tabEmployee` m
    JOIN `tabEmployee` e ON e.manager = m.name
    LEFT JOIN `tabEmployee Activity Log` al 
           ON al.employee = e.name AND al.activity_date = %(target_date)s
    WHERE m.designation LIKE '%%Manager%%' 
       OR m.designation LIKE '%%Director%%' 
       OR m.designation LIKE '%%VP%%'
       OR m.name IN ('EMP-00012', 'EMP-00013')
    GROUP BY m.name
    ORDER BY direct_reports_count DESC, m.employee_name ASC;
""", {"target_date": target_date})

perf_rows = cur.fetchall()
print(f"Aggregated performance for {len(perf_rows)} managers in {time.time() - t1:.3f}s")
for r in perf_rows[:5]:
    total = r["direct_reports_count"]
    attended = r["present_count"] + r["late_count"] + (r["half_day_count"] * 0.5)
    rate = round((attended / total) * 100, 1) if total > 0 else 0
    sec = int(r["avg_work_sec"] or 0)
    print(f"Manager: {r['manager_name']} ({r['department']}) | Reports: {total} | Attended: {attended} ({rate}%) | Avg: {sec//3600}h {(sec%3600)//60}m")

conn.close()
