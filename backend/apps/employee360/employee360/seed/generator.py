import datetime
import random
from typing import Generator, List, Tuple
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

def generate_all_employees() -> List[dict]:
    """
    Generates exactly 30,000 employees with a realistic, acyclic management hierarchy:
    - EMP-00001: CEO (no manager)
    - EMP-00002 to EMP-00011: 10 Department Heads (report to CEO)
    - EMP-00012 to EMP-00161: 150 Managers (report to Department Heads)
    - EMP-00162 to EMP-01361: 1,200 Team Leads (report to Managers)
    - EMP-01362 to EMP-30000: 28,639 Individual Contributors (report to Team Leads / Managers)
    All joining dates are between 2018-01-01 and 2024-12-31 (active during all 365 seed days).
    """
    random.seed(SeedConfig.RANDOM_SEED)
    employees = []

    # Map of demo accounts by employee_id
    demo_map = {d["employee_id"]: d for d in SeedConfig.DEMO_USERS}

    for idx in range(1, SeedConfig.TOTAL_EMPLOYEES + 1):
        emp_id = f"EMP-{idx:05d}"

        # Assign hierarchy level & manager
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
            # Reports to one of the 10 department heads
            head_idx = 2 + ((idx - 12) % 10)
            manager = f"EMP-{head_idx:05d}"
            dept = SeedConfig.DEPARTMENTS[(idx - 12) % len(SeedConfig.DEPARTMENTS)]
            designation = f"{dept} Manager"
        elif 162 <= idx <= 1361:
            level = "Lead"
            # Reports to one of the 150 managers
            mgr_idx = 12 + ((idx - 162) % 150)
            manager = f"EMP-{mgr_idx:05d}"
            dept = SeedConfig.DEPARTMENTS[(idx - 162) % len(SeedConfig.DEPARTMENTS)]
            designation = f"{dept} Team Lead"
        else:
            level = "IC"
            # Reports to one of the 1,200 team leads
            lead_idx = 162 + ((idx - 1362) % 1200)
            manager = f"EMP-{lead_idx:05d}"
            dept = SeedConfig.DEPARTMENTS[(idx - 1362) % len(SeedConfig.DEPARTMENTS)]
            designation = random.choice(SeedConfig.DESIGNATIONS_BY_LEVEL["IC"])

        # Name selection
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

        # Joining date between 2018-01-01 and 2024-12-31
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


def stream_activity_log_batches(
    start_batch_idx: int = 0,
    batch_size: int = SeedConfig.BATCH_SIZE
) -> Generator[Tuple[int, List[tuple]], None, None]:
    """
    Yields batches of tuples ready for high-speed multi-row INSERT.
    Guarantees exactly 365 daily records per employee (30,000 * 365 = 10,950,000).
    Bounded memory footprint: yields batch_size records at a time and frees memory.
    """
    random.seed(SeedConfig.RANDOM_SEED)

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

    total_records = SeedConfig.TOTAL_EMPLOYEES * SeedConfig.DAYS_PER_EMPLOYEE  # 10,950,000
    total_batches = (total_records + batch_size - 1) // batch_size

    calc_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    current_batch_rows = []
    current_batch_number = 0
    records_yielded = 0

    # Stream across all 30,000 employees
    for emp_idx in range(1, SeedConfig.TOTAL_EMPLOYEES + 1):
        emp_id = f"EMP-{emp_idx:05d}"
        
        # Consistent employee seed offset for deterministic variety per employee
        emp_rand = random.Random(SeedConfig.RANDOM_SEED + emp_idx)

        for date_obj, date_str, is_weekend, is_holiday in dates_meta:
            name = f"EAL-{emp_id}-{date_str}"

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
            else:
                # Working day: probabilistic distribution
                roll = emp_rand.random()
                if roll < 0.84:
                    # Present (84%): On-time arrival (08:30:00 - 09:14:59)
                    status = "Present"
                    login_min = emp_rand.randint(30, 74)  # 08:30 to 09:14
                    first_login = f"{login_min // 60 + 8:02d}:{login_min % 60:02d}:{emp_rand.randint(0, 59):02d}"
                    logout_hour = emp_rand.randint(17, 19)
                    logout_min = emp_rand.randint(15, 55)
                    last_logout = f"{logout_hour:02d}:{logout_min:02d}:{emp_rand.randint(0, 59):02d}"
                    # 8h to 9.5h work time (28800 to 34200 sec)
                    work_seconds = emp_rand.randint(28800, 34200)
                    sessions = 2 if emp_rand.random() < 0.65 else 1
                elif roll < 0.89:
                    # Late (5%): Arrival after grace period (09:16:00 - 10:30:00)
                    status = "Late"
                    login_min = emp_rand.randint(76, 150)  # 09:16 to 10:30
                    first_login = f"{login_min // 60 + 8:02d}:{login_min % 60:02d}:{emp_rand.randint(0, 59):02d}"
                    logout_hour = emp_rand.randint(18, 20)
                    logout_min = emp_rand.randint(10, 45)
                    last_logout = f"{logout_hour:02d}:{logout_min:02d}:{emp_rand.randint(0, 59):02d}"
                    work_seconds = emp_rand.randint(27000, 31000)
                    sessions = 2 if emp_rand.random() < 0.50 else 1
                elif roll < 0.93:
                    # On Leave (4%)
                    status = "On Leave"
                    first_login = None
                    last_logout = None
                    work_seconds = 0
                    sessions = 0
                elif roll < 0.96:
                    # Absent (3%)
                    status = "Absent"
                    first_login = None
                    last_logout = None
                    work_seconds = 0
                    sessions = 0
                elif roll < 0.98:
                    # Half Day (2%): 4 - 4.5 hours
                    status = "Half Day"
                    first_login = f"09:{emp_rand.randint(0, 15):02d}:{emp_rand.randint(0, 59):02d}"
                    last_logout = f"13:{emp_rand.randint(30, 59):02d}:{emp_rand.randint(0, 59):02d}"
                    work_seconds = emp_rand.randint(14400, 16200)
                    sessions = 1
                else:
                    # Missing Check-out (2%): Punch in occurred, no checkout punch
                    # CRITICAL: No fabricated work duration!
                    status = "Missing Check-out"
                    first_login = f"09:{emp_rand.randint(0, 30):02d}:{emp_rand.randint(0, 59):02d}"
                    last_logout = None
                    work_seconds = 0
                    sessions = 1

            # Build row tuple
            row = (
                name,
                emp_id,
                date_str,
                status,
                first_login,
                last_logout,
                work_seconds,
                work_seconds,  # active_seconds
                sessions,
                calc_timestamp
            )
            current_batch_rows.append(row)

            if len(current_batch_rows) >= batch_size:
                current_batch_number += 1
                if current_batch_number > start_batch_idx:
                    yield current_batch_number, current_batch_rows
                current_batch_rows = []

    # Final partial batch if any
    if current_batch_rows:
        current_batch_number += 1
        if current_batch_number > start_batch_idx:
            yield current_batch_number, current_batch_rows

