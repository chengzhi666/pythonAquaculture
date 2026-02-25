import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

try:
    from common.db import calc_price_change, get_conn
    from common.extract_rules import SalmonDataEnricher
    from common.logger import get_logger
    from jobs.crawl_jd import run as run_jd
    from jobs.crawl_taobao import run as run_taobao
except ModuleNotFoundError:
    # Support direct execution: python fish_intel_mvp/jobs/crawl_salmon.py
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from common.db import calc_price_change, get_conn
    from common.extract_rules import SalmonDataEnricher
    from common.logger import get_logger
    from crawl_jd import run as run_jd
    from crawl_taobao import run as run_taobao

LOGGER = get_logger(__name__)

DEFAULT_SALMON_KEYWORDS = ["虹鳟", "帝王鲑", "帝王三文鱼", "rainbow", "king salmon"]


def _split_env_list(raw: str) -> list[str]:
    raw = (raw or "").replace("，", ",")
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values


def _load_keywords_from_db(conn) -> list[str]:
    sql = """
    SELECT DISTINCT keyword_hint
    FROM product_type_dict
    WHERE is_active=1
      AND keyword_hint IS NOT NULL
      AND keyword_hint <> ''
    ORDER BY keyword_hint
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall() or []
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("salmon keyword db load failed: err=%s", exc)
        return []
    return [str(row.get("keyword_hint") or "").strip() for row in rows if row.get("keyword_hint")]


def load_salmon_keywords(conn, env_key: str) -> list[str]:
    env_keywords = _split_env_list(os.getenv(env_key, ""))
    if env_keywords:
        return env_keywords

    generic_env = _split_env_list(os.getenv("SALMON_KEYWORDS", ""))
    if generic_env:
        return generic_env

    db_keywords = _load_keywords_from_db(conn)
    if db_keywords:
        return db_keywords
    return DEFAULT_SALMON_KEYWORDS


def _build_enrich_fn(enricher: SalmonDataEnricher):
    def enrich(item: dict[str, Any]) -> dict[str, Any]:
        extracted = enricher.enrich(item)
        debug_payload = {
            "extractor": "salmon_rule_chain_v1",
            "product_type_match_text": extracted.pop("product_type_match_text", None),
            "product_type_confidence": extracted.get("product_type_confidence"),
            "spec_raw": extracted.get("spec_raw"),
            "origin_standardized": extracted.get("origin_standardized"),
        }
        extracted["extra_json"] = json.dumps(debug_payload, ensure_ascii=False)
        return extracted

    return enrich


def _safe_int(env_name: str, default_value: int) -> int:
    raw = os.getenv(env_name, str(default_value))
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return max(1, int(default_value))


def _backfill_price_changes(conn, platform: str, days_list: Optional[list[int]] = None) -> int:
    days_list = days_list or [7, 30]
    sql = """
    SELECT
      id, platform, product_type, spec_weight_normalized, shop, snapshot_time
    FROM product_snapshot
    WHERE platform=%s
      AND product_type <> ''
      AND spec_weight_normalized <> ''
      AND snapshot_time >= CURDATE()
    ORDER BY id DESC
    """
    updated = 0
    with conn.cursor() as cur:
        cur.execute(sql, (platform,))
        rows = cur.fetchall() or []

    for row in rows:
        values: dict[str, Any] = {}
        for days in days_list:
            result = calc_price_change(
                conn,
                platform=row["platform"],
                product_type=row["product_type"],
                spec_weight_normalized=row["spec_weight_normalized"],
                days=days,
                shop=row.get("shop"),
                as_of=row.get("snapshot_time"),
            )
            values[f"price_change_{days}d"] = result["pct_change"]

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE product_snapshot
                SET price_change_7d=%s, price_change_30d=%s
                WHERE id=%s
                """,
                (values.get("price_change_7d"), values.get("price_change_30d"), row["id"]),
            )
        updated += 1
    return updated


def crawl_taobao_salmon(
    conn,
    keywords: Optional[list[str]] = None,
    pages: Optional[int] = None,
    schedule_times: Optional[list[str]] = None,
) -> int:
    del schedule_times  # reserved for external scheduler integration
    keywords = keywords or load_salmon_keywords(conn, env_key="TAOBAO_SALMON_KEYWORDS")
    pages = pages or _safe_int("TAOBAO_SALMON_PAGES", _safe_int("TAOBAO_PAGES", 1))
    enricher = SalmonDataEnricher(conn=conn)
    enrich_fn = _build_enrich_fn(enricher)

    LOGGER.info("taobao salmon start: keywords=%s pages=%s", ",".join(keywords), pages)
    count = run_taobao(
        conn,
        keywords=keywords,
        pages=pages,
        enrich_item_fn=enrich_fn,
        source_name="taobao_salmon",
    )
    updated = _backfill_price_changes(conn, platform="taobao")
    LOGGER.info("taobao salmon done: items=%s price_change_rows=%s", count, updated)
    return count


def crawl_jd_salmon(
    conn,
    keywords: Optional[list[str]] = None,
    pages: Optional[int] = None,
    schedule_times: Optional[list[str]] = None,
) -> int:
    del schedule_times  # reserved for external scheduler integration
    keywords = keywords or load_salmon_keywords(conn, env_key="JD_SALMON_KEYWORDS")
    pages = pages or _safe_int("JD_SALMON_PAGES", _safe_int("JD_PAGES", 1))
    enricher = SalmonDataEnricher(conn=conn)
    enrich_fn = _build_enrich_fn(enricher)

    LOGGER.info("jd salmon start: keywords=%s pages=%s", ",".join(keywords), pages)
    count = run_jd(
        conn,
        keywords=keywords,
        pages=pages,
        enrich_item_fn=enrich_fn,
        source_name="jd_salmon",
    )
    updated = _backfill_price_changes(conn, platform="jd")
    LOGGER.info("jd salmon done: items=%s price_change_rows=%s", count, updated)
    return count


def run(conn) -> int:
    platforms = {
        item.lower() for item in _split_env_list(os.getenv("SALMON_PLATFORMS", "taobao,jd"))
    }
    if not platforms:
        platforms = {"taobao", "jd"}

    total = 0
    errors: list[str] = []
    if "taobao" in platforms:
        try:
            total += crawl_taobao_salmon(conn)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"taobao:{exc}")
            LOGGER.warning("taobao salmon failed: err=%s", exc)

    if "jd" in platforms:
        try:
            total += crawl_jd_salmon(conn)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"jd:{exc}")
            LOGGER.warning("jd salmon failed: err=%s", exc)

    if errors and total <= 0:
        raise RuntimeError(f"all salmon crawlers failed: {' | '.join(errors)}")
    if errors:
        LOGGER.warning("partial salmon crawl failures: %s", " | ".join(errors))
    return total


if __name__ == "__main__":
    connection = get_conn()
    try:
        total_items = run(connection)
        print(f"[OK] salmon items={total_items}")
    finally:
        connection.close()
