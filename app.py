
print("Starting Flask app...")

from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from datetime import date
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Needed for flash messages & session
app.secret_key = "some_secret_key_for_flask_session"

DB_NAME = "students.db"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- AUTH HELPERS ----------

def require_login():
    if "teacher_id" not in session:
        flash("Please login as a teacher to continue.", "danger")
        return False
    return True


def current_department():
    return session.get("teacher_department")


# ---------- ROUTES ----------

@app.route("/")
def root():
    return redirect(url_for("home"))


# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        teacher = conn.execute(
            "SELECT * FROM teachers WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if teacher and check_password_hash(teacher["password_hash"], password):
            session["teacher_id"] = teacher["id"]
            session["teacher_name"] = teacher["name"]
            session["teacher_department"] = teacher["department"]
            flash("Login successful.", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register_teacher():
    # Simple protection so random users can't register
    SECRET_CODE = "admin123"   # you can change this

    if request.method == "POST":
        form = request.form

        username = form.get("username", "").strip()
        password = form.get("password", "").strip()
        name = form.get("name", "").strip()
        department = form.get("department", "").strip()
        code = form.get("code", "").strip()

        # Basic validation
        if not (username and password and name and department and code):
            flash("Please fill all fields.", "danger")
            return redirect(url_for("register_teacher"))

        if code != SECRET_CODE:
            flash("Invalid admin code. You are not allowed to register teachers.", "danger")
            return redirect(url_for("register_teacher"))

        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash(password)

        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO teachers (username, password_hash, name, department)
                VALUES (?, ?, ?, ?)
                """,
                (username, password_hash, name, department),
            )
            conn.commit()
            flash("Teacher registered successfully. You can now log in.", "success")
        except sqlite3.IntegrityError:
            flash("Username already exists. Choose another.", "danger")
        finally:
            conn.close()

        return redirect(url_for("login"))

    return render_template("register_teacher.html")




# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


# Home page with stats (department-wise)
@app.route("/home")
def home():
    if not require_login():
        return redirect(url_for("login"))

    department = current_department()

    conn = get_db_connection()
    students_rows = conn.execute(
        "SELECT * FROM students WHERE department = ? ORDER BY roll_no",
        (department,)
    ).fetchall()

    today = date.today().isoformat()

    # check if attendance for today exists for this department
    row = conn.execute(
        """
        SELECT COUNT(*) as c
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date = ? AND s.department = ?
        """,
        (today, department),
    ).fetchone()
    today_marked = (row["c"] > 0)

    total_students = len(students_rows)

    # total attendance records for this department
    summary_row = conn.execute(
        """
        SELECT COUNT(*) as c
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE s.department = ?
        """,
        (department,),
    ).fetchone()
    total_attendance_records = summary_row["c"] if summary_row else 0

    # calculate today's class attendance percentage
    present_row = conn.execute(
        """
        SELECT COUNT(*) as c
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.date = ? AND s.department = ? AND a.status = 'Present'
        """,
        (today, department),
    ).fetchone()
    present_today = present_row["c"] if present_row else 0

    if total_students > 0 and today_marked:
        class_attendance_percent = round(present_today / total_students * 100, 1)
    else:
        class_attendance_percent = 0

    conn.close()
    return render_template(
        "home.html",
        students=students_rows,
        today_marked=today_marked,
        total_students=total_students,
        total_attendance_records=total_attendance_records,
        class_attendance_percent=class_attendance_percent,
    )



# Students listing + search (department-wise)
@app.route("/students")
def students():
    if not require_login():
        return redirect(url_for("login"))

    # Search text and selected course from URL
    q = request.args.get("q", "").strip()
    selected_course = request.args.get("course", "").strip()

    conn = get_db_connection()

    # Get distinct course list for dropdown
    course_rows = conn.execute(
        "SELECT DISTINCT course FROM students ORDER BY course"
    ).fetchall()
    courses = [r["course"] for r in course_rows]

    # Build query based on filters
    if selected_course and q:
        like = f"%{q}%"
        students_rows = conn.execute(
            """
            SELECT * FROM students
            WHERE course = ?
              AND (roll_no LIKE ? OR name LIKE ? OR course LIKE ?)
            ORDER BY course, roll_no
            """,
            (selected_course, like, like, like),
        ).fetchall()
    elif selected_course:
        students_rows = conn.execute(
            """
            SELECT * FROM students
            WHERE course = ?
            ORDER BY course, roll_no
            """,
            (selected_course,),
        ).fetchall()
    elif q:
        like = f"%{q}%"
        students_rows = conn.execute(
            """
            SELECT * FROM students
            WHERE roll_no LIKE ? OR name LIKE ? OR course LIKE ?
            ORDER BY course, roll_no
            """,
            (like, like, like),
        ).fetchall()
    else:
        students_rows = conn.execute(
            """
            SELECT * FROM students
            ORDER BY course, roll_no
            """,
        ).fetchall()

    conn.close()
    return render_template(
        "index.html",
        students=students_rows,
        q=q,
        courses=courses,
        selected_course=selected_course,
    )



# Add student (assigned to current teacher's department)
@app.route("/add", methods=["GET", "POST"])
def add_student():
    if not require_login():
        return redirect(url_for("login"))

    department = current_department()  # teacher's department

    if request.method == "POST":
        form = request.form

        roll_no = form.get("roll_no", "").strip()
        name = form.get("name", "").strip()
        email = form.get("email", "").strip()
        course = form.get("course", "").strip()
        semester = form.get("semester", "").strip()
        phone = form.get("phone", "").strip()

        if not roll_no or not name:
            flash("Roll No and Name are required.", "danger")
            return redirect(url_for("add_student"))

        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO students
            (roll_no, name, email, course, semester, phone, department)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (roll_no, name, email, course, semester, phone, department),
        )
        conn.commit()
        conn.close()

        flash("Student added successfully.", "success")
        return redirect(url_for("students"))

    # GET: show form
    return render_template("add_student.html")



# Edit student (ensure same department)
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_student(id):
    if not require_login():
        return redirect(url_for("login"))

    department = current_department()
    conn = get_db_connection()
    student = conn.execute(
        "SELECT * FROM students WHERE id = ? AND department = ?",
        (id, department),
    ).fetchone()

    if not student:
        conn.close()
        return "Student not found or not in your department.", 404

    if request.method == "POST":
        roll_no = request.form["roll_no"]
        name = request.form["name"]
        email = request.form["email"]
        course = request.form["course"]
        semester = request.form["semester"]
        phone = request.form["phone"]

        conn.execute(
            """
            UPDATE students
            SET roll_no = ?, name = ?, email = ?, course = ?, semester = ?, phone = ?
            WHERE id = ? AND department = ?
            """,
            (roll_no, name, email, course, semester, phone, id, department),
        )
        conn.commit()
        conn.close()

        flash("Student details updated successfully.", "success")
        return redirect(url_for("students"))

    conn.close()
    return render_template("edit_student.html", student=student)

@app.route("/students/<int:id>/set_login", methods=["GET", "POST"])
def set_student_login(id):
    if not require_login():
        return redirect(url_for("login"))

    department = current_department()
    conn = get_db_connection()
    student = conn.execute(
        "SELECT * FROM students WHERE id = ? AND department = ?",
        (id, department),
    ).fetchone()

    if not student:
        conn.close()
        return "Student not found or not in your department.", 404

    if request.method == "POST":
        username = request.form.get("student_username", "").strip()
        password = request.form.get("student_password", "").strip()

        if not username or not password:
            flash("Username and password are required.", "danger")
            conn.close()
            return redirect(url_for("set_student_login", id=id))

        password_hash = generate_password_hash(password)

        conn.execute(
            """
            UPDATE students
            SET student_username = ?, student_password_hash = ?
            WHERE id = ? AND department = ?
            """,
            (username, password_hash, id, department),
        )
        conn.commit()
        conn.close()

        flash("Student login credentials set successfully.", "success")
        return redirect(url_for("students"))

    conn.close()
    return render_template("set_student_login.html", student=student)

@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db_connection()
        student = conn.execute(
            "SELECT * FROM students WHERE student_username = ?",
            (username,),
        ).fetchone()
        conn.close()

        if student and student["student_password_hash"]:
            if check_password_hash(student["student_password_hash"], password):
                # set student session
                session["student_id"] = student["id"]
                session["student_name"] = student["name"]
                session["student_roll_no"] = student["roll_no"]
                flash("Student login successful.", "success")
                return redirect(url_for("student_dashboard"))
        
        flash("Invalid username or password.", "danger")

    return render_template("student_login.html")

@app.route("/student/logout")
def student_logout():
    session.pop("student_id", None)
    session.pop("student_name", None)
    session.pop("student_roll_no", None)
    flash("Student logged out.", "success")
    return redirect(url_for("student_login"))

@app.route("/student/dashboard")
def student_dashboard():
    student_id = session.get("student_id")
    if not student_id:
        flash("Please login as student.", "danger")
        return redirect(url_for("student_login"))

    conn = get_db_connection()
    student = conn.execute(
        "SELECT * FROM students WHERE id = ?",
        (student_id,),
    ).fetchone()

    if not student:
        conn.close()
        flash("Student not found.", "danger")
        return redirect(url_for("student_login"))

    records = conn.execute(
        """
        SELECT date, status
        FROM attendance
        WHERE student_id = ?
        ORDER BY date DESC
        """,
        (student_id,),
    ).fetchall()
    conn.close()

    total = len(records)
    presents = sum(1 for r in records if r["status"] == "Present")
    absents = sum(1 for r in records if r["status"] == "Absent")
    percent = (presents / total * 100) if total > 0 else 0

    return render_template(
        "student_dashboard.html",
        student=student,
        records=records,
        total=total,
        presents=presents,
        absents=absents,
        percent=round(percent, 1),
    )



# Delete student (department-safe)
@app.route("/delete/<int:id>", methods=["POST"])
def delete_student(id):
    if not require_login():
        return redirect(url_for("login"))

    department = current_department()
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM students WHERE id = ? AND department = ?",
        (id, department),
    )
    conn.commit()
    conn.close()

    flash("Student deleted successfully.", "success")
    return redirect(url_for("students"))


# Mark attendance (only department students)
@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    if not require_login():
        return redirect(url_for("login"))

    conn = get_db_connection()

    # list of all distinct courses for dropdown
    courses = [row["course"] for row in conn.execute(
        "SELECT DISTINCT course FROM students ORDER BY course"
    ).fetchall()]

    # which course is selected? (works for GET and POST)
    selected_course = request.values.get("course", "")

    # choose students based on selected course
    if selected_course:
        students = conn.execute(
            "SELECT * FROM students WHERE course = ? ORDER BY roll_no",
            (selected_course,),
        ).fetchall()
    else:
        # default: show no students until a course is chosen
        students = []

    if request.method == "POST":
        date_str = request.form["date"]
        present_ids = request.form.getlist("present_ids")  # list of ids as strings

        # Remove old records for this date (for these students)
        if selected_course:
            # delete attendance for this course and date
            conn.execute(
                """
                DELETE FROM attendance
                WHERE date = ?
                  AND student_id IN (
                      SELECT id FROM students WHERE course = ?
                  )
                """,
                (date_str, selected_course),
            )
        else:
            conn.execute("DELETE FROM attendance WHERE date = ?", (date_str,))

        for s in students:
            sid = str(s["id"])
            status = "Present" if sid in present_ids else "Absent"
            conn.execute(
                "INSERT INTO attendance (student_id, date, status) VALUES (?, ?, ?)",
                (s["id"], date_str, status),
            )

        conn.commit()
        conn.close()
        flash(f"Attendance saved for {date_str} ({selected_course or 'All courses'})", "success")
        return redirect(url_for("attendance"))

    today = date.today().isoformat()
    conn.close()
    return render_template(
        "attendance.html",
        students=students,
        today=today,
        courses=courses,
        selected_course=selected_course,
    )



# Per-student attendance details (within department)
@app.route("/students/<int:id>/attendance")
def student_attendance(id):
    if not require_login():
        return redirect(url_for("login"))

    department = current_department()
    conn = get_db_connection()
    student = conn.execute(
        "SELECT * FROM students WHERE id = ? AND department = ?",
        (id, department),
    ).fetchone()
    if not student:
        conn.close()
        return "Student not found or not in your department.", 404

    records = conn.execute(
        """
        SELECT date, status
        FROM attendance
        WHERE student_id = ?
        ORDER BY date DESC
        """,
        (id,),
    ).fetchall()

    total = len(records)
    presents = sum(1 for r in records if r["status"] == "Present")
    absents = sum(1 for r in records if r["status"] == "Absent")
    percent = (presents / total * 100) if total > 0 else 0

    conn.close()

    return render_template(
        "student_attendance.html",
        student=student,
        records=records,
        total=total,
        presents=presents,
        absents=absents,
        percent=round(percent, 1),
    )


# Attendance by date (department-wise)
@app.route("/attendance/by-date")
def attendance_by_date():
    if not require_login():
        return redirect(url_for("login"))

    department = current_department()
    date_str = request.args.get("date")
    if not date_str:
        date_str = date.today().isoformat()

    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT s.roll_no, s.name, a.status
        FROM students s
        LEFT JOIN attendance a
          ON a.student_id = s.id AND a.date = ?
        WHERE s.department = ?
        ORDER BY s.roll_no
        """,
        (date_str, department),
    ).fetchall()
    conn.close()

    records = []
    present_count = 0
    absent_count = 0
    not_marked = 0

    for r in rows:
        status = r["status"]
        if status == "Present":
            present_count += 1
        elif status == "Absent":
            absent_count += 1
        else:
            not_marked += 1
            status = "Not Marked"

        records.append(
            {
                "roll_no": r["roll_no"],
                "name": r["name"],
                "status": status,
            }
        )

    return render_template(
        "attendance_by_date.html",
        date_str=date_str,
        records=records,
        present_count=present_count,
        absent_count=absent_count,
        not_marked=not_marked,
    )


# Attendance summary (department-wise)
@app.route("/attendance/summary")
def attendance_summary():
    if not require_login():
        return redirect(url_for("login"))

    department = current_department()
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT s.id,
               s.roll_no,
               s.name,
               SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS presents,
               SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END)  AS absents,
               COUNT(a.id) AS total_days
        FROM students s
        LEFT JOIN attendance a ON a.student_id = s.id
        WHERE s.department = ?
        GROUP BY s.id, s.roll_no, s.name
        ORDER BY s.roll_no;
        """,
        (department,),
    ).fetchall()
    conn.close()

    summary = []
    low_students = []

    for r in rows:
        total = r["total_days"] or 0
        presents = r["presents"] or 0
        absents = r["absents"] or 0
        percent = (presents / total * 100) if total > 0 else 0

        # Decide Category
        if total == 0:
            category = "No Data"
        elif percent >= 90:
            category = "Excellent"
        elif percent >= 75:
            category = "Good"
        else:
            category = "Needs Improvement"

        entry = {
            "roll_no": r["roll_no"],
            "name": r["name"],
            "presents": presents,
            "absents": absents,
            "total": total,
            "percent": round(percent, 1),
            "category": category,
        }
        summary.append(entry)

        # Collect Low Attendance Students (<75%)
        if total > 0 and percent < 75:
            low_students.append(entry)

    return render_template(
        "attendance_summary.html",
        summary=summary,
        low_students=low_students
    )


if __name__ == "__main__":
    print("Running Flask development server...")
    app.run(debug=True)
