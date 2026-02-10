import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

try:
    from common.db import insert_raw_event, upsert_intel_item
    from common.logger import get_logger
except ModuleNotFoundError:
    # Support direct execution: python fish_intel_mvp/jobs/crawl_moa_fishery.py
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from common.db import insert_raw_event, upsert_intel_item
    from common.logger import get_logger

LOGGER = get_logger(__name__)

BASE_URL = "https://yyj.moa.gov.cn"
LIST_FIRST = f"{BASE_URL}/tzgg/index.htm"
SOURCE_NAME = "moa_fishery_tzgg"
SOURCE_TYPE = "MOA_FISHERY_TZGG"
DEFAULT_ORG = "农业农村部渔业渔政管理局"
DEFAULT_REGION = "中国-全国"


def _clean_text(text: str) -> str:
    return (text or "").replace("\u3000", " ").strip()


def _build_session() -> requests.Session:
    session = requests.Session()
    # Ignore broken proxy env vars in local environment.
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
    )
    return session


def _fetch_text(session: requests.Session, url: str, timeout: int = 20, retries: int = 2) -> str:
    last_err = None
    for _ in range(retries + 1):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(0.8)
    raise RuntimeError(f"fetch failed: url={url}, err={last_err}")


def _list_url(page_index: int) -> str:
    if page_index <= 0:
        return LIST_FIRST
    return f"{BASE_URL}/tzgg/index_{page_index}.htm"


def _parse_list(html: str, list_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    ul = soup.select_one("div.sj_e_tonzhi_list ul#div") or soup.select_one("ul#div")
    if not ul:
        return []

    records: list[dict] = []
    for li in ul.find_all("li"):
        a = li.find("a")
        if not a:
            continue

        title = ""
        title_span = a.find("span", class_="sj_gztzle")
        if title_span:
            title = _clean_text(title_span.get_text(" ", strip=True))
        if not title:
            title = _clean_text(a.get_text(" ", strip=True))
        if not title:
            continue

        pub_time = ""
        date_span = a.find("span", class_="sj_gztzri")
        if date_span:
            pub_time = _clean_text(date_span.get_text(" ", strip=True))
        if not pub_time:
            li_text = _clean_text(li.get_text(" ", strip=True))
            match = re.search(r"\d{4}-\d{2}-\d{2}", li_text)
            pub_time = match.group(0) if match else ""

        href = _clean_text(a.get("href") or "")
        if not href:
            continue

        records.append(
            {
                "title": title,
                "pub_time": pub_time,
                "url": urljoin(list_url, href),
            }
        )
    return records


def _extract_meta(full_text: str) -> dict[str, str]:
    text = _clean_text(full_text)
    meta = {"pub_time": "", "author": "", "source": ""}

    match = re.search(r"日期[:：]\s*(\d{4}-\d{2}-\d{2})", text)
    if match:
        meta["pub_time"] = match.group(1)

    match = re.search(r"作者[:：]\s*([^\n\r]+)", text)
    if match:
        author = _clean_text(match.group(1))
        author = re.split(r"(来源[:：]|【字号|打印本页)", author)[0].strip()
        meta["author"] = author

    match = re.search(r"来源[:：]\s*([^\n\r]+)", text)
    if match:
        source = _clean_text(match.group(1))
        source = re.split(r"(【字号|打印本页)", source)[0].strip()
        meta["source"] = source

    return meta


def _parse_detail(html: str, fallback_title: str, fallback_pub_time: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    title = _clean_text(h1.get_text(" ", strip=True)) if h1 else _clean_text(fallback_title)

    content_node = (
        soup.select_one("div.TRS_Editor")
        or soup.select_one("#zoom")
        or soup.select_one("div.con-content")
        or soup.select_one("div.content")
    )
    if content_node:
        paragraphs = [_clean_text(p.get_text(" ", strip=True)) for p in content_node.find_all("p")]
        paragraphs = [p for p in paragraphs if p]
        content = (
            "\n".join(paragraphs)
            if paragraphs
            else _clean_text(content_node.get_text("\n", strip=True))
        )
    else:
        content = _clean_text(soup.get_text("\n", strip=True))

    meta = _extract_meta(soup.get_text("\n", strip=True))
    return {
        "title": title or _clean_text(fallback_title),
        "pub_time": meta["pub_time"] or _clean_text(fallback_pub_time),
        "author": meta["author"],
        "source": meta["source"] or DEFAULT_ORG,
        "content": content,
    }


def run(conn) -> int:
    max_pages = max(1, int(os.getenv("MOA_MAX_PAGES", "1")))
    max_items = max(1, int(os.getenv("MOA_MAX_ITEMS", "200")))
    sleep_seconds = max(0.0, float(os.getenv("MOA_SLEEP_SECONDS", "0.3")))
    raw_html_max_chars = max(10000, int(os.getenv("MOA_RAW_HTML_MAX_CHARS", "120000")))
    content_max_chars = max(2000, int(os.getenv("MOA_CONTENT_MAX_CHARS", "200000")))

    session = _build_session()
    written = 0

    for page_idx in range(max_pages):
        list_url = _list_url(page_idx)
        LOGGER.info("moa fetch list: page=%s url=%s", page_idx, list_url)
        try:
            list_html = _fetch_text(session, list_url)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("moa list fetch failed: page=%s err=%s", page_idx, exc)
            if page_idx == 0:
                break
            continue

        records = _parse_list(list_html, list_url)
        LOGGER.info("moa list parsed: page=%s items=%s", page_idx, len(records))
        if not records and page_idx > 0:
            break

        for idx, base in enumerate(records, start=1):
            detail_url = base["url"]
            try:
                is_pdf = detail_url.lower().endswith(".pdf")
                if is_pdf:
                    detail_html = ""
                    detail = {
                        "title": base["title"],
                        "pub_time": base["pub_time"],
                        "author": "",
                        "source": DEFAULT_ORG,
                        "content": "",
                    }
                else:
                    detail_html = _fetch_text(session, detail_url)
                    detail = _parse_detail(
                        detail_html,
                        fallback_title=base["title"],
                        fallback_pub_time=base["pub_time"],
                    )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("moa detail failed: url=%s err=%s", detail_url, exc)
                continue

            content_for_db = detail["content"][:content_max_chars]
            raw_id = insert_raw_event(
                conn,
                source_name=SOURCE_NAME,
                url=detail_url,
                title=detail["title"],
                pub_time=detail["pub_time"],
                raw_text=detail_html[:raw_html_max_chars],
                raw_json=json.dumps(
                    {
                        "list_title": base["title"],
                        "list_pub_time": base["pub_time"],
                        "author": detail["author"],
                        "source": detail["source"],
                        "is_pdf": detail_url.lower().endswith(".pdf"),
                        "raw_html_len": len(detail_html),
                        "raw_html_truncated": len(detail_html) > raw_html_max_chars,
                        "content_len": len(detail["content"]),
                        "content_truncated": len(detail["content"]) > content_max_chars,
                    },
                    ensure_ascii=False,
                ),
            )

            upsert_intel_item(
                conn,
                {
                    "source_type": SOURCE_TYPE,
                    "title": detail["title"],
                    "pub_time": detail["pub_time"],
                    "org": detail["source"] or DEFAULT_ORG,
                    "region": DEFAULT_REGION,
                    "content": content_for_db,
                    "source_url": detail_url,
                    "tags_json": json.dumps(["通知公告"], ensure_ascii=False),
                    "extra_json": json.dumps(
                        {"author": detail["author"], "channel": "通知公告"},
                        ensure_ascii=False,
                    ),
                    "raw_id": raw_id,
                },
            )

            written += 1
            if idx % 5 == 0 or idx == len(records):
                LOGGER.info(
                    "moa db progress: page=%s %s/%s written_total=%s",
                    page_idx,
                    idx,
                    len(records),
                    written,
                )

            if written >= max_items:
                LOGGER.info("moa reached max_items=%s, stop early", max_items)
                return written

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    return written


if __name__ == "__main__":
    from common.db import get_conn

    connection = get_conn()
    try:
        count = run(connection)
        print(f"[OK] moa items={count}")
    finally:
        connection.close()
