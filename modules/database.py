"""
database.py - SQLite persistence layer for the Expense Savings Agent
"""
import sqlite3
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "expense_agent.db")


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory enabled."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """Initialize the database schema (idempotent)."""
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.executescript("""
        CREATE TABLE IF NOT EXISTS analysis_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT,
            filename TEXT,
            total_rows INTEGER,
            accepted_rows INTEGER,
            rejected_rows INTEGER,
            total_amount REAL,
            currency TEXT DEFAULT 'USD',
            analysis_date TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS recommendation_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            recommendation_title TEXT NOT NULL,
            category TEXT,
            status TEXT DEFAULT 'Pending'
                CHECK(status IN ('Pending','Accepted','Rejected','Implemented')),
            estimated_monthly_savings REAL,
            estimated_annual_savings REAL,
            priority TEXT,
            notes TEXT,
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES analysis_sessions(id)
        );

        CREATE TABLE IF NOT EXISTS category_thresholds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT UNIQUE NOT NULL,
            monthly_threshold REAL,
            alert_pct_increase REAL DEFAULT 20.0,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS flagged_transaction_review (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            transaction_id TEXT,
            flag_type TEXT,
            flag_reason TEXT,
            review_status TEXT DEFAULT 'Unreviewed'
                CHECK(review_status IN ('Unreviewed','Confirmed','Dismissed','Escalated')),
            reviewer_notes TEXT,
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES analysis_sessions(id)
        );

        CREATE TABLE IF NOT EXISTS report_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            report_type TEXT,
            filename TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES analysis_sessions(id)
        );
        """)
        conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    except Exception as e:
        logger.error("DB init error: %s", e)
        raise
    finally:
        conn.close()


def save_session(
    filename: str,
    total_rows: int,
    accepted_rows: int,
    rejected_rows: int,
    total_amount: float,
    currency: str = "USD",
    session_name: Optional[str] = None,
) -> int:
    """Save analysis session metadata and return session_id."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO analysis_sessions
               (session_name, filename, total_rows, accepted_rows, rejected_rows,
                total_amount, currency, analysis_date)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                session_name or filename,
                filename,
                total_rows,
                accepted_rows,
                rejected_rows,
                total_amount,
                currency,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_sessions(limit: int = 20) -> List[Dict]:
    """Return recent analysis sessions."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM analysis_sessions ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def upsert_recommendation(
    session_id: int,
    title: str,
    category: str,
    status: str,
    monthly_savings: float,
    annual_savings: float,
    priority: str,
    notes: str = "",
) -> int:
    """Insert or update a recommendation decision, return its id."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM recommendation_decisions WHERE session_id=? AND recommendation_title=?",
            (session_id, title),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                """UPDATE recommendation_decisions
                   SET status=?, estimated_monthly_savings=?, estimated_annual_savings=?,
                       priority=?, notes=?, updated_at=datetime('now')
                   WHERE id=?""",
                (status, monthly_savings, annual_savings, priority, notes, row["id"]),
            )
            conn.commit()
            return row["id"]
        else:
            cur.execute(
                """INSERT INTO recommendation_decisions
                   (session_id, recommendation_title, category, status,
                    estimated_monthly_savings, estimated_annual_savings, priority, notes)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (session_id, title, category, status, monthly_savings, annual_savings, priority, notes),
            )
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def get_recommendations(session_id: int) -> List[Dict]:
    """Return recommendation decisions for a session."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM recommendation_decisions WHERE session_id=? ORDER BY id",
            (session_id,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def update_recommendation_status(rec_id: int, status: str, notes: str = "") -> bool:
    """Update the status of a recommendation decision."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE recommendation_decisions
               SET status=?, notes=?, updated_at=datetime('now')
               WHERE id=?""",
            (status, notes, rec_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def upsert_category_threshold(category: str, monthly_threshold: float, alert_pct: float = 20.0) -> None:
    """Save or update a category spending threshold."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO category_thresholds (category, monthly_threshold, alert_pct_increase)
               VALUES (?,?,?)
               ON CONFLICT(category) DO UPDATE SET
                 monthly_threshold=excluded.monthly_threshold,
                 alert_pct_increase=excluded.alert_pct_increase,
                 updated_at=datetime('now')""",
            (category, monthly_threshold, alert_pct),
        )
        conn.commit()
    finally:
        conn.close()


def get_category_thresholds() -> Dict[str, Dict]:
    """Return all stored category thresholds as {category: {threshold, alert_pct}}."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM category_thresholds")
        return {row["category"]: dict(row) for row in cur.fetchall()}
    finally:
        conn.close()


def save_flagged_transaction(
    session_id: int,
    transaction_id: str,
    flag_type: str,
    flag_reason: str,
) -> int:
    """Save a flagged transaction for later review."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO flagged_transaction_review
               (session_id, transaction_id, flag_type, flag_reason)
               VALUES (?,?,?,?)""",
            (session_id, transaction_id, flag_type, flag_reason),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_flagged_status(flag_id: int, status: str, notes: str = "") -> bool:
    """Update the review status of a flagged transaction."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE flagged_transaction_review
               SET review_status=?, reviewer_notes=?, updated_at=datetime('now')
               WHERE id=?""",
            (status, notes, flag_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def save_report_metadata(session_id: int, report_type: str, filename: str) -> None:
    """Log generated report metadata."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO report_metadata (session_id, report_type, filename) VALUES (?,?,?)",
            (session_id, report_type, filename),
        )
        conn.commit()
    finally:
        conn.close()
