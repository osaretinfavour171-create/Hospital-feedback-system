"""Database access for the HFD demo — dual backend.

* Postgres (psycopg3) when ``DATABASE_URL`` is set — used on Vercel/Neon.
* SQLite (builtin) otherwise — used for local dev (``hospital_demo.db``).

All SQL is written with ``?`` placeholders; ``_sql()`` converts them to
``%s`` for Postgres. Rows are returned as dict-like objects in both modes
(``sqlite3.Row`` / ``psycopg.rows.dict_row``) so callers index by column name.
"""
import json
import sqlite3
import uuid
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

from config import DATABASE_URL, DB_BACKEND, DB_FILE, SCHEMA_FILE


def get_db_connection():
    """Returns a connection to the active backend with dict-style rows."""
    if DB_BACKEND == "postgres":
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        conn.autocommit = True  # each statement commits; matches sqlite flow
        return conn
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _sql(query: str) -> str:
    """Adapt a query written with '?' placeholders for the active backend."""
    return query.replace("?", "%s") if DB_BACKEND == "postgres" else query


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

# Postgres DDL (used on Vercel/Neon). SQLite devs use schema.sql instead.
POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO departments (id, name) VALUES
    ('OPD',       'Outpatient Department'),
    ('EMERGENCY', 'Accident & Emergency'),
    ('PHARMACY',  'Main Pharmacy'),
    ('BILLING',   'Accounts & Revenue'),
    ('WARDS',     'Inpatient Wards')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS patient_feedback (
    id TEXT PRIMARY KEY,
    visit_id TEXT NOT NULL,
    department_id TEXT NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    channel TEXT NOT NULL CHECK (channel IN ('NURSE_ASSISTED', 'WHATSAPP_BOT')),
    patient_phone_hash TEXT,
    overall_rating INTEGER NOT NULL CHECK (overall_rating >= 1 AND overall_rating <= 5),
    sentiment_score DOUBLE PRECISION DEFAULT 0.0 CHECK (sentiment_score >= -1.0 AND sentiment_score <= 1.0),
    category_tags TEXT DEFAULT '[]',
    raw_comment TEXT,
    summary TEXT,
    is_anonymous INTEGER DEFAULT 0 CHECK (is_anonymous IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_department ON patient_feedback(department_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON patient_feedback(overall_rating);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON patient_feedback(created_at);

CREATE TABLE IF NOT EXISTS hospital_alerts (
    id TEXT PRIMARY KEY,
    feedback_id TEXT NOT NULL REFERENCES patient_feedback(id) ON DELETE CASCADE,
    department_id TEXT NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    severity TEXT NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    issue_summary TEXT NOT NULL,
    status TEXT DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'RESOLVED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alerts_status ON hospital_alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_department ON hospital_alerts(department_id);

CREATE OR REPLACE VIEW v_dashboard_metrics AS
SELECT
    d.id AS department_id,
    d.name AS department_name,
    COUNT(f.id) AS total_feedback_count,
    ROUND(AVG(f.overall_rating), 2) AS average_csat,
    ROUND(AVG(f.sentiment_score)::numeric, 2) AS average_sentiment,
    SUM(CASE WHEN f.overall_rating <= 2 THEN 1 ELSE 0 END) AS negative_reviews_count,
    SUM(CASE WHEN a.status = 'OPEN' THEN 1 ELSE 0 END) AS active_alerts_count
FROM departments d
LEFT JOIN patient_feedback f ON d.id = f.department_id
LEFT JOIN hospital_alerts a ON f.id = a.feedback_id
GROUP BY d.id, d.name;

CREATE TABLE IF NOT EXISTS conversation_sessions (
    phone_hash TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'start',
    collected TEXT NOT NULL DEFAULT '{}',
    history TEXT NOT NULL DEFAULT '[]',
    updated_at DOUBLE PRECISION NOT NULL
);
"""


def init_db() -> None:
    """Initializes the schema (idempotent) and seeds default departments."""
    conn = get_db_connection()
    try:
        if DB_BACKEND == "postgres":
            for stmt in POSTGRES_SCHEMA.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)
        else:
            with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Feedback CRUD
# ---------------------------------------------------------------------------
def insert_feedback(data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts a feedback record; auto-creates an escalation alert if
    `overall_rating <= 2` or `is_critical_issue` is set.

    Returns the feedback id plus alert details (if any).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        feedback_id = f"fb-{uuid.uuid4().hex[:8]}"
        category_tags_json = json.dumps(data.get("category_tags", []))

        cursor.execute(
            _sql(
                """
                INSERT INTO patient_feedback (
                    id, visit_id, department_id, channel, patient_phone_hash,
                    overall_rating, sentiment_score, category_tags, raw_comment,
                    summary, is_anonymous
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
            ),
            (
                feedback_id,
                data["visit_id"],
                data["department_id"],
                data["channel"],
                data.get("patient_phone_hash"),
                data["overall_rating"],
                round(float(data.get("sentiment_score", 0.0)), 2),
                category_tags_json,
                data.get("raw_comment"),
                data.get("summary", ""),
                1 if data.get("is_anonymous") else 0,
            ),
        )

        result: Dict[str, Any] = {"feedback_id": feedback_id, "alert_generated": False}

        # Escalation Rule: trigger alert if rating <= 2 or critical flag present
        if data["overall_rating"] <= 2 or data.get("is_critical_issue"):
            alert_id = f"alt-{uuid.uuid4().hex[:8]}"
            severity = "CRITICAL" if data.get("is_critical_issue") else "HIGH"
            summary = data.get("summary") or (
                f"Low rating ({data['overall_rating']}/5) reported in "
                f"{data['department_id']}"
            )
            cursor.execute(
                _sql(
                    """
                    INSERT INTO hospital_alerts (id, feedback_id, department_id, severity, issue_summary, status)
                    VALUES (?, ?, ?, ?, ?, 'OPEN')
                    """
                ),
                (alert_id, feedback_id, data["department_id"], severity, summary),
            )
            result.update({"alert_generated": True, "alert_id": alert_id})

        conn.commit()
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Dashboard queries
# ---------------------------------------------------------------------------
def get_dashboard_metrics() -> Dict[str, Any]:
    """Aggregated CSAT, sentiment, volume and open-alert metrics per department."""
    conn = get_db_connection()
    try:
        dept_rows = conn.execute(_sql("SELECT id, name FROM departments ORDER BY id")).fetchall()

        departments = []
        for d in dept_rows:
            fb = conn.execute(
                _sql(
                    """
                    SELECT COUNT(*) AS total,
                           AVG(overall_rating) AS avg_csat,
                           AVG(sentiment_score) AS avg_sentiment,
                           SUM(CASE WHEN overall_rating <= 2 THEN 1 ELSE 0 END) AS neg
                    FROM patient_feedback WHERE department_id = ?
                    """
                ),
                (d["id"],),
            ).fetchone()
            alerts_open = conn.execute(
                _sql(
                    """
                    SELECT COUNT(*) AS c FROM hospital_alerts
                    WHERE department_id = ? AND status = 'OPEN'
                    """
                ),
                (d["id"],),
            ).fetchone()["c"]

            total = fb["total"] or 0
            departments.append(
                {
                    "department_id": d["id"],
                    "department_name": d["name"],
                    "total_count": total,
                    "average_csat": round(fb["avg_csat"], 2) if fb["avg_csat"] is not None else None,
                    "average_sentiment": round(fb["avg_sentiment"], 2) if fb["avg_sentiment"] is not None else None,
                    "negative_count": fb["neg"] or 0,
                    "active_alerts_count": alerts_open,
                }
            )

        overall = conn.execute(
            _sql("SELECT AVG(overall_rating) AS csat, COUNT(*) AS total FROM patient_feedback")
        ).fetchone()
        open_alerts = conn.execute(
            _sql("SELECT COUNT(*) AS c FROM hospital_alerts WHERE status = 'OPEN'")
        ).fetchone()["c"]
        with_feedback = [d for d in departments if d["total_count"] > 0]

        return {
            "overall_csat": round(overall["csat"], 2) if overall["csat"] is not None else None,
            "total_responses": overall["total"],
            "open_alerts_count": open_alerts,
            "nps_proxy_percentage": _nps_proxy(conn),
            "department_metrics": departments,
            "top_department": max(with_feedback, key=lambda d: d["average_csat"])["department_id"]
            if with_feedback else None,
            "bottom_department": min(with_feedback, key=lambda d: d["average_csat"])["department_id"]
            if with_feedback else None,
        }
    finally:
        conn.close()


def _nps_proxy(conn) -> float:
    """Proxy NPS: (promoters - detractors) / total * 100. Promoters 4-5, detractors 1-2."""
    row = conn.execute(
        _sql(
            """
            SELECT
                SUM(CASE WHEN overall_rating >= 4 THEN 1 ELSE 0 END) AS promoters,
                SUM(CASE WHEN overall_rating <= 2 THEN 1 ELSE 0 END) AS detractors,
                COUNT(*) AS total
            FROM patient_feedback
            """
        )
    ).fetchone()
    total = row["total"] or 0
    if total == 0:
        return 0.0
    return round(((row["promoters"] or 0) - (row["detractors"] or 0)) / total * 100, 1)


def get_alerts(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches alerts, optionally filtered by status (OPEN/RESOLVED)."""
    conn = get_db_connection()
    try:
        if status:
            rows = conn.execute(
                _sql("SELECT * FROM hospital_alerts WHERE status = ? ORDER BY created_at DESC"),
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                _sql("SELECT * FROM hospital_alerts ORDER BY created_at DESC")
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def resolve_alert(alert_id: str) -> Optional[Dict[str, Any]]:
    """Marks an alert RESOLVED. Returns the updated row or None if not found."""
    conn = get_db_connection()
    try:
        cur = conn.execute(
            _sql(
                "UPDATE hospital_alerts SET status = 'RESOLVED' WHERE id = ? AND status = 'OPEN'"
            ),
            (alert_id,),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            _sql("SELECT * FROM hospital_alerts WHERE id = ?"), (alert_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_recent_feedback(limit: int = 20) -> List[Dict[str, Any]]:
    """Most recent feedback records (used by the WhatsApp simulator history)."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            _sql("SELECT * FROM patient_feedback ORDER BY created_at DESC LIMIT ?"),
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Conversation session store (DB-backed so it survives serverless cold starts)
# ---------------------------------------------------------------------------
def upsert_session(
    phone_hash: str,
    state: str,
    collected_json: str,
    history_json: str,
    updated_at: float,
) -> None:
    """Creates or refreshes a conversation session row."""
    conn = get_db_connection()
    try:
        if DB_BACKEND == "postgres":
            conn.execute(
                """
                INSERT INTO conversation_sessions (phone_hash, state, collected, history, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (phone_hash) DO UPDATE SET
                    state = EXCLUDED.state,
                    collected = EXCLUDED.collected,
                    history = EXCLUDED.history,
                    updated_at = EXCLUDED.updated_at
                """,
                (phone_hash, state, collected_json, history_json, updated_at),
            )
        else:
            conn.execute(
                """
                INSERT INTO conversation_sessions (phone_hash, state, collected, history, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(phone_hash) DO UPDATE SET
                    state = excluded.state,
                    collected = excluded.collected,
                    history = excluded.history,
                    updated_at = excluded.updated_at
                """,
                (phone_hash, state, collected_json, history_json, updated_at),
            )
        conn.commit()
    finally:
        conn.close()


def get_session(phone_hash: str) -> Optional[Dict[str, Any]]:
    """Returns a conversation session row or None."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            _sql(
                "SELECT phone_hash, state, collected, history, updated_at "
                "FROM conversation_sessions WHERE phone_hash = ?"
            ),
            (phone_hash,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_session(phone_hash: str) -> None:
    """Removes a conversation session (cancel / completed / guardrail)."""
    conn = get_db_connection()
    try:
        conn.execute(
            _sql("DELETE FROM conversation_sessions WHERE phone_hash = ?"),
            (phone_hash,),
        )
        conn.commit()
    finally:
        conn.close()


def prune_sessions(older_than_epoch: float) -> None:
    """Deletes sessions that have been idle past the TTL."""
    conn = get_db_connection()
    try:
        conn.execute(
            _sql("DELETE FROM conversation_sessions WHERE updated_at < ?"),
            (older_than_epoch,),
        )
        conn.commit()
    finally:
        conn.close()
