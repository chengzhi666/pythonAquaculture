"""crawlers/utils.py 与 storage/db._normalize_pub_time 单元测试"""

import pytest

from crawlers.utils import (
    clean_text,
    create_session,
    extract_date,
    extract_keywords,
    normalize_url,
)
from storage.db import _normalize_pub_time


# ==================== clean_text ====================


class TestCleanText:
    def test_none_returns_empty(self):
        assert clean_text(None) == ""

    def test_empty_string(self):
        assert clean_text("") == ""

    def test_strips_whitespace(self):
        assert clean_text("  hello  world  ") == "hello world"

    def test_replaces_fullwidth_space(self):
        assert clean_text("A\u3000B") == "A B"

    def test_replaces_newlines(self):
        assert clean_text("line1\nline2\nline3") == "line1 line2 line3"

    def test_collapses_multiple_spaces(self):
        assert clean_text("a   b    c") == "a b c"


# ==================== extract_keywords ====================


class TestExtractKeywords:
    def test_empty_input(self):
        assert extract_keywords("") == []

    def test_simple_semicolon(self):
        assert extract_keywords("水产;养殖;技术") == ["水产", "养殖", "技术"]

    def test_comma_separated(self):
        assert extract_keywords("A,B,C") == ["A", "B", "C"]

    def test_strips_keyword_prefix(self):
        result = extract_keywords("关键词：水产;养殖")
        assert result == ["水产", "养殖"]

    def test_strips_english_keyword_prefix(self):
        result = extract_keywords("keywords: fish;aquaculture")
        assert result == ["fish", "aquaculture"]


# ==================== extract_date ====================


class TestExtractDate:
    def test_standard_date(self):
        assert extract_date("发布于 2026-02-10") == "2026-02-10"

    def test_no_date_returns_none(self):
        assert extract_date("没有日期信息") is None

    def test_date_in_middle(self):
        assert extract_date("date:2025-01-15 ok") == "2025-01-15"


# ==================== normalize_url ====================


class TestNormalizeUrl:
    def test_none_returns_empty(self):
        assert normalize_url(None) == ""

    def test_empty_returns_empty(self):
        assert normalize_url("") == ""

    def test_absolute_http(self):
        assert normalize_url("http://example.com/a") == "http://example.com/a"

    def test_absolute_https(self):
        assert normalize_url("https://example.com/b") == "https://example.com/b"

    def test_protocol_relative(self):
        assert normalize_url("//example.com/c") == "https://example.com/c"

    def test_root_path_with_base(self):
        result = normalize_url("/path/page", base_url="https://example.com/old")
        assert result == "https://example.com/path/page"

    def test_relative_with_base(self):
        result = normalize_url("page.html", base_url="https://example.com/dir/")
        assert result == "https://example.com/dir/page.html"


# ==================== _normalize_pub_time ====================


class TestNormalizePubTime:
    def test_none_returns_empty(self):
        assert _normalize_pub_time(None) == ""

    def test_empty_string(self):
        assert _normalize_pub_time("") == ""

    def test_standard_iso(self):
        assert _normalize_pub_time("2026-02-10") == "2026-02-10 00:00:00"

    def test_with_time(self):
        assert _normalize_pub_time("2026-02-10 08:30:00") == "2026-02-10 08:30:00"

    def test_chinese_date(self):
        assert _normalize_pub_time("2026年2月10日") == "2026-02-10 00:00:00"

    def test_slash_date(self):
        assert _normalize_pub_time("2025/12/31") == "2025-12-31 00:00:00"

    def test_dot_date(self):
        assert _normalize_pub_time("2025.06.15") == "2025-06-15 00:00:00"

    def test_iso_with_t_and_z(self):
        assert _normalize_pub_time("2025-03-01T14:30:00Z") == "2025-03-01 14:30:00"

    def test_garbage_returns_empty(self):
        assert _normalize_pub_time("不是日期") == ""

    def test_partial_date_year_month_only(self):
        result = _normalize_pub_time("2026-03")
        # 应返回补全后的日期或空（取决于实现）
        assert result in ("2026-03-01 00:00:00", "")


# ==================== create_session ====================


class TestCreateSession:
    def test_returns_session_with_ua(self):
        session = create_session()
        ua = session.headers.get("User-Agent", "")
        assert "Mozilla" in ua

    def test_returns_session_with_retry_adapter(self):
        session = create_session(retries=2)
        adapter = session.get_adapter("https://example.com")
        assert adapter.max_retries.total == 2
