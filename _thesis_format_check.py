"""
中国农业大学学位论文格式审查脚本
对照《中国农业大学研究生学位论文格式及书写规范（2025年修订）》
"""
import zipfile
import xml.etree.ElementTree as ET
import re
import json
from pathlib import Path
from collections import defaultdict

DOCX_PATH = r"D:\Onedrive\桌面\杨志诚毕业论文1.docx"

NSMAP = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
}

# ---- 农大规范常量 ----
# 字号对照表 (half-points → 中文字号)
HPSIZE_TO_CN = {
    44: "小二", 36: "小三", 32: "三号", 28: "四号",
    24: "小四", 21: "五号", 18: "小五", 16: "六号",
    # pt 直接值
}

def hp_to_pt(hp):
    """半磅值 → pt"""
    return hp / 2 if hp else None

def twips_to_mm(tw):
    """缇 → mm"""
    return round(tw / 56.692913, 1) if tw else None

def twips_to_pt(tw):
    """缇 → pt"""
    return round(tw / 20, 1) if tw else None

def emu_to_mm(emu):
    """EMU → mm"""
    return round(emu / 914400 * 25.4, 1) if emu else None

def get_text(para_elem):
    """获取段落纯文本"""
    texts = []
    for t in para_elem.iter(f'{{{NSMAP["w"]}}}t'):
        texts.append(t.text or "")
    return "".join(texts).strip()

def get_run_fonts(run_elem):
    """获取 run 的字体信息"""
    rpr = run_elem.find(f'{{{NSMAP["w"]}}}rPr')
    if rpr is None:
        return {}
    fonts = {}
    rf = rpr.find(f'{{{NSMAP["w"]}}}rFonts')
    if rf is not None:
        fonts["eastAsia"] = rf.get(f'{{{NSMAP["w"]}}}eastAsia', '')
        fonts["ascii"] = rf.get(f'{{{NSMAP["w"]}}}ascii', '')
        fonts["hAnsi"] = rf.get(f'{{{NSMAP["w"]}}}hAnsi', '')
    sz = rpr.find(f'{{{NSMAP["w"]}}}sz')
    if sz is not None:
        fonts["sz_hp"] = int(sz.get(f'{{{NSMAP["w"]}}}val', '0'))
    szcs = rpr.find(f'{{{NSMAP["w"]}}}szCs')
    if szcs is not None:
        fonts["szCs_hp"] = int(szcs.get(f'{{{NSMAP["w"]}}}val', '0'))
    b = rpr.find(f'{{{NSMAP["w"]}}}b')
    if b is not None:
        val = b.get(f'{{{NSMAP["w"]}}}val', 'true')
        fonts["bold"] = val != '0' and val != 'false'
    return fonts

def get_para_props(para_elem):
    """获取段落格式属性"""
    ppr = para_elem.find(f'{{{NSMAP["w"]}}}pPr')
    props = {}
    if ppr is None:
        return props
    # 对齐方式
    jc = ppr.find(f'{{{NSMAP["w"]}}}jc')
    if jc is not None:
        props["jc"] = jc.get(f'{{{NSMAP["w"]}}}val', '')
    # 样式
    pstyle = ppr.find(f'{{{NSMAP["w"]}}}pStyle')
    if pstyle is not None:
        props["style"] = pstyle.get(f'{{{NSMAP["w"]}}}val', '')
    # 大纲级别
    outlvl = ppr.find(f'{{{NSMAP["w"]}}}outlineLvl')
    if outlvl is not None:
        props["outlineLvl"] = int(outlvl.get(f'{{{NSMAP["w"]}}}val', '9'))
    # 行距
    spacing = ppr.find(f'{{{NSMAP["w"]}}}spacing')
    if spacing is not None:
        props["lineSpacing"] = spacing.get(f'{{{NSMAP["w"]}}}line', '')
        props["lineRule"] = spacing.get(f'{{{NSMAP["w"]}}}lineRule', '')
        props["beforeSpacing"] = spacing.get(f'{{{NSMAP["w"]}}}before', '')
        props["afterSpacing"] = spacing.get(f'{{{NSMAP["w"]}}}after', '')
        props["beforeLines"] = spacing.get(f'{{{NSMAP["w"]}}}beforeLines', '')
        props["afterLines"] = spacing.get(f'{{{NSMAP["w"]}}}afterLines', '')
    # 首行缩进
    ind = ppr.find(f'{{{NSMAP["w"]}}}ind')
    if ind is not None:
        props["firstLine"] = ind.get(f'{{{NSMAP["w"]}}}firstLine', '')
        props["firstLineChars"] = ind.get(f'{{{NSMAP["w"]}}}firstLineChars', '')
        props["left"] = ind.get(f'{{{NSMAP["w"]}}}left', '')
    # 段落字体
    rpr = ppr.find(f'{{{NSMAP["w"]}}}rPr')
    if rpr is not None:
        rf = rpr.find(f'{{{NSMAP["w"]}}}rFonts')
        if rf is not None:
            props["pFontEA"] = rf.get(f'{{{NSMAP["w"]}}}eastAsia', '')
            props["pFontAscii"] = rf.get(f'{{{NSMAP["w"]}}}ascii', '')
        sz = rpr.find(f'{{{NSMAP["w"]}}}sz')
        if sz is not None:
            props["pSz_hp"] = int(sz.get(f'{{{NSMAP["w"]}}}val', '0'))
    return props

def classify_heading(text, props):
    """判断段落是否为标题及级别"""
    style = props.get("style", "")
    outline = props.get("outlineLvl", 9)

    # 通过样式识别
    if re.match(r"(?i)heading\s*1|标题\s*1", style) or outline == 0:
        return 1
    if re.match(r"(?i)heading\s*2|标题\s*2", style) or outline == 1:
        return 2
    if re.match(r"(?i)heading\s*3|标题\s*3", style) or outline == 2:
        return 3

    # 通过文本模式识别
    if re.match(r"第[一二三四五六七八九十]+章\s", text):
        return 1
    if re.match(r"\d+\.\d+\s", text) and not re.match(r"\d+\.\d+\.\d+", text):
        return 2
    if re.match(r"\d+\.\d+\.\d+\s", text):
        return 3
    return 0

def parse_styles(zf):
    """解析 styles.xml 获取样式定义"""
    styles = {}
    try:
        raw = zf.read("word/styles.xml")
    except KeyError:
        return styles
    root = ET.fromstring(raw)
    for st in root.findall(f'{{{NSMAP["w"]}}}style'):
        sid = st.get(f'{{{NSMAP["w"]}}}styleId', '')
        name_elem = st.find(f'{{{NSMAP["w"]}}}name')
        sname = name_elem.get(f'{{{NSMAP["w"]}}}val', '') if name_elem is not None else sid
        stype = st.get(f'{{{NSMAP["w"]}}}type', '')

        info = {"id": sid, "name": sname, "type": stype}

        # 字体字号
        rpr = st.find(f'{{{NSMAP["w"]}}}rPr')
        if rpr is not None:
            rf = rpr.find(f'{{{NSMAP["w"]}}}rFonts')
            if rf is not None:
                info["eastAsia"] = rf.get(f'{{{NSMAP["w"]}}}eastAsia', '')
                info["ascii"] = rf.get(f'{{{NSMAP["w"]}}}ascii', '')
            sz = rpr.find(f'{{{NSMAP["w"]}}}sz')
            if sz is not None:
                info["sz_hp"] = int(sz.get(f'{{{NSMAP["w"]}}}val', '0'))
            b = rpr.find(f'{{{NSMAP["w"]}}}b')
            if b is not None:
                info["bold"] = True

        # 段落属性
        ppr = st.find(f'{{{NSMAP["w"]}}}pPr')
        if ppr is not None:
            jc = ppr.find(f'{{{NSMAP["w"]}}}jc')
            if jc is not None:
                info["jc"] = jc.get(f'{{{NSMAP["w"]}}}val', '')
            spacing = ppr.find(f'{{{NSMAP["w"]}}}spacing')
            if spacing is not None:
                info["line"] = spacing.get(f'{{{NSMAP["w"]}}}line', '')
                info["lineRule"] = spacing.get(f'{{{NSMAP["w"]}}}lineRule', '')
                info["before"] = spacing.get(f'{{{NSMAP["w"]}}}before', '')
                info["after"] = spacing.get(f'{{{NSMAP["w"]}}}after', '')
            outlvl = ppr.find(f'{{{NSMAP["w"]}}}outlineLvl')
            if outlvl is not None:
                info["outlineLvl"] = int(outlvl.get(f'{{{NSMAP["w"]}}}val', '9'))

        styles[sid] = info
    return styles

def parse_section_props(zf):
    """解析页面设置（纸张大小、边距）"""
    raw = zf.read("word/document.xml")
    root = ET.fromstring(raw)
    body = root.find(f'{{{NSMAP["w"]}}}body')
    results = []

    for sectPr in body.iter(f'{{{NSMAP["w"]}}}sectPr'):
        sec = {}
        pgSz = sectPr.find(f'{{{NSMAP["w"]}}}pgSz')
        if pgSz is not None:
            sec["pageW_mm"] = twips_to_mm(int(pgSz.get(f'{{{NSMAP["w"]}}}w', '0')))
            sec["pageH_mm"] = twips_to_mm(int(pgSz.get(f'{{{NSMAP["w"]}}}h', '0')))
        pgMar = sectPr.find(f'{{{NSMAP["w"]}}}pgMar')
        if pgMar is not None:
            sec["marginTop_mm"] = twips_to_mm(int(pgMar.get(f'{{{NSMAP["w"]}}}top', '0')))
            sec["marginBottom_mm"] = twips_to_mm(int(pgMar.get(f'{{{NSMAP["w"]}}}bottom', '0')))
            sec["marginLeft_mm"] = twips_to_mm(int(pgMar.get(f'{{{NSMAP["w"]}}}left', '0')))
            sec["marginRight_mm"] = twips_to_mm(int(pgMar.get(f'{{{NSMAP["w"]}}}right', '0')))
            sec["header_mm"] = twips_to_mm(int(pgMar.get(f'{{{NSMAP["w"]}}}header', '0')))
            sec["footer_mm"] = twips_to_mm(int(pgMar.get(f'{{{NSMAP["w"]}}}footer', '0')))

        # 页眉页脚引用
        for hdr in sectPr.findall(f'{{{NSMAP["w"]}}}headerReference'):
            htype = hdr.get(f'{{{NSMAP["w"]}}}type', '')
            sec[f"header_{htype}"] = hdr.get(f'{{{NSMAP["r"]}}}id', '')
        for ftr in sectPr.findall(f'{{{NSMAP["w"]}}}footerReference'):
            ftype = ftr.get(f'{{{NSMAP["w"]}}}type', '')
            sec[f"footer_{ftype}"] = ftr.get(f'{{{NSMAP["r"]}}}id', '')

        # 页码格式
        pgNumType = sectPr.find(f'{{{NSMAP["w"]}}}pgNumType')
        if pgNumType is not None:
            sec["pgNumFmt"] = pgNumType.get(f'{{{NSMAP["w"]}}}fmt', '')
            sec["pgNumStart"] = pgNumType.get(f'{{{NSMAP["w"]}}}start', '')

        results.append(sec)
    return results

def check_headers(zf):
    """检查页眉内容"""
    headers = []
    rels_raw = zf.read("word/_rels/document.xml.rels")
    rels_root = ET.fromstring(rels_raw)
    ns_rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    hdr_files = {}
    for rel in rels_root.findall(f'{{{ns_rel}}}Relationship'):
        rid = rel.get("Id", "")
        target = rel.get("Target", "")
        if "header" in target.lower():
            hdr_files[rid] = target

    for rid, target in hdr_files.items():
        fpath = f"word/{target}" if not target.startswith("word/") else target
        try:
            raw = zf.read(fpath)
        except KeyError:
            continue
        root = ET.fromstring(raw)
        texts = []
        for p in root.findall(f'.//{{{NSMAP["w"]}}}p'):
            t = get_text(p)
            if t:
                texts.append(t)
                # 检查字体字号
                for run in p.findall(f'{{{NSMAP["w"]}}}r'):
                    rf = get_run_fonts(run)
                    if rf:
                        texts.append(f"  [字体: {rf}]")
        headers.append({"rid": rid, "file": target, "texts": texts})
    return headers

def check_tables(body):
    """检查表格格式（三线表）"""
    issues = []
    tbl_idx = 0
    for tbl in body.findall(f'.//{{{NSMAP["w"]}}}tbl'):
        tbl_idx += 1
        tpr = tbl.find(f'{{{NSMAP["w"]}}}tblPr')
        borders = None
        if tpr is not None:
            borders = tpr.find(f'{{{NSMAP["w"]}}}tblBorders')

        if borders is not None:
            border_info = {}
            for side in ["top", "bottom", "left", "right", "insideH", "insideV"]:
                b = borders.find(f'{{{NSMAP["w"]}}}{side}')
                if b is not None:
                    bval = b.get(f'{{{NSMAP["w"]}}}val', 'none')
                    bsz = b.get(f'{{{NSMAP["w"]}}}sz', '0')
                    border_info[side] = f"{bval}({bsz})"
                else:
                    border_info[side] = "none"

            # 三线表应该：top粗线、bottom粗线、左右和insideV应为none
            if border_info.get("left", "none") != "none" and "none" not in border_info.get("left", ""):
                issues.append(f"第{tbl_idx}个表格: 左边框不应有线（三线表要求）")
            if border_info.get("right", "none") != "none" and "none" not in border_info.get("right", ""):
                issues.append(f"第{tbl_idx}个表格: 右边框不应有线（三线表要求）")
            if border_info.get("insideV", "none") != "none" and "none" not in border_info.get("insideV", ""):
                issues.append(f"第{tbl_idx}个表格: 内部纵线不应有线（三线表要求）")
        else:
            issues.append(f"第{tbl_idx}个表格: 未定义边框属性，请确认是否为三线表")

    return issues, tbl_idx

def check_figure_table_captions(paragraphs):
    """检查图表编号格式"""
    issues = []
    fig_pattern = re.compile(r"图\s*(\d+)[-‐–—]\s*(\d+)")
    tbl_pattern = re.compile(r"表\s*(\d+)[-‐–—]\s*(\d+)")

    for i, (text, props, run_fonts_list) in enumerate(paragraphs):
        if fig_pattern.search(text):
            # 图名应在图下方 — 无法从单纯文档流确定，但可检查字号
            for rf in run_fonts_list:
                sz = rf.get("sz_hp", 0)
                if sz and sz != 21:  # 五号=10.5pt=21hp
                    issues.append(
                        f"段落{i+1} \"{text[:40]}...\": 图标题字号={hp_to_pt(sz)}pt, 规范要求五号(10.5pt)"
                    )
                ea = rf.get("eastAsia", "")
                if ea and "黑体" not in ea and "SimHei" not in ea.lower() and ea:
                    issues.append(
                        f"段落{i+1} \"{text[:40]}...\": 图标题中文字体={ea}, 规范要求黑体"
                    )
                break

        if tbl_pattern.search(text):
            for rf in run_fonts_list:
                sz = rf.get("sz_hp", 0)
                if sz and sz != 21:
                    issues.append(
                        f"段落{i+1} \"{text[:40]}...\": 表标题字号={hp_to_pt(sz)}pt, 规范要求五号(10.5pt)"
                    )
                ea = rf.get("eastAsia", "")
                if ea and "黑体" not in ea and "SimHei" not in ea.lower() and ea:
                    issues.append(
                        f"段落{i+1} \"{text[:40]}...\": 表标题中文字体={ea}, 规范要求黑体"
                    )
                break

    return issues

def check_references_format(paragraphs):
    """检查参考文献格式"""
    issues = []
    in_refs = False
    ref_count = 0

    for i, (text, props, run_fonts_list) in enumerate(paragraphs):
        if re.match(r"参\s*考\s*文\s*献", text):
            in_refs = True
            continue
        if in_refs and text:
            # 检查是否到了下一个一级标题
            if re.match(r"(第[一二三四五六七八九十]+章|致\s*谢|附\s*录|作者简介)", text):
                break

            if len(text) > 5:
                ref_count += 1
                # 著者—出版年制检查：应有 "著者, 年份." 格式
                # 检查字号是否为五号
                for rf in run_fonts_list:
                    sz = rf.get("sz_hp", 0)
                    if sz and sz != 21:  # 五号=10.5pt=21hp
                        issues.append(
                            f"参考文献第{ref_count}条: 字号={hp_to_pt(sz)}pt, 规范要求五号宋体(10.5pt)"
                        )
                    ea = rf.get("eastAsia", "")
                    if ea and "宋" not in ea and "SimSun" not in ea.lower() and "Song" not in ea:
                        issues.append(
                            f"参考文献第{ref_count}条: 中文字体={ea}, 规范要求宋体"
                        )
                    break

                # 检查是否为著者-出版年制（正文引用格式）
                # 文献列表中应有年份
                if not re.search(r"[,，]\s*(1[89]\d{2}|20[0-2]\d)", text):
                    if not re.search(r"[,，]\s*\d{4}[a-z]?\.?\s", text):
                        pass  # 不一定是问题，有些格式变体

    return issues, ref_count

def main():
    print("=" * 70)
    print("中国农业大学学位论文格式审查报告")
    print("审查依据：《中国农业大学研究生学位论文格式及书写规范（2025年修订）》")
    print("=" * 70)

    zf = zipfile.ZipFile(DOCX_PATH)

    # ========== 1. 页面设置 ==========
    print("\n【一、页面设置（版面）】")
    sections = parse_section_props(zf)
    CAU = {"left": 30.0, "right": 25.0, "top": 30.0, "bottom": 25.0, "header": 23.0, "footer": 18.0}
    for idx, sec in enumerate(sections):
        print(f"  节{idx+1}:")
        pw = sec.get("pageW_mm", 0)
        ph = sec.get("pageH_mm", 0)
        print(f"    纸张: {pw}mm × {ph}mm", end="")
        if abs(pw - 210) > 2 or abs(ph - 297) > 2:
            print(f" ❌ (应为 210×297 A4)")
        else:
            print(f" ✅")

        for side, std in CAU.items():
            actual = sec.get(f"margin{side.capitalize()}_mm", sec.get(f"{side}_mm", 0))
            if side in ("header", "footer"):
                actual = sec.get(f"{side}_mm", 0)
            label = {"left": "左边距", "right": "右边距", "top": "上边距",
                     "bottom": "下边距", "header": "页眉边距", "footer": "页脚边距"}[side]
            if actual and abs(actual - std) > 1.5:
                print(f"    {label}: {actual}mm ❌ (应为 {std}mm)")
            elif actual:
                print(f"    {label}: {actual}mm ✅")

        fmt = sec.get("pgNumFmt", "")
        if fmt:
            print(f"    页码格式: {fmt}")

    # ========== 2. 样式定义 ==========
    print("\n【二、样式定义检查】")
    styles = parse_styles(zf)
    heading_styles = {k: v for k, v in styles.items()
                      if v.get("outlineLvl") is not None or "heading" in k.lower() or "标题" in v.get("name", "")}
    for sid, sinfo in heading_styles.items():
        lvl = sinfo.get("outlineLvl", "?")
        name = sinfo.get("name", sid)
        sz = sinfo.get("sz_hp", 0)
        ea = sinfo.get("eastAsia", "")
        jc = sinfo.get("jc", "")
        bold = sinfo.get("bold", False)
        print(f"  样式 [{name}] (outlineLvl={lvl}): 中文字体={ea or '继承'}, "
              f"字号={hp_to_pt(sz) if sz else '继承'}pt, 对齐={jc or '继承'}, 加粗={bold}")

        if lvl == 0:  # 一级标题
            if sz and sz != 32:  # 三号=16pt=32hp
                print(f"    ❌ 一级标题字号应为三号(16pt/32hp), 实际={hp_to_pt(sz)}pt")
            if ea and "黑体" not in ea and "SimHei" not in ea:
                print(f"    ❌ 一级标题字体应为黑体, 实际={ea}")
            if jc and jc != "center":
                print(f"    ❌ 一级标题应居中, 实际={jc}")
        elif lvl == 1:  # 二级标题
            if sz and sz != 28:  # 四号=14pt=28hp
                print(f"    ❌ 二级标题字号应为四号(14pt/28hp), 实际={hp_to_pt(sz)}pt")
            if ea and "黑体" not in ea and "SimHei" not in ea:
                print(f"    ❌ 二级标题字体应为黑体, 实际={ea}")
        elif lvl == 2:  # 三级标题
            if sz and sz != 24:  # 小四=12pt=24hp
                print(f"    ❌ 三级标题字号应为小四(12pt/24hp), 实际={hp_to_pt(sz)}pt")

    # ========== 3. 正文逐段检查 ==========
    print("\n【三、正文逐段格式抽查】")
    raw = zf.read("word/document.xml")
    root = ET.fromstring(raw)
    body = root.find(f'{{{NSMAP["w"]}}}body')

    paragraphs = []
    heading_count = {1: 0, 2: 0, 3: 0}
    heading_issues = []
    body_font_issues = []
    body_spacing_issues = []
    front_matter_order = []

    front_keywords = ["封面", "独创性声明", "版权授权", "使用授权",
                      "摘要", "Abstract", "ABSTRACT", "目录", "关键词"]

    para_idx = 0
    for para in body.findall(f'{{{NSMAP["w"]}}}p'):
        para_idx += 1
        text = get_text(para)
        props = get_para_props(para)
        run_fonts_list = []
        for run in para.findall(f'{{{NSMAP["w"]}}}r'):
            rf = get_run_fonts(run)
            if rf:
                run_fonts_list.append(rf)

        paragraphs.append((text, props, run_fonts_list))

        if not text:
            continue

        # 前置部分顺序
        for kw in front_keywords:
            if kw.lower() in text.lower() and len(text) < 60:
                front_matter_order.append((para_idx, text[:50]))
                break

        # 标题检查
        hlevel = classify_heading(text, props)
        if hlevel > 0:
            heading_count[hlevel] = heading_count.get(hlevel, 0) + 1

            # 检查对应的字体和字号
            actual_sz = None
            actual_font = None
            actual_jc = props.get("jc", "")

            # 优先用段落级 rPr
            if props.get("pSz_hp"):
                actual_sz = props["pSz_hp"]
            if props.get("pFontEA"):
                actual_font = props["pFontEA"]

            # 再用第一个run
            if run_fonts_list:
                if not actual_sz and run_fonts_list[0].get("sz_hp"):
                    actual_sz = run_fonts_list[0]["sz_hp"]
                if not actual_font and run_fonts_list[0].get("eastAsia"):
                    actual_font = run_fonts_list[0]["eastAsia"]

            # 如果仍为空，从样式继承
            sid = props.get("style", "")
            if sid in styles:
                si = styles[sid]
                if not actual_sz and si.get("sz_hp"):
                    actual_sz = si["sz_hp"]
                if not actual_font and si.get("eastAsia"):
                    actual_font = si["eastAsia"]
                if not actual_jc and si.get("jc"):
                    actual_jc = si["jc"]

            expected = {1: (32, "center"), 2: (28, ""), 3: (24, "")}
            exp_sz, exp_jc = expected.get(hlevel, (0, ""))

            if actual_sz and actual_sz != exp_sz:
                heading_issues.append(
                    f"段落{para_idx} H{hlevel} \"{text[:30]}\": "
                    f"字号={hp_to_pt(actual_sz)}pt, 应为{hp_to_pt(exp_sz)}pt"
                )
            if hlevel == 1 and actual_jc and actual_jc != "center":
                heading_issues.append(
                    f"段落{para_idx} H1 \"{text[:30]}\": 对齐={actual_jc}, 应居中"
                )
            if actual_font and "黑体" not in (actual_font or "") and "SimHei" not in (actual_font or "").lower():
                heading_issues.append(
                    f"段落{para_idx} H{hlevel} \"{text[:30]}\": 字体={actual_font}, 应为黑体"
                )

        # 正文段落抽查（非标题、非空、长度>10的普通段落）
        elif len(text) > 20 and hlevel == 0:
            # 检查字号
            for rf in run_fonts_list[:1]:
                sz = rf.get("sz_hp", 0)
                if sz and sz != 24:  # 小四=12pt=24hp
                    body_font_issues.append(
                        f"段落{para_idx} \"{text[:25]}...\": 字号={hp_to_pt(sz)}pt, 应为小四(12pt)"
                    )
                ea = rf.get("eastAsia", "")
                ascii_f = rf.get("ascii", "")
                if ea and "宋" not in ea and "SimSun" not in ea and "Song" not in ea:
                    body_font_issues.append(
                        f"段落{para_idx} \"{text[:25]}...\": 中文字体={ea}, 应为宋体"
                    )
                if ascii_f and "Times" not in ascii_f and "times" not in ascii_f.lower():
                    if ascii_f and "宋" not in ascii_f:  # 有些段落没单独设英文字体
                        body_font_issues.append(
                            f"段落{para_idx} \"{text[:25]}...\": 英文字体={ascii_f}, 应为Times New Roman"
                        )

            # 行距检查
            ls = props.get("lineSpacing", "")
            lr = props.get("lineRule", "")
            if ls and lr == "exact":
                ls_pt = int(ls) / 20  # twips to pt
                if abs(ls_pt - 20) > 1:
                    body_spacing_issues.append(
                        f"段落{para_idx}: 行距={ls_pt}pt(固定值), 应为20磅"
                    )

    # 输出前置部分
    print("\n【四、前置部分顺序】")
    if front_matter_order:
        for pidx, txt in front_matter_order:
            print(f"  段落{pidx}: {txt}")
    else:
        print("  ⚠️ 未检测到标准前置部分关键词（可能使用了非标准文本）")

    # 输出标题问题
    print(f"\n【五、标题格式检查】(共检测到: H1×{heading_count.get(1,0)}, H2×{heading_count.get(2,0)}, H3×{heading_count.get(3,0)})")
    if heading_issues:
        for iss in heading_issues:
            print(f"  ❌ {iss}")
    else:
        print("  ✅ 标题格式未发现明显偏差")

    # 输出正文字体问题（截取前15条）
    print(f"\n【六、正文字体字号检查】(抽检首个run)")
    if body_font_issues:
        for iss in body_font_issues[:15]:
            print(f"  ❌ {iss}")
        if len(body_font_issues) > 15:
            print(f"  ... 以及另外 {len(body_font_issues)-15} 处")
    else:
        print("  ✅ 正文字体字号未发现明显偏差")

    # 输出行距问题
    print(f"\n【七、行距与间距检查】")
    if body_spacing_issues:
        for iss in body_spacing_issues[:10]:
            print(f"  ❌ {iss}")
        if len(body_spacing_issues) > 10:
            print(f"  ... 以及另外 {len(body_spacing_issues)-10} 处")
    else:
        print("  ✅ 行距设置未发现明显偏差（或未使用固定值行距）")

    # ========== 4. 表格检查 ==========
    print(f"\n【八、表格格式检查（三线表）】")
    tbl_issues, tbl_count = check_tables(body)
    print(f"  共检测到 {tbl_count} 个表格")
    if tbl_issues:
        for iss in tbl_issues:
            print(f"  ❌ {iss}")
    else:
        print("  ✅ 表格边框设置未发现明显偏差")

    # ========== 5. 图表标题检查 ==========
    print(f"\n【九、图表标题格式检查】")
    cap_issues = check_figure_table_captions(paragraphs)
    if cap_issues:
        for iss in cap_issues:
            print(f"  ❌ {iss}")
    else:
        print("  ✅ 图表标题格式未发现明显偏差")

    # ========== 6. 参考文献检查 ==========
    print(f"\n【十、参考文献格式检查】")
    ref_issues, ref_count = check_references_format(paragraphs)
    print(f"  共检测到约 {ref_count} 条参考文献")
    if ref_issues:
        for iss in ref_issues[:10]:
            print(f"  ❌ {iss}")
        if len(ref_issues) > 10:
            print(f"  ... 以及另外 {len(ref_issues)-10} 处")
    else:
        print("  ✅ 参考文献字体字号未发现明显偏差")

    # ========== 7. 页眉检查 ==========
    print(f"\n【十一、页眉检查】")
    headers = check_headers(zf)
    for h in headers:
        print(f"  {h['file']}: {' | '.join([t for t in h['texts'] if not t.startswith('  [')])}")
        for t in h["texts"]:
            if t.startswith("  ["):
                print(f"    {t}")
    if not headers:
        print("  ⚠️ 未检测到页眉定义")

    # ========== 8. 摘要字数 ==========
    print(f"\n【十二、中文摘要字数检查】")
    in_abstract = False
    abstract_text = []
    for text, props, _ in paragraphs:
        if re.match(r"摘\s*要", text) and len(text) < 10:
            in_abstract = True
            continue
        if in_abstract:
            if re.match(r"(关\s*键\s*词|ABSTRACT|Abstract|目\s*录|第[一二三四五六七八九十]+章)", text):
                break
            if text:
                abstract_text.append(text)

    abs_chars = sum(len(t) for t in abstract_text)
    print(f"  中文摘要约 {abs_chars} 字", end="")
    if abs_chars > 800:
        print(f" ⚠️ 超过800字上限（硕士论文）")
    else:
        print(f" ✅")

    print("\n" + "=" * 70)
    print("审查完毕")
    print("=" * 70)

    zf.close()

if __name__ == "__main__":
    main()
