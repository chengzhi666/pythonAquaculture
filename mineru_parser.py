"""
MinerU 深度版面解析管线
对应论文 4.5 + 5.3 节

用法：
    from mineru_parser import parse_pdf_with_mineru, evaluate_availability

安装依赖：
    pip install magic-pdf[full] --extra-index-url https://wheels.myhloli.com
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    pdf_path: str
    markdown: str
    layout_elements: list[dict] = field(default_factory=list)
    parse_time_s: float = 0.0
    method: str = "mineru"
    error: Optional[str] = None


@dataclass
class AvailabilityReport:
    pdf_path: str
    method: str
    total_paragraphs: int
    complete_paragraphs: int
    noise_paragraphs: int
    availability_rate: float   # complete / total
    noise_rate: float          # noise / total
    is_available: bool         # availability_rate >= threshold


# ---------------------------------------------------------------------------
# MinerU 调用
# ---------------------------------------------------------------------------

def _call_mineru(pdf_path: str) -> tuple[str, list[dict]]:
    """
    调用 MinerU 1.3.x 解析 PDF，返回 (markdown_text, layout_elements)。
    依赖：pip install magic-pdf[full] --extra-index-url https://wheels.myhloli.com
    """
    from magic_pdf.config.make_content_config import DropMode
    from magic_pdf.data.data_reader_writer import FileBasedDataWriter
    from magic_pdf.data.dataset import PymuDocDataset
    from magic_pdf.dict2md import ocr_mkcontent
    from magic_pdf.libs import language as language_mod
    from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
    from magic_pdf.post_proc import para_split_v3

    pdf_bytes = Path(pdf_path).read_bytes()
    img_dir = str(Path(pdf_path).parent / "images")

    # fast-langdetect may fail with newer NumPy; fall back to Chinese so markdown generation can continue.
    original_detect_lang = language_mod.detect_lang

    def safe_detect_lang(text: str) -> str:
        try:
            return original_detect_lang(text)
        except Exception:
            return "zh"

    language_mod.detect_lang = safe_detect_lang
    ocr_mkcontent.detect_lang = safe_detect_lang
    para_split_v3.detect_lang = safe_detect_lang

    def run_pipeline(formula_enable: bool) -> tuple[str, list[dict]]:
        image_writer = FileBasedDataWriter(img_dir)
        ds = PymuDocDataset(pdf_bytes)
        infer_result = ds.apply(
            doc_analyze,
            ocr=False,
            lang=getattr(ds, "_lang", None),
            layout_model="doclayout_yolo",
            formula_enable=formula_enable,
            table_enable=True,
        )
        pipe_result = infer_result.pipe_txt_mode(
            image_writer,
            debug_mode=True,
            lang=getattr(ds, "_lang", None),
        )
        md_content = pipe_result.get_markdown(Path(img_dir).name, drop_mode=DropMode.NONE)

        layout_elements = []
        try:
            mid = json.loads(pipe_result.get_middle_json())
            for page_info in mid.get("pdf_info", []):
                for block in page_info.get("preproc_blocks", []):
                    layout_elements.append({
                        "type": block.get("type", "unknown"),
                        "text": block.get("text", ""),
                    })
        except Exception:
            pass
        return md_content, layout_elements

    try:
        return run_pipeline(formula_enable=True)
    except Exception as exc:
        message = str(exc)
        if "cache_position" not in message and "unexpected keyword argument" not in message:
            raise
        return run_pipeline(formula_enable=False)


# ---------------------------------------------------------------------------
# 4 项后处理规则
# ---------------------------------------------------------------------------

def fix_formula_regions(md: str) -> str:
    """
    修复 MinerU 输出中的公式区域：
    - 将孤立的 $ ... $ 行包裹为 $$ ... $$ 块
    - 修复常见的 OCR 公式乱码（希腊字母替换）
    """
    # 将单行内联公式升级为块级公式（避免渲染错误）
    md = re.sub(
        r'(?m)^[ \t]*\$([^$\n]{4,})\$[ \t]*$',
        r'$$\1$$',
        md
    )
    # 修复常见 OCR 乱码：α β γ δ
    replacements = {
        r'\bα\b': 'α', r'\bβ\b': 'β', r'\bγ\b': 'γ', r'\bδ\b': 'δ',
        r'(?<!\$)\\alpha(?!\w)': 'α',
        r'(?<!\$)\\beta(?!\w)': 'β',
    }
    for pattern, repl in replacements.items():
        md = re.sub(pattern, repl, md)
    return md

def merge_cross_page_tables(md: str) -> str:
    """
    合并跨页表格：检测连续两个 Markdown 表格块，
    若表头相同则合并（去掉第二个表格的表头行）。
    """
    # 匹配 Markdown 表格块（至少含表头+分隔行+1数据行）
    table_pattern = re.compile(
        r'(\|[^\n]+\|\n\|[-| :]+\|\n(?:\|[^\n]+\|\n)+)',
        re.MULTILINE
    )
    tables = list(table_pattern.finditer(md))

    if len(tables) < 2:
        return md

    result = md
    # 从后往前处理，避免偏移量错乱
    for i in range(len(tables) - 1, 0, -1):
        t_prev = tables[i - 1]
        t_curr = tables[i]

        # 提取表头（第一行）
        prev_header = t_prev.group(0).split('\n')[0]
        curr_header = t_curr.group(0).split('\n')[0]

        # 两表之间只有空行或页码行（跨页特征）
        between = result[t_prev.end():t_curr.start()]
        is_cross_page = bool(re.match(r'^[\s\d\-—]*$', between))

        if prev_header == curr_header and is_cross_page:
            # 去掉第二个表格的表头+分隔行
            curr_lines = t_curr.group(0).split('\n')
            merged_rows = '\n'.join(curr_lines[2:])  # 跳过表头和分隔行
            result = result[:t_curr.start()] + merged_rows + result[t_curr.end():]

    return result


def filter_header_footer(md: str) -> str:
    """
    过滤页眉页脚：
    - 位置特征：短行（< 30 字符）且包含期刊名/卷期/页码关键词
    - 关键词：卷、期、页、Vol、No、DOI、ISSN、页眉、页脚
    """
    header_footer_patterns = [
        # 期刊卷期格式
        r'(?m)^.{0,50}(第\s*\d+\s*[卷期]|Vol\.\s*\d+|No\.\s*\d+).{0,50}$',
        # DOI / ISSN 行
        r'(?m)^.{0,80}(DOI|ISSN|doi\.org).{0,80}$',
        # 纯页码行（单独一行，只有数字或 "- 数字 -"）
        r'(?m)^[ \t]*[-—]?\s*\d{1,4}\s*[-—]?[ \t]*$',
        # 明确标注的页眉页脚
        r'(?m)^.{0,20}(页眉|页脚|Header|Footer).{0,20}$',
        # 水产学报、渔业科学等期刊名短行
        r'(?m)^.{0,30}(水产学报|渔业科学|中国水产|Aquaculture|Fisheries).{0,30}$',
    ]
    for pattern in header_footer_patterns:
        md = re.sub(pattern, '', md)
    # 清理多余空行
    md = re.sub(r'\n{3,}', '\n\n', md)
    return md


def separate_figure_captions(md: str) -> str:
    """
    分离图注：将正文中混入的图注单独成段，
    并统一格式为 **图N** 描述文字。
    """
    # 匹配 "图1"、"图 2"、"Figure 1" 等开头的行
    caption_pattern = re.compile(
        r'(?m)^(图\s*\d+[\s\S]{0,200}?(?=\n\n|\n图|\n表|\Z))',
        re.MULTILINE
    )
    # 将图注包裹为独立段落并加粗编号
    def format_caption(m: re.Match) -> str:
        text = m.group(1).strip()
        # 统一格式：**图N** 后接描述
        text = re.sub(r'^(图\s*\d+)', r'**\1**', text)
        return f'\n\n{text}\n\n'

    md = caption_pattern.sub(format_caption, md)
    md = re.sub(r'\n{3,}', '\n\n', md)
    return md


def _apply_postprocessing(md: str) -> str:
    """按顺序应用 4 项后处理规则。"""
    md = fix_formula_regions(md)
    md = merge_cross_page_tables(md)
    md = filter_header_footer(md)
    md = separate_figure_captions(md)
    return md


# ---------------------------------------------------------------------------
# 主解析入口
# ---------------------------------------------------------------------------

def parse_pdf_with_mineru(pdf_path: str, apply_postprocessing: bool = True) -> ParseResult:
    """
    解析单篇 PDF，返回 ParseResult。

    Args:
        pdf_path: PDF 文件路径
        apply_postprocessing: 是否应用 4 项后处理规则（默认 True）

    Returns:
        ParseResult 对象，包含 markdown 文本和版面元素
    """
    t0 = time.time()
    try:
        pdf = Path(pdf_path)
        if not pdf.exists():
            raise FileNotFoundError(f"PDF 文件不存在：{pdf}")

        raw_md, layout_elements = _call_mineru(str(pdf))
        if apply_postprocessing:
            processed_md = _apply_postprocessing(raw_md)
        else:
            processed_md = raw_md
        return ParseResult(
            pdf_path=pdf_path,
            markdown=processed_md,
            layout_elements=layout_elements,
            parse_time_s=time.time() - t0,
            method="mineru",
        )
    except Exception as e:
        return ParseResult(
            pdf_path=pdf_path,
            markdown="",
            parse_time_s=time.time() - t0,
            method="mineru",
            error=str(e),
        )


# ---------------------------------------------------------------------------
# 可用率评估
# ---------------------------------------------------------------------------

# 噪声段落特征（正则）
_NOISE_PATTERNS = [
    re.compile(r'^[-—=\s]{3,}$'),                          # 纯分隔线
    re.compile(r'^\s*\d{1,4}\s*$'),                        # 纯页码
    re.compile(r'[^\u4e00-\u9fff\w]{5,}'),                 # 连续乱码字符
    re.compile(r'(DOI|ISSN|doi\.org)', re.IGNORECASE),     # 元数据行
    re.compile(r'^.{1,5}$'),                               # 极短段落（< 5 字符）
]

# 不完整段落特征（句子未结束）
_INCOMPLETE_ENDINGS = re.compile(r'[，,、；;：:\(（【\[]$')


def evaluate_availability(
    md: str,
    pdf_path: str = "",
    method: str = "mineru",
    availability_threshold: float = 0.85,
) -> AvailabilityReport:
    """
    评估 Markdown 文本的可用率。

    判定逻辑：
    - 将文本按空行分段
    - 噪声段落：匹配 _NOISE_PATTERNS 之一
    - 不完整段落：以标点符号结尾（句子被截断）
    - 可用率 = 完整段落数 / 总段落数
    - is_available = 可用率 >= availability_threshold

    Returns:
        AvailabilityReport
    """
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', md) if p.strip()]
    total = len(paragraphs)
    if total == 0:
        return AvailabilityReport(
            pdf_path=pdf_path, method=method,
            total_paragraphs=0, complete_paragraphs=0,
            noise_paragraphs=0, availability_rate=0.0,
            noise_rate=0.0, is_available=False,
        )

    noise_count = 0
    incomplete_count = 0

    for para in paragraphs:
        is_noise = any(p.search(para) for p in _NOISE_PATTERNS)
        is_incomplete = bool(_INCOMPLETE_ENDINGS.search(para))
        if is_noise:
            noise_count += 1
        elif is_incomplete:
            incomplete_count += 1

    complete = total - noise_count - incomplete_count
    availability_rate = complete / total
    noise_rate = noise_count / total

    return AvailabilityReport(
        pdf_path=pdf_path,
        method=method,
        total_paragraphs=total,
        complete_paragraphs=complete,
        noise_paragraphs=noise_count,
        availability_rate=round(availability_rate, 4),
        noise_rate=round(noise_rate, 4),
        is_available=availability_rate >= availability_threshold,
    )


# ---------------------------------------------------------------------------
# Baseline 解析器（用于对比实验）
# ---------------------------------------------------------------------------

def parse_with_pymupdf(pdf_path: str) -> ParseResult:
    """使用 PyMuPDF (fitz) 解析 PDF。"""
    t0 = time.time()
    try:
        import fitz  # pip install pymupdf
        doc = fitz.open(pdf_path)
        pages = []
        for page in doc:
            pages.append(page.get_text("text"))
        doc.close()
        md = "\n\n".join(pages)
        return ParseResult(pdf_path=pdf_path, markdown=md,
                           parse_time_s=time.time() - t0, method="pymupdf")
    except ImportError:
        return ParseResult(pdf_path=pdf_path, markdown="",
                           parse_time_s=time.time() - t0, method="pymupdf",
                           error="pymupdf not installed")
    except Exception as e:
        return ParseResult(pdf_path=pdf_path, markdown="",
                           parse_time_s=time.time() - t0, method="pymupdf",
                           error=str(e))


def parse_with_pdfplumber(pdf_path: str) -> ParseResult:
    """使用 pdfplumber 解析 PDF。"""
    t0 = time.time()
    try:
        import pdfplumber  # pip install pdfplumber
        pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
        md = "\n\n".join(pages)
        return ParseResult(pdf_path=pdf_path, markdown=md,
                           parse_time_s=time.time() - t0, method="pdfplumber")
    except ImportError:
        return ParseResult(pdf_path=pdf_path, markdown="",
                           parse_time_s=time.time() - t0, method="pdfplumber",
                           error="pdfplumber not installed")
    except Exception as e:
        return ParseResult(pdf_path=pdf_path, markdown="",
                           parse_time_s=time.time() - t0, method="pdfplumber",
                           error=str(e))


def parse_cnki_txt(txt_path: str) -> ParseResult:
    """读取 CNKI 导出的 TXT 全文。"""
    t0 = time.time()
    try:
        text = Path(txt_path).read_text(encoding="utf-8", errors="replace")
        return ParseResult(pdf_path=txt_path, markdown=text,
                           parse_time_s=time.time() - t0, method="cnki_txt")
    except Exception as e:
        return ParseResult(pdf_path=txt_path, markdown="",
                           parse_time_s=time.time() - t0, method="cnki_txt",
                           error=str(e))
