from typing import cast

from storage.db import DB_PATH, get_conn  # 放在文件最上面

QueryRow = tuple[str, str, str, str, str, str]


def query_intel(keyword: str = "", order_by: str = "time") -> list[QueryRow]:
    conn = get_conn()
    cur = conn.cursor()

    sql = "SELECT pub_time, region, org, title, source_type, source_url FROM intel_item"
    params: list[str] = []

    if keyword:
        sql += " WHERE title LIKE ? OR content LIKE ?"
        kw = f"%{keyword}%"
        params.extend([kw, kw])

    if order_by == "time":
        sql += " ORDER BY pub_time DESC"
    elif order_by == "org_time":
        sql += " ORDER BY org, pub_time DESC"
    elif order_by == "region_time":
        sql += " ORDER BY region, pub_time DESC"
    else:
        sql += " ORDER BY pub_time DESC"

    cur.execute(sql, params)
    rows = cast(list[QueryRow], cur.fetchall())
    conn.close()
    return rows


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

    print("当前数据库文件：", DB_PATH)
