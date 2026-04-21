"""Flask backend for Previous Year Question Papers website."""
import os
import re
from flask import Flask, request, jsonify, send_file, send_from_directory, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

import database as db

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.urandom(24)
app.url_map.strict_slashes = False
CORS(app, supports_credentials=True)

@app.after_request
def add_header(response):
    """Disable caching for all responses to prevent 304s."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

PDF_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdf")
os.makedirs(PDF_FOLDER, exist_ok=True)

# Admin credentials (demo)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@1234"

# Academic year format: 2023-24
YEAR_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def init_app():
    db.init_db()


# ---------- Auth helpers ----------
def check_admin_creds(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def is_admin_logged_in():
    return session.get("admin") is True


def require_admin():
    if is_admin_logged_in():
        return True
    data = request.get_json(silent=True) or request.form or {}
    uname = data.get("username")
    pwd = data.get("password")
    if check_admin_creds(uname, pwd):
        return True
    return False


# ---------- Student routes (public) ----------
@app.route("/")
def index():
    return send_from_directory("templates", "index.html")


@app.route("/login.html")
def login_page():
    return send_from_directory("templates", "login.html")


@app.route("/signup.html")
def signup_page():
    return send_from_directory("templates", "signup.html")


@app.route("/admin.html")
def admin_page():
    return send_from_directory("templates", "admin.html")


@app.route("/api/branches")
def get_branches():
    with db.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name FROM branches ORDER BY name")
        rows = c.fetchall()
    return jsonify([{"id": r["id"], "name": r["name"]} for r in rows])


@app.route("/api/semesters")
def get_semesters():
    with db.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, number FROM semesters ORDER BY number")
        rows = c.fetchall()
    return jsonify([{"id": r["id"], "number": r["number"]} for r in rows])


@app.route("/api/subjects")
def get_subjects():
    semester_id = request.args.get("semester_id")
    branch_id = request.args.get("branch_id")
    with db.get_db() as conn:
        c = conn.cursor()
        if semester_id:
            if branch_id:
                c.execute(
                    """SELECT MIN(id) as id, name FROM subjects 
                       WHERE (semester_id = ? AND (branch_id IS NULL OR branch_id = ?)) 
                       GROUP BY name ORDER BY name""",
                    (semester_id, branch_id),
                )
            else:
                c.execute(
                    "SELECT MIN(id) as id, name FROM subjects WHERE semester_id = ? GROUP BY name ORDER BY name",
                    (semester_id,),
                )
        else:
            c.execute(
                """SELECT MIN(id) as id, name, semester_id FROM subjects 
                   GROUP BY name, semester_id ORDER BY semester_id, name"""
            )
        rows = c.fetchall()
    return jsonify(
        [
            {
                "id": r["id"],
                "name": r["name"],
                "semester_id": r["semester_id"] if "semester_id" in r.keys() else None,
            }
            for r in rows
        ]
    )


@app.route("/api/years")
def get_years():
    """Return distinct academic years from uploaded papers."""
    with db.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT DISTINCT academic_year FROM question_papers ORDER BY academic_year DESC")
        rows = c.fetchall()
    years = [r["academic_year"] for r in rows if r["academic_year"]]
    if not years:
        years = ["2024-25", "2023-24", "2022-23", "2021-22"]
    return jsonify(years)


@app.route("/api/papers")
def get_papers():
    branch_id = request.args.get("branch_id")
    semester_id = request.args.get("semester_id")
    subject_id = request.args.get("subject_id")
    year = request.args.get("year")
    if not all([branch_id, semester_id, subject_id, year]):
        return jsonify([])
    with db.get_db() as conn:
        c = conn.cursor()
        # Find all subject ids with same name (handles duplicates)
        c.execute(
            "SELECT id FROM subjects WHERE name = (SELECT name FROM subjects WHERE id = ?) AND semester_id = ?",
            (subject_id, semester_id),
        )
        subject_ids = [r["id"] for r in c.fetchall()]
        if not subject_ids:
            return jsonify([])
        placeholders = ",".join("?" * len(subject_ids))
        c.execute(
            f"""
            SELECT qp.id, qp.academic_year, qp.file_path, qp.upload_date, qp.description,
                   b.name as branch_name, s.number as semester_num, sub.name as subject_name
            FROM question_papers qp
            JOIN branches b ON qp.branch_id = b.id
            JOIN semesters s ON qp.semester_id = s.id
            JOIN subjects sub ON qp.subject_id = sub.id
            WHERE qp.branch_id = ? AND qp.semester_id = ? AND qp.subject_id IN ({placeholders}) AND qp.academic_year = ?
            ORDER BY qp.upload_date DESC
            """,
            (branch_id, semester_id, *subject_ids, year),
        )
        rows = c.fetchall()
    return jsonify(
        [
            {
                "id": r["id"],
                "academic_year": r["academic_year"],
                "file_path": r["file_path"],
                "upload_date": r["upload_date"],
                "description": r["description"] or "",
                "branch_name": r["branch_name"],
                "semester_num": r["semester_num"],
                "subject_name": r["subject_name"],
            }
            for r in rows
        ]
    )


@app.route("/api/papers/download/<int:paper_id>")
def download_paper(paper_id):
    with db.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT file_path FROM question_papers WHERE id = ?", (paper_id,))
        row = c.fetchone()
    if not row:
        return jsonify({"error": "Paper not found"}), 404
    path = os.path.join(PDF_FOLDER, row["file_path"])
    if not os.path.isfile(path):
        return jsonify({"error": "File not found"}), 404
    return send_file(path, as_attachment=True, download_name=os.path.basename(row["file_path"]))


# ---------- Unified login (admin and user) ----------
@app.route("/api/login", methods=["POST"])
def login():
    """Single login for both admin and users. Uses username and password only."""
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    # Try admin first
    if check_admin_creds(username, password):
        session["admin"] = True
        return jsonify({"success": True, "role": "admin"})
    # Try user (username + password)
    with db.get_db() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, username, password, email, academic_year FROM users WHERE username = ?",
            (username,),
        )
        row = c.fetchone()
    if row and row.get("password") and check_password_hash(row["password"], password):
        return jsonify({
            "success": True,
            "role": "user",
            "user": {
                "id": row["id"],
                "username": row["username"],
                "email": row["email"],
                "academic_year": row["academic_year"],
            },
        })
    return jsonify({"error": "Invalid credentials"}), 401


# ---------- User signup (optional) ----------
@app.route("/api/user/signup", methods=["POST"])
def user_signup():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    email = data.get("email", "").strip()
    academic_year = data.get("academic_year", "")
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    pwd_hash = generate_password_hash(password)
    try:
        with db.get_db() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (username, password, email, academic_year) VALUES (?, ?, ?, ?)",
                (username, pwd_hash, email or None, academic_year or None),
            )
        return jsonify({"success": True})
    except Exception as e:
        if "UNIQUE" in str(e):
            return jsonify({"error": "Username or email already exists"}), 400
        return jsonify({"error": str(e)}), 500


@app.route("/api/user/login", methods=["POST"])
def user_login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    if not username:
        return jsonify({"error": "Username required"}), 400
    with db.get_db() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, username, email, academic_year FROM users WHERE username = ?",
            (username,),
        )
        row = c.fetchone()
    if not row:
        return jsonify({"error": "Invalid credentials"}), 401
    if email and row["email"] != email:
        return jsonify({"error": "Invalid credentials"}), 401
    return jsonify(
        {
            "success": True,
            "user": {
                "id": row["id"],
                "username": row["username"],
                "email": row["email"],
                "academic_year": row["academic_year"],
            },
        }
    )


# ---------- Admin routes ----------
@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json() or {}
    if not check_admin_creds(data.get("username", ""), data.get("password", "")):
        return jsonify({"error": "Invalid credentials"}), 401
    session["admin"] = True
    return jsonify({"success": True})


@app.route("/api/admin/check")
def admin_check():
    """Check if admin is logged in (for admin page load)."""
    return jsonify({"logged_in": is_admin_logged_in()})


@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin", None)
    return jsonify({"success": True})


@app.route("/api/admin/branches", methods=["GET", "POST"])
def admin_branches():
    if request.method == "GET":
        with db.get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT id, name FROM branches ORDER BY name")
            rows = c.fetchall()
        return jsonify([{"id": r["id"], "name": r["name"]} for r in rows])
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Branch name required"}), 400
    try:
        with db.get_db() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO branches (name) VALUES (?)", (name,))
        return jsonify({"success": True})
    except Exception as e:
        if "UNIQUE" in str(e):
            return jsonify({"error": "Branch already exists"}), 400
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/branches/<int:branch_id>", methods=["DELETE"])
def admin_delete_branch(branch_id):
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        with db.get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM question_papers WHERE branch_id = ? LIMIT 1", (branch_id,))
            if c.fetchone():
                return jsonify({"error": "Cannot delete: branch has question papers"}), 400
            c.execute("DELETE FROM branches WHERE id = ?", (branch_id,))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/semesters", methods=["GET", "POST"])
def admin_semesters():
    if request.method == "GET":
        with db.get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT id, number FROM semesters ORDER BY number")
            rows = c.fetchall()
        return jsonify([{"id": r["id"], "number": r["number"]} for r in rows])
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    num = data.get("number")
    if num is None or not (1 <= int(num) <= 8):
        return jsonify({"error": "Semester must be 1-8"}), 400
    try:
        with db.get_db() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO semesters (number) VALUES (?)", (int(num),))
        return jsonify({"success": True})
    except Exception as e:
        if "UNIQUE" in str(e):
            return jsonify({"error": "Semester already exists"}), 400
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/semesters/<int:semester_id>", methods=["DELETE"])
def admin_delete_semester(semester_id):
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        with db.get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM question_papers WHERE semester_id = ? LIMIT 1", (semester_id,))
            if c.fetchone():
                return jsonify({"error": "Cannot delete: semester has question papers"}), 400
            c.execute("DELETE FROM subjects WHERE semester_id = ?", (semester_id,))
            c.execute("DELETE FROM semesters WHERE id = ?", (semester_id,))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/subjects", methods=["GET", "POST"])
def admin_subjects():
    if request.method == "GET":
        semester_id = request.args.get("semester_id")
        with db.get_db() as conn:
            c = conn.cursor()
            if semester_id:
                c.execute(
                    "SELECT MIN(id) as id, name, semester_id, branch_id FROM subjects WHERE semester_id = ? GROUP BY name, branch_id ORDER BY name",
                    (semester_id,),
                )
            else:
                c.execute(
                    "SELECT MIN(id) as id, name, semester_id, branch_id FROM subjects GROUP BY name, semester_id, branch_id ORDER BY semester_id, name"
                )
            rows = c.fetchall()
        return jsonify(
            [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "semester_id": r["semester_id"],
                    "branch_id": r["branch_id"],
                }
                for r in rows
            ]
        )
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    semester_id = data.get("semester_id")
    branch_id = data.get("branch_id")
    if not name or not semester_id:
        return jsonify({"error": "Subject name and semester required"}), 400
    try:
        with db.get_db() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO subjects (name, semester_id, branch_id) VALUES (?, ?, ?)",
                (name, semester_id, branch_id or None),
            )
        return jsonify({"success": True})
    except Exception as e:
        if "UNIQUE" in str(e):
            return jsonify({"error": "Subject already exists for this semester"}), 400
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/subjects/<int:subject_id>", methods=["DELETE"])
def admin_delete_subject(subject_id):
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        with db.get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT name, semester_id FROM subjects WHERE id = ?", (subject_id,))
            row = c.fetchone()
            if not row:
                return jsonify({"error": "Subject not found"}), 404
            c.execute(
                "SELECT 1 FROM question_papers qp JOIN subjects s ON qp.subject_id = s.id WHERE s.name = ? AND s.semester_id = ? LIMIT 1",
                (row["name"], row["semester_id"]),
            )
            if c.fetchone():
                return jsonify({"error": "Cannot delete: subject has question papers"}), 400
            c.execute("DELETE FROM subjects WHERE name = ? AND semester_id = ?", (row["name"], row["semester_id"]))
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/papers", methods=["GET", "POST"])
def admin_papers():
    if request.method == "GET":
        with db.get_db() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT qp.id, qp.academic_year, qp.file_path, qp.upload_date, qp.description,
                       b.name as branch_name, s.number as semester_num, sub.name as subject_name
                FROM question_papers qp
                JOIN branches b ON qp.branch_id = b.id
                JOIN semesters s ON qp.semester_id = s.id
                JOIN subjects sub ON qp.subject_id = sub.id
                ORDER BY qp.upload_date DESC
                """
            )
            rows = c.fetchall()
        return jsonify(
            [
                {
                    "id": r["id"],
                    "academic_year": r["academic_year"],
                    "file_path": r["file_path"],
                    "upload_date": r["upload_date"],
                    "description": r["description"] or "",
                    "branch_name": r["branch_name"],
                    "semester_num": r["semester_num"],
                    "subject_name": r["subject_name"],
                }
                for r in rows
            ]
        )
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    branch_id = request.form.get("branch_id")
    semester_id = request.form.get("semester_id")
    subject_id = request.form.get("subject_id")
    academic_year = (request.form.get("academic_year") or "").strip()
    description = (request.form.get("description") or "").strip()
    file = request.files.get("file")
    if not all([branch_id, semester_id, subject_id, academic_year, file]):
        return jsonify({"error": "Branch, semester, subject, year and file required"}), 400
    if not YEAR_PATTERN.match(academic_year):
        return jsonify({"error": "Year must be format 2023-24"}), 400
    if file.filename == "" or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Valid PDF file required"}), 400
    with db.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM branches WHERE id = ?", (branch_id,))
        br = c.fetchone()
        c.execute("SELECT number FROM semesters WHERE id = ?", (semester_id,))
        sem = c.fetchone()
        c.execute("SELECT name FROM subjects WHERE id = ?", (subject_id,))
        sub = c.fetchone()
    if not br or not sem or not sub:
        return jsonify({"error": "Invalid branch/semester/subject"}), 400
    branch_slug = db.slugify(br["name"])
    sub_slug = db.slugify(sub["name"])
    filename = f"{branch_slug}_{sem['number']}_{sub_slug}_{academic_year}.pdf"
    filename = secure_filename(filename)
    filepath = os.path.join(PDF_FOLDER, filename)
    try:
        file.save(filepath)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    try:
        with db.get_db() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO question_papers (branch_id, semester_id, subject_id, academic_year, file_path, description) VALUES (?, ?, ?, ?, ?, ?)",
                (branch_id, semester_id, subject_id, academic_year, filename, description or None),
            )
        return jsonify({"success": True, "file_path": filename})
    except Exception as e:
        if os.path.isfile(filepath):
            os.remove(filepath)
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/papers/<int:paper_id>", methods=["DELETE"])
def admin_delete_paper(paper_id):
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 401
    with db.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT file_path FROM question_papers WHERE id = ?", (paper_id,))
        row = c.fetchone()
    if not row:
        return jsonify({"error": "Paper not found"}), 404
    path = os.path.join(PDF_FOLDER, row["file_path"])
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass
    with db.get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM question_papers WHERE id = ?", (paper_id,))
    return jsonify({"success": True})


if __name__ == "__main__":
    init_app()
    app.run(debug=True, port=5000)
