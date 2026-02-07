import sys
import traceback

from common.db import finish_crawl_run, get_conn, insert_crawl_run
from jobs.crawl_bj_form import run as run_bj
from jobs.crawl_cnki import run as run_cnki
from jobs.crawl_jd import run as run_jd
from jobs.crawl_moa_fishery import run as run_moa
from jobs.crawl_taobao import run as run_taobao

JOB_MAP = {
    "jd": run_jd,
    "taobao": run_taobao,
    "moa": run_moa,
    "cnki": run_cnki,
    "bjform": run_bj,
}


if __name__ == "__main__":
    job = sys.argv[1] if len(sys.argv) > 1 else "jd"
    if job not in JOB_MAP:
        print(f"[FAIL] unknown job={job}, allowed={','.join(JOB_MAP.keys())}")
        raise SystemExit(2)

    conn = get_conn()
    run_id = insert_crawl_run(conn, job)
    try:
        items = JOB_MAP[job](conn)
        finish_crawl_run(conn, run_id, "SUCCESS", items=items)
        print(f"[OK] {job} items={items}")
    except Exception as exc:
        finish_crawl_run(
            conn,
            run_id,
            "FAIL",
            items=0,
            error_text=str(exc) + "\n" + traceback.format_exc(),
        )
        print(f"[FAIL] {job} err={exc}")
        raise
    finally:
        conn.close()
