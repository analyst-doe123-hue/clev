from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import csv, os
from werkzeug.utils import secure_filename
import smtplib
from email.message import EmailMessage
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Cloudinary config
cloudinary.config(
    cloud_name='dbdchnnei',
    api_key='641414359882347',
    api_secret='XToITayCxZ5FNIWSqjQS_5WmB4o'
)

# Global in-memory storage
students_data = {}
uploads = []
result_links = {}   # kept for backward compatibility if used elsewhere
letter_links = {}

RESULTS_CSV = "results.csv"

# ----------------------
# Helper: students
# ----------------------
def load_students():
    """Load students.csv into students_data dict keyed by Admission Number (UPPER)."""
    if not os.path.exists('students.csv'):
        return
    with open('students.csv', newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            adm = row.get('Admission Number', '').strip().upper()
            if adm:
                students_data[adm] = row

# ----------------------
# Helpers: results CSV
# ----------------------
def load_results():
    """
    Return a list of result dicts read from RESULTS_CSV.
    Each dict has keys: "Admission Number", "url", "public_id", "note"
    """
    if not os.path.exists(RESULTS_CSV):
        return []
    with open(RESULTS_CSV, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def save_results(results_list):
    """
    Write the list of dicts to RESULTS_CSV with the header:
    Admission Number,url,public_id,note
    """
    # Ensure consistent fieldnames
    fieldnames = ["Admission Number", "url", "public_id", "note"]
    with open(RESULTS_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results_list:
            # Normalize keys to ensure writer doesn't fail
            out = {
                "Admission Number": row.get("Admission Number", ""),
                "url": row.get("url", ""),
                "public_id": row.get("public_id", ""),
                "note": row.get("note", "")
            }
            writer.writerow(out)

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
    # textual academic results from separate CSV (unchanged)
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
    # load all result image records for this student
    all_results = load_results()
    student_results = [r for r in all_results if r["Admission Number"].strip().upper() == adm_no]
    # template expects variable name result_images (per your results.html)
    # We'll shape each item to have url, public_id, note, filename (optional)
    result_images = []
    for r in student_results:
        url = r.get('url', '')
        public_id = r.get('public_id', '')
        note = r.get('note', '')
        filename = url.split('/')[-1] if url else ''
        result_images.append({
            'url': url,
            'public_id': public_id,
            'note': note,
            'filename': filename
        })
    return render_template('results.html', student=student, results=[], result_images=result_images)

@app.route("/upload_result_file/<adm_no>", methods=["POST"])
def upload_result_file(adm_no):
    """
    Accept multiple image files from input name="result_file"
    Upload each to Cloudinary under folder results/<adm_no>/
    Save metadata (Admission Number, url, public_id, note) to results.csv
    """
    # The form field used in your results.html is "result_file" (multiple)
    uploaded_files = request.files.getlist("result_file")
    note = request.form.get("note", "")

    if not uploaded_files or all(f.filename == "" for f in uploaded_files):
        flash("No files selected", "error")
        return redirect(url_for("results", adm_no=adm_no))

    results = load_results()

    for file in uploaded_files:
        if file and file.filename:
            # Optional: validate image filetypes by extension
            filename = file.filename.lower()
            if not any(filename.endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                # skip non-image files
                continue

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
    """
    Generic AJAX delete endpoint used by gallery, results, letters.
    Expects JSON: { adm_no, public_id, type } where type is 'letter', 'result', or 'gallery'
    """
    data = request.get_json()
    adm_no = data.get('adm_no', '').strip().upper()
    public_id = data.get('public_id', '')
    file_type = data.get('type', '')

    if not public_id:
        return jsonify({"success": False, "error": "Missing data"}), 400

    try:
        # For letter files we uploaded as raw; for images we used default image resource type.
        if file_type == 'letter':
            cloudinary.uploader.destroy(public_id, resource_type='raw')
        else:
            # image/result/gallery => default resource_type (image)
            cloudinary.uploader.destroy(public_id)

        # remove from server-side stores
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

# Letter route (multiple uploads already present)
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
                if adm_no not in letter_links:
                    letter_links[adm_no] = []
                letter_links[adm_no].append(entry)

        flash(f"{len(files)} letter(s) uploaded successfully.")

    letters = letter_links.get(adm_no, [])
    return render_template('letter.html', student=student, letters=letters)

# Departments, contact, update_bio keep as before
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
    filtered = {
        adm: st for adm, st in students_data.items()
        if st.get('Department', '').strip().lower() == section.lower()
    }
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
            mail['From'] = 'your_email@gmail.com'
            mail['To'] = 'recipient@example.com'
            mail.set_content(f"From: {e}\n\n{m}")
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login('gaylordndenga4@gmail.com', 'your_app_password')
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
    with open('edited_students.csv', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Admission Number'].strip().upper() == adm_no:
                row['Small Biography'] = new_bio
                updated = True
            rows.append(row)

    if updated:
        with open('edited_students.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        students_data[adm_no]['Small Biography'] = new_bio
        return '', 204
    else:
        return 'Student not found', 404

# Load students on start
load_students()

if __name__ == '__main__':
    app.run(debug=True)
