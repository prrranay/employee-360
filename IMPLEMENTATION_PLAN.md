# Employee360 — Production Architecture & Implementation Plan

## 1. Current Repository Architecture & Environment Inspection

### 1.1 Physical Filesystem & Workspace Inventory
* **Workspace Directory:** `c:\Users\ADMIN\Desktop\pern\assesment\empoyee`
* **File Inventory:** The directory was inspected recursively via PowerShell (`Get-ChildItem -Force -Recurse`) and CMD (`dir /a`). 
* **Current State:** **Greenfield / Empty.** Zero source files, zero configuration files, and zero Git worktrees are currently initialized in this directory.

### 1.2 Host Environment & Tooling Audit
* **Operating System:** Windows 11 Enterprise (x64) with WSL 2 enabled (`docker-desktop` distro running).
* **Node.js Environment:** Node.js `v24.12.0`, npm `11.6.2`.
* **Python Runtime (Host):** Python `3.14.6` at `C:\Users\ADMIN\AppData\Local\Microsoft\WindowsApps\python.exe`.
* **Container Engine:** Docker Engine `29.5.3`, Docker Compose `v5.1.4`.
* **Pre-cached Docker Images:**
  * `mariadb:10.11` (Official MariaDB Server)
  * `redis:latest` (Redis Cache & Queue Broker)
  * `python:3.11-slim` (Debian-based Python 3.11 runtime, optimal for Frappe)
* **Storage Footprint:**
  * Host volume `C:` free space: **4.53 GB**.
  * Reclaimable Docker build cache and volumes were inspected and pruned to preserve disk headroom.

### 1.3 Backend Inspection
* **Frappe Version:** Greenfield — Frappe v15 / Python 3.11 target architecture to be bootstrapped.
* **Installed Applications:** None currently present.
* **Existing DocTypes & Schemas:** None in the local workspace.
* **Existing Controllers & API Methods:** None.
* **Existing Authentication & Permissions:** None configured.
* **Existing HRMS Installation:** HRMS is not installed locally. Standard HRMS models (`Employee`, `Employee Checkin`, `Leave Application`, `Department`) will be implemented natively in the Frappe app schema without unnecessary third-party dependencies, adhering strictly to the required specifications.

### 1.4 Frontend Inspection
* **React & Vite:** Not yet scaffolded.
* **TypeScript & Tailwind CSS:** Not yet initialized.
* **Routes, State Management & UI Components:** Greenfield.

---

## 2. Existing Implementation Assessment

| Evaluation Criterion | Current Capability | Architectural Gap / Risk | Resolution Strategy |
| :--- | :--- | :--- | :--- |
| **30,000 Employees** | Empty | No schema or hierarchy table | Build `tabEmployee` with indexed `reports_to` and `department` fields. |
| **10,950,000 Activity Logs** | Empty | Standard ORM `frappe.get_all()` will exhaust memory and crash | Use pure SQL aggregations, composite B-Tree indexes, server-side pagination, and streaming generation. |
| **Employee Historical Analytics** | Empty | Massive range scans across 10.95M rows would be unacceptably slow | Implement composite index `(employee, activity_date)` on `tabEmployee Activity Log`. |
| **Manager Hierarchy** | Empty | N+1 recursive lookups for indirect reports will degrade response times | Use indexed parent lookups / recursive CTEs to resolve team member IDs in a single query. |
| **Role-Based Access Control** | Empty | Relying on frontend visibility leaves security holes | Enforce backend role guards in Python controllers on every whitelisted method. |
| **Synthetic Seed Generation** | Empty | Naive ORM record-by-record insertion would take 15+ hours | Implement direct multi-row batch SQL inserts (25,000 rows/batch) with checkpointing and idempotency. |
| **Disk Quota Constraints** | 4.53 GB free | 10.95M rows with poor column sizing could exceed disk space | Use compact SQL types (`DATE`, `TIME`, `INT UNSIGNED`, `ENUM`), disable binlogs in dev, compact InnoDB storage. |

---

## 3. Proposed Backend Architecture

```
                               ┌─────────────────────────────────────────┐
                               │       Client Requests (React SPA)       │
                               └────────────────────┬────────────────────┘
                                                    │
                                     HTTP / Cookie Authentication (`sid`)
                                                    │
                               ┌────────────────────▼────────────────────┐
                               │         Frappe Python Backend           │
                               │                                         │
                               │  ┌───────────────────────────────────┐  │
                               │  │ Session & RBAC Middleware         │  │
                               │  │ (CEO, Manager, Employee)          │  │
                               │  └─────────────────┬─────────────────┘  │
                               │                    │                    │
                               │  ┌─────────────────▼─────────────────┐  │
                               │  │ Whitelisted API Methods           │  │
                               │  │ - api/ceo.py                      │  │
                               │  │ - api/manager.py                  │  │
                               │  │ - api/employee.py                 │  │
                               │  │ - api/auth.py                     │  │
                               │  └─────────────────┬─────────────────┘  │
                               │                    │                    │
                               │  ┌─────────────────▼─────────────────┐  │
                               │  │ Optimized Analytics Engine        │  │
                               │  │ (SQL Aggregations, GROUP BY, CTE) │  │
                               │  └─────────────────┬─────────────────┘  │
                               └────────────────────┼────────────────────┘
                                                    │
                                        Indexed SQL TCP Connection
                                                    │
                               ┌────────────────────▼────────────────────┐
                               │           MariaDB 10.11 Server          │
                               │                                         │
                               │  - tabEmployee (30,000)                 │
                               │  - tabEmployee Activity Log (10,950,000)│
                               │  - tabEmployee Checkin                  │
                               │  - tabLeave Application                 │
                               │  - tabAttendance Correction Request     │
                               │  - tabSeed Checkpoint                   │
                               └─────────────────────────────────────────┘
```

### 3.1 Backend Runtimes & Containerization
* **MariaDB 10.11:** Configured with UTF8MB4, `innodb_buffer_pool_size=1G`, `innodb_file_per_table=1`, and transaction durability tuned for high throughput.
* **Redis:** In-memory store for session caching and background job message broker.
* **Python Runtime:** Python 3.11 container environment with Frappe Framework core libraries (`frappe-bench`, `werkzeug`, `gunicorn`, `redis`, `pymysql`).
* **Session Lifecycle:** 
  * Cookie-based session tracking using standard Frappe `sid` cookie.
  * Zero custom JWT overhead — seamless native integration with `frappe.session.user`.

---

## 4. Proposed Frontend Architecture

### 4.1 Technology Stack
* **Framework:** React 18 with Vite and TypeScript.
* **Styling:** Tailwind CSS with utility-first responsive styling.
* **Component Design:** Atomic component architecture (Atoms: Badges, Buttons; Molecules: Stat Cards, Filter Bars, Data Pickers; Organisms: Analytics Charts, Drilldown Modals, History Tables).
* **Charts & Visualizations:** Recharts / Chart.js for attendance trends, status donuts, and department bar charts.
* **Icons:** Lucide React.
* **API Client:** Axios instance with `withCredentials: true` and automated CSRF / session handling.

### 4.2 Application Route & View Structure
* `/login`: Frappe session authentication screen.
* `/`: Role-aware redirector based on authenticated profile.
* `/ceo`:
  * Company KPI cards (Total headcount, Present, Absent, On Leave, Late, Weekly Off).
  * 30-day company-wide attendance trend line/bar chart.
  * Department-wise attendance breakdown table with sorting and filtering.
  * Employee search with instant debounced autocomplete (`name` or `employee_id`).
  * Employee 360 profile drill-down modal with full 365-day attendance log.
  * Exception summary (anomalies, missing punch, excessive tardiness).
* `/manager`:
  * Direct and indirect reports headcount overview.
  * Team attendance summary for current date.
  * Missing check-in / check-out and late arrival exception queue.
  * Team member profiles and drill-down.
  * Leave approval and rejection inbox with single-click actions.
  * Interactive team leave calendar.
* `/employee`:
  * Punch action widget (one-click Check-in and Check-out with instant status update).
  * Current day status card (First login, last logout, elapsed work time).
  * Personal attendance history table with server-side pagination, date filters, and status tags.
  * Monthly attendance metrics (Present days, leaves taken, late count).
  * Leave application form and approval tracking timeline.
  * Attendance correction request dialog.

---

## 5. DocType Design & Database Schema

### 5.1 `Employee`
Standard Frappe DocType representing the workforce hierarchy.
* `name`: VARCHAR(32) PRIMARY KEY (e.g. `EMP-00001` to `EMP-30000`)
* `employee_name`: VARCHAR(140) NOT NULL
* `department`: VARCHAR(100) NOT NULL (e.g. Engineering, Sales, Marketing, HR, Finance, Operations)
* `designation`: VARCHAR(100) NOT NULL
* `reports_to`: VARCHAR(32) NULL (Foreign key to `Employee.name`)
* `user_id`: VARCHAR(140) UNIQUE NOT NULL (Email linked to `tabUser`)
* `status`: ENUM (`Active`, `Left`, `Suspended`) DEFAULT `Active`
* `date_of_joining`: DATE NOT NULL

### 5.2 `Employee Checkin`
Raw timecard punch events.
* `name`: VARCHAR(36) PRIMARY KEY
* `employee`: VARCHAR(32) NOT NULL
* `time`: DATETIME NOT NULL
* `log_type`: ENUM (`IN`, `OUT`) NOT NULL
* `device_id`: VARCHAR(50) DEFAULT `WEB`

### 5.3 `Employee Activity Log`
One derived daily summary per employee per calendar date.
* `name`: VARCHAR(64) PRIMARY KEY (e.g. `EAL-EMP00001-20250101`)
* `employee`: VARCHAR(32) NOT NULL
* `activity_date`: DATE NOT NULL
* `first_login`: TIME NULL
* `last_logout`: TIME NULL
* `total_work_seconds`: INT UNSIGNED NOT NULL DEFAULT 0
* `number_of_sessions`: SMALLINT UNSIGNED NOT NULL DEFAULT 0
* `attendance_status`: ENUM (`Present`, `Absent`, `On Leave`, `Late`, `Weekly Off`) NOT NULL
* `calculation_timestamp`: DATETIME NOT NULL
* **Constraints:**
  * `UNIQUE KEY uk_emp_date (employee, activity_date)`

### 5.4 `Leave Application`
* `name`: VARCHAR(36) PRIMARY KEY
* `employee`: VARCHAR(32) NOT NULL
* `leave_type`: ENUM (`Casual Leave`, `Sick Leave`, `Earned Leave`) NOT NULL
* `from_date`: DATE NOT NULL
* `to_date`: DATE NOT NULL
* `total_leave_days`: DECIMAL(5,1) NOT NULL
* `status`: ENUM (`Pending`, `Approved`, `Rejected`) DEFAULT `Pending`
* `approved_by`: VARCHAR(32) NULL

### 5.5 `Attendance Correction Request`
* `name`: VARCHAR(36) PRIMARY KEY
* `employee`: VARCHAR(32) NOT NULL
* `activity_date`: DATE NOT NULL
* `requested_status`: ENUM (`Present`, `On Leave`) NOT NULL
* `reason`: TEXT NOT NULL
* `status`: ENUM (`Pending`, `Approved`, `Rejected`) DEFAULT `Pending`
* `reviewed_by`: VARCHAR(32) NULL

### 5.6 `Seed Checkpoint`
Tracks synthetic data generator progress.
* `seed_key`: VARCHAR(64) PRIMARY KEY
* `last_completed_batch`: INT NOT NULL
* `total_records_inserted`: BIGINT NOT NULL
* `status`: ENUM (`Pending`, `In Progress`, `Completed`, `Failed`)
* `updated_at`: DATETIME NOT NULL

---

## 6. API Design & Endpoint Contracts

All API methods are exposed via Frappe whitelisted functions (`@frappe.whitelist()`) and return strict JSON payloads.

### 6.1 Authentication (`employee360.api.auth`)
* `POST /api/method/login` — Standard Frappe session initiation.
* `GET /api/method/logout` — Destroys current session cookie.
* `GET /api/method/employee360.api.auth.get_current_profile`
  * **Role:** Any authenticated user.
  * **Response:** `{ employee_id, employee_name, user_id, roles: ["CEO"|"Manager"|"Employee"], department, designation }`

### 6.2 CEO Analytics (`employee360.api.ceo`)
* `GET /api/method/employee360.api.ceo.get_company_kpis?date=YYYY-MM-DD`
  * **Authorization:** CEO role only.
  * **Response:**
    ```json
    {
      "total_employees": 30000,
      "present": 25200,
      "absent": 1800,
      "on_leave": 1200,
      "late": 1500,
      "weekly_off": 300,
      "attendance_rate_percentage": 84.0
    }
    ```
* `GET /api/method/employee360.api.ceo.get_attendance_trends?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD`
  * **Authorization:** CEO role only.
  * **Aggregation:** SQL `GROUP BY activity_date, attendance_status`.
* `GET /api/method/employee360.api.ceo.get_department_analytics?date=YYYY-MM-DD`
  * **Authorization:** CEO role only.
  * **Aggregation:** Joined `tabEmployee` and `tabEmployee Activity Log` grouped by `department`.
* `GET /api/method/employee360.api.ceo.search_employees?query=EMP-001&limit=10`
  * **Authorization:** CEO role only.
  * **Response:** Matching employees with ID, name, department, designation.
* `GET /api/method/employee360.api.ceo.get_employee_drilldown?employee=EMP-00001`
  * **Authorization:** CEO role only.
  * **Response:** Complete 365-day summary timeline, KPI cards, and leave summary.

### 6.3 Manager Team Endpoints (`employee360.api.manager`)
* `GET /api/method/employee360.api.manager.get_team_kpis?date=YYYY-MM-DD`
  * **Authorization:** Manager or CEO.
  * **Scope:** Scoped strictly to direct and indirect reports via recursive hierarchy CTE.
* `GET /api/method/employee360.api.manager.get_team_exceptions?date=YYYY-MM-DD&page=1&page_size=25`
  * **Authorization:** Manager or CEO.
  * **Output:** Missing punches, arrivals after 10:00 AM, unexcused absences.
* `POST /api/method/employee360.api.manager.action_leave_request`
  * **Payload:** `{ "leave_request_id": "...", "action": "Approved"|"Rejected" }`
  * **Authorization:** Manager of the reporting employee.

### 6.4 Employee Self-Service (`employee360.api.employee`)
* `POST /api/method/employee360.api.employee.punch`
  * **Payload:** `{ "log_type": "IN" | "OUT" }`
  * **Action:** Inserts punch event and triggers immediate incremental recalculation of today's `Employee Activity Log`.
* `GET /api/method/employee360.api.employee.get_today_status`
  * **Response:** Today's first punch, last punch, accumulated seconds, current status.
* `GET /api/method/employee360.api.employee.get_attendance_history?page=1&page_size=30&month=2025-05`
  * **Authorization:** Self only (`doc.employee == session_employee`).
* `POST /api/method/employee360.api.employee.apply_leave`
* `POST /api/method/employee360.api.employee.submit_correction_request`

---

## 7. Role and Permission Model

| Resource / DocType | CEO | Manager | Employee | Backend Enforcement Mechanism |
| :--- | :---: | :---: | :---: | :--- |
| **Company-Wide KPIs** | Full Read | No Access | No Access | Role guard: `frappe.only_for("CEO")` |
| **All Employee Profiles** | Full Read | Team Only | Self Only | Filter injected SQL: `WHERE employee IN (team_ids)` |
| **Employee Activity Log** | Full Read | Team Only | Self Only | Filter injected SQL: `WHERE employee = %(session_emp)s` |
| **Check-in / Punch** | Self | Self | Self | Enforce `employee == get_session_employee()` |
| **Leave Approval** | Full | Team Only | No Access | Verify `applicant.reports_to == session_employee` |
| **Correction Requests**| Full | Review Team | Create Self | Verify ownership on insert; verify hierarchy on update |

---

## 8. Database Indexing & Query Optimization Strategy

### 8.1 Critical Indexes on `tabEmployee Activity Log` (10,950,000 Rows)
1. **Primary / Unique Index:**
   ```sql
   UNIQUE INDEX uk_employee_date (employee, activity_date);
   ```
   *Guarantees zero duplicates and supports instant employee daily lookups in $O(1)$.*

2. **Company-Wide Analytics Index:**
   ```sql
   INDEX idx_date_status (activity_date, attendance_status);
   ```
   *Enables CEO dashboard aggregations across 30,000 daily records in < 25ms without full-table scans.*

3. **Employee Historical Range Index:**
   ```sql
   INDEX idx_emp_date (employee, activity_date DESC);
   ```
   *Enables employee drill-down and paginated historical queries in < 5ms.*

### 8.2 Indexes on `tabEmployee` (30,000 Rows)
```sql
INDEX idx_reports_to (reports_to);
INDEX idx_department (department);
INDEX idx_emp_search (employee_name, name);
```
*Accelerates manager recursive hierarchy resolution and instant prefix search autocomplete.*

---

## 9. Synthetic Data Generation Strategy (10,950,000 Records)

### 9.1 Data Generation Architecture
* **Target Scale:** 30,000 employees $\times$ 365 calendar days = **exactly 10,950,000 records**.
* **Generation Engine:** Direct Python database generator streaming parameterized SQL multi-row batch inserts (`INSERT INTO ... VALUES (...)`).
* **Batch Size:** 25,000 rows per batch transaction.
* **Memory Management:** Rows are yielded dynamically by a generator function and committed in batches. Application memory footprint is strictly bounded to $< 50\text{ MB}$.
* **Idempotency & Resumability:**
  * Uses `tabSeed Checkpoint` storing `(last_completed_batch, total_records)`.
  * If interrupted, the generator inspects the checkpoint and resumes from the exact batch without duplicate insertion.
  * SQL execution leverages `INSERT IGNORE` or verified partition ranges to prevent primary key collisions.
* **Realistic Business Simulation:**
  * Weekends (Saturdays/Sundays) mapped to `Weekly Off`.
  * Weekdays assigned realistic distributions: 85% `Present`, 5% `Late`, 5% `On Leave`, 5% `Absent`.
  * Realistic punch pairs: First login between 08:30–10:30 AM, last logout between 17:00–19:30 PM, computed total work seconds.

---

## 10. Scalability & Storage Considerations

* **Disk Budgeting:**
  * Raw data per activity row: ~65 bytes.
  * Index overhead: ~25 bytes.
  * Total storage for 10.95M rows: **~980 MB to 1.15 GB**.
  * Fits comfortably within the available 4.53 GB free disk space.
* **InnoDB Configuration:**
  * Set `innodb_buffer_pool_size=1G` to keep active indexes in memory.
  * MariaDB `character-set-server=utf8mb4` with `innodb_file_per_table=1`.
  * Development binary logging disabled (`skip-log-bin`) during seeding to avoid consuming disk with undo/redo binlogs.

---

## 11. Testing Strategy

1. **Database & Index Verification:**
   * Automated SQL verification queries confirming exactly 30,000 employees and 10,950,000 daily summaries.
   * `EXPLAIN` query plan checks verifying `type: ref` or `range` with zero `ALL` table scans.
2. **RBAC Security Tests:**
   * Role leakage tests ensuring employees cannot access CEO or manager endpoints.
   * Cross-department isolation tests ensuring managers cannot inspect employees outside their reporting tree.
3. **Performance Benchmarking:**
   * Measure execution latency for:
     * CEO Company KPI query (target: $< 50\text{ ms}$).
     * CEO 30-day attendance trend query (target: $< 100\text{ ms}$).
     * Employee historical paginated drilldown (target: $< 20\text{ ms}$).
     * Manager team exception list (target: $< 50\text{ ms}$).

---

## 12. Implementation Milestones

```
Milestone 1: Backend Foundation & Container Environment
  ├── Configure Docker Compose (MariaDB 10.11, Redis, Python 3.11 Frappe runtime)
  ├── Initialize Frappe custom app 'employee360' and database connection
  └── Verify Frappe session authentication

Milestone 2: Schema Implementation & Performance Tuning
  ├── Define DocTypes: Employee, Employee Activity Log, Checkin, Correction Request
  ├── Apply composite database indexes & unique constraints
  └── Configure role permissions (CEO, Manager, Employee)

Milestone 3: High-Performance Synthetic Seed Engine
  ├── Seed 30,000 employees with structured organizational hierarchy
  ├── Run batch generator for 10,950,000 Employee Activity Log records
  └── Execute count and integrity verification scripts

Milestone 4: Optimized Backend Analytics APIs & RBAC Enforcement
  ├── Implement CEO analytics methods (KPIs, Trends, Department, Autocomplete)
  ├── Implement Manager team methods (Reports tree, Exceptions, Leave actions)
  ├── Implement Employee self-service methods (Punch, History, Correction request)
  └── Run RBAC security and performance test suite

Milestone 5: Frontend Development (React + Vite + TypeScript + Tailwind)
  ├── Setup Vite SPA project with Tailwind CSS & Lucide icons
  ├── Build responsive CEO Dashboard with analytics charts & drilldown modals
  ├── Build Manager Team Dashboard with exception monitoring & leave approvals
  ├── Build Employee Portal with one-click punch, status card, & history table
  └── Wire up Frappe session authentication & API client

Milestone 6: System Verification, Benchmarking & Documentation
  ├── Perform query latency benchmarks on the 10.95M dataset
  ├── Document verification results, API reference, and start commands
  └── Final delivery walkthrough
```

---

## 13. Risks & Mitigations

* **Seed Generation Timeout:** Seeding 10.95M rows could take excessive time if executed row-by-row.
  * *Mitigation:* Multi-value bulk SQL statements (25,000 rows/batch) inside committed transactions, yielding ~50,000–80,000 rows/sec.
* **Large Dataset Memory Overflow in Python:** Loading query results into Python memory.
  * *Mitigation:* All calculations, counts, and aggregations are delegated directly to MariaDB via SQL `GROUP BY` and `COUNT()`.

