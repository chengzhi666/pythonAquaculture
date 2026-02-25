import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import quote

import requests

try:
    from common.db import get_conn, insert_raw_event, upsert_product_snapshot
    from common.logger import get_logger
    from jobs.refresh_taobao_cookie import refresh_taobao_cookie
except ModuleNotFoundError:
    # Support direct execution: python fish_intel_mvp/jobs/crawl_taobao.py
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from common.db import get_conn, insert_raw_event, upsert_product_snapshot
    from common.logger import get_logger
    from refresh_taobao_cookie import refresh_taobao_cookie

LOGGER = get_logger(__name__)

SOURCE_NAME = "taobao"
API_NAME = "mtop.relationrecommend.wirelessrecommend.recommend"
API_URL = "https://h5api.m.taobao.com/h5/mtop.relationrecommend.wirelessrecommend.recommend/2.0/"

DEFAULT_APP_KEY = "12574478"
DEFAULT_APP_ID = "34385"
DEFAULT_REFERER = "https://s.taobao.com/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36"
)

BASE_EP_PARAMS: dict[str, Any] = {
    "device": "HMA-AL00",
    "isBeta": "false",
    "grayHair": "false",
    "from": "nt_history",
    "brand": "HUAWEI",
    "info": "wifi",
    "index": "4",
    "rainbow": "",
    "schemaType": "auction",
    "elderHome": "false",
    "isEnterSrpSearch": "true",
    "newSearch": "false",
    "network": "wifi",
    "subtype": "",
    "hasPreposeFilter": "false",
    "prepositionVersion": "v2",
    "client_os": "Android",
    "gpsEnabled": "false",
    "searchDoorFrom": "srp",
    "debug_rerankNewOpenCard": "false",
    "homePageVersion": "v7",
    "searchElderHomeOpen": "false",
    "search_action": "initiative",
    "sugg": "_4_1",
    "sversion": "13.6",
    "style": "list",
    "ttid": "600000@taobao_pc_10.7.0",
    "needTabs": "true",
    "areaCode": "CN",
    "vm": "nw",
    "countryNum": "156",
    "m": "pc",
    "qSource": "url",
    "pageSource": "",
    "channelSrp": "",
    "tab": "all",
    "sourceS": "1",
    "sort": "_coefp",
    "bcoffset": "-3",
    "ntoffset": "0",
    "filterTag": "",
    "service": "",
    "prop": "",
    "loc": "",
    "start_price": None,
    "end_price": None,
    "startPrice": None,
    "endPrice": None,
    "categoryp": "",
    "ha3Kvpairs": None,
    "couponFilter": 0,
    "screenResolution": "1536x864",
    "viewResolution": "634x4675",
    "couponUnikey": "",
    "subTabId": "",
    "np": "",
    "clientType": "h5",
    "isNewDomainAb": "false",
    "forceOldDomain": "false",
}


class TokenExpiredError(RuntimeError):
    """Raised when Taobao API tells us `_m_h5_tk` is expired."""


def _is_true(raw: str) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _auto_refresh_enabled() -> bool:
    return _is_true(os.getenv("TAOBAO_AUTO_REFRESH_COOKIE", "1"))


def _try_refresh_cookie(reason: str) -> Optional[str]:
    if not _auto_refresh_enabled():
        LOGGER.warning("taobao auto cookie refresh disabled: reason=%s", reason)
        return None

    timeout_seconds = max(10, int(os.getenv("TAOBAO_COOKIE_REFRESH_TIMEOUT_SECONDS", "180")))
    poll_interval = max(0.2, float(os.getenv("TAOBAO_COOKIE_REFRESH_POLL_SECONDS", "1.0")))
    start_url = (
        os.getenv("TAOBAO_COOKIE_REFRESH_START_URL", "").strip()
        or "https://login.taobao.com/member/login.jhtml"
    )

    LOGGER.info("taobao auto cookie refresh triggered: reason=%s", reason)
    try:
        cookie = refresh_taobao_cookie(
            timeout_seconds=timeout_seconds,
            poll_interval=poll_interval,
            start_url=start_url,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("taobao cookie refresh failed: reason=%s err=%s", reason, exc)
        return None

    if cookie:
        os.environ["TAOBAO_COOKIE"] = cookie
    return cookie or None


def _split_env_list(raw: str) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def _extract_cookie_value(cookie: str, key: str) -> str:
    pattern = rf"(?:^|;\s*){re.escape(key)}=([^;]+)"
    match = re.search(pattern, cookie)
    return match.group(1).strip() if match else ""


def _extract_token_from_cookie_value(value: str) -> Optional[str]:
    raw = (value or "").strip()
    if not raw:
        return None
    if "_" in raw:
        raw = raw.split("_", 1)[0].strip()
    return raw or None


def _extract_token_from_cookie(cookie: str) -> Optional[str]:
    return _extract_token_from_cookie_value(_extract_cookie_value(cookie, "_m_h5_tk"))


def _seed_session_cookies(session: requests.Session, cookie: str) -> None:
    for part in cookie.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        session.cookies.set(key, value)


def _cookie_dict_from_jar(session: requests.Session) -> dict[str, str]:
    merged: dict[str, str] = {}
    for cookie in session.cookies:
        merged[cookie.name] = cookie.value
    return merged


def _build_session(cookie: str, user_agent: str) -> requests.Session:
    session = requests.Session()
    # Keep behavior stable across environments with broken proxy vars.
    session.trust_env = False
    _seed_session_cookies(session, cookie)
    session.headers.update(
        {
            "Referer": DEFAULT_REFERER,
            "User-Agent": user_agent,
        }
    )
    return session


def _build_ep_params(keyword: str, page: int, page_size: int, user_agent: str, my_cna: str) -> dict:
    ep = dict(BASE_EP_PARAMS)
    ep["page"] = page
    ep["n"] = page_size
    ep["pageSize"] = str(page_size)
    ep["q"] = quote(keyword, safe="")
    ep["userAgent"] = user_agent
    ep["myCNA"] = my_cna
    return ep


def _build_data_payload(app_id: str, ep_params: dict) -> str:
    data = {
        "appId": str(app_id),
        "params": json.dumps(ep_params, separators=(",", ":"), ensure_ascii=False),
    }
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def _make_sign(token: str, timestamp_ms: int, app_key: str, payload: str) -> str:
    raw = f"{token}&{timestamp_ms}&{app_key}&{payload}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _parse_jsonp(text: str, callback: str) -> dict:
    body = (text or "").strip()
    if not body:
        raise RuntimeError("empty response body")

    if body.startswith("{"):
        return json.loads(body)

    pattern = rf"^\s*{re.escape(callback)}\((.*)\)\s*;?\s*$"
    match = re.match(pattern, body, flags=re.DOTALL)
    if not match:
        raise RuntimeError(f"unexpected jsonp payload, callback={callback}")
    return json.loads(match.group(1))


def _ensure_api_success(payload: dict) -> None:
    ret = payload.get("ret")
    if isinstance(ret, list):
        summary = " | ".join(str(x) for x in ret)
    else:
        summary = str(ret or "")
    if "SUCCESS" in summary:
        return
    if "FAIL_SYS_TOKEN_EXOIRED" in summary:
        raise TokenExpiredError(summary)
    if summary:
        raise RuntimeError(f"taobao api failed: {summary}")
    raise RuntimeError("taobao api failed: missing ret")


def _strip_html(text: Optional[str]) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _extract_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _parse_procity(value: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    text = (value or "").strip()
    if not text:
        return None, None
    parts = [x for x in re.split(r"\s+", text) if x]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return parts[0], None


def _normalize_detail_url(item: dict) -> Optional[str]:
    for key in ("itemUrl", "url", "detail_url"):
        raw = str(item.get(key) or "").strip()
        if not raw:
            continue
        if raw.startswith("//"):
            return f"https:{raw}"
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        if raw.startswith("/"):
            return f"https://s.taobao.com{raw}"

    item_id = str(item.get("item_id") or item.get("itemId") or "").strip()
    if item_id:
        return f"https://item.taobao.com/item.htm?id={item_id}"
    return None


def _extract_products(payload: dict, keyword: str) -> list[dict]:
    data = payload.get("data") or {}
    items = data.get("itemsArray") or []
    if not isinstance(items, list):
        return []

    products: list[dict] = []
    for src in items:
        if not isinstance(src, dict):
            continue

        title = _strip_html(src.get("title"))
        if not title:
            continue

        detail_url = _normalize_detail_url(src)
        if not detail_url:
            continue

        province, city = _parse_procity(src.get("procity"))
        sales = str(src.get("realSales") or src.get("sales") or "").strip()
        item_id = str(src.get("item_id") or src.get("itemId") or "").strip()

        products.append(
            {
                "keyword": keyword,
                "item_id": item_id or None,
                "title": title,
                "price": _extract_float(src.get("price")),
                "original_price": _extract_float(
                    src.get("origPrice") or src.get("priceBeforeCoupon") or src.get("originalPrice")
                ),
                "sales_or_commit": sales or None,
                "shop": str(src.get("nick") or src.get("shopName") or "").strip() or None,
                "province": province,
                "city": city,
                "category": str(src.get("category") or "").strip() or None,
                "detail_url": detail_url,
                "raw_item": src,
            }
        )

    return products


def _fetch_page(
    session: requests.Session,
    *,
    token: str,
    app_key: str,
    app_id: str,
    keyword: str,
    page: int,
    page_size: int,
    timeout_seconds: int,
    user_agent: str,
    my_cna: str,
) -> tuple[list[dict], str]:
    timestamp_ms = int(time.time() * 1000)
    callback = f"mtopjsonp{(timestamp_ms % 100000) + page}"
    ep_params = _build_ep_params(
        keyword=keyword,
        page=page,
        page_size=page_size,
        user_agent=user_agent,
        my_cna=my_cna,
    )
    data_payload = _build_data_payload(app_id, ep_params)
    sign = _make_sign(token, timestamp_ms, app_key, data_payload)

    params = {
        "jsv": "2.7.4",
        "appKey": app_key,
        "t": str(timestamp_ms),
        "sign": sign,
        "api": API_NAME,
        "v": "2.0",
        "timeout": "10000",
        "type": "jsonp",
        "dataType": "jsonp",
        "callback": callback,
        "data": data_payload,
        "bx-ua": "fast-load",
    }

    resp = session.get(
        API_URL,
        params=params,
        cookies=_cookie_dict_from_jar(session),
        timeout=timeout_seconds,
    )
    resp.raise_for_status()

    payload = _parse_jsonp(resp.text, callback=callback)
    _ensure_api_success(payload)
    return _extract_products(payload, keyword=keyword), resp.text


def run(
    conn,
    *,
    keywords: Optional[list[str]] = None,
    pages: Optional[int] = None,
    enrich_item_fn: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
    source_name: str = SOURCE_NAME,
) -> int:
    cookie = os.getenv("TAOBAO_COOKIE", "").strip()
    if not cookie:
        cookie = _try_refresh_cookie("cookie_missing") or ""
        if not cookie:
            LOGGER.warning("taobao skipped: TAOBAO_COOKIE is empty")
            return 0

    token = _extract_token_from_cookie(cookie)
    if not token:
        refreshed = _try_refresh_cookie("token_missing_in_cookie")
        if refreshed:
            cookie = refreshed
            token = _extract_token_from_cookie(cookie)
        if not token:
            LOGGER.warning("taobao skipped: `_m_h5_tk` not found in TAOBAO_COOKIE")
            return 0

    keywords = keywords or _split_env_list(os.getenv("TAOBAO_KEYWORDS", "salmon"))
    if not keywords:
        keywords = ["salmon"]

    max_pages = max(1, int(pages)) if pages is not None else max(1, int(os.getenv("TAOBAO_PAGES", "1")))
    page_size = max(1, min(50, int(os.getenv("TAOBAO_PAGE_SIZE", "50"))))
    max_items = max(1, int(os.getenv("TAOBAO_MAX_ITEMS", "500")))
    sleep_seconds = max(0.0, float(os.getenv("TAOBAO_SLEEP_SECONDS", "1.0")))
    timeout_seconds = max(5, int(os.getenv("TAOBAO_TIMEOUT_SECONDS", "20")))
    app_key = os.getenv("TAOBAO_APP_KEY", DEFAULT_APP_KEY).strip() or DEFAULT_APP_KEY
    app_id = os.getenv("TAOBAO_APP_ID", DEFAULT_APP_ID).strip() or DEFAULT_APP_ID
    user_agent = os.getenv("TAOBAO_USER_AGENT", DEFAULT_USER_AGENT).strip() or DEFAULT_USER_AGENT
    raw_text_max_chars = max(0, int(os.getenv("TAOBAO_RAW_TEXT_MAX_CHARS", "4000")))

    my_cna = _extract_cookie_value(cookie, "cna")
    snapshot_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    session = _build_session(cookie=cookie, user_agent=user_agent)
    browser_refreshed_once = False

    written = 0
    for keyword in keywords:
        LOGGER.info("taobao start keyword=%s pages=%s", keyword, max_pages)

        for page in range(1, max_pages + 1):
            if written >= max_items:
                LOGGER.info("taobao reached max_items=%s", max_items)
                return written

            for attempt in range(2):
                try:
                    products, raw_text = _fetch_page(
                        session,
                        token=token,
                        app_key=app_key,
                        app_id=app_id,
                        keyword=keyword,
                        page=page,
                        page_size=page_size,
                        timeout_seconds=timeout_seconds,
                        user_agent=user_agent,
                        my_cna=my_cna,
                    )
                    break
                except TokenExpiredError as exc:
                    refreshed = _extract_token_from_cookie_value(
                        _cookie_dict_from_jar(session).get("_m_h5_tk", "")
                    )
                    if refreshed and refreshed != token and attempt == 0:
                        token = refreshed
                        LOGGER.info("taobao token refreshed, retry current page")
                        continue

                    if not browser_refreshed_once:
                        new_cookie = _try_refresh_cookie("token_expired")
                        browser_refreshed_once = True
                        if new_cookie:
                            cookie = new_cookie
                            token = _extract_token_from_cookie(cookie) or token
                            my_cna = _extract_cookie_value(cookie, "cna")
                            session = _build_session(cookie=cookie, user_agent=user_agent)
                            LOGGER.info("taobao cookie refreshed via browser, retry current page")
                            continue

                    LOGGER.warning(
                        "taobao page failed: keyword=%s page=%s err=%s",
                        keyword,
                        page,
                        exc,
                    )
                    products, raw_text = [], ""
                    break
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("taobao page failed: keyword=%s page=%s err=%s", keyword, page, exc)
                    products, raw_text = [], ""
                    break

            if not products:
                LOGGER.info("taobao empty page: keyword=%s page=%s", keyword, page)
                break

            LOGGER.info("taobao page parsed: keyword=%s page=%s items=%s", keyword, page, len(products))
            raw_text_trimmed = raw_text[:raw_text_max_chars] if raw_text_max_chars > 0 else None

            for idx, product in enumerate(products, start=1):
                if written >= max_items:
                    LOGGER.info("taobao reached max_items=%s", max_items)
                    return written

                enriched: dict[str, Any] = {}
                if enrich_item_fn is not None:
                    try:
                        enriched = enrich_item_fn(
                            {
                                "platform": "taobao",
                                "keyword": keyword,
                                "title": product["title"],
                                "price": product["price"],
                                "original_price": product["original_price"],
                                "sales_or_commit": product["sales_or_commit"],
                                "shop": product["shop"],
                                "province": product["province"],
                                "city": product["city"],
                                "detail_url": product["detail_url"],
                                "category": product["category"],
                            }
                        ) or {}
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.warning(
                            "taobao enrich failed: keyword=%s page=%s idx=%s err=%s",
                            keyword,
                            page,
                            idx,
                            exc,
                        )

                raw_payload = {
                    "keyword": keyword,
                    "page": page,
                    "page_index": idx,
                    "item_id": product["item_id"],
                    "price": product["price"],
                    "raw_item": product["raw_item"],
                    "extract": enriched,
                }
                raw_id = insert_raw_event(
                    conn,
                    source_name=source_name,
                    url=product["detail_url"],
                    title=product["title"],
                    raw_text=raw_text_trimmed,
                    raw_json=json.dumps(raw_payload, ensure_ascii=False),
                )

                upsert_product_snapshot(
                    conn,
                    {
                        **enriched,
                        "platform": "taobao",
                        "keyword": keyword,
                        "title": product["title"],
                        "price": product["price"],
                        "original_price": product["original_price"],
                        "sales_or_commit": product["sales_or_commit"],
                        "shop": product["shop"],
                        "province": product["province"],
                        "city": product["city"],
                        "detail_url": product["detail_url"],
                        "category": product["category"],
                        "snapshot_time": snapshot_time,
                        "raw_id": raw_id,
                    },
                )
                written += 1

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    return written


if __name__ == "__main__":
    connection = get_conn()
    try:
        total = run(connection)
        print(f"[OK] taobao items={total}")
    finally:
        connection.close()
