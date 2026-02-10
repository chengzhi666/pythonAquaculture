import json
import os
import re
import sys
import time
from pathlib import Path
from typing import cast
from urllib.parse import urljoin

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC  # noqa: N812
from selenium.webdriver.support.ui import WebDriverWait

try:
    from common.db import get_conn, insert_raw_event, upsert_paper
    from common.logger import get_logger
except ModuleNotFoundError:
    # Support direct execution: python fish_intel_mvp/jobs/crawl_cnki.py
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from common.db import get_conn, insert_raw_event, upsert_paper
    from common.logger import get_logger

LOGGER = get_logger(__name__)

CNKI_ADV_SEARCH_URL = "https://kns.cnki.net/kns8/AdvSearch"


def _clean_text(text: str) -> str:
    return (text or "").replace("\u3000", " ").strip()


def _split_keywords(text: str) -> list[str]:
    text = _clean_text(text)
    if not text:
        return []
    # Remove common prefixes: "Keywords:", "keyword:", and Chinese variants via unicode escapes.
    text = re.sub(
        r"^(?:keywords?|key\s*words?|\u5173\u952e\u8bcd|\u5173\u952e\u5b57)[:：\s]*",
        "",
        text,
        flags=re.I,
    )
    text = text.replace("\uFF1B", ";").replace("\uFF0C", ",").replace("\u3001", ",")
    parts = re.split(r"[;,\s]+", text)
    return [p.strip() for p in parts if p.strip()]


def _build_driver():
    options = webdriver.EdgeOptions()
    if os.getenv("CNKI_HEADLESS", "0").strip() == "1":
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1600,1000")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Optional driver path, keep empty to let Selenium Manager resolve automatically.
    driver_path = (
        os.getenv("EDGE_DRIVER_PATH", "").strip() or os.getenv("CHROME_DRIVER_PATH", "").strip()
    )
    if driver_path:
        service = Service(driver_path)
        driver = webdriver.Edge(service=service, options=options)
    else:
        driver = webdriver.Edge(options=options)

    driver.set_page_load_timeout(45)
    return driver


def _open_search_result(driver, theme: str) -> None:
    wait = WebDriverWait(driver, 30)
    driver.get(CNKI_ADV_SEARCH_URL)

    topic_input = wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//div[@class='gradeSearch']//dl[@id='gradetxt']/dd[1]//input[@type='text']",
            )
        )
    )
    topic_input.clear()
    topic_input.send_keys(theme)

    search_btn = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, "//div[@class='search-buttons']/input[@class='btn-search']")
        )
    )
    search_btn.click()

    wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table.result-table-list tbody tr"))
    )


def _row_text(row, selector: str) -> str:
    try:
        return _clean_text(row.find_element(By.CSS_SELECTOR, selector).text)
    except Exception:
        return ""


def _extract_list_rows(driver: WebDriver) -> list[WebElement]:
    return cast(
        list[WebElement], driver.find_elements(By.CSS_SELECTOR, "table.result-table-list tbody tr")
    )


def _safe_switch_detail_window(driver, original_handle: str) -> None:
    time.sleep(1.2)
    handles = driver.window_handles
    if len(handles) > 1:
        driver.switch_to.window(handles[-1])
    else:
        driver.switch_to.window(original_handle)


def _extract_detail(driver, list_meta: dict) -> dict:
    wait = WebDriverWait(driver, 20)
    title = list_meta["list_title"]
    try:
        title = (
            _clean_text(
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.wxTitle h1, h1"))
                ).text
            )
            or title
        )
    except Exception:
        pass

    authors = list_meta.get("list_authors", "")
    for css in ["div.wxTitle h3:nth-of-type(1)", "#authorpart"]:
        try:
            value = _clean_text(driver.find_element(By.CSS_SELECTOR, css).text)
            if value:
                authors = value
                break
        except Exception:
            continue

    institute = ""
    for css in ["div.wxTitle h3:nth-of-type(2)", "#organpart"]:
        try:
            institute = _clean_text(driver.find_element(By.CSS_SELECTOR, css).text)
            if institute:
                break
        except Exception:
            continue

    abstract = ""
    for css in ["span#ChDivSummary", "#abstracts p", "div.abstract-text"]:
        try:
            abstract = _clean_text(driver.find_element(By.CSS_SELECTOR, css).text)
            if abstract:
                break
        except Exception:
            continue

    keywords = []
    keyword_text = ""
    for css in ["#kwpart .kw_main", ".keywords", "p.keywords"]:
        try:
            keyword_text = _clean_text(driver.find_element(By.CSS_SELECTOR, css).text)
            if keyword_text:
                keywords = _split_keywords(keyword_text)
                break
        except Exception:
            continue

    detail_url = _clean_text(driver.current_url) or list_meta.get("list_url", "")
    if detail_url.startswith("//"):
        detail_url = "https:" + detail_url
    if detail_url and not detail_url.startswith("http"):
        detail_url = urljoin("https://kns.cnki.net", detail_url)

    try:
        raw_html = driver.page_source or ""
    except Exception:
        raw_html = ""

    return {
        "title": title,
        "authors": authors,
        "institute": institute,
        "source": list_meta.get("source", ""),
        "pub_date": list_meta.get("pub_date", ""),
        "database_name": list_meta.get("database_name", ""),
        "abstract": abstract,
        "keywords": keywords,
        "url": detail_url,
        "raw_html": raw_html,
        "raw_keyword_text": keyword_text,
    }


def _go_back_to_list(driver, original_handle: str) -> None:
    try:
        handles = driver.window_handles
        if len(handles) > 1:
            driver.close()
            driver.switch_to.window(original_handle)
        else:
            driver.back()
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.result-table-list tbody tr"))
        )
    except Exception:
        pass


def run(conn) -> int:
    theme = os.getenv("CNKI_THEME", "aquaculture").strip() or "aquaculture"
    papers_need = max(1, int(os.getenv("CNKI_PAPERS", "10")))
    max_pages = max(1, int(os.getenv("CNKI_MAX_PAGES", "5")))
    login_wait_seconds = max(0, int(os.getenv("CNKI_LOGIN_WAIT_SECONDS", "20")))
    raw_html_max_chars = max(5000, int(os.getenv("CNKI_RAW_HTML_MAX_CHARS", "150000")))

    driver = _build_driver()
    inserted = 0
    page_no = 1

    try:
        _open_search_result(driver, theme)
        if "passport.cnki.net" in (driver.current_url or ""):
            LOGGER.info(
                "cnki login page detected, please complete login in %ss",
                login_wait_seconds,
            )
            end_at = time.time() + login_wait_seconds
            while time.time() < end_at:
                if "passport.cnki.net" not in (driver.current_url or ""):
                    break
                time.sleep(1)

        while inserted < papers_need and page_no <= max_pages:
            rows = _extract_list_rows(driver)
            LOGGER.info("cnki list parsed: page=%s rows=%s", page_no, len(rows))
            if not rows:
                break

            for row_index in range(len(rows)):
                if inserted >= papers_need:
                    break

                rows = _extract_list_rows(driver)
                if row_index >= len(rows):
                    break
                row = rows[row_index]

                try:
                    title_link = row.find_element(By.CSS_SELECTOR, "a.fz14")
                except Exception:
                    continue

                list_title = _clean_text(title_link.text)
                list_href = _clean_text(title_link.get_attribute("href") or "")
                if list_href.startswith("//"):
                    list_href = "https:" + list_href
                if list_href and not list_href.startswith("http"):
                    list_href = urljoin("https://kns.cnki.net", list_href)

                list_meta = {
                    "list_title": list_title,
                    "list_url": list_href,
                    "list_authors": _row_text(row, "td.author"),
                    "source": _row_text(row, "td.source"),
                    "pub_date": _row_text(row, "td.date"),
                    "database_name": _row_text(row, "td.data"),
                }

                original_handle = driver.current_window_handle
                try:
                    driver.execute_script("arguments[0].click();", title_link)
                    _safe_switch_detail_window(driver, original_handle)
                    detail = _extract_detail(driver, list_meta)
                except TimeoutException:
                    LOGGER.warning("cnki detail timeout: page=%s row=%s", page_no, row_index + 1)
                    _go_back_to_list(driver, original_handle)
                    continue
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning(
                        "cnki detail failed: page=%s row=%s err=%s",
                        page_no,
                        row_index + 1,
                        exc,
                    )
                    _go_back_to_list(driver, original_handle)
                    continue

                detail_url = detail["url"] or list_meta["list_url"]
                if not detail_url:
                    # Keep dedup key stable even when detail URL is unavailable.
                    detail_url = f"cnki://{theme}/{page_no}/{row_index + 1}"

                raw_json = {
                    "list_title": list_meta["list_title"],
                    "list_authors": list_meta["list_authors"],
                    "source": list_meta["source"],
                    "pub_date": list_meta["pub_date"],
                    "database_name": list_meta["database_name"],
                    "keyword_text": detail["raw_keyword_text"],
                    "raw_html_len": len(detail["raw_html"]),
                    "raw_html_truncated": len(detail["raw_html"]) > raw_html_max_chars,
                }
                raw_id = insert_raw_event(
                    conn,
                    source_name="cnki",
                    url=detail_url,
                    title=detail["title"] or list_meta["list_title"],
                    pub_time=detail["pub_date"] or list_meta["pub_date"],
                    raw_text=detail["raw_html"][:raw_html_max_chars],
                    raw_json=json.dumps(raw_json, ensure_ascii=False),
                )

                upsert_paper(
                    conn,
                    {
                        "theme": theme,
                        "title": detail["title"] or list_meta["list_title"],
                        "authors": detail["authors"] or list_meta["list_authors"],
                        "institute": detail["institute"],
                        "source": detail["source"] or list_meta["source"],
                        "pub_date": detail["pub_date"] or list_meta["pub_date"],
                        "database_name": detail["database_name"] or list_meta["database_name"],
                        "abstract": detail["abstract"],
                        "keywords_json": json.dumps(detail["keywords"], ensure_ascii=False),
                        "url": detail_url,
                        "raw_id": raw_id,
                    },
                )

                inserted += 1
                LOGGER.info(
                    "cnki db progress: page=%s row=%s inserted=%s/%s title=%s",
                    page_no,
                    row_index + 1,
                    inserted,
                    papers_need,
                    (detail["title"] or list_meta["list_title"])[:40],
                )

                _go_back_to_list(driver, original_handle)
                time.sleep(0.8)

            if inserted >= papers_need:
                break

            try:
                next_btn = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.ID, "PageNext"))
                )
                classes = _clean_text(next_btn.get_attribute("class") or "").lower()
                if "disabled" in classes:
                    break
                driver.execute_script("arguments[0].click();", next_btn)
                page_no += 1
                time.sleep(1.5)
            except Exception:
                break
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return inserted


if __name__ == "__main__":
    connection = get_conn()
    try:
        count = run(connection)
        print(f"[OK] cnki items={count}")
    finally:
        connection.close()
