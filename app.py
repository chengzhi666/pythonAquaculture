"""
水产养殖情报采集与分析系统 — Flask 可视化界面
功能：关键词输入 → 选择爬虫 → 一键采集 → 数据查询/展示

注意事项：
  - 知网(CNKI)：需手动完成滑块验证
  - 京东(JD)：需扫码登录
  - 淘宝(Taobao)：需提前运行 refresh_taobao_cookie.py 获取 cookie
  - 农业农村部(MOA)：无需额外操作
"""

import logging
import os
import sys
import threading
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from flask import Flask, jsonify, render_template, request

# ── 让 fish_intel_mvp 包可被 import ──────────────────────────────────
MVP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fish_intel_mvp")
if MVP_DIR not in sys.path:
    sys.path.insert(0, MVP_DIR)

from common.db import get_conn  # noqa: E402

# ── Flask app ────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ── 任务管理（内存中）──────────────────────────────────────────────────
_tasks: dict[str, dict] = {}


def _serialise_row(row: dict) -> dict:
    """将一行数据库结果中的不可 JSON 序列化类型转换为字符串/数字。"""
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(v, timedelta):
            out[k] = str(v)
        elif isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, bytes):
            out[k] = v.decode("utf-8", errors="replace")
        else:
            out[k] = v
    return out


# ── 后台爬虫线程 ──────────────────────────────────────────────────────
def _run_crawler_thread(task_id: str, crawler_name: str, keyword: str, pages: int):
    """在后台线程中执行指定爬虫。"""
    task = _tasks[task_id]
    task["status"] = "running"
    task["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = None
    try:
        conn = get_conn()

        if crawler_name == "cnki":
            os.environ["CNKI_THEME"] = keyword
            os.environ["CNKI_PAPERS"] = str(max(1, pages * 10))
            os.environ["CNKI_HEADLESS"] = "0"          # 需要手动滑块验证，不能无头
            from jobs.crawl_cnki import run as run_cnki
            count = run_cnki(conn)

        elif crawler_name == "jd":
            from jobs.crawl_jd import run as run_jd
            count = run_jd(conn, keywords=[keyword], pages=pages)

        elif crawler_name == "taobao":
            from jobs.crawl_taobao import run as run_taobao
            count = run_taobao(conn, keywords=[keyword], pages=pages)

        elif crawler_name == "moa":
            os.environ["MOA_MAX_PAGES"] = str(pages)
            from jobs.crawl_moa_fishery import run as run_moa
            count = run_moa(conn)

        else:
            raise ValueError(f"未知爬虫: {crawler_name}")

        task["status"] = "done"
        task["result"] = f"采集完成，共获取 {count} 条数据"

    except Exception as exc:
        logger.exception("爬虫执行异常: %s", exc)
        task["status"] = "error"
        task["result"] = str(exc)
    finally:
        task["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════
#                              路  由
# ══════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


# ── 爬虫相关 ──────────────────────────────────────────────────────────

@app.route("/api/crawl", methods=["POST"])
def start_crawl():
    """启动爬虫任务（异步后台线程）。"""
    data = request.get_json(force=True)
    crawler = data.get("crawler", "").strip()
    keyword = data.get("keyword", "").strip()
    pages = int(data.get("pages", 1))

    if not crawler:
        return jsonify({"error": "请选择一个爬虫"}), 400
    if not keyword and crawler != "moa":
        return jsonify({"error": "请输入关键词"}), 400

    task_id = uuid.uuid4().hex[:8]
    _tasks[task_id] = {
        "id": task_id,
        "crawler": crawler,
        "keyword": keyword,
        "pages": pages,
        "status": "pending",
        "result": None,
        "started_at": None,
        "finished_at": None,
    }

    t = threading.Thread(
        target=_run_crawler_thread,
        args=(task_id, crawler, keyword, pages),
        daemon=True,
    )
    t.start()
    return jsonify({"task_id": task_id, "message": "任务已启动"})


@app.route("/api/task/<task_id>")
def task_status(task_id: str):
    """查询任务状态。"""
    task = _tasks.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(task)


# ── 数据查询 ──────────────────────────────────────────────────────────

@app.route("/api/query/papers")
def query_papers():
    keyword = request.args.get("keyword", "").strip()
    limit = min(int(request.args.get("limit", 100)), 500)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if keyword:
                sql = """
                    SELECT id, theme, title, authors, institute, source, pub_date,
                           abstract, keywords_json, url, fetched_at
                    FROM paper_meta
                    WHERE title LIKE %s OR abstract LIKE %s OR keywords_json LIKE %s
                    ORDER BY fetched_at DESC LIMIT %s
                """
                like = f"%{keyword}%"
                cur.execute(sql, (like, like, like, limit))
            else:
                sql = """
                    SELECT id, theme, title, authors, institute, source, pub_date,
                           abstract, keywords_json, url, fetched_at
                    FROM paper_meta ORDER BY fetched_at DESC LIMIT %s
                """
                cur.execute(sql, (limit,))
            return jsonify({"count": len(rows := [_serialise_row(r) for r in cur.fetchall()]),
                            "data": rows})
    finally:
        conn.close()


@app.route("/api/query/products")
def query_products():
    keyword = request.args.get("keyword", "").strip()
    platform = request.args.get("platform", "").strip()
    limit = min(int(request.args.get("limit", 100)), 500)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            conds, params = [], []
            if keyword:
                conds.append("(title LIKE %s OR keyword LIKE %s)")
                like = f"%{keyword}%"
                params += [like, like]
            if platform:
                conds.append("platform = %s")
                params.append(platform)
            where = ("WHERE " + " AND ".join(conds)) if conds else ""
            sql = f"""
                SELECT id, platform, keyword, title, price, original_price,
                       sales_or_commit, shop, province, city, detail_url, snapshot_time
                FROM product_snapshot {where}
                ORDER BY snapshot_time DESC LIMIT %s
            """
            params.append(limit)
            cur.execute(sql, params)
            return jsonify({"count": len(rows := [_serialise_row(r) for r in cur.fetchall()]),
                            "data": rows})
    finally:
        conn.close()


@app.route("/api/query/intel")
def query_intel():
    keyword = request.args.get("keyword", "").strip()
    limit = min(int(request.args.get("limit", 100)), 500)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if keyword:
                sql = """
                    SELECT id, source_type, title, pub_time, org, region,
                           content, source_url, tags_json, fetched_at
                    FROM intel_item
                    WHERE title LIKE %s OR content LIKE %s
                    ORDER BY fetched_at DESC LIMIT %s
                """
                like = f"%{keyword}%"
                cur.execute(sql, (like, like, limit))
            else:
                sql = """
                    SELECT id, source_type, title, pub_time, org, region,
                           content, source_url, tags_json, fetched_at
                    FROM intel_item ORDER BY fetched_at DESC LIMIT %s
                """
                cur.execute(sql, (limit,))
            return jsonify({"count": len(rows := [_serialise_row(r) for r in cur.fetchall()]),
                            "data": rows})
    finally:
        conn.close()


@app.route("/api/stats")
def stats():
    """各表数据量统计。"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            result = {}
            for table in ("paper_meta", "product_snapshot", "intel_item", "raw_event"):
                try:
                    cur.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
                    result[table] = cur.fetchone()["cnt"]
                except Exception:
                    result[table] = 0
            return jsonify(result)
    finally:
        conn.close()


# ── 启动 ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # use_reloader=False: 防止 watchdog 检测到 playwright 等第三方库变化时自动重启，导致任务丢失
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
