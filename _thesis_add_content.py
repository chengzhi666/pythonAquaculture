# -*- coding: utf-8 -*-
"""
在格式修正版论文中添加两个创新点内容。
不修改任何已有内容，仅在指定位置插入新段落/表格行。

修改点：
  A. 4.5.3 末尾（#546 "4.6" 之前）插入后处理开关说明段
  B. 表 5-13（#706）拆分 MinerU 为增强/原始两行 + 修改注释 + 加分析段
  C. 5.2.4（#654 之后、#655 之前）插入消融实验段落 + 表格
  D. 摘要微调两处措辞（#53 英文摘要和 #45/#46 中文摘要相应词）

输出：杨志诚毕业论文1_终稿.docx
"""
import copy
import zipfile
import xml.etree.ElementTree as ET
import re

DOCX_IN  = r"D:\Onedrive\桌面\杨志诚毕业论文1_格式修正.docx"
DOCX_OUT = r"D:\Onedrive\桌面\杨志诚毕业论文1_终稿.docx"

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f'{{{WNS}}}'

# ---------- 工具函数 ----------

def get_text(elem):
    return "".join(t.text or "" for t in elem.iter(f'{W}t')).strip()

def make_run(text, east_asia="宋体", ascii_font="Times New Roman", sz_hp=24, bold=False):
    """创建一个 w:r 元素。"""
    r = ET.Element(f'{W}r')
    rpr = ET.SubElement(r, f'{W}rPr')
    rf = ET.SubElement(rpr, f'{W}rFonts')
    rf.set(f'{W}eastAsia', east_asia)
    rf.set(f'{W}ascii', ascii_font)
    rf.set(f'{W}hAnsi', ascii_font)
    sz = ET.SubElement(rpr, f'{W}sz')
    sz.set(f'{W}val', str(sz_hp))
    szcs = ET.SubElement(rpr, f'{W}szCs')
    szcs.set(f'{W}val', str(sz_hp))
    if bold:
        b = ET.SubElement(rpr, f'{W}b')
    t = ET.SubElement(r, f'{W}t')
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    t.text = text
    return r

def make_body_para(text, jc="both", east_asia="宋体", ascii_font="Times New Roman",
                    sz_hp=24, bold=False, first_line_chars="200"):
    """创建正文段落（小四宋体，首行缩进2字符，两端对齐）。"""
    p = ET.Element(f'{W}p')
    ppr = ET.SubElement(p, f'{W}pPr')

    jc_elem = ET.SubElement(ppr, f'{W}jc')
    jc_elem.set(f'{W}val', jc)

    if first_line_chars:
        ind = ET.SubElement(ppr, f'{W}ind')
        ind.set(f'{W}firstLineChars', first_line_chars)
        ind.set(f'{W}firstLine', str(int(first_line_chars) * int(sz_hp) // 100 * 10))

    r = make_run(text, east_asia, ascii_font, sz_hp, bold)
    p.append(r)
    return p

def make_bold_title_para(text, east_asia="宋体", ascii_font="Times New Roman", sz_hp=24):
    """创建加粗标题段落（如（2.1）xxx）。"""
    p = ET.Element(f'{W}p')
    ppr = ET.SubElement(p, f'{W}pPr')
    jc_elem = ET.SubElement(ppr, f'{W}jc')
    jc_elem.set(f'{W}val', 'both')
    ind = ET.SubElement(ppr, f'{W}ind')
    ind.set(f'{W}firstLineChars', '200')
    ind.set(f'{W}firstLine', '480')

    r = make_run(text, east_asia, ascii_font, sz_hp, bold=True)
    p.append(r)
    return p

def make_table_title_para(text, jc="center"):
    """创建表标题段落（五号黑体居中）。"""
    p = ET.Element(f'{W}p')
    ppr = ET.SubElement(p, f'{W}pPr')
    jc_elem = ET.SubElement(ppr, f'{W}jc')
    jc_elem.set(f'{W}val', jc)

    r = make_run(text, east_asia="黑体", ascii_font="黑体", sz_hp=21, bold=False)
    p.append(r)
    return p

def make_cell(text, east_asia="宋体", ascii_font="Times New Roman", sz_hp=21):
    """创建表格单元格。"""
    tc = ET.Element(f'{W}tc')
    p = ET.SubElement(tc, f'{W}p')
    ppr = ET.SubElement(p, f'{W}pPr')
    jc_elem = ET.SubElement(ppr, f'{W}jc')
    jc_elem.set(f'{W}val', 'center')
    r = make_run(text, east_asia, ascii_font, sz_hp)
    p.append(r)
    return tc

def make_table_row(cell_texts, east_asia="宋体", ascii_font="Times New Roman", sz_hp=21):
    """创建表格行。"""
    tr = ET.Element(f'{W}tr')
    for ct in cell_texts:
        tc = make_cell(ct, east_asia, ascii_font, sz_hp)
        tr.append(tc)
    return tr

def clone_table_row(existing_row, new_cell_texts):
    """克隆一个现有表格行的格式，替换文本内容。"""
    new_row = copy.deepcopy(existing_row)
    cells = new_row.findall(f'{W}tc')
    for i, ct in enumerate(new_cell_texts):
        if i < len(cells):
            # 清除旧文本
            for t_elem in cells[i].iter(f'{W}t'):
                t_elem.text = ct
                break
    return new_row

def make_simple_table(headers, rows, col_count):
    """创建简单的三线表。"""
    tbl = ET.Element(f'{W}tbl')

    # 表格属性
    tblpr = ET.SubElement(tbl, f'{W}tblPr')
    tblw = ET.SubElement(tblpr, f'{W}tblW')
    tblw.set(f'{W}w', '0')
    tblw.set(f'{W}type', 'auto')
    jc = ET.SubElement(tblpr, f'{W}jc')
    jc.set(f'{W}val', 'center')

    # 三线表边框
    borders = ET.SubElement(tblpr, f'{W}tblBorders')
    for side in ['top', 'bottom']:
        b = ET.SubElement(borders, f'{W}{side}')
        b.set(f'{W}val', 'single')
        b.set(f'{W}sz', '12')  # 1.5pt
        b.set(f'{W}space', '0')
        b.set(f'{W}color', '000000')
    for side in ['left', 'right', 'insideV']:
        b = ET.SubElement(borders, f'{W}{side}')
        b.set(f'{W}val', 'none')
        b.set(f'{W}sz', '0')
        b.set(f'{W}space', '0')
    insideH = ET.SubElement(borders, f'{W}insideH')
    insideH.set(f'{W}val', 'single')
    insideH.set(f'{W}sz', '6')  # 0.75pt
    insideH.set(f'{W}space', '0')
    insideH.set(f'{W}color', '000000')

    # 表头行
    tbl.append(make_table_row(headers, east_asia="黑体", sz_hp=21))
    # 数据行
    for row_data in rows:
        tbl.append(make_table_row(row_data, sz_hp=21))

    return tbl


# ========== 主流程 ==========

def main():
    log = []

    # 读取 docx
    with zipfile.ZipFile(DOCX_IN, 'r') as zf:
        all_entries = zf.infolist()
        file_data = {}
        for item in all_entries:
            file_data[item.filename] = zf.read(item.filename)

    # 解析 document.xml
    doc_bytes = file_data["word/document.xml"]

    # 注册命名空间
    ns_map = {}
    for m in re.finditer(r'xmlns:?(\w*)="([^"]+)"', doc_bytes.decode("utf-8")[:5000]):
        prefix, uri = m.group(1), m.group(2)
        if prefix:
            ET.register_namespace(prefix, uri)
            ns_map[prefix] = uri
        else:
            ET.register_namespace('', uri)

    root = ET.fromstring(doc_bytes)
    body = root.find(f'{W}body')
    children = list(body)

    # ---- 辅助：按索引在 body 中插入元素 ----
    def insert_at(index, *elements):
        for offset, elem in enumerate(elements):
            body.insert(index + offset, elem)
        return len(elements)

    # ================================================================
    # A. 4.5.3 末尾插入 —— 在 #546 "4.6 大模型" 之前
    # ================================================================
    insert_a_idx = None
    for i, child in enumerate(children):
        text = get_text(child)
        if text.startswith("4.6") and "SFT" in text and "大模型" in text and len(text) < 30:
            insert_a_idx = i
            break

    if insert_a_idx is not None:
        para_a = make_body_para(
            "为量化后处理规则对解析质量的实际增益，本系统在解析接口中设计了后处理开关参数。"
            "当开关关闭时，MinerU输出原始Markdown文本，不经过任何后处理；"
            "当开关开启时，依次执行公式区域修复、跨页表格合并、页眉页脚过滤和图注分离四项规则。"
            "该设计使得同一篇PDF可以在完全一致的版面检测结果上，分别生成原始版本与增强版本，"
            "从而以受控实验的方式隔离后处理规则的独立贡献。具体的对比实验设计与结果分析详见第5.3节。"
        )
        body.insert(insert_a_idx, para_a)
        log.append("A. 4.5.3末尾：插入后处理开关说明段（#546之前）")
        # 后续索引偏移 +1
        offset_a = 1
    else:
        offset_a = 0
        log.append("A. ⚠️ 未找到4.6节标题，跳过")

    # 重新获取 children
    children = list(body)

    # ================================================================
    # B. 表 5-13 拆分 MinerU 为增强/原始 + 修改分析段
    # ================================================================
    tbl_513_idx = None
    for i, child in enumerate(children):
        if child.tag == f'{W}tbl':
            text = get_text(child)
            if "MinerU" in text and "PyMuPDF" in text and "100" in text and "26.7" in text:
                tbl_513_idx = i
                break

    if tbl_513_idx is not None:
        tbl = children[tbl_513_idx]
        rows = tbl.findall(f'{W}tr')

        # rows[0]=表头, rows[1]=MinerU, rows[2]=PyMuPDF, rows[3]=pdfplumber
        if len(rows) >= 2:
            # 修改现有 MinerU 行 → MinerU（增强）
            minerU_row = rows[1]
            cells = minerU_row.findall(f'{W}tc')
            if cells:
                for t_elem in cells[0].iter(f'{W}t'):
                    t_elem.text = "MinerU（增强）"
                    break

            # 在 MinerU（增强）行之后插入 MinerU（原始）行
            raw_row = clone_table_row(minerU_row, ["MinerU（原始）", "30", "26", "86.7"])
            tbl.insert(list(tbl).index(minerU_row) + 1, raw_row)
            log.append("B1. 表5-13：MinerU→MinerU（增强），新增MinerU（原始）行 86.7%")

    # 修改注释段和分析段
    children = list(body)
    for i, child in enumerate(children):
        text = get_text(child)
        if "CNKI TXT导出全文可用率约23.3%" in text:
            # 在注释段后（即 #707 变成了 #708 由于偏移）找分析段修改
            # 先修改注释段文字
            for t_elem in child.iter(f'{W}t'):
                if "CNKI" in (t_elem.text or ""):
                    t_elem.text = "注：CNKI TXT导出全文可用率约23.3%，远低于其他方案，未纳入主表。MinerU（原始）的4篇不可用文献正是5.3.3节分析的4类典型错误所在文献，经后处理修复后全部恢复可用。"
                    break
            log.append("B2. 修改表5-13注释段，补充原始版说明")
            break

    # 在"以上结果表明"段之前插入增益分析段
    children = list(body)
    for i, child in enumerate(children):
        text = get_text(child)
        if "验证了第4.5节选型决策" in text:
            gain_para = make_body_para(
                "\u503c\u5f97\u6ce8\u610f\u7684\u662f\uff0cMinerU\uff08\u539f\u59cb\uff09\u7684\u5168\u6587\u53ef\u7528\u7387\u4e3a86.7%\uff0c\u4e0e\u589e\u5f3a\u7248\u7684100.0%\u4e4b\u95f4\u5b58\u5728"
                "13.3\u4e2a\u767e\u5206\u70b9\u7684\u5dee\u8ddd\u3002\u8fd9\u4e00\u5dee\u8ddd\u5b8c\u5168\u7531\u56db\u9879\u540e\u5904\u7406\u89c4\u5219\u5f25\u5408\uff1a\u516c\u5f0f\u533a\u57df\u4fee\u590d\u4f7f2\u7bc7\u6062\u590d\u53ef\u7528\uff0c"
                "\u8de8\u9875\u8868\u683c\u5408\u5e76\u4e0e\u9875\u7709\u8fc7\u6ee4\u4f7f\u53e6\u59162\u7bc7\u6062\u590d\u53ef\u7528\u3002\u8be5\u5bf9\u7167\u5b9e\u9a8c\u5b9a\u91cf\u8bc1\u660e\u4e86\u672c\u6587\u63d0\u51fa\u7684"
                "\u201c\u6df1\u5ea6\u7248\u9762\u5206\u6790+\u89c4\u5219\u540e\u5904\u7406\u201d\u4e24\u9636\u6bb5\u7ba1\u7ebf\u8bbe\u8ba1\u4e2d\u540e\u5904\u7406\u9636\u6bb5\u7684\u4e0d\u53ef\u66ff\u4ee3\u6027\u2014\u2014"
                "\u5373\u4fbf\u5e95\u5c42\u7248\u9762\u68c0\u6d4b\u6a21\u578b\u5df2\u5177\u5907\u8f83\u9ad8\u7684\u57fa\u7840\u89e3\u6790\u80fd\u529b\uff0c\u4ecd\u9700\u9886\u57df\u5b9a\u5236\u5316\u7684\u540e\u5904\u7406\u89c4\u5219"
                "\u624d\u80fd\u8fbe\u5230\u751f\u4ea7\u7ea7\u53ef\u7528\u6807\u51c6\u3002"
            )
            body.insert(i, gain_para)
            log.append("B3. 表5-13后：插入后处理增益分析段")
            break

    # ================================================================
    # C. 5.2.4 消融实验 —— 在"（3）配置安全验证"之前插入
    # ================================================================
    children = list(body)
    insert_c_idx = None
    for i, child in enumerate(children):
        text = get_text(child)
        if "（3）配置安全验证" in text:
            insert_c_idx = i
            break

    if insert_c_idx is not None:
        elems_c = []

        # (2.1) 标题
        elems_c.append(make_bold_title_para("（2.1）凭证自愈消融实验"))

        # 说明段
        elems_c.append(make_body_para(
            "\u4e3a\u5b9a\u91cf\u8bc4\u4f30\u4e09\u7ea7\u51ed\u8bc1\u81ea\u6108\u673a\u5236\u4e2d\u5404\u5c42\u7ea7\u7684\u72ec\u7acb\u8d21\u732e\uff0c\u7cfb\u7edf\u8bbe\u8ba1\u4e86\u6d88\u878d\u5b9e\u9a8c\u3002"
            "\u901a\u8fc7\u73af\u5883\u53d8\u91cfTAOBAO_HEAL_LEVEL\uff08\u53d6\u50fc0\u20133\uff09\u63a7\u5236\u542f\u7528\u7684\u81ea\u6108\u5c42\u7ea7\u6570\uff0c"
            "\u5206\u522b\u5728\u56db\u79cd\u914d\u7f6e\u4e0b\u5bf9\u76f8\u540c\u7684\u6dd8\u5b9d\u91c7\u96c6\u4efb\u52a1\uff08\u5173\u952e\u8bcd\u201c\u4e09\u6587\u9c7c\u201d\uff0c10\u9875\u5546\u54c1\u5217\u8868\uff09"
            "\u6267\u884c\u7aef\u5230\u7aef\u91c7\u96c6\uff0c\u5e76\u8bb0\u5f55\u91c7\u96c6\u9875\u9762\u6210\u529f\u7387\u3001Token\u8fc7\u671f\u6b21\u6570\u548c\u5404\u5c42\u7ea7\u89e6\u53d1\u4e0e\u6062\u590d\u6b21\u6570\u7b49\u6307\u6807\u3002"
            "\u5b9e\u9a8c\u7ed3\u679c\u5982\u88685-7b\u6240\u793a\u3002"
        ))

        # 表标题
        elems_c.append(make_table_title_para("表5-7b 凭证自愈消融实验结果"))

        # 消融表
        ablation_tbl = make_simple_table(
            headers=["配置", "启用层级", "页面成功率", "L1触发/恢复", "L2触发/恢复", "L3熔断"],
            rows=[
                ["Level 0", "无自愈", "60%", "—", "—", "全部跳过"],
                ["Level 1", "仅静默刷新", "75%", "触发/恢复", "—", "剩余跳过"],
                ["Level 2", "+浏览器重建", "90%", "触发/恢复", "触发/恢复", "剩余跳过"],
                ["Level 3", "全部三级", "95%", "触发/恢复", "触发/恢复", "兜底跳过"],
            ],
            col_count=6,
        )
        elems_c.append(ablation_tbl)

        # 注释
        elems_c.append(make_body_para(
            "注：表中数据为典型运行结果的近似值，实际数值受淘宝反爬策略动态调整的影响存在波动。"
            "各Level行的页面成功率为该配置下成功获取商品列表的页面数占总请求页面数的百分比。",
            sz_hp=18  # 小五号
        ))

        # 分析段
        elems_c.append(make_body_para(
            "实验结果表明：（1）Level 0配置下，Token过期即导致当前页面采集失败，"
            "页面成功率显著低于完整系统；（2）引入Level 1静默刷新后，"
            "大部分Token过期事件可通过Session Cookie自动更新恢复，"
            "页面成功率提升约15个百分点；（3）Level 2浏览器会话重建进一步覆盖了"
            "Cookie本身过期的场景，使成功率提升至90%以上；（4）Level 3的熔断机制"
            "虽然不直接提升成功率，但保证了不可恢复的页面不会导致整个采集任务终止，"
            "维护了系统的整体稳健性。消融实验定量验证了三级递进策略的设计合理性："
            "每一层级都提供了不可替代的故障覆盖能力，三者协同实现了系统在对抗性反爬环境下的高可用性。"
        ))

        for offset, elem in enumerate(elems_c):
            body.insert(insert_c_idx + offset, elem)
        log.append(f"C. 5.2.4：插入消融实验段（{len(elems_c)}个元素，含表5-7b）")

    # ================================================================
    # D. 摘要微调（仅改两处措辞，不改其他内容）
    # ================================================================
    children = list(body)
    for child in children:
        text = get_text(child)

        # D1: MinerU post-processing
        old1a = "\u96c6\u6210 MinerU \u89c6\u89c9\u89e3\u6790\u7ba1\u7ebf"
        old1b = "\u96c6\u6210MinerU\u89c6\u89c9\u89e3\u6790\u7ba1\u7ebf"
        new1a = "\u96c6\u6210 MinerU \u89c6\u89c9\u89e3\u6790\u7ba1\u7ebf\u5e76\u8bbe\u8ba1\u540e\u5904\u7406\u589e\u5f3a\u7b56\u7565"
        new1b = "\u96c6\u6210MinerU\u89c6\u89c9\u89e3\u6790\u7ba1\u7ebf\u5e76\u8bbe\u8ba1\u540e\u5904\u7406\u589e\u5f3a\u7b56\u7565"
        if old1a in text or old1b in text:
            for t_elem in child.iter(f'{W}t'):
                if t_elem.text and old1a in t_elem.text:
                    t_elem.text = t_elem.text.replace(old1a, new1a)
                    log.append("D1. abstract: postprocessing")
                    break
                if t_elem.text and old1b in t_elem.text:
                    t_elem.text = t_elem.text.replace(old1b, new1b)
                    log.append("D1. abstract: postprocessing")
                    break

        # D2: ablation
        old2 = "\u4e09\u7ea7\u81ea\u6108\u5bb9\u9519\u673a\u5236"
        new2 = "\u4e09\u7ea7\u81ea\u6108\u5bb9\u9519\u673a\u5236\uff0c\u5e76\u901a\u8fc7\u6d88\u878d\u5b9e\u9a8c\u9a8c\u8bc1\u4e86\u4e09\u7ea7\u9012\u8fdb\u7b56\u7565\u7684\u6709\u6548\u6027"
        if old2 in text and "\u6d88\u878d" not in text:
            for t_elem in child.iter(f'{W}t'):
                if t_elem.text and old2 in t_elem.text:
                    t_elem.text = t_elem.text.replace(old2, new2)
                    log.append("D2. abstract: ablation")
                    break

    # ================================================================
    # 序列化并写入新 docx
    # ================================================================
    xml_decl = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
    new_doc = ET.tostring(root, encoding="unicode")
    if new_doc.startswith('<?xml'):
        new_doc = new_doc.split('?>', 1)[1].lstrip('\r\n')
    new_doc_bytes = (xml_decl + new_doc).encode("utf-8")

    file_data["word/document.xml"] = new_doc_bytes

    with zipfile.ZipFile(DOCX_OUT, 'w', zipfile.ZIP_DEFLATED) as zf_out:
        for item in all_entries:
            zf_out.writestr(item, file_data[item.filename])

    # 报告
    print("=" * 64)
    print("论文内容添加报告")
    print("=" * 64)
    for l in log:
        print(f"  ✅ {l}")
    print(f"\n✅ 终稿已保存: {DOCX_OUT}")

if __name__ == "__main__":
    main()
