import os
import csv
import sqlite3

DATA_DIR = "."
STUDENTS_CSV = os.path.join(DATA_DIR, "students.csv")
DB_PATH = os.path.join(DATA_DIR, "students.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS biographies (
            adm_no TEXT PRIMARY KEY,
            biography TEXT
        )
    ''')
    conn.commit()
    conn.close()

def migrate_csv_to_sqlite():
    if not os.path.exists(STUDENTS_CSV):
        print("❌ students.csv not found.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    with open(STUDENTS_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            adm_no = row.get("Admission Number", "").strip().upper()
            bio = row.get("Small Biography", "").strip()
            if adm_no and bio:
                c.execute('''
                    INSERT INTO biographies (adm_no, biography) VALUES (?, ?)
                    ON CONFLICT(adm_no) DO UPDATE SET biography=excluded.biography
                ''', (adm_no, bio))
                count += 1

    conn.commit()
    conn.close()
    print(f"✅ Migration complete. {count} biographies copied to SQLite.")

if __name__ == "__main__":
    init_db()
    migrate_csv_to_sqlite()
