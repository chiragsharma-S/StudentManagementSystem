import sqlite3
from werkzeug.security import generate_password_hash

DB_NAME = "students.db"

username = "bca_teacher"      # you can change
password = "123456"           # login password
name = "BCA Department Teacher"
department = "BCA"            # must match student department

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

password_hash = generate_password_hash(password)

cur.execute("""
INSERT INTO teachers (username, password_hash, name, department)
VALUES (?, ?, ?, ?)
""", (username, password_hash, name, department))

conn.commit()
conn.close()

print("Teacher created successfully.")
