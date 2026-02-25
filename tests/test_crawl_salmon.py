"""crawl_salmon.py 逻辑测试

覆盖关键词加载优先级、enrich_fn 调试字段、_safe_int 健壮性。
不进行真实网络请求。
"""

import json
import os

import pytest

from fish_intel_mvp.common.extract_rules import SalmonDataEnricher
from fish_intel_mvp.jobs.crawl_salmon import (
    DEFAULT_SALMON_KEYWORDS,
    _build_enrich_fn,
    _safe_int,
    _split_env_list,
    load_salmon_keywords,
)

# ==================== _split_env_list ====================


class TestSplitEnvList:
    def test_empty(self):
        assert _split_env_list("") == []

    def test_comma_separated(self):
        assert _split_env_list("虹鳟,帝王鲑") == ["虹鳟", "帝王鲑"]

    def test_fullwidth_comma(self):
        assert _split_env_list("虹鳟，帝王鲑") == ["虹鳟", "帝王鲑"]

    def test_strips_whitespace(self):
        assert _split_env_list(" A , B , C ") == ["A", "B", "C"]


# ==================== _safe_int ====================


class TestSafeInt:
    def test_normal(self, monkeypatch):
        monkeypatch.setenv("TEST_INT_VAR", "5")
        assert _safe_int("TEST_INT_VAR", 1) == 5

    def test_invalid_returns_default(self, monkeypatch):
        monkeypatch.setenv("TEST_INT_VAR", "abc")
        assert _safe_int("TEST_INT_VAR", 3) == 3

    def test_zero_returns_one(self, monkeypatch):
        monkeypatch.setenv("TEST_INT_VAR", "0")
        assert _safe_int("TEST_INT_VAR", 1) == 1  # max(1, 0) = 1

    def test_missing_env_returns_default(self, monkeypatch):
        monkeypatch.delenv("TEST_INT_VAR", raising=False)
        assert _safe_int("TEST_INT_VAR", 2) == 2


# ==================== load_salmon_keywords ====================


class TestLoadSalmonKeywords:
    def test_env_override_takes_priority(self, monkeypatch):
        monkeypatch.setenv("TAOBAO_SALMON_KEYWORDS", "A,B")
        monkeypatch.delenv("SALMON_KEYWORDS", raising=False)
        result = load_salmon_keywords(conn=None, env_key="TAOBAO_SALMON_KEYWORDS")
        assert result == ["A", "B"]

    def test_generic_env_fallback(self, monkeypatch):
        monkeypatch.delenv("TAOBAO_SALMON_KEYWORDS", raising=False)
        monkeypatch.setenv("SALMON_KEYWORDS", "X,Y,Z")
        result = load_salmon_keywords(conn=None, env_key="TAOBAO_SALMON_KEYWORDS")
        assert result == ["X", "Y", "Z"]

    def test_default_when_no_env_no_db(self, monkeypatch):
        monkeypatch.delenv("TAOBAO_SALMON_KEYWORDS", raising=False)
        monkeypatch.delenv("SALMON_KEYWORDS", raising=False)
        result = load_salmon_keywords(conn=None, env_key="TAOBAO_SALMON_KEYWORDS")
        assert result == DEFAULT_SALMON_KEYWORDS


# ==================== _build_enrich_fn ====================


class TestBuildEnrichFn:
    def test_enrich_fn_returns_extra_json(self):
        enricher = SalmonDataEnricher()
        enrich = _build_enrich_fn(enricher)

        item = {
            "title": "智利帝王鲑 500g 冷冻",
            "keyword": "帝王鲑",
            "price": 198.0,
        }
        result = enrich(item)

        # 应包含 extra_json 调试字段
        assert "extra_json" in result
        debug = json.loads(result["extra_json"])
        assert debug["extractor"] == "salmon_rule_chain_v1"
        assert "product_type_confidence" in debug
        assert "spec_raw" in debug
        assert "origin_standardized" in debug
