import sys
import os
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
APP_DIR = os.path.join(BACKEND_DIR, "apps", "employee360")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, APP_DIR)
import frappe_bridge
frappe_bridge.install_frappe_compat()
import frappe

frappe.db.sql("""
    DELETE FROM `tabEmployee Activity Log` 
    WHERE activity_date > '2026-11-16' OR activity_date < '2025-11-17';
""")
frappe.db.sql("""
    DELETE FROM `tabEmployee Checkin` 
    WHERE DATE(time) > '2026-11-16';
""")
try:
    frappe.db.sql("""
        DELETE FROM `tabAttendance Exception` 
        WHERE activity_date > '2026-11-16';
    """)
except Exception:
    pass

frappe.db.sql("""
    DELETE FROM `tabLeave Application` 
    WHERE name LIKE 'LEAV-TEST-%';
""")

count = frappe.db.sql("SELECT COUNT(*) FROM `tabEmployee Activity Log`")[0][0]
print(f"Cleanup finished! Current total rows in tabEmployee Activity Log: {count:,}")
