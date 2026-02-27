import json
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

try:
    from common.db import get_conn, insert_raw_event, upsert_paper
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from common.db import get_conn, insert_raw_event, upsert_paper


def open_page(page, theme):
    # 打开高级检索页面
    page.goto("https://kns.cnki.net/kns8/AdvSearch", wait_until="domcontentloaded")
    page.set_viewport_size({"width": 1600, "height": 1000})

    # ===== 1. 主题输入框（第 1 行）=====
    topic_xpath = "//div[@class='gradeSearch']//dl[@id='gradetxt']/dd[1]//input[@type='text' and @maxlength='120']"
    topic_input = page.locator(f"xpath={topic_xpath}")
    topic_input.wait_for(state="visible", timeout=30000)
    topic_input.fill(theme)

    # ===== 2.（可选）文献来源输入框（第 3 行）=====
    # 如果暂时不需要限制文献来源，可以先不填
    # source_xpath = "//div[@class='gradeSearch']//dl[@id='gradetxt']/dd[3]//input[@type='text' and @maxlength='120']"
    # source_input = page.locator(f"xpath={source_xpath}")
    # source_input.wait_for(state="visible", timeout=30000)
    # source_input.fill("期刊")

    # ===== 3. 点击"检索"按钮 =====
    search_button_xpath = "//div[@class='search-buttons']/input[@class='btn-search']"
    search_btn = page.locator(f"xpath={search_button_xpath}")
    search_btn.wait_for(state="visible", timeout=30000)
    search_btn.click()

    # 等待点击后的页面导航/加载完成
    page.wait_for_load_state("domcontentloaded", timeout=45000)

    # ===== 4. 等待结果列表加载出来（兼容登录页跳转）=====
    deadline = time.time() + 60
    while time.time() < deadline:
        current_url = page.url or ""
        # 如果跳转到了登录页，等待用户手动登录
        if "passport.cnki.net" in current_url:
            print("检测到知网登录页，请在浏览器中完成登录…")
            while "passport.cnki.net" in (page.url or ""):
                page.wait_for_timeout(1000)
            # 登录完成后重新提交搜索
            print("登录完成，重新提交搜索…")
            page.goto("https://kns.cnki.net/kns8/AdvSearch", wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            topic_input2 = page.locator(f"xpath={topic_xpath}")
            topic_input2.wait_for(state="visible", timeout=30000)
            topic_input2.fill(theme)
            search_btn2 = page.locator(f"xpath={search_button_xpath}")
            search_btn2.wait_for(state="visible", timeout=10000)
            # 用 expect_navigation 确保等到搜索结果页加载
            try:
                with page.expect_navigation(wait_until="domcontentloaded", timeout=45000):
                    search_btn2.click()
            except Exception:
                # 如果没发生导航（AJAX加载结果），等一下就好
                page.wait_for_timeout(3000)
            continue

        # 检查结果表格是否已出现
        rows = page.locator("table.result-table-list tbody tr")
        if rows.count() > 0:
            break
        page.wait_for_timeout(500)
    else:
        raise TimeoutError("等待检索结果超时（60s），当前URL: " + (page.url or ""))

    print("检索结果页加载完成")


def crawl(page, context, papers_need, theme, conn=None):
    count = 1  # 已经成功爬到的条数

    while count <= papers_need:
        # 等当前页的结果行加载出来
        page.wait_for_selector("table.result-table-list tbody tr", timeout=20000)
        time.sleep(1)

        # 重新获取当前页所有行（每页一般 20 条）
        rows = page.locator("table.result-table-list tbody tr")
        row_count = rows.count()

        for row_index in range(row_count):
            if count > papers_need:
                break

            try:
                # 再取一次，避免刚才 list 失效
                rows = page.locator("table.result-table-list tbody tr")
                row = rows.nth(row_index)

                # 标题链接（a.fz14）
                title_link = row.locator("a.fz14").first
                list_title = title_link.inner_text(timeout=5000).strip()

                # 列表页上的作者、来源、日期、数据库
                try:
                    authors_list = row.locator("td.author").inner_text(timeout=2000).strip()
                except Exception:
                    authors_list = ""
                try:
                    source = row.locator("td.source").inner_text(timeout=2000).strip()
                except Exception:
                    source = ""
                try:
                    date = row.locator("td.date").inner_text(timeout=2000).strip()
                except Exception:
                    date = ""
                try:
                    database = row.locator("td.data").inner_text(timeout=2000).strip()
                except Exception:
                    database = ""

                # 获取详情页链接，在新标签中打开
                detail_href = title_link.get_attribute("href") or ""
                if detail_href.startswith("//"):
                    detail_href = "https:" + detail_href
                elif detail_href and not detail_href.startswith("http"):
                    detail_href = "https://kns.cnki.net" + detail_href

                detail_page = None
                opened_new_tab = False
                if detail_href:
                    # 优先用链接直接在新标签打开，最稳定
                    detail_page = context.new_page()
                    opened_new_tab = True
                    try:
                        detail_page.goto(detail_href, wait_until="domcontentloaded", timeout=30000)
                    except Exception:
                        pass  # 部分内容可能已加载，继续尝试提取
                else:
                    # 没有 href，尝试点击
                    try:
                        with context.expect_page(timeout=8000) as new_page_info:
                            title_link.click()
                        detail_page = new_page_info.value
                        opened_new_tab = True
                        detail_page.wait_for_load_state("domcontentloaded", timeout=20000)
                    except Exception:
                        detail_page = page

                try:
                    # ======= 详情页提取信息 =======
                    # 标题
                    title = detail_page.locator("div.wxTitle h1, h1").first.inner_text(
                        timeout=20000
                    ).strip()

                    # 作者、单位
                    try:
                        authors_detail = detail_page.locator(
                            "div.wxTitle h3:nth-of-type(1)"
                        ).first.inner_text(timeout=2000).strip()
                    except Exception:
                        authors_detail = authors_list or ""
                    try:
                        institute = detail_page.locator(
                            "div.wxTitle h3:nth-of-type(2)"
                        ).first.inner_text(timeout=2000).strip()
                    except Exception:
                        institute = ""

                    # 摘要（新老页面有两种常见写法）
                    try:
                        abstract = detail_page.locator(
                            "span#ChDivSummary, div.abstract-text"
                        ).first.inner_text(timeout=2000).strip()
                    except Exception:
                        abstract = "无"

                    # 关键词
                    try:
                        keywords = detail_page.locator(
                            ".keywords, p.keywords"
                        ).first.inner_text(timeout=2000).strip()
                    except Exception:
                        keywords = "无"

                    url = detail_page.url

                    # 写入文件
                    res = f"{count}\t{title}\t{authors_detail}\t{institute}\t{date}\t{source}\t{database}\t{keywords}\t{abstract}\t{url}"
                    res = res.replace("\n", "") + "\n"
                    print(res)

                    with open(f"CNKI_{theme}.tsv", "a", encoding="gbk", errors="ignore") as f:
                        f.write(res)

                    # ===== 入库 =====
                    if conn is not None:
                        try:
                            raw_id = insert_raw_event(
                                conn,
                                source_name="cnki",
                                url=url,
                                title=title,
                                pub_time=date,
                                raw_text="",
                                raw_json=json.dumps({
                                    "authors": authors_detail,
                                    "institute": institute,
                                    "source": source,
                                    "database": database,
                                    "keywords": keywords,
                                    "abstract": abstract,
                                }, ensure_ascii=False),
                            )
                            upsert_paper(conn, {
                                "theme": theme,
                                "title": title,
                                "authors": authors_detail,
                                "institute": institute,
                                "source": source,
                                "pub_date": date,
                                "database_name": database,
                                "abstract": abstract,
                                "keywords_json": json.dumps(
                                    [k.strip() for k in keywords.replace("\uff1b", ";").split(";") if k.strip()]
                                    if keywords and keywords != "无" else [],
                                    ensure_ascii=False,
                                ),
                                "url": url,
                                "raw_id": raw_id,
                            })
                            print(f"第{count}条已入库")
                        except Exception as e_db:
                            print(f"第{count}条入库失败: {e_db}")

                except Exception as e_detail:
                    print(f"第{count}条详情页爬取失败: {e_detail}")

                finally:
                    # 关掉详情页，回到列表
                    if opened_new_tab and detail_page is not page:
                        detail_page.close()
                    else:
                        # 如果是在同一标签打开，就回退
                        page.go_back(wait_until="domcontentloaded")
                        page.wait_for_selector(
                            "table.result-table-list tbody tr", timeout=20000
                        )

                    count += 1

            except Exception as e_row:
                print(f"第{count}条爬取失败: {e_row}")
                count += 1
                continue

        # ===== 翻页 =====
        if count <= papers_need:
            try:
                next_btn = page.locator("#PageNext")
                next_btn.wait_for(state="visible", timeout=20000)
                next_btn.click()
                time.sleep(2)
            except Exception as e_next:
                print(f"翻页失败或没有下一页了：{e_next}")
                break


def _launch_and_crawl(conn, theme, papers_need):
    """启动浏览器并执行采集，返回采集条数。"""
    with sync_playwright() as p:
        headless = os.getenv("CNKI_HEADLESS", "0").strip() == "1"
        browser = p.chromium.launch(
            headless=headless,
            channel="msedge",
        )

        context = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # 不加载图片，提高速度
        context.route(
            "**/*",
            lambda route: (
                route.abort()
                if route.request.resource_type == "image"
                else route.continue_()
            ),
        )

        page = context.new_page()
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(45000)

        try:
            open_page(page, theme)
            crawl(page, context, papers_need, theme, conn=conn)
        finally:
            browser.close()

    return papers_need


def run(conn) -> int:
    """标准入口，供 run_one.py 等调度模块调用。"""
    theme = os.getenv("CNKI_THEME", "aquaculture").strip() or "aquaculture"
    papers_need = max(1, int(os.getenv("CNKI_PAPERS", "10")))
    return _launch_and_crawl(conn, theme, papers_need)


if __name__ == "__main__":
    # 设置搜索主题
    theme = "python"
    # 设置所需篇数
    papers_need = 20

    # 连接数据库
    conn = None
    try:
        conn = get_conn()
        print("数据库连接成功，采集结果将同时入库")
    except Exception as e:
        print(f"数据库连接失败，仅写入TSV: {e}")

    try:
        _launch_and_crawl(conn, theme, papers_need)
    finally:
        if conn is not None:
            conn.close()
