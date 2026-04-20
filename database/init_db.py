import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'nexus.db')

def init_db():
    print(f"Initializing database at: {DB_PATH}")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team TEXT,
        author TEXT NOT NULL,
        source TEXT,
        context TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    try:
        cursor.execute("ALTER TABLE memory ADD COLUMN summarized INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chunk_summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        team TEXT NOT NULL DEFAULT 'center',
        chunk_index INTEGER NOT NULL,
        raw_count INTEGER DEFAULT 0,
        topics TEXT,
        brief_analysis TEXT,
        source_views TEXT,
        source_confidence TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(date, team, chunk_index)
    )
    ''')
    try:
        cursor.execute("ALTER TABLE chunk_summary ADD COLUMN team TEXT NOT NULL DEFAULT 'center'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE chunk_summary ADD COLUMN source_confidence TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS daily_summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        content TEXT NOT NULL,
        team TEXT DEFAULT 'center',
        source_hint TEXT,
        raw_count INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS overall_summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        source_hint TEXT,
        raw_count INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 新增字段（幂等，忽略已存在的报错）
    try:
        cursor.execute("ALTER TABLE raw_data ADD COLUMN confidence_score REAL DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE raw_data ADD COLUMN confidence_rationale TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE raw_data ADD COLUMN source_key TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS source_confidence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_key TEXT NOT NULL UNIQUE,
        anchor REAL NOT NULL,
        tier TEXT NOT NULL DEFAULT 'medium',
        notes TEXT DEFAULT '',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()
    print("Database initialized successfully with new schema.")

if __name__ == "__main__":
    init_db()
