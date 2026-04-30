"""
MinerU vs Baseline 对比实验脚本
对应论文 5.3 节表格（可用率、噪声率、耗时对比）

用法：
    python run_mineru_comparison.py
    python run_mineru_comparison.py --pdf-dir ./test_pdfs --output ./results

输出：
    results/comparison_table.csv   — 逐篇对比数据（供论文表 5-x）
    results/summary.json           — 汇总统计（可用率、噪声率、平均耗时）
    results/markdown/              — MinerU 解析的 30 篇 Markdown（供 SFT 使用）
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# 将项目根目录加入 path
sys.path.insert(0, str(Path(__file__).parent))

from mineru_parser import (
    ParseResult,
    AvailabilityReport,
    _apply_postprocessing,
    parse_pdf_with_mineru,
    parse_with_pymupdf,
    parse_with_pdfplumber,
    parse_cnki_txt,
    evaluate_availability,
)

DEFAULT_PDF_DIR = Path(__file__).resolve().parent / "test_pdfs"
METHODS = ["mineru_raw", "mineru_enhanced", "pymupdf", "pdfplumber", "cnki_txt"]
AVAILABILITY_THRESHOLD = 0.85


# ---------------------------------------------------------------------------
# 文件发现
# ---------------------------------------------------------------------------

def discover_pdfs(pdf_dir: Path) -> list[Path]:
    """递归查找目录下所有 PDF 文件。"""
    if not pdf_dir.exists():
        raise FileNotFoundError(f"PDF 目录不存在：{pdf_dir}")
    if not pdf_dir.is_dir():
        raise NotADirectoryError(f"PDF 路径不是目录：{pdf_dir}")

    pdfs = sorted(pdf_dir.glob("**/*.pdf"))
    if not pdfs:
        raise RuntimeError(f"PDF 目录中未找到任何 .pdf 文件：{pdf_dir}")
    return pdfs


def find_cnki_txt(pdf_path: Path, cnki_dir: Path) -> Path | None:
    """根据 PDF 文件名查找对应的 CNKI TXT 文件。"""
    stem = pdf_path.stem
    candidates = list(cnki_dir.glob(f"{stem}*.txt")) + list(cnki_dir.glob(f"*{stem}*.txt"))
    return candidates[0] if candidates else None


# ---------------------------------------------------------------------------
# 单篇对比
# ---------------------------------------------------------------------------

def compare_one(
    pdf_path: Path,
    cnki_dir: Path | None = None,
) -> tuple[list[dict], ParseResult | None]:
    """对单篇 PDF 运行所有方法，返回 (评估结果行列表, 增强版MinerU结果)。"""
    rows = []
    pdf_str = str(pdf_path)

    # MinerU 底层只跑一次；增强版只在 raw markdown 上执行规则后处理，方便 Ubuntu 现场演示。
    mineru_raw = parse_pdf_with_mineru(pdf_str, apply_postprocessing=False)
    if mineru_raw.error:
        mineru_enhanced = ParseResult(
            pdf_path=pdf_str,
            markdown="",
            layout_elements=[],
            parse_time_s=mineru_raw.parse_time_s,
            method="mineru",
            error=mineru_raw.error,
        )
    else:
        mineru_enhanced = ParseResult(
            pdf_path=pdf_str,
            markdown=_apply_postprocessing(mineru_raw.markdown),
            layout_elements=mineru_raw.layout_elements,
            parse_time_s=mineru_raw.parse_time_s,
            method="mineru",
        )

    parsers: list[tuple[str, ParseResult]] = [
        ("mineru_raw", mineru_raw),
        ("mineru_enhanced", mineru_enhanced),
        ("pymupdf", parse_with_pymupdf(pdf_str)),
        ("pdfplumber", parse_with_pdfplumber(pdf_str)),
    ]

    # CNKI TXT（如果有对应文件）
    if cnki_dir:
        txt_path = find_cnki_txt(pdf_path, cnki_dir)
        if txt_path:
            parsers.append(("cnki_txt", parse_cnki_txt(str(txt_path))))

    for method, result in parsers:
        if result.error:
            print(f"  [{method}] ERROR: {result.error}")
            report = AvailabilityReport(
                pdf_path=pdf_str, method=method,
                total_paragraphs=0, complete_paragraphs=0,
                noise_paragraphs=0, availability_rate=0.0,
                noise_rate=0.0, is_available=False,
            )
        else:
            report = evaluate_availability(
                result.markdown,
                pdf_path=pdf_str,
                method=method,
                availability_threshold=AVAILABILITY_THRESHOLD,
            )

        rows.append({
            "paper": pdf_path.name,
            "method": method,
            "total_paragraphs": report.total_paragraphs,
            "complete_paragraphs": report.complete_paragraphs,
            "noise_paragraphs": report.noise_paragraphs,
            "availability_rate": report.availability_rate,
            "noise_rate": report.noise_rate,
            "is_available": report.is_available,
            "parse_time_s": round(result.parse_time_s, 3),
            "error": result.error or "",
        })

    enhanced_ok = mineru_enhanced if not mineru_enhanced.error else None
    return rows, enhanced_ok


# ---------------------------------------------------------------------------
# 保存 Markdown 输出
# ---------------------------------------------------------------------------

def save_markdown(pdf_path: Path, result: ParseResult, output_dir: Path) -> None:
    """将 MinerU 解析结果保存为 Markdown 文件。"""
    md_dir = output_dir / "markdown"
    md_dir.mkdir(parents=True, exist_ok=True)
    out_path = md_dir / (pdf_path.stem + ".md")
    out_path.write_text(result.markdown, encoding="utf-8")


# ---------------------------------------------------------------------------
# 汇总统计
# ---------------------------------------------------------------------------

def compute_summary(all_rows: list[dict]) -> dict:
    """计算各方法的汇总统计（对应论文表 5-x）。"""
    from collections import defaultdict

    method_rows: dict[str, list[dict]] = defaultdict(list)
    for row in all_rows:
        method_rows[row["method"]].append(row)

    summary = {}
    for method, rows in method_rows.items():
        valid = [r for r in rows if not r["error"]]
        n = len(valid)
        if n == 0:
            continue
        available_count = sum(1 for r in valid if r["is_available"])
        summary[method] = {
            "total_papers": n,
            "available_papers": available_count,
            "availability_rate": round(available_count / n, 4) if n else 0,
            "avg_noise_rate": round(sum(r["noise_rate"] for r in valid) / n, 4),
            "avg_parse_time_s": round(sum(r["parse_time_s"] for r in valid) / n, 3),
        }

    return summary


def print_summary_table(summary: dict) -> None:
    """打印对比表格（论文 5.3 节格式）。"""
    print("\n" + "=" * 80)
    print("表 5-x  各方法全文解析可用率对比")
    print("=" * 80)
    header = f"{'方法':<18} {'篇数':>6} {'可用篇数':>8} {'可用率':>8} {'噪声率':>8} {'耗时(s)':>10} {'vs原始MinerU':>14}"
    print(header)
    print("-" * 80)
    raw_rate = summary.get("mineru_raw", {}).get("availability_rate", 0)
    for method, stats in summary.items():
        delta = stats['availability_rate'] - raw_rate
        delta_str = f"+{delta:.1%}" if delta > 0 else f"{delta:.1%}" if delta < 0 else "基线"
        print(
            f"{method:<18} "
            f"{stats['total_papers']:>6} "
            f"{stats['available_papers']:>8} "
            f"{stats['availability_rate']:>8.1%} "
            f"{stats['avg_noise_rate']:>8.1%} "
            f"{stats['avg_parse_time_s']:>10.3f} "
            f"{delta_str:>14}"
        )
    print("=" * 80)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="MinerU vs Baseline 对比实验")
    parser.add_argument(
        "--pdf-dir",
        default=str(DEFAULT_PDF_DIR),
        help=f"测试 PDF 所在目录（默认 {DEFAULT_PDF_DIR}）",
    )
    parser.add_argument(
        "--cnki-dir",
        default="./cnki_debug",
        help="CNKI TXT 导出文件目录（默认 ./cnki_debug）",
    )
    parser.add_argument(
        "--output",
        default="./results",
        help="结果输出目录（默认 ./results）",
    )
    parser.add_argument(
        "--max-pdfs",
        type=int,
        default=0,
        help="最多解析多少篇 PDF；0 表示全部（默认 0）",
    )
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir).expanduser().resolve()
    cnki_dir = Path(args.cnki_dir) if Path(args.cnki_dir).exists() else None
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = discover_pdfs(pdf_dir)
    if args.max_pdfs > 0:
        pdfs = pdfs[: args.max_pdfs]
    print(f"找到 {len(pdfs)} 篇 PDF，开始对比实验...\n")

    all_rows: list[dict] = []

    for i, pdf_path in enumerate(pdfs, 1):
        print(f"[{i:02d}/{len(pdfs)}] {pdf_path.name}")
        rows, enhanced_result = compare_one(pdf_path, cnki_dir)
        all_rows.extend(rows)

        # 保存增强版 MinerU 的 Markdown 输出（供 SFT 使用）
        if enhanced_result is not None:
            save_markdown(pdf_path, enhanced_result, output_dir)

    # 保存逐篇 CSV
    csv_path = output_dir / "comparison_table.csv"
    if all_rows:
        fieldnames = list(all_rows[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"\n逐篇数据已保存：{csv_path}")

    # 计算并打印汇总
    summary = compute_summary(all_rows)
    print_summary_table(summary)

    # 保存汇总 JSON
    summary_path = output_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"汇总统计已保存：{summary_path}")

    # 统计 MinerU 可用篇数
    # Prefer the postprocessed MinerU result in the final demo summary.
    mineru_stats = summary.get("mineru_enhanced") or summary.get("mineru_raw", {})
    available = mineru_stats.get("available_papers", 0)
    total = mineru_stats.get("total_papers", len(pdfs))
    print(f"\nMinerU 可用率：{available}/{total} = {available/total:.1%}（论文目标：96.7%）")
    md_dir = output_dir / "markdown"
    md_count = len(list(md_dir.glob("*.md"))) if md_dir.exists() else 0
    print(f"已生成 Markdown 文件：{md_count} 篇（保存在 {md_dir}，供 SFT 使用）")


if __name__ == "__main__":
    main()
