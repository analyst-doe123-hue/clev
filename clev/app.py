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

@app.route('/upload_result_file', methods=['POST'])
def upload_result_file():
    adm = request.form['adm_no'].strip().upper()
    file = request.files.get('result_pdf')
    note = request.form.get('note', '')
    if adm in students_data and file and allowed_file(file.filename):
        fn = secure_filename(f"{adm}_result.pdf")
        path = os.path.join(app.config['RESULTS_UPLOAD_FOLDER'], fn)
        file.save(path)
        result_links[adm] = {'url': url_for('static', filename=f'images/results_uploads/{fn}'), 'note': note}
    return redirect(url_for('profile', adm_no=adm))

@app.route('/gallery', methods=['GET','POST'])
def gallery():
    if request.method=='POST':
        photo = request.files.get('photo')
        note = request.form.get('note','')
        if photo and photo.filename:
            fn = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
            uploads.append({'filename': fn, 'note': note})
    return render_template('gallery.html', uploads=uploads)

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
if __name__=='__main__':
    app.run(debug=True)