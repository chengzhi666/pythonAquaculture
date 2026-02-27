import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pymysql
from dotenv import load_dotenv

# Always load env from fish_intel_mvp/.env regardless of current working directory.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")


def get_conn():
    db_pass = os.getenv("DB_PASS")
    if db_pass == "change_me":
        raise RuntimeError(
            "DB_PASS is still 'change_me'. Please update fish_intel_mvp/.env with your real MySQL password."
        )
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=db_pass,
        database=os.getenv("DB_NAME", "fish_intel"),
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def now():
    return datetime.now()


def _fallback_spec_key(detail_url: Optional[str]) -> str:
    raw = str(detail_url or "").strip()
    if not raw:
        return "unknown"
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    return f"url#{digest}"


def insert_crawl_run(conn, source_name):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO crawl_run(source_name, started_at, status, items) VALUES(%s,%s,%s,%s)",
            (source_name, now(), "RUNNING", 0),
        )
        return cur.lastrowid


def finish_crawl_run(conn, run_id, status, items=0, error_text=None):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE crawl_run SET ended_at=%s, status=%s, items=%s, error_text=%s WHERE id=%s",
            (now(), status, items, error_text, run_id),
        )


def insert_raw_event(
    conn, source_name, url=None, title=None, pub_time=None, raw_text=None, raw_json=None
):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO raw_event(source_name, url, title, pub_time, fetched_at, raw_text, raw_json) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (source_name, url, title, pub_time, now(), raw_text, raw_json),
        )
        return cur.lastrowid


def upsert_product_snapshot(conn, item):
    payload = {
        "platform": item["platform"],
        "keyword": item["keyword"],
        "title": item["title"],
        "price": item.get("price"),
        "original_price": item.get("original_price"),
        "price_unit": item.get("price_unit") or "CNY",
        "currency": item.get("currency") or "CNY",
        "price_per_kg": item.get("price_per_kg"),
        "price_change_7d": item.get("price_change_7d"),
        "price_change_30d": item.get("price_change_30d"),
        "sales_or_commit": item.get("sales_or_commit"),
        "shop": str(item.get("shop") or "").strip(),
        "shop_type": item.get("shop_type"),
        "brand": item.get("brand"),
        "sku": item.get("sku"),
        "province": item.get("province"),
        "city": item.get("city"),
        "detail_url": item["detail_url"],
        "category": item.get("category"),
        "product_type": str(item.get("product_type") or item.get("keyword") or "unknown").strip()[
            :64
        ],
        "product_type_confidence": item.get("product_type_confidence"),
        "product_type_rule_id": item.get("product_type_rule_id"),
        "spec_raw": item.get("spec_raw"),
        "spec_weight_value": item.get("spec_weight_value"),
        "spec_weight_unit": item.get("spec_weight_unit"),
        "spec_weight_grams": item.get("spec_weight_grams"),
        "spec_pack_count": item.get("spec_pack_count"),
        "spec_unit": item.get("spec_unit"),
        "spec_total_weight_grams": item.get("spec_total_weight_grams"),
        "spec_weight_normalized": str(
            item.get("spec_weight_normalized") or _fallback_spec_key(item.get("detail_url"))
        ).strip()[:32],
        "origin_raw": item.get("origin_raw"),
        "origin_country": item.get("origin_country"),
        "origin_province": item.get("origin_province"),
        "origin_city": item.get("origin_city"),
        "origin_standardized": item.get("origin_standardized"),
        "origin_rule_id": item.get("origin_rule_id"),
        "storage_method": item.get("storage_method"),
        "is_wild": item.get("is_wild"),
        "is_fresh": item.get("is_fresh"),
        "nutrition_protein_g_per_100g": item.get("nutrition_protein_g_per_100g"),
        "nutrition_fat_g_per_100g": item.get("nutrition_fat_g_per_100g"),
        "nutrition_omega3_g_per_100g": item.get("nutrition_omega3_g_per_100g"),
        "cert_organic": item.get("cert_organic"),
        "cert_green_food": item.get("cert_green_food"),
        "cert_asc": item.get("cert_asc"),
        "cert_msc": item.get("cert_msc"),
        "cert_bap": item.get("cert_bap"),
        "cert_haccp": item.get("cert_haccp"),
        "cert_halal": item.get("cert_halal"),
        "cert_qs": item.get("cert_qs"),
        "extra_json": item.get("extra_json"),
        "snapshot_time": item["snapshot_time"],
        "raw_id": item.get("raw_id"),
    }
    insert_cols = [
        "platform",
        "keyword",
        "title",
        "price",
        "original_price",
        "price_unit",
        "currency",
        "price_per_kg",
        "price_change_7d",
        "price_change_30d",
        "sales_or_commit",
        "shop",
        "shop_type",
        "brand",
        "sku",
        "province",
        "city",
        "detail_url",
        "category",
        "product_type",
        "product_type_confidence",
        "product_type_rule_id",
        "spec_raw",
        "spec_weight_value",
        "spec_weight_unit",
        "spec_weight_grams",
        "spec_pack_count",
        "spec_unit",
        "spec_total_weight_grams",
        "spec_weight_normalized",
        "origin_raw",
        "origin_country",
        "origin_province",
        "origin_city",
        "origin_standardized",
        "origin_rule_id",
        "storage_method",
        "is_wild",
        "is_fresh",
        "nutrition_protein_g_per_100g",
        "nutrition_fat_g_per_100g",
        "nutrition_omega3_g_per_100g",
        "cert_organic",
        "cert_green_food",
        "cert_asc",
        "cert_msc",
        "cert_bap",
        "cert_haccp",
        "cert_halal",
        "cert_qs",
        "extra_json",
        "snapshot_time",
        "raw_id",
    ]
    update_cols = [
        "keyword",
        "title",
        "price",
        "original_price",
        "price_unit",
        "currency",
        "price_per_kg",
        "price_change_7d",
        "price_change_30d",
        "sales_or_commit",
        "shop",
        "shop_type",
        "brand",
        "sku",
        "province",
        "city",
        "detail_url",
        "category",
        "product_type_confidence",
        "product_type_rule_id",
        "spec_raw",
        "spec_weight_value",
        "spec_weight_unit",
        "spec_weight_grams",
        "spec_pack_count",
        "spec_unit",
        "spec_total_weight_grams",
        "origin_raw",
        "origin_country",
        "origin_province",
        "origin_city",
        "origin_standardized",
        "origin_rule_id",
        "storage_method",
        "is_wild",
        "is_fresh",
        "nutrition_protein_g_per_100g",
        "nutrition_fat_g_per_100g",
        "nutrition_omega3_g_per_100g",
        "cert_organic",
        "cert_green_food",
        "cert_asc",
        "cert_msc",
        "cert_bap",
        "cert_haccp",
        "cert_halal",
        "cert_qs",
        "extra_json",
        "raw_id",
    ]

    with conn.cursor() as cur:
        cur.execute("SHOW COLUMNS FROM product_snapshot")
        existing_cols = {row["Field"] for row in cur.fetchall()}

    filtered_insert_cols = [c for c in insert_cols if c in existing_cols]
    filtered_update_cols = [c for c in update_cols if c in existing_cols]

    required_cols = {"platform", "keyword", "title", "detail_url", "snapshot_time"}
    if not required_cols.issubset(existing_cols):
        missing = ", ".join(sorted(required_cols - existing_cols))
        raise RuntimeError(
            f"product_snapshot table is missing required columns: {missing}. "
            "Please run fish_intel_mvp/schema.sql to upgrade schema."
        )

    if not filtered_insert_cols:
        raise RuntimeError("product_snapshot has no compatible columns for upsert.")

    insert_clause = ", ".join(filtered_insert_cols)
    values_clause = ", ".join(f"%({c})s" for c in filtered_insert_cols)
    if filtered_update_cols:
        update_clause = ",\n      ".join(f"{c}=VALUES({c})" for c in filtered_update_cols)
    else:
        update_clause = "platform=platform"

    sql = f"""
    INSERT INTO product_snapshot(
      {insert_clause}
    ) VALUES (
      {values_clause}
    )
    ON DUPLICATE KEY UPDATE
      {update_clause}
    """
    with conn.cursor() as cur:
        cur.execute(sql, payload)


def calc_price_change(
    conn,
    *,
    platform: str,
    product_type: str,
    spec_weight_normalized: str,
    days: int = 7,
    shop: Optional[str] = None,
    as_of: Optional[datetime] = None,
) -> dict[str, Any]:
    days = max(1, int(days))
    as_of_dt = as_of or now()
    baseline_dt = as_of_dt - timedelta(days=days)

    def _latest_price(until_dt: datetime) -> Optional[dict[str, Any]]:
        sql = """
        SELECT price, snapshot_time
        FROM product_snapshot
        WHERE platform=%s
          AND product_type=%s
          AND spec_weight_normalized=%s
          AND (%s = '' OR shop=%s)
          AND price IS NOT NULL
          AND snapshot_time <= %s
        ORDER BY snapshot_time DESC
        LIMIT 1
        """
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    platform,
                    product_type,
                    spec_weight_normalized,
                    (shop or ""),
                    (shop or ""),
                    until_dt,
                ),
            )
            return cur.fetchone()

    latest = _latest_price(as_of_dt)
    baseline = _latest_price(baseline_dt)

    latest_price = float(latest["price"]) if latest and latest.get("price") is not None else None
    baseline_price = (
        float(baseline["price"]) if baseline and baseline.get("price") is not None else None
    )
    pct_change = None
    if latest_price is not None and baseline_price is not None and baseline_price > 0:
        pct_change = round(((latest_price - baseline_price) / baseline_price) * 100.0, 4)

    return {
        "days": days,
        "as_of": as_of_dt,
        "baseline_time": baseline["snapshot_time"] if baseline else None,
        "latest_time": latest["snapshot_time"] if latest else None,
        "baseline_price": baseline_price,
        "latest_price": latest_price,
        "pct_change": pct_change,
    }


def upsert_intel_item(conn, item):
    sql = """
    INSERT INTO intel_item(
      source_type, title, pub_time, org, region, content, source_url,
      tags_json, extra_json, fetched_at, raw_id
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
      title=VALUES(title),
      pub_time=VALUES(pub_time),
      org=VALUES(org),
      content=VALUES(content),
      tags_json=VALUES(tags_json),
      extra_json=VALUES(extra_json),
      raw_id=VALUES(raw_id)
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                item["source_type"],
                item["title"],
                item.get("pub_time"),
                item.get("org"),
                item.get("region"),
                item.get("content"),
                item["source_url"],
                item.get("tags_json"),
                item.get("extra_json"),
                now(),
                item.get("raw_id"),
            ),
        )


def upsert_paper(conn, item):
    sql = """
    INSERT INTO paper_meta(
      theme, title, authors, institute, source, pub_date, database_name,
      abstract, keywords_json, url, fetched_at, raw_id
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
      abstract=VALUES(abstract),
      keywords_json=VALUES(keywords_json),
      raw_id=VALUES(raw_id)
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                item.get("theme"),
                item["title"],
                item.get("authors"),
                item.get("institute"),
                item.get("source"),
                item.get("pub_date"),
                item.get("database_name"),
                item.get("abstract"),
                item.get("keywords_json"),
                item["url"],
                now(),
                item.get("raw_id"),
            ),
        )
