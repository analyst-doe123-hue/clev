from flask import Flask, render_template, request, redirect, url_for
import csv, os
from werkzeug.utils import secure_filename
import smtplib
from email.message import EmailMessage

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/images/gallery_uploads'
app.config['RESULTS_UPLOAD_FOLDER'] = 'static/images/results_uploads'
app.config['ALLOWED_RESULT_EXTENSIONS'] = {'pdf'}
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['MAX_CONTENT_LENGTH'] = 16*1024*1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_UPLOAD_FOLDER'], exist_ok=True)

students_data = {}
uploads = []
result_links = {}

def load_students():
    with open('edited_students.csv', newline='', encoding='utf‑8') as f:
        for row in csv.DictReader(f):
            students_data[row['Admission Number'].strip().upper()] = row

def get_student_results(adm_no):
    rows = []
    if os.path.exists('results.csv'):
        for row in csv.DictReader(open('results.csv', newline='', encoding='utf‑8')):
            if row['Admission Number'].strip().upper() == adm_no:
                rows.append({'subject': row['Subject'], 'score': row['Score']})
    return rows

def allowed_file(fn):
    return '.' in fn and fn.rsplit('.', 1)[1].lower() in app.config['ALLOWED_RESULT_EXTENSIONS']

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
    results = get_student_results(adm_no)
    rl = result_links.get(adm_no)
    return render_template('profile.html', student=st, results=results,
                           result_pdf=rl['url'] if rl else None,
                           result_note=rl['note'] if rl else "")

@app.route('/gallery/<adm_no>', methods=['GET', 'POST'])
def gallery(adm_no):
    student = students_data.get(adm_no)
    if not student:
        return redirect(url_for('index'))
    if request.method == 'POST':
        photo = request.files.get('photo')
        note = request.form.get('note', '')
        if photo and photo.filename:
            fn = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
            uploads.append({'filename': fn, 'note': note, 'adm_no': adm_no})
    student_uploads = [up for up in uploads if up['adm_no'] == adm_no]
    return render_template('gallery.html', uploads=student_uploads, student=student)

@app.route('/results/<adm_no>')
def results(adm_no):
    student = students_data.get(adm_no)
    if not student:
        return redirect(url_for('index'))
    results = get_student_results(adm_no)
    rl = result_links.get(adm_no)
    return render_template('results.html', student=student, results=results,
                           result_pdf=rl['url'] if rl else None,
                           result_note=rl['note'] if rl else "")
@app.route('/upload_result_file/<adm_no>', methods=['POST'])
def upload_result_file(adm_no):
    adm_no = adm_no.strip().upper()
    file = request.files.get('result_pdf')
    note = request.form.get('note', '')

    if adm_no in students_data and file and allowed_file(file.filename):
        fn = secure_filename(f"{adm_no}_result.pdf")
        path = os.path.join(app.config['RESULTS_UPLOAD_FOLDER'], fn)
        file.save(path)
        result_links[adm_no] = {
            'url': url_for('static', filename=f'images/results_uploads/{fn}'),
            'note': note
        }
    return redirect(url_for('results', adm_no=adm_no))
@app.route('/departments')
def departments():
    return render_template('department/department.html')

@app.route('/department/<dept_name>', methods=['GET','POST'])
def department(dept_name):
    dept_map = {
        'germans': 'Germans',
        'italians': 'Italians',
        'education': 'Education for Generations',
        'warmhearted': 'Warmhearted Group',
        'assisted': 'Assisted Group'
    }
    section = dept_map.get(dept_name, 'Department')
    
    # Filter students by department label
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

    # 👇 Ensure student=filtered is passed to the template
    return render_template('department/department_search.html', dept=section, error=error, student=filtered)

@app.route('/contact', methods=['GET','POST'])
def contact():
    msg=None
    if request.method=='POST':
        e = request.form['email']
        m = request.form['message']
        try:
            mail = EmailMessage()
            mail['Subject']="Message from Daisy Portal"
            mail['From']='your_email@gmail.com'
            mail['To']='recipient@example.com'
            mail.set_content(f"From: {e}\n\n{m}")
            with smtplib.SMTP_SSL('smtp.gmail.com',465) as smtp:
                smtp.login('gaylordndenga4@gmail.com','your_app_password')
                smtp.send_message(mail)
            msg=('success',"Message sent successfully!")
        except Exception as ex:
            msg=('error',f"Failed: {ex}")
    return render_template('contact.html', **({msg[0]:msg[1]} if msg else {}))

load_students()
@app.route('/update_bio', methods=['POST'])
def update_bio():
    data = request.get_json()
    adm_no = data.get('adm_no', '').strip().upper()
    new_bio = data.get('biography', '').strip()
    updated = False

    # Update the CSV file
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

if __name__=='__main__':
    app.run(debug=True)
