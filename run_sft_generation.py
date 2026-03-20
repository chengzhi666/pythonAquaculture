"""
One-click SFT dataset generation script for thesis sections 4.6 and 5.4.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sft_generator import (
    TEMPLATE_LABELS,
    build_target_template_counts,
    compute_length_statistics,
    export_csv,
    export_jsonl,
    export_sharegpt,
    generate_sft_dataset,
    load_parsed_docs,
    report_to_dict,
    samples_to_rows,
)


def build_template_distribution_rows(total_samples: int, template_distribution: dict[str, int]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for template_type, count in sorted(
        template_distribution.items(),
        key=lambda item: item[0],
    ):
        rows.append(
            {
                "template_type": template_type,
                "template_label": TEMPLATE_LABELS.get(template_type, template_type),
                "count": count,
                "ratio": round(count / total_samples, 4) if total_samples else 0.0,
            }
        )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate SFT dataset from MinerU markdown and CNKI abstracts.")
    parser.add_argument(
        "--markdown-dir",
        action="append",
        default=[],
        help="Markdown directory produced by MinerU. Can be passed multiple times.",
    )
    parser.add_argument(
        "--cnki-path",
        action="append",
        default=[],
        help="CNKI TSV path. Can be passed multiple times.",
    )
    parser.add_argument(
        "--output-dir",
        default="results/sft_generation",
        help="Output directory for dataset and reports.",
    )
    parser.add_argument(
        "--total-samples",
        type=int,
        default=852,
        help="Target total sample count. Default matches thesis section 5.4.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    markdown_dirs = [Path(path) for path in args.markdown_dir] if args.markdown_dir else [Path("results/markdown")]
    cnki_paths = [Path(path) for path in args.cnki_path] if args.cnki_path else sorted(Path("fish_intel_mvp").glob("CNKI_*.tsv"))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    blocks = load_parsed_docs(markdown_dirs=markdown_dirs, cnki_paths=cnki_paths)
    if not blocks:
        raise SystemExit("No parsed documents found. Please provide Markdown output and/or CNKI TSV files.")

    template_counts = build_target_template_counts(args.total_samples)
    samples, report = generate_sft_dataset(blocks, template_counts=template_counts)

    dataset_jsonl = export_jsonl(samples, output_dir / "sft_dataset.jsonl")
    dataset_sharegpt = export_sharegpt(samples, output_dir / "sft_dataset_sharegpt.json")
    sample_rows = samples_to_rows(samples)
    export_csv(sample_rows, output_dir / "sft_dataset_samples.csv")

    template_rows = build_template_distribution_rows(len(samples), report.template_distribution)
    export_csv(template_rows, output_dir / "table_5_14_template_distribution.csv")

    length_rows = compute_length_statistics(samples)
    export_csv(length_rows, output_dir / "table_5_15_length_statistics.csv")

    automatic_metrics_path = output_dir / "automatic_metrics.json"
    automatic_metrics_path.write_text(
        json.dumps(report.auto_metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    generation_report_path = output_dir / "generation_report.json"
    generation_report_path.write_text(
        json.dumps(report_to_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    source_summary = {
        "markdown_dirs": [str(path) for path in markdown_dirs],
        "cnki_paths": [str(path) for path in cnki_paths],
        "block_count": len(blocks),
        "requested_total_samples": args.total_samples,
        "actual_total_samples": len(samples),
        "jsonl_path": str(dataset_jsonl),
        "sharegpt_path": str(dataset_sharegpt),
    }
    (output_dir / "source_summary.json").write_text(
        json.dumps(source_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Loaded blocks: {len(blocks)}")
    print(f"Generated samples: {len(samples)}")
    print(f"JSONL: {dataset_jsonl}")
    print(f"ShareGPT: {dataset_sharegpt}")
    print(f"Template stats: {output_dir / 'table_5_14_template_distribution.csv'}")
    print(f"Length stats: {output_dir / 'table_5_15_length_statistics.csv'}")
    print(f"Auto metrics: {automatic_metrics_path}")


if __name__ == "__main__":
    main()
