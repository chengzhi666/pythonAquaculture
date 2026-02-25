import logging
import os
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support import expected_conditions as EC  # noqa: N812
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)


def create_driver():
    """
    Create and return an Edge WebDriver.
    - If EDGE_DRIVER_PATH is set, use that driver binary.
    - Otherwise let Selenium Manager auto-resolve a matching driver.
    """
    options = webdriver.EdgeOptions()
    # 如果你想加快一点速度，可以取消注释这两行（不加载图片、懒加载页面）
    # options.page_load_strategy = "none"
    # options.add_experimental_option(
    #     "prefs", {"profile.managed_default_content_settings.images": 2}
    # )

    driver_path = os.environ.get("EDGE_DRIVER_PATH", "").strip()
    if driver_path:
        service = Service(driver_path)
        driver = webdriver.Edge(service=service, options=options)
    else:
        driver = webdriver.Edge(options=options)
    driver.maximize_window()
    return driver


def open_page(driver, theme: str):
    """
    打开知网高级检索页面，并用主题词 theme 进行检索，停在结果列表第一页
    """
    driver.get("https://kns.cnki.net/kns8/AdvSearch")
    wait = WebDriverWait(driver, 30)

    # ===== 1. 主题输入框（第 1 行）=====
    topic_xpath = (
        "//div[@class='gradeSearch']//dl[@id='gradetxt']"
        "/dd[1]//input[@type='text' and @maxlength='120']"
    )
    topic_input = wait.until(EC.element_to_be_clickable((By.XPATH, topic_xpath)))
    topic_input.clear()
    topic_input.send_keys(theme)

    # ===== 2.（可选）文献来源输入框（第 3 行）=====
    # 如果暂时不需要限制文献来源，可以先不填
    # source_xpath = "//div[@class='gradeSearch']//dl[@id='gradetxt']/dd[3]//input[@type='text' and @maxlength='120']"
    # source_input = wait.until(EC.element_to_be_clickable((By.XPATH, source_xpath)))
    # source_input.clear()
    # source_input.send_keys("期刊")

    # ===== 3. 点击“检索”按钮 =====
    search_button_xpath = "//div[@class='search-buttons']/input[@class='btn-search']"
    search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, search_button_xpath)))
    search_btn.click()

    # ===== 4. 等待结果列表加载出来 =====
    wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table.result-table-list tbody tr"))
    )
    logger.info("检索结果页加载完成")


def crawl(driver, papers_need: int, theme: str) -> list[dict]:
    """
    真正干活的函数：在结果列表翻页、点详情、抽取字段，返回 IntelItem 列表
    返回值：List[dict]，每个 dict 是一条情报
    """
    wait = WebDriverWait(driver, 20)
    results: list[dict] = []  # 用来存放所有情报
    count = 1  # 已经尝试爬取的条数（包含失败）

    while count <= papers_need:
        # 等当前页的结果行加载出来
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.result-table-list tbody tr"))
        )
        time.sleep(1)

        # 重新获取当前页所有行（每页一般 20 条）
        rows = driver.find_elements(By.CSS_SELECTOR, "table.result-table-list tbody tr")

        for row_index in range(len(rows)):
            if count > papers_need:
                break

            try:
                # 再取一次，避免刚才 list 失效
                rows = driver.find_elements(By.CSS_SELECTOR, "table.result-table-list tbody tr")
                row = rows[row_index]

                # 标题链接（a.fz14）
                title_link = row.find_element(By.CSS_SELECTOR, "a.fz14")
                list_title = title_link.text.strip()

                # 列表页上的作者、来源、日期、数据库
                try:
                    authors_list = row.find_element(By.CSS_SELECTOR, "td.author").text.strip()
                except Exception:
                    authors_list = ""
                try:
                    source = row.find_element(By.CSS_SELECTOR, "td.source").text.strip()
                except Exception:
                    source = ""
                try:
                    date = row.find_element(By.CSS_SELECTOR, "td.date").text.strip()
                except Exception:
                    date = ""
                try:
                    database = row.find_element(By.CSS_SELECTOR, "td.data").text.strip()
                except Exception:
                    database = ""

                # 点击标题，打开详情页
                original_handle = driver.current_window_handle
                driver.execute_script("arguments[0].click();", title_link)

                # 等待新标签页（大多数情况下知网是新标签打开）
                time.sleep(2)
                handles = driver.window_handles
                if len(handles) > 1:
                    driver.switch_to.window(handles[-1])
                # 否则就在当前标签打开，不切换

                try:
                    # ======= 详情页提取信息 =======
                    # 标题
                    title = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.wxTitle h1, h1"))
                    ).text.strip()

                    # 作者、单位
                    try:
                        authors_detail = driver.find_element(
                            By.CSS_SELECTOR, "div.wxTitle h3:nth-of-type(1)"
                        ).text.strip()
                    except Exception:
                        authors_detail = authors_list or ""
                    try:
                        institute = driver.find_element(
                            By.CSS_SELECTOR, "div.wxTitle h3:nth-of-type(2)"
                        ).text.strip()
                    except Exception:
                        institute = ""

                    # 摘要（新老页面有两种常见写法）
                    try:
                        abstract = driver.find_element(
                            By.CSS_SELECTOR,
                            "span#ChDivSummary, div.abstract-text",
                        ).text.strip()
                    except Exception:
                        abstract = "无"

                    # 关键词（这里的选择器可能不完全可靠，视页面结构调整）
                    try:
                        kw_el = driver.find_element(
                            By.CSS_SELECTOR,
                            ".keywords, p.keywords",
                        )
                        keywords_text = kw_el.text.strip()
                    except Exception:
                        keywords_text = ""

                    url = driver.current_url

                    # ======= 组装 IntelItem 字典 =======
                    # 关键词简单按分号/空格切开，你可以视情况调整
                    if keywords_text:
                        # 例： "关键词：A；B；C" 或 "A;B;C"
                        for sep in ["关键词：", "关键词:", "Key words:", "关键词"]:
                            if sep in keywords_text:
                                keywords_text = keywords_text.replace(sep, "")
                        tags = [
                            k.strip()
                            for k in keywords_text.replace("；", ";").split(";")
                            if k.strip()
                        ]
                    else:
                        tags = []

                    item = {
                        "title": title or list_title,
                        "content": abstract,
                        "pub_time": date,  # 先保存字符串形式，之后可转 datetime
                        "region": "中国-全国",  # 先写死
                        "org": institute or source,  # 单位优先，其次期刊/来源
                        "source_type": "CNKI",
                        "source_url": url,
                        "tags": tags,
                        "extra": {
                            "authors": authors_detail,
                            "list_authors": authors_list,
                            "journal": source,
                            "database": database,
                            "theme": theme,
                        },
                    }

                    # 加入结果列表
                    results.append(item)
                    logger.info(
                        "[OK] 第%d条：%s (%s | %s)", count, title, date, institute or source
                    )

                except Exception as e_detail:
                    logger.warning("第%d条详情页爬取失败: %s", count, e_detail)

                finally:
                    # 关掉详情页，回到列表
                    handles = driver.window_handles
                    if len(handles) > 1:
                        driver.close()
                        driver.switch_to.window(original_handle)
                    else:
                        # 如果是在同一标签打开，就回退
                        driver.back()
                        wait.until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, "table.result-table-list tbody tr")
                            )
                        )

                    count += 1  # 不论成功失败，计数+1，避免死循环

            except Exception as e_row:
                logger.warning("第%d条列表行爬取失败: %s", count, e_row)
                count += 1
                continue

        # ===== 翻页 =====
        if count <= papers_need:
            try:
                next_btn = wait.until(EC.element_to_be_clickable((By.ID, "PageNext")))
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(2)
            except Exception as e_next:
                logger.info("翻页失败或没有下一页了：%s", e_next)
                break

    return results


def crawl_cnki(theme: str, papers_need: int) -> list[dict]:
    """
    对外使用的入口：输入主题和需要的篇数，返回 IntelItem 列表
    """
    driver = create_driver()
    try:
        open_page(driver, theme)
        items = crawl(driver, papers_need, theme)
        return items
    finally:
        driver.quit()


# ===== 测试入口：单独运行本文件时执行 =====
if __name__ == "__main__":
    theme = "python"  # 这里你可以改成“水产养殖”等等
    papers_need = 10  # 测试先抓 10 条

    data = crawl_cnki(theme, papers_need)
    print("\n==================== 抓取结果预览 ====================")
    print("总条数：", len(data))
    for i, it in enumerate(data, start=1):
        print(f"[{i}] {it['pub_time']} | {it['org']} | {it['title']}")
        print("     URL:", it["source_url"])
        print("     tags:", it["tags"])
        print("-" * 80)
