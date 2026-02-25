"""农业农村部水产品批发市场价格采集器.

目标: 全国农产品批发市场价格信息系统 - 水产品板块
页面: http://pfsc.agri.cn  (可通过 MOA_PRICE_BASE_URL 覆盖)

流程:
  1. 请求价格监测页面（HTML 表格 或 JSON API）
  2. 解析行级数据 → 日期 / 市场 / 品类 / 规格 / 价格 / 备注
  3. 按品类关键词过滤虹鳟 / 帝王鲑 / 三文鱼等水产
  4. 原始 HTML 存入 raw_event  (溯源)
  5. 解析结果以 list[dict] 返回 (离线价格快照,
     待 offline_price_snapshot 表上线后直接入库)

注意:
  - 本模块是 **新增文件**, 不修改任何已有模块的接口。
  - 依赖 common.db 中已有的 insert_raw_event / get_conn 等,
    不新增/改动 db.py 的函数签名。
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup, Tag

try:
    from common.db import get_conn, insert_raw_event
    from common.logger import get_logger
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from common.db import get_conn, insert_raw_event
    from common.logger import get_logger

LOGGER = get_logger(__name__)

# ---------------------------------------------------------------------------
# 常量 & 默认配置
# ---------------------------------------------------------------------------
SOURCE_NAME = "moa_wholesale_price"
DEFAULT_BASE_URL = "http://pfsc.agri.cn"

# 价格查询 API path (JSON) & 列表 path (HTML) — 优先 API, 降级 HTML
API_PRICE_PATH = "/api/price/queryByCategory"
HTML_PRICE_PATH = "/price/aquatic"

# 品类过滤关键词 (宽匹配，采集后再精筛)
DEFAULT_AQUATIC_KEYWORDS = [
    "虹鳟",
    "帝王鲑",
    "帝王三文鱼",
    "三文鱼",
    "salmon",
    "king salmon",
    "rainbow trout",
    "鲑",
    "鳟",
]

# 更细的虹鳟/帝王鲑精筛正则
SALMON_FILTER_RE = re.compile(
    r"虹鳟|帝王鲑|帝王三文鱼|rainbow\s*trout|king\s*salmon|chinook|三文鱼|鲑鱼|salmon",
    re.IGNORECASE,
)

# 存储方式推断关键词
_STORAGE_FROZEN = re.compile(r"冷冻|冻品|速冻|frozen", re.IGNORECASE)
_STORAGE_ICE_FRESH = re.compile(r"冰鲜|冰冻鲜|ice.?fresh", re.IGNORECASE)
_STORAGE_FRESH = re.compile(r"鲜活|活鲜|活|鲜|fresh|live", re.IGNORECASE)


# ---------------------------------------------------------------------------
# HTTP 工具
# ---------------------------------------------------------------------------


def _build_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "application/json,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    )
    return session


def _fetch(
    session: requests.Session,
    url: str,
    *,
    params: Optional[dict[str, Any]] = None,
    timeout: int = 20,
    retries: int = 2,
) -> requests.Response:
    """GET with simple retry; raises on total failure."""
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"fetch failed after {retries + 1} tries: url={url}, err={last_err}")


# ---------------------------------------------------------------------------
# 价格数据解析 — HTML 表格
# ---------------------------------------------------------------------------


def _clean(text: Optional[str]) -> str:
    return (text or "").replace("\u3000", " ").replace("\xa0", " ").strip()


def _extract_float(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    text = _clean(text).replace(",", "")
    m = re.search(r"\d+(?:\.\d+)?", text)
    return float(m.group(0)) if m else None


def _guess_storage_method(text: str) -> Optional[str]:
    """从文本推断存储方式."""
    if _STORAGE_FROZEN.search(text):
        return "frozen"
    if _STORAGE_ICE_FRESH.search(text):
        return "ice_fresh"
    if _STORAGE_FRESH.search(text):
        return "fresh"
    return None


def _detect_header_map(header_cells: list[str]) -> dict[str, int]:
    """根据表头文字自动映射列号.

    支持常见变体:
      品名/品种/品类, 市场/批发市场, 最低价/最低, 最高价/最高,
      均价/平均价/价格, 单位, 日期/报价日期, 规格, 备注
    """
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(header_cells):
        h = _clean(raw)
        if not h:
            continue
        hl = h.lower()
        if re.search(r"品名|品种|品类|产品名|product", hl):
            mapping.setdefault("product_name", idx)
        elif re.search(r"市场|批发市场|market", hl):
            mapping.setdefault("market_name", idx)
        elif re.search(r"最低|min", hl):
            mapping.setdefault("min_price", idx)
        elif re.search(r"最高|max", hl):
            mapping.setdefault("max_price", idx)
        elif re.search(r"均价|平均|avg|价格|price", hl):
            mapping.setdefault("avg_price", idx)
        elif re.search(r"单位|unit", hl):
            mapping.setdefault("unit", idx)
        elif re.search(r"日期|date|报价", hl):
            mapping.setdefault("date", idx)
        elif re.search(r"规格|spec", hl):
            mapping.setdefault("spec", idx)
        elif re.search(r"备注|产地|remark|note|存储|冷冻", hl):
            mapping.setdefault("remark", idx)
        elif re.search(r"地区|region|区域", hl):
            mapping.setdefault("region", idx)
    return mapping


def parse_price_table(html: str) -> list[dict[str, Any]]:
    """从 HTML 中找到价格表格并解析为行级字典列表.

    兼容多种表格结构 — 自动检测表头映射列号。
    """
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    if not tables:
        LOGGER.debug("moa_prices: no <table> found in HTML")
        return []

    all_rows: list[dict[str, Any]] = []

    for table in tables:
        # 取第一个 <tr> 或 <thead> 作为表头
        header_row: Optional[Tag] = None
        thead = table.find("thead")
        if thead:
            header_row = thead.find("tr")
        if header_row is None:
            trs = table.find_all("tr")
            if trs:
                header_row = trs[0]
        if header_row is None:
            continue

        header_cells = [
            _clean(c.get_text(" ", strip=True)) for c in header_row.find_all(["th", "td"])
        ]
        col_map = _detect_header_map(header_cells)

        # 至少要有 product_name (或 avg_price) 才认为是价格表
        if "product_name" not in col_map and "avg_price" not in col_map:
            continue

        body_rows = table.find_all("tr")[1:]  # skip header
        if thead:
            tbody = table.find("tbody")
            body_rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

        for tr in body_rows:
            cells = [_clean(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])]
            if not cells or len(cells) < 2:
                continue

            def _cell(name: str) -> str:
                idx = col_map.get(name)
                if idx is not None and idx < len(cells):
                    return cells[idx]
                return ""

            product_name = _cell("product_name")
            market_name = _cell("market_name")
            avg_price = _extract_float(_cell("avg_price"))
            min_price = _extract_float(_cell("min_price"))
            max_price = _extract_float(_cell("max_price"))
            unit = _cell("unit") or "元/公斤"
            date_str = _cell("date")
            spec = _cell("spec")
            remark = _cell("remark")
            region = _cell("region")

            # 如果没有均价，尝试从最高最低算
            if avg_price is None and min_price is not None and max_price is not None:
                avg_price = round((min_price + max_price) / 2, 2)

            # 至少要有品名和某种价格
            if not product_name or avg_price is None:
                continue

            storage_method = _guess_storage_method(" ".join([product_name, spec, remark]))

            all_rows.append(
                {
                    "product_name": product_name,
                    "market_name": market_name,
                    "region": region,
                    "spec": spec,
                    "min_price": min_price,
                    "max_price": max_price,
                    "avg_price": avg_price,
                    "unit": unit,
                    "storage_method": storage_method,
                    "date": date_str,
                    "remark": remark,
                }
            )

    return all_rows


# ---------------------------------------------------------------------------
# 价格数据解析 — JSON API
# ---------------------------------------------------------------------------


def parse_price_json(data: Any) -> list[dict[str, Any]]:
    """解析 JSON API 返回的价格数据.

    兼容结构:
      {"code": 0, "data": {"list": [...]}}
      {"data": [...]}
      [...]
    """
    rows: list[dict[str, Any]] = []

    items: list[dict] = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, list):
            items = inner
        elif isinstance(inner, dict):
            items = inner.get("list") or inner.get("rows") or inner.get("records") or []
        if not items:
            items = data.get("list") or data.get("rows") or []

    for item in items:
        if not isinstance(item, dict):
            continue
        product_name = _clean(
            item.get("prodName")
            or item.get("product_name")
            or item.get("name")
            or item.get("品名")
            or ""
        )
        if not product_name:
            continue

        market_name = _clean(
            item.get("marketName") or item.get("market_name") or item.get("市场") or ""
        )
        avg_price = _extract_float(
            str(item.get("avgPrice") or item.get("price") or item.get("均价") or "")
        )
        min_price = _extract_float(str(item.get("minPrice") or item.get("最低价") or ""))
        max_price = _extract_float(str(item.get("maxPrice") or item.get("最高价") or ""))
        if avg_price is None and min_price is not None and max_price is not None:
            avg_price = round((min_price + max_price) / 2, 2)
        if avg_price is None:
            continue

        unit = _clean(item.get("unit") or item.get("单位") or "元/公斤")
        date_str = _clean(str(item.get("reportDate") or item.get("date") or item.get("日期") or ""))
        spec = _clean(item.get("spec") or item.get("规格") or "")
        remark = _clean(item.get("remark") or item.get("备注") or "")
        region = _clean(item.get("region") or item.get("地区") or "")
        storage_method = _guess_storage_method(" ".join([product_name, spec, remark]))

        rows.append(
            {
                "product_name": product_name,
                "market_name": market_name,
                "region": region,
                "spec": spec,
                "min_price": min_price,
                "max_price": max_price,
                "avg_price": avg_price,
                "unit": unit,
                "storage_method": storage_method,
                "date": date_str,
                "remark": remark,
            }
        )

    return rows


# ---------------------------------------------------------------------------
# 品类过滤
# ---------------------------------------------------------------------------


def filter_aquatic_rows(
    rows: list[dict[str, Any]],
    *,
    keywords: Optional[list[str]] = None,
    strict: bool = False,
) -> list[dict[str, Any]]:
    """按品类关键词过滤水产品价格行.

    strict=False 时使用宽匹配 (DEFAULT_AQUATIC_KEYWORDS);
    strict=True  时使用精筛正则 (SALMON_FILTER_RE).
    """
    if strict:
        return [r for r in rows if SALMON_FILTER_RE.search(r.get("product_name", ""))]

    kw_list = keywords or DEFAULT_AQUATIC_KEYWORDS
    patterns = [re.compile(re.escape(k), re.IGNORECASE) for k in kw_list]

    result: list[dict[str, Any]] = []
    for row in rows:
        name = row.get("product_name", "")
        if any(p.search(name) for p in patterns):
            result.append(row)
    return result


# ---------------------------------------------------------------------------
# 行数据 → 标准化离线价格快照 dict
# ---------------------------------------------------------------------------


def normalize_row(
    row: dict[str, Any],
    *,
    source_name: str = SOURCE_NAME,
    snapshot_time: Optional[datetime] = None,
) -> dict[str, Any]:
    """把一行解析结果转为 offline_price_snapshot 兼容格式.

    当 offline_price_snapshot 表上线后,
    可直接用这个 dict 做 INSERT。
    """
    return {
        "source_name": source_name,
        "market_name": row.get("market_name", ""),
        "region": row.get("region", ""),
        "product_type": _infer_product_type(row.get("product_name", "")),
        "product_name_raw": row.get("product_name", ""),
        "spec": row.get("spec", ""),
        "min_price": row.get("min_price"),
        "max_price": row.get("max_price"),
        "price": row.get("avg_price"),
        "unit": row.get("unit", "元/公斤"),
        "storage_method": row.get("storage_method"),
        "snapshot_time": snapshot_time or datetime.now(),
        "date_str": row.get("date", ""),
        "remark": row.get("remark", ""),
    }


def _infer_product_type(name: str) -> str:
    """简单品种推断 (不依赖 DB 词典, 独立于 extract_rules)."""
    if re.search(r"帝王鲑|帝王三文鱼|king\s*salmon|chinook", name, re.IGNORECASE):
        return "king_salmon"
    if re.search(r"虹鳟|rainbow\s*trout", name, re.IGNORECASE):
        return "rainbow_trout"
    if re.search(r"三文鱼|salmon|鲑", name, re.IGNORECASE):
        return "salmon_generic"
    if re.search(r"鳟", name, re.IGNORECASE):
        return "trout_generic"
    return "aquatic_other"


# ---------------------------------------------------------------------------
# 页面抓取 (先试 JSON API, 降级 HTML)
# ---------------------------------------------------------------------------


def _try_fetch_json(
    session: requests.Session,
    base_url: str,
    *,
    category: str = "水产品",
    page: int = 1,
    page_size: int = 100,
    timeout: int = 20,
) -> Optional[list[dict[str, Any]]]:
    """尝试 JSON API 获取价格数据, 失败返回 None."""
    api_url = base_url.rstrip("/") + API_PRICE_PATH
    params = {
        "category": category,
        "page": page,
        "pageSize": page_size,
    }
    try:
        resp = _fetch(session, api_url, params=params, timeout=timeout, retries=1)
        ct = resp.headers.get("Content-Type", "")
        if "json" in ct or resp.text.strip().startswith(("{", "[")):
            data = resp.json()
            return parse_price_json(data)
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("moa_prices json api not available: url=%s err=%s", api_url, exc)
    return None


def _try_fetch_html(
    session: requests.Session,
    base_url: str,
    *,
    html_path: str = HTML_PRICE_PATH,
    timeout: int = 20,
) -> tuple[str, list[dict[str, Any]]]:
    """获取 HTML 页面并解析价格表格. 返回 (raw_html, rows)."""
    page_url = base_url.rstrip("/") + html_path
    resp = _fetch(session, page_url, timeout=timeout, retries=2)
    resp.encoding = resp.apparent_encoding or "utf-8"
    html = resp.text
    rows = parse_price_table(html)
    return html, rows


# ---------------------------------------------------------------------------
# run() — 主入口 (遵循现有 job 的 run(conn) -> int 约定)
# ---------------------------------------------------------------------------


def run(conn, *, base_url: Optional[str] = None) -> int:
    """采集农业农村部水产品批发市场价格.

    Args:
        conn: MySQL 连接 (已有 pymysql 连接).
        base_url: 覆盖默认 URL (用于测试).

    Returns:
        成功写入 raw_event 的水产品价格行数.
    """
    base = base_url or os.getenv("MOA_PRICE_BASE_URL", "").strip() or DEFAULT_BASE_URL
    timeout = max(5, int(os.getenv("MOA_PRICE_TIMEOUT", "20")))
    page_size = max(10, int(os.getenv("MOA_PRICE_PAGE_SIZE", "200")))
    max_pages = max(1, int(os.getenv("MOA_PRICE_MAX_PAGES", "3")))
    strict_filter = os.getenv("MOA_PRICE_STRICT_FILTER", "0").strip() == "1"
    raw_html_max = max(10000, int(os.getenv("MOA_PRICE_RAW_HTML_MAX", "500000")))
    sleep_seconds = max(0.0, float(os.getenv("MOA_PRICE_SLEEP_SECONDS", "0.5")))

    session = _build_session()
    snapshot_time = datetime.now()

    all_rows: list[dict[str, Any]] = []
    raw_html_combined = ""

    # --- 1. 尝试 JSON API ---
    for page in range(1, max_pages + 1):
        json_rows = _try_fetch_json(session, base, page=page, page_size=page_size, timeout=timeout)
        if json_rows is not None:
            LOGGER.info("moa_prices json page=%s raw_rows=%s", page, len(json_rows))
            all_rows.extend(json_rows)
            if len(json_rows) < page_size:
                break
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
        else:
            if page == 1:
                LOGGER.info("moa_prices json api unavailable, falling back to HTML")
            break

    # --- 2. 降级 HTML ---
    if not all_rows:
        try:
            raw_html, html_rows = _try_fetch_html(session, base, timeout=timeout)
            raw_html_combined = raw_html
            all_rows = html_rows
            LOGGER.info("moa_prices html raw_rows=%s", len(all_rows))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("moa_prices html fetch failed: err=%s", exc)
            return 0

    if not all_rows:
        LOGGER.warning("moa_prices: no price rows found from %s", base)
        return 0

    # --- 3. 过滤水产品 ---
    filtered = filter_aquatic_rows(all_rows, strict=strict_filter)
    LOGGER.info(
        "moa_prices filter: total=%s aquatic=%s strict=%s",
        len(all_rows),
        len(filtered),
        strict_filter,
    )

    # --- 4. 存储 raw_event & 准备离线快照 ---
    written = 0
    for row in filtered:
        normalized = normalize_row(row, snapshot_time=snapshot_time)
        try:
            insert_raw_event(
                conn,
                source_name=SOURCE_NAME,
                url=base,
                title=row.get("product_name", ""),
                pub_time=row.get("date"),
                raw_json=json.dumps(
                    {
                        "parsed_row": row,
                        "normalized": {
                            k: (v.isoformat() if isinstance(v, datetime) else v)
                            for k, v in normalized.items()
                        },
                    },
                    ensure_ascii=False,
                ),
                raw_text=(
                    raw_html_combined[:raw_html_max] if raw_html_combined and written == 0 else None
                ),
            )
            written += 1
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning(
                "moa_prices db write failed: product=%s market=%s err=%s",
                row.get("product_name"),
                row.get("market_name"),
                exc,
            )

    LOGGER.info("moa_prices done: written=%s", written)
    return written


# ---------------------------------------------------------------------------
# 直接执行
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    connection = get_conn()
    try:
        count = run(connection)
        print(f"[OK] moa_prices items={count}")
    finally:
        connection.close()
