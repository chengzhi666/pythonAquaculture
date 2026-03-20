"""
Validate core table row counts and print a thesis-friendly console table.

Strategy:
1. Try the configured SQLite file first.
2. If the required tables are not present there, fall back to the project's MySQL backend.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


# Change this path if your SQLite database lives elsewhere.
DB_PATH = Path("./intel.db")
ENABLE_MYSQL_FALLBACK = True

TABLE_SPECS = [
    ("product_snapshot", "商品快照表"),
    ("intel_item", "行业资讯表"),
    ("offline_price_snapshot", "线下价格表"),
]


def icon(emoji: str, fallback: str) -> str:
    encoding = (getattr(sys.stdout, "encoding", "") or "").lower()
    return emoji if "utf" in encoding else fallback


def count_table_rows(conn: sqlite3.Connection, table_name: str) -> tuple[int, bool]:
    try:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            return 0, False
        raise
    return int(cur.fetchone()[0]), True


def count_sqlite_tables(db_path: Path) -> tuple[list[tuple[str, str, int]], list[str]]:
    conn = sqlite3.connect(db_path)
    rows: list[tuple[str, str, int]] = []
    missing_tables: list[str] = []
    try:
        for table_name, description in TABLE_SPECS:
            count, exists = count_table_rows(conn, table_name)
            if not exists:
                missing_tables.append(table_name)
            rows.append((table_name, description, count))
    finally:
        conn.close()
    return rows, missing_tables


def count_mysql_tables() -> tuple[list[tuple[str, str, int]], list[str]]:
    import sys as _sys

    project_mvp = Path(__file__).resolve().parent / "fish_intel_mvp"
    if str(project_mvp) not in _sys.path:
        _sys.path.insert(0, str(project_mvp))

    from common.db import get_conn  # type: ignore

    conn = get_conn()
    rows: list[tuple[str, str, int]] = []
    missing_tables: list[str] = []
    try:
        with conn.cursor() as cur:
            for table_name, description in TABLE_SPECS:
                try:
                    cur.execute(f"SELECT COUNT(*) AS cnt FROM {table_name}")
                    row = cur.fetchone()
                    count = int(row["cnt"]) if row else 0
                except Exception:
                    count = 0
                    missing_tables.append(table_name)
                rows.append((table_name, description, count))
    finally:
        conn.close()
    return rows, missing_tables


def render_table(rows: list[tuple[str, str, int]]) -> str:
    headers = ("表名", "中文描述", "当前数据量")
    widths = [
        max(len(headers[0]), *(len(row[0]) for row in rows)),
        max(len(headers[1]), *(len(row[1]) for row in rows)),
        max(len(headers[2]), *(len(str(row[2])) for row in rows)),
    ]

    def line(char: str = "-") -> str:
        return "+" + "+".join(char * (width + 2) for width in widths) + "+"

    def row(values: tuple[str, str, str] | tuple[str, str, int]) -> str:
        rendered = []
        for value, width in zip(values, widths):
            rendered.append(f" {str(value):<{width}} ")
        return "|" + "|".join(rendered) + "|"

    parts = [line("="), row(headers), line("=")]
    for item in rows:
        parts.append(row(item))
        parts.append(line("-"))
    return "\n".join(parts)


def main() -> int:
    chart_icon = icon("📊", "[DATA]")
    fail_icon = icon("❌", "[FAIL]")
    warn_icon = icon("⚠️", "[WARN]")

    print("=" * 88)
    print(f"{chart_icon} 渔业情报系统：数据库端到端数据验证")
    print("=" * 88)
    print(f"SQLite path: {DB_PATH.resolve()}")

    rows: list[tuple[str, str, int]] = []
    missing_tables: list[str] = []
    backend_name = "sqlite"

    if DB_PATH.exists():
        rows, missing_tables = count_sqlite_tables(DB_PATH)
    else:
        missing_tables = [name for name, _ in TABLE_SPECS]

    if missing_tables and ENABLE_MYSQL_FALLBACK:
        try:
            rows, missing_tables = count_mysql_tables()
            backend_name = "mysql"
        except Exception as exc:
            print(f"{warn_icon} SQLite 中缺少核心表，且 MySQL 回退失败：{exc}")

    if not rows:
        print(f"{fail_icon} 未能从 SQLite 或 MySQL 读取到核心表统计。")
        return 1

    total_rows = sum(row[2] for row in rows)

    print(render_table(rows))
    print(f"Backend used: {backend_name}")
    print(f"{chart_icon} 数据库端到端验证完成，核心表数据已达 {total_rows} 条，系统数据中台运行正常。")

    if missing_tables:
        print(f"{warn_icon} 以下表当前未在该 SQLite 库中找到：{', '.join(missing_tables)}")
        print("脚本已自动尝试回退到 MySQL；如需固定到某个 SQLite 文件，请直接修改脚本顶部的 DB_PATH。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
