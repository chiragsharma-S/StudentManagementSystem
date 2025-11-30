
print("Testing execution...")

import sqlite3

DB_NAME = "students.db"

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

# Students table with department
cur.execute("""
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT,
    course TEXT,
    semester INTEGER,
    phone TEXT,
    department TEXT NOT NULL
);
""")

# Attendance table (same as before)
cur.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id)
);
""")

# Teachers table
cur.execute("""
CREATE TABLE IF NOT EXISTS teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    department TEXT NOT NULL
);
""")

conn.commit()
conn.close()

print("Database and tables created successfully.")
