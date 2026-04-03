# -*- coding: utf-8 -*-
"""验证修正后的docx：页眉 + Segoe UI + 图表标题"""
import zipfile
import xml.etree.ElementTree as ET
import re

DOCX = r"D:\Onedrive\桌面\杨志诚毕业论文1_格式修正.docx"
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

def get_text(elem):
    return "".join(t.text or "" for t in elem.iter(f'{{{WNS}}}t')).strip()

def main():
    zf = zipfile.ZipFile(DOCX, 'r')

    # ---- 1. 页眉验证 ----
    print("=" * 60)
    print("[1] \u9875\u7709\u5185\u5bb9\u9a8c\u8bc1")  # 页眉内容验证
    print("=" * 60)
    rels_raw = zf.read("word/_rels/document.xml.rels")
    rels_root = ET.fromstring(rels_raw)
    ns_rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    problems = 0
    for rel in rels_root.findall(f'{{{ns_rel}}}Relationship'):
        target = rel.get("Target", "")
        if "header" not in target.lower():
            continue
        fpath = f"word/{target}"
        try:
            raw = zf.read(fpath)
        except KeyError:
            continue
        root = ET.fromstring(raw)
        texts = [get_text(p) for p in root.findall(f'.//{{{WNS}}}p') if get_text(p)]
        combined = " | ".join(texts)
        if not combined:
            continue

        issues = []
        if "\u53cc\u51fb\u9875\u7709" in combined:   # 双击页眉
            issues.append("\u6a21\u677f\u6b8b\u7559")
        if "\u535a\u58eb/\u7855\u58eb" in combined:   # 博士/硕士
            issues.append("\u535a\u58eb/\u7855\u58eb\u672a\u6539")
        if "\u5fae\u670d\u52a1\u67b6\u6784" in combined:
            issues.append("\u7ae0\u540d\u9519\u8bef")
        if "\u5316\u5b66\u54c1\u5546\u57ce" in combined:
            issues.append("\u7ae0\u540d\u9519\u8bef")

        icon = "\u274c" if issues else "\u2705"
        detail = " [" + ", ".join(issues) + "]" if issues else ""
        print(f"  {icon} {target}: {combined}{detail}")
        if issues:
            problems += 1

    # ---- 2. Segoe UI 检查 ----
    print(f"\n{'='*60}")
    print("[2] Segoe UI \u5b57\u4f53\u68c0\u67e5")  # 字体检查
    print("=" * 60)
    doc_raw = zf.read("word/document.xml").decode("utf-8")
    segoe_count = doc_raw.count("Segoe UI")
    if segoe_count:
        print(f"  \u274c \u4ecd\u6709 {segoe_count} \u5904 Segoe UI")
        problems += 1
    else:
        print("  \u2705 \u65e0 Segoe UI")

    # ---- 3. 图表标题字号检查 ----
    print(f"\n{'='*60}")
    print("[3] \u56fe\u8868\u6807\u9898\u5b57\u53f7\u68c0\u67e5")  # 图表标题字号检查
    print("=" * 60)
    root = ET.fromstring(doc_raw.encode("utf-8"))
    body = root.find(f'{{{WNS}}}body')
    cap_ok = 0
    cap_bad = 0
    for para in body.iter(f'{{{WNS}}}p'):
        pt = get_text(para)
        if not re.match(r'^[\u56fe\u8868]\s*\d+[-\u2010\u2013\u2014\u2015]\s*\d+', pt):
            continue
        if len(pt) > 80:
            continue
        # 检查第一个 run 的字号
        for run in para.findall(f'{{{WNS}}}r'):
            rpr = run.find(f'{{{WNS}}}rPr')
            if rpr is not None:
                sz = rpr.find(f'{{{WNS}}}sz')
                rf = rpr.find(f'{{{WNS}}}rFonts')
                sz_val = int(sz.get(f'{{{WNS}}}val', '0')) if sz is not None else 0
                ea = rf.get(f'{{{WNS}}}eastAsia', '') if rf is not None else ''
                if sz_val == 21 and '\u9ed1' in ea:
                    cap_ok += 1
                else:
                    cap_bad += 1
                    if cap_bad <= 3:
                        print(f"  \u274c \"{pt[:40]}\": \u5b57\u53f7={sz_val/2}pt \u5b57\u4f53={ea}")
            break

    if cap_bad == 0:
        print(f"  \u2705 \u5168\u90e8 {cap_ok} \u4e2a\u56fe\u8868\u6807\u9898\u5df2\u4fee\u6b63\u4e3a\u9ed1\u4f535\u53f7")
    else:
        print(f"  \u5171 {cap_ok} ok, {cap_bad} \u5f85\u4fee")
        problems += 1

    # ---- 4. [n] 引用残留 ----
    print(f"\n{'='*60}")
    print("[4] [n] \u5f15\u7528\u6b8b\u7559\u68c0\u67e5")
    print("=" * 60)
    bracket_refs = re.findall(r'\[\d+\]', doc_raw)
    if bracket_refs:
        unique = sorted(set(bracket_refs))
        print(f"  \u26a0\ufe0f \u4ecd\u6709 {len(bracket_refs)} \u5904: {', '.join(unique[:10])}")
    else:
        print("  \u2705 \u65e0 [n] \u5f15\u7528")

    print(f"\n{'='*60}")
    if problems == 0:
        print("\u2705 \u81ea\u52a8\u4fee\u6b63\u9879\u5168\u90e8\u901a\u8fc7!")
    else:
        print(f"\u26a0\ufe0f \u8fd8\u6709 {problems} \u9879\u95ee\u9898")
    print("=" * 60)

    zf.close()

if __name__ == "__main__":
    main()
