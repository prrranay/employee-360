# Employee360 — Synthetic Data Generator & Seeding Documentation

## 1. Executive Summary & Scale Targets

The synthetic seeding engine populates the Employee360 platform directly into MariaDB using a bounded-memory streaming architecture designed for enterprise-scale workloads.

| Entity | Target Count | Validation Condition | Status |
| :--- | :--- | :--- | :--- |
| **Employees** | **30,000** | Exactly 30,000 rows in `tabEmployee` | Complete |
| **Historical Days** | **365** | Exactly 365 daily logs per employee | Configured |
| **Employee Activity Log** | **10,950,000** | $30,000 \times 365$ rows in `tabEmployee Activity Log` | In Progress |
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

## 3. Business Invariants & Attendance Modeling

Every daily record satisfies the following invariants:
1. **Exactly 365 Days per Employee:** Evaluated over the fixed calendar window (`2025-11-17` to `2026-11-16`).
2. **Weekly Off Consistency:** Every Saturday and Sunday is mapped strictly to `Weekly Off` with zero work seconds, `NULL` login/logout, and `total_sessions = 0`.
3. **Holiday Consistency:** 10 official corporate holidays (New Year, Memorial Day, Labor Day, Thanksgiving, Christmas, etc.) are mapped to `Holiday`.
4. **Missing Check-out Integrity:** When an employee forgets to clock out, `attendance_status = 'Missing Check-out'`, `first_login` is recorded, but **`last_logout` remains `NULL` and `total_work_seconds` is `0`**. Fabricated completed work durations are forbidden.
5. **Chronological Validity:** For all completed sessions, `first_login < last_logout` and `total_work_seconds > 0`.
6. **Late Arrivals:** Logins after the 15-minute grace period (after 09:15:00 AM) are classified as `Late`.
7. **Deterministic Reproducibility:** The generator utilizes a fixed seed (`seed = 42`) ensuring identical data generation across multiple executions.

---

## 4. High-Performance Insertion Architecture

```
┌────────────────────────────────────────────────────────┐
│           Synthetic Generator (Generator Function)     │
│   - Streams 25,000 rows per batch                      │
│   - Peak Memory < 50 MB (Zero full-dataset hoarding)   │
└───────────────────────────┬────────────────────────────┘
                            │ Multi-row SQL batches (5,000 rows/chunk)
┌───────────────────────────▼────────────────────────────┐
│                    MariaDB Engine                      │
│   1. Drop secondary B-Tree indexes                     │
│   2. Bulk insert via INSERT IGNORE                     │
│   3. Commit every 25,000 records                       │
│   4. Update tabSeed Checkpoint table                   │
│   5. Rebuild composite indexes in a single fast pass   │
└────────────────────────────────────────────────────────┘
```

### Key Optimizations:
* **Temporary Secondary Index Dropping:** Dropping `idx_eal_emp_date`, `idx_eal_date_emp`, `idx_eal_status_date`, and `idx_eal_date_status` during insertion accelerates write throughput from ~4,000 rows/sec to **~25,000–35,000 rows/sec**. The indexes are rebuilt via a single B-Tree pass upon completion.
* **Bounded Memory Footprint:** Python generator yields row tuples dynamically, garbage-collecting each batch after database commit.
* **Disabled Binary Logging:** MariaDB started with `--skip-log-bin` to prevent exhausting disk space with ~5 GB of binlog files.

---

## 5. Resumability & Idempotency Engine

Progress is continuously recorded in `tabSeed Checkpoint`:

```sql
SELECT * FROM `tabSeed Checkpoint`;
```

| Field | Description |
| :--- | :--- |
| `seed_key` | Primary identifier (`attendance_seed`) |
| `last_completed_batch` | Last successfully committed transaction batch |
| `total_records_inserted` | Running total of verified inserted records |
| `target_records` | Total target (10,950,000) |
| `status` | `Pending`, `In Progress`, or `Completed` |
| `updated_at` | Timestamp of last committed batch |

If interrupted by process kill or power loss, re-running `runner.py` detects the checkpoint and resumes from batch `last_completed_batch + 1` without duplicate keys or re-insertion.

---

## 6. Execution Commands

### Run Seeding
```bash
# Direct runner on host or container
python backend/apps/employee360/employee360/seed/runner.py
```

### Validate Dataset Integrity
```bash
python backend/apps/employee360/employee360/seed/validator.py
```

### Safe Development Database Reset
```bash
# Protected by safety confirmation flag
python backend/apps/employee360/employee360/seed/reset.py --force-dev-reset
```

