import importlib
import json
import logging
from typing import Any, Optional

from storage.db import init_db, save_items

logger = logging.getLogger(__name__)


def _import_func(module_name: str, func_name: str):
    mod = importlib.import_module(module_name)
    fn = getattr(mod, func_name, None)
    if fn is None or not callable(fn):
        raise AttributeError(f"function not found or not callable: {module_name}.{func_name}")
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
    success_stats: dict[str, int] = {}
    failed_stats: dict[str, str] = {}

    for src in cfg.get("sources", []):
        if not src.get("enabled", False):
            continue

        sid = str(src.get("id") or "<unknown>")
        module_name = src.get("module")
        func_name = src.get("function")
        params = dict(src.get("params", {}))
        defaults = dict(src.get("defaults", {}))

        try:
            if not module_name or not func_name:
                raise ValueError(f"invalid source config: id={sid}, module/function is required")

            # 覆盖参数
            for k, v in overrides.items():
                prefix = f"{sid}."
                if k.startswith(prefix):
                    p = k[len(prefix) :]
                    params[p] = v

            logger.info("[RUN] %s %s.%s params=%s", sid, module_name, func_name, params)

            fn = _import_func(module_name, func_name)
            raw_items = fn(**params)
            if not isinstance(raw_items, list):
                logger.warning("source returned non-list, sid=%s type=%s", sid, type(raw_items))
                raw_items = []

            items = _normalize_items(raw_items, defaults)

            success_stats[sid] = len(items)  # 记录每个源成功条数
            all_items.extend(items)

            if save_to_db:
                save_items(items)

        except Exception as exc:
            failed_stats[sid] = str(exc)
            logger.exception("source failed and skipped: sid=%s", sid)
            logger.error("[FAIL] %s: %s", sid, exc)
            continue

    # 打印统计
    total = sum(success_stats.values())
    logger.info("采集统计：")
    for sid, n in success_stats.items():
        logger.info("  - %s: %d 条", sid, n)
    if failed_stats:
        logger.warning("失败统计：")
        for sid, err in failed_stats.items():
            logger.warning("  - %s: %s", sid, err)
    logger.info("全部采集完成：%d 条", total)

    return all_items
