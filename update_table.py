import sqlite3

con = sqlite3.connect("task.db")
cur = con.cursor()

try:
    cur.execute("ALTER TABLE adds__task ADD COLUMN est_hours INTEGER DEFAULT 1;")
    print("Column est_hours added successfully ✅")
except Exception as e:
    print("Maybe column already exists:", e)

con.commit()
con.close()