import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "vacancy_bot.db"

# O'zbekistonning barcha hududlari (12 ta viloyat + Qoraqalpog'iston Respublikasi + Toshkent shahri)
REGIONS = [
    "Andijon",
    "Buxoro",
    "Farg'ona",
    "Jizzax",
    "Xorazm",
    "Namangan",
    "Navoiy",
    "Qashqadaryo",
    "Qoraqalpog'iston Respublikasi",
    "Samarqand",
    "Sirdaryo",
    "Surxondaryo",
    "Toshkent viloyati",
    "Toshkent shahri",
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS employers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_user_id INTEGER UNIQUE NOT NULL,
            company_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_user_id INTEGER NOT NULL,
            region TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(tg_user_id, region)
        );

        CREATE TABLE IF NOT EXISTS vacancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employer_id INTEGER NOT NULL REFERENCES employers(id),
            region TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            salary TEXT,
            contact TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected
            created_at TEXT NOT NULL,
            decided_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def upsert_employer(tg_user_id: int, company_name: str) -> int:
    conn = get_conn()
    cur = conn.execute("SELECT id FROM employers WHERE tg_user_id = ?", (tg_user_id,))
    row = cur.fetchone()
    if row:
        conn.execute(
            "UPDATE employers SET company_name = ? WHERE tg_user_id = ?",
            (company_name, tg_user_id),
        )
        conn.commit()
        emp_id = row["id"]
    else:
        cur = conn.execute(
            "INSERT INTO employers (tg_user_id, company_name, created_at) VALUES (?, ?, ?)",
            (tg_user_id, company_name, datetime.utcnow().isoformat()),
        )
        conn.commit()
        emp_id = cur.lastrowid
    conn.close()
    return emp_id


def create_vacancy(employer_id: int, region: str, title: str, description: str, salary: str, contact: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO vacancies (employer_id, region, title, description, salary, contact, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
        (employer_id, region, title, description, salary, contact, datetime.utcnow().isoformat()),
    )
    conn.commit()
    vac_id = cur.lastrowid
    conn.close()
    return vac_id


def get_vacancy(vacancy_id: int):
    conn = get_conn()
    row = conn.execute(
        """SELECT v.*, e.company_name, e.tg_user_id AS employer_tg_id
           FROM vacancies v JOIN employers e ON e.id = v.employer_id
           WHERE v.id = ?""",
        (vacancy_id,),
    ).fetchone()
    conn.close()
    return row


def set_vacancy_status(vacancy_id: int, status: str):
    conn = get_conn()
    conn.execute(
        "UPDATE vacancies SET status = ?, decided_at = ? WHERE id = ?",
        (status, datetime.utcnow().isoformat(), vacancy_id),
    )
    conn.commit()
    conn.close()


def get_approved_vacancies(region: str = None):
    conn = get_conn()
    if region:
        rows = conn.execute(
            """SELECT v.*, e.company_name FROM vacancies v JOIN employers e ON e.id = v.employer_id
               WHERE v.status = 'approved' AND v.region = ? ORDER BY v.created_at DESC""",
            (region,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT v.*, e.company_name FROM vacancies v JOIN employers e ON e.id = v.employer_id
               WHERE v.status = 'approved' ORDER BY v.created_at DESC"""
        ).fetchall()
    conn.close()
    return rows


def get_pending_vacancies():
    conn = get_conn()
    rows = conn.execute(
        """SELECT v.*, e.company_name FROM vacancies v JOIN employers e ON e.id = v.employer_id
           WHERE v.status = 'pending' ORDER BY v.created_at ASC"""
    ).fetchall()
    conn.close()
    return rows


def get_vacancies_by_tg_user(tg_user_id: int):
    conn = get_conn()
    rows = conn.execute(
        """SELECT v.* FROM vacancies v JOIN employers e ON e.id = v.employer_id
           WHERE e.tg_user_id = ? ORDER BY v.created_at DESC""",
        (tg_user_id,),
    ).fetchall()
    conn.close()
    return rows


def delete_vacancy(vacancy_id: int, tg_user_id: int) -> bool:
    """Faqat shu vakansiyaning egasi o'chira oladi. True/False qaytaradi."""
    conn = get_conn()
    row = conn.execute(
        """SELECT v.id FROM vacancies v JOIN employers e ON e.id = v.employer_id
           WHERE v.id = ? AND e.tg_user_id = ?""",
        (vacancy_id, tg_user_id),
    ).fetchone()
    if not row:
        conn.close()
        return False
    conn.execute("DELETE FROM vacancies WHERE id = ?", (vacancy_id,))
    conn.commit()
    conn.close()
    return True


def toggle_subscription(tg_user_id: int, region: str) -> bool:
    """Obunani yoqadi/o'chiradi. True = endi obuna bo'ldi, False = obunadan chiqdi."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM subscriptions WHERE tg_user_id = ? AND region = ?",
        (tg_user_id, region),
    ).fetchone()
    if row:
        conn.execute("DELETE FROM subscriptions WHERE id = ?", (row["id"],))
        conn.commit()
        conn.close()
        return False
    conn.execute(
        "INSERT INTO subscriptions (tg_user_id, region, created_at) VALUES (?, ?, ?)",
        (tg_user_id, region, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return True


def get_user_subscriptions(tg_user_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT region FROM subscriptions WHERE tg_user_id = ?", (tg_user_id,)
    ).fetchall()
    conn.close()
    return {row["region"] for row in rows}


def get_subscribers(region: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT tg_user_id FROM subscriptions WHERE region = ?", (region,)
    ).fetchall()
    conn.close()
    return [row["tg_user_id"] for row in rows]


def get_stats():
    conn = get_conn()
    row = conn.execute(
        """SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) AS rejected
           FROM vacancies"""
    ).fetchone()
    conn.close()
    return dict(row)
