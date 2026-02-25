"""检查实际数据库表结构。"""

from fish_intel_mvp.common.db import get_conn

conn = get_conn()
cur = conn.cursor()

# 查看 product_snapshot 表结构
cur.execute("DESCRIBE product_snapshot")
columns = cur.fetchall()

print("=== product_snapshot 表结构 ===")
for col in columns:
    print(f"{col['Field']:40s} {col['Type']:30s} {col['Null']:5s} {col['Key']:5s}")

conn.close()
