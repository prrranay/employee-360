import sys
import os
import time
import statistics
import tracemalloc
import json
import urllib.request
import urllib.parse
import http.cookiejar

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

CEO_USER = "ceo@employee360.local"
MGR_USER = "manager1@employee360.local"
EMP_USER = "emp1@employee360.local"
DEFAULT_PWD = os.environ.get("ADMIN_PASSWORD", "Admin123!")
EMP_ID = "EMP-01362"


def run_http_benchmarks(base_url="http://localhost:8000", iterations=20):
    print("=" * 100)
    print(f"HTTP ENDPOINT BENCHMARK (Full Request Path through Frappe & Gunicorn)")
    print(f"Target URL: {base_url} | Iterations: {iterations}")
    print("=" * 100)

    # Establish authenticated session
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    login_data = urllib.parse.urlencode({"usr": CEO_USER, "pwd": DEFAULT_PWD}).encode()
    login_req = urllib.request.Request(f"{base_url}/api/method/login", data=login_data)
    try:
        resp = opener.open(login_req, timeout=10)
        if resp.status != 200:
            print(f"Failed to authenticate: HTTP {resp.status}")
            return []
    except Exception as e:
        print(f"Could not connect to {base_url}: {e}")
        return []

    endpoints = [
        ("CEO: Dashboard Summary (HTTP)", f"{base_url}/api/method/employee360.api.ceo.get_company_dashboard_summary?target_date=2026-11-16"),
        ("CEO: Employee Autocomplete (HTTP)", f"{base_url}/api/method/employee360.api.ceo.search_employees?query=Elena&limit=10"),
        ("CEO: Department Analytics (HTTP)", f"{base_url}/api/method/employee360.api.ceo.get_department_analytics?target_date=2026-11-16"),
        ("CEO: 30-Day Trend (HTTP)", f"{base_url}/api/method/employee360.api.ceo.get_company_attendance_trend?days=30"),
        ("CEO: 365-Day Trajectory (HTTP)", f"{base_url}/api/method/employee360.api.ceo.get_company_attendance_trend?days=365"),
        ("Manager: Team Summary (HTTP)", f"{base_url}/api/method/employee360.api.manager.get_team_dashboard_summary?target_date=2026-11-16"),
        ("Employee: Today Attendance (HTTP)", f"{base_url}/api/method/employee360.api.attendance.get_today_attendance"),
    ]

    results = []
    for name, url in endpoints:
        # Warmup
        try:
            opener.open(url, timeout=30)
        except Exception:
            pass

        latencies = []
        t_start = time.time()
        for _ in range(iterations):
            t0 = time.perf_counter()
            try:
                r = opener.open(url, timeout=30)
                _ = r.read()
                t1 = time.perf_counter()
                latencies.append((t1 - t0) * 1000.0)
            except Exception as e:
                print(f"Error on {name}: {e}")

        total_time = time.time() - t_start
        if not latencies:
            continue

        latencies.sort()
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)
        rps = len(latencies) / total_time if total_time > 0 else 0

        print(f"{name:<45} | p50: {p50:>7.2f}ms | p95: {p95:>7.2f}ms | p99: {p99:>7.2f}ms | RPS: {rps:>5.1f}")
        results.append({
            "name": name,
            "mode": "http_endpoint",
            "iterations": len(latencies),
            "min_ms": round(min(latencies), 2),
            "avg_ms": round(avg, 2),
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
            "max_ms": round(max(latencies), 2),
            "rps": round(rps, 1)
        })

    return results


def run_rpc_benchmarks(iterations=30):
    try:
        import frappe
    except ImportError:
        print("Genuine Frappe is not installed in this environment. Skipping internal Python RPC benchmarks.")
        return []

    if not getattr(frappe, "db", None) or not frappe.db:
        try:
            frappe.init(site="employee360.localhost")
            frappe.connect()
        except Exception as e:
            print(f"Warning: Frappe could not connect to database: {e}")
            return []

    from employee360.api import ceo, manager, employee, attendance

    print("=" * 100)
    print(f"INTERNAL PYTHON RPC BENCHMARK (Direct Method Execution)")
    print("=" * 100)

    benchmarks = [
        ("CEO: get_company_dashboard_summary", ceo.get_company_dashboard_summary, (), {"target_date": "2026-11-16"}, iterations, CEO_USER),
        ("CEO: search_employees (Autocomplete)", ceo.search_employees, (), {"query": "Elena", "limit": 10}, iterations, CEO_USER),
        ("CEO: get_department_analytics", ceo.get_department_analytics, (), {"target_date": "2026-11-16"}, iterations, CEO_USER),
        ("CEO: get_company_attendance_trend (30D)", ceo.get_company_attendance_trend, (), {"days": 30}, iterations, CEO_USER),
        ("CEO: get_company_attendance_trend (365D)", ceo.get_company_attendance_trend, (), {"days": 365}, iterations, CEO_USER),
        ("Manager: get_team_dashboard_summary", manager.get_team_dashboard_summary, (), {"target_date": "2026-11-16"}, iterations, MGR_USER),
        ("Employee: get_today_attendance", attendance.get_today_attendance, (), {}, iterations, EMP_USER),
    ]

    results = []
    for name, func, args, kwargs, iters, user in benchmarks:
        frappe.set_user(user)
        # Warmup
        for _ in range(2):
            func(*args, **kwargs)

        latencies = []
        tracemalloc.start()
        mem_before, _ = tracemalloc.get_traced_memory()
        t_start = time.time()
        for _ in range(iters):
            t0 = time.perf_counter()
            func(*args, **kwargs)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)
        total_time = time.time() - t_start
        _, mem_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        latencies.sort()
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)
        rps = iters / total_time if total_time > 0 else 0
        mem_mb = (mem_peak - mem_before) / (1024 * 1024)

        print(f"{name:<45} | p50: {p50:>7.2f}ms | p95: {p95:>7.2f}ms | p99: {p99:>7.2f}ms | RPS: {rps:>5.1f}")
        results.append({
            "name": name,
            "mode": "python_rpc",
            "iterations": iters,
            "min_ms": round(min(latencies), 2),
            "avg_ms": round(avg, 2),
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
            "max_ms": round(max(latencies), 2),
            "rps": round(rps, 1),
            "peak_mem_mb": round(mem_mb, 2)
        })

    return results


if __name__ == "__main__":
    http_results = run_http_benchmarks()
    rpc_results = run_rpc_benchmarks()
    all_results = http_results + rpc_results

    with open("benchmark_api_results.json", "w") as f:
        json.dump(all_results, f, indent=2)

    print("\nSaved comprehensive benchmark results to benchmark_api_results.json")
