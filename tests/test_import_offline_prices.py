"""import_offline_prices.py 单元测试

覆盖: 表头映射、行解析、数据校验、CSV解析、品种推断、upsert SQL 生成。
不连接真实数据库。
"""

from datetime import datetime
from io import StringIO

import pytest

from fish_intel_mvp.jobs.import_offline_prices import (
    SOURCE_NAME_DEFAULT,
    ValidationError,
    _build_header_map,
    _guess_storage,
    _infer_product_type,
    _parse_datetime,
    _parse_float,
    parse_csv,
    row_to_snapshot,
    validate_row,
)

# ==================== 表头映射 ====================


class TestBuildHeaderMap:
    def test_english_headers(self):
        headers = ["source_name", "market_name", "region", "product_name_raw", "price", "unit"]
        m = _build_header_map(headers)
        assert m["source_name"] == 0
        assert m["market_name"] == 1
        assert m["product_name_raw"] == 3
        assert m["price"] == 4

    def test_chinese_headers(self):
        headers = ["数据来源", "市场", "地区", "品名", "均价", "单位", "日期"]
        m = _build_header_map(headers)
        assert m["source_name"] == 0
        assert m["market_name"] == 1
        assert m["product_name_raw"] == 3
        assert m["price"] == 4
        assert m["date_str"] == 6

    def test_mixed_headers(self):
        headers = ["source_name", "批发市场", "品种名称", "avg_price", "规格", "备注"]
        m = _build_header_map(headers)
        assert m["source_name"] == 0
        assert m["market_name"] == 1
        assert m["product_name_raw"] == 2
        assert m["price"] == 3
        assert m["spec"] == 4
        assert m["remark"] == 5

    def test_bom_handling(self):
        headers = ["\ufeff品名", "价格"]
        m = _build_header_map(headers)
        assert m["product_name_raw"] == 0
        assert m["price"] == 1


# ==================== 数据校验 ====================


class TestValidateRow:
    def test_valid_row(self):
        row = {"product_name_raw": "虹鳟", "price": "50.0"}
        assert validate_row(row, 1) == []

    def test_missing_product_name(self):
        row = {"product_name_raw": "", "price": "50.0"}
        errors = validate_row(row, 1)
        assert len(errors) == 1
        assert errors[0].field == "product_name_raw"

    def test_missing_all_prices(self):
        row = {"product_name_raw": "虹鳟", "price": "", "min_price": "", "max_price": ""}
        errors = validate_row(row, 2)
        assert any(e.field == "price" for e in errors)

    def test_negative_price(self):
        row = {"product_name_raw": "虹鳟", "price": "-5"}
        errors = validate_row(row, 3)
        assert any("负" in e.message for e in errors)

    def test_extreme_price(self):
        row = {"product_name_raw": "虹鳟", "price": "999999"}
        errors = validate_row(row, 4)
        assert any("异常高" in e.message for e in errors)

    def test_min_greater_than_max(self):
        row = {"product_name_raw": "虹鳟", "price": "50", "min_price": "60", "max_price": "40"}
        errors = validate_row(row, 5)
        assert any("最低价" in e.message for e in errors)

    def test_valid_with_min_max_only(self):
        row = {"product_name_raw": "虹鳟", "price": "", "min_price": "40", "max_price": "60"}
        assert validate_row(row, 6) == []


# ==================== _parse_float ====================


class TestParseFloat:
    def test_normal(self):
        assert _parse_float("50.00") == 50.0

    def test_with_comma(self):
        assert _parse_float("1,234.5") == 1234.5

    def test_empty(self):
        assert _parse_float("") is None

    def test_none(self):
        assert _parse_float(None) is None

    def test_text(self):
        assert _parse_float("N/A") is None


# ==================== _parse_datetime ====================


class TestParseDatetime:
    def test_date_only(self):
        dt = _parse_datetime("2026-02-25")
        assert dt == datetime(2026, 2, 25)

    def test_datetime(self):
        dt = _parse_datetime("2026-02-25 08:30:00")
        assert dt == datetime(2026, 2, 25, 8, 30, 0)

    def test_slash_format(self):
        dt = _parse_datetime("2026/02/25")
        assert dt == datetime(2026, 2, 25)

    def test_compact(self):
        dt = _parse_datetime("20260225")
        assert dt == datetime(2026, 2, 25)

    def test_empty(self):
        assert _parse_datetime("") is None

    def test_invalid(self):
        assert _parse_datetime("not-a-date") is None


# ==================== _infer_product_type ====================


class TestInferProductType:
    def test_king_salmon(self):
        assert _infer_product_type("帝王鲑 冷冻") == "king_salmon"

    def test_rainbow_trout(self):
        assert _infer_product_type("虹鳟鱼 冰鲜") == "rainbow_trout"

    def test_generic_salmon(self):
        assert _infer_product_type("三文鱼") == "salmon_generic"

    def test_other(self):
        assert _infer_product_type("草鱼") == "aquatic_other"


# ==================== _guess_storage ====================


class TestGuessStorage:
    def test_frozen(self):
        assert _guess_storage("冷冻虹鳟") == "frozen"

    def test_ice_fresh(self):
        assert _guess_storage("冰鲜三文鱼") == "ice_fresh"

    def test_fresh(self):
        assert _guess_storage("鲜活草鱼") == "fresh"

    def test_none(self):
        assert _guess_storage("进口切块") is None


# ==================== row_to_snapshot ====================


class TestRowToSnapshot:
    def test_full_row(self):
        headers = [
            "品名",
            "市场",
            "地区",
            "均价",
            "最低价",
            "最高价",
            "单位",
            "日期",
            "规格",
            "备注",
        ]
        header_map = _build_header_map(headers)
        cells = [
            "虹鳟 冰鲜",
            "北京新发地",
            "北京",
            "50.00",
            "45.00",
            "55.00",
            "元/公斤",
            "2026-02-25",
            "3-5kg",
            "进口",
        ]
        snapshot, errors = row_to_snapshot(cells, header_map, row_num=2)
        assert errors == []
        assert snapshot is not None
        assert snapshot["product_name_raw"] == "虹鳟 冰鲜"
        assert snapshot["price"] == 50.0
        assert snapshot["min_price"] == 45.0
        assert snapshot["max_price"] == 55.0
        assert snapshot["product_type"] == "rainbow_trout"
        assert snapshot["storage_method"] == "ice_fresh"
        assert snapshot["snapshot_time"] == datetime(2026, 2, 25)

    def test_avg_computed_from_min_max(self):
        headers = ["品名", "最低价", "最高价"]
        header_map = _build_header_map(headers)
        cells = ["帝王鲑", "120", "140"]
        snapshot, errors = row_to_snapshot(cells, header_map, row_num=2)
        assert errors == []
        assert snapshot["price"] == 130.0

    def test_validation_failure(self):
        headers = ["品名", "均价"]
        header_map = _build_header_map(headers)
        cells = ["", "50"]  # empty product name
        snapshot, errors = row_to_snapshot(cells, header_map, row_num=2)
        assert snapshot is None
        assert len(errors) > 0

    def test_fallback_snapshot_time(self):
        headers = ["品名", "均价"]
        header_map = _build_header_map(headers)
        cells = ["虹鳟", "50"]
        fallback = datetime(2026, 1, 1, 12, 0, 0)
        snapshot, _ = row_to_snapshot(cells, header_map, row_num=2, fallback_snapshot_time=fallback)
        assert snapshot["snapshot_time"] == fallback


# ==================== parse_csv ====================


class TestParseCsv:
    def test_simple_csv(self):
        csv_text = (
            "品名,市场,均价,日期\n"
            "虹鳟 冰鲜,北京新发地,50.00,2026-02-25\n"
            "帝王鲑 冷冻,上海江阳,130.00,2026-02-25\n"
        )
        rows, errors = parse_csv(StringIO(csv_text))
        assert len(rows) == 2
        assert len(errors) == 0
        assert rows[0]["product_name_raw"] == "虹鳟 冰鲜"
        assert rows[0]["price"] == 50.0
        assert rows[1]["product_type"] == "king_salmon"

    def test_skip_blank_rows(self):
        csv_text = "品名,均价\n" "虹鳟,50\n" ",,\n" "帝王鲑,130\n"
        rows, errors = parse_csv(StringIO(csv_text))
        assert len(rows) == 2

    def test_validation_errors_collected(self):
        csv_text = (
            "品名,均价\n"
            ",50\n"  # missing product name
            "虹鳟,60\n"
        )
        rows, errors = parse_csv(StringIO(csv_text))
        assert len(rows) == 1  # only the valid row
        assert len(errors) == 1  # one validation error

    def test_empty_csv(self):
        rows, errors = parse_csv(StringIO(""))
        assert rows == []
        assert len(errors) == 1
        assert errors[0].field == "header"

    def test_header_only(self):
        rows, errors = parse_csv(StringIO("品名,均价\n"))
        assert rows == []
        assert errors == []

    def test_english_headers(self):
        csv_text = (
            "product_name_raw,market_name,price,date_str\n"
            "rainbow trout,Beijing Xinfadi,50.00,2026-02-25\n"
        )
        rows, errors = parse_csv(StringIO(csv_text))
        assert len(rows) == 1
        assert rows[0]["product_name_raw"] == "rainbow trout"

    def test_source_name_override(self):
        csv_text = "品名,均价\n虹鳟,50\n"
        rows, _ = parse_csv(StringIO(csv_text), source_name="my_source")
        assert rows[0]["source_name"] == "my_source"

    def test_source_name_from_csv_column(self):
        csv_text = "数据来源,品名,均价\nmoa_test,虹鳟,50\n"
        rows, _ = parse_csv(StringIO(csv_text))
        assert rows[0]["source_name"] == "moa_test"
