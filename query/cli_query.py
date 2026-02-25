from typing import Any, cast

import storage.db as storage_db  # 放在文件最上面
from storage.db import DB_PATH

QueryRow = tuple[str, str, str, str, str, str]


def query_intel(keyword: str = "", order_by: str = "time") -> list[QueryRow]:
    backend = storage_db.get_backend()
    if backend == "mysql":
        return _query_mysql(keyword=keyword, order_by=order_by)
    return _query_sqlite(keyword=keyword, order_by=order_by)


def _query_sqlite(keyword: str, order_by: str) -> list[QueryRow]:
    conn = storage_db.get_conn()
    try:
        cur = conn.cursor()

        sql = "SELECT pub_time, region, org, title, source_type, source_url FROM intel_item"
        params: list[str] = []

        if keyword:
            sql += " WHERE title LIKE ? OR content LIKE ?"
            kw = f"%{keyword}%"
            params.extend([kw, kw])

        if order_by == "time":
            sql += " ORDER BY pub_time_norm DESC, created_at DESC, pub_time DESC"
        elif order_by == "org_time":
            sql += " ORDER BY org, pub_time_norm DESC, created_at DESC, pub_time DESC"
        elif order_by == "region_time":
            sql += " ORDER BY region, pub_time_norm DESC, created_at DESC, pub_time DESC"
        else:
            sql += " ORDER BY pub_time_norm DESC, created_at DESC, pub_time DESC"

        cur.execute(sql, params)
        rows = cast(list[QueryRow], cur.fetchall())
        return rows
    finally:
        conn.close()


def _query_mysql(keyword: str, order_by: str) -> list[QueryRow]:
    conn = storage_db.get_conn()
    try:
        cur = conn.cursor()

        sql = "SELECT pub_time, region, org, title, source_type, source_url FROM intel_item"
        params: list[str] = []

        if keyword:
            sql += " WHERE title LIKE %s OR content LIKE %s"
            kw = f"%{keyword}%"
            params.extend([kw, kw])

        time_expr = (
            "COALESCE("
            "STR_TO_DATE(pub_time, '%Y-%m-%d %H:%i:%s'),"
            "STR_TO_DATE(pub_time, '%Y-%m-%d'),"
            "STR_TO_DATE(REPLACE(REPLACE(REPLACE(pub_time, '年', '-'), '月', '-'), '日', ''), '%Y-%m-%d')"
            ")"
        )

        if order_by == "time":
            sql += f" ORDER BY {time_expr} DESC, fetched_at DESC, pub_time DESC"
        elif order_by == "org_time":
            sql += f" ORDER BY org, {time_expr} DESC, fetched_at DESC, pub_time DESC"
        elif order_by == "region_time":
            sql += f" ORDER BY region, {time_expr} DESC, fetched_at DESC, pub_time DESC"
        else:
            sql += f" ORDER BY {time_expr} DESC, fetched_at DESC, pub_time DESC"

        cur.execute(sql, params)
        rows_raw = cast(list[dict[str, Any]], cur.fetchall())

        return [
            (
                str(row.get("pub_time") or ""),
                str(row.get("region") or ""),
                str(row.get("org") or ""),
                str(row.get("title") or ""),
                str(row.get("source_type") or ""),
                str(row.get("source_url") or ""),
            )
            for row in rows_raw
        ]
    finally:
        conn.close()


if __name__ == "__main__":
    print("=== 情报查询（命令行版） ===")
    kw = input("请输入关键词（回车表示不筛选）：").strip()
    print("排序方式：1=按时间  2=按单位+时间  3=按区域+时间")
    mode = input("请输入数字选择排序方式：").strip()

    order_by = "time"
    if mode == "2":
        order_by = "org_time"
    elif mode == "3":
        order_by = "region_time"

    results = query_intel(keyword=kw, order_by=order_by)
    print(f"共查询到 {len(results)} 条，展示前 20 条：\n")

    for i, (pub_time, region, org, title, source_type, url) in enumerate(results[:20], start=1):
        print(f"[{i}] {pub_time} | {region} | {org} | {source_type}")
        print(f"     {title}")
        print(f"     {url}")
        print("-" * 80)

    if storage_db.get_backend() == "mysql":
        print("当前存储后端：MySQL")
    else:
        print("当前数据库文件：", DB_PATH)
