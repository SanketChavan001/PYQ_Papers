"""Database setup and helpers for Previous Year Question Papers."""
import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "question_papers.db")

# Dummy subjects by semester (common across branches for demo)
SEMESTER_SUBJECTS = {
    1: ["Engineering Mathematics-I", "Engineering Physics", "Engineering Chemistry", "Basic Electrical Engineering", "Programming in C"],
    2: ["Engineering Mathematics-II", "Engineering Mechanics", "Data Structures", "Digital Electronics", "Object Oriented Programming"],
    3: ["Engineering Mathematics-III", "Data Structures and Algorithms", "Database Management Systems", "Computer Networks", "Operating Systems"],
    4: ["Discrete Mathematics", "Theory of Computation", "Software Engineering", "Computer Organization", "Web Technologies"],
    5: ["Machine Learning", "Artificial Intelligence", "Compiler Design", "Computer Graphics", "Microprocessors"],
    6: ["Data Science", "Cyber Security", "Cloud Computing", "Mobile Computing", "Design Patterns"],
    7: ["Big Data Analytics", "Natural Language Processing", "Deep Learning", "Project Management", "Professional Ethics"],
    8: ["Project Phase-II", "Industry Training", "Elective-I", "Elective-II", "Elective-III"],
}

# All branches from PCCOE dataset
BRANCHES = [
    "Computer Engineering",
    "Information Technology",
    "Electronics and Telecommunication Engineering (E&TC)",
    "Mechanical Engineering",
    "Civil Engineering",
    "Computer Science & Engineering (AI-ML)",
    "Computer Engineering (Regional/Marathi)",
]


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables and seed initial data."""
    with get_db() as conn:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS branches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS semesters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number INTEGER UNIQUE NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                semester_id INTEGER NOT NULL,
                branch_id INTEGER,
                FOREIGN KEY (semester_id) REFERENCES semesters(id),
                FOREIGN KEY (branch_id) REFERENCES branches(id),
                UNIQUE(name, semester_id, branch_id)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT,
                academic_year TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            c.execute("ALTER TABLE users ADD COLUMN password TEXT")
        except sqlite3.OperationalError:
            pass

        c.execute("""
            CREATE TABLE IF NOT EXISTS question_papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_id INTEGER NOT NULL,
                semester_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                academic_year TEXT NOT NULL,
                file_path TEXT NOT NULL,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT,
                FOREIGN KEY (branch_id) REFERENCES branches(id),
                FOREIGN KEY (semester_id) REFERENCES semesters(id),
                FOREIGN KEY (subject_id) REFERENCES subjects(id)
            )
        """)

        # Seed branches
        for name in BRANCHES:
            c.execute("INSERT OR IGNORE INTO branches (name) VALUES (?)", (name,))

        # Seed semesters 1-8
        for i in range(1, 9):
            c.execute("INSERT OR IGNORE INTO semesters (number) VALUES (?)", (i,))

        # Seed subjects (branch_id NULL = common for all branches)
        for sem_num, subjects in SEMESTER_SUBJECTS.items():
            c.execute("SELECT id FROM semesters WHERE number = ?", (sem_num,))
            sem_row = c.fetchone()
            if sem_row:
                sem_id = sem_row[0]
                for subj in subjects:
                    c.execute(
                        "INSERT OR IGNORE INTO subjects (name, semester_id, branch_id) VALUES (?, ?, ?)",
                        (subj, sem_id, None),
                    )


def slugify(text):
    """Create filesystem-safe slug from text."""
    return text.lower().replace(" ", "_").replace("&", "and").replace("-", "_").replace("(", "").replace(")", "").replace("/", "_")[:50]

