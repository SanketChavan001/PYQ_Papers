# PaperVault – Previous Year Question Papers

A web application for students to search and download previous year question papers by branch, semester, subject and academic year. Built with HTML, CSS, JavaScript (frontend) and Python Flask (backend) with SQLite.

## Features

- **Students**: Filter by Branch, Semester, Subject, Academic Year (e.g. 2023-24) and download PDFs
- **Continue without sign in**: Browse and download papers without creating an account
- **Optional Sign up / Sign in**: Create account with username, email and academic year (profile only)
- **Admin**: Upload papers, manage branches, semesters and subjects
- **Admin Login**: username `admin`, password `Admin@1234`

## Setup

1. Install Python 3 and create a virtual environment (optional):

```bash
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the application:

```bash
python app.py
```

4. Open browser: `http://127.0.0.1:5000`

## Project Structure

- `app.py` - Flask backend, API routes
- `database.py` - SQLite setup, seed data (branches, semesters, subjects)
- `pdf/` - Folder where uploaded PDFs are stored
- `question_papers.db` - SQLite database (created on first run)
- `static/` - CSS and JS
- `templates/` - HTML pages (index, login, signup, admin)

## Branches (Pre-loaded)

- Computer Engineering
- Information Technology
- Electronics and Telecommunication Engineering (E&TC)
- Mechanical Engineering
- Civil Engineering
- Computer Science & Engineering (AI-ML)
- Computer Engineering (Regional/Marathi)

## PDF Storage

Uploaded files are saved as: `{branch}_{semester}_{subject}_{year}.pdf` in the `pdf/` folder.
