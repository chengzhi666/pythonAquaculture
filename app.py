# app.py

import logging

import streamlit as st

from config_mgr import get_config
from crawlers.cnki_crawler import crawl_cnki
from crawlers.moa_fishery_crawler import crawl_moa_fishery_tzgg
from query.cli_query import QueryRow, query_intel
from runner import run_from_config
from storage.db import init_db, save_items

# 配置日志
_cfg = get_config()
logging.basicConfig(level=getattr(logging, _cfg.LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

# 初始化数据库
init_db()


@st.cache_data(ttl=3600)
def _cached_query(keyword: str, order_by: str) -> list[QueryRow]:
    """缓存查询结果（1小时）"""
    try:
        rows = query_intel(keyword=keyword, order_by=order_by)
        return rows
    except Exception as e:
        logger.error(f"查询失败：{e}")
        return []


def render_preview(items, limit: int = 20):
    """展示前 N 条作为预览"""
    if not items:
        st.info("没有数据")
        return
    preview = [
        {
            "时间": it.get("pub_time", ""),
            "单位": it.get("org", ""),
            "来源类型": it.get("source_type", ""),
            "标题": it.get("title", ""),
            "链接": it.get("source_url", ""),
        }
        for it in items[:limit]
    ]
    st.subheader(f"本次采集结果预览（前 {limit} 条）")
    st.table(preview)


def page_collect():
    st.header("情报采集")

    keyword = st.text_input("请输入采集主题关键词（用于知网检索）", "水产养殖")

    col1, col2 = st.columns(2)
    with col1:
        cnki_num = st.number_input("知网采集篇数", min_value=0, max_value=200, value=20, step=10)
    with col2:
        moa_pages = st.number_input(
            "渔业渔政局通知公告页数", min_value=0, max_value=10, value=1, step=1
        )

    st.caption("建议使用“按配置采集”，后续新增网站只需改配置文件，不用改前端/执行器。")

    # 两个按钮并排
    btn_col1, btn_col2 = st.columns(2)

    # 旧版：写死调用（保留，方便你对照/回退）
    with btn_col1:
        if st.button("开始采集（旧版写死调用）"):
            try:
                init_db()
                all_items = []

                # 1. 知网
                if cnki_num > 0:
                    st.write("正在从知网采集数据...")
                    cnki_items = crawl_cnki(keyword, int(cnki_num))
                    st.write(f"知网采集完成：{len(cnki_items)} 条")
                    save_items(cnki_items)
                    all_items.extend(cnki_items)

                # 2. 渔业渔政局通知公告
                if moa_pages > 0:
                    st.write("正在从农业农村部渔业渔政管理局采集通知公告...")
                    moa_items = crawl_moa_fishery_tzgg(max_pages=int(moa_pages))
                    st.write(f"渔业渔政局采集完成：{len(moa_items)} 条")
                    save_items(moa_items)
                    all_items.extend(moa_items)

                st.success(f"本次共采集并入库 {len(all_items)} 条情报")
                render_preview(all_items, limit=20)

            except Exception as e:
                st.error(f"采集失败：{e}")

    # 新版：按配置采集（推荐）
    with btn_col2:
        if st.button("按配置采集（推荐）"):
            try:
                overrides = {
                    "cnki.theme": keyword,
                    "cnki.papers_need": int(cnki_num),
                    "moa_yyj_tzgg.max_pages": int(moa_pages),
                }
                items = run_from_config("config/sites.json", overrides=overrides, save_to_db=True)

                st.success(f"本次共采集并入库 {len(items)} 条情报")
                render_preview(items, limit=20)

            except FileNotFoundError:
                st.error("找不到 config/sites.json，请先创建配置文件：config/sites.json")
            except Exception as e:
                st.error(f"按配置采集失败：{e}")


def page_query():
    st.header("情报检索")

    keyword = st.text_input("关键词（在标题或内容中匹配）", "")
    col1, col2 = st.columns([2, 1])

    with col1:
        order_by_label = st.selectbox(
            "排序方式", options=["按时间（最新在前）", "按单位+时间", "按区域+时间"], index=0
        )

    with col2:
        use_cache = st.checkbox("使用缓存查询", value=True)

    if order_by_label == "按时间（最新在前）":
        ob = "time"
    elif order_by_label == "按单位+时间":
        ob = "org_time"
    else:
        ob = "region_time"

    if st.button("开始查询"):
        try:
            st.write("正在查询，请稍候...")

            if use_cache:
                rows = _cached_query(keyword=keyword, order_by=ob)
            else:
                # 清除缓存并重新查询
                _cached_query.clear()
                rows = query_intel(keyword=keyword, order_by=ob)

            st.write(f"共查询到 {len(rows)} 条，展示前 50 条：")

            if not rows:
                st.info("没有查询结果")
            else:
                preview = []
                for pub_time, region, org, title, source_type, url in rows[:50]:
                    preview.append(
                        {
                            "时间": pub_time,
                            "区域": region,
                            "单位": org,
                            "来源类型": source_type,
                            "标题": title,
                            "链接": url,
                        }
                    )
                st.table(preview)
        except Exception as e:
            logger.error(f"查询失败：{e}")
            st.error(f"查询失败：{e}")


def main():
    st.set_page_config(page_title="水产养殖情报采集与分析系统", layout="wide")
    st.title("水产养殖情报采集与分析系统")

    tabs = st.tabs(["采集（输入关键词自动爬取）", "查询（按条件检索历史情报）"])
    with tabs[0]:
        page_collect()
    with tabs[1]:
        page_query()


if __name__ == "__main__":
    main()
