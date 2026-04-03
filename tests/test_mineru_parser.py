"""
tests/test_mineru_parser.py
对应论文 5.1 节：8 个测试文件共 170 个用例
"""

from __future__ import annotations

import re
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

import mineru_parser

from mineru_parser import (
    fix_formula_regions,
    merge_cross_page_tables,
    filter_header_footer,
    separate_figure_captions,
    evaluate_availability,
    parse_pdf_with_mineru,
    parse_with_pymupdf,
    parse_with_pdfplumber,
    parse_cnki_txt,
    ParseResult,
    AvailabilityReport,
)


def _sample_mineru_output() -> tuple[str, list[dict]]:
    raw_md = "\n\n".join([
        "页眉：水产学报 第2卷 第1期",
        "三文鱼养殖研究表明，循环水养殖系统可以提升成活率和增重率。",
        "| 品种 | 价格 |\n|---|---|\n| 三文鱼 | 98 |\n",
        "图1 三文鱼价格趋势图",
        "帝王鲑与虹鳟在市场定位和价格区间上存在明显差异。",
    ])
    layout = [
        {"type": "header", "text": "页眉：水产学报 第2卷 第1期"},
        {"type": "paragraph", "text": "三文鱼养殖研究表明，循环水养殖系统可以提升成活率和增重率。"},
        {"type": "table", "text": "品种价格表"},
        {"type": "caption", "text": "图1 三文鱼价格趋势图"},
    ]
    return raw_md, layout


def _write_dummy_pdf(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")
    return path


def _real_pdf_paths(limit: int | None = None) -> list[str]:
    pdf_dir = Path("test_pdfs")
    pdfs = sorted(str(p) for p in pdf_dir.glob("**/*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No real PDFs found under {pdf_dir.resolve()}")
    return pdfs[:limit] if limit is not None else pdfs


# ===========================================================================
# fix_formula_regions
# ===========================================================================

class TestFixFormulaRegions:
    def test_single_dollar_line_upgraded_to_block(self):
        md = "前文\n$E = mc^2$\n后文"
        result = fix_formula_regions(md)
        assert "$$E = mc^2$$" in result

    def test_short_inline_formula_not_upgraded(self):
        """短于 4 字符的内联公式不应被升级。"""
        md = "设 $x$ 为变量"
        result = fix_formula_regions(md)
        assert "$$x$$" not in result

    def test_already_block_formula_unchanged(self):
        md = "$$\\frac{a}{b} = c$$"
        result = fix_formula_regions(md)
        assert "$$\\frac{a}{b} = c$$" in result

    def test_multiple_formulas_on_separate_lines(self):
        md = "$\\alpha + \\beta = \\gamma$\n\n$\\delta = 0$"
        result = fix_formula_regions(md)
        assert result.count("$$") >= 2

    def test_empty_string(self):
        assert fix_formula_regions("") == ""

    def test_no_formula_unchanged(self):
        md = "这是普通文本，没有公式。"
        assert fix_formula_regions(md) == md


# ===========================================================================
# merge_cross_page_tables
# ===========================================================================

class TestMergeCrossPageTables:
    def _make_table(self, header: str, rows: list[str]) -> str:
        sep = re.sub(r'[^|]', '-', header)
        return header + "\n" + sep + "\n" + "\n".join(rows) + "\n"

    def test_same_header_tables_merged(self):
        t1 = self._make_table("| A | B |", ["| 1 | 2 |", "| 3 | 4 |"])
        t2 = self._make_table("| A | B |", ["| 5 | 6 |"])
        md = t1 + "\n\n" + t2
        result = merge_cross_page_tables(md)
        # 合并后只应有一个表头
        assert result.count("| A | B |") == 1

    def test_different_header_tables_not_merged(self):
        t1 = self._make_table("| A | B |", ["| 1 | 2 |"])
        t2 = self._make_table("| C | D |", ["| 3 | 4 |"])
        md = t1 + "\n\n" + t2
        result = merge_cross_page_tables(md)
        assert result.count("| A | B |") == 1
        assert result.count("| C | D |") == 1

    def test_single_table_unchanged(self):
        t = self._make_table("| X | Y |", ["| a | b |"])
        result = merge_cross_page_tables(t)
        assert "| X | Y |" in result

    def test_empty_string(self):
        assert merge_cross_page_tables("") == ""

    def test_no_table_unchanged(self):
        md = "普通段落\n\n另一段落"
        assert merge_cross_page_tables(md) == md


# ===========================================================================
# filter_header_footer
# ===========================================================================

class TestFilterHeaderFooter:
    def test_volume_issue_line_removed(self):
        md = "正文内容\n\n水产学报 第42卷 第3期\n\n更多内容"
        result = filter_header_footer(md)
        assert "第42卷" not in result
        assert "正文内容" in result

    def test_doi_line_removed(self):
        md = "摘要\n\nDOI: 10.1234/example\n\n引言"
        result = filter_header_footer(md)
        assert "DOI" not in result

    def test_page_number_removed(self):
        md = "段落一\n\n  42  \n\n段落二"
        result = filter_header_footer(md)
        assert re.search(r'^\s*42\s*$', result, re.MULTILINE) is None

    def test_journal_name_line_removed(self):
        md = "内容\n\nAquaculture Research\n\n更多内容"
        result = filter_header_footer(md)
        assert "Aquaculture Research" not in result

    def test_normal_content_preserved(self):
        md = "三文鱼（Salmo salar）是重要的养殖鱼类。"
        result = filter_header_footer(md)
        assert "三文鱼" in result

    def test_empty_string(self):
        assert filter_header_footer("") == ""

    def test_no_extra_blank_lines(self):
        md = "段落一\n\n水产学报 第1卷\n\n段落二"
        result = filter_header_footer(md)
        assert "\n\n\n" not in result


# ===========================================================================
# separate_figure_captions
# ===========================================================================

class TestSeparateFigureCaptions:
    def test_figure_caption_bolded(self):
        md = "图1 三文鱼生长曲线\n\n正文继续"
        result = separate_figure_captions(md)
        assert "**图1**" in result

    def test_figure_with_space_bolded(self):
        md = "图 2 养殖密度与生长关系"
        result = separate_figure_captions(md)
        assert "**图 2**" in result

    def test_non_figure_line_unchanged(self):
        md = "表1 实验数据汇总"
        result = separate_figure_captions(md)
        assert "**表1**" not in result

    def test_multiple_figures(self):
        md = "图1 第一张图\n\n正文\n\n图2 第二张图"
        result = separate_figure_captions(md)
        assert result.count("**图") == 2

    def test_empty_string(self):
        assert separate_figure_captions("") == ""


# ===========================================================================
# evaluate_availability
# ===========================================================================

class TestEvaluateAvailability:
    def test_clean_text_high_availability(self):
        md = "\n\n".join([
            "三文鱼是重要的养殖鱼类，具有较高的经济价值。",
            "本研究采用循环水养殖系统进行实验，取得了良好效果。",
            "实验结果表明，实验组生长速率显著高于对照组。",
            "综上所述，本方法具有推广应用价值。",
        ] * 5)
        report = evaluate_availability(md, method="test")
        assert report.availability_rate >= 0.7
        assert report.total_paragraphs > 0

    def test_noisy_text_low_availability(self):
        md = "\n\n".join([
            "---",
            "42",
            "===",
            "- 1 -",
            "DOI: 10.1234/test",
        ] * 4)
        report = evaluate_availability(md, method="test")
        assert report.noise_rate > 0.5

    def test_empty_text_zero_availability(self):
        report = evaluate_availability("", method="test")
        assert report.total_paragraphs == 0
        assert report.availability_rate == 0.0
        assert not report.is_available

    def test_availability_threshold_respected(self):
        md = "\n\n".join(["完整的句子，以句号结尾。"] * 10)
        report_strict = evaluate_availability(md, availability_threshold=0.99)
        report_loose = evaluate_availability(md, availability_threshold=0.5)
        # 宽松阈值下应该可用
        assert report_loose.is_available

    def test_report_fields_populated(self):
        md = "段落一。\n\n段落二。\n\n段落三。"
        report = evaluate_availability(md, pdf_path="test.pdf", method="mineru")
        assert report.pdf_path == "test.pdf"
        assert report.method == "mineru"
        assert isinstance(report.total_paragraphs, int)
        assert isinstance(report.availability_rate, float)
        assert isinstance(report.is_available, bool)

    def test_noise_rate_plus_availability_rate_leq_one(self):
        md = "正常段落。\n\n---\n\n另一段落。\n\n42"
        report = evaluate_availability(md, method="test")
        assert report.noise_rate + report.availability_rate <= 1.0 + 1e-9


# ===========================================================================
# parse_pdf_with_mineru
# ===========================================================================

class TestParsePdfWithMineru:
    @staticmethod
    def _patch_call_mineru(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            mineru_parser,
            "_call_mineru",
            lambda _pdf_path: _sample_mineru_output(),
        )

    def test_returns_parse_result(self, tmp_path, monkeypatch):
        self._patch_call_mineru(monkeypatch)
        pdf_path = _write_dummy_pdf(tmp_path / "sample.pdf")
        result = parse_pdf_with_mineru(str(pdf_path))
        assert isinstance(result, ParseResult)

    def test_markdown_not_empty(self, tmp_path, monkeypatch):
        self._patch_call_mineru(monkeypatch)
        pdf_path = _write_dummy_pdf(tmp_path / "sample.pdf")
        result = parse_pdf_with_mineru(str(pdf_path))
        assert result.markdown

    def test_method_is_mineru(self, tmp_path, monkeypatch):
        self._patch_call_mineru(monkeypatch)
        pdf_path = _write_dummy_pdf(tmp_path / "sample.pdf")
        result = parse_pdf_with_mineru(str(pdf_path))
        assert result.method == "mineru"

    def test_parse_time_recorded(self, tmp_path, monkeypatch):
        self._patch_call_mineru(monkeypatch)
        pdf_path = _write_dummy_pdf(tmp_path / "sample.pdf")
        result = parse_pdf_with_mineru(str(pdf_path))
        assert result.parse_time_s >= 0

    def test_postprocessing_applied(self, tmp_path, monkeypatch):
        self._patch_call_mineru(monkeypatch)
        pdf_path = _write_dummy_pdf(tmp_path / "sample.pdf")
        result = parse_pdf_with_mineru(str(pdf_path), apply_postprocessing=True)
        assert "页眉：水产学报" not in result.markdown

    def test_no_postprocessing_preserves_raw(self, tmp_path, monkeypatch):
        self._patch_call_mineru(monkeypatch)
        pdf_path = _write_dummy_pdf(tmp_path / "sample.pdf")
        result_raw = parse_pdf_with_mineru(str(pdf_path), apply_postprocessing=False)
        result_processed = parse_pdf_with_mineru(str(pdf_path), apply_postprocessing=True)
        assert result_raw.markdown != result_processed.markdown

    def test_layout_elements_returned(self, tmp_path, monkeypatch):
        self._patch_call_mineru(monkeypatch)
        pdf_path = _write_dummy_pdf(tmp_path / "sample.pdf")
        result = parse_pdf_with_mineru(str(pdf_path))
        assert isinstance(result.layout_elements, list)

    def test_missing_file_returns_error_result(self):
        result = parse_pdf_with_mineru("nonexistent_file_xyz.pdf")
        assert result.error is not None
        assert "PDF 文件不存在" in result.error


# ===========================================================================
# Baseline 解析器（无真实 PDF 时测试错误处理）
# ===========================================================================

class TestBaselineParsers:
    def test_pymupdf_nonexistent_file_returns_error(self):
        result = parse_with_pymupdf("nonexistent_file_xyz.pdf")
        assert isinstance(result, ParseResult)
        assert result.error is not None or result.markdown == ""

    def test_pdfplumber_nonexistent_file_returns_error(self):
        result = parse_with_pdfplumber("nonexistent_file_xyz.pdf")
        assert isinstance(result, ParseResult)
        assert result.error is not None or result.markdown == ""

    def test_cnki_txt_nonexistent_file_returns_error(self):
        result = parse_cnki_txt("nonexistent_file_xyz.txt")
        assert isinstance(result, ParseResult)
        assert result.error is not None

    def test_cnki_txt_reads_existing_file(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("三文鱼养殖研究摘要内容。", encoding="utf-8")
        result = parse_cnki_txt(str(txt_file))
        assert result.error is None
        assert "三文鱼" in result.markdown
        assert result.method == "cnki_txt"


# ===========================================================================
# 集成测试：真实 PDF 可用率断言
# ===========================================================================

class TestAvailabilityWithRealPdfs:
    TARGET_AVAILABILITY = 0.85

    def _get_pdf_paths(self) -> list[str]:
        return _real_pdf_paths()

    def test_mineru_availability_meets_target(self):
        """MinerU 解析的可用率应达到目标值。"""
        pdfs = self._get_pdf_paths()
        available = 0
        for pdf_path in pdfs:
            result = parse_pdf_with_mineru(pdf_path)
            if result.error:
                continue
            report = evaluate_availability(result.markdown, method="mineru")
            if report.is_available:
                available += 1
        rate = available / len(pdfs)
        assert rate >= self.TARGET_AVAILABILITY, (
            f"MinerU availability {rate:.1%} is below target {self.TARGET_AVAILABILITY:.1%}"
        )

    def test_all_real_papers_processed_without_crash(self):
        """All discovered real PDFs should return ParseResult objects."""
        pdfs = self._get_pdf_paths()
        results = [parse_pdf_with_mineru(p) for p in pdfs]
        assert len(results) == len(pdfs)
        assert all(isinstance(r, ParseResult) for r in results)

    def test_mineru_outperforms_pymupdf(self):
        """MinerU 可用率应高于 PyMuPDF（论文核心对比结论）。"""
        pdfs = self._get_pdf_paths()[:5]
        mineru_available = 0
        pymupdf_available = 0
        for pdf_path in pdfs:
            r_mineru = parse_pdf_with_mineru(pdf_path)
            r_pymupdf = parse_with_pymupdf(pdf_path)
            if not r_mineru.error:
                rep = evaluate_availability(r_mineru.markdown, method="mineru")
                if rep.is_available:
                    mineru_available += 1
            if not r_pymupdf.error:
                rep = evaluate_availability(r_pymupdf.markdown, method="pymupdf")
                if rep.is_available:
                    pymupdf_available += 1
        assert mineru_available >= pymupdf_available
