"""配置与存储模块单元测试"""

import json
import sqlite3

import pytest

import storage.db as storage_db
from config_mgr import Config


@pytest.fixture
def isolated_sqlite_db(tmp_path, monkeypatch):
    """将 storage.db 指向临时 SQLite 文件，避免污染真实数据"""
    db_path = tmp_path / "intel_test.db"
    monkeypatch.setattr(storage_db, "DB_PATH", str(db_path))
    storage_db.init_db()
    return db_path


def test_save_items_insert_and_upsert(isolated_sqlite_db):
    """保存数据并验证 source_url 去重更新行为"""
    first = {
        "title": "原始标题",
        "content": "原始内容",
        "pub_time": "2026-02-10",
        "region": "中国",
        "org": "测试组织",
        "source_type": "TEST",
        "source_url": "https://example.com/a",
        "tags": ["政策"],
        "extra": {"score": 1},
    }
    second = {
        "title": "第二条",
        "content": "内容2",
        "pub_time": "2026-02-10",
        "region": "中国",
        "org": "测试组织2",
        "source_type": "TEST",
        "source_url": "https://example.com/b",
        "tags": [],
        "extra": {},
    }
    storage_db.save_items([first, second])

    updated = dict(first)
    updated["title"] = "更新后标题"
    updated["content"] = "更新后内容"
    storage_db.save_items([updated])

    conn = sqlite3.connect(str(isolated_sqlite_db))
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM intel_item")
        assert cur.fetchone()[0] == 2

        cur.execute(
            "SELECT title, tags, extra FROM intel_item WHERE source_url = ?",
            ("https://example.com/a",),
        )
        title, tags_raw, extra_raw = cur.fetchone()
        assert title == "更新后标题"
        assert json.loads(tags_raw) == ["政策"]
        assert json.loads(extra_raw) == {"score": 1}
    finally:
        conn.close()


def test_config_to_dict_redaction(monkeypatch):
    """默认导出应对敏感字段脱敏"""
    monkeypatch.setattr(Config, "DB_PASS", "secret-pass", raising=False)
    monkeypatch.setattr(Config, "TAOBAO_COOKIE", "cookie-abc", raising=False)

    plain = Config.to_dict(redact=False)
    redacted = Config.to_dict()

    assert plain["DB_PASS"] == "secret-pass"
    assert plain["TAOBAO_COOKIE"] == "cookie-abc"
    assert redacted["DB_PASS"] == "***REDACTED***"
    assert redacted["TAOBAO_COOKIE"] == "***REDACTED***"


def test_config_validate_change_me(monkeypatch):
    """DB_PASS 为 change_me 时应阻止继续运行"""
    monkeypatch.setattr(Config, "DB_PASS", "change_me", raising=False)

    with pytest.raises(RuntimeError):
        Config.validate()
