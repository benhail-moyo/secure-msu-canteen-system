import sqlite3
conn = sqlite3.connect('instance/canteen.db')
c = conn.cursor()
c.execute('PRAGMA table_info(students)')
rows = c.fetchall()
print(rows)
conn.close()
