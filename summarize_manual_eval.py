"""
Summarize real manual-evaluation scores from a sampled workbook.

Usage:
    python summarize_manual_eval.py --input results/.../manual_eval_100_samples.xlsx
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from openpyxl import load_workbook


REQUIRED_SCORE_FIELDS = ("fact_correctness", "logic_coherence", "completeness")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize manual evaluation workbook scores.")
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the XLSX workbook produced by manual_eval_sampler.py.",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional output JSON path. Defaults to <input>_summary.json",
    )
    return parser.parse_args()


def to_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    workbook = load_workbook(input_path)
    sheet = workbook.active

    headers = [cell.value for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
    header_index = {str(name): idx for idx, name in enumerate(headers)}

    missing_headers = [field for field in REQUIRED_SCORE_FIELDS if field not in header_index]
    if missing_headers:
        raise SystemExit(f"Workbook is missing required columns: {missing_headers}")

    rows = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        payload = {str(headers[idx]): row[idx] for idx in range(len(headers))}
        fact = to_float(payload.get("fact_correctness"))
        logic = to_float(payload.get("logic_coherence"))
        completeness = to_float(payload.get("completeness"))
        if None in (fact, logic, completeness):
            continue
        overall = round((fact + logic + completeness) / 3, 4)
        rows.append(
            {
                "sample_no": payload.get("sample_no"),
                "fact_correctness": fact,
                "logic_coherence": logic,
                "completeness": completeness,
                "overall_score": overall,
            }
        )

    if not rows:
        raise SystemExit("No completed score rows found in workbook.")

    summary = {
        "input_path": str(input_path),
        "completed_rows": len(rows),
        "fact_correctness_avg": round(sum(row["fact_correctness"] for row in rows) / len(rows), 4),
        "logic_coherence_avg": round(sum(row["logic_coherence"] for row in rows) / len(rows), 4),
        "completeness_avg": round(sum(row["completeness"] for row in rows) / len(rows), 4),
        "overall_avg": round(sum(row["overall_score"] for row in rows) / len(rows), 4),
    }

    output_json = Path(args.output_json) if args.output_json else input_path.with_name(f"{input_path.stem}_summary.json")
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Completed rows: {summary['completed_rows']}")
    print(f"Overall average: {summary['overall_avg']}")
    print(f"Summary JSON: {output_json}")


if __name__ == "__main__":
    main()
