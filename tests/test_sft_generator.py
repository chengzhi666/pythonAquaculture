from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sft_generator import (
    ParsedBlock,
    build_sample,
    export_jsonl,
    export_sharegpt,
    generate_sft_dataset,
    inject_cot,
    load_parsed_docs,
    quality_filter_sample,
)


def make_block(
    title: str = "三文鱼循环水养殖技术研究",
    section_title: str = "结果与分析",
    content: str | None = None,
) -> ParsedBlock:
    content = content or (
        "三文鱼在循环水养殖系统中表现出较高的生长稳定性。"
        "研究表明，养殖密度、水温和溶解氧共同影响摄食率与增重率。"
        "当溶解氧保持在较高水平时，三文鱼的饲料系数更低，成活率更高。"
        "因此，循环水养殖条件下的精准水质调控对生产管理具有直接意义。"
    )
    return ParsedBlock(
        doc_id="block-1",
        title=title,
        section_title=section_title,
        content=content,
        source_path="results/demo.md",
        source_type="mineru_markdown",
        keywords=["三文鱼", "循环水养殖", "溶解氧"],
    )


def test_load_parsed_docs_reads_markdown_and_cnki(tmp_path: Path) -> None:
    markdown_dir = tmp_path / "markdown"
    markdown_dir.mkdir()
    (markdown_dir / "paper.md").write_text(
        "# 三文鱼健康养殖\n\n## 摘要\n\n三文鱼养殖与溶解氧调控密切相关，"
        "高密度养殖条件下需要持续监测水温与成活率。\n",
        encoding="utf-8",
    )

    cnki_path = tmp_path / "CNKI_三文鱼.tsv"
    cnki_path.write_text(
        "1\t三文鱼价格趋势研究\t张三\t某研究院\t2026-01-01\t水产学报\tCNKI\t三文鱼;价格;市场\t"
        "本文分析三文鱼市场价格波动与进口供应之间的关系，并讨论零售价格变化。\thttps://example.com\n",
        encoding="gbk",
    )

    blocks = load_parsed_docs(markdown_dirs=[markdown_dir], cnki_paths=[cnki_path])

    assert len(blocks) >= 2
    assert {block.source_type for block in blocks} == {"mineru_markdown", "cnki_abstract"}


def test_load_parsed_docs_requires_real_markdown_input(tmp_path: Path) -> None:
    cnki_path = tmp_path / "CNKI_only.tsv"
    cnki_path.write_text(
        "1\t三文鱼价格趋势研究\t张三\t某研究院\t2026-01-01\t水产学报\tCNKI\t三文鱼;价格;市场\t"
        "本文分析三文鱼市场价格波动与进口供应之间的关系，并讨论零售价格变化。\thttps://example.com\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Markdown directory"):
        load_parsed_docs(markdown_dirs=[], cnki_paths=[cnki_path])


def test_load_parsed_docs_rejects_fake_markdown_marker(tmp_path: Path) -> None:
    markdown_dir = tmp_path / "markdown"
    markdown_dir.mkdir()
    (markdown_dir / "stub_paper_01.md").write_text(
        "# 示例文档（STUB）\n\n这是一个不应该被加载的占位文件。",
        encoding="utf-8",
    )

    cnki_path = tmp_path / "CNKI_real.tsv"
    cnki_path.write_text(
        "1\t三文鱼价格趋势研究\t张三\t某研究院\t2026-01-01\t水产学报\tCNKI\t三文鱼;价格;市场\t"
        "本文分析三文鱼市场价格波动与进口供应之间的关系，并讨论零售价格变化。\thttps://example.com\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="forbidden fake marker"):
        load_parsed_docs(markdown_dirs=[markdown_dir], cnki_paths=[cnki_path])


def test_inject_cot_for_reasoning_has_required_markers() -> None:
    output, injected, strategy = inject_cot(
        "三文鱼养殖成效受水温和溶解氧共同影响。",
        template_type="reasoning",
        key_sentences=["水温影响摄食率", "溶解氧影响成活率", "养殖密度影响应激水平"],
    )

    assert injected is True
    assert strategy == "forced"
    assert "【分析过程】" in output
    assert "【结论】" in output
    assert "首先" in output


def test_generate_sft_dataset_matches_requested_counts() -> None:
    blocks = [
        make_block(),
        make_block(
            title="虹鳟饲料配方优化研究",
            content=(
                "虹鳟在高蛋白饲料下具有更高的增重率。"
                "研究对比了不同饲料配方对成活率、摄食率和出肉率的影响。"
                "结果显示，蛋白水平与养殖成本控制存在平衡关系。"
                "该结论可用于优化工厂化养殖中的投喂策略。"
            ),
        ),
    ]

    target_counts = {
        "definition": 2,
        "reasoning": 2,
        "comparison": 2,
        "summary": 2,
        "application": 2,
    }
    samples, report = generate_sft_dataset(blocks, template_counts=target_counts)

    assert len(samples) == 10
    assert Counter(sample.template_type for sample in samples) == target_counts
    assert report.total_samples_after_filter == 10


def test_build_sample_variant_changes_context_or_focus() -> None:
    block = make_block(
        content=(
            "三文鱼循环水养殖系统需要稳定控制水温和溶解氧。"
            "高密度养殖条件下，饲料系数和成活率会随水质波动变化。"
            "研究还比较了不同养殖密度对生长性能和应激水平的影响。"
            "结果表明精准水质调控有助于降低饲料系数并提升成活率。"
            "进一步分析发现，不同管理策略对应的市场供应稳定性也存在差异。"
        ),
    )

    sample_0 = build_sample(block, template_type="reasoning", variant=0)
    sample_1 = build_sample(block, template_type="reasoning", variant=1)

    assert sample_0.input != sample_1.input or sample_0.instruction != sample_1.instruction


def test_quality_filter_rejects_duplicate_and_domain_irrelevant() -> None:
    sample = build_sample(make_block(), template_type="definition", variant=0)
    registry = {}
    removed = Counter()

    assert quality_filter_sample(sample, registry, removed) is True
    assert quality_filter_sample(sample, registry, removed) is False
    assert removed["duplicate"] == 1

    irrelevant_block = make_block(
        title="通用管理文本",
        section_title="摘要",
        content="该文本讨论研究方法、数据分析和整体流程，但不涉及任何水产养殖术语。",
    )
    irrelevant_sample = build_sample(irrelevant_block, template_type="summary", variant=0)
    registry = {}
    removed = Counter()
    assert quality_filter_sample(irrelevant_sample, registry, removed) is False
    assert removed["domain_irrelevant"] == 1


def test_export_jsonl_and_sharegpt(tmp_path: Path) -> None:
    blocks = [make_block()]
    samples, _ = generate_sft_dataset(
        blocks,
        template_counts={
            "definition": 1,
            "reasoning": 1,
            "comparison": 1,
            "summary": 1,
            "application": 1,
        },
    )

    jsonl_path = tmp_path / "dataset.jsonl"
    sharegpt_path = tmp_path / "dataset_sharegpt.json"
    export_jsonl(samples, jsonl_path)
    export_sharegpt(samples, sharegpt_path)

    jsonl_lines = [line for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    sharegpt_payload = json.loads(sharegpt_path.read_text(encoding="utf-8"))

    assert len(jsonl_lines) == 5
    assert len(sharegpt_payload) == 5
    assert "instruction" in json.loads(jsonl_lines[0])
    assert "conversations" in sharegpt_payload[0]
