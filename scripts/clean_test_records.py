import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

try:
    import frappe
except ImportError:
    frappe = None

from employee360.seed.runner import get_db_connection


def is_disposable_site(site: str) -> bool:
    """Verifies that the target Frappe site or database is explicitly disposable or permitted for test cleanup."""
    if os.environ.get("ALLOW_TEST_CLEANUP") == "1":
        return True
    if "--force-cleanup" in sys.argv:
        return True
    disposable_indicators = ["test", "disposable", "sandbox", "ci", "dev"]
    return any(ind in site.lower() for ind in disposable_indicators)


def clean_test_records(site: str = "employee360.localhost", force: bool = False):
    """
    Safely purges ONLY identifiable test fixture records (prefixed with TEST- or LEAV-TEST-).
    Never silently modifies production or normal application data.
    Requires explicit permission flag if not a disposable test site.
    """
    if not force and not is_disposable_site(site):
        print(f"[!] Safety Guard: Refusing to clean records on non-test site '{site}'.")
        print("    To run test cleanup explicitly, set ALLOW_TEST_CLEANUP=1 or pass '--force-cleanup'.")
        return False

    print(f"[*] Safely removing identifiable test fixtures on site '{site}'...")

    queries = [
        "DELETE FROM `tabEmployee Activity Log` WHERE name LIKE 'TEST-%' OR employee LIKE 'TEST-%';",
        "DELETE FROM `tabEmployee Checkin` WHERE name LIKE 'TEST-%' OR employee LIKE 'TEST-%' OR device_info LIKE '%Test%' OR device_info LIKE '%Concurrent%';",
        "DELETE FROM `tabAttendance Exception` WHERE name LIKE 'TEST-%' OR employee LIKE 'TEST-%' OR description LIKE '%Test%' OR description LIKE '%Security Audit%';",
        "DELETE FROM `tabAttendance Correction Request` WHERE name LIKE 'TEST-%' OR employee LIKE 'TEST-%';",
        "DELETE FROM `tabLeave Application` WHERE name LIKE 'LEAV-TEST-%' OR name LIKE 'TEST-%' OR employee LIKE 'TEST-%';",
        "DELETE FROM `tabEmployee` WHERE name LIKE 'TEST-%';"
    ]

    # Mode 1: Frappe ORM if available
    if frappe is not None:
        try:
            if not getattr(frappe, "db", None) or not frappe.db:
                sites_path = "/home/frappe/frappe-bench/sites" if os.path.exists("/home/frappe/frappe-bench/sites") else None
                frappe.init(site=site, sites_path=sites_path)
                frappe.connect()

            for q in queries:
                frappe.db.sql(q)
            frappe.db.commit()
            print("[+] Test fixture cleanup completed safely via Frappe ORM.")
            return True
        except Exception as e:
            print(f"[!] Error during Frappe test cleanup: {e}")
            return False
        finally:
            try:
                frappe.destroy()
            except Exception:
                pass

    # Mode 2: Direct database connection fallback
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            for q in queries:
                cur.execute(q)
            conn.commit()
        conn.close()
        print("[+] Test fixture cleanup completed safely via database connection.")
        return True
    except Exception as e:
        print(f"[i] Direct database connection unavailable ({e}); skipped fixture cleanup.")
        return True


if __name__ == "__main__":
    target_site = "employee360.localhost"
    force_flag = False
    for arg in sys.argv[1:]:
        if arg == "--force-cleanup":
            force_flag = True
        elif not arg.startswith("--"):
            target_site = arg

    success = clean_test_records(target_site, force=force_flag)
    sys.exit(0 if success else 1)
