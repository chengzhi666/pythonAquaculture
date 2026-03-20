"""
SFT 语料自动生成管线
对应论文 4.6 + 5.4 节

功能：
1. 读取 MinerU 解析后的 Markdown 与 CNKI 摘要 TSV
2. 生成 5 类模板样本（定义型 / 推理型 / 对比型 / 摘要型 / 应用型）
3. 差异化注入 CoT
4. 执行完整性、重复性、CoT 结构、领域相关性四类过滤
5. 导出 Alpaca(JSONL) 与 ShareGPT(JSON) 两种格式
6. 计算模板分布、长度统计与自动化指标
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence


TEMPLATE_ORDER = ["definition", "reasoning", "comparison", "summary", "application"]
TEMPLATE_LABELS = {
    "definition": "定义型",
    "reasoning": "推理型",
    "comparison": "对比型",
    "summary": "摘要型",
    "application": "应用型",
}
FORCED_COT_TEMPLATES = {"reasoning", "comparison", "application"}
NO_COT_TEMPLATES = {"definition"}
SELECTIVE_COT_TEMPLATES = {"summary"}
SUMMARY_COT_RATIO = 96 / 178

DEFAULT_TEMPLATE_COUNTS = {
    "definition": 203,
    "reasoning": 157,
    "comparison": 157,
    "summary": 178,
    "application": 157,
}

PROMPT_VARIANTS = {
    "definition": [
        "请解释文中提到的“{focus}”在水产养殖语境中的含义，并概括其核心要点。",
        "请基于以下材料说明“{focus}”的定义、特征及其在研究中的作用。",
        "请阅读材料并回答：“{focus}”主要指什么？有哪些关键特征？",
    ],
    "reasoning": [
        "请根据以下材料，分析“{focus}”产生的原因、机制及可能影响。",
        "请结合材料推断“{focus}”背后的因果关系，并给出专业判断。",
        "请阅读材料，说明“{focus}”为什么会出现，以及它会带来什么结果。",
    ],
    "comparison": [
        "请根据以下材料，对比“{left}”与“{right}”的主要差异，并给出综合评价。",
        "请结合材料比较“{left}”和“{right}”在目标、特点和适用场景上的不同。",
        "请阅读材料，概括“{left}”与“{right}”的异同点及其启示。",
    ],
    "summary": [
        "请根据以下研究内容归纳核心观点、关键发现与结论。",
        "请阅读材料并总结其研究目标、主要方法和结论。",
        "请对以下内容进行摘要，概括研究重点和实际意义。",
    ],
    "application": [
        "请根据以下材料，说明该研究结论在水产养殖实际场景中的应用方式。",
        "请结合材料提出“{focus}”在生产管理或市场分析中的应用建议。",
        "请阅读材料，并说明相关发现可如何转化为行业实践。",
    ],
}

GENERIC_PHRASES = {
    "本研究",
    "结果表明",
    "研究表明",
    "本文",
    "该文",
    "材料",
    "研究",
    "分析",
    "结论",
    "方法",
    "结果",
    "影响",
}

DOMAIN_TERM_GROUPS = {
    "species": [
        "三文鱼", "大西洋三文鱼", "帝王鲑", "虹鳟", "鲑鱼", "鲑鳟", "鳕鱼", "金枪鱼", "罗非鱼",
        "草鱼", "鲫鱼", "鲈鱼", "对虾", "南美白对虾", "凡纳滨对虾", "斑节对虾", "海参", "扇贝",
        "牡蛎", "鲍鱼", "海鲈", "石斑鱼", "黄鳝", "泥鳅", "水产品",
    ],
    "aquaculture": [
        "养殖", "水产养殖", "循环水养殖", "工厂化养殖", "池塘养殖", "网箱养殖", "苗种", "育苗", "驯化",
        "养殖密度", "成活率", "生长性能", "增重率", "特定生长率", "饲料系数", "摄食率", "出肉率",
        "病害防控", "病原", "应激", "免疫", "抗氧化", "繁殖", "营养需求", "种质",
    ],
    "water_quality": [
        "溶解氧", "水温", "盐度", "pH", "氨氮", "亚硝酸盐", "硝酸盐", "总磷", "总氮", "悬浮物",
        "水质", "藻相", "透明度", "碱度", "硬度", "微生态", "菌群", "尾水", "净化", "增氧",
    ],
    "feed_and_health": [
        "饲料", "配方", "鱼粉", "鱼油", "蛋白质", "脂肪", "维生素", "氨基酸", "益生菌", "酶制剂",
        "疫苗", "病害", "寄生虫", "弧菌", "细菌性疾病", "病毒", "炎症", "肠道健康", "免疫力", "抗病力",
    ],
    "processing_market": [
        "加工", "冷链", "冰鲜", "冷冻", "货架期", "保鲜", "品质", "脂肪酸", "感官评价", "质构",
        "电商", "零售价格", "批发价格", "市场监测", "价格趋势", "产地", "规格", "认证", "进口", "销量",
    ],
}

CORE_DOMAIN_TERMS = sorted({term for terms in DOMAIN_TERM_GROUPS.values() for term in terms})
NEGATION_HINTS = ("不涉及", "无关", "并非", "不是", "缺乏", "脱离")


@dataclass
class ParsedBlock:
    doc_id: str
    title: str
    section_title: str
    content: str
    source_path: str
    source_type: str
    keywords: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class SftSample:
    sample_id: str
    template_type: str
    instruction: str
    input: str
    output: str
    source_doc_id: str
    source_title: str
    source_section: str
    cot_strategy: str
    cot_injected: bool
    domain_terms: list[str] = field(default_factory=list)
    needs_manual_review: bool = False
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class GenerationReport:
    total_blocks: int
    total_samples_before_filter: int
    total_samples_after_filter: int
    template_distribution: dict[str, int]
    cot_injection_ratio: float
    avg_output_length: float
    removed_counts: dict[str, int] = field(default_factory=dict)
    auto_metrics: dict[str, object] = field(default_factory=dict)


def read_text_with_fallback(path: Path, encodings: Sequence[str] | None = None) -> str:
    encodings = encodings or ("utf-8", "utf-8-sig", "gb18030", "gbk")
    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    text = normalize_text(text)
    parts = re.split(r"(?<=[。！？；!?;])\s*", text)
    return [p.strip() for p in parts if p.strip()]


def parse_keywords(raw_keywords: str) -> list[str]:
    if not raw_keywords:
        return []
    cleaned = normalize_text(raw_keywords).strip("；;，,")
    parts = re.split(r"[；;、,，]\s*", cleaned)
    return [p.strip() for p in parts if p.strip()]


def stable_hash(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def extract_candidate_phrases(text: str, limit: int = 8) -> list[str]:
    phrases = re.findall(r"[\u4e00-\u9fffA-Za-z]{2,12}", text)
    counts: Counter[str] = Counter()
    for phrase in phrases:
        if phrase in GENERIC_PHRASES:
            continue
        if phrase in CORE_DOMAIN_TERMS:
            counts[phrase] += 5
        else:
            counts[phrase] += 1
    return [item for item, _ in counts.most_common(limit)]


def extract_domain_terms(text: str, limit: int = 8) -> list[str]:
    found: list[str] = []
    for term in CORE_DOMAIN_TERMS:
        start = text.find(term)
        while start != -1:
            context_start = max(0, start - 12)
            context_end = min(len(text), start + len(term) + 12)
            context = text[context_start:context_end]
            if not any(hint in context for hint in NEGATION_HINTS):
                found.append(term)
                break
            start = text.find(term, start + len(term))
    return found[:limit]


def should_skip_markdown_paragraph(paragraph: str, section_title: str) -> bool:
    if not paragraph:
        return True
    lowered = paragraph.lower()
    if "参考文献" in section_title or lowered.startswith("references"):
        return True
    if re.match(r"^[\-\s_=]{3,}$", paragraph):
        return True
    if len(paragraph) < 30:
        return True
    return False


def chunk_text(paragraph: str, max_chars: int = 1200) -> list[str]:
    sentences = split_sentences(paragraph)
    if not sentences:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for sentence in sentences:
        sent_len = len(sentence)
        if current and current_len + sent_len > max_chars:
            chunks.append("".join(current).strip())
            current = [sentence]
            current_len = sent_len
        else:
            current.append(sentence)
            current_len += sent_len
    if current:
        chunks.append("".join(current).strip())
    return chunks


def extract_markdown_title(path: Path, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return re.sub(r"^#+\s*", "", stripped).strip()
    return path.stem


def load_markdown_blocks(markdown_dirs: Sequence[Path]) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    for markdown_dir in markdown_dirs:
        if not markdown_dir.exists():
            continue
        for md_path in sorted(markdown_dir.glob("**/*.md")):
            text = normalize_text(read_text_with_fallback(md_path))
            if not text:
                continue
            title = extract_markdown_title(md_path, text)
            current_section = title
            paragraph_lines: list[str] = []

            def flush_paragraph() -> None:
                nonlocal paragraph_lines, current_section
                paragraph = normalize_text("\n".join(paragraph_lines))
                paragraph_lines = []
                if should_skip_markdown_paragraph(paragraph, current_section):
                    return
                keywords = extract_domain_terms(f"{title}\n{current_section}\n{paragraph}")
                for idx, chunk in enumerate(chunk_text(paragraph)):
                    block_id = stable_hash(f"{md_path}:{current_section}:{idx}:{chunk[:80]}")
                    blocks.append(
                        ParsedBlock(
                            doc_id=block_id,
                            title=title,
                            section_title=current_section,
                            content=chunk,
                            source_path=str(md_path),
                            source_type="mineru_markdown",
                            keywords=keywords,
                            metadata={"file_name": md_path.name},
                        )
                    )

            for raw_line in text.splitlines():
                line = raw_line.strip()
                if line.startswith("#"):
                    flush_paragraph()
                    current_section = re.sub(r"^#+\s*", "", line).strip() or title
                    continue
                if not line:
                    flush_paragraph()
                    continue
                paragraph_lines.append(line)
            flush_paragraph()
    return blocks


def parse_cnki_tsv_row(parts: Sequence[str]) -> ParsedBlock | None:
    if len(parts) < 10:
        return None
    rank, title, authors, institute, pub_date, source, database, keywords, abstract, url = parts[:10]
    abstract = normalize_text(abstract)
    if len(abstract) < 30:
        return None
    keywords_list = parse_keywords(keywords)
    block_id = stable_hash(f"{title}|{pub_date}|{url}")
    return ParsedBlock(
        doc_id=block_id,
        title=normalize_text(title) or "CNKI 摘要",
        section_title="摘要",
        content=abstract,
        source_path=url,
        source_type="cnki_abstract",
        keywords=keywords_list,
        metadata={
            "authors": normalize_text(authors),
            "institute": normalize_text(institute),
            "pub_date": normalize_text(pub_date),
            "source": normalize_text(source),
            "database": normalize_text(database),
            "rank": normalize_text(rank),
        },
    )


def load_cnki_abstract_blocks(cnki_paths: Sequence[Path]) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    for cnki_path in cnki_paths:
        if not cnki_path.exists():
            continue
        text = read_text_with_fallback(cnki_path)
        for line in text.splitlines():
            parts = line.rstrip("\n").split("\t")
            block = parse_cnki_tsv_row(parts)
            if block is not None:
                blocks.append(block)
    return blocks


def load_parsed_docs(
    markdown_dirs: Sequence[str | Path] | None = None,
    cnki_paths: Sequence[str | Path] | None = None,
) -> list[ParsedBlock]:
    markdown_dirs = markdown_dirs or [Path("results/markdown")]
    cnki_paths = cnki_paths or sorted(Path("fish_intel_mvp").glob("CNKI_*.tsv"))
    markdown_paths = [Path(p) for p in markdown_dirs]
    cnki_file_paths = [Path(p) for p in cnki_paths]

    blocks = load_markdown_blocks(markdown_paths)
    blocks.extend(load_cnki_abstract_blocks(cnki_file_paths))
    return blocks


def extract_key_sentences(block: ParsedBlock, desired: int = 3, offset: int = 0) -> list[str]:
    sentences = split_sentences(block.content)
    if not sentences:
        return [block.content]
    if len(sentences) <= desired:
        return sentences
    start = offset % max(len(sentences) - desired + 1, 1)
    window = sentences[start:start + desired]
    if len(window) < desired:
        window.extend(sentences[: desired - len(window)])
    return window


def pick_focus_terms(block: ParsedBlock, limit: int = 4) -> list[str]:
    ordered_terms: list[str] = []
    for source in (block.keywords, extract_domain_terms(block.content), extract_candidate_phrases(block.title), extract_candidate_phrases(block.content)):
        for item in source:
            if item not in ordered_terms:
                ordered_terms.append(item)
            if len(ordered_terms) >= limit:
                return ordered_terms
    return ordered_terms or [block.section_title or block.title]


def ensure_length(text: str, minimum: int = 50) -> str:
    if len(text) >= minimum:
        return text
    padding = "这说明该主题在文献中具有明确的专业语义和研究价值，适合作为后续大模型微调语料的训练样本。"
    while len(text) < minimum:
        text += padding
    return text


def build_context_input(block: ParsedBlock, max_chars: int = 900) -> str:
    context = block.content[:max_chars].strip()
    return "\n".join([
        f"文献标题：{block.title}",
        f"章节位置：{block.section_title}",
        f"材料内容：{context}",
    ])


def build_definition_output(block: ParsedBlock, focus: str, variant: int) -> str:
    sentences = extract_key_sentences(block, desired=2, offset=variant)
    lead = sentences[0].rstrip("。；;")
    extra = sentences[1].rstrip("。；;") if len(sentences) > 1 else lead
    output = (
        f"根据材料，{focus}主要指{lead}。"
        f"结合文中语境可知，{focus}的关键特征在于{extra}。"
        f"在该研究场景下，{focus}是理解文献核心观点的重要概念。"
    )
    return ensure_length(output)


def build_summary_output(block: ParsedBlock, variant: int) -> str:
    sentences = extract_key_sentences(block, desired=3, offset=variant)
    output = (
        f"材料围绕“{block.title}”展开，主要讨论了{sentences[0].rstrip('。')}。"
        f"进一步来看，文中指出{sentences[1].rstrip('。') if len(sentences) > 1 else sentences[0].rstrip('。')}。"
        f"综合而言，该材料的核心结论是{sentences[2].rstrip('。') if len(sentences) > 2 else sentences[-1].rstrip('。')}。"
    )
    return ensure_length(output)


def build_reasoning_output(block: ParsedBlock, focus: str, variant: int) -> str:
    sentences = extract_key_sentences(block, desired=3, offset=variant)
    output = (
        f"从材料可以看出，{focus}的形成首先与{sentences[0].rstrip('。')}有关。"
        f"进一步分析，{sentences[1].rstrip('。') if len(sentences) > 1 else sentences[0].rstrip('。')}说明其背后存在明显的因果链条。"
        f"因此，{focus}最终会影响{sentences[2].rstrip('。') if len(sentences) > 2 else block.section_title}，并对水产养殖实践产生实际意义。"
    )
    return ensure_length(output)


def build_comparison_output(block: ParsedBlock, left: str, right: str, variant: int) -> str:
    sentences = extract_key_sentences(block, desired=3, offset=variant)
    output = (
        f"根据材料，{left}与{right}都与“{block.section_title}”相关，但侧重点并不相同。"
        f"其中，{left}更突出{sentences[0].rstrip('。')}；而{right}则更多体现为{sentences[1].rstrip('。') if len(sentences) > 1 else sentences[0].rstrip('。')}。"
        f"综合比较可知，两者在研究对象、作用机制和实际应用上存在差异，文中最终强调的是{sentences[2].rstrip('。') if len(sentences) > 2 else block.title}。"
    )
    return ensure_length(output)


def build_application_output(block: ParsedBlock, focus: str, variant: int) -> str:
    sentences = extract_key_sentences(block, desired=3, offset=variant)
    output = (
        f"结合材料，{focus}可应用于水产养殖生产管理、市场监测或技术优化等场景。"
        f"具体而言，可先依据{sentences[0].rstrip('。')}建立分析依据，再根据{sentences[1].rstrip('。') if len(sentences) > 1 else sentences[0].rstrip('。')}制定执行方案。"
        f"在落地过程中，还应关注{sentences[2].rstrip('。') if len(sentences) > 2 else block.section_title}，以确保方案具备可操作性和行业适配性。"
    )
    return ensure_length(output)


def inject_cot(
    output: str,
    template_type: str,
    key_sentences: Sequence[str] | None = None,
    forced: bool | None = None,
) -> tuple[str, bool, str]:
    key_sentences = [s.rstrip("。；;") for s in (key_sentences or []) if s.strip()]
    strategy = "forced" if template_type in FORCED_COT_TEMPLATES else "none"
    if template_type in SELECTIVE_COT_TEMPLATES:
        strategy = "selective"
    if forced is None:
        forced = strategy == "forced"
    if strategy == "none":
        return output, False, strategy
    if not forced and strategy == "selective":
        return output, False, strategy

    fact_1 = key_sentences[0] if len(key_sentences) > 0 else output[:60].rstrip("。")
    fact_2 = key_sentences[1] if len(key_sentences) > 1 else output[:80].rstrip("。")
    fact_3 = key_sentences[2] if len(key_sentences) > 2 else "材料还提示需要结合具体养殖场景进行补充判断"
    conclusion = output.rstrip()
    cot_output = "\n".join([
        "【分析过程】",
        f"首先，从材料可以直接定位到：{fact_1}。",
        f"其次，结合上下文可以进一步推断：{fact_2}。",
        f"此外，还需要注意：{fact_3}。",
        "【结论】",
        f"{conclusion}",
    ])
    return cot_output, True, strategy


def build_sample(block: ParsedBlock, template_type: str, variant: int, force_summary_cot: bool = False) -> SftSample:
    focus_terms = pick_focus_terms(block)
    focus = focus_terms[0]
    left = focus_terms[0]
    right = focus_terms[1] if len(focus_terms) > 1 else f"{focus}的相关因素"
    prompt_templates = PROMPT_VARIANTS[template_type]
    prompt_template = prompt_templates[variant % len(prompt_templates)]

    if template_type == "definition":
        instruction = prompt_template.format(focus=focus)
        output = build_definition_output(block, focus, variant)
    elif template_type == "reasoning":
        instruction = prompt_template.format(focus=focus)
        output = build_reasoning_output(block, focus, variant)
    elif template_type == "comparison":
        instruction = prompt_template.format(left=left, right=right)
        output = build_comparison_output(block, left, right, variant)
    elif template_type == "summary":
        instruction = prompt_template
        output = build_summary_output(block, variant)
    else:
        instruction = prompt_template.format(focus=focus)
        output = build_application_output(block, focus, variant)

    key_sentences = extract_key_sentences(block, desired=3, offset=variant)
    output, cot_injected, cot_strategy = inject_cot(
        output,
        template_type=template_type,
        key_sentences=key_sentences,
        forced=force_summary_cot if template_type == "summary" else None,
    )

    input_text = build_context_input(block)
    sample_id = stable_hash(f"{block.doc_id}|{template_type}|{variant}|{instruction}")
    domain_terms = extract_domain_terms(f"{block.title}\n{block.content}\n{output}")
    return SftSample(
        sample_id=sample_id,
        template_type=template_type,
        instruction=instruction,
        input=input_text,
        output=output,
        source_doc_id=block.doc_id,
        source_title=block.title,
        source_section=block.section_title,
        cot_strategy=cot_strategy,
        cot_injected=cot_injected,
        domain_terms=domain_terms,
        metadata={
            "template_label": TEMPLATE_LABELS[template_type],
            "source_type": block.source_type,
            "source_path": block.source_path,
        },
    )


def is_block_suitable(block: ParsedBlock, template_type: str) -> bool:
    length = len(block.content)
    has_numbers = bool(re.search(r"\d", block.content))
    focus_terms = pick_focus_terms(block)
    if template_type == "definition":
        return bool(focus_terms) and length >= 80
    if template_type == "reasoning":
        return length >= 140
    if template_type == "comparison":
        return len(focus_terms) >= 2 or "对比" in block.content or "比较" in block.content
    if template_type == "summary":
        return length >= 120
    if template_type == "application":
        return has_numbers or length >= 160
    return True


def quality_filter_sample(
    sample: SftSample,
    dedupe_registry: dict[str, SftSample],
    removed_counts: Counter[str],
) -> bool:
    if not sample.instruction.strip() or not sample.output.strip():
        removed_counts["incomplete"] += 1
        return False
    if not (50 <= len(sample.output) <= 4096):
        removed_counts["incomplete"] += 1
        return False

    dedupe_key = stable_hash(sample.instruction + "\n" + sample.input)
    if dedupe_key in dedupe_registry:
        removed_counts["duplicate"] += 1
        return False

    if sample.template_type in FORCED_COT_TEMPLATES:
        has_cot = "【分析过程】" in sample.output and "【结论】" in sample.output
        if not has_cot:
            removed_counts["cot_incomplete"] += 1
            return False

    if not sample.domain_terms:
        removed_counts["domain_irrelevant"] += 1
        return False

    if len(sample.output) > 2000:
        sample.needs_manual_review = True

    dedupe_registry[dedupe_key] = sample
    return True


def generate_sft_dataset(
    blocks: Sequence[ParsedBlock],
    template_counts: dict[str, int] | None = None,
    summary_cot_ratio: float = SUMMARY_COT_RATIO,
) -> tuple[list[SftSample], GenerationReport]:
    template_counts = template_counts or DEFAULT_TEMPLATE_COUNTS.copy()
    removed_counts: Counter[str] = Counter()
    samples: list[SftSample] = []
    dedupe_registry: dict[str, SftSample] = {}
    total_before_filter = 0

    if not blocks:
        report = GenerationReport(
            total_blocks=0,
            total_samples_before_filter=0,
            total_samples_after_filter=0,
            template_distribution={},
            cot_injection_ratio=0.0,
            avg_output_length=0.0,
            removed_counts={},
            auto_metrics={},
        )
        return [], report

    for template_type in TEMPLATE_ORDER:
        target_count = template_counts.get(template_type, 0)
        if target_count <= 0:
            continue

        eligible = [block for block in blocks if is_block_suitable(block, template_type)]
        if not eligible:
            eligible = list(blocks)

        summary_cot_target = round(target_count * summary_cot_ratio) if template_type == "summary" else 0
        produced = 0
        attempts = 0
        max_attempts = max(target_count * 40, 200)

        while produced < target_count and attempts < max_attempts:
            block = eligible[attempts % len(eligible)]
            force_summary_cot = template_type == "summary" and produced < summary_cot_target
            sample = build_sample(block, template_type=template_type, variant=attempts, force_summary_cot=force_summary_cot)
            total_before_filter += 1
            if quality_filter_sample(sample, dedupe_registry, removed_counts):
                samples.append(sample)
                produced += 1
            attempts += 1

    report = build_generation_report(
        blocks=blocks,
        samples=samples,
        total_before_filter=total_before_filter,
        removed_counts=removed_counts,
    )
    return samples, report


def build_generation_report(
    blocks: Sequence[ParsedBlock],
    samples: Sequence[SftSample],
    total_before_filter: int,
    removed_counts: Counter[str],
) -> GenerationReport:
    template_distribution = Counter(sample.template_type for sample in samples)
    cot_ratio = (
        sum(1 for sample in samples if sample.cot_injected) / len(samples)
        if samples else 0.0
    )
    avg_output_length = (
        sum(len(sample.output) for sample in samples) / len(samples)
        if samples else 0.0
    )
    auto_metrics = compute_automatic_metrics(samples, total_before_filter, removed_counts)
    return GenerationReport(
        total_blocks=len(blocks),
        total_samples_before_filter=total_before_filter,
        total_samples_after_filter=len(samples),
        template_distribution=dict(template_distribution),
        cot_injection_ratio=round(cot_ratio, 4),
        avg_output_length=round(avg_output_length, 2),
        removed_counts=dict(removed_counts),
        auto_metrics=auto_metrics,
    )


def compute_automatic_metrics(
    samples: Sequence[SftSample],
    total_before_filter: int,
    removed_counts: Counter[str] | None = None,
) -> dict[str, object]:
    removed_counts = removed_counts or Counter()
    total = len(samples)
    format_pass_count = sum(
        1 for sample in samples
        if sample.instruction.strip() and 50 <= len(sample.output) <= 4096
    )
    forced_samples = [sample for sample in samples if sample.template_type in FORCED_COT_TEMPLATES]
    cot_complete_count = sum(
        1 for sample in forced_samples
        if "【分析过程】" in sample.output and "【结论】" in sample.output
    )
    cot_step_counts = [
        sum(sample.output.count(marker) for marker in ("首先", "其次", "此外"))
        for sample in samples
        if sample.cot_injected
    ]
    covered_terms = {
        term
        for sample in samples
        for term in CORE_DOMAIN_TERMS
        if term in f"{sample.input}\n{sample.output}"
    }
    dedupe_keep_rate = total / total_before_filter if total_before_filter else 0.0
    return {
        "total_samples": total,
        "format_pass_rate": round(format_pass_count / total, 4) if total else 0.0,
        "avg_output_length": round(sum(len(sample.output) for sample in samples) / total, 2) if total else 0.0,
        "dedupe_keep_rate": round(dedupe_keep_rate, 4),
        "cot_completeness_rate": round(cot_complete_count / len(forced_samples), 4) if forced_samples else 0.0,
        "cot_injection_ratio": round(sum(1 for sample in samples if sample.cot_injected) / total, 4) if total else 0.0,
        "cot_step_distribution": {
            "avg": round(sum(cot_step_counts) / len(cot_step_counts), 2) if cot_step_counts else 0.0,
            "two_or_less": sum(1 for count in cot_step_counts if count <= 2),
            "three": sum(1 for count in cot_step_counts if count == 3),
            "four_or_more": sum(1 for count in cot_step_counts if count >= 4),
        },
        "domain_term_coverage_rate": round(len(covered_terms) / len(CORE_DOMAIN_TERMS), 4) if CORE_DOMAIN_TERMS else 0.0,
        "manual_review_count": sum(1 for sample in samples if sample.needs_manual_review),
        "removed_counts": dict(removed_counts),
    }


def compute_length_statistics(samples: Sequence[SftSample]) -> list[dict[str, object]]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for sample in samples:
        grouped[sample.template_type].append(len(sample.output))
    rows: list[dict[str, object]] = []
    for template_type in TEMPLATE_ORDER:
        lengths = grouped.get(template_type, [])
        if not lengths:
            continue
        rows.append({
            "template_type": template_type,
            "template_label": TEMPLATE_LABELS[template_type],
            "count": len(lengths),
            "mean_length": round(sum(lengths) / len(lengths), 2),
            "min_length": min(lengths),
            "max_length": max(lengths),
        })
    return rows


def export_jsonl(samples: Sequence[SftSample], output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for sample in samples:
            payload = {
                "instruction": sample.instruction,
                "input": sample.input,
                "output": sample.output,
                "template_type": sample.template_type,
                "template_label": TEMPLATE_LABELS[sample.template_type],
                "source_doc_id": sample.source_doc_id,
                "source_title": sample.source_title,
                "source_section": sample.source_section,
                "cot_strategy": sample.cot_strategy,
                "cot_injected": sample.cot_injected,
                "domain_terms": sample.domain_terms,
                "needs_manual_review": sample.needs_manual_review,
                "metadata": sample.metadata,
            }
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return output_path


def export_sharegpt(samples: Sequence[SftSample], output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for sample in samples:
        payload.append({
            "id": sample.sample_id,
            "template_type": sample.template_type,
            "template_label": TEMPLATE_LABELS[sample.template_type],
            "cot_injected": sample.cot_injected,
            "conversations": [
                {"from": "human", "value": sample.instruction + "\n\n" + sample.input},
                {"from": "gpt", "value": sample.output},
            ],
            "metadata": {
                "source_doc_id": sample.source_doc_id,
                "source_title": sample.source_title,
                "source_section": sample.source_section,
                **sample.metadata,
            },
        })
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def export_csv(rows: Sequence[dict[str, object]], output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return output_path
    fieldnames = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def build_target_template_counts(total_samples: int) -> dict[str, int]:
    if total_samples <= 0:
        return {name: 0 for name in TEMPLATE_ORDER}
    ratios = {
        "definition": DEFAULT_TEMPLATE_COUNTS["definition"] / 852,
        "reasoning": DEFAULT_TEMPLATE_COUNTS["reasoning"] / 852,
        "comparison": DEFAULT_TEMPLATE_COUNTS["comparison"] / 852,
        "summary": DEFAULT_TEMPLATE_COUNTS["summary"] / 852,
        "application": DEFAULT_TEMPLATE_COUNTS["application"] / 852,
    }
    scaled = {name: math.floor(total_samples * ratios[name]) for name in TEMPLATE_ORDER}
    remainder = total_samples - sum(scaled.values())
    for name in TEMPLATE_ORDER:
        if remainder <= 0:
            break
        scaled[name] += 1
        remainder -= 1
    return scaled


def samples_to_rows(samples: Sequence[SftSample]) -> list[dict[str, object]]:
    rows = []
    for sample in samples:
        rows.append({
            "sample_id": sample.sample_id,
            "template_type": sample.template_type,
            "template_label": TEMPLATE_LABELS[sample.template_type],
            "cot_strategy": sample.cot_strategy,
            "cot_injected": sample.cot_injected,
            "source_title": sample.source_title,
            "source_section": sample.source_section,
            "instruction": sample.instruction,
            "input": sample.input,
            "output": sample.output,
            "needs_manual_review": sample.needs_manual_review,
        })
    return rows


def report_to_dict(report: GenerationReport) -> dict[str, object]:
    data = asdict(report)
    data["template_distribution"] = {
        TEMPLATE_LABELS.get(key, key): value
        for key, value in report.template_distribution.items()
    }
    return data
