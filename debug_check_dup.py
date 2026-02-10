from storage.db import DB_PATH, get_conn

if __name__ == "__main__":
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM intel_item")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT source_url) FROM intel_item")
    distinct_url = cur.fetchone()[0]

    conn.close()

    print("数据库路径：", DB_PATH)
    print("总记录数：", total)
    print("按 source_url 去重后条数：", distinct_url)
