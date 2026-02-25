import importlib
import json
import logging
from pathlib import Path
from typing import Any, Optional

from storage.db import init_db, save_items

logger = logging.getLogger(__name__)


def _import_function(module_name: str, function_name: str):
    module = importlib.import_module(module_name)
    fn = getattr(module, function_name, None)
    if fn is None or not callable(fn):
        raise AttributeError(f"Invalid source function: {module_name}.{function_name}")
    return fn


def _normalize_items(items: Any, defaults: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return normalized

    for raw in items:
        if not isinstance(raw, dict):
            continue
        for key, value in defaults.items():
            if not raw.get(key):
                raw[key] = value
        if raw.get("source_url"):
            normalized.append(raw)
    return normalized


def _apply_overrides(
    source_id: str, params: dict[str, Any], overrides: Optional[dict[str, Any]]
) -> dict[str, Any]:
    updated = dict(params)
    for key, value in (overrides or {}).items():
        prefix = f"{source_id}."
        if key.startswith(prefix):
            param_name = key[len(prefix) :]
            updated[param_name] = value
    return updated


def run_from_config(
    config_path: str = "config/sources.json",
    source_ids: Optional[list[str]] = None,
    overrides: Optional[dict[str, Any]] = None,
    save_to_db: bool = True,
) -> list[dict[str, Any]]:
    config_file = Path(config_path)
    if not config_file.exists():
        config_file = Path(__file__).resolve().parent / config_path
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_file.open("r", encoding="utf-8") as f:
        config = json.load(f)

    selected = set(source_ids or [])
    all_items: list[dict[str, Any]] = []
    failed_sources: list[str] = []

    if save_to_db:
        init_db()

    for source in config.get("sources", []):
        source_id = str(source.get("id") or "")
        if not source_id:
            continue
        if selected and source_id not in selected:
            continue
        if not source.get("enabled", True):
            continue

        module_name = source.get("module")
        function_name = source.get("function")
        params = dict(source.get("params", {}))
        defaults = dict(source.get("defaults", {}))
        params = _apply_overrides(source_id, params, overrides)

        if not module_name or not function_name:
            logger.warning("Skip source without module/function: %s", source_id)
            continue

        try:
            logger.info(
                "Running source=%s module=%s function=%s params=%s",
                source_id,
                module_name,
                function_name,
                params,
            )
            fn = _import_function(module_name, function_name)
            raw_items = fn(**params)
            items = _normalize_items(raw_items, defaults)
            all_items.extend(items)

            if save_to_db:
                saved = save_items(items)
                logger.info("Saved %s items for source=%s", saved, source_id)

            logger.info("Collected %s items for source=%s", len(items), source_id)
        except Exception:
            failed_sources.append(source_id)
            logger.exception("Source failed: %s", source_id)
            continue

    if failed_sources:
        logger.warning("Failed sources: %s", ", ".join(failed_sources))

    return all_items
