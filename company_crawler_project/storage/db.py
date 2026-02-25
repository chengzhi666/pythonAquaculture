import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "intel.db"


def get_conn(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target = db_path or DB_PATH
    conn = sqlite3.connect(str(target))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    conn = get_conn(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS intel_item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                pub_time TEXT,
                region TEXT,
                org TEXT,
                source_type TEXT,
                source_url TEXT UNIQUE,
                tags TEXT,
                extra TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_intel_pub_time ON intel_item(pub_time DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_intel_source_type ON intel_item(source_type)")
        conn.commit()
    finally:
        conn.close()


def save_items(items: list[dict[str, Any]], db_path: Optional[Path] = None) -> int:
    if not items:
        return 0

    conn = get_conn(db_path)
    now = datetime.now().isoformat(timespec="seconds")
    saved = 0

    try:
        cur = conn.cursor()
        cur.execute("BEGIN TRANSACTION")
        for item in items:
            source_url = (item.get("source_url") or "").strip()
            if not source_url:
                logger.warning("Skip item without source_url: %s", item.get("title", ""))
                continue

            tags = json.dumps(item.get("tags", []), ensure_ascii=False)
            extra = json.dumps(item.get("extra", {}), ensure_ascii=False)

            cur.execute(
                """
                INSERT INTO intel_item
                (title, content, pub_time, region, org, source_type, source_url, tags, extra, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_url) DO UPDATE SET
                    title=excluded.title,
                    content=excluded.content,
                    pub_time=excluded.pub_time,
                    region=excluded.region,
                    org=excluded.org,
                    source_type=excluded.source_type,
                    tags=excluded.tags,
                    extra=excluded.extra,
                    updated_at=excluded.updated_at
                """,
                (
                    item.get("title", ""),
                    item.get("content", ""),
                    item.get("pub_time", ""),
                    item.get("region", ""),
                    item.get("org", ""),
                    item.get("source_type", ""),
                    source_url,
                    tags,
                    extra,
                    now,
                    now,
                ),
            )
            saved += 1

        conn.commit()
        return saved
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
