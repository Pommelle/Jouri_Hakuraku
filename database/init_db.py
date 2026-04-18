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
        key_concept TEXT NOT NULL,
        source TEXT,
        context TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

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

    # 新增字段（幂等，忽略已存在的报错）
    try:
        cursor.execute("ALTER TABLE raw_data ADD COLUMN confidence_score REAL DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE raw_data ADD COLUMN confidence_rationale TEXT DEFAULT NULL")
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

    # 插入默认名单
    default_entries = [
        ("reuters", 0.95, "high", "International wire service, very high credibility"),
        ("ap_news", 0.95, "high", "Associated Press wire service"),
        ("bloomberg", 0.92, "high", "Financial and business news authority"),
        ("bbc", 0.90, "high", "British Broadcasting Corporation"),
        ("nyt", 0.88, "high", "New York Times"),
        ("wsj", 0.88, "high", "Wall Street Journal"),
        ("washpost", 0.87, "high", "Washington Post"),
        ("defense_one", 0.88, "high", "Defense news outlet"),
        ("breaking defense", 0.88, "high", "Defense industry news"),
        ("krebsonsecurity", 0.90, "high", "Brian Krebs - security journalist"),
        ("bleepingcomputer", 0.85, "high", "Major cybersecurity news site"),
        ("arstechnica", 0.85, "high", "Technology and security news"),
        ("cisa", 0.95, "high", "Cybersecurity and Infrastructure Security Agency"),
        ("nist", 0.95, "high", "National Institute of Standards and Technology"),
        ("nvd", 0.95, "high", "NIST National Vulnerability Database"),
        ("reddit", 0.50, "medium", "User-generated, variable quality"),
        ("hacker news", 0.55, "medium", "Tech community aggregator"),
        ("lobste", 0.60, "medium", "Tech community links aggregator"),
        ("twitter", 0.45, "medium", "Microblog, mixed credibility"),
        ("x.com", 0.45, "medium", "Microblog, mixed credibility"),
        ("discord", 0.50, "medium", "Chat platform, variable sources"),
        ("telegram", 0.45, "medium", "Messaging platform, unverified channels common"),
        ("facebook", 0.35, "medium", "Social media, high misinformation rate"),
        ("tiktok", 0.30, "medium", "Short video platform, low fact-checking"),
        ("trump", 0.25, "low", "Known for false and misleading statements"),
        ("donald", 0.25, "low", "Known for false and misleading statements"),
        ("elon", 0.30, "low", "Occasional misinformation, verify independently"),
        ("4chan", 0.20, "low", "Anonymous imageboard, low credibility"),
        ("parler", 0.20, "low", "Social platform with low fact-checking"),
        ("gab", 0.15, "low", "Social platform with low moderation"),
        ("zerohedge", 0.30, "low", "Known for sensationalist and unverified claims"),
        ("infowars", 0.10, "low", "Conspiracy and misinformation site"),
        ("naturalnews", 0.10, "low", "Health misinformation site"),
        ("beforeitsnews", 0.10, "low", "Conspiracy content site"),
        ("anonymous", 0.25, "low", "Unknown source, unverifiable"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO source_confidence (source_key, anchor, tier, notes) VALUES (?, ?, ?, ?)",
        default_entries
    )

    conn.commit()
    conn.close()
    print("Database initialized successfully with new schema.")

if __name__ == "__main__":
    init_db()
