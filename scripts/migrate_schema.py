import pymysql

conn = pymysql.connect(host='127.0.0.1', user='root', password='root', database='employee360')
cur = conn.cursor()

def add_col_if_not_exists(table, col, col_def):
    cur.execute(f"SHOW COLUMNS FROM `{table}` LIKE '{col}'")
    if not cur.fetchone():
        print(f"Adding {col} to {table}...")
        cur.execute(f"ALTER TABLE `{table}` ADD COLUMN `{col}` {col_def}")
        conn.commit()
    else:
        print(f"{table}.{col} already exists.")

# 1. tabEmployee Activity Log
add_col_if_not_exists('tabEmployee Activity Log', 'is_regularized', 'TINYINT(1) NOT NULL DEFAULT 0')
add_col_if_not_exists('tabEmployee Activity Log', 'regularization_exception', 'VARCHAR(140) DEFAULT NULL')

# 2. tabAttendance Exception
add_col_if_not_exists('tabAttendance Exception', 'original_status', 'VARCHAR(50) DEFAULT NULL')
add_col_if_not_exists('tabAttendance Exception', 'requested_status', 'VARCHAR(50) DEFAULT NULL')
add_col_if_not_exists('tabAttendance Exception', 'requested_in_time', 'TIME DEFAULT NULL')
add_col_if_not_exists('tabAttendance Exception', 'requested_out_time', 'TIME DEFAULT NULL')

# 3. tabLeave Application
add_col_if_not_exists('tabLeave Application', 'total_leave_days', 'DECIMAL(5,2) DEFAULT 1.00')

# 4. tabRole
cur.execute("""
CREATE TABLE IF NOT EXISTS `tabRole` (
  `name` VARCHAR(140) NOT NULL PRIMARY KEY,
  `creation` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
  `modified` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `modified_by` VARCHAR(140) DEFAULT 'Administrator',
  `owner` VARCHAR(140) DEFAULT 'Administrator',
  `docstatus` INT(1) NOT NULL DEFAULT 0,
  `role_name` VARCHAR(140) NOT NULL UNIQUE,
  `disabled` INT(1) NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
""")
for r in ['CEO', 'Manager', 'Employee', 'System Manager', 'Administrator']:
    cur.execute("INSERT IGNORE INTO `tabRole` (name, role_name) VALUES (%s, %s)", (r, r))
conn.commit()
print("tabRole initialized and seeded.")

cur.close()
conn.close()
print("Schema migration complete!")

