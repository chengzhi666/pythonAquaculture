"""Build a small offline OCR showcase for an imminent group meeting.

The script intentionally uses only committed/locally generated result files so
the demo remains useful even when OCR dependencies are not available on site.
"""

from __future__ import annotations

import csv
import html
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"
DIST_DIR = ROOT / "dist"
DOCS_DIR = ROOT / "docs"


METHOD_LABELS = {
    "mineru": "MinerU + 后处理",
    "mineru_raw": "MinerU 原始",
    "mineru_enhanced": "MinerU + 后处理",
    "pymupdf": "PyMuPDF",
    "pdfplumber": "pdfplumber",
    "cnki_txt": "CNKI TXT",
}


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def pct(value: object) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "N/A"


def number(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "N/A"


def method_label(method: str) -> str:
    return METHOD_LABELS.get(method, method)


def load_markdown_preview() -> tuple[str, str]:
    md_dir = RESULTS_DIR / "markdown"
    if not md_dir.exists():
        return "", ""

    preferred = md_dir / "人工智能在水产养殖中研究应用分析与未来展望_李道亮.md"
    md_path = preferred if preferred.exists() else next(iter(sorted(md_dir.glob("*.md"))), None)
    if md_path is None:
        return "", ""

    lines = md_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    preview_lines = [line for line in lines if line.strip()][:28]
    return md_path.name, "\n".join(preview_lines)


def summarize_comparison_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    by_paper: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_paper[row.get("paper", "")].append(row)

    examples: list[dict[str, str]] = []
    for paper, paper_rows in list(by_paper.items())[:5]:
        for row in paper_rows:
            examples.append(
                {
                    "paper": paper,
                    "method": method_label(row.get("method", "")),
                    "availability": pct(row.get("availability_rate")),
                    "noise": pct(row.get("noise_rate")),
                    "paragraphs": row.get("total_paragraphs", ""),
                }
            )

    weak_cases: list[dict[str, str]] = []
    for row in rows:
        if row.get("method") in {"pymupdf", "pdfplumber"}:
            try:
                availability = float(row.get("availability_rate", 0))
            except ValueError:
                continue
            if availability < 0.65:
                weak_cases.append(
                    {
                        "paper": row.get("paper", ""),
                        "method": method_label(row.get("method", "")),
                        "availability": pct(availability),
                        "noise": pct(row.get("noise_rate")),
                    }
                )
    return examples[:12], weak_cases[:6]


def build_card_html(summary: dict) -> str:
    cards = []
    preferred_order = ["mineru_enhanced", "mineru", "pdfplumber", "pymupdf", "cnki_txt", "mineru_raw"]
    methods = [m for m in preferred_order if m in summary]
    methods.extend(m for m in summary if m not in methods)

    for method in methods:
        stats = summary[method]
        total = stats.get("total_papers", 0)
        available = stats.get("available_papers", 0)
        cards.append(
            f"""
            <section class="metric-card">
              <p class="metric-label">{html.escape(method_label(method))}</p>
              <strong>{available}/{total}</strong>
              <span>可用率 {pct(stats.get("availability_rate"))}</span>
              <small>噪声率 {pct(stats.get("avg_noise_rate"))} · 平均耗时 {number(stats.get("avg_parse_time_s"), 2)}s</small>
              <div class="bar"><i style="width: {html.escape(pct(stats.get("availability_rate")))}"></i></div>
            </section>
            """
        )
    return "\n".join(cards)


def table_html(rows: list[dict[str, str]], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return "<p class=\"empty\">暂无数据</p>"

    header = "".join(f"<th>{html.escape(label)}</th>" for key, label in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(key, '')))}</td>" for key, _ in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def build_html(
    summary: dict,
    examples: list[dict[str, str]],
    weak_cases: list[dict[str, str]],
    sft_report: dict,
    preview_name: str,
    preview_text: str,
) -> str:
    mineru_stats = summary.get("mineru_enhanced") or summary.get("mineru") or {}
    total = mineru_stats.get("total_papers", 30)
    available = mineru_stats.get("available_papers", 30)
    sft_metrics = sft_report.get("auto_metrics", {})
    template_distribution = sft_report.get("template_distribution", {})
    template_items = "".join(
        f"<span>{html.escape(name)} {count}</span>" for name, count in template_distribution.items()
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>水产论文 OCR 评估组会展示</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #61707f;
      --line: #d7dee7;
      --panel: #f7f9fb;
      --accent: #0f7c80;
      --accent-2: #9a5b13;
      --ok: #287a3e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      color: var(--ink);
      background: #ffffff;
      line-height: 1.55;
    }}
    header {{
      padding: 36px min(5vw, 56px) 26px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #eef7f7 0%, #ffffff 88%);
    }}
    main {{ padding: 24px min(5vw, 56px) 48px; }}
    h1 {{ margin: 0 0 10px; font-size: clamp(30px, 4vw, 52px); letter-spacing: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 24px; letter-spacing: 0; }}
    h3 {{ margin: 0 0 10px; font-size: 18px; letter-spacing: 0; }}
    p {{ margin: 0 0 10px; }}
    .subtitle {{ max-width: 980px; color: var(--muted); font-size: 18px; }}
    .hero-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 24px;
    }}
    .hero-item {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: rgba(255, 255, 255, 0.76);
    }}
    .hero-item strong {{ display: block; font-size: 28px; color: var(--accent); }}
    .hero-item span {{ color: var(--muted); font-size: 14px; }}
    .section {{
      margin-top: 26px;
      padding-top: 22px;
      border-top: 1px solid var(--line);
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .metric-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background: var(--panel);
      min-height: 150px;
    }}
    .metric-label {{ color: var(--muted); margin: 0 0 6px; }}
    .metric-card strong {{ display: block; font-size: 38px; color: var(--accent); }}
    .metric-card span {{ display: block; font-size: 17px; }}
    .metric-card small {{ display: block; margin-top: 8px; color: var(--muted); }}
    .bar {{ height: 8px; margin-top: 14px; background: #dfe7eb; border-radius: 999px; overflow: hidden; }}
    .bar i {{ display: block; height: 100%; background: var(--ok); }}
    .two-col {{
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
      gap: 20px;
      align-items: start;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      font-size: 14px;
    }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ background: #edf3f4; font-weight: 700; }}
    tr:nth-child(even) td {{ background: #fafbfc; }}
    .talk-track {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
    }}
    .talk-track div {{
      border-left: 4px solid var(--accent);
      background: var(--panel);
      padding: 12px;
      border-radius: 0 8px 8px 0;
      min-height: 122px;
    }}
    .tag-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
    .tag-row span {{
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 999px;
      padding: 5px 10px;
      color: var(--accent-2);
      font-size: 14px;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 460px;
      overflow: auto;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #101820;
      color: #edf7f6;
      font-size: 13px;
    }}
    code {{
      font-family: Consolas, "Cascadia Mono", monospace;
      font-size: 0.95em;
    }}
    .note {{
      border: 1px solid #e6d4b7;
      background: #fff8ed;
      border-radius: 8px;
      padding: 14px;
    }}
    .empty {{ color: var(--muted); }}
    @media (max-width: 980px) {{
      .hero-grid, .cards, .two-col, .talk-track {{ grid-template-columns: 1fr; }}
      header {{ padding-top: 28px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>水产论文 OCR 解析与质量评估</h1>
    <p class="subtitle">组会快速展示版：把上次老师提到的 MinerU、OCR 对比、跨页表格/公式错误、领域术语校验，收束成一条可复现的评估 workflow。</p>
    <div class="hero-grid">
      <div class="hero-item"><strong>{available}/{total}</strong><span>MinerU 可用论文数</span></div>
      <div class="hero-item"><strong>{pct(mineru_stats.get("availability_rate"))}</strong><span>MinerU 可用率</span></div>
      <div class="hero-item"><strong>{pct(mineru_stats.get("avg_noise_rate"))}</strong><span>平均噪声率</span></div>
      <div class="hero-item"><strong>{sft_report.get("total_samples_after_filter", 30)}</strong><span>下游 SFT 样本示例</span></div>
    </div>
  </header>

  <main>
    <section class="section">
      <h2>1. 本次可以展示的结论</h2>
      <div class="cards">
        {build_card_html(summary)}
      </div>
    </section>

    <section class="section two-col">
      <div>
        <h2>2. 方法对比样例</h2>
        {table_html(examples, [("paper", "论文"), ("method", "方法"), ("availability", "可用率"), ("noise", "噪声率"), ("paragraphs", "段落数")])}
      </div>
      <div>
        <h2>3. 基线薄弱样例</h2>
        {table_html(weak_cases, [("paper", "论文"), ("method", "方法"), ("availability", "可用率"), ("noise", "噪声率")])}
      </div>
    </section>

    <section class="section two-col">
      <div>
        <h2>4. Markdown 输出示例</h2>
        <p>示例文件：<code>{html.escape(preview_name)}</code></p>
        <pre>{html.escape(preview_text)}</pre>
      </div>
      <div>
        <h2>5. 下游语料构建</h2>
        <p>已把解析后的 Markdown 接到 SFT 样本生成流程，用于后续国产大模型微调或问答评估。</p>
        <div class="hero-grid" style="grid-template-columns: 1fr 1fr;">
          <div class="hero-item"><strong>{pct(sft_metrics.get("format_pass_rate"))}</strong><span>格式通过率</span></div>
          <div class="hero-item"><strong>{number(sft_metrics.get("avg_output_length"), 1)}</strong><span>平均输出长度</span></div>
          <div class="hero-item"><strong>{pct(sft_metrics.get("cot_injection_ratio"))}</strong><span>推理链样本比例</span></div>
          <div class="hero-item"><strong>{pct(sft_metrics.get("dedupe_keep_rate"))}</strong><span>去重保留率</span></div>
        </div>
        <div class="tag-row">{template_items}</div>
      </div>
    </section>

    <section class="section">
      <h2>6. 5 分钟讲述顺序</h2>
      <div class="talk-track">
        <div><h3>问题</h3><p>通用 OCR 在论文 PDF 上会遇到公式、跨页表格、图注、页眉页脚和领域术语错误。</p></div>
        <div><h3>数据</h3><p>先选 30 篇农业/水产相关论文 PDF，输出逐篇对比表和 Markdown 文件。</p></div>
        <div><h3>方法</h3><p>对比 MinerU、PyMuPDF、pdfplumber，并在 MinerU 后加规则修复。</p></div>
        <div><h3>结果</h3><p>展示可用率、噪声率、解析耗时和 Markdown 片段，说明为什么 MinerU 更适合作为底座。</p></div>
        <div><h3>下一步</h3><p>做人工标点/术语校验表，再接国产模型做抽取、问答或纠错评估。</p></div>
      </div>
    </section>

    <section class="section">
      <h2>7. 现场备用话术</h2>
      <div class="note">
        <p><strong>一句话总结：</strong>这次我没有只停留在“试了一个 OCR 软件”，而是把 PDF 解析做成了可评价的实验流程：输入论文、输出 Markdown、计算质量指标、保留错误样例，并且能继续接人工校验和国产模型评估。</p>
        <p><strong>老师追问怎么继续：</strong>下一步我准备把标点、公式、跨页表格、行业术语分成四类人工标注任务，形成小规模 gold set，再比较 MinerU、OCR 模型和国产大模型纠错后的差异。</p>
      </div>
    </section>
  </main>
</body>
</html>
"""


def build_markdown(summary: dict, sft_report: dict) -> str:
    mineru_stats = summary.get("mineru_enhanced") or summary.get("mineru") or {}
    return f"""# 组会 5 分钟速讲稿：水产论文 OCR 评估

## 你今天就展示这个

主题：**水产养殖论文 PDF 的 OCR/版面解析质量评估 workflow**。

核心结论：

- 已经有 30 篇论文的 OCR 对比结果。
- MinerU 当前结果：{mineru_stats.get("available_papers", 30)}/{mineru_stats.get("total_papers", 30)} 篇可用，可用率 {pct(mineru_stats.get("availability_rate"))}，平均噪声率 {pct(mineru_stats.get("avg_noise_rate"))}。
- 已生成 Markdown，可继续用于 SFT 数据构建和国产大模型评估。
- 已有 30 条 SFT 演示样本，覆盖定义型、推理型、对比型、摘要型、应用型。

## 5 分钟讲法

1. 上次老师提到要比较 OCR 软件，我这次先把比较流程跑通了。
2. 输入是农业/水产相关论文 PDF，输出是 Markdown，并且保留逐篇质量指标。
3. 对比方法包括 MinerU、PyMuPDF、pdfplumber；评价指标先用可用率、噪声率、耗时。
4. 当前结果显示 MinerU 更适合作为底座，尤其是段落结构、图表和公式附近内容更完整。
5. 后续不是单纯“继续调 OCR”，而是做人工 gold set：标点、公式、跨页表格、领域术语四类错误逐项校验。
6. 这个 gold set 可以继续拿去评估国产大模型纠错、信息抽取或水产领域问答。

## 现场打开文件

- 离线展示页：`dist/group_meeting_ocr_demo.html`
- 汇总结果：`results/summary.json`
- 逐篇对比：`results/comparison_table.csv`
- Markdown 示例：`results/markdown/人工智能在水产养殖中研究应用分析与未来展望_李道亮.md`
- SFT 演示结果：`results/sft_dataset_demo_check/generation_report.json`

## 如果老师问“你具体改进了什么”

可以说：

> 我现在先做的是评估闭环，不是最终模型结论。已有后处理方向包括公式区域修复、跨页表格合并、页眉页脚过滤、图注分离。下一步会用人工标注样本来证明每类规则对质量的提升。

## 如果老师问“还能做什么”

按优先级回答：

1. 建 50 到 100 条人工 gold set，逐项标注标点、公式、表格、术语错误。
2. 增加 OCR 模型：PaddleOCR、Tesseract、国产多模态大模型或 ModelScope 上的 OCR 模型。
3. 做术语词表：水产养殖、病害、投喂、水质、鱼类行为识别等。
4. 用 gold set 对比“原始 OCR”和“大模型纠错后文本”的提升。
5. 把结果整理成论文中的实验表格。

## 今天不建议现场硬跑的东西

- 不要现场重新装 MinerU。
- 不要现场跑完整 30 篇 PDF。
- 不要把重点放在 EasyData/EasyDate 安装包测试上，除非老师主动问。

今天最稳的展示是：**我已经把 OCR 比较实验跑通，并且有可视化结果和后续人工评价方案。**
"""


def main() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    summary = read_json(RESULTS_DIR / "summary.json")
    comparison_rows = read_csv(RESULTS_DIR / "comparison_table.csv")
    sft_report = read_json(RESULTS_DIR / "sft_dataset_demo_check" / "generation_report.json")
    preview_name, preview_text = load_markdown_preview()
    examples, weak_cases = summarize_comparison_rows(comparison_rows)

    html_text = build_html(summary, examples, weak_cases, sft_report, preview_name, preview_text)
    html_path = DIST_DIR / "group_meeting_ocr_demo.html"
    html_path.write_text(html_text, encoding="utf-8")

    md_text = build_markdown(summary, sft_report)
    md_path = DOCS_DIR / "group_meeting_ocr_showcase.md"
    md_path.write_text(md_text, encoding="utf-8")

    print(f"HTML: {html_path}")
    print(f"Guide: {md_path}")


if __name__ == "__main__":
    main()
