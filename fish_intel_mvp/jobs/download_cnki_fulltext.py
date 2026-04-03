"""
Manual-assist CNKI fulltext downloader for thesis artifact collection.

This helper is intentionally separate from the main `crawl_cnki.py` flow:
- `crawl_cnki.py` focuses on metadata collection and database ingestion.
- This script focuses on saving real CNKI PDF/HTML fulltext files to disk.

Typical usage:
    python fish_intel_mvp/jobs/download_cnki_fulltext.py --theme 三文鱼 --max-papers 5
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


DEFAULT_THEME = "三文鱼"
DEFAULT_MAX_PAPERS = 5
DEFAULT_BROWSER_CHANNEL = "msedge"

DATA_DIR = Path("data") / "cnki"
DEBUG_DIR = DATA_DIR / "debug"
STATE_DIR = DATA_DIR / "state"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download CNKI PDF/HTML fulltext files with manual login support."
    )
    parser.add_argument(
        "--theme",
        default=DEFAULT_THEME,
        help="CNKI search theme. Default: 三文鱼",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=DEFAULT_MAX_PAPERS,
        help="Maximum number of non-newspaper papers to save.",
    )
    parser.add_argument(
        "--browser-channel",
        default=DEFAULT_BROWSER_CHANNEL,
        help="Browser channel for Playwright launch, e.g. msedge. Empty means bundled Chromium.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode. Usually keep this off because CNKI may require manual login/captcha.",
    )
    parser.add_argument(
        "--prefer",
        choices=("pdf", "html", "auto"),
        default="pdf",
        help="Preferred fulltext format. Default: pdf",
    )
    return parser.parse_args()


def screenshot(page, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path), full_page=False)
    except Exception:
        pass


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]+', "", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:120] or f"paper_{int(time.time())}"


def is_auth_or_verify_url(url: str) -> bool:
    return any(flag in (url or "") for flag in ("/verify/", "captchaType", "passport.cnki.net"))


def prompt_continue(message: str) -> None:
    print(message)
    input("按 Enter 继续...")


def wait_for_results(page, timeout_seconds: int = 20) -> int:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        rows = page.locator("table.result-table-list tbody tr")
        count = rows.count()
        if count > 0:
            return count
        if is_auth_or_verify_url(page.url):
            prompt_continue("检测到知网验证或登录页面，请在浏览器中处理。")
        time.sleep(1)
    return 0


def choose_candidate(candidates: list[tuple[str, str]], prefer: str) -> tuple[str, str] | None:
    if not candidates:
        return None

    def pick(predicate):
        for item in candidates:
            if predicate(item):
                return item
        return None

    if prefer in {"pdf", "auto"}:
        chosen = pick(lambda item: item[0].strip() == "PDF下载")
        if chosen:
            return chosen
        chosen = pick(lambda item: "pdf" in item[0].lower() or "pdf" in item[1].lower())
        if chosen:
            return chosen

    if prefer in {"html", "auto", "pdf"}:
        chosen = pick(lambda item: item[0].strip() == "HTML阅读")
        if chosen:
            return chosen
        chosen = pick(lambda item: "html" in item[0].lower() or "html" in item[1].lower())
        if chosen:
            return chosen

    return candidates[0]


def collect_fulltext_candidates(detail_page) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    anchors = detail_page.locator("a")
    anchor_count = min(anchors.count(), 200)
    for index in range(anchor_count):
        try:
            anchor = anchors.nth(index)
            text = anchor.inner_text(timeout=300).strip()
            href = (anchor.get_attribute("href") or "").strip()
        except Exception:
            continue

        if not href:
            continue
        lower = (text + " " + href).lower()
        if any(
            bad in lower
            for bad in (
                "manual.html",
                "newhelper",
                "help",
                "javascript:void",
                "passport.cnki.net",
                "mailto:",
                "weibo",
            )
        ):
            continue
        if any(keyword in lower for keyword in ("html", "pdf", "caj", "全文", "阅读", "下载")):
            candidates.append((text, href))
    return candidates


def launch_browser(playwright, headless: bool, browser_channel: str):
    launch_kwargs = {"headless": headless}
    if browser_channel:
        launch_kwargs["channel"] = browser_channel
    try:
        return playwright.chromium.launch(**launch_kwargs)
    except Exception:
        if browser_channel:
            print(f"浏览器通道 {browser_channel!r} 启动失败，回退到 Playwright 自带 Chromium。")
            return playwright.chromium.launch(headless=headless)
        raise


def save_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path
    if target.exists():
        target = target.with_stem(f"{target.stem}_{int(time.time())}")
    target.write_text(content, encoding="utf-8")
    return target


def save_download(download, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path
    if target.exists():
        target = target.with_stem(f"{target.stem}_{int(time.time())}")
    download.save_as(target)
    return target


def perform_search(page, theme: str) -> int:
    page.set_default_timeout(15000)
    page.goto("https://kns.cnki.net/kns8/AdvSearch", wait_until="domcontentloaded")
    time.sleep(2)

    if is_auth_or_verify_url(page.url):
        prompt_continue("请先在浏览器中完成知网登录或验证。")
        page.goto("https://kns.cnki.net/kns8/AdvSearch", wait_until="domcontentloaded")
        time.sleep(2)

    topic_xpath = (
        "//div[@class='gradeSearch']//dl[@id='gradetxt']"
        "/dd[1]//input[@type='text' and @maxlength='120']"
    )
    page.locator(f"xpath={topic_xpath}").fill(theme)

    try:
        page.evaluate("document.querySelector('.search-sidebar-b')?.remove()")
    except Exception:
        pass

    page.locator(
        "xpath=//div[@class='search-buttons']/input[@class='btn-search']"
    ).click(force=True)
    time.sleep(3)

    return wait_for_results(page)


def iter_result_rows(page):
    rows = page.locator("table.result-table-list tbody tr")
    for index in range(rows.count()):
        yield rows.nth(index)


def main() -> None:
    args = parse_args()
    theme = args.theme.strip() or DEFAULT_THEME
    max_papers = max(1, args.max_papers)
    browser_channel = args.browser_channel.strip()

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    pdf_dir = DATA_DIR / "pdfs" / theme
    html_dir = DATA_DIR / "fulltexts" / theme
    pdf_dir.mkdir(parents=True, exist_ok=True)
    html_dir.mkdir(parents=True, exist_ok=True)
    storage_state_path = STATE_DIR / f"{sanitize_filename(theme)}_storage_state.json"

    with sync_playwright() as playwright:
        browser = launch_browser(
            playwright,
            headless=args.headless,
            browser_channel=browser_channel,
        )
        context_kwargs = {
            "viewport": {"width": 1600, "height": 1000},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "accept_downloads": True,
        }
        if storage_state_path.exists():
            context_kwargs["storage_state"] = str(storage_state_path)

        context = browser.new_context(**context_kwargs)

        try:
            print("=" * 70)
            print("CNKI 全文下载辅助工具")
            print("=" * 70)
            print(f"主题: {theme}")
            print(f"目标数量: {max_papers}")
            print(f"PDF 输出目录: {pdf_dir}")
            print(f"HTML 输出目录: {html_dir}")
            print("")
            print("会先打开浏览器，请根据需要完成机构登录或验证码。")

            login_page = context.new_page()
            login_page.goto("https://www.cnki.net/", wait_until="domcontentloaded")
            time.sleep(2)
            screenshot(login_page, DEBUG_DIR / "cnki_login_home.png")
            prompt_continue("浏览器已打开知网首页。")
            try:
                context.storage_state(path=str(storage_state_path))
            except Exception:
                pass
            login_page.close()

            page = context.new_page()
            row_count = perform_search(page, theme)
            if row_count == 0:
                print("没有搜索结果，或结果页未能成功加载。")
                return

            screenshot(page, DEBUG_DIR / "cnki_search_results.png")
            print(f"搜索结果页已加载，当前页找到 {row_count} 条结果。")
            print("")

            downloaded = 0
            current_page = 1
            seen_titles: set[str] = set()

            while downloaded < max_papers:
                rows = list(iter_result_rows(page))
                if not rows:
                    print(f"第 {current_page} 页没有结果，停止。")
                    break

                print(f"第 {current_page} 页，共 {len(rows)} 条结果。")
                for row in rows:
                    if downloaded >= max_papers:
                        break

                    try:
                        title_link = row.locator("a.fz14").first
                        list_title = title_link.inner_text(timeout=3000).strip()
                    except Exception:
                        list_title = ""

                    if not list_title:
                        continue
                    if list_title in seen_titles:
                        continue

                    try:
                        db_name = row.locator("td.data").inner_text(timeout=1000).strip()
                    except Exception:
                        db_name = ""

                    if "报纸" in db_name:
                        print(f"跳过报纸类结果: {list_title[:40]}")
                        seen_titles.add(list_title)
                        continue

                    print(f"\n[{downloaded + 1}/{max_papers}] {list_title}")

                    href = title_link.get_attribute("href") or ""
                    if href.startswith("//"):
                        href = "https:" + href
                    elif href and not href.startswith("http"):
                        href = "https://kns.cnki.net" + href
                    if not href:
                        print("  跳过：未获取到详情页链接。")
                        seen_titles.add(list_title)
                        continue

                    detail_page = context.new_page()
                    detail_page.set_default_timeout(15000)
                    try:
                        detail_page.goto(href, wait_until="domcontentloaded", timeout=20000)
                    except PlaywrightTimeoutError:
                        print("  详情页加载超时，继续尝试提取。")
                    time.sleep(3)

                    if is_auth_or_verify_url(detail_page.url):
                        prompt_continue("详情页遇到验证或登录，请先在浏览器中处理。")
                        try:
                            detail_page.goto(href, wait_until="domcontentloaded", timeout=20000)
                        except PlaywrightTimeoutError:
                            pass
                        time.sleep(3)

                    screenshot(detail_page, DEBUG_DIR / f"detail_{downloaded + 1}.png")

                    candidates = collect_fulltext_candidates(detail_page)
                    if not candidates:
                        print("  未找到全文入口。")
                        try:
                            save_text(
                                DEBUG_DIR / f"detail_page_{downloaded + 1}.html",
                                detail_page.content(),
                            )
                        except Exception:
                            pass
                        detail_page.close()
                        seen_titles.add(list_title)
                        continue

                    chosen = choose_candidate(candidates, args.prefer)
                    if chosen is None:
                        detail_page.close()
                        seen_titles.add(list_title)
                        continue

                    target_text, _target_href = chosen
                    safe_title = sanitize_filename(list_title)
                    button_locator = detail_page.locator(f'a:has-text("{target_text}")').first

                    if target_text.strip() == "PDF下载" or "pdf" in target_text.lower():
                        try:
                            with detail_page.expect_download() as download_info:
                                button_locator.click()
                            download = download_info.value
                            saved_path = save_download(download, pdf_dir / f"{safe_title}.pdf")
                            print(f"  PDF 保存成功: {saved_path}")
                            downloaded += 1
                        except Exception as exc:
                            print(f"  PDF 下载失败: {exc}")
                        finally:
                            detail_page.close()
                            seen_titles.add(list_title)
                        continue

                    html_page = None
                    try:
                        with context.expect_page(timeout=8000) as new_page_info:
                            button_locator.click()
                        html_page = new_page_info.value
                    except Exception:
                        html_page = None

                    if html_page is not None:
                        time.sleep(5)
                        if is_auth_or_verify_url(html_page.url):
                            prompt_continue("全文页遇到验证或登录，请先在浏览器中处理。")
                        try:
                            saved_path = save_text(
                                html_dir / f"{safe_title}.html",
                                html_page.content(),
                            )
                            print(f"  HTML 保存成功: {saved_path}")
                            downloaded += 1
                        except Exception as exc:
                            print(f"  HTML 保存失败: {exc}")
                        finally:
                            try:
                                html_page.close()
                            except Exception:
                                pass
                            detail_page.close()
                            seen_titles.add(list_title)
                        continue

                    print("  未能打开 PDF/HTML 全文页。")
                    detail_page.close()
                    seen_titles.add(list_title)

                if downloaded >= max_papers:
                    break

                next_button = page.locator('a:has-text("下一页")')
                if next_button.count() == 0:
                    print("未找到下一页按钮，停止。")
                    break
                try:
                    if next_button.is_disabled():
                        print("下一页按钮已禁用，停止。")
                        break
                except Exception:
                    pass

                print("尝试翻到下一页...")
                next_button.click()
                time.sleep(2)
                if wait_for_results(page, timeout_seconds=10) == 0:
                    print("翻页后未检测到结果，停止。")
                    break
                current_page += 1

            print("")
            print("=" * 70)
            print(f"完成，共保存 {downloaded} 篇全文文件。")
            print(f"PDF 目录: {pdf_dir}")
            print(f"HTML 目录: {html_dir}")
            print("=" * 70)
            print("关闭浏览器前，会顺手保存登录态，便于下次继续。")

            try:
                context.storage_state(path=str(storage_state_path))
            except Exception:
                pass

            if sys.stdin and sys.stdin.isatty():
                input("按 Enter 关闭浏览器退出...")
        finally:
            try:
                browser.close()
            except Exception as exc:
                print(f"关闭浏览器时出现异常（可忽略）: {exc}")


if __name__ == "__main__":
    main()
