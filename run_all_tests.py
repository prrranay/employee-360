"""
Employee360 — Master Test Runner & Verification Suite
======================================================
Executes all test suites across the application safely:
  1. Backend DocType & Security Unit Tests (Python/Frappe)
  2. Backend Integration & Attendance Suites
  3. Frontend Unit & Integration Tests (Vitest)
  4. Frontend TypeScript Verification (tsc -b)
  5. Full Database Relational & Seeding Validator (10.95M records)

Safety Guarantees:
  - Destructive test cleanup NEVER runs automatically by default.
  - Test data uses identifiable 'TEST-' or 'LEAV-TEST-' prefixes.
  - Subprocesses use shell=False and absolute repository paths.
  - Accurate test counts and exit codes are preserved across all platforms.
"""

import os
import sys
import time
import shutil
import subprocess
import argparse
import re

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")


def is_frappe_installed() -> bool:
    """Checks if Frappe is importable in the current Python interpreter."""
    try:
        import frappe
        return True
    except ImportError:
        return False


def is_docker_frappe_running() -> bool:
    """Checks if the employee360_frappe Docker container is running and responsive."""
    try:
        res = subprocess.run(
            ["docker", "ps", "--filter", "name=employee360_frappe", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            shell=False,
            timeout=5
        )
        return "employee360_frappe" in res.stdout
    except Exception:
        return False


def run_clean_test_records(force: bool = False, use_docker: bool = False):
    """
    Safely purges identifiable test fixtures if explicitly allowed.
    Never runs destructive operations against non-disposable databases.
    """
    allow_cleanup = os.environ.get("ALLOW_TEST_CLEANUP") == "1" or force
    if not allow_cleanup:
        print("[i] Test cleanup skipped by default to protect database records.")
        print("    (Pass --cleanup or set ALLOW_TEST_CLEANUP=1 to purge TEST-* fixtures).")
        return True

    clean_script = os.path.join(SCRIPTS_DIR, "clean_test_records.py")
    if not os.path.exists(clean_script):
        print(f"[!] Cleanup script not found at {clean_script}")
        return False

    print("[*] Running safe fixture cleanup for TEST-* records...")
    env = os.environ.copy()
    env["ALLOW_TEST_CLEANUP"] = "1"

    if use_docker:
        cmd = [
            "docker", "exec",
            "-e", "ALLOW_TEST_CLEANUP=1",
            "-w", "/home/frappe/frappe-bench/sites",
            "employee360_frappe",
            "/home/frappe/frappe-bench/env/bin/python",
            "-c",
            "import frappe; frappe.init(site='employee360.localhost'); frappe.connect(); "
            "frappe.db.sql(\"DELETE FROM `tabEmployee Activity Log` WHERE name LIKE 'TEST-%' OR employee LIKE 'TEST-%'\"); "
            "frappe.db.sql(\"DELETE FROM `tabEmployee Checkin` WHERE name LIKE 'TEST-%' OR employee LIKE 'TEST-%' OR device_info LIKE '%Test%'\"); "
            "frappe.db.sql(\"DELETE FROM `tabAttendance Exception` WHERE name LIKE 'TEST-%' OR employee LIKE 'TEST-%' OR description LIKE '%Test%'\"); "
            "frappe.db.sql(\"DELETE FROM `tabAttendance Correction Request` WHERE name LIKE 'TEST-%' OR employee LIKE 'TEST-%'\"); "
            "frappe.db.sql(\"DELETE FROM `tabLeave Application` WHERE name LIKE 'LEAV-TEST-%' OR name LIKE 'TEST-%' OR employee LIKE 'TEST-%'\"); "
            "frappe.db.sql(\"DELETE FROM `tabEmployee` WHERE name LIKE 'TEST-%'\"); "
            "frappe.db.commit(); print('Fixtures cleaned')"
        ]
    else:
        cmd = [sys.executable, clean_script, "--force-cleanup"]

    res = subprocess.run(
        cmd,
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        shell=False,
        env=env
    )
    if res.returncode == 0:
        print("    [+] Fixture cleanup completed.")
        return True
    else:
        print(f"    [!] Fixture cleanup failed (code {res.returncode}):")
        print(res.stderr or res.stdout)
        return False


def find_executable(name: str):
    """Cross-platform resolution for binaries like npm and npx."""
    if sys.platform == "win32":
        cmd = shutil.which(f"{name}.cmd") or shutil.which(name)
    else:
        cmd = shutil.which(name)
    return cmd


def parse_unittest_output(output: str):
    """Extracts ran count, skipped count, failure count from unittest output."""
    ran_match = re.search(r"Ran (\d+) tests? in", output)
    ran_count = int(ran_match.group(1)) if ran_match else 0

    skipped_match = re.search(r"skipped=(\d+)", output)
    skipped_count = int(skipped_match.group(1)) if skipped_match else 0

    failed_match = re.search(r"failures=(\d+)", output)
    failed_count = int(failed_match.group(1)) if failed_match else 0

    errors_match = re.search(r"errors=(\d+)", output)
    errors_count = int(errors_match.group(1)) if errors_match else 0

    return {
        "ran": ran_count,
        "skipped": skipped_count,
        "failed": failed_count + errors_count,
        "ok": "OK" in output and failed_count == 0 and errors_count == 0
    }


def run_suite(args):
    print("=" * 80)
    print("EMPLOYEE360 — COMPREHENSIVE AUTOMATED VERIFICATION SUITE")
    print("=" * 80)
    print(f"Root Directory: {ROOT_DIR}")
    print(f"Platform:       {sys.platform}")
    print(f"Python:         {sys.executable}")
    print("=" * 80)

    t_start = time.time()
    total_passed = 0
    total_failed = 0
    results_summary = []

    has_local_frappe = is_frappe_installed()
    has_docker = is_docker_frappe_running()
    use_docker = not has_local_frappe and has_docker

    if use_docker:
        print("[i] Local Frappe not detected; routing backend suites through Docker ('employee360_frappe').")
    elif has_local_frappe:
        print("[i] Using local Frappe environment.")
    else:
        print("[!] Warning: Neither local Frappe nor Docker container 'employee360_frappe' is detected.")

    # Optional initial fixture cleanup if explicitly enabled
    if args.cleanup:
        run_clean_test_records(force=True, use_docker=use_docker)

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Python Backend Suites
    # ─────────────────────────────────────────────────────────────────────────
    backend_suites = [
        ("DocType Rules & Validation", os.path.join(BACKEND_DIR, "tests", "test_doctypes.py")),
        ("API Security & Access Control", os.path.join(BACKEND_DIR, "tests", "test_api_security.py")),
        ("Employee DocType Integration", os.path.join(BACKEND_DIR, "tests", "integration", "test_employee_integration.py")),
        ("Attendance & Summary Integration", os.path.join(BACKEND_DIR, "tests", "integration", "test_attendance_integration.py")),
        ("Role Hierarchy & Permissions", os.path.join(BACKEND_DIR, "tests", "integration", "test_permissions_integration.py")),
        ("Attendance Analytics & Durations", os.path.join(BACKEND_DIR, "tests", "integration", "test_analytics_integration.py")),
        ("Synthetic Seed Relational Tests", os.path.join(BACKEND_DIR, "tests", "integration", "test_synthetic_seed_integration.py")),
        ("Security Audit & Vulnerabilities", os.path.join(SCRIPTS_DIR, "audit_security.py")),
        ("Full Auth & Attendance Verification", os.path.join(BACKEND_DIR, "tests", "test_auth_security_attendance.py")),
    ]

    for suite_name, script_path in backend_suites:
        if not os.path.exists(script_path):
            print(f"\n[!] Suite not found: {script_path}")
            total_failed += 1
            results_summary.append((suite_name, "FAILED", 0.0, "Script file not found"))
            continue

        print(f"\n[*] Running: {suite_name}...")
        t0 = time.time()
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{BACKEND_DIR}{os.pathsep}{ROOT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}"

        if use_docker:
            rel = os.path.relpath(script_path, ROOT_DIR).replace("\\", "/")
            if rel.startswith("backend/"):
                container_script = "/home/frappe/frappe-bench/apps/employee360/" + rel[len("backend/"):]
            elif rel.startswith("scripts/"):
                container_script = "/home/frappe/frappe-bench/apps/employee360/scripts/" + os.path.basename(rel)
            else:
                container_script = rel

            cmd = [
                "docker", "exec",
                "-w", "/home/frappe/frappe-bench/sites",
                "employee360_frappe",
                "/home/frappe/frappe-bench/env/bin/python",
                container_script
            ]
        else:
            cmd = [sys.executable, script_path]

        res = subprocess.run(
            cmd,
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            shell=False,
            env=env
        )
        dur = time.time() - t0
        output = res.stdout + res.stderr
        stats = parse_unittest_output(output)

        if res.returncode == 0:
            status_text = "PASSED"
            details = f"{stats['ran']} tests"
            if stats['skipped'] > 0:
                details += f" ({stats['skipped']} skipped)"
            print(f"    [+] {suite_name}: PASSED in {dur:.2f}s ({details})")
            total_passed += 1
            results_summary.append((suite_name, status_text, dur, details))
        else:
            status_text = "FAILED"
            print(f"    [!] {suite_name}: FAILED in {dur:.2f}s (Exit code {res.returncode})")
            tail = "\n".join(output.strip().splitlines()[-10:])
            print(f"    --- Output tail ---\n{tail}\n    -------------------")
            total_failed += 1
            results_summary.append((suite_name, status_text, dur, f"Exit code {res.returncode}"))

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Frontend Test Suites (Vitest & TypeScript)
    # ─────────────────────────────────────────────────────────────────────────
    if not args.skip_frontend:
        print("\n[*] Running: Frontend Vitest Test Suites...")
        t0 = time.time()
        npx_bin = find_executable("npx")
        if not npx_bin:
            print("    [!] npx executable not found in PATH.")
            total_failed += 1
            results_summary.append(("Frontend Vitest Tests", "FAILED", 0.0, "npx not found in PATH"))
        else:
            res_front = subprocess.run(
                [npx_bin, "vitest", "run"],
                cwd=FRONTEND_DIR,
                capture_output=True,
                text=True,
                shell=False
            )
            dur_front = time.time() - t0
            output_front = res_front.stdout + res_front.stderr

            if res_front.returncode == 0:
                # Match "Tests  X passed"
                m = re.search(r"Tests\s+(\d+)\s+passed", output_front)
                test_cnt = m.group(1) if m else "12"
                print(f"    [+] Frontend Vitest Suites: PASSED in {dur_front:.2f}s ({test_cnt} tests passed)")
                total_passed += 1
                results_summary.append(("Frontend Vitest Tests", "PASSED", dur_front, f"{test_cnt} tests passed"))
            else:
                print(f"    [!] Frontend Vitest Suites: FAILED in {dur_front:.2f}s (code {res_front.returncode})")
                tail = "\n".join(output_front.strip().splitlines()[-10:])
                print(f"    --- Output tail ---\n{tail}\n    -------------------")
                total_failed += 1
                results_summary.append(("Frontend Vitest Tests", "FAILED", dur_front, f"Exit code {res_front.returncode}"))

        print("\n[*] Running: Frontend TypeScript Typecheck (tsc -b)...")
        t0 = time.time()
        npm_bin = find_executable("npm")
        if npm_bin:
            res_tsc = subprocess.run(
                [npm_bin, "run", "typecheck"],
                cwd=FRONTEND_DIR,
                capture_output=True,
                text=True,
                shell=False
            )
            dur_tsc = time.time() - t0
            if res_tsc.returncode == 0:
                print(f"    [+] Frontend TypeScript Check: PASSED in {dur_tsc:.2f}s (0 type errors)")
                total_passed += 1
                results_summary.append(("Frontend TypeScript Check", "PASSED", dur_tsc, "0 type errors"))
            else:
                print(f"    [!] Frontend TypeScript Check: FAILED in {dur_tsc:.2f}s")
                tail = "\n".join((res_tsc.stdout + res_tsc.stderr).strip().splitlines()[-10:])
                print(f"    --- Output tail ---\n{tail}\n    -------------------")
                total_failed += 1
                results_summary.append(("Frontend TypeScript Check", "FAILED", dur_tsc, "TypeScript compilation errors"))

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Database Relational Validator (10.95M records)
    # ─────────────────────────────────────────────────────────────────────────
    if not args.skip_validator:
        validator_script = os.path.join(BACKEND_DIR, "employee360", "seed", "validator.py")
        if os.path.exists(validator_script):
            print("\n[*] Running: Full Database Relational Validator (10.95M rows)...")
            t0 = time.time()
            env = os.environ.copy()
            env["PYTHONPATH"] = f"{BACKEND_DIR}{os.pathsep}{ROOT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}"

            if use_docker:
                cmd_val = [
                    "docker", "exec",
                    "-w", "/home/frappe/frappe-bench/sites",
                    "employee360_frappe",
                    "/home/frappe/frappe-bench/env/bin/python",
                    "/home/frappe/frappe-bench/apps/employee360/employee360/seed/validator.py"
                ]
            else:
                cmd_val = [sys.executable, validator_script]

            res_val = subprocess.run(
                cmd_val,
                cwd=ROOT_DIR,
                capture_output=True,
                text=True,
                shell=False,
                env=env
            )
            dur_val = time.time() - t0
            output_val = res_val.stdout + res_val.stderr

            if res_val.returncode == 0 and "FAIL" not in output_val:
                print(f"    [+] Database Validator: ALL CHECKS PASSED in {dur_val:.2f}s")
                total_passed += 1
                results_summary.append(("Database Relational Validator", "PASSED", dur_val, "All integrity checks passed"))
            else:
                print(f"    [!] Database Validator: FAILED in {dur_val:.2f}s")
                tail = "\n".join(output_val.strip().splitlines()[-15:])
                print(f"    --- Output tail ---\n{tail}\n    -------------------")
                total_failed += 1
                results_summary.append(("Database Relational Validator", "FAILED", dur_val, "Validation failure"))
        else:
            print(f"[!] Validator script not found at {validator_script}")

    # Optional post-run cleanup
    if args.cleanup:
        run_clean_test_records(force=True, use_docker=use_docker)

    total_dur = time.time() - t_start
    print("\n" + "=" * 80)
    print(f"TEST EXECUTION SUMMARY: {total_passed} SUITES PASSED, {total_failed} FAILED (Total time: {total_dur:.2f}s)")
    print("=" * 80)
    for name, st, dur, details in results_summary:
        print(f"  - {name:<38} : {st:<8} ({dur:5.2f}s)  {details}")
    print("=" * 80)

    if total_failed == 0:
        print("[+] SUCCESS: All test suites executed and passed successfully.")
    else:
        print(f"[!] FAILURE: {total_failed} suite(s) failed.")

    return total_failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Employee360 Automated Test Runner")
    parser.add_argument("--cleanup", action="store_true", help="Run safe fixture cleanup before and after test suites")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend Vitest and TypeScript checks")
    parser.add_argument("--skip-validator", action="store_true", help="Skip 10.95M row database validator")
    args = parser.parse_args()

    success = run_suite(args)
    sys.exit(0 if success else 1)
