"""农业农村部水产品批发市场价格采集器.

目标: 全国农产品批发市场价格信息系统 (pfsc.agri.cn) — 水产品板块
页面: https://pfsc.agri.cn/#/priceMarket

流程 (Playwright + AES 解密):
  1. 用 Playwright 打开 pfsc.agri.cn (SPA 需要浏览器环境)
  2. 通过 page.evaluate 调用品种列表 API 获取水产品 variety ID
  3. 通过 page.evaluate 调用价格 API, 用前端自带的 decryptAes 解密响应
  4. 解析解密后的 JSON → 日期 / 市场 / 品名 / 价格
  5. 可选: strict 模式下按三文鱼关键词过滤虹鳟 / 帝王鲑 / 三文鱼
  6. 原始数据存入 raw_event (溯源)
  7. 解析结果以 list[dict] 返回

数据结构 (解密后):
  {"date":"2026-02-27", "x":["市场1","市场2",...], "y":[18.5,21.0,...]}

API 端点:
  POST /api/priceQuotationController/getVarietyNameByPid?pid=AM  → 水产品品种列表
  POST /price_portal/index/getMarketReportPriceChart?varietyID=xxx → 某品种价格

依赖: playwright, common.db, common.logger

首次使用须安装浏览器:
  .\.venv\Scripts\python -m playwright install chromium
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag

try:
    from playwright.sync_api import sync_playwright, Page
except ImportError as _pw_err:
    sync_playwright = None  # type: ignore[assignment]
    _PW_IMPORT_ERR = _pw_err
else:
    _PW_IMPORT_ERR = None

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
PRICE_MARKET_URL = "https://pfsc.agri.cn/#/priceMarket"

# 水产品大类 pid (品种树中 AM = 水产品)
AQUATIC_PID = "AM"

# 品类过滤关键词 (宽匹配)
DEFAULT_AQUATIC_KEYWORDS = [
    "虹鳟", "帝王鲑", "帝王三文鱼", "三文鱼", "salmon",
    "king salmon", "rainbow trout", "鲑", "鳟",
]

# 精筛正则
SALMON_FILTER_RE = re.compile(
    r"虹鳟|帝王鲑|帝王三文鱼|rainbow\s*trout|king\s*salmon|chinook|三文鱼|鲑鱼|salmon",
    re.IGNORECASE,
)

# 存储方式推断
_STORAGE_FROZEN = re.compile(r"冷冻|冻品|速冻|frozen", re.IGNORECASE)
_STORAGE_ICE_FRESH = re.compile(r"冰鲜|冰冻鲜|ice.?fresh", re.IGNORECASE)
_STORAGE_FRESH = re.compile(r"鲜活|活鲜|活|鲜|fresh|live", re.IGNORECASE)


# ---------------------------------------------------------------------------
# 工具函数
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


def _infer_product_type(name: str) -> str:
    """简单品种推断."""
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
# 表头自动映射 (HTML 表格解析用)
# ---------------------------------------------------------------------------


def _detect_header_map(header_cells: list[str]) -> dict[str, int]:
    """根据表头文字自动映射列号."""
    mapping: dict[str, int] = {}
    for idx, raw in enumerate(header_cells):
        h = _clean(raw)
        if not h:
            continue
        hl = h.lower()
        if re.search(r"品名|品种|品类|产品名|product|产品", hl):
            mapping.setdefault("product_name", idx)
        elif re.search(r"市场|批发市场|market", hl):
            mapping.setdefault("market_name", idx)
        elif re.search(r"最低|min", hl):
            mapping.setdefault("min_price", idx)
        elif re.search(r"最高|max", hl):
            mapping.setdefault("max_price", idx)
        elif re.search(r"均价|平均|avg|价格|price|大宗价", hl):
            mapping.setdefault("avg_price", idx)
        elif re.search(r"单位|unit", hl):
            mapping.setdefault("unit", idx)
        elif re.search(r"日期|date|报价|发布", hl):
            mapping.setdefault("date", idx)
        elif re.search(r"规格|spec", hl):
            mapping.setdefault("spec", idx)
        elif re.search(r"备注|产地|remark|note|存储|冷冻", hl):
            mapping.setdefault("remark", idx)
        elif re.search(r"地区|region|区域", hl):
            mapping.setdefault("region", idx)
    return mapping


def _map_cells_to_row(cells: list[str], col_map: dict[str, int]) -> Optional[dict[str, Any]]:
    """将一行单元格文本按 col_map 映射成结构化字典."""
    if not cells or len(cells) < 2:
        return None

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

    if avg_price is None and min_price is not None and max_price is not None:
        avg_price = round((min_price + max_price) / 2, 2)

    if not product_name or avg_price is None:
        return None

    storage_method = _guess_storage_method(" ".join([product_name, spec, remark]))

    return {
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


# ---------------------------------------------------------------------------
# BeautifulSoup HTML 表格解析
# ---------------------------------------------------------------------------


def parse_price_table(html: str) -> list[dict[str, Any]]:
    """从 HTML 中找到价格表格并解析为行级字典列表."""
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    if not tables:
        LOGGER.debug("moa_prices: no <table> found in HTML")
        return []

    all_rows: list[dict[str, Any]] = []

    for table in tables:
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

        if "product_name" not in col_map and "avg_price" not in col_map:
            continue

        body_rows = table.find_all("tr")[1:]
        if thead:
            tbody = table.find("tbody")
            body_rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

        for tr in body_rows:
            cells = [_clean(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])]
            row = _map_cells_to_row(cells, col_map)
            if row:
                all_rows.append(row)

    return all_rows


# ---------------------------------------------------------------------------
# JSON 解析
# ---------------------------------------------------------------------------


def parse_price_json(data: Any) -> list[dict[str, Any]]:
    """解析 JSON API 返回的价格数据.

    支持两种格式:
    1. 解密后的图表数据: {"date":"...", "x":["市场1",...], "y":[价格1,...]}
    2. 通用列表格式: {"data": {"list": [...]}}
    """
    rows: list[dict[str, Any]] = []

    # --- 格式 1: 解密后的图表数据 (pfsc.agri.cn getMarketReportPriceChart) ---
    if isinstance(data, dict) and "x" in data and "y" in data:
        markets = data.get("x", [])
        prices = data.get("y", [])
        date_str = data.get("date", "")
        for market, price in zip(markets, prices):
            if price is None:
                continue
            rows.append({
                "product_name": data.get("variety_name", ""),
                "market_name": _clean(str(market)),
                "region": "",
                "spec": "",
                "min_price": None,
                "max_price": None,
                "avg_price": float(price) if price is not None else None,
                "unit": "元/公斤",
                "storage_method": None,
                "date": _clean(str(date_str)),
                "remark": "",
            })
        return rows

    # --- 格式 2: 通用列表格式 ---
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
            item.get("prodName") or item.get("product_name")
            or item.get("name") or item.get("品名") or ""
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
        date_str = _clean(
            str(item.get("reportDate") or item.get("date") or item.get("日期") or "")
        )
        spec = _clean(item.get("spec") or item.get("规格") or "")
        remark = _clean(item.get("remark") or item.get("备注") or "")
        region = _clean(item.get("region") or item.get("地区") or "")
        storage_method = _guess_storage_method(" ".join([product_name, spec, remark]))

        rows.append({
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
        })

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
    """按品类关键词过滤水产品价格行."""
    if strict:
        return [r for r in rows if SALMON_FILTER_RE.search(r.get("product_name", ""))]

    kw_list = keywords or DEFAULT_AQUATIC_KEYWORDS
    patterns = [re.compile(re.escape(k), re.IGNORECASE) for k in kw_list]

    return [
        row for row in rows
        if any(p.search(row.get("product_name", "")) for p in patterns)
    ]


# ---------------------------------------------------------------------------
# 行数据 → 标准化离线价格快照
# ---------------------------------------------------------------------------


def normalize_row(
    row: dict[str, Any],
    *,
    source_name: str = SOURCE_NAME,
    snapshot_time: Optional[datetime] = None,
) -> dict[str, Any]:
    """把一行解析结果转为 offline_price_snapshot 兼容格式."""
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


# ---------------------------------------------------------------------------
# Chrome 路径
# ---------------------------------------------------------------------------


def _resolve_chrome_path() -> str:
    """查找 Chrome 可执行文件."""
    candidates = [
        os.getenv("CHROME_PATH", ""),
        str(Path(__file__).resolve().parents[2]
            / ".chrome-for-testing" / "chrome-win64" / "chrome.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return ""


# ---------------------------------------------------------------------------
# Playwright API 调用核心
# ---------------------------------------------------------------------------


def _fetch_varieties(page: "Page", pid: str = AQUATIC_PID) -> list[dict[str, Any]]:
    """通过 API 获取水产品品种列表.

    Returns:
        [{"id": "1018", "name": "三文鱼", "code": "AM01020"}, ...]
    """
    raw = page.evaluate(f"""
        () => {{
            return new Promise((resolve) => {{
                fetch('/api/priceQuotationController/getVarietyNameByPid?pid={pid}', {{
                    method: 'POST'
                }})
                .then(r => r.json())
                .then(d => {{
                    var varieties = [];
                    if (d.content) {{
                        d.content.forEach(function(group) {{
                            if (Array.isArray(group)) {{
                                group.forEach(function(v) {{
                                    if (v.varietyName) {{
                                        varieties.push({{
                                            id: v.id,
                                            name: v.varietyName,
                                            code: v.varietyCode || '',
                                            typeName: v.varietyTypeName || ''
                                        }});
                                    }}
                                }});
                            }}
                        }});
                    }}
                    resolve(JSON.stringify(varieties));
                }})
                .catch(e => resolve(JSON.stringify([])));
            }});
        }}
    """)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def _fetch_price_chart(
    page: "Page",
    variety_id: str,
    market_ids: str = "",
    province_codes: str = "",
) -> Optional[dict[str, Any]]:
    """调用价格 API 并用前端 decryptAes 解密响应.

    Returns:
        {"date": "2026-02-27", "x": ["市场1", ...], "y": [18.5, ...]}
    """
    raw = page.evaluate(f"""
        () => {{
            return new Promise((resolve) => {{
                var app = null;
                try {{
                    var el = document.querySelector('#app');
                    if (el && el.__vue__) app = el.__vue__;
                }} catch(e) {{}}

                fetch('/price_portal/index/getMarketReportPriceChart?marketIDs={market_ids}&provinceCodes={province_codes}&varietyID={variety_id}', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: '{{}}'
                }})
                .then(r => r.json())
                .then(d => {{
                    if ((d.code === 0 || d.code === 200) && d.data && typeof d.data === 'string') {{
                        if (app && typeof app.decryptAes === 'function') {{
                            try {{
                                var decrypted = app.decryptAes(d.data);
                                resolve(decrypted);
                                return;
                            }} catch(e) {{}}
                        }}
                        // Fallback: try to find decryptAes on prototype chain
                        try {{
                            var proto = Object.getPrototypeOf(app);
                            while (proto) {{
                                if (typeof proto.decryptAes === 'function') {{
                                    resolve(proto.decryptAes(d.data));
                                    return;
                                }}
                                proto = Object.getPrototypeOf(proto);
                            }}
                        }} catch(e) {{}}
                        // Return encrypted if can't decrypt
                        resolve(JSON.stringify({{"encrypted": true, "raw": d.data.substring(0, 100)}}));
                    }} else {{
                        resolve(JSON.stringify(d));
                    }}
                }})
                .catch(e => resolve(JSON.stringify({{"error": e.message}})));
            }});
        }}
    """)
    try:
        if isinstance(raw, str):
            return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _parse_chart_data(
    chart_data: dict[str, Any],
    variety_name: str,
) -> list[dict[str, Any]]:
    """将解密后的图表数据转为行级字典列表."""
    if not chart_data or "x" not in chart_data or "y" not in chart_data:
        return []

    markets = chart_data.get("x", [])
    prices = chart_data.get("y", [])
    date_str = chart_data.get("date", "")
    storage_method = _guess_storage_method(variety_name)

    rows: list[dict[str, Any]] = []
    for market, price in zip(markets, prices):
        if price is None:
            continue
        try:
            avg_price = float(price)
        except (ValueError, TypeError):
            continue
        rows.append({
            "product_name": variety_name,
            "market_name": _clean(str(market)),
            "region": "",
            "spec": "",
            "min_price": None,
            "max_price": None,
            "avg_price": avg_price,
            "unit": "元/公斤",
            "storage_method": storage_method,
            "date": _clean(str(date_str)),
            "remark": "",
        })
    return rows


# ---------------------------------------------------------------------------
# run() — 主入口
# ---------------------------------------------------------------------------


def run(conn, *, url: Optional[str] = None) -> int:
    """采集农业农村部水产品批发市场价格.

    Args:
        conn: MySQL 连接.
        url: 覆盖默认 URL (用于测试).

    Returns:
        成功写入 raw_event 的水产品价格行数.
    """
    if sync_playwright is None:
        raise RuntimeError(
            f"playwright is not installed: {_PW_IMPORT_ERR}\n"
            "Tip: pip install playwright && python -m playwright install chromium"
        )

    target_url = url or os.getenv("MOA_PRICE_URL", "").strip() or PRICE_MARKET_URL
    headless = os.getenv("MOA_PRICE_HEADLESS", "1").strip() != "0"
    strict_filter = os.getenv("MOA_PRICE_STRICT_FILTER", "0").strip() == "1"
    snapshot_time = datetime.now()

    chrome_path = _resolve_chrome_path()
    launch_args = [
        "--no-proxy-server", "--disable-gpu",
        "--no-first-run", "--no-default-browser-check",
    ]

    all_rows: list[dict[str, Any]] = []

    LOGGER.info(
        "moa_prices: headless=%s chrome=%s target=%s",
        headless, chrome_path or "<bundled>", target_url,
    )

    with sync_playwright() as pw:
        launch_kwargs: dict[str, Any] = {"headless": headless, "args": launch_args}
        if chrome_path:
            launch_kwargs["executable_path"] = chrome_path

        browser = pw.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            # 1. 打开页面 (需要 SPA 环境初始化 decryptAes)
            page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)
            LOGGER.info("moa_prices: page loaded")

            # 2. 获取水产品品种列表
            varieties = _fetch_varieties(page, AQUATIC_PID)
            LOGGER.info("moa_prices: found %d aquatic varieties", len(varieties))

            if not varieties:
                LOGGER.warning("moa_prices: no varieties returned from API")

            # 3. 逐品种调用价格 API
            for var in varieties:
                var_id = str(var.get("id", ""))
                var_name = var.get("name", "")
                if not var_id or not var_name:
                    continue

                chart_data = _fetch_price_chart(page, var_id)
                if not chart_data:
                    continue

                if chart_data.get("encrypted"):
                    LOGGER.debug(
                        "moa_prices: could not decrypt data for %s (id=%s)",
                        var_name, var_id,
                    )
                    continue

                if chart_data.get("error"):
                    LOGGER.debug(
                        "moa_prices: API error for %s: %s",
                        var_name, chart_data["error"],
                    )
                    continue

                rows = _parse_chart_data(chart_data, var_name)
                if rows:
                    LOGGER.info(
                        "moa_prices: %s (id=%s) → %d price records",
                        var_name, var_id, len(rows),
                    )
                    all_rows.extend(rows)

        except Exception as exc:
            LOGGER.error("moa_prices: browser session failed: %s", exc)
        finally:
            context.close()
            browser.close()

    if not all_rows:
        LOGGER.warning("moa_prices: no price rows found")
        return 0

    LOGGER.info("moa_prices: total rows = %d", len(all_rows))

    # --- 过滤 ---
    # 采集源已经按 AQUATIC_PID=AM 拉取了全量水产品。
    # 默认保留全量，仅 strict 模式下再收敛到 salmon 相关品类。
    if strict_filter:
        filtered = filter_aquatic_rows(all_rows, strict=True)
        LOGGER.info(
            "moa_prices filter: mode=strict total=%d selected=%d",
            len(all_rows), len(filtered),
        )
        if not filtered:
            LOGGER.info("moa_prices: strict filter hit nothing, keeping all %d rows", len(all_rows))
            filtered = all_rows
    else:
        filtered = all_rows
        LOGGER.info(
            "moa_prices filter: mode=off total=%d selected=%d",
            len(all_rows), len(filtered),
        )

    # --- 存储 raw_event ---
    written = 0
    for row in filtered:
        normalized = normalize_row(row, snapshot_time=snapshot_time)
        try:
            insert_raw_event(
                conn,
                source_name=SOURCE_NAME,
                url=target_url,
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
                raw_text=None,
            )
            written += 1
        except Exception as exc:
            LOGGER.warning(
                "moa_prices db write failed: product=%s market=%s err=%s",
                row.get("product_name"), row.get("market_name"), exc,
            )

    LOGGER.info("moa_prices done: written=%d", written)
    return written


# ---------------------------------------------------------------------------
# 独立运行模式 (无 DB)
# ---------------------------------------------------------------------------


def run_standalone(
    *,
    url: Optional[str] = None,
    save_json: bool = True,
    target_varieties: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """不依赖数据库的独立运行，适合调试.

    Args:
        url: 覆盖默认 URL.
        save_json: 是否保存 JSON 到文件.
        target_varieties: 只采集指定品种名称 (None = 全部).
    """
    if sync_playwright is None:
        raise RuntimeError(
            f"playwright is not installed: {_PW_IMPORT_ERR}\n"
            "Tip: pip install playwright && python -m playwright install chromium"
        )

    target_url = url or os.getenv("MOA_PRICE_URL", "").strip() or PRICE_MARKET_URL
    headless = os.getenv("MOA_PRICE_HEADLESS", "1").strip() != "0"
    snapshot_time = datetime.now()

    chrome_path = _resolve_chrome_path()
    launch_args = ["--no-proxy-server", "--disable-gpu", "--no-first-run"]

    all_rows: list[dict[str, Any]] = []

    LOGGER.info(
        "moa_prices standalone: headless=%s chrome=%s",
        headless, chrome_path or "<bundled>",
    )

    with sync_playwright() as pw:
        launch_kwargs: dict[str, Any] = {"headless": headless, "args": launch_args}
        if chrome_path:
            launch_kwargs["executable_path"] = chrome_path

        browser = pw.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(5000)

            varieties = _fetch_varieties(page, AQUATIC_PID)
            LOGGER.info("moa_prices standalone: %d varieties", len(varieties))

            # 按目标品种过滤
            if target_varieties:
                varieties = [
                    v for v in varieties
                    if any(t in v.get("name", "") for t in target_varieties)
                ]
                LOGGER.info(
                    "moa_prices standalone: filtered to %d target varieties",
                    len(varieties),
                )

            for var in varieties:
                var_id = str(var.get("id", ""))
                var_name = var.get("name", "")
                if not var_id or not var_name:
                    continue

                chart_data = _fetch_price_chart(page, var_id)
                if not chart_data or chart_data.get("encrypted") or chart_data.get("error"):
                    continue

                rows = _parse_chart_data(chart_data, var_name)
                if rows:
                    all_rows.extend(rows)
                    LOGGER.info("  %s → %d records", var_name, len(rows))

        except Exception as exc:
            LOGGER.error("moa_prices standalone failed: %s", exc)
        finally:
            context.close()
            browser.close()

    LOGGER.info("moa_prices standalone: total rows = %d", len(all_rows))

    results = [normalize_row(r, snapshot_time=snapshot_time) for r in all_rows]

    if save_json and results:
        out_path = Path(__file__).resolve().parent / "moa_prices_output.json"
        serializable = [
            {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in r.items()}
            for r in results
        ]
        out_path.write_text(
            json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        LOGGER.info("moa_prices standalone: saved to %s", out_path)

    return results


# ---------------------------------------------------------------------------
# 直接执行
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="农业农村部水产品价格采集 (Playwright)")
    parser.add_argument("--no-db", action="store_true", help="不连接数据库，仅输出到控制台/JSON")
    parser.add_argument("--url", default=None, help="覆盖目标URL")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器窗口 (调试用)")
    parser.add_argument(
        "--species", nargs="*", default=None,
        help="只采集指定品种 (如 --species 虹鳟鱼 三文鱼)",
    )
    args = parser.parse_args()

    if args.no_headless:
        os.environ["MOA_PRICE_HEADLESS"] = "0"

    if args.no_db:
        results = run_standalone(url=args.url, target_varieties=args.species)
        print(f"\n[OK] moa_prices standalone: {len(results)} items")
        for r in results[:15]:
            print(
                f"  {r.get('product_name_raw', '?'):12s} | "
                f"{r.get('market_name', '?'):20s} | "
                f"¥{r.get('price', '?'):>8} | {r.get('date_str', '?')}"
            )
        if len(results) > 15:
            print(f"  ... ({len(results) - 15} more)")
    else:
        connection = get_conn()
        try:
            count = run(connection, url=args.url)
            print(f"[OK] moa_prices items={count}")
        finally:
            connection.close()
