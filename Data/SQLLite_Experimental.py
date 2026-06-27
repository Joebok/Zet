import sqlite3

# Connect to a database file (creates it if it doesn't exist)
conn = sqlite3.connect("test_database.db")

# Create a cursor object to execute SQL commands
cursor = conn.cursor()

# Create a table for project tasks
cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'Pending'
)
""")
conn.commit()  # Save changes to the database

task_title = "Write project documentation"

# Use a question mark placeholder for safety
cursor.execute("INSERT INTO tasks (title) VALUES (?)", (task_title,))
conn.commit()

# Query all tasks
cursor.execute("SELECT * FROM tasks")
all_tasks = cursor.fetchall()

for row in all_tasks:
    print(f"Task ID: {row[0]}, Title: {row[1]}, Status: {row[2]}")

# Update task status
cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", ("Completed", 1))

# Delete a task
cursor.execute("DELETE FROM tasks WHERE id = ?", (1,))

conn.commit()

cursor.close()
conn.close()

# The 'with' block manages the transaction automatically
with sqlite3.connect("project_database.db") as conn:
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (title) VALUES (?)", ("Clean up code",))
    # No manual conn.commit() needed here!

# Remember to close the connection when completely done with the application
conn.close()
