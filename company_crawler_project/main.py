import argparse
import json
import logging
from collections import Counter
from typing import Any

from runner import run_from_config


def _parse_set_pairs(values: list[str]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for pair in values:
        if "=" not in pair:
            raise ValueError(f"Invalid --set value: {pair}. Expected key=value")
        key, raw = pair.split("=", 1)
        key = key.strip()
        raw = raw.strip()
        if not key:
            raise ValueError(f"Invalid --set key in: {pair}")

        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        overrides[key] = value
    return overrides


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified aquaculture crawler project for company delivery."
    )
    parser.add_argument(
        "--config",
        default="config/sources.json",
        help="Path to source config JSON. Default: config/sources.json",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Only run selected source id. Repeat this option for multiple sources.",
    )
    parser.add_argument(
        "--set",
        dest="set_values",
        action="append",
        default=[],
        help='Override config param by key=value, e.g. --set cnki.theme="aquaculture".',
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Collect only and skip DB write.",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=5,
        help="Print first N item titles after collection. Default: 5",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    overrides = _parse_set_pairs(args.set_values)
    items = run_from_config(
        config_path=args.config,
        source_ids=args.source,
        overrides=overrides,
        save_to_db=not args.no_save,
    )

    source_counter = Counter(it.get("source_type", "UNKNOWN") for it in items)
    print(f"Total collected items: {len(items)}")
    for source_type, count in sorted(source_counter.items()):
        print(f"  - {source_type}: {count}")

    if args.preview > 0 and items:
        print(f"\nPreview (first {min(args.preview, len(items))}):")
        for idx, item in enumerate(items[: args.preview], start=1):
            pub_time = item.get("pub_time", "")
            title = item.get("title", "")
            url = item.get("source_url", "")
            print(f"{idx}. {pub_time} | {title}")
            print(f"   {url}")


if __name__ == "__main__":
    main()

