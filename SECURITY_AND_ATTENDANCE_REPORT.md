# Employee360 Security & Attendance Hardening Report

## Executive Summary

This report documents the security audit, vulnerability remediation, and attendance transaction hardening performed on the **Employee360** application following its migration to the genuine Frappe Framework.

All vulnerabilities related to authentication bypasses, insecure password hashing, CSRF weaknesses, client-controlled authorization parameters, punch concurrency race conditions, and regularization double-approvals have been eliminated. The system was verified using a comprehensive automated test suite consisting of 16 live integration tests and 11 unit tests running inside the Frappe container against MariaDB and Redis, as well as the frontend test suite and production build.

---

## 1. Vulnerabilities Identified

| Vulnerability ID | Description | Severity | Impact |
| :--- | :--- | :--- | :--- |
| **VULN-01: Hardcoded Demo Password Bypass** | The application code or legacy authentication accepted universal hardcoded passwords (`Admin123!`, `admin`) regardless of user credentials. | **Critical** | Complete authentication bypass across all roles. |
| **VULN-02: Direct SQL Password Hashing in Seed** | `backend/employee360/seed/runner.py` used `passlib.hash.pbkdf2_sha256` and raw SQL inserts into `tabUser.password`. Modern Frappe v14 stores passwords in the `__Auth` table via PBKDF2-SHA512. | **High** | Users created via seed could not authenticate natively or broke Frappe password validation standards. |
| **VULN-03: Permissive CSRF Token Validation** | Previous custom middleware only validated CSRF tokens if one was provided in the header, letting requests without any CSRF token bypass checks completely. | **High** | Cross-Site Request Forgery on all state-changing endpoints (check-in, check-out, leave, approvals). |
| **VULN-04: Client-Controlled Source Authorization Bypass** | `EmployeeCheckin.enforce_authorization()` trusted `self.source in ["Regularization", "Admin Correction", "Seed"]` sent by the client, allowing employees to forge check-in/out records for other users. | **Critical** | Privilege escalation; falsification of employee work hours and attendance history. |
| **VULN-05: Attendance Check-in/Out Race Conditions** | Check-in and check-out APIs performed non-locking reads (`SELECT`) before inserting punches. Under MariaDB's default `REPEATABLE READ`, concurrent punches both saw 0 open sessions. | **High** | Simultaneous duplicate punches, corrupted session intervals, and inaccurate total work duration. |
| **VULN-06: Timestamp Sequence & Anomaly Blindness** | Client could record future timestamps, consecutive duplicate IN punches, or check-out without any preceding check-in. | **Medium** | Corrupted attendance calculations and negative/erroneous working durations. |
| **VULN-07: Double-Approval & Anti-Self-Approval Flaws** | Managers could approve their own regularization requests. Concurrent approval requests could execute simultaneously, creating duplicate correction punches. | **High** | Conflict of interest and double-counting of hours. |
| **VULN-08: Regularization Overwrite in Background Recalculation** | `recalculate_daily_summary` recomputed attendance strictly from raw punches, overwriting manually regularized statuses (`is_regularized`) on recalculation. | **Medium** | Loss of historical regularized attendance records. |

---

## 2. Remediation Details & Files Modified

### 2.1 Authentication & User Management
**Files Modified:**
- `backend/employee360/seed/runner.py`
- `backend/employee360/api/auth_utils.py`

**Changes Made:**
1. **Genuine Frappe User DocType & Password Storage:**
   - Removed all raw SQL inserts into `tabUser` and `tabHas Role`.
   - Used Frappe's native `frappe.new_doc("User")` / `frappe.get_doc("User")` and `user.add_roles()`.
   - Set user passwords using `frappe.utils.password.update_password(email, demo_password)`. This writes directly to Frappe's protected `__Auth` table using Frappe's native PBKDF2-SHA512 hashing algorithm.
2. **Configurable Demo Credentials:**
   - Password is dynamically loaded from environment variables `DEMO_USER_PASSWORD` or `ADMIN_PASSWORD`, defaulting to a secure dev password (`Admin123!`) if omitted.
   - No hardcoded universal password checks exist in application code. Invalid passwords return HTTP 401 Unauthorized via Frappe's `frappe.auth.LoginManager`.
3. **Demo User & Employee Linking:**
   - `seed_demo_users()` creates default `Shift` ("General Shift") and links all 6 demo accounts (`EMP-00001` CEO, `EMP-00012` & `EMP-00013` Managers, `EMP-01362`, `EMP-01363`, `EMP-01364` Employees) with valid reporting hierarchies (`reports_to`) and `user_id` relations.

### 2.2 Native CSRF Protection
**Files Modified:**
- `backend/employee360/api/auth_utils.py`

**Changes Made:**
1. **CSRF Generation & Cookie Synchronization:**
   - In `get_session_user_and_roles_api()`, Frappe's active session CSRF token is obtained via `frappe.sessions.get_csrf_token()`.
   - The token is set in the `csrf_token` cookie via `frappe.local.cookie_manager.set_cookie("csrf_token", csrf_token)`.
   - The token is also returned in the response payload for frontend HTTP client consumption.
2. **Strict Frappe Native Enforcement:**
   - Frappe automatically validates `X-Frappe-CSRF-Token` on all non-GET requests (`POST`, `PUT`, `DELETE`).
   - Missing CSRF token is rejected with HTTP 400 Bad Request (`CSRFTokenError`).
   - Invalid CSRF token is rejected with HTTP 400 Bad Request (`CSRFTokenError`).

### 2.3 Role-Based Server-Side Authorization
**Files Modified:**
- `backend/employee360/api/auth_utils.py`
- `backend/employee360/api/ceo.py`
- `backend/employee360/api/manager.py`
- `backend/employee360/api/employee.py`
- `backend/employee360/doctype/employee_checkin/employee_checkin.py`

**Changes Made:**
1. **Hierarchical Isolation:**
   - **CEO / System Manager:** Unrestricted access across company analytics, employee search, attendance logs, and leave summaries.
   - **Manager:** Scoped strictly to direct and indirect reporting trees via recursive SQL query on `tabEmployee.reports_to`. Cross-manager access is strictly rejected with `frappe.PermissionError`.
   - **Employee:** Scoped strictly to their own linked employee record (`user_id = frappe.session.user`). Attempts to query peer data are rejected with `frappe.PermissionError`.
2. **Elimination of Client `source` Bypass:**
   - In `EmployeeCheckin.enforce_authorization()`, bypass is allowed **only** for internal server flags:
     - `getattr(frappe.flags, "in_seed", False)`
     - `getattr(frappe.flags, "in_regularization_approval", False)`
   - If a client supplies `source="Admin Correction"` or `"Regularization"`, the system strictly validates that `source_record_id` points to an existing `Attendance Exception` with `status == "Resolved"` for that employee. Otherwise, it throws `frappe.PermissionError`.

### 2.4 Attendance Concurrency & Transaction Integrity
**Files Modified:**
- `backend/employee360/doctype/employee_checkin/employee_checkin.py`
- `backend/employee360/api/attendance.py`

**Changes Made:**
1. **Row-Level Locking (`SELECT ... FOR UPDATE`):**
   - In `check_in()` and `check_out()`, an explicit row lock is acquired on the employee record:
     ```sql
     SELECT name FROM `tabEmployee` WHERE name = %s FOR UPDATE;
     ```
   - Punch history for the day is queried with `FOR UPDATE`:
     ```sql
     SELECT name, time, log_type FROM `tabEmployee Checkin`
     WHERE employee = %(employee)s AND time >= %(day_start)s AND time <= %(time)s
     ORDER BY time DESC LIMIT 1 FOR UPDATE;
     ```
   - This serializes concurrent check-in and check-out requests. The second simultaneous request detects the open session / recent punch and is rejected cleanly with `frappe.ValidationError` (HTTP 417 / 500).
2. **Server-Generated Timestamps:**
   - Punches logged via web API use `now_datetime()`, ignoring client-submitted clocks to prevent clock-skew attacks.
3. **Timestamp & Sequence Validation:**
   - Reject future timestamps (`time > now_datetime() + 10s`).
   - Reject identical timestamp punches (`frappe.DuplicateEntryError`).
   - Reject consecutive IN punches without checkout.
   - Reject OUT punches without preceding open IN session.
   - Reject OUT punch if `out_time <= in_time`.
4. **Multi-Session Support:**
   - Multiple valid sessions per day (IN -> OUT -> IN -> OUT) are fully supported and summed in daily work seconds.

### 2.5 Attendance Regularization & Double-Approval Prevention
**Files Modified:**
- `backend/employee360/api/attendance.py`
- `backend/employee360/api/manager.py`
- `backend/employee360/doctype/employee_activity_log/employee_activity_log.py`

**Changes Made:**
1. **Anti-Self-Approval:**
   - `assert_can_manage_employee(target_emp)` verifies that `target_emp != current_emp`. A manager attempting to approve their own regularization or leave is rejected with `frappe.PermissionError("Self-approval is strictly forbidden")`.
2. **Pessimistic Double-Approval Lock:**
   - `approve_attendance_exception()`, `reject_attendance_exception()`, `approve_leave_application()`, and `reject_leave_application()` lock the target record using `SELECT ... FOR UPDATE`.
   - If the record status is already `Resolved`, `Ignored`, `Approved`, or `Rejected`, subsequent requests are rejected immediately with `frappe.ValidationError`.
3. **Auditable Punch Creation:**
   - When approving regularization, punches are created with `source="Admin Correction"`, `source_record_id=exception_id`, and manager audit comments under the verified `frappe.flags.in_regularization_approval = True` flag.
4. **Preservation of Regularized Status:**
   - `recalculate_daily_summary()` checks `existing_row.get("is_regularized")`. If regularized, the status and regularization exception linkage are preserved rather than reset by automated re-scans.

---

## 3. Verification & Test Execution Results

### 3.1 Security & Attendance Integration Test Suite
Test file: `backend/tests/test_auth_security_attendance.py`
Command executed in container:
```bash
docker compose exec -w /home/frappe/frappe-bench/apps/employee360 frappe /home/frappe/frappe-bench/env/bin/python -m unittest tests.test_auth_security_attendance
```

| Test Case | Scenario Description | Result |
| :--- | :--- | :--- |
| `test_01_valid_login` | Valid authentication with demo credentials; returns HTTP 200 and sets `sid` cookie. | **PASS** |
| `test_02_invalid_login` | Invalid password rejected with HTTP 401 Unauthorized via native Frappe LoginManager. | **PASS** |
| `test_03_hardcoded_password_rejection` | Legacy hardcoded bypass (`admin` / `Admin123!`) on non-existent account is rejected (HTTP 401). | **PASS** |
| `test_04_session_expiration_and_logout` | Session logout clears `sid`; subsequent authenticated calls are rejected. | **PASS** |
| `test_05_csrf_missing_token_rejection` | Authenticated POST request without `X-Frappe-CSRF-Token` header rejected with HTTP 400 (`CSRFTokenError`). | **PASS** |
| `test_06_csrf_invalid_token_rejection` | Authenticated POST request with forged `X-Frappe-CSRF-Token` rejected with HTTP 400 (`CSRFTokenError`). | **PASS** |
| `test_07_unauthorized_employee_access` | Regular employee calling CEO endpoint (`get_company_dashboard_summary`) rejected with `PermissionError`. | **PASS** |
| `test_08_unauthorized_manager_access` | Manager 1 attempting to access Manager 2's direct report rejected with `PermissionError`. | **PASS** |
| `test_09_ceo_global_access` | CEO has unrestricted access to company summary, search, and all employee records. | **PASS** |
| `test_10_employee_access_to_another_employee_rejected` | Individual employee accessing peer profile or activity rejected with `PermissionError`. | **PASS** |
| `test_11_duplicate_concurrent_checkins` | 2 simultaneous check-in HTTP requests serialized with row-level locks; exactly 1 succeeds, 1 rejected. | **PASS** |
| `test_12_duplicate_concurrent_checkouts` | 2 simultaneous check-out HTTP requests serialized with row-level locks; exactly 1 succeeds, 1 rejected. | **PASS** |
| `test_13_invalid_punch_order` | OUT without preceding IN and future timestamps rejected with `ValidationError`. | **PASS** |
| `test_14_multiple_daily_sessions` | Multi-session flow (IN -> OUT -> IN -> OUT) correctly recorded and daily work seconds accumulated. | **PASS** |
| `test_15_unauthorized_regularization_and_anti_self_approval` | Manager self-approval rejected; cross-manager approval rejected; client-side forged `source` rejected. | **PASS** |
| `test_16_double_approval_prevention` | Regularization exception approved once; concurrent/subsequent second approval rejected with `ValidationError`. | **PASS** |

**Summary: 16 passed, 0 failures, 0 errors (Ran in 8.045s).**

---

### 3.2 Full Backend Discover Test Suite
Command executed in container:
```bash
docker compose exec -w /home/frappe/frappe-bench/apps/employee360 frappe /home/frappe/frappe-bench/env/bin/python -m unittest discover tests
```
- `tests.test_api_security` (5 tests): **PASS**
- `tests.test_doctypes` (6 tests): **PASS**
- `tests.test_auth_security_attendance` (16 tests): **PASS**

**Summary: 27 passed, 0 failures, 0 errors (Ran in 7.772s).**

---

### 3.3 Frontend Test Suite & Production Build
1. **Vitest Test Suite:**
   ```bash
   npm --prefix frontend test
   ```
   - `src/tests/auth_and_routes.test.tsx` (3 tests): **PASS**
   - `src/tests/interactions.test.tsx` (6 tests): **PASS**
   - `src/tests/dashboards.test.tsx` (3 tests): **PASS**
   **Summary: 3 test files passed, 12 tests passed.**

2. **Frontend Production Build:**
   ```bash
   npm --prefix frontend run build
   ```
   - TypeScript compilation (`tsc -b`): **SUCCESS**
   - Vite bundling (`vite build`): **SUCCESS** (dist generated in 937ms).

---

## 4. Remaining Risks & Production Hardening Guidance

1. **Production Secret Management:**
   - In production, set `ADMIN_PASSWORD` and `DEMO_USER_PASSWORD` via secure vault or secret management (e.g. AWS Secrets Manager, HashiCorp Vault) rather than environment files committed to source control.
2. **Reverse Proxy SSL/TLS Termination:**
   - Deploy Frappe behind an Nginx or Traefik reverse proxy with HTTPS/TLS termination and enable HSTS to ensure cookies (`sid`, `system_user`, `csrf_token`) have the `Secure` attribute.
3. **Rate Limiting:**
   - Configure Nginx rate limiting on `/api/method/login` (e.g. 5 requests per minute per IP) to prevent brute-force attacks against user credentials.
4. **MariaDB Isolation Level:**
   - Ensure MariaDB maintains standard `REPEATABLE READ` or `READ COMMITTED` with InnoDB engines on all `tabEmployee*` tables to support `SELECT ... FOR UPDATE` locking behavior.

