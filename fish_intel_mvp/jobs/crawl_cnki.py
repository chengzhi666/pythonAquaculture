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
TOPIC_INPUT_XPATH = (
    "//div[@class='gradeSearch']//dl[@id='gradetxt']/dd[1]//input[@type='text' and @maxlength='120']"
)
SEARCH_BUTTON_XPATH = "//div[@class='search-buttons']/input[@class='btn-search']"


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
    text = text.replace("\uff1b", ";").replace("\uff0c", ",").replace("\u3001", ",")
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


def _resolve_chrome_path() -> str:
    env_path = os.getenv("CNKI_CHROME_PATH", "").strip()
    if env_path:
        return env_path
    candidates = [
        str((Path(__file__).resolve().parents[2] / ".chrome-for-testing" / "chrome-win64" / "chrome.exe")),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def _is_true(value: str) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _build_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError("playwright is not installed. run: pip install playwright") from exc

    headless = _is_true(os.getenv("CNKI_HEADLESS", "0"))
    chrome_path = _resolve_chrome_path()
    launch_kwargs = {
        "headless": headless,
        "args": [
            "--disable-gpu",
            "--window-size=1600,1000",
        ],
    }
    if chrome_path and os.path.exists(chrome_path):
        launch_kwargs["executable_path"] = chrome_path

    LOGGER.info(
        "cnki playwright launch opts: headless=%s chrome_path=%s",
        headless,
        chrome_path or "<default>",
    )

    pw = sync_playwright().start()
    browser = pw.chromium.launch(**launch_kwargs)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    )
    if _is_true(os.getenv("CNKI_BLOCK_ASSETS", "1")):
        context.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in {"image", "media", "font"}
            else route.continue_(),
        )
    page = context.new_page()
    page.set_default_timeout(30000)
    page.set_default_navigation_timeout(45000)
    return pw, browser, context, page


def _safe_locator_text(locator, timeout_ms: int = 1200) -> str:
    try:
        return _clean_text(locator.inner_text(timeout=timeout_ms))
    except Exception:
        return ""


def _safe_locator_attr(locator, name: str, timeout_ms: int = 1200) -> str:
    try:
        return _clean_text(locator.get_attribute(name, timeout=timeout_ms) or "")
    except Exception:
        return ""


def _open_search_result(driver, theme: str) -> None:
    wait = WebDriverWait(driver, 30)
    driver.get(CNKI_ADV_SEARCH_URL)
    try:
        driver.maximize_window()
    except Exception:
        pass

    topic_input = wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                TOPIC_INPUT_XPATH,
            )
        )
    )
    topic_input.clear()
    topic_input.send_keys(theme)

    search_btn = wait.until(
        EC.element_to_be_clickable(
            (By.XPATH, SEARCH_BUTTON_XPATH)
        )
    )
    search_btn.click()

    wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table.result-table-list tbody tr"))
    )


def _open_search_result_playwright(page, theme: str) -> None:
    page.goto(CNKI_ADV_SEARCH_URL, wait_until="domcontentloaded", timeout=45000)
    _submit_search_playwright(page, theme)


def _submit_search_playwright(page, theme: str) -> None:
    topic_input = page.locator(f"xpath={TOPIC_INPUT_XPATH}").first
    topic_input.wait_for(state="visible", timeout=30000)
    topic_input.fill(theme)

    search_btn = page.locator(f"xpath={SEARCH_BUTTON_XPATH}").first
    search_btn.click()


def _wait_list_or_login_playwright(page, timeout_seconds: int = 30) -> str:
    end_at = time.time() + max(1, timeout_seconds)
    while time.time() < end_at:
        url = (page.url or "").lower()
        if "passport.cnki.net" in url:
            return "login"
        rows = page.locator("table.result-table-list tbody tr")
        table = page.locator("table.result-table-list")
        try:
            if rows.count() > 0:
                return "list"
            if table.count() > 0:
                # Result table rendered but currently empty.
                return "list"
        except Exception:
            pass
        page.wait_for_timeout(500)
    return "timeout"


def _ensure_list_ready_playwright(page, theme: str, login_wait_seconds: int) -> str:
    _open_search_result_playwright(page, theme)
    state = _wait_list_or_login_playwright(page, timeout_seconds=40)
    if state == "list":
        return state

    if state == "login" or "passport.cnki.net" in (page.url or ""):
        LOGGER.info(
            "cnki login page detected, please complete login in %ss",
            login_wait_seconds,
        )
        end_at = time.time() + login_wait_seconds
        while time.time() < end_at:
            if "passport.cnki.net" not in (page.url or ""):
                break
            page.wait_for_timeout(1000)

    # Re-submit search after login/redirect until list is ready.
    for attempt in range(1, 4):
        state = _wait_list_or_login_playwright(page, timeout_seconds=8)
        if state == "list":
            return state
        LOGGER.info(
            "cnki list not ready, resubmit search: attempt=%s state=%s url=%s",
            attempt,
            state,
            page.url,
        )
        try:
            page.goto(CNKI_ADV_SEARCH_URL, wait_until="domcontentloaded", timeout=45000)
        except Exception:
            pass
        try:
            _submit_search_playwright(page, theme)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("cnki submit search failed on attempt=%s err=%s", attempt, exc)
            continue
        state = _wait_list_or_login_playwright(page, timeout_seconds=40)
        if state == "list":
            return state

    return state


def _row_text(row, selector: str) -> str:
    try:
        return _clean_text(row.find_element(By.CSS_SELECTOR, selector).text)
    except Exception:
        return ""


def _extract_list_rows(driver: WebDriver) -> list[WebElement]:
    return cast(
        list[WebElement], driver.find_elements(By.CSS_SELECTOR, "table.result-table-list tbody tr")
    )


def _extract_detail_playwright(page, list_meta: dict) -> dict:
    url_now = (page.url or "").lower()
    if "captcha" in url_now or "verify" in url_now:
        return {
            "title": list_meta["list_title"],
            "authors": list_meta.get("list_authors", ""),
            "institute": "",
            "source": list_meta.get("source", ""),
            "pub_date": list_meta.get("pub_date", ""),
            "database_name": list_meta.get("database_name", ""),
            "abstract": "",
            "keywords": [],
            "url": page.url or list_meta.get("list_url", ""),
            "raw_html": "",
            "raw_keyword_text": "",
        }

    title = _safe_locator_text(page.locator("div.wxTitle h1, h1").first) or list_meta["list_title"]

    authors = list_meta.get("list_authors", "")
    for css in ["div.wxTitle h3:nth-of-type(1)", "#authorpart"]:
        value = _safe_locator_text(page.locator(css).first)
        if value:
            authors = value
            break

    institute = ""
    for css in ["div.wxTitle h3:nth-of-type(2)", "#organpart"]:
        institute = _safe_locator_text(page.locator(css).first)
        if institute:
            break

    abstract = ""
    for css in ["span#ChDivSummary", "#abstracts p", "div.abstract-text"]:
        abstract = _safe_locator_text(page.locator(css).first)
        if abstract:
            break

    keywords = []
    keyword_text = ""
    for css in ["#kwpart .kw_main", ".keywords", "p.keywords"]:
        keyword_text = _safe_locator_text(page.locator(css).first)
        if keyword_text:
            keywords = _split_keywords(keyword_text)
            break

    detail_url = _clean_text(page.url) or list_meta.get("list_url", "")
    if detail_url.startswith("//"):
        detail_url = "https:" + detail_url
    if detail_url and not detail_url.startswith("http"):
        detail_url = urljoin("https://kns.cnki.net", detail_url)

    try:
        raw_html = page.content() or ""
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


def _fallback_detail_from_list(list_meta: dict, detail_url: str) -> dict:
    return {
        "title": list_meta["list_title"],
        "authors": list_meta.get("list_authors", ""),
        "institute": "",
        "source": list_meta.get("source", ""),
        "pub_date": list_meta.get("pub_date", ""),
        "database_name": list_meta.get("database_name", ""),
        "abstract": "",
        "keywords": [],
        "url": detail_url,
        "raw_html": "",
        "raw_keyword_text": "",
    }


def _wait_detail_ready_playwright(page, timeout_seconds: float = 12.0) -> bool:
    end_at = time.time() + max(1.0, float(timeout_seconds))
    while time.time() < end_at:
        url = (page.url or "").lower()
        if "captcha" in url or "verify" in url:
            return False

        title = _safe_locator_text(page.locator("div.wxTitle h1, h1").first, timeout_ms=500)
        abstract = _safe_locator_text(
            page.locator("span#ChDivSummary, #abstracts p, div.abstract-text").first,
            timeout_ms=500,
        )
        if title or abstract:
            return True
        page.wait_for_timeout(350)
    return False


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


def _run_selenium(
    conn,
    *,
    theme: str,
    papers_need: int,
    max_pages: int,
    login_wait_seconds: int,
    raw_html_max_chars: int,
) -> int:
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


def _run_playwright(
    conn,
    *,
    theme: str,
    papers_need: int,
    max_pages: int,
    login_wait_seconds: int,
    raw_html_max_chars: int,
) -> int:
    pw, browser, context, list_page = _build_playwright()
    click_flow = _is_true(os.getenv("CNKI_PLAYWRIGHT_CLICK_FLOW", "1"))
    detail_page = None
    if not click_flow:
        detail_page = context.new_page()
    detail_timeout_ms = max(5000, int(float(os.getenv("CNKI_DETAIL_TIMEOUT_SECONDS", "30")) * 1000))
    detail_ready_wait_seconds = max(3.0, float(os.getenv("CNKI_DETAIL_READY_WAIT_SECONDS", "12")))
    detail_retries = max(1, int(os.getenv("CNKI_DETAIL_RETRIES", "2")))
    detail_wait_until = os.getenv("CNKI_DETAIL_WAIT_UNTIL", "load").strip().lower()
    if detail_wait_until not in {"domcontentloaded", "load", "networkidle"}:
        detail_wait_until = "load"
    row_pause_seconds = max(0.0, float(os.getenv("CNKI_ROW_PAUSE_SECONDS", "0.25")))
    allow_list_fallback = _is_true(os.getenv("CNKI_ALLOW_LIST_FALLBACK", "0"))
    LOGGER.info(
        "cnki playwright mode: click_flow=%s detail_wait_until=%s detail_retries=%s",
        click_flow,
        detail_wait_until,
        detail_retries,
    )
    inserted = 0
    page_no = 1

    try:
        state = _ensure_list_ready_playwright(list_page, theme, login_wait_seconds)
        if state != "list":
            LOGGER.warning(
                "cnki list not ready after search/login: state=%s url=%s",
                state,
                list_page.url,
            )
            try:
                debug_path = Path("fish_intel_mvp/cnki_debug.html")
                debug_path.write_text(list_page.content(), encoding="utf-8")
                LOGGER.info("cnki debug html saved: %s", debug_path.resolve())
            except Exception:
                pass
            return inserted

        while inserted < papers_need and page_no <= max_pages:
            rows_locator = list_page.locator("table.result-table-list tbody tr")
            row_count = rows_locator.count()
            LOGGER.info("cnki list parsed: page=%s rows=%s", page_no, row_count)
            if row_count == 0:
                break

            for row_index in range(row_count):
                if inserted >= papers_need:
                    break

                rows_locator = list_page.locator("table.result-table-list tbody tr")
                if row_index >= rows_locator.count():
                    break
                row = rows_locator.nth(row_index)
                title_link = row.locator("a.fz14").first
                if title_link.count() == 0:
                    continue

                list_title = _safe_locator_text(title_link)
                list_href = _safe_locator_attr(title_link, "href")
                if list_href.startswith("//"):
                    list_href = "https:" + list_href
                if list_href and not list_href.startswith("http"):
                    list_href = urljoin("https://kns.cnki.net", list_href)
                if not list_href:
                    continue

                list_meta = {
                    "list_title": list_title,
                    "list_url": list_href,
                    "list_authors": _safe_locator_text(row.locator("td.author").first),
                    "source": _safe_locator_text(row.locator("td.source").first),
                    "pub_date": _safe_locator_text(row.locator("td.date").first),
                    "database_name": _safe_locator_text(row.locator("td.data").first),
                }

                detail = None
                last_exc = None
                if click_flow:
                    for detail_try in range(1, detail_retries + 1):
                        work_page = None
                        opened_new_tab = False
                        try:
                            try:
                                with list_page.expect_popup(timeout=3500) as popup_info:
                                    title_link.click(timeout=5000)
                                work_page = popup_info.value
                                opened_new_tab = True
                            except Exception:
                                title_link.click(timeout=5000)
                                work_page = list_page

                            try:
                                work_page.wait_for_load_state("domcontentloaded", timeout=detail_timeout_ms)
                            except Exception:
                                pass

                            if not _wait_detail_ready_playwright(
                                work_page, timeout_seconds=detail_ready_wait_seconds
                            ):
                                raise TimeoutError(
                                    f"detail not ready in {detail_ready_wait_seconds}s, url={work_page.url}"
                                )
                            detail = _extract_detail_playwright(work_page, list_meta)
                            break
                        except Exception as exc:  # noqa: BLE001
                            last_exc = exc
                        finally:
                            if work_page is not None and opened_new_tab:
                                try:
                                    work_page.close()
                                except Exception:
                                    pass
                            elif work_page is list_page:
                                try:
                                    list_page.go_back(wait_until="domcontentloaded", timeout=detail_timeout_ms)
                                except Exception:
                                    pass
                                try:
                                    list_page.wait_for_selector(
                                        "table.result-table-list tbody tr",
                                        timeout=12000,
                                    )
                                except Exception:
                                    pass

                        if detail_try < detail_retries:
                            list_page.wait_for_timeout(500)
                else:
                    for detail_try in range(1, detail_retries + 1):
                        try:
                            detail_page.goto(
                                list_href,
                                wait_until=detail_wait_until,
                                timeout=detail_timeout_ms,
                            )
                            if not _wait_detail_ready_playwright(
                                detail_page, timeout_seconds=detail_ready_wait_seconds
                            ):
                                raise TimeoutError(
                                    f"detail not ready in {detail_ready_wait_seconds}s, url={detail_page.url}"
                                )
                            detail = _extract_detail_playwright(detail_page, list_meta)
                            break
                        except Exception as exc:  # noqa: BLE001
                            last_exc = exc
                            if detail_try < detail_retries:
                                detail_page.wait_for_timeout(500)

                if detail is None:
                    LOGGER.warning(
                        "cnki detail failed: page=%s row=%s retries=%s err=%s",
                        page_no,
                        row_index + 1,
                        detail_retries,
                        last_exc,
                    )
                    if not allow_list_fallback:
                        continue
                    detail = _fallback_detail_from_list(list_meta, list_href)

                detail_url = detail["url"] or list_meta["list_url"]
                if not detail_url:
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
                time.sleep(row_pause_seconds)

            if inserted >= papers_need:
                break

            next_btn = list_page.locator("#PageNext").first
            if next_btn.count() == 0:
                break
            classes = _safe_locator_attr(next_btn, "class").lower()
            if "disabled" in classes:
                break
            try:
                next_btn.click()
                page_no += 1
                list_page.wait_for_timeout(1500)
                list_page.wait_for_selector("table.result-table-list tbody tr", timeout=15000)
            except Exception:
                break
    finally:
        for obj, method in (
            (detail_page, "close"),
            (list_page, "close"),
            (context, "close"),
            (browser, "close"),
            (pw, "stop"),
        ):
            try:
                getattr(obj, method)()
            except Exception:
                pass

    return inserted


def run(conn) -> int:
    theme = os.getenv("CNKI_THEME", "aquaculture").strip() or "aquaculture"
    papers_need = max(1, int(os.getenv("CNKI_PAPERS", "10")))
    max_pages = max(1, int(os.getenv("CNKI_MAX_PAGES", "5")))
    login_wait_seconds = max(0, int(os.getenv("CNKI_LOGIN_WAIT_SECONDS", "20")))
    raw_html_max_chars = max(5000, int(os.getenv("CNKI_RAW_HTML_MAX_CHARS", "150000")))
    backend = os.getenv("CNKI_BROWSER_BACKEND", "playwright").strip().lower()

    if backend == "playwright":
        return _run_playwright(
            conn,
            theme=theme,
            papers_need=papers_need,
            max_pages=max_pages,
            login_wait_seconds=login_wait_seconds,
            raw_html_max_chars=raw_html_max_chars,
        )
    if backend == "selenium":
        return _run_selenium(
            conn,
            theme=theme,
            papers_need=papers_need,
            max_pages=max_pages,
            login_wait_seconds=login_wait_seconds,
            raw_html_max_chars=raw_html_max_chars,
        )
    raise RuntimeError("CNKI_BROWSER_BACKEND must be 'playwright' or 'selenium'")


if __name__ == "__main__":
    connection = get_conn()
    try:
        count = run(connection)
        print(f"[OK] cnki items={count}")
    finally:
        connection.close()
