"""
MinerU vs Baseline 对比实验脚本
对应论文 5.3 节表格（可用率、噪声率、耗时对比）

用法：
    python run_mineru_comparison.py
    python run_mineru_comparison.py --pdf-dir ./test_pdfs/30_papers --output ./results

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
    parse_pdf_with_mineru,
    parse_with_pymupdf,
    parse_with_pdfplumber,
    parse_cnki_txt,
    evaluate_availability,
)

METHODS = ["mineru", "pymupdf", "pdfplumber", "cnki_txt"]
AVAILABILITY_THRESHOLD = 0.85


# ---------------------------------------------------------------------------
# 文件发现
# ---------------------------------------------------------------------------

def discover_pdfs(pdf_dir: Path) -> list[Path]:
    """递归查找目录下所有 PDF 文件。"""
    pdfs = sorted(pdf_dir.glob("**/*.pdf"))
    if not pdfs:
        # 如果没有真实 PDF，生成 30 个占位路径用于演示
        print(f"[WARN] {pdf_dir} 中未找到 PDF，使用占位路径（STUB 模式）")
        pdfs = [Path(f"stub_paper_{i:02d}.pdf") for i in range(1, 31)]
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
) -> list[dict]:
    """对单篇 PDF 运行所有方法，返回各方法的评估结果行。"""
    rows = []
    pdf_str = str(pdf_path)

    parsers = {
        "mineru": lambda: parse_pdf_with_mineru(pdf_str),
        "pymupdf": lambda: parse_with_pymupdf(pdf_str),
        "pdfplumber": lambda: parse_with_pdfplumber(pdf_str),
    }

    # CNKI TXT（如果有对应文件）
    if cnki_dir:
        txt_path = find_cnki_txt(pdf_path, cnki_dir)
        if txt_path:
            parsers["cnki_txt"] = lambda p=txt_path: parse_cnki_txt(str(p))

    for method, parser_fn in parsers.items():
        result: ParseResult = parser_fn()
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

    return rows


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
    print("\n" + "=" * 70)
    print("表 5-x  各方法全文解析可用率对比")
    print("=" * 70)
    header = f"{'方法':<15} {'篇数':>6} {'可用篇数':>8} {'可用率':>8} {'噪声率':>8} {'平均耗时(s)':>12}"
    print(header)
    print("-" * 70)
    for method, stats in summary.items():
        print(
            f"{method:<15} "
            f"{stats['total_papers']:>6} "
            f"{stats['available_papers']:>8} "
            f"{stats['availability_rate']:>8.1%} "
            f"{stats['avg_noise_rate']:>8.1%} "
            f"{stats['avg_parse_time_s']:>12.3f}"
        )
    print("=" * 70)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="MinerU vs Baseline 对比实验")
    parser.add_argument(
        "--pdf-dir",
        default="./test_pdfs/30_papers",
        help="30 篇测试 PDF 所在目录（默认 ./test_pdfs/30_papers）",
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
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    cnki_dir = Path(args.cnki_dir) if Path(args.cnki_dir).exists() else None
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = discover_pdfs(pdf_dir)
    print(f"找到 {len(pdfs)} 篇 PDF，开始对比实验...\n")

    all_rows: list[dict] = []

    for i, pdf_path in enumerate(pdfs, 1):
        print(f"[{i:02d}/{len(pdfs)}] {pdf_path.name}")
        rows = compare_one(pdf_path, cnki_dir)
        all_rows.extend(rows)

        # 保存 MinerU 的 Markdown 输出（供 SFT 使用）
        mineru_result = parse_pdf_with_mineru(str(pdf_path))
        if not mineru_result.error:
            save_markdown(pdf_path, mineru_result, output_dir)

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
    mineru_stats = summary.get("mineru", {})
    available = mineru_stats.get("available_papers", 0)
    total = mineru_stats.get("total_papers", len(pdfs))
    print(f"\nMinerU 可用率：{available}/{total} = {available/total:.1%}（论文目标：96.7%）")
    md_dir = output_dir / "markdown"
    md_count = len(list(md_dir.glob("*.md"))) if md_dir.exists() else 0
    print(f"已生成 Markdown 文件：{md_count} 篇（保存在 {md_dir}，供 SFT 使用）")


if __name__ == "__main__":
    main()
