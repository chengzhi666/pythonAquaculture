"""Dashboard 查询模块 —— 为 Streamlit 可视化提供所有统计/筛选/时序查询。

所有函数统一走 MySQL（通过 fish_intel_mvp.common.db.get_conn()），
返回 list[dict]，方便直接转 pandas DataFrame 或 plotly 数据源。
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from fish_intel_mvp.common.db import get_conn

logger = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────


@contextmanager
def _cursor():
    """获取一个 MySQL 连接 + DictCursor，用完自动关闭。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def _fetchall(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """执行 SELECT 并返回全部行（list[dict]）。"""
    with _cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


# ── 1. 总量统计（仪表盘 metric 卡片） ────────────────────────────────────────


def get_total_counts() -> dict[str, int]:
    """返回各主表的总行数，供仪表盘顶部数字展示。

    Returns:
        {"intel_items": N, "products": N, "papers": N, "crawl_runs": N}
    """
    tables = {
        "intel_items": "intel_item",
        "products": "product_snapshot",
        "papers": "paper_meta",
        "crawl_runs": "crawl_run",
    }
    counts: dict[str, int] = {}
    with _cursor() as cur:
        for key, table in tables.items():
            try:
                cur.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
                row = cur.fetchone()
                counts[key] = row["cnt"] if row else 0
            except Exception:
                counts[key] = 0
    return counts


# ── 2. 来源分布统计 ──────────────────────────────────────────────────────────


def get_source_stats() -> list[dict[str, Any]]:
    """按 source_type 分组统计 intel_item 条数。

    Returns:
        [{"source_type": "CNKI", "count": 120}, ...]
    """
    sql = (
        "SELECT source_type, COUNT(*) AS count "
        "FROM intel_item "
        "GROUP BY source_type "
        "ORDER BY count DESC"
    )
    return _fetchall(sql)


def get_product_stats() -> list[dict[str, Any]]:
    """按 platform + product_type 分组统计 product_snapshot 条数。

    Returns:
        [{"platform": "jd", "product_type": "king_salmon", "count": 85}, ...]
    """
    sql = (
        "SELECT platform, "
        "  COALESCE(NULLIF(product_type, ''), '未分类') AS product_type, "
        "  COUNT(*) AS count "
        "FROM product_snapshot "
        "GROUP BY platform, product_type "
        "ORDER BY count DESC"
    )
    return _fetchall(sql)


# ── 3. 每日采集趋势 ─────────────────────────────────────────────────────────


def get_daily_trend(days: int = 30) -> list[dict[str, Any]]:
    """按天统计 intel_item 和 product_snapshot 的新增条目数。

    两张表分别查询后合并，返回：
        [{"date": "2026-02-01", "intel_items": 5, "products": 12}, ...]
    """
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # intel_item 用 fetched_at
    sql_intel = (
        "SELECT DATE(fetched_at) AS dt, COUNT(*) AS cnt "
        "FROM intel_item "
        "WHERE fetched_at >= %s "
        "GROUP BY dt ORDER BY dt"
    )
    # product_snapshot 用 snapshot_time
    sql_product = (
        "SELECT DATE(snapshot_time) AS dt, COUNT(*) AS cnt "
        "FROM product_snapshot "
        "WHERE snapshot_time >= %s "
        "GROUP BY dt ORDER BY dt"
    )

    intel_rows = _fetchall(sql_intel, (since,))
    product_rows = _fetchall(sql_product, (since,))

    # 合并到一个 dict，按日期对齐
    merged: dict[str, dict[str, Any]] = {}
    for row in intel_rows:
        d = str(row["dt"])
        merged.setdefault(d, {"date": d, "intel_items": 0, "products": 0})
        merged[d]["intel_items"] = row["cnt"]
    for row in product_rows:
        d = str(row["dt"])
        merged.setdefault(d, {"date": d, "intel_items": 0, "products": 0})
        merged[d]["products"] = row["cnt"]

    return sorted(merged.values(), key=lambda x: x["date"])


# ── 4. 采集运行记录 ─────────────────────────────────────────────────────────


def get_recent_crawl_runs(limit: int = 20) -> list[dict[str, Any]]:
    """查 crawl_run 表最近的运行记录。

    Returns:
        [{"source_name": "cnki", "started_at": ..., "ended_at": ...,
          "status": "OK", "items": 20, "error_text": None}, ...]
    """
    sql = (
        "SELECT source_name, started_at, ended_at, status, items, error_text "
        "FROM crawl_run "
        "ORDER BY started_at DESC "
        "LIMIT %s"
    )
    rows = _fetchall(sql, (limit,))
    # datetime 转字符串方便 Streamlit 展示
    for row in rows:
        for k in ("started_at", "ended_at"):
            if isinstance(row.get(k), datetime):
                row[k] = row[k].strftime("%Y-%m-%d %H:%M:%S")
    return rows


# ── 5. 电商商品快照查询 ─────────────────────────────────────────────────────


def get_product_snapshots(
    *,
    platform: str | None = None,
    product_type: str | None = None,
    keyword: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """带筛选的商品快照查询，返回展示所需的关键列。"""
    conditions: list[str] = []
    params: list[Any] = []

    if platform:
        conditions.append("platform = %s")
        params.append(platform)
    if product_type:
        conditions.append("product_type = %s")
        params.append(product_type)
    if keyword:
        conditions.append("title LIKE %s")
        params.append(f"%{keyword}%")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = (
        "SELECT title, platform, "
        "  COALESCE(product_type, '未分类') AS product_type, "
        "  price, original_price, "
        "  spec_raw, spec_weight_normalized, "
        "  origin_standardized, shop, "
        "  sales_or_commit, province, city, category, "
        "  snapshot_time, detail_url "
        f"FROM product_snapshot {where} "
        "ORDER BY snapshot_time DESC "
        "LIMIT %s"
    )
    params.append(limit)
    rows = _fetchall(sql, tuple(params))
    for row in rows:
        if isinstance(row.get("snapshot_time"), datetime):
            row["snapshot_time"] = row["snapshot_time"].strftime("%Y-%m-%d %H:%M")
    return rows


# ── 6. 价格趋势（时序聚合） ─────────────────────────────────────────────────


def get_price_trend(
    product_type: str,
    *,
    platform: str | None = None,
    days: int = 90,
) -> list[dict[str, Any]]:
    """从 product_snapshot 按 snapshot_time 聚合每日均价/最高/最低。

    Returns:
        [{"date": "2026-01-15", "avg_price": 89.5, "min_price": 60.0,
          "max_price": 128.0, "count": 15}, ...]
    """
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    conditions = ["product_type = %s", "snapshot_time >= %s", "price IS NOT NULL"]
    params: list[Any] = [product_type, since]

    if platform:
        conditions.append("platform = %s")
        params.append(platform)

    where = "WHERE " + " AND ".join(conditions)

    sql = (
        "SELECT DATE(snapshot_time) AS date, "
        "  ROUND(AVG(price), 2) AS avg_price, "
        "  ROUND(MIN(price), 2) AS min_price, "
        "  ROUND(MAX(price), 2) AS max_price, "
        "  COUNT(*) AS count "
        f"FROM product_snapshot {where} "
        "GROUP BY DATE(snapshot_time) "
        "ORDER BY date"
    )
    rows = _fetchall(sql, tuple(params))
    for row in rows:
        row["date"] = str(row["date"])
    return rows


def get_price_trend_by_species(
    *,
    platform: str | None = None,
    days: int = 90,
) -> list[dict[str, Any]]:
    """按品种分组的每日均价趋势，用于多条折线叠加。

    Returns:
        [{"date": "2026-01-15", "product_type": "king_salmon",
          "avg_price": 89.5}, ...]
    """
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    conditions = [
        "snapshot_time >= %s",
        "price IS NOT NULL",
        "product_type IS NOT NULL",
        "product_type != ''",
    ]
    params: list[Any] = [since]

    if platform:
        conditions.append("platform = %s")
        params.append(platform)

    where = "WHERE " + " AND ".join(conditions)

    sql = (
        "SELECT DATE(snapshot_time) AS date, product_type, "
        "  ROUND(AVG(price), 2) AS avg_price "
        f"FROM product_snapshot {where} "
        "GROUP BY DATE(snapshot_time), product_type "
        "ORDER BY date, product_type"
    )
    rows = _fetchall(sql, tuple(params))
    for row in rows:
        row["date"] = str(row["date"])
    return rows


# ── 7. 品种-产地 价格对比 ───────────────────────────────────────────────────


def get_price_by_species_origin(
    *,
    platform: str | None = None,
    days: int = 30,
) -> list[dict[str, Any]]:
    """按品种 + 产地分组的均价对比。

    Returns:
        [{"product_type": "king_salmon", "origin": "智利",
          "avg_price": 128.5, "count": 20}, ...]
    """
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    conditions = [
        "snapshot_time >= %s",
        "price IS NOT NULL",
        "product_type IS NOT NULL",
        "product_type != ''",
    ]
    params: list[Any] = [since]

    if platform:
        conditions.append("platform = %s")
        params.append(platform)

    where = "WHERE " + " AND ".join(conditions)

    sql = (
        "SELECT product_type, "
        "  COALESCE(NULLIF(origin_standardized, ''), '未知') AS origin, "
        "  ROUND(AVG(price), 2) AS avg_price, "
        "  COUNT(*) AS count "
        f"FROM product_snapshot {where} "
        "GROUP BY product_type, origin "
        "HAVING count >= 1 "
        "ORDER BY product_type, avg_price DESC"
    )
    return _fetchall(sql, tuple(params))


# ── 8. 价格变动排行 ─────────────────────────────────────────────────────────


def get_recent_products_by_price(
    *,
    order_by: str = "price_desc",
    limit: int = 10,
) -> list[dict[str, Any]]:
    """最近商品快照按价格排序。

    Args:
        order_by: "price_desc" 价格降序 | "price_asc" 价格升序
        limit: 返回条数

    Returns:
        [{"title": "...", "platform": "jd", "product_type": "king_salmon",
          "price": 128.0, ...}, ...]
    """
    order_clause = "price DESC" if order_by == "price_desc" else "price ASC"

    sql = (
        "SELECT title, platform, "
        "  COALESCE(product_type, '未分类') AS product_type, "
        "  price, original_price, shop, origin_standardized, "
        "  snapshot_time, detail_url "
        "FROM product_snapshot "
        "WHERE price IS NOT NULL "
        f"ORDER BY {order_clause} "
        "LIMIT %s"
    )
    rows = _fetchall(sql, (limit,))
    for row in rows:
        if isinstance(row.get("snapshot_time"), datetime):
            row["snapshot_time"] = row["snapshot_time"].strftime("%Y-%m-%d %H:%M")
    return rows


# ── 9. 论文检索 ─────────────────────────────────────────────────────────────


def get_papers(
    keyword: str = "",
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """查 paper_meta 表，支持关键词搜索 title / abstract / keywords_json。

    Returns:
        [{"title": "...", "authors": "...", "institute": "...",
          "source": "...", "pub_date": "...", "abstract": "...",
          "keywords_json": "...", "url": "..."}, ...]
    """
    conditions: list[str] = []
    params: list[Any] = []

    if keyword:
        conditions.append("(title LIKE %s OR abstract LIKE %s OR keywords_json LIKE %s)")
        kw = f"%{keyword}%"
        params.extend([kw, kw, kw])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = (
        "SELECT title, authors, institute, source, pub_date, "
        "  abstract, keywords_json, url "
        f"FROM paper_meta {where} "
        "ORDER BY fetched_at DESC "
        "LIMIT %s"
    )
    params.append(limit)
    return _fetchall(sql, tuple(params))


# ── 10. 可用筛选值（下拉框选项） ────────────────────────────────────────────


def get_distinct_platforms() -> list[str]:
    """返回 product_snapshot 中所有不同的 platform 值。"""
    rows = _fetchall("SELECT DISTINCT platform FROM product_snapshot ORDER BY platform")
    return [r["platform"] for r in rows]


def get_distinct_species() -> list[str]:
    """返回 product_snapshot 中所有不同的 product_type 值。"""
    rows = _fetchall(
        "SELECT DISTINCT product_type FROM product_snapshot "
        "WHERE product_type IS NOT NULL AND product_type != '' "
        "ORDER BY product_type"
    )
    return [r["product_type"] for r in rows]


def get_distinct_source_types() -> list[str]:
    """返回 intel_item 中所有不同的 source_type 值。"""
    rows = _fetchall("SELECT DISTINCT source_type FROM intel_item ORDER BY source_type")
    return [r["source_type"] for r in rows]


# ── 11. 情报检索增强（带 source_type 筛选） ────────────────────────────────


def query_intel_enhanced(
    *,
    keyword: str = "",
    source_type: str | None = None,
    order_by: str = "time",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """增强版情报查询：支持关键词 + source_type 筛选 + 可配数量。

    相比 cli_query.query_intel，返回 dict 而非 tuple，多一列 content 摘要。
    """
    conditions: list[str] = []
    params: list[Any] = []

    if keyword:
        conditions.append("(title LIKE %s OR content LIKE %s)")
        kw = f"%{keyword}%"
        params.extend([kw, kw])

    if source_type:
        conditions.append("source_type = %s")
        params.append(source_type)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    time_expr = (
        "COALESCE("
        "STR_TO_DATE(pub_time, '%%Y-%%m-%%d %%H:%%i:%%s'),"
        "STR_TO_DATE(pub_time, '%%Y-%%m-%%d'),"
        "STR_TO_DATE(REPLACE(REPLACE(REPLACE(pub_time, '年', '-'), '月', '-'), '日', ''), '%%Y-%%m-%%d')"
        ")"
    )

    order_map = {
        "time": f"{time_expr} DESC, fetched_at DESC",
        "org_time": f"org, {time_expr} DESC, fetched_at DESC",
        "region_time": f"region, {time_expr} DESC, fetched_at DESC",
    }
    order_clause = order_map.get(order_by, order_map["time"])

    sql = (
        "SELECT pub_time, region, org, title, source_type, source_url, "
        "  LEFT(content, 200) AS content_preview "
        f"FROM intel_item {where} "
        f"ORDER BY {order_clause} "
        f"LIMIT %s"
    )
    params.append(limit)
    return _fetchall(sql, tuple(params))
