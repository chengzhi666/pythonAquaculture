# -*- coding: utf-8 -*-
"""
中国农业大学学位论文格式自动修正脚本
====================================
修正项：
  1. 页眉：模板残留文字 / "博士/硕士"→"硕士" / 章节名称错误（6个header文件）
  2. 正文：英文字体 Segoe UI → Times New Roman
  3. 图表独立标题行：宋体→黑体、12pt→10.5pt（五号）
输出：在桌面生成 _格式修正.docx，不修改原文件。
"""
import zipfile
import re
import xml.etree.ElementTree as ET
import os

DOCX_IN  = r"D:\Onedrive\桌面\杨志诚毕业论文1.docx"
DOCX_OUT = r"D:\Onedrive\桌面\杨志诚毕业论文1_格式修正.docx"

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# ---------- 正确的章节名称（从正文标题确认） ----------
CH_NAMES = {
    "\u4e00": "\u7eea\u8bba",
    "\u4e8c": "\u60c5\u62a5\u91c7\u96c6\u4e0e\u5927\u6a21\u578b\u8bed\u6599\u76f8\u5173\u6280\u672f\u7814\u7a76",
    "\u4e09": "\u6e14\u4e1a\u60c5\u62a5\u91c7\u96c6\u7cfb\u7edf\u5206\u6790\u4e0e\u8bbe\u8ba1",
    "\u56db": "\u91c7\u96c6\u7cfb\u7edf\u5b9e\u73b0\u4e0e\u5173\u952e\u6280\u672f\u5e94\u7528",
    "\u4e94": "\u81ea\u52a8\u5316\u6d4b\u8bd5\u7814\u7a76\u4e0e\u7cfb\u7edf\u6d4b\u8bd5",
    "\u516d": "\u603b\u7ed3\u4e0e\u5c55\u671b",
}

# ========== 页眉修正 ==========

def fix_header(filename, raw_bytes, template_bytes):
    """修正单个页眉 XML 文件，返回 (new_bytes, list_of_changes)."""
    text = raw_bytes.decode("utf-8")
    changes = []

    # --- A. 含模板提示文字 → 用 header6 模板重建 ---
    if "\u53cc\u51fb\u9875\u7709\u4fee\u6539\u6b64\u5904" in text:        # "双击页眉修改此处"
        m = re.search(r"\u7b2c([\u4e00\u4e8c\u4e09\u56db\u4e94\u516d])\u7ae0", text)
        if m and template_bytes:
            cn = m.group(1)
            name = CH_NAMES.get(cn, "")
            new_text = template_bytes.decode("utf-8")
            new_text = new_text.replace("\u7eea\u8bba", name)           # 绪论→正确章名
            new_text = new_text.replace("\u7b2c\u4e00\u7ae0", "\u7b2c" + cn + "\u7ae0")  # 第一章→第X章
            text = new_text
            changes.append(
                "\u6a21\u677f\u91cd\u5efa \u2192 \u7b2c" + cn + "\u7ae0 " + name
            )  # "模板重建 → 第X章 ..."

    # --- B. 博士/硕士 → 硕士 ---
    if "\u535a\u58eb/\u7855\u58eb" in text:       # "博士/硕士"
        text = text.replace("\u535a\u58eb/\u7855\u58eb", "\u7855\u58eb")
        changes.append("\u535a\u58eb/\u7855\u58eb \u2192 \u7855\u58eb")

    # --- C. 错误章节名称替换 ---
    WRONG_NAMES = [
        # (wrong, right, label)
        ("\u5fae\u670d\u52a1\u67b6\u6784\u4e0e\u81ea\u52a8\u5316\u6d4b\u8bd5\u76f8\u5173\u6280\u672f\u7814\u7a76",
         "\u60c5\u62a5\u91c7\u96c6\u4e0e\u5927\u6a21\u578b\u8bed\u6599\u76f8\u5173\u6280\u672f\u7814\u7a76",
         "\u7b2c\u4e8c\u7ae0"),   # 第二章
        ("\u5316\u5b66\u54c1\u5546\u57ce\u7cfb\u7edf\u5b9e\u73b0\u4e0e\u5173\u952e\u6280\u672f\u5e94\u7528",
         "\u91c7\u96c6\u7cfb\u7edf\u5b9e\u73b0\u4e0e\u5173\u952e\u6280\u672f\u5e94\u7528",
         "\u7b2c\u56db\u7ae0"),   # 第四章
    ]
    for wrong, right, label in WRONG_NAMES:
        if wrong in text:
            text = text.replace(wrong, right)
            changes.append(label + " \u7ae0\u8282\u540d\u4fee\u6b63")  # "章节名修正"

    if changes:
        return text.encode("utf-8"), changes
    return raw_bytes, []

# ========== document.xml 修正 ==========

def fix_document(raw_bytes):
    """修正 document.xml：Segoe UI 字体 + 图表标题字号."""
    text = raw_bytes.decode("utf-8")
    changes = []

    # --- 1. Segoe UI → Times New Roman ---
    n = text.count("Segoe UI")
    if n:
        text = text.replace("Segoe UI", "Times New Roman")
        changes.append("Segoe UI \u2192 Times New Roman (" + str(n) + "\u5904)")

    # --- 2. 图表独立标题行字体/字号 ---
    # 用 ET 解析来精确定位标题段落
    try:
        # 注册命名空间，保证序列化后前缀不变
        ns_pairs = []
        # 从 XML 中提取所有命名空间声明
        for m in re.finditer(r'xmlns:?(\w*)="([^"]+)"', text[:5000]):
            prefix = m.group(1)
            uri = m.group(2)
            if prefix:
                ET.register_namespace(prefix, uri)
                ns_pairs.append((prefix, uri))
            else:
                ET.register_namespace('', uri)

        root = ET.fromstring(text.encode("utf-8"))
        body = root.find(f'{{{WNS}}}body')
        caption_count = 0

        for para in body.iter(f'{{{WNS}}}p'):
            # 提取段落纯文本
            texts = []
            for t_elem in para.iter(f'{{{WNS}}}t'):
                texts.append(t_elem.text or "")
            pt = "".join(texts).strip()

            # 判断是否为独立图表标题行
            if len(pt) < 4 or len(pt) > 80:
                continue
            if not re.match(r'^[\u56fe\u8868]\s*\d+[-\u2010\u2013\u2014\u2015]\s*\d+', pt):
                continue

            # 修改每个 run 的 rPr
            for run in para.findall(f'{{{WNS}}}r'):
                rpr = run.find(f'{{{WNS}}}rPr')
                if rpr is None:
                    rpr = ET.SubElement(run, f'{{{WNS}}}rPr')
                    run.insert(0, rpr)

                # 设置中文字体=黑体
                rf = rpr.find(f'{{{WNS}}}rFonts')
                if rf is None:
                    rf = ET.SubElement(rpr, f'{{{WNS}}}rFonts')
                rf.set(f'{{{WNS}}}eastAsia', '\u9ed1\u4f53')  # 黑体

                # 字号=10.5pt → 21 half-points
                for tag in ['sz', 'szCs']:
                    elem = rpr.find(f'{{{WNS}}}{tag}')
                    if elem is None:
                        elem = ET.SubElement(rpr, f'{{{WNS}}}{tag}')
                    elem.set(f'{{{WNS}}}val', '21')

            caption_count += 1

        if caption_count:
            # 序列化
            xml_decl = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
            body_str = ET.tostring(root, encoding="unicode")
            # ET.tostring 可能添加自己的 xml 声明，去掉重复
            if body_str.startswith('<?xml'):
                body_str = body_str.split('?>', 1)[1].lstrip('\r\n')
            text = xml_decl + body_str
            changes.append(
                str(caption_count) + " \u4e2a\u56fe\u8868\u6807\u9898 \u2192 \u9ed1\u4f535\u53f7(10.5pt)"
            )

    except Exception as exc:
        changes.append(
            "\u26a0\ufe0f \u56fe\u8868\u6807\u9898\u4fee\u6b63\u8df3\u8fc7: " + str(exc)
        )

    return text.encode("utf-8"), changes


# ========== 主流程 ==========

def main():
    assert os.path.isfile(DOCX_IN), f"File not found: {DOCX_IN}"
    log = []

    # 读取模板页眉（header6.xml 格式正确）
    with zipfile.ZipFile(DOCX_IN, 'r') as zf:
        try:
            template = zf.read("word/header6.xml")
        except KeyError:
            template = None

    with zipfile.ZipFile(DOCX_IN, 'r') as zf_in, \
         zipfile.ZipFile(DOCX_OUT, 'w', zipfile.ZIP_DEFLATED) as zf_out:

        for item in zf_in.infolist():
            data = zf_in.read(item.filename)

            if item.filename.startswith("word/header") and item.filename.endswith(".xml"):
                data, ch = fix_header(item.filename, data, template)
                for c in ch:
                    log.append(("\u2705", item.filename, c))

            elif item.filename == "word/document.xml":
                data, ch = fix_document(data)
                for c in ch:
                    log.append(("\u2705", "document.xml", c))

            zf_out.writestr(item, data)

    # ---------- 报告 ----------
    print("=" * 64)
    print("\u683c\u5f0f\u4fee\u6b63\u62a5\u544a")   # 格式修正报告
    print("=" * 64)
    for icon, src, msg in log:
        print(f"  {icon} [{src}] {msg}")

    print(f"\n\u2705 \u4fee\u6b63\u7248\u5df2\u4fdd\u5b58: {DOCX_OUT}")

    print(f"\n\u26a0\ufe0f  \u4ecd\u9700\u624b\u52a8\u5904\u7406:")
    print("  1. \u6b63\u6587 6 \u5904 [n] \u5f15\u7528\u6539\u4e3a\uff08\u8457\u8005\uff0c\u5e74\u4efd\uff09\u683c\u5f0f:")
    print("     - Ctrl+H \u67e5\u627e: [10] [13] [25] [32] [33] [34]")
    print("     - \u66ff\u6362\u4e3a\u5bf9\u5e94\u7684 (\u8457\u8005, \u5e74\u4efd) \u683c\u5f0f")
    print("  2. \u4e2d\u6587\u6458\u8981\u7ea6 875 \u5b57\uff0c\u9700\u7cbe\u7b80\u81f3 \u2264800 \u5b57")
    print("  3. Word \u4e2d\u66f4\u65b0\u76ee\u5f55: \u53f3\u952e\u76ee\u5f55 \u2192 \u66f4\u65b0\u57df \u2192 \u66f4\u65b0\u6574\u4e2a\u76ee\u5f55")

if __name__ == "__main__":
    main()
