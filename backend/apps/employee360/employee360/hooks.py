app_name = "employee360"
app_title = "Employee360"
app_publisher = "Employee360 Team"
app_description = "Production-scale Employee360 platform supporting 30,000 employees and 10.95M daily summaries"
app_email = "admin@employee360.local"
app_license = "MIT"

# Document Events
doc_events = {
    "Employee Checkin": {
        "on_update": "employee360.employee360.doctype.employee_checkin.employee_checkin.EmployeeCheckin.trigger_daily_summary_recalculation"
    }
}

# Scheduled Tasks / Background Jobs
scheduler_events = {
    "daily": [
        "employee360.tasks.recalculate_unclosed_sessions"
    ]
}

# Fixtures for Roles
fixtures = [
    {
        "doctype": "Role",
        "filters": [["name", "in", ["CEO", "Manager", "Employee"]]]
    }
]

