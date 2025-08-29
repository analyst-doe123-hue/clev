# app.py
import os
import csv
import smtplib
import sqlite3
from email.message import EmailMessage
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader
from pathlib import Path
from flask_sqlalchemy import SQLAlchemy
app = Flask(__name__)

app = Flask(__name__)

# Database config: prefer Postgres, fallback to SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    "DATABASE_URL",
    "sqlite:///students.db"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ----------------------------
# Define your models here
# ----------------------------
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    adm_no = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.Text)
    # add more fields as needed

# ----------------------------
# Routes
# ----------------------------
@app.route("/")
def index():
    return "Student Portfolio running!"
# =====================================================
# Configuration (use environment variables in production)
# =====================================================
# Core app
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-prod")
MAX_CONTENT_MB = int(os.getenv("MAX_CONTENT_MB", "16"))
# On Render, only /opt/render/project/src and /tmp are writable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Prefer environment variable (if you attach a Render Disk later),
# otherwise default to a safe project-local path.
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "students.db"))

# Make sure the directory exists (only if not using /var/data without a disk)
Path(os.path.dirname(DB_PATH) or ".").mkdir(parents=True, exist_ok=True)

# CSV roster (unchanged – read-only)
STUDENTS_CSV = os.getenv("STUDENTS_CSV", "students.csv")
RESULTS_CSV = os.getenv("RESULTS_CSV", "results.csv")  # legacy, used only for one-time migration

# Email (optional)
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_PASS = os.getenv("EMAIL_PASS", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")

# Cloudinary (REQUIRED for uploads)
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

# =====================================================
# Flask app
# =====================================================
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_MB * 1024 * 1024

# In-memory cache of student roster
students_data = {}

# =====================================================
# SQLite helpers
# =====================================================

def get_conn():
    return sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)


def init_db():
    conn = get_conn()
    c = conn.cursor()
    # Biography table (adm_no unique)
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS biographies (
            adm_no TEXT PRIMARY KEY,
            biography TEXT
        );
        """
    )
    # Unified uploads table for gallery/results/letters
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            adm_no TEXT NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('gallery','result','letter')),
            url TEXT NOT NULL,
            public_id TEXT NOT NULL UNIQUE,
            note TEXT,
            filename TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    conn.close()


def get_bio(adm_no: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT biography FROM biographies WHERE adm_no=?", (adm_no,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def save_bio(adm_no: str, biography: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO biographies (adm_no, biography)
        VALUES (?, ?)
        ON CONFLICT(adm_no) DO UPDATE SET biography=excluded.biography
        """,
        (adm_no, biography),
    )
    conn.commit()
    conn.close()


def add_upload(adm_no: str, kind: str, url: str, public_id: str, note: str = None, filename: str = None):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        INSERT OR IGNORE INTO uploads (adm_no, kind, url, public_id, note, filename)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (adm_no, kind, url, public_id, note, filename),
    )
    conn.commit()
    conn.close()


def get_uploads(adm_no: str, kind: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id, url, public_id, note, filename, created_at FROM uploads WHERE adm_no=? AND kind=? ORDER BY created_at DESC",
        (adm_no, kind),
    )
    rows = c.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "url": r[1],
            "public_id": r[2],
            "note": r[3] or "",
            "filename": r[4] or "",
            "created_at": r[5],
        }
        for r in rows
    ]


def delete_upload(public_id: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM uploads WHERE public_id=?", (public_id,))
    conn.commit()
    conn.close()

# =====================================================
# One-time migration: results.csv -> uploads(kind='result')
# =====================================================

def migrate_results_csv_to_db():
    if not os.path.exists(RESULTS_CSV):
        return
    try:
        with open(RESULTS_CSV, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                adm = (row.get('Admission Number') or '').strip().upper()
                url = (row.get('url') or '').strip()
                public_id = (row.get('public_id') or '').strip()
                note = (row.get('note') or '').strip()
                if adm and url and public_id:
                    add_upload(adm, 'result', url, public_id, note=note, filename=os.path.basename(url))
        # Optionally rename the CSV so we don't re-import on every boot
        try:
            os.rename(RESULTS_CSV, RESULTS_CSV + ".imported")
        except Exception:
            pass
    except Exception as ex:
        # Don't crash the app on migration issues
        print("Migration warning:", ex)

# =====================================================
# CSV roster loader (read-only student data)
# =====================================================

def load_students():
    students_data.clear()
    if not os.path.exists(STUDENTS_CSV):
        return
    with open(STUDENTS_CSV, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            adm = (row.get('Admission Number') or '').strip().upper()
            if adm:
                students_data[adm] = row

# =====================================================
# Routes
# =====================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/search', methods=['POST'])
def search():
    adm = (request.form.get('adm_no') or '').strip().upper()
    if not adm:
        flash('Please enter an admission number', 'error')
        return redirect(url_for('index'))
    return redirect(url_for('profile', adm_no=adm))


@app.route('/profile/<adm_no>')
def profile(adm_no):
    st = students_data.get(adm_no)
    if not st:
        flash('Student not found', 'error')
        return redirect(url_for('index'))
    # Override CSV biography with SQLite biography if available
    bio = get_bio(adm_no)
    if bio:
        st = dict(st)  # don't mutate cache row
        st['Small Biography'] = bio
    # Show latest result images below profile
    result_images = get_uploads(adm_no, 'result')
    return render_template('profile.html', student=st, results=[], result_images=result_images)


# --------- Gallery ----------
@app.route('/gallery/<adm_no>', methods=['GET', 'POST'])
def gallery(adm_no):
    student = students_data.get(adm_no)
    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        photos = request.files.getlist('gallery_file')
        note = request.form.get('note', '')
        count = 0
        for photo in photos:
            if photo and photo.filename:
                upload = cloudinary.uploader.upload(photo, folder=f"gallery/{adm_no}/")
                add_upload(
                    adm_no,
                    'gallery',
                    upload.get('secure_url', ''),
                    upload.get('public_id', ''),
                    note=note,
                    filename=secure_filename(photo.filename),
                )
                count += 1
        if count:
            flash(f"{count} photo(s) uploaded successfully.", 'success')
        else:
            flash('No files uploaded', 'error')
        return redirect(url_for('gallery', adm_no=adm_no))

    student_uploads = get_uploads(adm_no, 'gallery')
    return render_template('gallery.html', uploads=student_uploads, student=student)


# --------- Results ----------
@app.route('/results/<adm_no>')
def results(adm_no):
    student = students_data.get(adm_no)
    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('index'))
    result_images = get_uploads(adm_no, 'result')
    return render_template('results.html', student=student, results=[], result_images=result_images)


@app.route('/upload_result_file/<adm_no>', methods=['POST'])
def upload_result_file(adm_no):
    files = request.files.getlist('result_file')
    note = request.form.get('note', '')
    if not files or all((f.filename or '').strip() == '' for f in files):
        flash('No files selected', 'error')
        return redirect(url_for('results', adm_no=adm_no))

    count = 0
    for file in files:
        name = (file.filename or '').lower()
        if name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf')):
            # allow PDF result slips too
            resource_type = 'image' if not name.endswith('.pdf') else 'raw'
            upload = cloudinary.uploader.upload(file, folder=f"results/{adm_no}", resource_type=resource_type)
            add_upload(
                adm_no,
                'result',
                upload.get('secure_url', ''),
                upload.get('public_id', ''),
                note=note,
                filename=secure_filename(file.filename),
            )
            count += 1
    if count:
        flash('Files uploaded successfully', 'success')
    else:
        flash('No valid files uploaded', 'error')
    return redirect(url_for('results', adm_no=adm_no))


# --------- Letters ----------
@app.route('/letter/<adm_no>', methods=['GET', 'POST'])
def letter(adm_no):  # renamed from view_letter
    student = students_data.get(adm_no)
    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        files = request.files.getlist('letter_file')
        note = request.form.get('note', '')
        count = 0
        for file in files:
            name = (file.filename or '').lower()
            if name.endswith(('.pdf', '.doc', '.docx', '.txt')):
                upload = cloudinary.uploader.upload(
                    file,
                    folder=f"letters/{adm_no}/",
                    resource_type='raw',
                )
                add_upload(
                    adm_no,
                    'letter',
                    upload.get('secure_url', ''),
                    upload.get('public_id', ''),
                    note=note,
                    filename=secure_filename(file.filename),
                )
                count += 1
        if count:
            flash(f"{count} letter(s) uploaded successfully.", 'success')
        else:
            flash('No valid letter files uploaded', 'error')
        return redirect(url_for('letter', adm_no=adm_no))  # updated

    letters = get_uploads(adm_no, 'letter')
    return render_template('letter.html', student=student, letters=letters)

# --------- Delete Cloudinary + DB ----------
@app.route('/delete_file', methods=['POST'])
def delete_file():
    data = request.get_json(force=True)
    adm_no = (data.get('adm_no') or '').strip().upper()
    public_id = data.get('public_id') or ''
    file_type = data.get('type') or ''  # 'gallery' | 'result' | 'letter'

    if not public_id or file_type not in ('gallery', 'result', 'letter'):
        return jsonify({"success": False, "error": "Missing or invalid data"}), 400

    try:
        # Delete from Cloudinary
        if file_type == 'letter':
            cloudinary.uploader.destroy(public_id, resource_type='raw')
        else:
            cloudinary.uploader.destroy(public_id)
        # Delete from DB
        delete_upload(public_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --------- Departments + Contact ----------
@app.route('/departments')
def departments():
    return render_template('department/department.html')


@app.route('/department/<dept_name>', methods=['GET', 'POST'])
def department(dept_name):
    dept_map = {
        'germans': 'Germans',
        'italians': 'Italians',
        'education': 'Education for Generations',
        'warmhearted': 'Warmhearted Group',
        'assisted': 'Assisted Group',
    }
    section = dept_map.get(dept_name, 'Department')
    filtered = {adm: st for adm, st in students_data.items() if (st.get('Department') or '').strip().lower() == section.lower()}
    error = None
    if request.method == 'POST':
        adm = (request.form.get('adm_no') or '').strip().upper()
        if adm in filtered:
            return redirect(url_for('profile', adm_no=adm))
        else:
            error = "Student not found!"
    return render_template('department/department_search.html', dept=section, error=error, student=filtered)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    msg = None
    if request.method == 'POST':
        e = request.form.get('email') or ''
        m = request.form.get('message') or ''
        try:
            if not (EMAIL_FROM and EMAIL_PASS and EMAIL_TO):
                raise RuntimeError('Email not configured')
            mail = EmailMessage()
            mail['Subject'] = "Message from Daisy Portal"
            mail['From'] = EMAIL_FROM
            mail['To'] = EMAIL_TO
            mail.set_content(f"From: {e}\n\n{m}")
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(EMAIL_FROM, EMAIL_PASS)
                smtp.send_message(mail)
            msg = ('success', "Message sent successfully!")
        except Exception as ex:
            msg = ('error', f"Failed: {ex}")
    return render_template('contact.html', **({msg[0]: msg[1]} if msg else {}))


# --------- Update Biography (AJAX) ----------
@app.route('/update_bio', methods=['POST'])
def update_bio():
    data = request.get_json(force=True)
    adm_no = (data.get('adm_no') or '').strip().upper()
    new_bio = (data.get('biography') or '').strip()

    if not adm_no or not new_bio:
        return 'Missing data', 400

    save_bio(adm_no, new_bio)

    # Optional: immediately reflect in roster cache if present
    if adm_no in students_data:
        students_data[adm_no]['Small Biography'] = new_bio

    return '', 204

# =====================================================
# App startup
# =====================================================
init_db()
load_students()
migrate_results_csv_to_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=True)
