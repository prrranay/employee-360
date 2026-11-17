import pymysql

conn = pymysql.connect(
    host='127.0.0.1', port=3306, user='root', password='root', database='employee360',
    cursorclass=pymysql.cursors.DictCursor
)
cur = conn.cursor()
cur.execute("""
    SELECT name, employee_name, department, designation 
    FROM `tabEmployee` 
    WHERE manager = 'EMP-00001'
    ORDER BY department;
""")
rows = cur.fetchall()
print(f"Total direct reports under CEO: {len(rows)}")
for r in rows:
    print(r)
conn.close()
