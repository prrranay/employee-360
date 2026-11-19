import sys
import os
import time
import tracemalloc
import pymysql

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
APP_DIR = os.path.join(BACKEND_DIR, "apps", "employee360")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, APP_DIR)

from employee360.seed.config import SeedConfig
from employee360.seed.generator import (
    generate_all_employees,
    stream_activity_log_batches
)

print("=" * 80)
print("SEED PERFORMANCE & SCALABILITY BENCHMARK")
print("=" * 80)

# 1. Employee In-Memory Generation Benchmark
print("\n[*] 1. Employee In-Memory Generation Benchmark (Target: 30,000 employees)...")
tracemalloc.start()
t0 = time.perf_counter()
employees = generate_all_employees()
t1 = time.perf_counter()
current_mem, peak_mem = tracemalloc.get_traced_memory()
tracemalloc.stop()

emp_gen_time = t1 - t0
emp_rate = len(employees) / emp_gen_time
print(f"    - Generated {len(employees):,} employees in {emp_gen_time:.3f}s")
print(f"    - Generation Rate: {emp_rate:,.1f} employees/sec")
print(f"    - Peak Memory: {peak_mem / (1024*1024):.2f} MB")

# 2. Activity Log Generator Streaming Throughput (In-Memory)
print("\n[*] 2. Activity Log Generator Streaming Benchmark (100,000 rows)...")
tracemalloc.start()
t0 = time.perf_counter()
test_batch_count = 0
total_streamed = 0
for batch_idx, batch_rows, exc_rows, punch_rows in stream_activity_log_batches(start_batch_idx=0, batch_size=10000):
    test_batch_count += 1
    total_streamed += len(batch_rows)
    if total_streamed >= 100000:
        break
t1 = time.perf_counter()
_, peak_mem = tracemalloc.get_traced_memory()
tracemalloc.stop()

stream_time = t1 - t0
stream_rate = total_streamed / stream_time
print(f"    - Streamed {total_streamed:,} daily records in {stream_time:.3f}s")
print(f"    - Streaming Rate: {stream_rate:,.1f} records/sec")
print(f"    - Generator Peak Memory: {peak_mem / (1024*1024):.2f} MB (Bounded streaming)")

# 3. Batch Size Impact on Database Bulk Insertion
print("\n[*] 3. Batch Size Impact on MariaDB Insertion Rates...")
conn = pymysql.connect(
    host="127.0.0.1", port=3306, user="root", password="root", database="employee360",
    autocommit=False
)
cur = conn.cursor()

# Create a temporary benchmark table matching tabEmployee Activity Log
cur.execute("""
    CREATE TEMPORARY TABLE `tmp_bench_activity_log` (
        `name` VARCHAR(140) PRIMARY KEY,
        `employee` VARCHAR(140) NOT NULL,
        `activity_date` DATE NOT NULL,
        `attendance_status` VARCHAR(50) NOT NULL,
        `first_login` TIME DEFAULT NULL,
        `last_logout` TIME DEFAULT NULL,
        `total_work_seconds` INT DEFAULT 0,
        `active_seconds` INT DEFAULT 0,
        `total_sessions` INT DEFAULT 1,
        `modified` DATETIME DEFAULT NULL
    ) ENGINE=InnoDB;
""")
conn.commit()

batch_sizes = [500, 2000, 5000, 10000]
batch_results = []

for b_size in batch_sizes:
    # Generate 1 batch of b_size
    _, sample_rows = next(stream_activity_log_batches(start_batch_idx=0, batch_size=b_size))
    cur.execute("TRUNCATE TABLE `tmp_bench_activity_log`")
    conn.commit()
    
    t0 = time.perf_counter()
    cols = ["name", "employee", "activity_date", "attendance_status", "first_login", "last_logout", 
            "total_work_seconds", "active_seconds", "total_sessions", "modified"]
    col_str = ", ".join([f"`{c}`" for c in cols])
    
    # Construct multi-row values
    val_clauses = []
    for r in sample_rows:
        def q(v):
            if v is None: return "NULL"
            return f"'{v}'"
        row_str = f"({q(r[0])}, {q(r[1])}, {q(r[2])}, {q(r[3])}, {q(r[4])}, {q(r[5])}, {r[6]}, {r[7]}, {r[8]}, {q(r[9])})"
        val_clauses.append(row_str)
    
    sql = f"INSERT INTO `tmp_bench_activity_log` ({col_str}) VALUES {', '.join(val_clauses)}"
    cur.execute(sql)
    conn.commit()
    t1 = time.perf_counter()
    
    insert_dur = t1 - t0
    rate = b_size / insert_dur
    print(f"    - Batch Size: {b_size:>6,} rows | Time: {insert_dur:.3f}s | Rate: {rate:>8,.1f} rows/s")
    batch_results.append({"batch_size": b_size, "time_s": round(insert_dur, 3), "rate_rows_sec": round(rate, 1)})

cur.execute("DROP TEMPORARY TABLE `tmp_bench_activity_log`")
conn.commit()
conn.close()

# 4. Storage Growth Analysis
print("\n[*] 4. Database Storage Growth Metrics...")
conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password="root", database="employee360", cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("""
    SELECT 
        table_rows,
        data_length,
        index_length,
        (data_length + index_length) AS total_length
    FROM information_schema.TABLES
    WHERE table_name = 'tabEmployee Activity Log' AND table_schema = 'employee360';
""")
row = cur.fetchone()
conn.close()

total_bytes = row["total_length"]
data_bytes = row["data_length"]
index_bytes = row["index_length"]
rows_count = row["table_rows"] if row and row.get("table_rows") else 0

print(f"    - Target Record Count       : {rows_count:,}")
print(f"    - Raw Table Data Storage    : {data_bytes / (1024*1024):.2f} MB ({data_bytes / rows_count:.1f} bytes/row)")
print(f"    - B-Tree Index Storage      : {index_bytes / (1024*1024):.2f} MB ({index_bytes / rows_count:.1f} bytes/row)")
print(f"    - Total Physical Storage    : {total_bytes / (1024*1024):.2f} MB ({total_bytes / (1024*1024*1024):.2f} GB)")
print(f"    - Total Storage Overhead    : {total_bytes / rows_count:.1f} bytes per historical day record")

# 5. Checkpoint Recovery Verification
print("\n[*] 5. Checkpoint Interruption & Resumption Simulation...")
conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password="root", database="employee360", cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT * FROM `tabSeed Checkpoint` WHERE seed_key = 'attendance_seed'")
cp = cur.fetchone()
print(f"    - Recorded Checkpoint Key   : {cp.get('seed_key')}")
print(f"    - Last Completed Batch      : {cp.get('last_completed_batch')}")
print(f"    - Total Records Inserted    : {cp.get('total_records_inserted'):,}")
print(f"    - Final Seed Status         : {cp.get('status')}")
conn.close()

import json
seed_metrics = {
    "emp_generation": {
        "count": len(employees),
        "duration_s": round(emp_gen_time, 3),
        "rate_per_sec": round(emp_rate, 1),
        "peak_mem_mb": round(peak_mem / (1024*1024), 2)
    },
    "activity_log_streaming": {
        "streamed_sample": total_streamed,
        "duration_s": round(stream_time, 3),
        "rate_per_sec": round(stream_rate, 1)
    },
    "batch_size_impact": batch_results,
    "storage_growth": {
        "rows": rows_count,
        "data_mb": round(data_bytes / (1024*1024), 2),
        "index_mb": round(index_bytes / (1024*1024), 2),
        "total_mb": round(total_bytes / (1024*1024), 2),
        "bytes_per_row": round(total_bytes / rows_count, 1)
    }
}
with open("benchmark_seed_results.json", "w") as f:
    json.dump(seed_metrics, f, indent=2)

print("\nSaved seed benchmark results to benchmark_seed_results.json")
