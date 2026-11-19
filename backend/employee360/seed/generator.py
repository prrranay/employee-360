import datetime
import random
from typing import Generator, List, Tuple, Dict, Set
from employee360.seed.config import SeedConfig

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "David", "Elizabeth",
    "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Christopher", "Karen",
    "Charles", "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra",
    "Donald", "Ashley", "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Carol", "Kevin", "Amanda", "Brian", "Dorothy", "George", "Melissa", "Timothy", "Deborah",
    "Ronald", "Stephanie", "Edward", "Rebecca", "Jason", "Sharon", "Jeffrey", "Laura", "Ryan", "Cynthia",
    "Jacob", "Kathleen", "Gary", "Amy", "Nicholas", "Shirley", "Eric", "Angela", "Jonathan", "Helen",
    "Stephen", "Anna", "Larry", "Brenda", "Justin", "Pamela", "Scott", "Nicole", "Brandon", "Emma",
    "Benjamin", "Samantha", "Samuel", "Katherine", "Gregory", "Christine", "Alexander", "Debra", "Frank", "Rachel",
    "Patrick", "Catherine", "Raymond", "Carolyn", "Jack", "Janet", "Dennis", "Ruth", "Jerry", "Maria",
    "Tyler", "Heather", "Aaron", "Diane", "Jose", "Virginia", "Adam", "Julie", "Nathan", "Joyce",
    "Henry", "Victoria", "Douglas", "Olivia", "Zachary", "Kelly", "Peter", "Christina", "Kyle", "Lauren",
    "Noah", "Joan", "Ethan", "Evelyn", "Jeremy", "Judith", "Christian", "Megan", "Walter", "Andrea",
    "Keith", "Cheryl", "Austin", "Hannah", "Roger", "Jacqueline", "Terry", "Martha", "Sean", "Gloria",
    "Gerald", "Teresa", "Carl", "Ann", "Harold", "Sara", "Dylan", "Madison", "Arthur", "Frances",
    "Lawrence", "Kathryn", "Jordan", "Janice", "Jesse", "Jean", "Bryan", "Abigail", "Billy", "Alice"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts",
    "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker", "Cruz", "Edwards", "Collins", "Reyes",
    "Stewart", "Morris", "Morales", "Murphy", "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper",
    "Peterson", "Bailey", "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson",
    "Watson", "Brooks", "Chavez", "Wood", "James", "Bennett", "Gray", "Mendoza", "Ruiz", "Hughes",
    "Price", "Alvarez", "Castillo", "Sanders", "Patel", "Myers", "Long", "Ross", "Foster", "Jimenez"
]


def generate_shift_data() -> dict:
    return {
        "name": "General Shift",
        "shift_name": "General Shift",
        "start_time": "09:00:00",
        "end_time": "18:00:00",
        "grace_period_mins": 15,
        "expected_working_hours": 8.00,
        "weekly_off_days": "Saturday, Sunday",
        "applicable_departments": "All"
    }


def generate_all_employees(total_employees: int = None) -> List[dict]:
    """
    Generates employees with a realistic, acyclic management hierarchy.
    Handles any count from 1 up to 30,000+ employees.
    """
    if total_employees is None:
        total_employees = SeedConfig.TOTAL_EMPLOYEES

    random.seed(SeedConfig.RANDOM_SEED)
    employees = []

    demo_map = {d["employee_id"]: d for d in SeedConfig.DEMO_USERS}

    for idx in range(1, total_employees + 1):
        emp_id = f"EMP-{idx:05d}"

        if idx == 1:
            level = "CEO"
            manager = None
            dept = "Executive"
            designation = "Chief Executive Officer"
        elif 2 <= idx <= 11:
            level = "VP"
            manager = "EMP-00001"
            dept = SeedConfig.DEPARTMENTS[(idx - 2) % len(SeedConfig.DEPARTMENTS)]
            designation = f"VP of {dept}"
        elif 12 <= idx <= 161:
            level = "Manager"
            head_idx = 2 + ((idx - 12) % 10)
            if head_idx > total_employees:
                head_idx = 1
            manager = f"EMP-{head_idx:05d}"
            dept = SeedConfig.DEPARTMENTS[(idx - 12) % len(SeedConfig.DEPARTMENTS)]
            designation = f"{dept} Manager"
        elif 162 <= idx <= 1361:
            level = "Lead"
            mgr_idx = 12 + ((idx - 162) % 150)
            if mgr_idx > total_employees:
                mgr_idx = min(idx - 1, 1)
            manager = f"EMP-{mgr_idx:05d}"
            dept = SeedConfig.DEPARTMENTS[(idx - 162) % len(SeedConfig.DEPARTMENTS)]
            designation = f"{dept} Team Lead"
        else:
            level = "IC"
            lead_idx = 162 + ((idx - 1362) % 1200)
            if lead_idx > total_employees:
                lead_idx = min(idx - 1, 1)
            manager = f"EMP-{lead_idx:05d}"
            dept = SeedConfig.DEPARTMENTS[(idx - 1362) % len(SeedConfig.DEPARTMENTS)]
            designation = random.choice(SeedConfig.DESIGNATIONS_BY_LEVEL["IC"])

        # Demo user details take precedence
        if emp_id in demo_map:
            demo_info = demo_map[emp_id]
            emp_name = demo_info["name"]
            user_id = demo_info["email"]
            dept = demo_info["department"]
            designation = demo_info["designation"]
        else:
            fn = random.choice(FIRST_NAMES)
            ln = random.choice(LAST_NAMES)
            emp_name = f"{fn} {ln}"
            user_id = None

        join_days_ago = random.randint(700, 2500)
        doj = SeedConfig.START_DATE - datetime.timedelta(days=join_days_ago)

        employees.append({
            "name": emp_id,
            "employee_id": emp_id,
            "employee_name": emp_name,
            "user_id": user_id,
            "manager": manager,
            "department": dept,
            "designation": designation,
            "date_of_joining": str(doj),
            "employment_status": "Active",
            "shift": "General Shift"
        })

    return employees


def _sec_to_time_str(total_seconds: int) -> str:
    h = (total_seconds // 3600) % 24
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def generate_employee_leaves(
    emp_id: str,
    emp_idx: int,
    manager: str,
    start_date: datetime.date = SeedConfig.START_DATE,
    end_date: datetime.date = SeedConfig.END_DATE
) -> Tuple[List[dict], Set[datetime.date]]:
    """
    Generates non-overlapping Leave Applications for a specific employee within the seed window.
    Returns:
      - List of leave record dicts (including Approved, Rejected, Pending).
      - Set of approved scheduled working dates (dates where status must be 'On Leave').
    """
    # Deterministic seed per employee
    emp_rand = random.Random(SeedConfig.RANDOM_SEED + emp_idx * 7919)
    leave_types = ["Casual Leave", "Sick Leave", "Earned Leave"]
    leaves = []
    approved_dates: Set[datetime.date] = set()

    is_demo = emp_id in [d["employee_id"] for d in SeedConfig.DEMO_USERS]
    roll = emp_rand.random()

    if is_demo:
        num_leaves = emp_rand.randint(1, 3)
    elif roll < 0.35:
        num_leaves = 0
    elif roll < 0.70:
        num_leaves = 1
    elif roll < 0.92:
        num_leaves = 2
    else:
        num_leaves = 3

    if num_leaves == 0:
        return leaves, approved_dates

    # Minimum separation between leave windows (days)
    occupied_intervals = []

    for l_idx in range(num_leaves):
        # Pick start offset within the 365-day seed window
        day_offset = emp_rand.randint(14, SeedConfig.DAYS_PER_EMPLOYEE - 21)
        cur_start = start_date + datetime.timedelta(days=day_offset)

        # Advance to a working day
        while cur_start.weekday() in (5, 6) or cur_start in SeedConfig.HOLIDAYS:
            cur_start += datetime.timedelta(days=1)

        dur_days = emp_rand.randint(1, 3)

        # Calculate working days forward (excluding weekends and holidays)
        curr = cur_start
        working_days_count = 0
        cur_covered_dates = []

        while working_days_count < dur_days and curr <= end_date:
            if curr.weekday() not in (5, 6) and curr not in SeedConfig.HOLIDAYS:
                working_days_count += 1
                cur_covered_dates.append(curr)
            if working_days_count < dur_days:
                curr += datetime.timedelta(days=1)

        cur_end = curr
        if working_days_count == 0 or cur_end > end_date:
            continue

        # Overlap check against already planned leaves for this employee
        overlaps = False
        for (o_start, o_end) in occupied_intervals:
            if not (cur_end < o_start - datetime.timedelta(days=7) or cur_start > o_end + datetime.timedelta(days=7)):
                overlaps = True
                break

        if overlaps:
            continue

        occupied_intervals.append((cur_start, cur_end))

        # Status: 88% Approved, 8% Rejected, 4% Pending
        s_roll = emp_rand.random()
        if s_roll < 0.88 or is_demo:
            status = "Approved"
        elif s_roll < 0.96:
            status = "Rejected"
        else:
            status = "Pending"

        leave_type = leave_types[l_idx % len(leave_types)]
        leave_id = f"LA-{emp_id}-{cur_start.strftime('%Y%m%d')}"
        approver = manager if manager else "EMP-00001"
        applied_at = datetime.datetime.combine(cur_start - datetime.timedelta(days=7), datetime.time(9, 30))
        decision_at = datetime.datetime.combine(cur_start - datetime.timedelta(days=4), datetime.time(14, 0)) if status != "Pending" else None

        record = {
            "name": leave_id,
            "employee": emp_id,
            "leave_type": leave_type,
            "from_date": str(cur_start),
            "to_date": str(cur_end),
            "total_leave_days": working_days_count,
            "reason": f"Personal matter / {leave_type}",
            "status": status,
            "approver": approver,
            "approval_comments": "Approved by manager" if status == "Approved" else "Rejected due to team coverage" if status == "Rejected" else None,
            "applied_at": applied_at.strftime("%Y-%m-%d %H:%M:%S"),
            "decision_at": decision_at.strftime("%Y-%m-%d %H:%M:%S") if decision_at else None
        }
        leaves.append(record)

        if status == "Approved":
            for d in cur_covered_dates:
                approved_dates.add(d)

    return leaves, approved_dates


def generate_all_leave_applications(employees: List[dict]) -> List[dict]:
    """
    Generates all Leave Application records for all seeded employees.
    """
    all_leaves = []
    for idx, emp in enumerate(employees, start=1):
        emp_id = emp["employee_id"]
        manager = emp.get("manager")
        leaves, _ = generate_employee_leaves(emp_id, idx, manager)
        all_leaves.extend(leaves)
    return all_leaves


def stream_activity_log_batches(
    start_batch_idx: int = 0,
    batch_size: int = SeedConfig.BATCH_SIZE,
    total_employees: int = None
) -> Generator[Tuple[int, List[tuple], List[tuple], List[tuple]], None, None]:
    """
    Yields batches of tuples ready for high-speed multi-row INSERT.
    Guarantees exactly 365 daily records per employee (total_employees * 365).
    Bounded memory footprint: yields batch_size records at a time and frees memory.

    Yields:
      (batch_number, activity_log_rows, attendance_exception_rows, raw_checkin_rows)
    """
    if total_employees is None:
        total_employees = SeedConfig.TOTAL_EMPLOYEES

    # Pre-generate the 365 calendar dates and their characteristics
    dates_meta = []
    curr_date = SeedConfig.START_DATE
    while curr_date <= SeedConfig.END_DATE:
        weekday = curr_date.weekday()  # 5=Sat, 6=Sun
        is_weekend = weekday in (5, 6)
        is_holiday = curr_date in SeedConfig.HOLIDAYS
        dates_meta.append((curr_date, curr_date.strftime("%Y-%m-%d"), is_weekend, is_holiday))
        curr_date += datetime.timedelta(days=1)

    assert len(dates_meta) == SeedConfig.DAYS_PER_EMPLOYEE, f"Expected 365 dates, got {len(dates_meta)}"

    calc_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    current_activity_rows = []
    current_exception_rows = []
    current_punch_rows = []
    current_batch_number = 0

    # Build manager lookup map
    employees = generate_all_employees(total_employees)
    mgr_map = {e["employee_id"]: e["manager"] for e in employees}

    # Stream across all employees
    for emp_idx in range(1, total_employees + 1):
        emp_id = f"EMP-{emp_idx:05d}"
        manager = mgr_map.get(emp_id) or "EMP-00001"

        # Generate leave coverage deterministically for this employee
        _, approved_leave_dates = generate_employee_leaves(emp_id, emp_idx, manager)

        # Consistent employee seed offset for deterministic attendance per employee
        emp_rand = random.Random(SeedConfig.RANDOM_SEED + emp_idx)

        for date_obj, date_str, is_weekend, is_holiday in dates_meta:
            name = f"EAL-{emp_id}-{date_str}"
            raw_punches = []

            if is_holiday:
                status = "Holiday"
                first_login = None
                last_logout = None
                work_seconds = 0
                sessions = 0
            elif is_weekend:
                status = "Weekly Off"
                first_login = None
                last_logout = None
                work_seconds = 0
                sessions = 0
            elif date_obj in approved_leave_dates:
                # Guaranteed consistency: Exactly matches approved Leave Application
                status = "On Leave"
                first_login = None
                last_logout = None
                work_seconds = 0
                sessions = 0
            else:
                # Working day: probabilistic distribution with SESSION-FIRST calculation
                roll = emp_rand.random()
                if roll < 0.85:
                    # Present (85%): On-time arrival within grace period (08:30:00 - 09:15:00)
                    status = "Present"
                    login_sec = 8 * 3600 + emp_rand.randint(30 * 60, 75 * 60)

                    if emp_rand.random() < 0.70:
                        # 2 sessions: morning + afternoon with lunch break
                        sessions = 2
                        out1_sec = 12 * 3600 + emp_rand.randint(30 * 60, 60 * 60)
                        in2_sec = out1_sec + emp_rand.randint(30 * 60, 60 * 60)
                        out2_sec = in2_sec + emp_rand.randint(4 * 3600, 5 * 3600 + 15 * 60)

                        dur1 = out1_sec - login_sec
                        dur2 = out2_sec - in2_sec
                        work_seconds = dur1 + dur2
                        first_login = _sec_to_time_str(login_sec)
                        last_logout = _sec_to_time_str(out2_sec)

                        raw_punches = [
                            (login_sec, "IN"),
                            (out1_sec, "OUT"),
                            (in2_sec, "IN"),
                            (out2_sec, "OUT")
                        ]
                    else:
                        # 1 continuous session: 8.0h to 9.0h
                        sessions = 1
                        dur = emp_rand.randint(28800, 32400)
                        out_sec = login_sec + dur
                        work_seconds = dur
                        first_login = _sec_to_time_str(login_sec)
                        last_logout = _sec_to_time_str(out_sec)

                        raw_punches = [
                            (login_sec, "IN"),
                            (out_sec, "OUT")
                        ]

                elif roll < 0.92:
                    # Late (7%): Arrival after grace period (09:16:00 - 10:30:00)
                    status = "Late"
                    login_sec = 9 * 3600 + emp_rand.randint(16 * 60, 90 * 60)

                    if emp_rand.random() < 0.50:
                        sessions = 2
                        out1_sec = 13 * 3600 + emp_rand.randint(0, 30 * 60)
                        in2_sec = out1_sec + emp_rand.randint(30 * 60, 45 * 60)
                        out2_sec = in2_sec + emp_rand.randint(4 * 3600 + 30 * 60, 5 * 3600 + 30 * 60)

                        dur1 = out1_sec - login_sec
                        dur2 = out2_sec - in2_sec
                        work_seconds = dur1 + dur2
                        first_login = _sec_to_time_str(login_sec)
                        last_logout = _sec_to_time_str(out2_sec)

                        raw_punches = [
                            (login_sec, "IN"),
                            (out1_sec, "OUT"),
                            (in2_sec, "IN"),
                            (out2_sec, "OUT")
                        ]
                    else:
                        sessions = 1
                        dur = emp_rand.randint(27000, 30600)
                        out_sec = login_sec + dur
                        work_seconds = dur
                        first_login = _sec_to_time_str(login_sec)
                        last_logout = _sec_to_time_str(out_sec)

                        raw_punches = [
                            (login_sec, "IN"),
                            (out_sec, "OUT")
                        ]

                elif roll < 0.94:
                    # Half Day (2%): Exactly 4 to 4.5 hours
                    status = "Half Day"
                    login_sec = 8 * 3600 + emp_rand.randint(45 * 60, 90 * 60)
                    dur = emp_rand.randint(14400, 16200)
                    out_sec = login_sec + dur
                    first_login = _sec_to_time_str(login_sec)
                    last_logout = _sec_to_time_str(out_sec)
                    work_seconds = dur
                    sessions = 1

                    raw_punches = [
                        (login_sec, "IN"),
                        (out_sec, "OUT")
                    ]

                elif roll < 0.98:
                    # Absent (4%): Unexcused absence
                    status = "Absent"
                    first_login = None
                    last_logout = None
                    work_seconds = 0
                    sessions = 0

                else:
                    # Missing Check-out (2%): Punch IN recorded, no OUT
                    # CRITICAL: No fabricated work duration or logout!
                    status = "Missing Check-out"
                    login_sec = 8 * 3600 + emp_rand.randint(45 * 60, 90 * 60)
                    first_login = _sec_to_time_str(login_sec)
                    last_logout = None
                    work_seconds = 0
                    sessions = 1

                    raw_punches = [
                        (login_sec, "IN")
                    ]

                    # Generate corresponding Attendance Exception
                    exc_name = f"EXC-{emp_id}-{date_str}"
                    current_exception_rows.append((
                        exc_name,
                        f"{date_str} 18:30:00",
                        f"{date_str} 18:30:00",
                        "Administrator",
                        "Administrator",
                        0,
                        emp_id,
                        date_str,
                        "Missing Check-out",
                        "Open",
                        manager,
                        "Automated system exception: Missing check-out punch on scheduled shift",
                        "Missing Check-out"
                    ))

            # Build activity log row tuple (active_seconds = None, is_synthetic = 1)
            row = (
                name,
                f"{date_str} 23:59:59",  # creation
                f"{date_str} 23:59:59",  # modified
                "Administrator",         # modified_by
                "Administrator",         # owner
                0,                       # docstatus
                emp_id,
                date_str,
                status,
                first_login,
                last_logout,
                work_seconds,
                None,                    # active_seconds (unmeasured)
                sessions,
                calc_timestamp,
                0,                       # is_regularized
                None,                    # regularization_exception
                1                        # is_synthetic
            )
            current_activity_rows.append(row)

            # Build raw checkin records if raw punches are enabled
            if SeedConfig.GENERATE_RAW_PUNCHES and raw_punches:
                for p_idx, (sec_val, log_type) in enumerate(raw_punches, start=1):
                    p_time = f"{date_str} {_sec_to_time_str(sec_val)}"
                    chk_name = f"CHK-{emp_id}-{date_str}-{p_idx}"
                    current_punch_rows.append((
                        chk_name,
                        p_time,
                        p_time,
                        "Administrator",
                        "Administrator",
                        0,
                        emp_id,
                        p_time,
                        log_type,
                        "Seed",
                        None,
                        "Seeded historical attendance",
                        None,
                        0.0
                    ))

            if len(current_activity_rows) >= batch_size:
                current_batch_number += 1
                if current_batch_number > start_batch_idx:
                    yield (
                        current_batch_number,
                        current_activity_rows,
                        current_exception_rows,
                        current_punch_rows
                    )
                current_activity_rows = []
                current_exception_rows = []
                current_punch_rows = []

    # Final partial batch if any
    if current_activity_rows:
        current_batch_number += 1
        if current_batch_number > start_batch_idx:
            yield (
                current_batch_number,
                current_activity_rows,
                current_exception_rows,
                current_punch_rows
            )
