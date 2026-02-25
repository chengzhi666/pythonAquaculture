"""SalmonDataEnricher 端到端测试

覆盖品种识别、规格提取、产地标准化、存储方式/认证/营养提取、
价格每公斤计算以及 enrich() 全字段端到端串联。
"""

import pytest

from fish_intel_mvp.common.extract_rules import (
    OriginExtractor,
    ProductTypeExtractor,
    SalmonDataEnricher,
    SpecExtractor,
)

# ==================== 品种识别 ====================


class TestProductTypeChain:
    """品种识别完整链路"""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.extractor = ProductTypeExtractor(
            rule_rows=[
                {
                    "id": 1,
                    "product_type": "king_salmon",
                    "pattern": r"帝王鲑|帝王三文鱼|king\s*salmon|chinook",
                    "priority": 10,
                    "confidence": 0.98,
                },
                {
                    "id": 2,
                    "product_type": "rainbow_trout",
                    "pattern": r"虹鳟|rainbow\s*trout",
                    "priority": 20,
                    "confidence": 0.98,
                },
                {
                    "id": 3,
                    "product_type": "salmon_generic",
                    "pattern": r"三文鱼|salmon",
                    "priority": 90,
                    "confidence": 0.70,
                },
            ]
        )

    def test_king_salmon_chinese(self):
        result = self.extractor.extract(title="挪威进口帝王鲑刺身 500g")
        assert result["product_type"] == "king_salmon"
        assert result["product_type_confidence"] == 0.98

    def test_rainbow_trout_chinese(self):
        result = self.extractor.extract(title="青海冷水虹鳟切片 1kg")
        assert result["product_type"] == "rainbow_trout"

    def test_generic_salmon_fallback(self):
        result = self.extractor.extract(title="新鲜三文鱼柳 300g")
        assert result["product_type"] == "salmon_generic"
        assert result["product_type_confidence"] == 0.70

    def test_no_match_returns_empty_or_unknown(self):
        result = self.extractor.extract(title="有机蔬菜套餐")
        assert result["product_type"] in ("", "unknown")


# ==================== 规格提取 ====================


class TestSpecChain:
    """规格解析链"""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.extractor = SpecExtractor(rule_rows=[])

    def test_gram_with_pack(self):
        result = self.extractor.extract(title="虹鳟冷冻切片 500g*2袋")
        assert result["spec_weight_value"] == 500.0
        assert result["spec_pack_count"] == 2
        assert result["spec_total_weight_grams"] == 1000.0

    def test_kg_single(self):
        result = self.extractor.extract(title="帝王鲑整条 1.5kg")
        assert result["spec_weight_unit"] == "kg"
        assert result["spec_weight_grams"] == 1500.0

    def test_jin_unit(self):
        result = self.extractor.extract(title="虹鳟鱼 3斤装")
        assert result["spec_weight_grams"] == 1500.0

    def test_no_spec_empty(self):
        result = self.extractor.extract(title="新鲜三文鱼")
        assert result.get("spec_weight_value") is None


# ==================== 产地标准化 ====================


class TestOriginChain:
    """产地标准化链路"""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.extractor = OriginExtractor(
            rule_rows=[
                {
                    "id": 10,
                    "pattern": "智利",
                    "normalized_country": "智利",
                    "normalized_province": None,
                    "normalized_city": None,
                    "normalized_origin": "智利",
                    "priority": 10,
                },
                {
                    "id": 11,
                    "pattern": "青海",
                    "normalized_country": "中国",
                    "normalized_province": "青海",
                    "normalized_city": None,
                    "normalized_origin": "中国-青海",
                    "priority": 40,
                },
            ]
        )

    def test_chile_import(self):
        result = self.extractor.extract(title="智利进口帝王鲑")
        assert result["origin_country"] == "智利"
        assert result["origin_standardized"] == "智利"

    def test_qinghai_domestic(self):
        result = self.extractor.extract(title="青海冷水虹鳟")
        assert result["origin_country"] == "中国"
        assert result["origin_province"] == "青海"

    def test_no_origin_info(self):
        result = self.extractor.extract(title="三文鱼切片")
        # 无匹配，产地为空
        assert not result.get("origin_standardized")


# ==================== 存储方式 ====================


class TestStorageMethod:
    def test_frozen(self):
        assert SalmonDataEnricher._extract_storage_method("冷冻虹鳟切片") == "frozen"

    def test_ice_fresh(self):
        assert SalmonDataEnricher._extract_storage_method("冰鲜三文鱼") == "ice_fresh"

    def test_live_fresh(self):
        assert SalmonDataEnricher._extract_storage_method("鲜活虹鳟") == "live_fresh"

    def test_none(self):
        assert SalmonDataEnricher._extract_storage_method("帝王鲑干货") is None


# ==================== 认证标识 ====================


class TestCertFlags:
    def test_asc_cert(self):
        flags = SalmonDataEnricher._extract_cert_flags("ASC认证 三文鱼柳")
        assert flags["cert_asc"] == 1

    def test_organic(self):
        flags = SalmonDataEnricher._extract_cert_flags("有机虹鳟鱼排")
        assert flags["cert_organic"] == 1

    def test_no_cert(self):
        flags = SalmonDataEnricher._extract_cert_flags("普通三文鱼")
        assert all(v == 0 for v in flags.values())


# ==================== enrich() 全字段端到端 ====================


class TestEnrichEndToEnd:
    """模拟真实淘宝商品标题，验证 enrich() 全字段串联"""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.enricher = SalmonDataEnricher()

    def test_full_enrich_king_salmon(self):
        item = {
            "title": "智利进口帝王鲑刺身 冷冻 ASC认证 500g*2袋",
            "keyword": "帝王鲑",
            "price": 298.0,
            "province": None,
            "city": None,
        }
        result = self.enricher.enrich(item)

        # 品种
        assert result["product_type"] == "king_salmon"
        assert result["product_type_confidence"] >= 0.9

        # 规格
        assert result["spec_weight_value"] == 500.0
        assert result["spec_pack_count"] == 2
        assert result["spec_total_weight_grams"] == 1000.0

        # 产地
        assert result["origin_country"] == "智利"

        # 存储方式
        assert result["storage_method"] == "frozen"

        # 认证
        assert result["cert_asc"] == 1

        # 价格每公斤
        assert result["price_per_kg"] is not None
        assert result["price_per_kg"] == 298.0  # 298 / (1000g / 1000) = 298

    def test_full_enrich_rainbow_trout(self):
        item = {
            "title": "青海冷水虹鳟 冰鲜 1.5kg 有机认证",
            "keyword": "虹鳟",
            "price": 189.0,
            "province": "青海",
            "city": "西宁",
        }
        result = self.enricher.enrich(item)

        assert result["product_type"] == "rainbow_trout"
        assert result["origin_province"] == "青海"
        assert result["storage_method"] == "ice_fresh"
        assert result["cert_organic"] == 1
        assert result["is_wild"] == 0

    def test_price_per_kg_when_no_spec(self):
        item = {
            "title": "三文鱼柳",
            "keyword": "三文鱼",
            "price": 99.0,
        }
        result = self.enricher.enrich(item)
        assert result["price_per_kg"] is None

    def test_wild_flag(self):
        item = {"title": "野生帝王鲑 1kg", "keyword": "帝王鲑", "price": 500}
        result = self.enricher.enrich(item)
        assert result["is_wild"] == 1

    def test_fresh_flag(self):
        item = {"title": "鲜虹鳟鱼排 500g", "keyword": "虹鳟", "price": 120}
        result = self.enricher.enrich(item)
        assert result["is_fresh"] == 1
