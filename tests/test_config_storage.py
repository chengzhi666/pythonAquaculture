"""配置与存储模块单元测试"""

import json
import sqlite3
import textwrap
import uuid

import pytest

import runner
import storage.db as storage_db
from config_mgr import Config
from query.cli_query import query_intel


@pytest.fixture
def isolated_sqlite_db(tmp_path, monkeypatch):
    """将 storage.db 指向临时 SQLite 文件，避免污染真实数据"""
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
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


def test_init_db_adds_pub_time_norm_and_indexes(isolated_sqlite_db):
    """初始化后应包含标准化时间字段与查询索引"""
    conn = sqlite3.connect(str(isolated_sqlite_db))
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(intel_item)")
        columns = {row[1] for row in cur.fetchall()}
        assert "pub_time_norm" in columns

        cur.execute("PRAGMA index_list(intel_item)")
        indexes = {row[1] for row in cur.fetchall()}
        assert "idx_intel_pub_time_norm" in indexes
        assert "idx_intel_org_pub_time_norm" in indexes
        assert "idx_intel_region_pub_time_norm" in indexes
    finally:
        conn.close()


def test_query_orders_by_normalized_time(isolated_sqlite_db):
    """按时间排序应优先使用标准化时间列"""
    storage_db.save_items(
        [
            {
                "title": "较早",
                "content": "",
                "pub_time": "2026年2月9日",
                "region": "中国",
                "org": "组织A",
                "source_type": "TEST",
                "source_url": "https://example.com/old",
            },
            {
                "title": "较晚",
                "content": "",
                "pub_time": "2026-02-10 08:00:00",
                "region": "中国",
                "org": "组织A",
                "source_type": "TEST",
                "source_url": "https://example.com/new",
            },
        ]
    )

    rows = query_intel(order_by="time")
    assert rows[0][5] == "https://example.com/new"

    conn = sqlite3.connect(str(isolated_sqlite_db))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT pub_time_norm FROM intel_item WHERE source_url = ?",
            ("https://example.com/old",),
        )
        pub_time_norm = cur.fetchone()[0]
        assert pub_time_norm == "2026-02-09 00:00:00"
    finally:
        conn.close()


def test_run_from_config_continues_on_source_failure(tmp_path, monkeypatch):
    """单个采集源失败时不应中断其他采集源"""
    module_name = f"tmp_sources_{uuid.uuid4().hex}"
    module_path = tmp_path / f"{module_name}.py"
    module_path.write_text(
        textwrap.dedent(
            """
            def ok_source():
                return [{"title": "ok", "source_url": "https://example.com/ok"}]

            def bad_source():
                raise RuntimeError("boom")
            """
        ),
        encoding="utf-8",
    )

    config_path = tmp_path / "sites.json"
    config_path.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "id": "ok",
                        "enabled": True,
                        "module": module_name,
                        "function": "ok_source",
                        "params": {},
                        "defaults": {"source_type": "TEST"},
                    },
                    {
                        "id": "bad",
                        "enabled": True,
                        "module": module_name,
                        "function": "bad_source",
                        "params": {},
                        "defaults": {"source_type": "TEST"},
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(runner, "init_db", lambda: None)

    items = runner.run_from_config(config_path=str(config_path), save_to_db=False)
    assert len(items) == 1
    assert items[0]["source_url"] == "https://example.com/ok"


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
    monkeypatch.setattr(Config, "STORAGE_BACKEND", "mysql", raising=False)
    monkeypatch.setattr(Config, "DB_PASS", "change_me", raising=False)

    with pytest.raises(RuntimeError):
        Config.validate()
