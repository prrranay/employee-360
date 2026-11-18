import os
import sys
import pymysql

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from employee360.seed.runner import get_db_connection

def reset_database(force: bool = False):
    """
    Safely resets development/test database tables.
    Never runs in production.
    """
    if not force and "--force-dev-reset" not in sys.argv and os.environ.get("ALLOW_DEV_RESET") != "1":
        print("[!] Safety Block: Database reset requires '--force-dev-reset' or ALLOW_DEV_RESET=1")
        print("    This prevents accidental deletion of non-disposable environments.")
        sys.exit(1)

    print("[*] Performing safe development database reset...")
    conn = get_db_connection()
    cursor = conn.cursor()

    tables = [
        "tabAttendance Exception",
        "tabLeave Application",
        "tabEmployee Checkin",
        "tabEmployee Activity Log",
        "tabEmployee",
        "tabShift",
        "tabSeed Checkpoint"
    ]

    try:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        for table in tables:
            print(f"    -> Truncating `{table}`...")
            cursor.execute(f"TRUNCATE TABLE `{table}`;")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        conn.commit()
        print("[+] Development database reset successfully.")
    except Exception as e:
        conn.rollback()
        print(f"[!] Error resetting database: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    reset_database()

