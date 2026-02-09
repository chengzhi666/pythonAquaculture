import os
from datetime import datetime
from pathlib import Path

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
    sql = """
    INSERT INTO product_snapshot(
      platform, keyword, title, price, original_price, sales_or_commit,
      shop, province, city, detail_url, category, snapshot_time, raw_id
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
      price=VALUES(price),
      original_price=VALUES(original_price),
      sales_or_commit=VALUES(sales_or_commit),
      shop=VALUES(shop),
      category=VALUES(category),
      raw_id=VALUES(raw_id)
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                item["platform"],
                item["keyword"],
                item["title"],
                item.get("price"),
                item.get("original_price"),
                item.get("sales_or_commit"),
                item.get("shop"),
                item.get("province"),
                item.get("city"),
                item["detail_url"],
                item.get("category"),
                item["snapshot_time"],
                item.get("raw_id"),
            ),
        )


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
