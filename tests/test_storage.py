"""存储模块单元测试"""

import os
import sqlite3
import tempfile

import pytest


# 使用临时数据库进行测试
@pytest.fixture
def test_db():
    """创建临时测试数据库"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
        CREATE TABLE intel_item (
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
        yield conn
        conn.close()


def test_insert_item(test_db):
    """测试插入单条记录"""
    cur = test_db.cursor()
    now = "2026-02-09T12:00:00"

    cur.execute(
        """
    INSERT INTO intel_item
    (title, content, pub_time, region, org, source_type, source_url, tags, extra, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            "测试标题",
            "测试内容",
            "2026-02-09",
            "中国",
            "测试组织",
            "TEST",
            "http://example.com",
            "[]",
            "{}",
            now,
            now,
        ),
    )
    test_db.commit()

    cur.execute("SELECT COUNT(*) FROM intel_item")
    count = cur.fetchone()[0]
    assert count == 1


def test_duplicate_handling(test_db):
    """测试去重处理"""
    cur = test_db.cursor()
    now = "2026-02-09T12:00:00"

    # 插入第一条
    cur.execute(
        """
    INSERT INTO intel_item
    (title, content, pub_time, region, org, source_type, source_url, tags, extra, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            "标题1",
            "内容1",
            "2026-02-09",
            "中国",
            "组织1",
            "TEST",
            "http://example.com/1",
            "[]",
            "{}",
            now,
            now,
        ),
    )
    test_db.commit()

    # 尝试插入相同 source_url 的记录（应该被忽略或替换）
    try:
        cur.execute(
            """
        INSERT OR IGNORE INTO intel_item
        (title, content, pub_time, region, org, source_type, source_url, tags, extra, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                "标题2",
                "内容2",
                "2026-02-10",
                "中国",
                "组织2",
                "TEST",
                "http://example.com/1",
                "[]",
                "{}",
                now,
                now,
            ),
        )
        test_db.commit()
    except sqlite3.IntegrityError:
        pass

    cur.execute("SELECT COUNT(*) FROM intel_item")
    count = cur.fetchone()[0]
    assert count == 1
