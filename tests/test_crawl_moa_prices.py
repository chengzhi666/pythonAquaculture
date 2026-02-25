"""crawl_moa_prices.py 单元测试

覆盖: HTML 表格解析、JSON 解析、品类过滤、行标准化、存储推断。
不进行真实网络请求。
"""

from datetime import datetime

import pytest

from fish_intel_mvp.jobs.crawl_moa_prices import (
    DEFAULT_AQUATIC_KEYWORDS,
    SALMON_FILTER_RE,
    SOURCE_NAME,
    _extract_float,
    _guess_storage_method,
    _infer_product_type,
    filter_aquatic_rows,
    normalize_row,
    parse_price_json,
    parse_price_table,
)

# ==================== HTML 表格解析 ====================

SAMPLE_HTML_SIMPLE = """
<html><body>
<table>
  <thead>
    <tr><th>品名</th><th>市场</th><th>最低价</th><th>最高价</th><th>均价</th><th>单位</th><th>日期</th><th>备注</th></tr>
  </thead>
  <tbody>
    <tr><td>虹鳟 冰鲜</td><td>北京新发地</td><td>45.00</td><td>55.00</td><td>50.00</td><td>元/公斤</td><td>2026-02-25</td><td>进口</td></tr>
    <tr><td>帝王三文鱼 冷冻</td><td>上海江阳</td><td>120.00</td><td>140.00</td><td>130.00</td><td>元/公斤</td><td>2026-02-25</td><td>智利产</td></tr>
    <tr><td>草鱼 活鲜</td><td>武汉白沙洲</td><td>8.00</td><td>10.00</td><td>9.00</td><td>元/公斤</td><td>2026-02-25</td><td></td></tr>
  </tbody>
</table>
</body></html>
"""

SAMPLE_HTML_NO_THEAD = """
<html><body>
<table>
  <tr><td>品种</td><td>批发市场</td><td>价格</td><td>规格</td><td>报价日期</td></tr>
  <tr><td>三文鱼</td><td>广州黄沙</td><td>88.50</td><td>4-6kg/条</td><td>2026-02-24</td></tr>
  <tr><td>鲈鱼</td><td>广州黄沙</td><td>35.00</td><td>0.5-0.8kg</td><td>2026-02-24</td></tr>
</table>
</body></html>
"""

SAMPLE_HTML_AVG_ONLY = """
<html><body>
<table>
  <tr><th>品类</th><th>均价</th><th>地区</th></tr>
  <tr><td>帝王鲑</td><td>135.5</td><td>辽宁大连</td></tr>
</table>
</body></html>
"""

SAMPLE_HTML_NO_TABLE = "<html><body><p>暂无数据</p></body></html>"

SAMPLE_HTML_EMPTY_TABLE = """
<html><body>
<table>
  <tr><th>品名</th><th>价格</th></tr>
</table>
</body></html>
"""

SAMPLE_HTML_COMPUTED_AVG = """
<html><body>
<table>
  <tr><th>品名</th><th>最低价</th><th>最高价</th></tr>
  <tr><td>虹鳟</td><td>40</td><td>60</td></tr>
</table>
</body></html>
"""


class TestParsePriceTable:
    def test_simple_table(self):
        rows = parse_price_table(SAMPLE_HTML_SIMPLE)
        assert len(rows) == 3
        assert rows[0]["product_name"] == "虹鳟 冰鲜"
        assert rows[0]["market_name"] == "北京新发地"
        assert rows[0]["avg_price"] == 50.00
        assert rows[0]["min_price"] == 45.00
        assert rows[0]["max_price"] == 55.00
        assert rows[0]["unit"] == "元/公斤"
        assert rows[0]["date"] == "2026-02-25"
        assert rows[1]["product_name"] == "帝王三文鱼 冷冻"
        assert rows[1]["avg_price"] == 130.00

    def test_no_thead(self):
        rows = parse_price_table(SAMPLE_HTML_NO_THEAD)
        assert len(rows) == 2
        assert rows[0]["product_name"] == "三文鱼"
        assert rows[0]["avg_price"] == 88.50
        assert rows[0]["spec"] == "4-6kg/条"

    def test_avg_only(self):
        rows = parse_price_table(SAMPLE_HTML_AVG_ONLY)
        assert len(rows) == 1
        assert rows[0]["product_name"] == "帝王鲑"
        assert rows[0]["avg_price"] == 135.5
        assert rows[0]["region"] == "辽宁大连"

    def test_no_table(self):
        rows = parse_price_table(SAMPLE_HTML_NO_TABLE)
        assert rows == []

    def test_empty_table(self):
        rows = parse_price_table(SAMPLE_HTML_EMPTY_TABLE)
        assert rows == []

    def test_computed_avg_from_min_max(self):
        rows = parse_price_table(SAMPLE_HTML_COMPUTED_AVG)
        assert len(rows) == 1
        assert rows[0]["product_name"] == "虹鳟"
        assert rows[0]["avg_price"] == 50.0
        assert rows[0]["min_price"] == 40.0
        assert rows[0]["max_price"] == 60.0

    def test_storage_method_detected(self):
        rows = parse_price_table(SAMPLE_HTML_SIMPLE)
        assert rows[0]["storage_method"] == "ice_fresh"  # "虹鳟 冰鲜"
        assert rows[1]["storage_method"] == "frozen"  # "帝王三文鱼 冷冻"
        assert rows[2]["storage_method"] == "fresh"  # "草鱼 活鲜"


# ==================== JSON 解析 ====================

SAMPLE_JSON_LIST = {
    "code": 0,
    "data": {
        "list": [
            {
                "prodName": "虹鳟鱼 冷冻",
                "marketName": "北京新发地",
                "minPrice": "42.0",
                "maxPrice": "58.0",
                "avgPrice": "50.0",
                "unit": "元/公斤",
                "reportDate": "2026-02-25",
            },
            {
                "prodName": "帝王鲑",
                "marketName": "大连水产",
                "avgPrice": "128.0",
                "unit": "元/公斤",
                "reportDate": "2026-02-25",
            },
        ]
    },
}

SAMPLE_JSON_FLAT = [
    {"name": "三文鱼", "price": "90.5", "date": "2026-02-24"},
]

SAMPLE_JSON_EMPTY = {"code": 0, "data": {"list": []}}


class TestParsePriceJson:
    def test_nested_data_list(self):
        rows = parse_price_json(SAMPLE_JSON_LIST)
        assert len(rows) == 2
        assert rows[0]["product_name"] == "虹鳟鱼 冷冻"
        assert rows[0]["avg_price"] == 50.0
        assert rows[0]["market_name"] == "北京新发地"
        assert rows[1]["product_name"] == "帝王鲑"

    def test_flat_list(self):
        rows = parse_price_json(SAMPLE_JSON_FLAT)
        assert len(rows) == 1
        assert rows[0]["product_name"] == "三文鱼"
        assert rows[0]["avg_price"] == 90.5

    def test_empty(self):
        rows = parse_price_json(SAMPLE_JSON_EMPTY)
        assert rows == []

    def test_computed_avg_from_min_max(self):
        data = [{"prodName": "虹鳟", "minPrice": "40", "maxPrice": "60"}]
        rows = parse_price_json(data)
        assert len(rows) == 1
        assert rows[0]["avg_price"] == 50.0

    def test_storage_method(self):
        rows = parse_price_json(SAMPLE_JSON_LIST)
        assert rows[0]["storage_method"] == "frozen"  # "虹鳟鱼 冷冻"


# ==================== 品类过滤 ====================


class TestFilterAquaticRows:
    def test_wide_filter(self):
        rows = parse_price_table(SAMPLE_HTML_SIMPLE)
        filtered = filter_aquatic_rows(rows, strict=False)
        # "虹鳟 冰鲜" 和 "帝王三文鱼 冷冻" 命中, "草鱼" 不在默认关键词里
        assert len(filtered) == 2
        names = [r["product_name"] for r in filtered]
        assert "虹鳟 冰鲜" in names
        assert "帝王三文鱼 冷冻" in names

    def test_strict_filter(self):
        rows = parse_price_table(SAMPLE_HTML_SIMPLE)
        filtered = filter_aquatic_rows(rows, strict=True)
        assert len(filtered) == 2  # 虹鳟 & 帝王三文鱼 match SALMON_FILTER_RE

    def test_custom_keywords(self):
        rows = parse_price_table(SAMPLE_HTML_SIMPLE)
        filtered = filter_aquatic_rows(rows, keywords=["草鱼"])
        assert len(filtered) == 1
        assert filtered[0]["product_name"] == "草鱼 活鲜"

    def test_empty_input(self):
        assert filter_aquatic_rows([]) == []


# ==================== 品种推断 ====================


class TestInferProductType:
    def test_king_salmon(self):
        assert _infer_product_type("帝王鲑 冷冻切片") == "king_salmon"

    def test_king_salmon_alt(self):
        assert _infer_product_type("帝王三文鱼 500g") == "king_salmon"

    def test_rainbow_trout(self):
        assert _infer_product_type("虹鳟鱼 冰鲜整条") == "rainbow_trout"

    def test_generic_salmon(self):
        assert _infer_product_type("三文鱼 冷冻") == "salmon_generic"

    def test_generic_trout(self):
        assert _infer_product_type("金鳟 活鲜") == "trout_generic"

    def test_other(self):
        assert _infer_product_type("草鱼 活鲜") == "aquatic_other"


# ==================== 存储方式推断 ====================


class TestGuessStorageMethod:
    def test_frozen(self):
        assert _guess_storage_method("冷冻三文鱼") == "frozen"

    def test_ice_fresh(self):
        assert _guess_storage_method("冰鲜虹鳟") == "ice_fresh"

    def test_fresh(self):
        assert _guess_storage_method("鲜活草鱼") == "fresh"

    def test_none(self):
        assert _guess_storage_method("进口切块") is None


# ==================== 行标准化 ====================


class TestNormalizeRow:
    def test_basic(self):
        row = {
            "product_name": "虹鳟 冰鲜",
            "market_name": "北京新发地",
            "region": "",
            "spec": "",
            "min_price": 45.0,
            "max_price": 55.0,
            "avg_price": 50.0,
            "unit": "元/公斤",
            "storage_method": "ice_fresh",
            "date": "2026-02-25",
            "remark": "",
        }
        ts = datetime(2026, 2, 25, 8, 0, 0)
        result = normalize_row(row, snapshot_time=ts)
        assert result["source_name"] == SOURCE_NAME
        assert result["product_type"] == "rainbow_trout"
        assert result["price"] == 50.0
        assert result["snapshot_time"] == ts


# ==================== _extract_float ====================


class TestExtractFloat:
    def test_normal(self):
        assert _extract_float("50.00") == 50.0

    def test_with_comma(self):
        assert _extract_float("1,234.5") == 1234.5

    def test_empty(self):
        assert _extract_float("") is None

    def test_none(self):
        assert _extract_float(None) is None

    def test_no_number(self):
        assert _extract_float("N/A") is None


# ==================== SALMON_FILTER_RE ====================


class TestSalmonFilterRegex:
    @pytest.mark.parametrize(
        "text",
        [
            "虹鳟 冰鲜",
            "帝王鲑 冷冻",
            "帝王三文鱼 切片",
            "Rainbow Trout",
            "King Salmon fillet",
            "chinook salmon",
            "三文鱼 整条",
            "大西洋鲑鱼",
        ],
    )
    def test_matches(self, text):
        assert SALMON_FILTER_RE.search(text), f"expected match for: {text}"

    @pytest.mark.parametrize("text", ["草鱼", "对虾", "鲈鱼 活鲜", "大黄鱼"])
    def test_no_match(self, text):
        assert not SALMON_FILTER_RE.search(text), f"unexpected match for: {text}"
