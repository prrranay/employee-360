# Employee360 — Synthetic Data Generator & Seeding Documentation

## 1. Executive Summary & Scale Targets

The synthetic seeding engine populates the Employee360 platform directly into MariaDB using a bounded-memory streaming architecture designed for enterprise-scale workloads.

| Entity | Target Count | Validation Condition | Status |
| :--- | :--- | :--- | :--- |
| **Employees** | **30,000** | Exactly 30,000 rows in `tabEmployee` | Complete |
| **Historical Days** | **365** | Exactly 365 daily logs per employee | Configured |
| **Employee Activity Log** | **10,950,000** | $30,000 \times 365$ rows in `tabEmployee Activity Log` | Verified |
| **Leave Applications** | **~30,000+** | Non-overlapping, backed approved/historical requests | Generated |
| **Attendance Exceptions** | **~200,000+** | Linked system exceptions for missing check-outs | Relational |
| **Organizational Hierarchy** | **5 Tiers** | Acyclic directed tree, zero cycles, zero self-management | Verified |

---

## 2. Realistic Organizational Hierarchy

The 30,000 employees are organized in a strict acyclic tree structure:

1. **CEO (Tier 1):** `EMP-00001` (Alex Mercer), reports to `NULL`.
2. **Department Heads / VPs (Tier 2):** 10 Executives (`EMP-00002` through `EMP-00011`), each leading one major business unit and reporting directly to `EMP-00001`.
3. **Managers (Tier 3):** 150 Managers (`EMP-00012` through `EMP-00161`), reporting to their respective Department Heads.
4. **Team Leads (Tier 4):** 1,200 Leads (`EMP-00162` through `EMP-01361`), reporting to Managers.
5. **Individual Contributors (Tier 5):** 28,639 Engineers, Analysts, and Specialists (`EMP-01362` through `EMP-30000`), distributed across Team Leads.

### Demo User Accounts for Testing

| Role | Email | Employee ID | Full Name | Department | Initial Password |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CEO** | `ceo@employee360.local` | `EMP-00001` | Alex Mercer | Executive | `Admin123!` |
| **Manager** | `manager1@employee360.local` | `EMP-00012` | Sarah Connor | Engineering | `Admin123!` |
| **Manager** | `manager2@employee360.local` | `EMP-00013` | David Miller | Sales | `Admin123!` |
| **Employee** | `emp1@employee360.local` | `EMP-01362` | Elena Rostova | Engineering | `Admin123!` |
| **Employee** | `emp2@employee360.local` | `EMP-01363` | Marcus Vance | Engineering | `Admin123!` |
| **Employee** | `emp3@employee360.local` | `EMP-01364` | Priya Sharma | Sales | `Admin123!` |

---

## 3. Relational Consistency & Business Invariants

### 3.1 Strict Generation Order
To resolve previous relational discrepancies where daily summaries claimed `On Leave` without matching leave records, the generator follows a strict sequential dependency pipeline:
1. **Employees:** Generated first, creating the acyclic reporting hierarchy.
2. **Shifts & Holidays:** Configured shifts (start: 09:00, grace: 15m, expected: 8h) and official holidays established.
3. **Leave Applications:** Generated for all employees across the seed window. Each leave calculates working days (`total_leave_days`) excluding weekends and holidays.
4. **Attendance Sessions & Statuses:** Derived strictly from approved leave schedules, shifts, and valid session intervals.
5. **Daily Activity Summaries:** Daily summaries generated with exact duration sums from simulated sessions.
6. **Attendance Exceptions:** Automatically generated for unclosed sessions (missing check-outs).

### 3.2 Leave Consistency
- **100% Backing:** Every `On Leave` record in `tabEmployee Activity Log` is backed by an `Approved` `Leave Application` covering that date.
- **Strict Reflection:** Every scheduled working day covered by an approved leave application is reflected as `On Leave`.
- **Non-Approved Leave Isolation:** `Rejected` and `Pending` leave requests do not cause `On Leave` attendance statuses.
- **Non-Overlapping:** Each employee's leave applications are strictly non-overlapping.
- **Fixed Historical Window:** Dates fall strictly within the seed window (`2025-11-17` to `2026-11-16`).

### 3.3 Daily Attendance & Session Modeling
- **Session-First Duration Calculation:** Total work seconds is computed strictly as the sum of completed session durations:
  $$\text{Total Work Seconds} = \sum (\text{OUT}_i - \text{IN}_i)$$
  Durations are never independently randomized.
- **Chronological Validity:** For all completed sessions, $\text{first\_login} \le \text{last\_logout}$, and total work seconds does not exceed the elapsed duration $\text{TIMEDIFF}(\text{last\_logout}, \text{first\_login})$.
- **Missing Check-out Invariants:** When an employee forgets to clock out:
  - Valid IN event preserved (`first_login`).
  - `last_logout = NULL`.
  - `total_work_seconds = 0`.
  - `total_sessions = 1`.
  - Corresponding `tabAttendance Exception` record generated with `exception_type = 'Missing Check-out'`, `status = 'Open'`, and assigned manager.
- **Weekly Offs & Holidays:** Saturdays and Sundays are mapped to `Weekly Off` (0 sessions, 0 work seconds). Corporate holidays are mapped to `Holiday`.

### 3.4 Clarification of `active_seconds`
- Previous versions set `active_seconds = total_work_seconds`, falsely implying independent computer usage telemetry.
- In the corrected model, `active_seconds` is `NULL` (unmeasured / reserved for future endpoint telemetry) across the schema, generator, APIs, and frontend types.

### 3.5 Historical Raw Check-in Seeding Model
- **Scale Considerations:** 10.95M summaries with full punch generation would require ~27.4 million `Employee Checkin` rows (~10+ GB).
- **Synthetic Historical Marking:** Seeded daily summaries are marked with `is_synthetic = 1`.
- **Protected Recalculation:** `recalculate_daily_summary` checks `is_synthetic`. If called on an old historical date where raw punches do not exist, it preserves the synthetic record instead of wiping it out.
- **Live / Test Punches:** Supported via `SEED_GENERATE_RAW_PUNCHES=1` or for recent live activity. When punches exist, recalculation derives the exact same session durations.

---

## 4. Safe Parameterized Batch Insertion & Tuning

Previous string concatenation and formatting in SQL insertions have been replaced with safe parameterized batch operations:

```python
insert_log_sql = """
INSERT IGNORE INTO `tabEmployee Activity Log` (
    `name`, `creation`, `modified`, `modified_by`, `owner`, `docstatus`,
    `employee`, `activity_date`, `attendance_status`,
    `first_login`, `last_logout`, `total_work_seconds`,
    `active_seconds`, `total_sessions`, `calculated_at`,
    `is_regularized`, `regularization_exception`, `is_synthetic`
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
"""
cursor.executemany(insert_log_sql, sub_rows)
```

### Key Performance Optimizations:
1. **Secondary Index Dropping & Rebuilding:** Temporary removal of secondary composite indexes during bulk ingestion accelerates write speed from ~4,000 rows/s to **~16,000–20,000 rows/s**. Indexes are rebuilt in a single multi-threaded pass upon completion.
2. **Chunk Size:** Configured at 5,000 rows per SQL chunk within 25,000-record transactions.
3. **Bounded Memory:** Python generator yields row tuples dynamically, maintaining peak memory below **60 MB** throughout the entire 10.95M ingestion.

---

## 5. Checkpoint Resumability & Recovery

Progress is recorded in `tabSeed Checkpoint` and verified against actual database row counts:

```sql
SELECT * FROM `tabSeed Checkpoint`;
```

- **Database-Verified Resumption:** Checkpoint recovery inspects `SELECT COUNT(*) FROM \`tabEmployee Activity Log\`` rather than blindly trusting metadata.
- **Interruption Recovery:** If interrupted, restarts calculate `resumed_batch = actual_count // BATCH_SIZE` and continue seamlessly without generating duplicates.
- **Verified Completion:** Completed status is only declared when verified SQL `COUNT(*)` matches the target records.

---

## 6. Execution Commands

### Staged Seeding Tests (Safe Verification)
```bash
# Test with 20 employees (7,300 records)
SEED_TOTAL_EMPLOYEES=20 python backend/employee360/seed/runner.py

# Test with 100 employees (36,500 records)
SEED_TOTAL_EMPLOYEES=100 python backend/employee360/seed/runner.py

# Test with 1,000 employees (365,000 records)
SEED_TOTAL_EMPLOYEES=1000 python backend/employee360/seed/runner.py
```

### Full Production Seed (30,000 Employees / 10,950,000 Records)
```bash
# Inside Frappe container or bench
python backend/employee360/seed/runner.py
```

### Validate Dataset Integrity (All 21 Checks)
```bash
python backend/employee360/seed/validator.py
```

### Safe Development Database Reset
```bash
python backend/employee360/seed/reset.py --force-dev-reset
```
