import sqlite3
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'nexus.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# --- RAW DATA ---

def insert_raw_data(source: str, content: str, author: str = None, intel_type: str = "mixed") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO raw_data (source, content, author, intel_type) VALUES (?, ?, ?, ?)",
        (source, content, author, intel_type)
    )
    last_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return last_id


def get_unprocessed_data(limit: int = 10, intel_type: str = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    if intel_type:
        cursor.execute(
            "SELECT * FROM raw_data WHERE processed = 0 AND intel_type = ? ORDER BY created_at ASC LIMIT ?",
            (intel_type, limit)
        )
    else:
        cursor.execute(
            "SELECT * FROM raw_data WHERE processed = 0 ORDER BY created_at ASC LIMIT ?",
            (limit,)
        )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_unprocessed_news(limit: int = 10) -> List[Dict[str, Any]]:
    return get_unprocessed_data(limit=limit, intel_type="news")


def get_unprocessed_chat(limit: int = 30) -> List[Dict[str, Any]]:
    return get_unprocessed_data(limit=limit, intel_type="chat")


def get_unprocessed_chat_count() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM raw_data WHERE processed = 0 AND intel_type = 'chat'"
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def mark_raw_data_processed(data_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE raw_data SET processed = 1 WHERE id = ?", (data_id,))
    conn.commit()
    conn.close()


def update_raw_data_confidence(data_id: int, confidence_score: float, confidence_rationale: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE raw_data SET confidence_score = ?, confidence_rationale = ? WHERE id = ?",
        (confidence_score, confidence_rationale, data_id)
    )
    conn.commit()
    conn.close()


def update_raw_data_preview(data_id: int, og_title: str = None, og_description: str = None):
    """存储链接预览的 title 和 description"""
    conn = get_connection()
    cursor = conn.cursor()
    # 新增字段（幂等）
    try:
        cursor.execute("ALTER TABLE raw_data ADD COLUMN og_title TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE raw_data ADD COLUMN og_description TEXT")
    except sqlite3.OperationalError:
        pass
    cursor.execute(
        "UPDATE raw_data SET og_title = ?, og_description = ? WHERE id = ?",
        (og_title, og_description, data_id)
    )
    conn.commit()
    conn.close()


def mark_raw_data_batch_processed(data_ids: List[int]):
    if not data_ids:
        return
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(data_ids))
    cursor.execute(f"UPDATE raw_data SET processed = 1 WHERE id IN ({placeholders})", data_ids)
    conn.commit()
    conn.close()


# --- PROCESSED INTEL ---

def insert_processed_intel(
    raw_data_id: int,
    title: str,
    summary: str,
    red_team_analysis: str,
    blue_team_analysis: str,
    synthesis: str,
    tags: str,
    team_assignment: str,
    intel_type: str = "mixed",
    batch_count: int = 0
) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO processed_intel
        (raw_data_id, title, summary, red_team_analysis, blue_team_analysis, synthesis, tags, team_assignment, intel_type, batch_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (raw_data_id, title, summary, red_team_analysis, blue_team_analysis, synthesis, tags, team_assignment, intel_type, batch_count)
    )
    last_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return last_id


def get_pending_intel_by_team(team: str, limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM processed_intel WHERE team_assignment = ? AND user_approved = 0 ORDER BY created_at DESC LIMIT ?",
        (team, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_center_intel_today() -> List[Dict[str, Any]]:
    """Get all center intel created today."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM processed_intel WHERE team_assignment = 'center' AND DATE(created_at, 'localtime') = DATE('now', 'localtime') ORDER BY created_at DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_center_intel_by_date(date_str: str) -> List[Dict[str, Any]]:
    """Get all center intel for a specific date (YYYY-MM-DD)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM processed_intel WHERE team_assignment = 'center' AND DATE(created_at, 'localtime') = ? ORDER BY created_at DESC",
        (date_str,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_intel_by_id(intel_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM processed_intel WHERE id = ?", (intel_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_processed_intel_by_ids(intel_ids: List[int]):
    """Delete processed intel entries by their IDs."""
    if not intel_ids:
        return
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(intel_ids))
    cursor.execute(f"DELETE FROM processed_intel WHERE id IN ({placeholders})", intel_ids)
    conn.commit()
    conn.close()


def delete_center_intel_by_date(date_str: str) -> int:
    """Delete all center intel for a specific date. Returns count of deleted rows."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM processed_intel WHERE team_assignment = 'center' AND DATE(created_at, 'localtime') = ?",
        (date_str,)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def approve_and_memorize_intel(intel_id: int, team: str):
    intel = get_intel_by_id(intel_id)
    if not intel:
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT source FROM raw_data WHERE id = ?", (intel['raw_data_id'],))
    raw_data = cursor.fetchone()
    source = raw_data['source'] if raw_data else "Unknown"

    cursor.execute("UPDATE processed_intel SET user_approved = 1 WHERE id = ?", (intel_id,))

    context = intel['red_team_analysis'] if team == 'red' else intel['blue_team_analysis']
    full_memory_context = f"Source summary: {intel['summary']}\nAnalysis: {context}"

    cursor.execute(
        "INSERT INTO memory (team, key_concept, source, context) VALUES (?, ?, ?, ?)",
        (team, intel['title'], source, full_memory_context)
    )

    conn.commit()
    conn.close()


# --- DAILY SUMMARY ---

def insert_daily_summary(date: str, content: str, source_hint: str = None, raw_count: int = 0) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO daily_summary (date, content, source_hint, raw_count) VALUES (?, ?, ?, ?)",
        (date, content, source_hint, raw_count)
    )
    last_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return last_id


def get_daily_summaries(days: int = 7) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM daily_summary ORDER BY date DESC LIMIT ?",
        (days,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_daily_summary_by_date(date: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM daily_summary WHERE date = ?", (date,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# --- MEMORY ---

def insert_memory(team: str, key_concept: str, context: str, source: str = "Manual") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO memory (team, key_concept, source, context) VALUES (?, ?, ?, ?)",
        (team, key_concept, source, context)
    )
    last_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return last_id


def get_memory_by_team(team: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM memory WHERE team = ? ORDER BY created_at DESC", (team,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_memory(memory_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM memory WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()


def update_memory(memory_id: int, key_concept: str, context: str, source: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    if source:
        cursor.execute(
            "UPDATE memory SET key_concept = ?, context = ?, source = ? WHERE id = ?",
            (key_concept, context, source, memory_id)
        )
    else:
        cursor.execute(
            "UPDATE memory SET key_concept = ?, context = ? WHERE id = ?",
            (key_concept, context, memory_id)
        )
    conn.commit()
    conn.close()


def reset_all_data() -> dict:
    """Delete all data from all tables (keeps schema intact). Returns counts."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM raw_data")
    raw_count = cursor.fetchone()[0]
    cursor.execute("DELETE FROM raw_data")

    cursor.execute("SELECT COUNT(*) FROM processed_intel")
    intel_count = cursor.fetchone()[0]
    cursor.execute("DELETE FROM processed_intel")

    cursor.execute("SELECT COUNT(*) FROM memory")
    memory_count = cursor.fetchone()[0]
    cursor.execute("DELETE FROM memory")

    cursor.execute("SELECT COUNT(*) FROM daily_summary")
    summary_count = cursor.fetchone()[0]
    cursor.execute("DELETE FROM daily_summary")

    conn.commit()
    conn.close()

    return {
        "raw_data": raw_count,
        "processed_intel": intel_count,
        "memory": memory_count,
        "daily_summary": summary_count,
    }


# --- SOURCE CONFIDENCE ---

def get_all_source_confidence() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM source_confidence ORDER BY tier DESC, source_key ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_source_confidence_by_key(source_key: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM source_confidence WHERE source_key = ?", (source_key,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_source_confidence(source_key: str, anchor: float, tier: str, notes: str = "") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO source_confidence (source_key, anchor, tier, notes, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(source_key) DO UPDATE SET
            anchor = excluded.anchor,
            tier = excluded.tier,
            notes = excluded.notes,
            updated_at = CURRENT_TIMESTAMP
        """,
        (source_key, anchor, tier, notes)
    )
    last_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return last_id


def delete_source_confidence(entry_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM source_confidence WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
