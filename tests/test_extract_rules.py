from fish_intel_mvp.common.extract_rules import OriginExtractor, ProductTypeExtractor, SpecExtractor


def test_product_type_extractor_hits_custom_rule():
    extractor = ProductTypeExtractor(
        rule_rows=[
            {
                "id": 11,
                "product_type": "king_salmon",
                "pattern": r"帝王鲑|king\s*salmon",
                "priority": 10,
                "confidence": 0.98,
            }
        ]
    )
    result = extractor.extract(title="挪威帝王鲑刺身 500g")
    assert result["product_type"] == "king_salmon"
    assert result["product_type_rule_id"] == 11
    assert result["product_type_confidence"] == 0.98


def test_product_type_extractor_fallback_guess():
    extractor = ProductTypeExtractor(rule_rows=[])
    result = extractor.extract(title="rainbow trout fillet")
    assert result["product_type"] == "rainbow_trout"
    assert result["product_type_confidence"] >= 0.5


def test_spec_extractor_parse_weight_and_count():
    extractor = SpecExtractor(rule_rows=[])
    result = extractor.extract(title="虹鳟冷冻切片 500g*2袋")
    assert result["spec_weight_value"] == 500.0
    assert result["spec_pack_count"] == 2
    assert result["spec_total_weight_grams"] == 1000.0
    assert result["spec_weight_normalized"] == "1000g"


def test_spec_extractor_parse_single_kg():
    extractor = SpecExtractor(rule_rows=[])
    result = extractor.extract(title="帝王鲑整条 1.5kg")
    assert result["spec_weight_value"] == 1.5
    assert result["spec_weight_unit"] == "kg"
    assert result["spec_weight_grams"] == 1500.0
    assert result["spec_total_weight_grams"] == 1500.0


def test_origin_extractor_match_rule():
    extractor = OriginExtractor(
        rule_rows=[
            {
                "id": 21,
                "pattern": "青海",
                "normalized_country": "中国",
                "normalized_province": "青海",
                "normalized_city": None,
                "normalized_origin": "中国-青海",
                "priority": 10,
            }
        ]
    )
    result = extractor.extract(title="青海冷水虹鳟")
    assert result["origin_country"] == "中国"
    assert result["origin_province"] == "青海"
    assert result["origin_standardized"] == "中国-青海"
    assert result["origin_rule_id"] == 21


def test_origin_extractor_fallback_from_province_city():
    extractor = OriginExtractor(rule_rows=[])
    result = extractor.extract(title="冷水鱼", province="新疆", city="乌鲁木齐")
    assert result["origin_country"] == "中国"
    assert result["origin_province"] == "新疆"
    assert result["origin_city"] == "乌鲁木齐"
    assert result["origin_standardized"] == "中国-新疆-乌鲁木齐"
