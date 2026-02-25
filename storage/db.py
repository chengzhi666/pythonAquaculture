import json
import logging
import os
import re
import sqlite3
from datetime import datetime
from typing import Any

# 配置日志
logger = logging.getLogger(__name__)

# 项目根目录 = 当前文件的上一层的上一层
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "intel.db")
SUPPORTED_BACKENDS = {"mysql", "sqlite"}
DEFAULT_BACKEND = "mysql"


def _get_backend() -> str:
    backend = os.getenv("STORAGE_BACKEND", DEFAULT_BACKEND).strip().lower()
    if backend in SUPPORTED_BACKENDS:
        return backend
    logger.warning("未知 STORAGE_BACKEND=%s，回退为 %s", backend, DEFAULT_BACKEND)
    return DEFAULT_BACKEND


def get_backend() -> str:
    """返回当前存储后端。"""
    return _get_backend()


def _get_sqlite_conn():
    """获取 SQLite 连接（自动启用外键约束）"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _get_mysql_conn():
    try:
        from fish_intel_mvp.common.db import get_conn as get_mysql_conn_impl
    except ModuleNotFoundError as exc:
        raise RuntimeError("MySQL backend unavailable: fish_intel_mvp.common.db not found") from exc
    return get_mysql_conn_impl()


def get_conn():
    """
    获取当前后端连接：
    - mysql: 返回 PyMySQL 连接（DictCursor）
    - sqlite: 返回 sqlite3 连接
    """
    if _get_backend() == "mysql":
        return _get_mysql_conn()
    return _get_sqlite_conn()


def _has_column(cur, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _normalize_pub_time(value: Any) -> str:
    """
    将多种时间字符串统一为 `YYYY-MM-DD HH:MM:SS` 以支持稳定排序。
    无法解析时返回空字符串。
    """
    if value is None:
        return ""

    text = str(value).strip()
    if not text:
        return ""

    normalized = (
        text.replace("年", "-")
        .replace("月", "-")
        .replace("日", " ")
        .replace("T", " ")
        .replace("Z", "")
    )
    normalized = re.sub(r"[/.]", "-", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    try:
        # Python 3.9: 支持 `YYYY-MM-DD` 与 `YYYY-MM-DD HH:MM:SS`
        dt = datetime.fromisoformat(normalized)
        return dt.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass

    # 兜底：提取 `YYYY-M-D [H[:M[:S]]]`
    match = re.search(
        r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?(?:\s+(\d{1,2})(?::(\d{1,2}))?(?::(\d{1,2}))?)?",
        normalized,
    )
    if not match:
        return ""

    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3) or 1)
    hour = int(match.group(4) or 0)
    minute = int(match.group(5) or 0)
    second = int(match.group(6) or 0)

    try:
        dt = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return ""

    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _ensure_pub_time_norm_column(cur) -> None:
    if not _has_column(cur, "intel_item", "pub_time_norm"):
        cur.execute("ALTER TABLE intel_item ADD COLUMN pub_time_norm TEXT")


def _ensure_indexes(cur) -> None:
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_intel_pub_time_norm ON intel_item(pub_time_norm DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_intel_org_pub_time_norm ON intel_item(org, pub_time_norm DESC)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_intel_region_pub_time_norm ON intel_item(region, pub_time_norm DESC)"
    )


def _backfill_pub_time_norm(cur) -> None:
    cur.execute(
        "SELECT id, pub_time FROM intel_item WHERE pub_time_norm IS NULL OR pub_time_norm = ''"
    )
    rows = cur.fetchall()
    if not rows:
        return

    updates = [(_normalize_pub_time(pub_time), row_id) for row_id, pub_time in rows]
    cur.executemany("UPDATE intel_item SET pub_time_norm = ? WHERE id = ?", updates)
    logger.info("已回填 pub_time_norm: %d 条", len(updates))


def _init_sqlite_db() -> None:
    conn = _get_sqlite_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS intel_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            pub_time TEXT,
            pub_time_norm TEXT,
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
        _ensure_pub_time_norm_column(cur)
        _ensure_indexes(cur)
        _backfill_pub_time_norm(cur)
        conn.commit()
        logger.info("数据库初始化完成：%s", DB_PATH)
    except Exception as e:
        logger.error("数据库初始化失败：%s", e)
        raise
    finally:
        conn.close()


def _init_mysql_db() -> None:
    conn = _get_mysql_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS intel_item (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            source_type VARCHAR(64) NOT NULL,
            title TEXT NOT NULL,
            pub_time VARCHAR(32) NULL,
            org VARCHAR(255) NULL,
            region VARCHAR(64) NULL,
            content LONGTEXT NULL,
            source_url TEXT NOT NULL,
            tags_json TEXT NULL,
            extra_json TEXT NULL,
            fetched_at DATETIME NOT NULL,
            raw_id BIGINT NULL,
            UNIQUE KEY uk_source_url (source_url(150))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        )

        index_sqls = [
            "CREATE INDEX idx_intel_pub_time ON intel_item(pub_time)",
            "CREATE INDEX idx_intel_org_pub_time ON intel_item(org, pub_time)",
            "CREATE INDEX idx_intel_region_pub_time ON intel_item(region, pub_time)",
        ]
        for sql in index_sqls:
            try:
                cur.execute(sql)
            except Exception as exc:
                # MySQL 5.x 没有 IF NOT EXISTS；已存在索引时报错 1061（Duplicate key name）
                if "Duplicate key name" not in str(exc):
                    raise

        conn.commit()
        logger.info("MySQL 数据库初始化完成")
    except Exception as e:
        logger.error("MySQL 数据库初始化失败：%s", e)
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库，建表（只需跑一次，或在程序启动时调用）"""
    backend = _get_backend()
    if backend == "mysql":
        _init_mysql_db()
        return
    _init_sqlite_db()


def _save_items_sqlite(items: list[dict]) -> None:
    conn = _get_sqlite_conn()
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
            pub_time = it.get("pub_time", "")
            pub_time_norm = _normalize_pub_time(pub_time)

            try:
                cur.execute(
                    """
                INSERT INTO intel_item
                (title, content, pub_time, pub_time_norm, region, org, source_type, source_url, tags, extra, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_url) DO UPDATE SET
                    title=excluded.title,
                    content=excluded.content,
                    pub_time=excluded.pub_time,
                    pub_time_norm=excluded.pub_time_norm,
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
                        pub_time,
                        pub_time_norm,
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


def _save_items_mysql(items: list[dict]) -> None:
    conn = _get_mysql_conn()
    try:
        cur = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for it in items:
            tags_json = (
                json.dumps(it.get("tags", []), ensure_ascii=False) if it.get("tags") else "[]"
            )
            extra_json = (
                json.dumps(it.get("extra", {}), ensure_ascii=False) if it.get("extra") else "{}"
            )
            source_url = (it.get("source_url") or "").strip()
            if not source_url:
                logger.warning("跳过无 source_url 数据: title=%s", it.get("title"))
                continue

            cur.execute(
                """
            INSERT INTO intel_item(
              source_type, title, pub_time, org, region, content, source_url,
              tags_json, extra_json, fetched_at, raw_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              title=VALUES(title),
              pub_time=VALUES(pub_time),
              org=VALUES(org),
              region=VALUES(region),
              content=VALUES(content),
              tags_json=VALUES(tags_json),
              extra_json=VALUES(extra_json),
              fetched_at=VALUES(fetched_at)
            """,
                (
                    it.get("source_type", ""),
                    it.get("title", ""),
                    it.get("pub_time", ""),
                    it.get("org", ""),
                    it.get("region", ""),
                    it.get("content", ""),
                    source_url,
                    tags_json,
                    extra_json,
                    now,
                    None,
                ),
            )
        conn.commit()
        logger.info("成功保存 %d 条数据到 MySQL", len(items))
    except Exception as e:
        logger.error("MySQL 批量保存失败：%s", e)
        raise
    finally:
        conn.close()


def save_items(items: list[dict]):
    """批量保存数据项（默认 MySQL，兼容 SQLite）"""
    if not items:
        return

    backend = _get_backend()
    if backend == "mysql":
        _save_items_mysql(items)
        return
    _save_items_sqlite(items)


if __name__ == "__main__":
    init_db()
    print("数据库和表初始化完成，路径：", DB_PATH)
