import sqlite3
import os
import pandas as pd
from datetime import datetime

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "leads.db")

def get_connection(db_path=None):
    if not db_path:
        db_path = DEFAULT_DB_PATH
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=None):
    if not db_path:
        db_path = DEFAULT_DB_PATH
    conn = get_connection(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                total_records INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                row_order INTEGER,
                roll_no TEXT,
                company_name TEXT,
                location TEXT,
                domain TEXT,
                website_url TEXT,
                email TEXT,
                email_tier TEXT,
                phone TEXT,
                alt_phone TEXT,
                deliverability_status TEXT DEFAULT 'PENDING',
                mx_record TEXT,
                source TEXT,
                status TEXT DEFAULT 'PENDING',
                error_message TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_proj_status ON leads(project_id, status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_proj_order ON leads(project_id, row_order);")
    conn.close()

def create_or_get_project(project_name, total_records=0, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    with conn:
        cur = conn.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO projects (name, total_records) VALUES (?, ?)",
            (project_name, total_records)
        )
        return cur.lastrowid

def import_records(project_id, records, db_path=DEFAULT_DB_PATH):
    """
    Imports records while preserving input row_order.
    records: list of dicts with keys: roll_no, company_name, location
    """
    conn = get_connection(db_path)
    with conn:
        # Check existing row count to append or preserve
        cur = conn.execute("SELECT COUNT(*) AS cnt FROM leads WHERE project_id = ?", (project_id,))
        start_order = cur.fetchone()["cnt"]

        rows_to_insert = []
        for idx, rec in enumerate(records):
            rows_to_insert.append((
                project_id,
                start_order + idx + 1,
                rec.get("roll_no", ""),
                rec.get("company_name", "").strip(),
                rec.get("location", "").strip(),
                rec.get("email", "").strip() or None,
                "COMPLETED" if rec.get("email", "").strip() else "PENDING"
            ))

        conn.executemany("""
            INSERT INTO leads (project_id, row_order, roll_no, company_name, location, email, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, rows_to_insert)

        conn.execute(
            "UPDATE projects SET total_records = (SELECT COUNT(*) FROM leads WHERE project_id = ?), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (project_id, project_id)
        )
    conn.close()

def get_pending_leads(project_id, limit=50, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cur = conn.execute("""
        SELECT * FROM leads 
        WHERE project_id = ? AND status = 'PENDING'
        ORDER BY row_order ASC
        LIMIT ?
    """, (project_id, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def update_lead(lead_id, data, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    set_clauses = []
    values = []
    for k, v in data.items():
        set_clauses.append(f"{k} = ?")
        values.append(v)
    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    values.append(lead_id)

    query = f"UPDATE leads SET {', '.join(set_clauses)} WHERE id = ?"
    with conn:
        conn.execute(query, values)
    conn.close()

def get_project_stats(project_id, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cur = conn.execute("""
        SELECT 
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) AS failed,
            SUM(CASE WHEN email IS NOT NULL AND email != '' THEN 1 ELSE 0 END) AS with_email,
            SUM(CASE WHEN phone IS NOT NULL AND phone != '' THEN 1 ELSE 0 END) AS with_phone,
            SUM(CASE WHEN deliverability_status = 'DELIVERABLE' THEN 1 ELSE 0 END) AS deliverable
        FROM leads 
        WHERE project_id = ?
    """, (project_id,))
    row = dict(cur.fetchone())
    conn.close()
    return row

def export_dataframe(project_id, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    df = pd.read_sql_query("""
        SELECT 
            roll_no AS "Roll No",
            company_name AS "Company Name",
            location AS "Location",
            email AS "Mail",
            phone AS "Phone Number",
            website_url AS "Website",
            email_tier AS "Email Category",
            deliverability_status AS "Deliverability Status",
            mx_record AS "MX Server",
            source AS "Source"
        FROM leads
        WHERE project_id = ?
        ORDER BY row_order ASC
    """, conn, params=(project_id,))
    conn.close()
    return df
