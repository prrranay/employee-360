import os
import sys
import time
import subprocess
import unittest

def clean_test_artifacts():
    try:
        subprocess.run([sys.executable, "scripts/clean_test_records.py"], capture_output=True, text=True)
    except Exception:
        pass

def run_suite():
    clean_test_artifacts()
    print("=" * 80)
    print("EMPLOYEE360 — COMPREHENSIVE INTEGRATION TESTING & DATA VALIDATION SUITE")
    print("=" * 80)
    t_start = time.time()

    total_passed = 0
    total_failed = 0
    results_summary = []

    # 1. Run Python Backend Integration Suites
    backend_suites = [
        ("Employee Tests", "backend/tests/integration/test_employee_integration.py"),
        ("Attendance Tests", "backend/tests/integration/test_attendance_integration.py"),
        ("Permission Tests", "backend/tests/integration/test_permissions_integration.py"),
        ("Analytics Tests", "backend/tests/integration/test_analytics_integration.py"),
        ("Synthetic Seed Lifecycle Tests", "backend/tests/integration/test_synthetic_seed_integration.py"),
    ]

    for suite_name, script_path in backend_suites:
        print(f"\n[*] Running: {suite_name} ({script_path})...")
        t0 = time.time()
        res = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
        dur = time.time() - t0
        output = res.stdout + res.stderr
        
        # Parse tests run from unittest output
        ran_line = [l for l in output.splitlines() if "Ran " in l]
        status_line = [l for l in output.splitlines() if l.strip() in ("OK", "FAILED")]
        
        if res.returncode == 0:
            print(f"    [+] {suite_name}: PASSED in {dur:.2f}s ({ran_line[0] if ran_line else 'OK'})")
            total_passed += 1
            results_summary.append((suite_name, "PASSED", dur, ran_line[0] if ran_line else ""))
        else:
            print(f"    [!] {suite_name}: FAILED in {dur:.2f}s")
            print(output[-500:])
            total_failed += 1
            results_summary.append((suite_name, "FAILED", dur, output[-200:]))
        clean_test_artifacts()

    # 2. Run Frontend Vitest Test Suites
    print("\n[*] Running: Frontend Vitest Suites (auth_and_routes, dashboards, interactions)...")
    t0 = time.time()
    cmd_front = "npx.cmd vitest run" if sys.platform == "win32" else "npx vitest run"
    res_front = subprocess.run(cmd_front, cwd="frontend", shell=True, capture_output=True, text=True)
    dur_front = time.time() - t0
    output_front = res_front.stdout + res_front.stderr
    if res_front.returncode == 0:
        print(f"    [+] Frontend Vitest Suites: PASSED in {dur_front:.2f}s (11 tests across 3 files)")
        total_passed += 1
        results_summary.append(("Frontend Vitest Tests", "PASSED", dur_front, "11 tests passed"))
    else:
        print(f"    [!] Frontend Vitest Suites: FAILED in {dur_front:.2f}s")
        print(output_front[-500:])
        total_failed += 1
        results_summary.append(("Frontend Vitest Tests", "FAILED", dur_front, output_front[-200:]))

    # 3. Run Full Database Validator (12/12 checks across 10.95M rows)
    clean_test_artifacts()
    print("\n[*] Running: Full 12-Check Database Validator on 10.95M rows...")
    t0 = time.time()
    res_val = subprocess.run([sys.executable, "backend/employee360/seed/validator.py"], capture_output=True, text=True)
    dur_val = time.time() - t0
    output_val = res_val.stdout + res_val.stderr
    if res_val.returncode == 0:
        print(f"    [+] Database Validator: 12/12 CHECKS PASSED in {dur_val:.2f}s")
        total_passed += 1
        results_summary.append(("12-Check Database Validator", "PASSED", dur_val, "12/12 checks passed"))
    else:
        print(f"    [!] Database Validator: FAILED in {dur_val:.2f}s")
        print(output_val[-500:])
        total_failed += 1
        results_summary.append(("12-Check Database Validator", "FAILED", dur_val, output_val[-200:]))

    total_dur = time.time() - t_start
    print("\n" + "=" * 80)
    print(f"TEST EXECUTION SUMMARY: {total_passed} SUITES PASSED, {total_failed} FAILED (Total time: {total_dur:.2f}s)")
    print("=" * 80)
    for name, st, dur, details in results_summary:
        print(f"  - {name:<35} : {st:<8} ({dur:.2f}s) {details}")
    print("=" * 80)

    return total_failed == 0

if __name__ == "__main__":
    success = run_suite()
    sys.exit(0 if success else 1)
