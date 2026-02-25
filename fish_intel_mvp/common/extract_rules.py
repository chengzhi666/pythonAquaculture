import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

try:
    from common.db import get_conn
    from common.logger import get_logger
except ModuleNotFoundError:
    # Support direct execution: python fish_intel_mvp/common/extract_rules.py
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from common.db import get_conn
    from common.logger import get_logger

LOGGER = get_logger(__name__)

DEFAULT_RULE_RELOAD_SECONDS = 300

DEFAULT_PRODUCT_TYPE_RULES = [
    {
        "id": 0,
        "product_type": "king_salmon",
        "pattern": r"(帝王鲑|帝王三文鱼|king\s*salmon|chinook)",
        "priority": 10,
        "confidence": 0.98,
    },
    {
        "id": 0,
        "product_type": "rainbow_trout",
        "pattern": r"(虹鳟|rainbow\s*trout)",
        "priority": 20,
        "confidence": 0.98,
    },
    {
        "id": 0,
        "product_type": "salmon_generic",
        "pattern": r"(三文鱼|salmon)",
        "priority": 90,
        "confidence": 0.70,
    },
]

DEFAULT_SPEC_UNIT_RULES = [
    {
        "id": 0,
        "pattern": r"^(kg|千克|公斤)$",
        "normalized_unit": "kg",
        "gram_factor": 1000.0,
        "priority": 10,
    },
    {"id": 0, "pattern": r"^(g|克)$", "normalized_unit": "g", "gram_factor": 1.0, "priority": 20},
    {
        "id": 0,
        "pattern": r"^(斤)$",
        "normalized_unit": "jin",
        "gram_factor": 500.0,
        "priority": 30,
    },
    {
        "id": 0,
        "pattern": r"^(两)$",
        "normalized_unit": "liang",
        "gram_factor": 50.0,
        "priority": 40,
    },
    {
        "id": 0,
        "pattern": r"^(lb|lbs|磅)$",
        "normalized_unit": "lb",
        "gram_factor": 453.59237,
        "priority": 50,
    },
    {
        "id": 0,
        "pattern": r"^(oz|盎司)$",
        "normalized_unit": "oz",
        "gram_factor": 28.349523,
        "priority": 60,
    },
]

DEFAULT_ORIGIN_RULES = [
    {
        "id": 0,
        "pattern": r"智利",
        "normalized_country": "智利",
        "normalized_province": None,
        "normalized_city": None,
        "normalized_origin": "智利",
        "priority": 10,
    },
    {
        "id": 0,
        "pattern": r"挪威",
        "normalized_country": "挪威",
        "normalized_province": None,
        "normalized_city": None,
        "normalized_origin": "挪威",
        "priority": 20,
    },
    {
        "id": 0,
        "pattern": r"法罗",
        "normalized_country": "法罗群岛",
        "normalized_province": None,
        "normalized_city": None,
        "normalized_origin": "法罗群岛",
        "priority": 30,
    },
    {
        "id": 0,
        "pattern": r"青海",
        "normalized_country": "中国",
        "normalized_province": "青海",
        "normalized_city": None,
        "normalized_origin": "中国-青海",
        "priority": 40,
    },
    {
        "id": 0,
        "pattern": r"新疆",
        "normalized_country": "中国",
        "normalized_province": "新疆",
        "normalized_city": None,
        "normalized_origin": "中国-新疆",
        "priority": 50,
    },
]

DEFAULT_COUNTRY_HINTS = [
    "中国",
    "智利",
    "挪威",
    "法罗群岛",
    "冰岛",
    "丹麦",
    "加拿大",
    "俄罗斯",
]

DEFAULT_PROVINCE_HINTS = [
    "青海",
    "新疆",
    "西藏",
    "甘肃",
    "云南",
    "四川",
    "辽宁",
    "黑龙江",
    "吉林",
]

WEIGHT_PATTERNS = [
    re.compile(
        r"(?P<weight>\d+(?:\.\d+)?)\s*(?P<unit>kg|g|克|千克|公斤|斤|两|lb|lbs|磅|oz|盎司)"
        r"(?:\s*(?:x|X|×|\*)\s*(?P<count>\d{1,3}))?"
        r"(?:\s*(?P<pack_unit>袋|包|盒|尾|条|片|只|罐|份))?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<count>\d{1,3})\s*(?:x|X|×|\*)\s*"
        r"(?P<weight>\d+(?:\.\d+)?)\s*(?P<unit>kg|g|克|千克|公斤|斤|两|lb|lbs|磅|oz|盎司)"
        r"(?:\s*(?P<pack_unit>袋|包|盒|尾|条|片|只|罐|份))?",
        re.IGNORECASE,
    ),
]

PACK_COUNT_PATTERN = re.compile(r"(?P<count>\d{1,3})\s*(?P<pack_unit>袋|包|盒|尾|条|片|只|罐|份)")


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coalesce_str(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _compose_origin(country: str, province: str, city: str) -> str:
    parts = [p for p in [country, province, city] if p]
    return "-".join(parts)


def _normalize_weight_text(grams: Optional[float]) -> str:
    if grams is None:
        return ""
    if grams <= 0:
        return ""
    rounded = round(grams, 3)
    as_int = int(round(rounded))
    if abs(rounded - as_int) < 1e-6:
        return f"{as_int}g"
    text = f"{rounded:.3f}".rstrip("0").rstrip(".")
    return f"{text}g"


class DbBackedExtractor:
    def __init__(
        self,
        conn=None,
        reload_seconds: Optional[int] = None,
        rule_rows: Optional[list[dict[str, Any]]] = None,
    ):
        self._conn = conn
        self._rule_rows = rule_rows
        self._cache: list[dict[str, Any]] = []
        self._loaded_at = 0.0
        self._reload_seconds = max(
            1,
            int(
                reload_seconds
                or os.getenv("EXTRACT_RULES_RELOAD_SECONDS", str(DEFAULT_RULE_RELOAD_SECONDS))
            ),
        )

    def refresh(self, force: bool = False) -> None:
        now_ts = time.time()
        if not force and self._cache and (now_ts - self._loaded_at) < self._reload_seconds:
            return
        self._cache = self._load_rules()
        self._loaded_at = now_ts

    def _load_rules(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def _query_rows(self, sql: str, args: Optional[tuple[Any, ...]] = None) -> list[dict[str, Any]]:
        if self._rule_rows is not None:
            return list(self._rule_rows)

        if self._conn is not None:
            return self._query_with_conn(self._conn, sql, args=args)

        conn = None
        try:
            conn = get_conn()
            return self._query_with_conn(conn, sql, args=args)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("extract rule query failed: err=%s", exc)
            return []
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    @staticmethod
    def _query_with_conn(conn, sql: str, args: Optional[tuple[Any, ...]] = None) -> list[dict[str, Any]]:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            rows = cur.fetchall()
        return rows if isinstance(rows, list) else []


class ProductTypeExtractor(DbBackedExtractor):
    def _load_rules(self) -> list[dict[str, Any]]:
        rows = self._query_rows(
            """
            SELECT id, product_type, pattern, priority, confidence
            FROM product_type_dict
            WHERE is_active=1
            ORDER BY priority ASC, id ASC
            """
        )
        if not rows:
            rows = DEFAULT_PRODUCT_TYPE_RULES

        compiled: list[dict[str, Any]] = []
        for row in rows:
            pattern = _coalesce_str(row.get("pattern"))
            if not pattern:
                continue
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                LOGGER.warning("invalid product type regex skipped: pattern=%s err=%s", pattern, exc)
                continue

            compiled.append(
                {
                    "id": _to_int(row.get("id")),
                    "product_type": _coalesce_str(row.get("product_type"), "unknown"),
                    "pattern": pattern,
                    "regex": regex,
                    "priority": _to_int(row.get("priority"), 100),
                    "confidence": _to_float(row.get("confidence"), 0.8),
                }
            )
        return compiled

    def extract(self, *, title: str = "", keyword: str = "", category: str = "") -> dict[str, Any]:
        self.refresh()
        text = " ".join([_coalesce_str(title), _coalesce_str(keyword), _coalesce_str(category)])

        for rule in self._cache:
            match = rule["regex"].search(text)
            if not match:
                continue
            return {
                "product_type": rule["product_type"],
                "product_type_rule_id": rule["id"] or None,
                "product_type_confidence": round(_to_float(rule["confidence"], 0.8), 4),
                "product_type_match_text": match.group(0),
            }

        fallback = self._fallback_guess(text)
        return {
            "product_type": fallback,
            "product_type_rule_id": None,
            "product_type_confidence": 0.5 if fallback != "unknown" else 0.0,
            "product_type_match_text": None,
        }

    @staticmethod
    def _fallback_guess(text: str) -> str:
        lowered = (text or "").lower()
        if "king salmon" in lowered or "chinook" in lowered:
            return "king_salmon"
        if "rainbow trout" in lowered:
            return "rainbow_trout"
        if "帝王鲑" in text or "帝王三文鱼" in text:
            return "king_salmon"
        if "虹鳟" in text:
            return "rainbow_trout"
        if "三文鱼" in text or "salmon" in lowered:
            return "salmon_generic"
        return "unknown"


class SpecExtractor(DbBackedExtractor):
    def _load_rules(self) -> list[dict[str, Any]]:
        rows = self._query_rows(
            """
            SELECT id, pattern, normalized_unit, gram_factor, priority
            FROM spec_dict
            WHERE is_active=1
            ORDER BY priority ASC, id ASC
            """
        )
        if not rows:
            rows = DEFAULT_SPEC_UNIT_RULES

        compiled: list[dict[str, Any]] = []
        for row in rows:
            pattern = _coalesce_str(row.get("pattern"))
            if not pattern:
                continue
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                LOGGER.warning("invalid spec regex skipped: pattern=%s err=%s", pattern, exc)
                continue

            compiled.append(
                {
                    "id": _to_int(row.get("id")),
                    "pattern": pattern,
                    "regex": regex,
                    "normalized_unit": _coalesce_str(row.get("normalized_unit")),
                    "gram_factor": _to_float(row.get("gram_factor"), 1.0),
                    "priority": _to_int(row.get("priority"), 100),
                }
            )
        return compiled

    def extract(self, *, title: str = "", spec_text: str = "") -> dict[str, Any]:
        self.refresh()
        merged_text = " ".join([_coalesce_str(title), _coalesce_str(spec_text)]).strip()

        for pattern in WEIGHT_PATTERNS:
            match = pattern.search(merged_text)
            if not match:
                continue
            return self._build_result_from_match(merged_text, match)

        return {
            "spec_raw": None,
            "spec_weight_value": None,
            "spec_weight_unit": None,
            "spec_weight_grams": None,
            "spec_pack_count": None,
            "spec_unit": None,
            "spec_total_weight_grams": None,
            "spec_weight_normalized": "",
        }

    def _build_result_from_match(self, merged_text: str, match: re.Match[str]) -> dict[str, Any]:
        spec_raw = _coalesce_str(match.group(0))
        unit_text = _coalesce_str(match.groupdict().get("unit")).lower()
        weight_value = _to_float(match.groupdict().get("weight"), 0.0)
        if weight_value <= 0:
            return {
                "spec_raw": spec_raw or None,
                "spec_weight_value": None,
                "spec_weight_unit": None,
                "spec_weight_grams": None,
                "spec_pack_count": None,
                "spec_unit": None,
                "spec_total_weight_grams": None,
                "spec_weight_normalized": "",
            }

        count = _to_int(match.groupdict().get("count"), 0)
        pack_unit = _coalesce_str(match.groupdict().get("pack_unit"))
        if count <= 0:
            count_match = PACK_COUNT_PATTERN.search(merged_text)
            if count_match:
                count = _to_int(count_match.group("count"), 1)
                if not pack_unit:
                    pack_unit = _coalesce_str(count_match.group("pack_unit"))
        if count <= 0:
            count = 1

        unit_rule = self._match_unit_rule(unit_text)
        gram_factor = _to_float(unit_rule.get("gram_factor"), 1.0) if unit_rule else 1.0
        normalized_unit = _coalesce_str(unit_rule.get("normalized_unit")) if unit_rule else unit_text

        spec_weight_grams = weight_value * gram_factor
        total_grams = spec_weight_grams * count

        return {
            "spec_raw": spec_raw or None,
            "spec_weight_value": round(weight_value, 3),
            "spec_weight_unit": normalized_unit or None,
            "spec_weight_grams": round(spec_weight_grams, 3),
            "spec_pack_count": count,
            "spec_unit": pack_unit or None,
            "spec_total_weight_grams": round(total_grams, 3),
            "spec_weight_normalized": _normalize_weight_text(total_grams),
        }

    def _match_unit_rule(self, unit_text: str) -> Optional[dict[str, Any]]:
        for rule in self._cache:
            if rule["regex"].search(unit_text):
                return rule
        return None


class OriginExtractor(DbBackedExtractor):
    def _load_rules(self) -> list[dict[str, Any]]:
        rows = self._query_rows(
            """
            SELECT
              id, pattern, normalized_country, normalized_province,
              normalized_city, normalized_origin, priority
            FROM origin_dict
            WHERE is_active=1
            ORDER BY priority ASC, id ASC
            """
        )
        if not rows:
            rows = DEFAULT_ORIGIN_RULES

        compiled: list[dict[str, Any]] = []
        for row in rows:
            pattern = _coalesce_str(row.get("pattern"))
            if not pattern:
                continue
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                LOGGER.warning("invalid origin regex skipped: pattern=%s err=%s", pattern, exc)
                continue

            compiled.append(
                {
                    "id": _to_int(row.get("id")),
                    "pattern": pattern,
                    "regex": regex,
                    "normalized_country": _coalesce_str(row.get("normalized_country")),
                    "normalized_province": _coalesce_str(row.get("normalized_province")),
                    "normalized_city": _coalesce_str(row.get("normalized_city")),
                    "normalized_origin": _coalesce_str(row.get("normalized_origin")),
                }
            )
        return compiled

    def extract(
        self,
        *,
        title: str = "",
        province: str = "",
        city: str = "",
        origin_text: str = "",
    ) -> dict[str, Any]:
        self.refresh()
        merged_text = " ".join(
            [_coalesce_str(title), _coalesce_str(origin_text), _coalesce_str(province), _coalesce_str(city)]
        ).strip()

        for rule in self._cache:
            if not rule["regex"].search(merged_text):
                continue
            country = _coalesce_str(rule.get("normalized_country"))
            province_norm = _coalesce_str(rule.get("normalized_province"), province)
            city_norm = _coalesce_str(rule.get("normalized_city"), city)
            standardized = _coalesce_str(rule.get("normalized_origin"))
            if city_norm and city_norm not in standardized:
                standardized = _compose_origin(country, province_norm, city_norm)
            if not standardized:
                standardized = _compose_origin(country, province_norm, city_norm)
            return {
                "origin_raw": _coalesce_str(origin_text, province, city) or None,
                "origin_country": country or None,
                "origin_province": province_norm or None,
                "origin_city": city_norm or None,
                "origin_standardized": standardized or None,
                "origin_rule_id": rule["id"] or None,
            }

        country = self._guess_country(merged_text)
        province_norm = _coalesce_str(province, self._guess_province(merged_text))
        if province_norm and not country:
            country = "中国"
        city_norm = _coalesce_str(city)
        standardized = _compose_origin(country, province_norm, city_norm)

        return {
            "origin_raw": _coalesce_str(origin_text, province, city) or None,
            "origin_country": country or None,
            "origin_province": province_norm or None,
            "origin_city": city_norm or None,
            "origin_standardized": standardized or None,
            "origin_rule_id": None,
        }

    @staticmethod
    def _guess_country(text: str) -> str:
        for country in DEFAULT_COUNTRY_HINTS:
            if country in text:
                return country
        if text:
            lowered = text.lower()
            if "norway" in lowered:
                return "挪威"
            if "chile" in lowered:
                return "智利"
        return ""

    @staticmethod
    def _guess_province(text: str) -> str:
        for province in DEFAULT_PROVINCE_HINTS:
            if province in text:
                return province
        return ""


class SalmonDataEnricher:
    def __init__(self, conn=None, reload_seconds: Optional[int] = None):
        self.product_type = ProductTypeExtractor(conn=conn, reload_seconds=reload_seconds)
        self.spec = SpecExtractor(conn=conn, reload_seconds=reload_seconds)
        self.origin = OriginExtractor(conn=conn, reload_seconds=reload_seconds)

    def refresh(self, force: bool = False) -> None:
        self.product_type.refresh(force=force)
        self.spec.refresh(force=force)
        self.origin.refresh(force=force)

    def enrich(self, item: dict[str, Any]) -> dict[str, Any]:
        title = _coalesce_str(item.get("title"))
        keyword = _coalesce_str(item.get("keyword"))
        category = _coalesce_str(item.get("category"))
        province = _coalesce_str(item.get("province"))
        city = _coalesce_str(item.get("city"))

        type_info = self.product_type.extract(title=title, keyword=keyword, category=category)
        spec_info = self.spec.extract(title=title, spec_text=_coalesce_str(item.get("spec_raw")))
        origin_info = self.origin.extract(
            title=title,
            province=province,
            city=city,
            origin_text=_coalesce_str(item.get("origin_raw")),
        )

        storage_method = self._extract_storage_method(title)
        cert_flags = self._extract_cert_flags(title)
        nutrition = self._extract_nutrition(title)

        price = item.get("price")
        total_grams = spec_info.get("spec_total_weight_grams")
        price_per_kg = None
        try:
            price_float = float(price)
            grams_float = float(total_grams)
            if price_float > 0 and grams_float > 0:
                price_per_kg = round(price_float / (grams_float / 1000.0), 2)
        except (TypeError, ValueError):
            price_per_kg = None

        is_wild = 1 if ("野生" in title or "wild" in title.lower()) else 0
        is_fresh = 1 if ("鲜" in title and "冷冻" not in title) else 0

        return {
            **type_info,
            **spec_info,
            **origin_info,
            **cert_flags,
            **nutrition,
            "storage_method": storage_method,
            "is_wild": is_wild,
            "is_fresh": is_fresh,
            "price_per_kg": price_per_kg,
        }

    @staticmethod
    def _extract_storage_method(title: str) -> Optional[str]:
        if "冷冻" in title:
            return "frozen"
        if "冰鲜" in title:
            return "ice_fresh"
        if "鲜活" in title:
            return "live_fresh"
        if "冷鲜" in title:
            return "cold_fresh"
        if "鲜" in title:
            return "fresh"
        return None

    @staticmethod
    def _extract_cert_flags(title: str) -> dict[str, int]:
        lowered = title.lower()
        return {
            "cert_organic": int("有机" in title or "organic" in lowered),
            "cert_green_food": int("绿色食品" in title),
            "cert_asc": int("asc" in lowered),
            "cert_msc": int("msc" in lowered),
            "cert_bap": int("bap" in lowered),
            "cert_haccp": int("haccp" in lowered),
            "cert_halal": int("halal" in lowered),
            "cert_qs": int("qs" in lowered or "sc认证" in title),
        }

    @staticmethod
    def _extract_nutrition(title: str) -> dict[str, Optional[float]]:
        # Keep nutrition extraction conservative; values can be backfilled later by detail page parsing.
        omega3 = 0.0
        lowered = title.lower()
        if "omega-3" in lowered or "omega3" in lowered:
            omega3 = 1.0
        return {
            "nutrition_protein_g_per_100g": None,
            "nutrition_fat_g_per_100g": None,
            "nutrition_omega3_g_per_100g": omega3 if omega3 > 0 else None,
        }
