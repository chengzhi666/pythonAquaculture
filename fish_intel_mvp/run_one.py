import logging
import sys
import traceback

logger = logging.getLogger(__name__)

from common.db import finish_crawl_run, get_conn, insert_crawl_run
from jobs.crawl_cnki import run as run_cnki
from jobs.crawl_jd import run as run_jd
from jobs.crawl_moa_fishery import run as run_moa
from jobs.crawl_salmon import crawl_jd_salmon, crawl_taobao_salmon, run as run_salmon
from jobs.crawl_taobao import run as run_taobao

JOB_MAP = {
    "jd": run_jd,
    "taobao": run_taobao,
    "jd_salmon": crawl_jd_salmon,
    "taobao_salmon": crawl_taobao_salmon,
    "salmon": run_salmon,
    "moa": run_moa,
    "cnki": run_cnki,
}


if __name__ == "__main__":
    job = sys.argv[1] if len(sys.argv) > 1 else "jd"
    if job not in JOB_MAP:
        logger.error("[FAIL] unknown job=%s, allowed=%s", job, ",".join(JOB_MAP.keys()))
        raise SystemExit(2)

    conn = get_conn()
    run_id = insert_crawl_run(conn, job)
    try:
        items = JOB_MAP[job](conn)
        finish_crawl_run(conn, run_id, "SUCCESS", items=items)
        logger.info("[OK] %s items=%s", job, items)
    except Exception as exc:
        finish_crawl_run(
            conn,
            run_id,
            "FAIL",
            items=0,
            error_text=str(exc) + "\n" + traceback.format_exc(),
        )
        logger.error("[FAIL] %s err=%s", job, exc)
        raise
    finally:
        conn.close()
