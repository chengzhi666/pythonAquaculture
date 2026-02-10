import importlib
import json
from typing import Any, Optional

from storage.db import init_db, save_items


def _import_func(module_name: str, func_name: str):
    mod = importlib.import_module(module_name)
    fn = getattr(mod, func_name)
    return fn


def _normalize_items(items: list[dict], defaults: dict[str, Any]) -> list[dict]:
    """
    给 item 补默认字段，且过滤掉没有 source_url 的条目（否则无法入库去重）
    """
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue

        # 补默认字段
        for k, v in (defaults or {}).items():
            if not it.get(k):
                it[k] = v

        # 没有 url 直接丢弃（你的表里 source_url UNIQUE，必须有）
        if not it.get("source_url"):
            continue

        out.append(it)
    return out


def run_from_config(
    config_path: str = "config/sites.json",
    overrides: Optional[dict[str, Any]] = None,
    save_to_db: bool = True,
) -> list[dict]:
    overrides = overrides or {}
    init_db()

    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)

    all_items: list[dict] = []
    stats: dict[str, int] = {}

    for src in cfg.get("sources", []):
        if not src.get("enabled", False):
            continue

        sid = src.get("id")
        module_name = src.get("module")
        func_name = src.get("function")
        params = dict(src.get("params", {}))
        defaults = dict(src.get("defaults", {}))

        # 覆盖参数
        for k, v in overrides.items():
            prefix = f"{sid}."
            if k.startswith(prefix):
                p = k[len(prefix) :]
                params[p] = v

        print(f"[RUN] {sid} {module_name}.{func_name} params={params}")

        fn = _import_func(module_name, func_name)
        items = fn(**params)
        items = _normalize_items(items, defaults)

        stats[sid] = len(items)  # 记录每个源成功条数
        all_items.extend(items)

        if save_to_db:
            save_items(items)

    # 打印统计
    total = sum(stats.values())
    print("采集统计：")
    for sid, n in stats.items():
        print(f"  - {sid}: {n} 条")
    print(f"全部采集完成：{total} 条")

    return all_items
