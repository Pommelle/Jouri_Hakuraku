import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'nexus.db')

def init_db():
    print(f"Initializing database at: {DB_PATH}")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 【补全】创建原始数据表 - 这是接收 Discord 消息的入口
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS raw_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT,
        content TEXT,
        author TEXT,
        intel_type TEXT DEFAULT 'mixed',
        source_key TEXT,
        processed INTEGER DEFAULT 0,
        confidence_score REAL,
        confidence_rationale TEXT,
        og_title TEXT,
        og_description TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 2. 【补全】创建处理后的情报表 - 这是 Agent 输出存放的地方
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS processed_intel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_data_id INTEGER,
        title TEXT,
        summary TEXT,
        red_team_analysis TEXT,
        blue_team_analysis TEXT,
        synthesis TEXT,
        tags TEXT,
        team_assignment TEXT,
        intel_type TEXT DEFAULT 'mixed',
        batch_count INTEGER DEFAULT 0,
        user_approved INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 3. 记忆库
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team TEXT,
        author TEXT NOT NULL,
        source TEXT,
        context TEXT,
        summarized INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 4. 汇总表
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
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS daily_summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        content TEXT NOT NULL,
        team TEXT DEFAULT 'center',
        source_hint TEXT,
        raw_count INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS overall_summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        source_hint TEXT,
        raw_count INTEGER DEFAULT 0,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 5. 置信度名单
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS source_confidence (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_key TEXT NOT NULL UNIQUE,
        anchor REAL NOT NULL,
        tier TEXT NOT NULL DEFAULT 'medium',
        notes TEXT DEFAULT '',
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()
    print("Database initialized successfully with complete schema.")

if __name__ == "__main__":
    init_db()
