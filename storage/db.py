import json
import logging
import os
import sqlite3
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

# 项目根目录 = 当前文件的上一层的上一层
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "intel.db")


def get_conn():
    """获取 SQLite 连接（自动启用外键约束）"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """初始化数据库，建表（只需跑一次，或在程序启动时调用）"""
    conn = get_conn()
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
        conn.commit()
        logger.info("数据库初始化完成：%s", DB_PATH)
    except Exception as e:
        logger.error("数据库初始化失败：%s", e)
        raise
    finally:
        conn.close()


def save_items(items: list[dict]):
    """批量保存数据项（使用事务提高性能）"""
    if not items:
        return

    conn = get_conn()
    try:
        cur = conn.cursor()
        now = datetime.now().isoformat(timespec="seconds")

        # 使用事务
        cur.execute("BEGIN TRANSACTION")

        for it in items:
            # 序列化 tags 和 extra 为 JSON 字符串
            tags_json = (
                json.dumps(it.get("tags", []), ensure_ascii=False) if it.get("tags") else "[]"
            )
            extra_json = (
                json.dumps(it.get("extra", {}), ensure_ascii=False) if it.get("extra") else "{}"
            )

            try:
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
                        it.get("title", ""),
                        it.get("content", ""),
                        it.get("pub_time", ""),
                        it.get("region", ""),
                        it.get("org", ""),
                        it.get("source_type", ""),
                        it.get("source_url", ""),
                        tags_json,
                        extra_json,
                        now,
                        now,
                    ),
                )
            except Exception as e:
                logger.warning("保存单条数据失败 - url=%s: %s", it.get("source_url"), e)

        conn.commit()
        logger.info("成功保存 %d 条数据到 %s", len(items), DB_PATH)
    except Exception as e:
        conn.rollback()
        logger.error("批量保存失败：%s", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("数据库和表初始化完成，路径：", DB_PATH)
