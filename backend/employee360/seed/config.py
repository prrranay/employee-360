import datetime

class SeedConfig:
    # Scale targets
    TOTAL_EMPLOYEES: int = 30000
    DAYS_PER_EMPLOYEE: int = 365
    TOTAL_ACTIVITY_RECORDS: int = 10950000  # 30,000 * 365

    # Batching & Performance
    BATCH_SIZE: int = 25000          # Records per transaction
    SQL_CHUNK_SIZE: int = 5000       # Records per multi-value INSERT statement
    RANDOM_SEED: int = 42

    # Date range: 365 days ending yesterday (2026-11-16)
    END_DATE: datetime.date = datetime.date(2026, 11, 16)
    START_DATE: datetime.date = END_DATE - datetime.timedelta(days=DAYS_PER_EMPLOYEE - 1)  # 2025-11-17

    # Departments and weights
    DEPARTMENTS = [
        "Engineering",
        "Product",
        "Sales",
        "Marketing",
        "Customer Success",
        "Finance",
        "Human Resources",
        "Operations",
        "IT Support",
        "Legal"
    ]

    DESIGNATIONS_BY_LEVEL = {
        "VP": ["VP of Engineering", "VP of Sales", "VP of Product", "VP of Marketing", "VP of Finance"],
        "Director": ["Director of Engineering", "Director of Sales", "Director of Product", "Director of HR"],
        "Manager": ["Engineering Manager", "Sales Manager", "Product Manager", "Operations Manager", "Finance Manager"],
        "Lead": ["Team Lead", "Tech Lead", "Lead Account Executive", "Lead Designer"],
        "IC": ["Senior Software Engineer", "Software Engineer", "Frontend Developer", "Backend Developer", 
               "DevOps Engineer", "Account Executive", "Financial Analyst", "HR Specialist", "Support Specialist"]
    }

    # Demo accounts required for role verification
    DEMO_USERS = [
        {
            "email": "ceo@employee360.local",
            "name": "Alex Mercer",
            "role": "CEO",
            "employee_id": "EMP-00001",
            "department": "Executive",
            "designation": "Chief Executive Officer"
        },
        {
            "email": "manager1@employee360.local",
            "name": "Sarah Connor",
            "role": "Manager",
            "employee_id": "EMP-00012",
            "department": "Engineering",
            "designation": "Engineering Manager"
        },
        {
            "email": "manager2@employee360.local",
            "name": "David Miller",
            "role": "Manager",
            "employee_id": "EMP-00013",
            "department": "Sales",
            "designation": "Sales Manager"
        },
        {
            "email": "emp1@employee360.local",
            "name": "Elena Rostova",
            "role": "Employee",
            "employee_id": "EMP-01362",
            "department": "Engineering",
            "designation": "Senior Software Engineer"
        },
        {
            "email": "emp2@employee360.local",
            "name": "Marcus Vance",
            "role": "Employee",
            "employee_id": "EMP-01363",
            "department": "Engineering",
            "designation": "Frontend Developer"
        },
        {
            "email": "emp3@employee360.local",
            "name": "Priya Sharma",
            "role": "Employee",
            "employee_id": "EMP-01364",
            "department": "Sales",
            "designation": "Account Executive"
        }
    ]

    # Holiday dates within the 365-day seed window
    HOLIDAYS = {
        datetime.date(2025, 11, 27): "Thanksgiving Day",
        datetime.date(2025, 12, 25): "Christmas Day",
        datetime.date(2026, 1, 1): "New Year's Day",
        datetime.date(2026, 1, 19): "Martin Luther King Jr. Day",
        datetime.date(2026, 2, 16): "Presidents' Day",
        datetime.date(2026, 5, 25): "Memorial Day",
        datetime.date(2026, 6, 19): "Juneteenth",
        datetime.date(2026, 7, 4): "Independence Day",
        datetime.date(2026, 9, 7): "Labor Day",
        datetime.date(2026, 10, 12): "Columbus Day"
    }

