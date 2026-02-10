import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Union
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from DrissionPage import ChromiumOptions, ChromiumPage
from DrissionPage.common import Keys

try:
    from common.db import get_conn, insert_raw_event, upsert_product_snapshot
    from common.logger import get_logger
except ModuleNotFoundError:
    # Support direct execution: python fish_intel_mvp/jobs/crawl_jd.py
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from common.db import get_conn, insert_raw_event, upsert_product_snapshot
    from common.logger import get_logger

LOGGER = get_logger(__name__)


def _clean_text(text: Optional[str]) -> str:
    return (text or "").replace("\n", " ").strip()


def _extract_float(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    norm = text.replace(",", "")
    norm = re.sub(r"\s*\.\s*", ".", norm)
    norm = re.sub(r"\s+", "", norm)
    match = re.search(r"\d+(?:\.\d+)?", norm)
    return float(match.group(0)) if match else None


def _extract_price_from_blob(text: str) -> Optional[float]:
    if not text:
        return None
    m = re.search(r"[¥￥]\s*([0-9]+(?:\s*\.\s*[0-9]+)?)", text)
    if m:
        return _extract_float(m.group(0))
    return _extract_float(text)


def _normalize_url(href: Optional[str]) -> str:
    if not href:
        return ""
    href = href.strip()
    if href.startswith("//"):
        return f"https:{href}"
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return f"https://www.jd.com{href}"
    return f"https://{href.lstrip('/')}"


def _safe_ele_text(ele) -> str:
    try:
        return _clean_text(ele.text)
    except Exception:
        return ""


def _row_ele_now(row, selector):
    try:
        return row.ele(selector, timeout=0)
    except TypeError:
        try:
            return row.ele(selector)
        except Exception:
            return None
    except Exception:
        return None


def _row_text_now(row, selector) -> str:
    return _safe_ele_text(_row_ele_now(row, selector))


def _safe_page_title(dp: ChromiumPage) -> str:
    try:
        return _clean_text(dp.title)
    except Exception:
        return ""


def _first_non_empty(*values: str) -> str:
    for value in values:
        v = _clean_text(value)
        if v:
            return v
    return ""


def _get_product_rows(dp: ChromiumPage):
    selectors = [
        # New JD search page structure.
        "css:div[data-sku]",
        "css:div.plugin_goodsCardWrapper[data-sku]",
        "css:div[class*='goodsCardWrapper'][data-sku]",
        # Old structure fallback.
        "css:#J_goodsList .gl-item",
        "css:.gl-warp .gl-item",
        "css:li.gl-item",
        "css:li[data-sku]",
    ]
    for selector in selectors:
        rows = dp.eles(selector) or []
        if rows:
            LOGGER.info("jd row selector hit: selector=%s count=%s", selector, len(rows))
            return rows
    return []


def _extract_item_from_row(row):
    seen = {}
    try:
        sku = _clean_text(row.attr("data-sku"))
    except Exception:
        sku = ""

    # New JD card by sku.
    if sku:
        title_ele = (
            _row_ele_now(row, "css:[class*='title'][title]")
            or _row_ele_now(row, "css:[class*='title']")
            or _row_ele_now(row, "css:h5[title]")
            or _row_ele_now(row, "css:h5")
        )
        title = ""
        if title_ele:
            try:
                title = _clean_text(title_ele.attr("title")) or _safe_ele_text(title_ele)
            except Exception:
                title = _safe_ele_text(title_ele)
        if not title:
            return None

        price_text = _first_non_empty(
            _row_text_now(row, "css:[class*='price']"),
            _row_text_now(row, "css:[class*='priceConter']"),
        )
        if not price_text:
            price_text = _safe_ele_text(row)
        price = _extract_price_from_blob(price_text)
        if price is None:
            return None

        commit = _first_non_empty(
            _row_text_now(row, "css:[class*='comment']"),
            _row_text_now(row, "css:.p-commit a"),
        )
        shop = _first_non_empty(
            _row_text_now(row, "css:[class*='shop']"),
            _row_text_now(row, "css:.hd-shopname"),
            _row_text_now(row, "css:.p-shop a"),
        )
        detail_url = f"https://item.jd.com/{sku}.html"
        seen["key"] = detail_url

        return {
            "seen_key": seen["key"],
            "item": {
                "title": title,
                "price": price,
                "original_price": None,
                "sales_or_commit": commit,
                "shop": shop,
                "detail_url": detail_url,
                "province": None,
                "city": None,
                "category": None,
                "raw": {
                    "sku": sku,
                    "title": title,
                    "price_text": price_text[:300],
                    "commit_text": commit,
                    "shop": shop,
                    "detail_url": detail_url,
                    "extractor": "data_sku_dom",
                },
            },
        }

    # Old JD structure fallback.
    title = _first_non_empty(
        _row_text_now(row, "css:.p-name a em"),
        _row_text_now(row, "css:.p-name em"),
        _row_text_now(row, "css:.p-name-type-2 a em"),
        _row_text_now(row, "css:.p-name-type-2 em"),
        _row_text_now(row, "css:.p-name a"),
        _row_text_now(row, "css:.p-name"),
    )
    link_ele = _row_ele_now(row, "css:.p-name a") or _row_ele_now(row, "css:.p-name-type-2 a")
    href = ""
    if link_ele:
        href = (link_ele.attr("href") or "").strip() or (link_ele.attr("data-href") or "").strip()
    detail_url = _normalize_url(href)
    if not title or not detail_url:
        return None

    price_text = _first_non_empty(
        _row_text_now(row, "css:.p-price i"),
        _row_text_now(row, "css:.p-price"),
    )
    price = _extract_price_from_blob(price_text)
    if price is None:
        return None

    commit = _row_text_now(row, "css:.p-commit a")
    shop = _first_non_empty(
        _row_text_now(row, "css:.hd-shopname"),
        _row_text_now(row, "css:.p-shop a"),
    )
    seen["key"] = detail_url
    return {
        "seen_key": seen["key"],
        "item": {
            "title": title,
            "price": price,
            "original_price": None,
            "sales_or_commit": commit,
            "shop": shop,
            "detail_url": detail_url,
            "province": None,
            "city": None,
            "category": None,
            "raw": {
                "title": title,
                "price_text": price_text,
                "commit_text": commit,
                "shop": shop,
                "detail_url": detail_url,
                "extractor": "old_dom",
            },
        },
    }


def _extract_items_from_page(dp: ChromiumPage) -> list[dict]:
    rows = _get_product_rows(dp)
    if not rows:
        return []
    items: list[dict] = []
    seen = set()
    for row in rows:
        result = _extract_item_from_row(row)
        if not result:
            continue
        seen_key = result["seen_key"]
        if seen_key in seen:
            continue
        seen.add(seen_key)
        items.append(result["item"])
    return items


def _extract_items_from_html(dp: ChromiumPage) -> list[dict]:
    try:
        html = dp.html or ""
    except Exception:
        html = ""
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []
    seen_urls = set()

    # New structure first.
    for card in soup.select("div[data-sku]"):
        sku = _clean_text(card.get("data-sku"))
        if not sku:
            continue
        detail_url = f"https://item.jd.com/{sku}.html"
        if detail_url in seen_urls:
            continue

        title_tag = (
            card.select_one("[class*='title'][title]")
            or card.select_one("[class*='title']")
            or card.select_one("h5[title]")
            or card.select_one("h5")
        )
        title = ""
        if title_tag:
            title = _clean_text(title_tag.get("title") or title_tag.get_text(" ", strip=True))
        if not title:
            continue

        price_text = ""
        price_tag = card.select_one("[class*='price']")
        if price_tag:
            price_text = _clean_text(price_tag.get_text(" ", strip=True))
        if not price_text:
            price_text = _clean_text(card.get_text(" ", strip=True))
        price = _extract_price_from_blob(price_text)
        if price is None:
            continue

        commit_tag = card.select_one("[class*='comment'], .p-commit a")
        shop_tag = card.select_one("[class*='shop'], .hd-shopname, .p-shop a")
        commit = _clean_text(commit_tag.get_text(" ", strip=True)) if commit_tag else ""
        shop = _clean_text(shop_tag.get_text(" ", strip=True)) if shop_tag else ""

        items.append(
            {
                "title": title,
                "price": price,
                "original_price": None,
                "sales_or_commit": commit,
                "shop": shop,
                "detail_url": detail_url,
                "province": None,
                "city": None,
                "category": None,
                "raw": {
                    "sku": sku,
                    "title": title,
                    "price_text": price_text[:300],
                    "commit_text": commit,
                    "shop": shop,
                    "detail_url": detail_url,
                    "extractor": "data_sku_html",
                },
            }
        )
        seen_urls.add(detail_url)
        if len(items) >= 300:
            break

    if items:
        return items

    # Legacy anchor-based fallback.
    for a in soup.select("a[href*='item.jd.com'], a[href*='item.m.jd.com']"):
        href = _normalize_url(a.get("href") or "")
        if not href or href in seen_urls:
            continue
        title = _clean_text(a.get("title") or a.get_text(" ", strip=True))
        if not title:
            continue
        node = a
        for _ in range(6):
            if not node.parent:
                break
            node = node.parent
        text_blob = _clean_text(node.get_text(" ", strip=True))
        price = _extract_price_from_blob(text_blob)
        if price is None:
            continue
        items.append(
            {
                "title": title,
                "price": price,
                "original_price": None,
                "sales_or_commit": "",
                "shop": "",
                "detail_url": href,
                "province": None,
                "city": None,
                "category": None,
                "raw": {
                    "title": title,
                    "price_text": text_blob[:300],
                    "detail_url": href,
                    "extractor": "anchor_html",
                },
            }
        )
        seen_urls.add(href)
        if len(items) >= 300:
            break
    return items


def _save_debug_html(dp: ChromiumPage, keyword: str):
    try:
        html = dp.html or ""
    except Exception:
        html = ""
    if not html:
        return
    path = Path("fish_intel_mvp/jd_debug.html")
    path.write_text(html, encoding="utf-8")
    stats = {
        "html_len": len(html),
        "data_sku_token": html.count("data-sku"),
        "item_jd_token": html.count("item.jd.com"),
        "gl_item_token": html.count("gl-item"),
    }
    LOGGER.info("jd debug html saved: %s", path.resolve())
    LOGGER.info("jd dom stats: %s", stats)


def _wait_page_ready(dp: ChromiumPage, seconds: int = 30):
    end = time.time() + seconds
    while time.time() < end:
        rows = _get_product_rows(dp)
        if rows:
            return True
        time.sleep(1.0)
        try:
            dp.scroll.down(300)
        except Exception:
            pass
    return False


def _go_next_page(dp: ChromiumPage) -> bool:
    selectors = ["css:.pn-next", "css:a.pn-next", "css:.fp-next"]
    for selector in selectors:
        try:
            btn = dp.ele(selector)
            if not btn:
                continue
            cls = (btn.attr("class") or "").lower()
            if "disabled" in cls:
                return False
            btn.click()
            time.sleep(2)
            return True
        except Exception:
            continue
    try:
        first = dp.ele("css:[data-sku], .gl-item")
        if first:
            first.input(Keys.RIGHT)
            time.sleep(2)
            return True
    except Exception:
        pass
    return False


def run(conn, keywords: Optional[list[str]] = None, pages: Optional[int] = None) -> int:
    source_name = "jd"
    keywords = keywords or [
        k.strip() for k in os.getenv("JD_KEYWORDS", "大黄鱼").split(",") if k.strip()
    ]
    if not keywords:
        keywords = ["大黄鱼"]

    page_count_raw: Union[str, int]
    if pages is None:
        page_count_raw = os.getenv("JD_PAGES", "1")
    else:
        page_count_raw = pages
    page_count = int(page_count_raw)
    page_count = max(1, page_count)
    login_wait_seconds = max(0, int(os.getenv("JD_LOGIN_WAIT_SECONDS", "20")))
    max_items_per_page = max(1, int(os.getenv("JD_MAX_ITEMS_PER_PAGE", "40")))
    max_run_seconds = max(30, int(os.getenv("JD_MAX_RUN_SECONDS", "240")))
    run_started_at = time.time()

    snapshot_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    inserted = 0

    options = ChromiumOptions()
    options.set_argument("--no-proxy-server")
    options.set_argument("--disable-gpu")
    options.set_user_agent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    dp = ChromiumPage(options)
    try:
        for keyword in keywords:
            search_url = f"https://search.jd.com/Search?keyword={quote_plus(keyword)}&enc=utf-8"
            LOGGER.info("start jd crawl: keyword=%s pages=%s", keyword, page_count)
            dp.get(search_url)
            time.sleep(2)

            if "passport.jd.com" in (dp.url or ""):
                LOGGER.info(
                    "jd login page detected, please scan QR within %ss",
                    login_wait_seconds,
                )
                end = time.time() + login_wait_seconds
                while time.time() < end:
                    if "passport.jd.com" not in (dp.url or ""):
                        break
                    time.sleep(1)
                dp.get(search_url)
                time.sleep(2)

            _wait_page_ready(dp, seconds=25)

            for page_no in range(1, page_count + 1):
                if time.time() - run_started_at > max_run_seconds:
                    LOGGER.warning("jd max runtime reached (%ss), force stop", max_run_seconds)
                    return inserted
                try:
                    dp.scroll.to_bottom()
                except Exception:
                    pass
                time.sleep(1.5)

                page_items = _extract_items_from_page(dp)
                if not page_items:
                    page_items = _extract_items_from_html(dp)
                if not page_items:
                    _save_debug_html(dp, keyword)
                if len(page_items) > max_items_per_page:
                    LOGGER.info(
                        "jd trim items per page: %s -> %s",
                        len(page_items),
                        max_items_per_page,
                    )
                    page_items = page_items[:max_items_per_page]

                LOGGER.info(
                    "jd page parsed: keyword=%s page=%s items=%s url=%s title=%s",
                    keyword,
                    page_no,
                    len(page_items),
                    dp.url,
                    _safe_page_title(dp),
                )

                for idx, item in enumerate(page_items, start=1):
                    if time.time() - run_started_at > max_run_seconds:
                        LOGGER.warning(
                            "jd max runtime reached during db writes (%ss), force stop",
                            max_run_seconds,
                        )
                        return inserted
                    raw_id = insert_raw_event(
                        conn,
                        source_name=source_name,
                        url=item["detail_url"],
                        title=item["title"],
                        raw_json=json.dumps(item["raw"], ensure_ascii=False),
                    )
                    upsert_product_snapshot(
                        conn,
                        {
                            "platform": "jd",
                            "keyword": keyword,
                            "title": item["title"],
                            "price": item["price"],
                            "original_price": item["original_price"],
                            "sales_or_commit": item["sales_or_commit"],
                            "shop": item["shop"],
                            "province": item["province"],
                            "city": item["city"],
                            "detail_url": item["detail_url"],
                            "category": item["category"],
                            "snapshot_time": snapshot_time,
                            "raw_id": raw_id,
                        },
                    )
                    inserted += 1
                    if idx % 10 == 0 or idx == len(page_items):
                        LOGGER.info(
                            "jd db progress: page=%s %s/%s inserted_total=%s",
                            page_no,
                            idx,
                            len(page_items),
                            inserted,
                        )

                if page_no < page_count:
                    if not _go_next_page(dp):
                        LOGGER.info("jd no next page, stop early on page=%s", page_no)
                        break
                    time.sleep(2)
    finally:
        try:
            dp.quit()
        except Exception:
            pass

    return inserted


if __name__ == "__main__":
    conn = get_conn()
    try:
        count = run(conn)
        print(f"[OK] jd items={count}")
    finally:
        conn.close()
