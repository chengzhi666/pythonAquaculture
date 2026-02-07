import os
import sqlite3
from datetime import datetime

# 项目根目录 = 当前文件的上一层的上一层
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "intel.db")


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    """初始化数据库，建表（只需跑一次，或在程序启动时调用）"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS intel_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        content TEXT,
        pub_time TEXT,
        region TEXT,
        org TEXT,
        source_type TEXT,
        source_url TEXT UNIQUE,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    conn.commit()
    conn.close()
def save_items(items: list[dict]):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")

    for it in items:
        cur.execute("""
        INSERT INTO intel_item
        (title, content, pub_time, region, org, source_type, source_url, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_url) DO UPDATE SET
            title=excluded.title,
            content=excluded.content,
            pub_time=excluded.pub_time,
            region=excluded.region,
            org=excluded.org,
            source_type=excluded.source_type,
            updated_at=excluded.updated_at
        """, (
            it.get("title", ""),
            it.get("content", ""),
            it.get("pub_time", ""),
            it.get("region", ""),
            it.get("org", ""),
            it.get("source_type", ""),
            it.get("source_url", ""),
            now,
            now
        ))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("数据库和表初始化完成，路径：", DB_PATH)