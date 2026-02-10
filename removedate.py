import sqlite3

con = sqlite3.connect("task.db")
cur = con.cursor()

# Create new table WITHOUT task_date
cur.execute("""
CREATE TABLE IF NOT EXISTS dailys_task_new(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    taskname TEXT,
    description TEXT,
    task_time TEXT
)
""")

# Copy only needed columns
cur.execute("""
INSERT INTO dailys_task_new (id, email, taskname, description, task_time)
SELECT id, email, taskname, description, task_time
FROM dailys_task
""")

# Remove old table
cur.execute("DROP TABLE dailys_task")

# Rename new table
cur.execute("ALTER TABLE dailys_task_new RENAME TO dailys_task")

con.commit()
con.close()

print("task_date column removed from dailys_task")