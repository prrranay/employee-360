import sys
import os
import time
import statistics
import tracemalloc

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
APP_DIR = os.path.join(BACKEND_DIR, "apps", "employee360")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, APP_DIR)

import frappe_bridge
frappe_bridge.install_frappe_compat()
import frappe
from frappe_bridge import _current_user_var

from employee360.api import ceo, manager, employee, attendance

# Users
CEO_USER = "ceo@employee360.local"
MGR_USER = "manager1@employee360.local"
EMP_USER = "emp1@employee360.local"
EMP_ID = "EMP-01362"

def benchmark_function(name, func, args=(), kwargs=None, iterations=50, user=None):
    if kwargs is None:
        kwargs = {}
    
    if user:
        _current_user_var.set(user)
        
    latencies = []
    tracemalloc.start()
    mem_before, _ = tracemalloc.get_traced_memory()
    
    # Warmup 2 iterations
    for _ in range(2):
        func(*args, **kwargs)
        
    t_start_all = time.time()
    for _ in range(iterations):
        t0 = time.perf_counter()
        func(*args, **kwargs)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
    total_time = time.time() - t_start_all
    
    mem_current, mem_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    avg = statistics.mean(latencies)
    min_lat = min(latencies)
    max_lat = max(latencies)
    rps = iterations / total_time
    mem_delta_mb = (mem_peak - mem_before) / (1024 * 1024)
    
    print(f"{name:<42} | p50: {p50:>6.2f}ms | p95: {p95:>6.2f}ms | p99: {p99:>6.2f}ms | RPS: {rps:>6.1f} | PeakMem: {mem_delta_mb:>5.2f}MB")
    return {
        "name": name,
        "iterations": iterations,
        "min_ms": round(min_lat, 2),
        "avg_ms": round(avg, 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "max_ms": round(max_lat, 2),
        "rps": round(rps, 1),
        "peak_mem_mb": round(mem_delta_mb, 2)
    }

print("=" * 100)
print(f"BENCHMARKING EMPLOYEE360 APIS AGAINST 30,000 EMPLOYEES & 10,950,000 ACTIVITY LOGS")
print("=" * 100)

benchmarks = [
    # 1. CEO Dashboard Summary
    ("CEO: get_company_dashboard_summary", ceo.get_company_dashboard_summary, (), {"target_date": "2026-11-16"}, 40, CEO_USER),
    
    # 2. Employee Autocomplete (Partial Search)
    ("CEO: search_employees (Name / ID autocomplete)", ceo.search_employees, (), {"query": "Elena", "limit": 10}, 60, CEO_USER),
    ("CEO: search_employees (Prefix ID)", ceo.search_employees, (), {"query": "EMP-013", "limit": 10}, 60, CEO_USER),
    
    # 3. Employee Detail (Single Profile Drill-down)
    ("CEO: get_employee_overview (Detail)", ceo.get_employee_overview, (), {"employee_id": EMP_ID}, 40, CEO_USER),
    
    # 4. Employee Attendance History (Paginated 15 rows)
    ("Employee: get_employee_activity (Page 1)", employee.get_employee_activity, (EMP_ID,), {"page": 1, "page_size": 15}, 50, EMP_USER),
    ("Employee: get_employee_activity (Filtered Range)", employee.get_employee_activity, (EMP_ID,), {"from_date": "2026-01-01", "to_date": "2026-03-31", "page": 1, "page_size": 15}, 50, EMP_USER),
    
    # 5. Manager Team Summary
    ("Manager: get_team_dashboard_summary", manager.get_team_dashboard_summary, (), {"target_date": "2026-11-16"}, 40, MGR_USER),
    ("Manager: get_manager_team", manager.get_manager_team, (), {}, 40, MGR_USER),
    
    # 6. Department Analytics
    ("CEO: get_department_analytics", ceo.get_department_analytics, (), {"target_date": "2026-11-16"}, 40, CEO_USER),
    
    # 7. Attendance Trend
    ("CEO: get_company_attendance_trend (30 days)", ceo.get_company_attendance_trend, (), {"days": 30}, 30, CEO_USER),
    ("Manager: get_team_attendance_trend (30 days)", manager.get_team_attendance_trend, (), {"days": 30}, 30, MGR_USER),
    ("Employee: get_employee_attendance_trend (30 days)", employee.get_employee_attendance_trend, (EMP_ID,), {"days": 30}, 50, EMP_USER),
    
    # 8. Leave Overview
    ("CEO: get_company_leave_overview", ceo.get_company_leave_overview, (), {}, 40, CEO_USER),
    ("Manager: get_team_leave_overview", manager.get_team_leave_overview, (), {}, 40, MGR_USER),
    ("Employee: get_employee_leave_history", employee.get_employee_leave_history, (EMP_ID,), {}, 50, EMP_USER),
    
    # 9. Attendance Punch Widget
    ("Employee: get_today_attendance", attendance.get_today_attendance, (), {}, 50, EMP_USER),
]

results = []
for name, func, args, kwargs, iters, user in benchmarks:
    res = benchmark_function(name, func, args, kwargs, iters, user)
    results.append(res)

import json
with open("benchmark_api_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nSaved benchmark results to benchmark_api_results.json")

