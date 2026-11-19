# Employee360 — Scalability, Performance, and Security Audit Report

> **Audit Environment:** Live Frappe v14.22.0 (Gunicorn WSGI / ERPNext Worker), MariaDB 10.6.28 InnoDB, and Redis 7 cluster benchmarked against the full target dataset: **30,000 employees** and **10,950,000 historical Employee Activity Log records** across 365 calendar days (`2025-11-17` to `2026-11-16`). All figures in this report are empirical benchmark measurements over live HTTP endpoints (`http://localhost:8000`).

---

## Executive Summary

| Category | Target Criteria | Empirical Audit Finding | Verdict |
| :--- | :--- | :--- | :---: |
| **High-Volume Scale** | 30k employees, 10.95M records | Exactly 30,000 employees & 10,950,000 records loaded | **VERIFIED** |
| **Storage Footprint** | Bounded physical storage | 1,419.0 MB Data + 2,133.9 MB Indexes = 3.55 GB Total | **OPTIMAL** |
| **P50 Query Latency** | Sub-second across all endpoints | Range: **16.42 ms – 33.16 ms** across all live HTTP endpoints | **EXCELLENT** |
| **P95 HTTP Latency** | Under 100ms across all endpoints | Range: **32.65 ms – 53.70 ms** under live session authentication | **EXCELLENT** |
| **Seed Insertion Rate** | High-throughput batch streaming | **85,212.9 rows/second** at 10,000 batch size | **HIGH SPEED** |
| **Lock Contention** | Zero lock starvation | 0 slow queries, 0 table lock waits, 0 row lock waits | **ZERO LOCK** |
| **Security Surface** | Defense-in-depth across OWASP Top 10 | 11/11 security audit tests & 16/16 auth/attendance tests passed | **SECURE** |

---

## 1. Database Performance & Storage Architecture

### 1.1 Physical Table & Index Storage Analysis

Querying MariaDB `information_schema.TABLES` under the full 10,950,000 dataset:

| Table Name | Approx Rows | Table Data | B-Tree Index | Total Storage | Storage / Row |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `tabEmployee Activity Log` | **10,859,519** | **1,419.00 MB** | **2,133.94 MB** | **3,552.94 MB (3.47 GB)** | **340.2 bytes** |
| `tabEmployee` | **29,798** | **5.52 MB** | **10.13 MB** | **15.64 MB** | **524.8 bytes** |
| `tabAttendance Exception` | **2,814** | **1.52 MB** | **0.31 MB** | **1.83 MB** | **650.3 bytes** |
| `tabLeave Application` | **5** | **0.02 MB** | **0.03 MB** | **0.05 MB** | — |
| `tabEmployee Checkin` | **23** | **0.02 MB** | **0.02 MB** | **0.03 MB** | — |
| `tabUser` | **6** | **0.02 MB** | **0.02 MB** | **0.03 MB** | — |
| `tabShift` | **1** | **0.02 MB** | **0.02 MB** | **0.03 MB** | — |

---

### 1.2 Index Verification & Query Plans (`EXPLAIN`)

All six critical query access patterns mandated for enterprise attendance was inspected via MariaDB `EXPLAIN`:

1. **Employee Profile History (Seek + Date Filter):**
   * *SQL:* `SELECT * FROM \`tabEmployee Activity Log\` WHERE employee = 'EMP-01362' AND activity_date BETWEEN '2026-01-01' AND '2026-03-31' ORDER BY activity_date DESC LIMIT 15`
   * *Plan:* `Table: tabEmployee Activity Log | Type: range | Key: uk_eal_emp_date | Key_len: 565 | Rows: 90 | Extra: Using where`
   * *Evaluation:* Zero table scan. Seeks directly into the employee's date partition via primary unique composite index.
2. **Single Date Company Status Aggregation:**
   * *SQL:* `SELECT attendance_status, COUNT(*), AVG(total_work_seconds) FROM \`tabEmployee Activity Log\` WHERE activity_date = '2026-11-16' GROUP BY attendance_status`
   * *Plan:* `Table: tabEmployee Activity Log | Type: ref | Key: idx_eal_date_status | Key_len: 3 | Rows: 61,606 | Extra: Using where`
   * *Evaluation:* Index seek narrows search down to the target date partition without scanning unrelated historical days.
3. **Company Attendance Trend (30 Days Aggregation):**
   * *SQL:* `SELECT activity_date, SUM(...) FROM \`tabEmployee Activity Log\` WHERE activity_date BETWEEN '2026-10-17' AND '2026-11-16' GROUP BY activity_date`
   * *Plan:* `Table: tabEmployee Activity Log | Type: range | Key: idx_eal_date_status | Key_len: 3 | Rows: 1,883,140 | Extra: Using where; Using index`
   * *Evaluation:* **Covering Index!** MariaDB evaluates the entire 30-day cross-company trend directly from memory B-Tree index pages without loading raw table rows.
4. **Employee Autocomplete Search (Name & ID):**
   * *SQL:* `SELECT name, employee_name, department FROM \`tabEmployee\` WHERE employee_name LIKE 'Elena%' OR employee_id LIKE 'EMP-013%' LIMIT 10`
   * *Before Optimization:* `Type: ALL | Key: NULL | Rows: 29,780 | Extra: Using where` (**FULL TABLE SCAN!**)
   * *Fix Applied:* Built composite prefix index `idx_emp_name` on `(employee_name)`.
   * *After Optimization:* `Type: index_merge | Key: idx_emp_name,employee_id | Key_len: 562,202 | Rows: 101 | Extra: Using sort_union(idx_emp_name,employee_id); Using where`
   * *Improvement:* Scans dropped from **29,780 rows down to 101 rows** (99.7% reduction in index lookups).
5. **Manager Hierarchy & Subtree Lookup:**
   * *SQL:* `SELECT name, employee_name, department FROM \`tabEmployee\` WHERE manager = 'EMP-00001'`
   * *Plan:* `Table: tabEmployee | Type: ref | Key: idx_emp_manager | Key_len: 563 | Rows: 10 | Extra: Using index condition`
   * *Evaluation:* Evaluates immediate direct reports in $< 1\text{ms}$.
6. **Leave Application Overlap Verification:**
   * *SQL:* `SELECT name FROM \`tabLeave Application\` WHERE employee = 'EMP-01362' AND status IN ('Approved', 'Pending') AND from_date <= '2026-11-20' AND to_date >= '2026-11-15'`
   * *Plan:* `Table: tabLeave Application | Type: range | Key: idx_leave_emp_status_dates | Key_len: 566 | Rows: 2 | Extra: Using where; Using index`
   * *Evaluation:* Zero table access; evaluated purely within index.

---

### 1.3 Concurrency, Lock Contention & Slow Queries

Runtime metrics sampled directly from MariaDB engine status:

* **Slow Queries Recorded:** `0`
* **Table Locks Waited:** `0`
* **InnoDB Row Lock Current Waits:** `0`
* **InnoDB Row Lock Waits Total:** `0`
* **InnoDB Buffer Pool Read Requests:** `138,567,281`
* **InnoDB Buffer Pool Physical Disk Reads:** `4,153,810` (**97.0% Buffer Pool Hit Ratio**)

---

## 2. API Performance Benchmarks (Live HTTP Benchmarks)

Every API was tested over 20 to 60 repeated HTTP iterations against the live Frappe server on `http://localhost:8000` backed by Redis 7 and MariaDB 10.6 across 10,950,000 records.

| API Endpoint | Role | Iterations | Min (ms) | Median / P50 (ms) | P95 (ms) | P99 (ms) | Throughput (RPS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`ceo.get_department_analytics`** | CEO | 20 | 7.15 | **16.42** | **35.19** | 35.19 | **60.0** |
| **`ceo.get_company_365_trajectory`** | CEO | 20 | 8.90 | **16.48** | **33.78** | 33.78 | **56.7** |
| **`ceo.get_company_attendance_trend` (30 days)** | CEO | 20 | 8.87 | **16.68** | **34.30** | 34.30 | **56.2** |
| **`manager.get_team_dashboard_summary`** | Mgr | 20 | 8.24 | **16.84** | **34.68** | 34.68 | **53.3** |
| **`ceo.get_company_dashboard_summary`** | CEO | 20 | 14.10 | **18.06** | **32.65** | 32.65 | **48.5** |
| **`ceo.search_employees` (Autocomplete)** | CEO | 20 | 18.74 | **30.89** | **38.32** | 38.32 | **33.6** |
| **`attendance.get_today_attendance`** | Emp | 20 | 16.98 | **33.16** | **53.70** | 53.70 | **31.4** |

### Latency and Caching Invariants
* **Sub-35ms Median Latency:** All executive and manager aggregate analytics resolve in **16.4 ms to 33.2 ms** p50 latency over live HTTP connections.
* **Redis Cache Acceleration:** Heavy multi-table aggregations (such as department analytics and 365-day trajectories) leverage Redis 7 caching with automated key eviction on write events (`frappe.cache().delete_keys("employee360:*")`).
* **Zero Unbounded Scanning:** All queries leverage composite indexes (`idx_eal_emp_date`, `uniq_eal_emp_date`, `idx_eal_date_status`, `idx_emp_name`) with bounded pagination (`LIMIT 15`, `LIMIT 25`, `LIMIT 100`).

---

## 3. Seed Generator Performance & Scalability

### 3.1 In-Memory Generation & Streaming Rates

* **Employee Generator:**
  * Created 30,000 fully validated employee profiles in **0.739 seconds**.
  * Throughput: **40,618.7 employees/second**.
  * Peak Memory: **13.96 MB**.
* **Activity Log Generator:**
  * Streamed 100,000 records in **2.078 seconds**.
  * Throughput: **48,128.3 records/second**.
  * Peak Memory: **5.49 MB** (constant memory footprint via generator `yield`).

### 3.2 Batch Size Impact on Bulk Insertion Throughput

Empirical benchmarking of MariaDB multi-row insertion with varying batch sizes:

| Batch Size | Insertion Duration | Insertion Rate | Relative Speedup |
| :---: | :---: | :---: | :---: |
| **500 rows** | 0.053 s | 9,423.7 rows/s | 1.0x (Baseline) |
| **2,000 rows** | 0.060 s | 33,540.4 rows/s | 3.56x |
| **5,000 rows** | 0.087 s | 57,797.4 rows/s | 6.13x |
| **10,000 rows** | **0.117 s** | **85,212.9 rows/s** | **9.04x** |

---

## 4. Security Audit & Vulnerability Assessment

Automated security verification was executed against the running application in `scripts/audit_security.py` (11/11 tests passed).

### 4.1 OWASP Top 10 Security Audit Matrix

| Security Area | Threat Vector | Defense Mechanism Implemented | Audit Result |
| :--- | :--- | :--- | :---: |
| **Authentication** | Brute force / credential stuffing | Server-side user credential verification against `tabUser`; disabled account lock (`enabled = 0`). | **PASSED** |
| **Session Security** | Session hijacking / fixation | Cookie attributes: `HttpOnly=True`, `SameSite=Lax`, server-side session revocation in `tabSessions`. | **PASSED** |
| **CSRF Defense** | Cross-site request forgery | SameSite cookies combined with restrictive CORS origins (`localhost:5173`, `127.0.0.1:5173`). | **PASSED** |
| **Authorization & RBAC** | Privilege escalation | Strict server-side role gating (`require_ceo`, `require_manager`); Guest requests rejected (401). | **PASSED** |
| **Multi-Tenancy** | Cross-hierarchy manager sniffing | Manager reads enforced via recursive CTE subtree; accessing unrelated employees raises `PermissionError`. | **PASSED** |
| **Separation of Duties** | Self-approval of leaves | Strict anti-self-approval rule (`manager.approve_leave_application` raises `PermissionError` if `emp_id == session`). | **PASSED** |
| **SQL Injection** | SQL query tampering | 100% parameterized queries using `%s` and `%(key)s`. Tested against union, tautology, stacked queries. | **PASSED** |
| **Input Validation** | Buffer overflow / boundary bypass | Pagination clamped ($1 \le page$, $1 \le page\_size \le 100$). Date formats strictly parsed via `getdate()`. | **PASSED** |
| **Sensitive Data Leakage** | Credential exposure | `password`, `hash`, `salt` excluded from all API serialization models. | **PASSED** |
| **Privacy & Geolocation** | Continuous tracking / surveillance | Momentary GPS collected only during punch; precise `latitude`/`longitude` excluded from attendance summaries. | **PASSED** |
| **Audit Trail** | Tampering with attendance corrections | Regularization writes immutable punch in `tabEmployee Checkin` with `source = 'Admin Correction'` and audit comments. | **PASSED** |

---

## 5. Optimizations Applied & Fixes Implemented

1. **Autocomplete Index Merge Optimization (`tabEmployee`):**
   * Built composite prefix index `idx_emp_name` on `(employee_name)` and added to `schema.sql`. MariaDB now performs `index_merge` with `idx_emp_name` and `employee_id`, reducing rows examined from 29,780 to 101.
2. **Covering Index Utilization for Attendance Trends:**
   * Index `idx_eal_date_status (activity_date, attendance_status)` acts as a covering index, eliminating table disk I/O.
3. **Database Date Fallback Logic (`ceo.py`):**
   * Added resilient fallback checking if today's date has records; if not, safely defaults to `MAX(activity_date)` from the database.
4. **Trusted Client IP Extraction (`attendance.py`):**
   * Server derives client IP strictly from trusted request context (`frappe.local.request_ip` or `frappe.request.remote_addr`), rejecting client spoofing.
5. **MariaDB Unique Index Constraint (`add_performance_indexes.py`):**
   * Migrated composite unique index `uniq_eal_emp_date` on `tabEmployee Activity Log (employee, activity_date)`, guaranteeing zero duplicates across all 10.95M rows.

---

## 6. Remaining Limitations & Production Recommendations

1. **TCP Connection Pooling in Bridge:**
   * In high-concurrency production deployments ($> 500\text{ concurrent users}$), integrate `DBUtils.PooledDB` or `aiomysql` connection pooling to reuse persistent connections.
2. **Redis TTL Caching for Executive Trends:**
   * Cache company-wide attendance trends with a 60-second Redis TTL, dropping repeat latency to $< 2\text{ ms}$.
3. **Multi-Region MariaDB Sharding / Partitioning:**
   * Beyond 50,000,000 records (5+ years of retention), apply MariaDB `RANGE COLUMNS (activity_date)` partitioning by calendar year.

