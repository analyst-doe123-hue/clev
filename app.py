# app.py
import os
import csv
import smtplib
from email.message import EmailMessage
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader

# ----------------------
# Hard-coded configuration
# ----------------------
# Cloudinary: using direct credentials
cloudinary.config(
    cloud_name='dbdchnnei',
    api_key='641414359882347',
    api_secret='XToITayCxZ5FNIWSqjQS_5WmB4o',
    secure=True
)

# Email config (hard-code if you want, or keep env for security)
EMAIL_USER = "your_email@gmail.com"
EMAIL_PASS = "your_email_password"
EMAIL_FROM = "your_email@gmail.com"
EMAIL_TO = "recipient@example.com"

# File paths
DATA_DIR = "."
os.makedirs(DATA_DIR, exist_ok=True)
RESULTS_CSV = os.path.join(DATA_DIR, "results.csv")
EDITED_STUDENTS_CSV = os.path.join(DATA_DIR, "edited_students.csv")

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# ----------------------
# Global in-memory storage
# ----------------------
students_data = {}
uploads = []
letter_links = {}

# ----------------------
# Helpers
# ----------------------
def load_students():
    path = os.path.join(DATA_DIR, "students.csv")
    if not os.path.exists(path):
        return
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            adm = row.get('Admission Number', '').strip().upper()
            if adm:
                students_data[adm] = row

def load_results():
    if not os.path.exists(RESULTS_CSV):
        return []
    with open(RESULTS_CSV, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def save_results(results_list):
    fieldnames = ["Admission Number", "url", "public_id", "note"]
    with open(RESULTS_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results_list:
            writer.writerow({
                "Admission Number": row.get("Admission Number", ""),
                "url": row.get("url", ""),
                "public_id": row.get("public_id", ""),
                "note": row.get("note", "")
            })

# ----------------------
# Routes
# ----------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    adm = request.form.get('adm_no', '').strip().upper()
    return redirect(url_for('profile', adm_no=adm))

@app.route('/profile/<adm_no>')
def profile(adm_no):
    st = students_data.get(adm_no)
    if not st:
        return redirect(url_for('index'))
    results = [r for r in load_results() if r["Admission Number"] == adm_no]
    return render_template('profile.html', student=st, results=results)

@app.route('/gallery/<adm_no>', methods=['GET', 'POST'])
def gallery(adm_no):
    student = students_data.get(adm_no)
    if not student:
        return redirect(url_for('index'))

    if request.method == 'POST':
        photos = request.files.getlist('gallery_file')
        note = request.form.get('note', '')

        for photo in photos:
            if photo and photo.filename:
                result = cloudinary.uploader.upload(photo, folder=f"gallery/{adm_no}/")
                uploads.append({
                    'url': result['secure_url'],
                    'note': note,
                    'adm_no': adm_no,
                    'public_id': result['public_id']
                })

        flash(f"{len(photos)} photo(s) uploaded successfully.")

    student_uploads = [up for up in uploads if up['adm_no'] == adm_no]
    return render_template('gallery.html', uploads=student_uploads, student=student)

@app.route('/results/<adm_no>')
def results(adm_no):
    student = students_data.get(adm_no)
    if not student:
        return redirect(url_for('index'))
    all_results = load_results()
    student_results = [r for r in all_results if r["Admission Number"].strip().upper() == adm_no]
    result_images = [{
        'url': r.get('url', ''),
        'public_id': r.get('public_id', ''),
        'note': r.get('note', ''),
        'filename': r.get('url', '').split('/')[-1] if r.get('url') else ''
    } for r in student_results]
    return render_template('results.html', student=student, results=[], result_images=result_images)

@app.route("/upload_result_file/<adm_no>", methods=["POST"])
def upload_result_file(adm_no):
    uploaded_files = request.files.getlist("result_file")
    note = request.form.get("note", "")
    if not uploaded_files or all(f.filename == "" for f in uploaded_files):
        flash("No files selected", "error")
        return redirect(url_for("results", adm_no=adm_no))
    results = load_results()
    for file in uploaded_files:
        if file and file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            upload = cloudinary.uploader.upload(file, folder=f"results/{adm_no}")
            results.append({
                "Admission Number": adm_no,
                "url": upload.get("secure_url", ""),
                "public_id": upload.get("public_id", ""),
                "note": note
            })
    save_results(results)
    flash("Files uploaded successfully", "success")
    return redirect(url_for("results", adm_no=adm_no))

@app.route('/delete_file', methods=['POST'])
def delete_file():
    data = request.get_json()
    adm_no = data.get('adm_no', '').strip().upper()
    public_id = data.get('public_id', '')
    file_type = data.get('type', '')
    if not public_id:
        return jsonify({"success": False, "error": "Missing data"}), 400
    try:
        if file_type == 'letter':
            cloudinary.uploader.destroy(public_id, resource_type='raw')
        else:
            cloudinary.uploader.destroy(public_id)
        if file_type == 'letter' and adm_no in letter_links:
            letter_links[adm_no] = [f for f in letter_links[adm_no] if f['public_id'] != public_id]
        elif file_type == 'result':
            results = load_results()
            results = [r for r in results if r.get('public_id') != public_id]
            save_results(results)
        elif file_type == 'gallery':
            global uploads
            uploads = [f for f in uploads if f.get('public_id') != public_id]
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/letter/<adm_no>', methods=['GET', 'POST'])
def view_letter(adm_no):
    student = students_data.get(adm_no)
    if not student:
        return redirect(url_for('index'))
    if request.method == 'POST':
        files = request.files.getlist('letter_file')
        note = request.form.get('note', '')
        for file in files:
            if file and file.filename.lower().endswith(('.pdf', '.docx')):
                result = cloudinary.uploader.upload(file, folder=f"letters/{adm_no}/", resource_type='raw')
                entry = {
                    'url': result['secure_url'],
                    'note': note,
                    'filename': file.filename,
                    'public_id': result['public_id']
                }
                letter_links.setdefault(adm_no, []).append(entry)
        flash(f"{len(files)} letter(s) uploaded successfully.")
    letters = letter_links.get(adm_no, [])
    return render_template('letter.html', student=student, letters=letters)

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
        'assisted': 'Assisted Group'
    }
    section = dept_map.get(dept_name, 'Department')
    filtered = {adm: st for adm, st in students_data.items() if st.get('Department', '').strip().lower() == section.lower()}
    error = None
    if request.method == 'POST':
        adm = request.form.get('adm_no', '').strip().upper()
        if adm in filtered:
            return redirect(url_for('profile', adm_no=adm))
        else:
            error = "Student not found!"
    return render_template('department/department_search.html', dept=section, error=error, student=filtered)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    msg = None
    if request.method == 'POST':
        e = request.form['email']
        m = request.form['message']
        try:
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

@app.route('/update_bio', methods=['POST'])
def update_bio():
    data = request.get_json()
    adm_no = data.get('adm_no', '').strip().upper()
    new_bio = data.get('biography', '').strip()
    updated = False
    rows = []
    if not os.path.exists(EDITED_STUDENTS_CSV):
        return 'Student not found', 404
    with open(EDITED_STUDENTS_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Admission Number'].strip().upper() == adm_no:
                row['Small Biography'] = new_bio
                updated = True
            rows.append(row)
    if updated:
        with open(EDITED_STUDENTS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        students_data[adm_no]['Small Biography'] = new_bio
        return '', 204
    else:
        return 'Student not found', 404

# ----------------------
# Load data on startup
# ----------------------
load_students()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
