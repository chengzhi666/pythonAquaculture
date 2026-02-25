import logging
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from requests import RequestException

from crawlers.utils import DEFAULT_TIMEOUT, create_session

logger = logging.getLogger(__name__)

BASE_URL = "https://yyj.moa.gov.cn"
LIST_FIRST = "https://yyj.moa.gov.cn/tzgg/index.htm"

# 模块级共享 session（带 UA + 自动重试）
_session = create_session()


def parse_tzgg_list(html: str, list_url: str):
    """
    解析通知公告列表页 HTML，返回若干 {title, url, pub_time} 字典
    list_url 用来把相对链接补成绝对链接
    """
    soup = BeautifulSoup(html, "lxml")

    # 定位到这个块：<div class="sj_e_tonzhi_list"><ul id="div">...</ul></div>
    ul = soup.select_one("div.sj_e_tonzhi_list ul#div")
    if not ul:
        logger.warning("没有找到列表 ul#div，检查一下选择器")
        return []

    results = []

    for li in ul.find_all("li"):
        a = li.find("a")
        if not a:
            continue

        # 标题在 <span class="sj_gztzle">
        title_span = a.find("span", class_="sj_gztzle")
        # 日期在 <span class="sj_gztzri">
        date_span = a.find("span", class_="sj_gztzri")

        if not title_span or not date_span:
            continue

        title = title_span.get_text(strip=True)
        pub_time = date_span.get_text(strip=True)

        href = a.get("href", "").strip()
        if not href:
            continue

        # 把相对路径补成绝对 URL（处理 ./ 和 ../ 这两种情况）
        detail_url = urljoin(list_url, href)

        results.append(
            {
                "title": title,
                "pub_time": pub_time,
                "url": detail_url,
            }
        )

    return results


def fetch_tzgg_page(page_index: int = 0):
    """
    抓取第 page_index 页的通知公告列表：
    0 -> index.htm
    1 -> index_1.htm
    2 -> index_2.htm ...
    如果列表页请求超时/网络错误，返回 []，并打印错误提示。
    """
    if page_index == 0:
        list_url = LIST_FIRST
    else:
        list_url = f"https://yyj.moa.gov.cn/tzgg/index_{page_index}.htm"

    logger.info("正在抓取通知公告第 %d 页...", page_index)

    try:
        resp = _session.get(list_url, timeout=DEFAULT_TIMEOUT)
        # 如果状态码不是 2xx，会抛异常
        resp.raise_for_status()
    except RequestException as e:
        logger.error("列表页抓取失败，page=%d, url=%s, 错误：%s", page_index, list_url, e)
        return []

    # 自动根据网页猜编码，防止中文乱码
    resp.encoding = resp.apparent_encoding
    html = resp.text

    # 调用解析函数
    items = parse_tzgg_list(html, list_url)
    return items


def fetch_tzgg_detail(base: dict) -> dict:
    """
    根据列表页拿到的 {title, pub_time, url}，
    进一步请求详情页，解析出更准确的标题 / 日期 / 作者 / 来源 / 正文
    返回一个 dict
    """
    url = base["url"]
    resp = _session.get(url, timeout=DEFAULT_TIMEOUT)
    resp.encoding = resp.apparent_encoding
    html = resp.text

    soup = BeautifulSoup(html, "lxml")

    # 1. 标题：优先用详情页的 <h1>，没有就退回列表页 title
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    else:
        title = base["title"]

    # 2. 元信息：日期 / 作者 / 来源
    pub_time = base["pub_time"]  # 默认用列表页的日期
    author = ""
    source = "渔业渔政管理局"

    # 找一行同时包含“日期：”“作者：”“来源：”的标签
    meta_tag = None
    meta_text = ""
    for tag in soup.find_all(["p", "div", "span"]):
        txt = tag.get_text(strip=True)
        if "日期：" in txt and "作者" in txt and "来源" in txt:
            meta_tag = tag
            meta_text = txt.replace("\u3000", " ")  # 去掉全角空格
            break

    if meta_tag:
        # 例子：日期：2025-11-20 作者：  来源：渔业渔政管理局 〖字号：大 中 小〗 打印本页
        m = re.search(r"日期：(\d{4}-\d{2}-\d{2})", meta_text)
        if m:
            pub_time = m.group(1)

        # 作者：截到“来源/【/〖”之前
        m = re.search(r"作者：([^来源〖【]+)", meta_text)
        if m:
            author = m.group(1).strip()

        # 来源：截到“【字号”或“打印本页”等之前
        m = re.search(r"来源：(.+?)(?:【字号|〖字号|打印本页|$)", meta_text)
        if m:
            source = m.group(1).strip() or source

    # 3. 正文内容
    content_paras = []

    # 从 meta_tag 往后找所有 <p>，遇到“附件下载/主办单位/网站识别码”等就停止
    start_node = meta_tag if meta_tag else soup
    for p in start_node.find_all_next("p"):
        txt = p.get_text(strip=True)
        if not txt:
            continue

        # 导航条：直接跳过
        if txt.startswith("当前位置："):
            continue

        # 碰到附件区或页脚就停止
        if "附件下载" in txt:
            break
        if "主办单位：" in txt or "网站识别码" in txt or "承办单位：" in txt:
            break

        content_paras.append(txt)

    content = "\n".join(content_paras)

    return {
        "title": title,
        "pub_time": pub_time,
        "author": author,
        "source": source,
        "content": content,
    }


def to_intel_item(base: dict) -> dict:
    return {
        "title": base["title"],
        "content": "",  # 这里暂时先不抓详情页正文，后面再补
        "pub_time": base["pub_time"],
        "region": "中国-全国",
        "org": "农业农村部渔业渔政管理局",
        "source_type": "MOA_FISHERY_TZGG",
        "source_url": base["url"],
        "tags": [],
        "extra": {},
    }


def crawl_moa_fishery_tzgg(max_pages: int = 1) -> list[dict]:
    """
    对外使用的入口函数：
    连续抓取前 max_pages 页通知公告列表，
    对每条请求详情页，返回 List[IntelItem]
    """
    all_items = []

    for page in range(max_pages):
        base_list = fetch_tzgg_page(page)

        # 列表页失败或为空的情况
        if not base_list:
            if page == 0:
                logger.error("第 0 页列表抓取失败，本次不继续抓取渔业渔政通知公告。")
                break
            else:
                logger.warning("第 %d 页列表为空，跳过该页。", page)
                continue

        logger.info("本页抓到 %d 条", len(base_list))

        for base in base_list:
            try:
                detail = fetch_tzgg_detail(base)
            except Exception as e:
                logger.warning("抓详情失败，跳过：%s 错误：%s", base["url"], e)
                continue

            intel_item = {
                "title": detail["title"],
                "content": detail["content"],
                "pub_time": detail["pub_time"],
                "region": "中国-全国",
                "org": detail["source"] or "农业农村部渔业渔政管理局",
                "source_type": "MOA_FISHERY_TZGG",
                "source_url": base["url"],
                "tags": [],  # 后面可以根据标题加“养殖政策/环境/疫病”等标签
                "extra": {
                    "author": detail["author"],
                    "channel": "通知公告",
                },
            }
            all_items.append(intel_item)

            # 轻微 sleep，避免请求太频繁
            time.sleep(0.5)

    logger.info("本次渔业渔政通知公告成功采集 %d 条", len(all_items))
    return all_items


if __name__ == "__main__":
    items = crawl_moa_fishery_tzgg(max_pages=1)
    print("总共抓到：", len(items), "条")
    for i, it in enumerate(items[:5], start=1):  # 想看几条就改几条
        print(f"[{i}] {it['pub_time']} | {it['org']} | {it['title']}")
        print("URL:", it["source_url"])
        print("来源字段：", it["org"])
        print("正文前100字：", it["content"][:100].replace("\n", " "))
        print("-" * 80)
