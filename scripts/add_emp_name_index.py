import pymysql

conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='employee360')
cur = conn.cursor()
try:
    cur.execute("CREATE INDEX idx_emp_name ON `tabEmployee` (employee_name);")
    conn.commit()
    print("Created index idx_emp_name")
except pymysql.err.OperationalError as e:
    if "Duplicate key name" in str(e):
        print("idx_emp_name already exists")
    else:
        raise

# Now explain the autocomplete query
cur = conn.cursor(pymysql.cursors.DictCursor)
cur.execute("""
    EXPLAIN SELECT name, employee_name, department 
    FROM `tabEmployee` 
    WHERE employee_name LIKE 'Elena%' OR employee_id LIKE 'EMP-013%' 
    LIMIT 10
""")
for r in cur.fetchall():
    print("EXPLAIN with idx_emp_name:", r)

