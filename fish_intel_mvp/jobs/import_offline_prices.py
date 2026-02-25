"""CSV 批量导入 → offline_price_snapshot 表.

用法:
  # 导入单文件
  python fish_intel_mvp/jobs/import_offline_prices.py price_offline_moa_20260225.csv

  # 导入目录下所有 price_offline_*.csv
  python fish_intel_mvp/jobs/import_offline_prices.py data/

  # 导出爬虫结果为 CSV（供人工检查后再导入）
  python fish_intel_mvp/jobs/import_offline_prices.py --export-from-raw moa_wholesale_price

设计原则:
  - 新增文件，不改动任何已有模块接口。
  - CSV 作为中间格式方便人工检查。
  - 字段映射 + 数据校验，跳过校验失败的行并记录告警。
"""

import csv
import glob
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TextIO

try:
    from common.db import get_conn, insert_raw_event
    from common.logger import get_logger
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from common.db import get_conn, insert_raw_event
    from common.logger import get_logger

LOGGER = get_logger(__name__)

SOURCE_NAME_DEFAULT = "csv_offline_import"

# ---------------------------------------------------------------------------
# CSV 列名映射 — 支持中英文表头
# ---------------------------------------------------------------------------

_COLUMN_ALIASES: dict[str, list[str]] = {
    "source_name": ["source_name", "数据来源", "来源", "source"],
    "market_name": ["market_name", "市场", "批发市场", "market"],
    "region": ["region", "地区", "区域"],
    "product_type": ["product_type", "品种", "品类标识", "type"],
    "product_name_raw": [
        "product_name_raw",
        "品名",
        "原始品名",
        "product_name",
        "品种名称",
        "prodName",
        "name",
    ],
    "spec": ["spec", "规格", "specification"],
    "min_price": ["min_price", "最低价", "最低", "minPrice"],
    "max_price": ["max_price", "最高价", "最高", "maxPrice"],
    "price": ["price", "均价", "价格", "avg_price", "avgPrice"],
    "unit": ["unit", "单位", "价格单位"],
    "storage_method": ["storage_method", "存储方式", "冷藏方式", "storage"],
    "date_str": ["date_str", "日期", "报价日期", "date", "reportDate"],
    "remark": ["remark", "备注", "说明", "note"],
    "snapshot_time": ["snapshot_time", "采集时间", "快照时间"],
}


def _build_header_map(headers: list[str]) -> dict[str, int]:
    """将 CSV 表头映射到标准字段名, 返回 {field_name: column_index}."""
    cleaned = [h.strip().strip("\ufeff") for h in headers]  # strip BOM
    mapping: dict[str, int] = {}
    for field, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            alias_lower = alias.lower()
            for idx, h in enumerate(cleaned):
                if h.lower() == alias_lower:
                    mapping[field] = idx
                    break
            if field in mapping:
                break
    return mapping


# ---------------------------------------------------------------------------
# 数据校验
# ---------------------------------------------------------------------------


def _clean(text: Optional[str]) -> str:
    return (text or "").replace("\u3000", " ").replace("\xa0", " ").strip()


def _parse_float(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    text = _clean(text).replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    if m:
        return float(m.group(0))
    return None


def _parse_datetime(text: Optional[str]) -> Optional[datetime]:
    """尝试多种日期格式解析."""
    text = _clean(text)
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


_STORAGE_FROZEN = re.compile(r"冷冻|冻品|速冻|frozen", re.IGNORECASE)
_STORAGE_ICE_FRESH = re.compile(r"冰鲜|ice.?fresh", re.IGNORECASE)
_STORAGE_FRESH = re.compile(r"鲜活|活鲜|活|鲜|fresh|live", re.IGNORECASE)


def _guess_storage(text: str) -> Optional[str]:
    if _STORAGE_FROZEN.search(text):
        return "frozen"
    if _STORAGE_ICE_FRESH.search(text):
        return "ice_fresh"
    if _STORAGE_FRESH.search(text):
        return "fresh"
    return None


def _infer_product_type(name: str) -> str:
    if re.search(r"帝王鲑|帝王三文鱼|king\s*salmon|chinook", name, re.IGNORECASE):
        return "king_salmon"
    if re.search(r"虹鳟|rainbow\s*trout", name, re.IGNORECASE):
        return "rainbow_trout"
    if re.search(r"三文鱼|salmon|鲑", name, re.IGNORECASE):
        return "salmon_generic"
    if re.search(r"鳟", name, re.IGNORECASE):
        return "trout_generic"
    return "aquatic_other"


class ValidationError:
    """单行校验错误."""

    def __init__(self, row_num: int, field: str, message: str):
        self.row_num = row_num
        self.field = field
        self.message = message

    def __repr__(self) -> str:
        return f"Row {self.row_num}: [{self.field}] {self.message}"


def validate_row(row: dict[str, Any], row_num: int) -> list[ValidationError]:
    """校验一行数据, 返回错误列表 (空列表 = 通过)."""
    errors: list[ValidationError] = []

    # 必须有品名
    if not _clean(row.get("product_name_raw")):
        errors.append(ValidationError(row_num, "product_name_raw", "品名为空"))

    # 必须有价格（均价 或 最低+最高）
    price = _parse_float(str(row.get("price", "")))
    min_p = _parse_float(str(row.get("min_price", "")))
    max_p = _parse_float(str(row.get("max_price", "")))
    if price is None and (min_p is None or max_p is None):
        errors.append(ValidationError(row_num, "price", "缺少均价且最低/最高价不完整"))

    # 价格合理性 (负数/极端值)
    for label, val in [("price", price), ("min_price", min_p), ("max_price", max_p)]:
        if val is not None and val < 0:
            errors.append(ValidationError(row_num, label, f"价格为负: {val}"))
        if val is not None and val > 100000:
            errors.append(ValidationError(row_num, label, f"价格异常高: {val}"))

    if min_p is not None and max_p is not None and min_p > max_p:
        errors.append(ValidationError(row_num, "min_price", f"最低价({min_p}) > 最高价({max_p})"))

    return errors


# ---------------------------------------------------------------------------
# CSV 行 → offline_price_snapshot dict
# ---------------------------------------------------------------------------


def row_to_snapshot(
    cells: list[str],
    header_map: dict[str, int],
    *,
    row_num: int,
    source_name: str = SOURCE_NAME_DEFAULT,
    fallback_snapshot_time: Optional[datetime] = None,
) -> tuple[Optional[dict[str, Any]], list[ValidationError]]:
    """解析一行 CSV 为 offline_price_snapshot 字典.

    Returns:
        (snapshot_dict, validation_errors)
        若 validation_errors 非空, snapshot_dict 为 None.
    """

    def _cell(field: str) -> str:
        idx = header_map.get(field)
        if idx is not None and idx < len(cells):
            return _clean(cells[idx])
        return ""

    product_name_raw = _cell("product_name_raw")
    price_str = _cell("price")
    min_price_str = _cell("min_price")
    max_price_str = _cell("max_price")
    market = _cell("market_name")
    region = _cell("region")
    spec = _cell("spec")
    unit = _cell("unit") or "元/公斤"
    storage = _cell("storage_method")
    date_str = _cell("date_str")
    remark = _cell("remark")
    src = _cell("source_name") or source_name
    product_type = _cell("product_type")
    snapshot_str = _cell("snapshot_time")

    # 构造 raw dict for validation
    raw = {
        "product_name_raw": product_name_raw,
        "price": price_str,
        "min_price": min_price_str,
        "max_price": max_price_str,
    }
    errors = validate_row(raw, row_num)
    if errors:
        return None, errors

    price = _parse_float(price_str)
    min_price = _parse_float(min_price_str)
    max_price = _parse_float(max_price_str)
    if price is None and min_price is not None and max_price is not None:
        price = round((min_price + max_price) / 2, 2)

    if not product_type:
        product_type = _infer_product_type(product_name_raw)

    if not storage:
        storage = _guess_storage(" ".join([product_name_raw, spec, remark]))

    snapshot_time = _parse_datetime(snapshot_str)
    if snapshot_time is None:
        snapshot_time = _parse_datetime(date_str)
    if snapshot_time is None:
        snapshot_time = fallback_snapshot_time or datetime.now()

    return {
        "source_name": src,
        "market_name": market,
        "region": region,
        "product_type": product_type,
        "product_name_raw": product_name_raw,
        "spec": spec,
        "min_price": min_price,
        "max_price": max_price,
        "price": price,
        "unit": unit,
        "storage_method": storage,
        "date_str": date_str,
        "remark": remark,
        "snapshot_time": snapshot_time,
    }, []


# ---------------------------------------------------------------------------
# upsert_offline_price_snapshot — 新增函数, 不改 db.py
# ---------------------------------------------------------------------------


def upsert_offline_price_snapshot(conn, item: dict[str, Any], raw_id: Optional[int] = None) -> None:
    """INSERT ... ON DUPLICATE KEY UPDATE into offline_price_snapshot."""
    sql = """
    INSERT INTO offline_price_snapshot(
      source_name, market_name, region, product_type, product_name_raw,
      spec, min_price, max_price, price, unit,
      storage_method, date_str, remark, snapshot_time, raw_id
    ) VALUES (
      %(source_name)s, %(market_name)s, %(region)s, %(product_type)s, %(product_name_raw)s,
      %(spec)s, %(min_price)s, %(max_price)s, %(price)s, %(unit)s,
      %(storage_method)s, %(date_str)s, %(remark)s, %(snapshot_time)s, %(raw_id)s
    )
    ON DUPLICATE KEY UPDATE
      product_name_raw=VALUES(product_name_raw),
      spec=VALUES(spec),
      min_price=VALUES(min_price),
      max_price=VALUES(max_price),
      price=VALUES(price),
      unit=VALUES(unit),
      storage_method=VALUES(storage_method),
      date_str=VALUES(date_str),
      remark=VALUES(remark),
      raw_id=VALUES(raw_id)
    """
    payload = {
        "source_name": item["source_name"],
        "market_name": item.get("market_name", ""),
        "region": item.get("region", ""),
        "product_type": item.get("product_type", ""),
        "product_name_raw": item.get("product_name_raw"),
        "spec": item.get("spec"),
        "min_price": item.get("min_price"),
        "max_price": item.get("max_price"),
        "price": item.get("price"),
        "unit": item.get("unit", "元/公斤"),
        "storage_method": item.get("storage_method"),
        "date_str": item.get("date_str"),
        "remark": item.get("remark"),
        "snapshot_time": item["snapshot_time"],
        "raw_id": raw_id,
    }
    with conn.cursor() as cur:
        cur.execute(sql, payload)


# ---------------------------------------------------------------------------
# CSV 解析入口
# ---------------------------------------------------------------------------


def parse_csv(
    fp: TextIO,
    *,
    source_name: str = SOURCE_NAME_DEFAULT,
    fallback_snapshot_time: Optional[datetime] = None,
) -> tuple[list[dict[str, Any]], list[ValidationError]]:
    """解析一个 CSV 文件对象, 返回 (valid_rows, all_errors)."""
    reader = csv.reader(fp)
    headers = next(reader, None)
    if not headers:
        return [], [ValidationError(0, "header", "CSV 无表头")]

    header_map = _build_header_map(headers)
    if "product_name_raw" not in header_map and "price" not in header_map:
        return [], [ValidationError(0, "header", "CSV 表头缺少品名和价格列")]

    valid: list[dict[str, Any]] = []
    errors: list[ValidationError] = []
    for row_num, cells in enumerate(reader, start=2):  # row 1 is header
        if not any(c.strip() for c in cells):
            continue  # skip blank rows
        snapshot, row_errors = row_to_snapshot(
            cells,
            header_map,
            row_num=row_num,
            source_name=source_name,
            fallback_snapshot_time=fallback_snapshot_time,
        )
        if row_errors:
            errors.extend(row_errors)
        if snapshot is not None:
            valid.append(snapshot)

    return valid, errors


def import_csv_file(
    conn,
    filepath: str,
    *,
    source_name: str = SOURCE_NAME_DEFAULT,
    dry_run: bool = False,
) -> dict[str, Any]:
    """导入一个 CSV 文件到 offline_price_snapshot.

    Returns:
        {"file": ..., "total": ..., "imported": ..., "skipped": ..., "errors": [...]}
    """
    filepath = str(filepath)
    LOGGER.info("import_offline start: file=%s dry_run=%s", filepath, dry_run)

    with open(filepath, encoding="utf-8-sig") as f:
        rows, errors = parse_csv(f, source_name=source_name)

    if errors:
        for e in errors:
            LOGGER.warning("import_offline validation: %s", e)

    imported = 0
    if not dry_run:
        for row in rows:
            try:
                raw_id = insert_raw_event(
                    conn,
                    source_name=source_name,
                    url=filepath,
                    title=row.get("product_name_raw", ""),
                    pub_time=row.get("date_str"),
                    raw_json=json.dumps(row, ensure_ascii=False, default=str),
                )
                upsert_offline_price_snapshot(conn, row, raw_id=raw_id)
                imported += 1
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "import_offline db write failed: product=%s err=%s",
                    row.get("product_name_raw"),
                    exc,
                )
                errors.append(
                    ValidationError(0, "db", f"DB写入失败: {row.get('product_name_raw')}: {exc}")
                )

    result = {
        "file": filepath,
        "total": len(rows) + len([e for e in errors if e.field != "db"]),
        "imported": imported,
        "skipped": len([e for e in errors if e.field != "db"]),
        "errors": [repr(e) for e in errors],
    }
    LOGGER.info(
        "import_offline done: file=%s imported=%s skipped=%s",
        filepath,
        imported,
        len(errors),
    )
    return result


def import_csv_dir(
    conn,
    dirpath: str,
    *,
    pattern: str = "price_offline_*.csv",
    source_name: str = SOURCE_NAME_DEFAULT,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """批量导入目录下匹配 pattern 的所有 CSV 文件."""
    search = os.path.join(dirpath, pattern)
    files = sorted(glob.glob(search))
    if not files:
        LOGGER.warning("import_offline: no files match %s", search)
        return []

    LOGGER.info("import_offline batch: %s files found", len(files))
    results: list[dict[str, Any]] = []
    for fp in files:
        result = import_csv_file(conn, fp, source_name=source_name, dry_run=dry_run)
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# 从 raw_event 导出为 CSV (供人工检查)
# ---------------------------------------------------------------------------


def export_raw_to_csv(
    conn,
    output_path: str,
    *,
    source_name: str = "moa_wholesale_price",
    limit: int = 1000,
) -> int:
    """把 raw_event 中指定来源的 raw_json 导出为 CSV 文件.

    方便人工检查后修正再导入。
    """
    sql = """
    SELECT id, source_name, url, title, pub_time, raw_json, fetched_at
    FROM raw_event
    WHERE source_name = %s
    ORDER BY id DESC
    LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (source_name, limit))
        rows = cur.fetchall() or []

    if not rows:
        LOGGER.info("export_raw: no raw_event rows for source=%s", source_name)
        return 0

    csv_headers = [
        "source_name",
        "market_name",
        "region",
        "product_type",
        "品名",
        "spec",
        "min_price",
        "max_price",
        "price",
        "unit",
        "storage_method",
        "日期",
        "remark",
        "snapshot_time",
        "raw_event_id",
    ]

    count = 0
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers)

        for row in rows:
            raw_json_str = row.get("raw_json") or "{}"
            try:
                data = json.loads(raw_json_str)
            except (json.JSONDecodeError, TypeError):
                continue

            parsed = data.get("parsed_row") or data.get("normalized") or data
            if not isinstance(parsed, dict):
                continue

            writer.writerow(
                [
                    parsed.get("source_name", source_name),
                    parsed.get("market_name", ""),
                    parsed.get("region", ""),
                    parsed.get("product_type", ""),
                    parsed.get(
                        "product_name", parsed.get("product_name_raw", row.get("title", ""))
                    ),
                    parsed.get("spec", ""),
                    parsed.get("min_price", ""),
                    parsed.get("max_price", ""),
                    parsed.get("avg_price", parsed.get("price", "")),
                    parsed.get("unit", "元/公斤"),
                    parsed.get("storage_method", ""),
                    parsed.get("date", parsed.get("date_str", row.get("pub_time", ""))),
                    parsed.get("remark", ""),
                    row.get("fetched_at", ""),
                    row.get("id", ""),
                ]
            )
            count += 1

    LOGGER.info("export_raw done: file=%s rows=%s", output_path, count)
    return count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli():
    import argparse

    parser = argparse.ArgumentParser(description="CSV ↔ offline_price_snapshot 导入导出")
    sub = parser.add_subparsers(dest="cmd")

    # import
    imp = sub.add_parser("import", help="导入 CSV 到 offline_price_snapshot")
    imp.add_argument("path", help="CSV 文件路径或目录路径")
    imp.add_argument("--source", default=SOURCE_NAME_DEFAULT, help="source_name 标识")
    imp.add_argument("--pattern", default="price_offline_*.csv", help="目录模式")
    imp.add_argument("--dry-run", action="store_true", help="仅校验不入库")

    # export
    exp = sub.add_parser("export", help="从 raw_event 导出 CSV")
    exp.add_argument("output", help="输出 CSV 文件路径")
    exp.add_argument("--source", default="moa_wholesale_price", help="raw_event.source_name")
    exp.add_argument("--limit", type=int, default=1000, help="最大导出行数")

    args = parser.parse_args()

    if args.cmd == "export":
        conn = get_conn()
        try:
            count = export_raw_to_csv(conn, args.output, source_name=args.source, limit=args.limit)
            print(f"[OK] exported {count} rows → {args.output}")
        finally:
            conn.close()

    elif args.cmd == "import":
        conn = get_conn()
        try:
            path = args.path
            if os.path.isdir(path):
                results = import_csv_dir(
                    conn, path, pattern=args.pattern, source_name=args.source, dry_run=args.dry_run
                )
                for r in results:
                    print(f"  {r['file']}: imported={r['imported']} skipped={r['skipped']}")
            else:
                result = import_csv_file(conn, path, source_name=args.source, dry_run=args.dry_run)
                print(
                    f"[OK] {result['file']}: imported={result['imported']} skipped={result['skipped']}"
                )
                if result["errors"]:
                    for e in result["errors"]:
                        print(f"  WARN: {e}")
        finally:
            conn.close()

    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
