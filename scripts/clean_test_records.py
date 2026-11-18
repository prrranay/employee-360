import sys
import os
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)
import frappe_runtime
frappe_runtime.install_frappe_compat()
import frappe

frappe.db.sql("""
    DELETE FROM `tabEmployee Activity Log` 
    WHERE activity_date > '2026-11-16' OR activity_date < '2025-11-17';
""")
frappe.db.sql("""
    DELETE FROM `tabEmployee Checkin` 
    WHERE DATE(time) > '2026-11-16' OR source = 'Admin Correction';
""")
try:
    frappe.db.sql("""
        DELETE FROM `tabAttendance Exception` 
        WHERE activity_date > '2026-11-16' OR description LIKE '%Security Audit%' OR description LIKE '%Regularization requested%';
    """)
except Exception:
    pass

frappe.db.sql("""
    DELETE FROM `tabLeave Application` 
    WHERE name LIKE 'LEAV-TEST-%';
""")
frappe.db.commit()

count = frappe.db.sql("SELECT COUNT(*) FROM `tabEmployee Activity Log`")[0][0]
print(f"Cleanup finished! Current total rows in tabEmployee Activity Log: {count:,}")
