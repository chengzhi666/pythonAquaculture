# -*- coding: utf-8 -*-
"""验证终稿中新增内容是否正确插入。"""
import zipfile
import xml.etree.ElementTree as ET
import re

DOCX = r"D:\Onedrive\桌面\杨志诚毕业论文1_终稿.docx"
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f'{{{WNS}}}'

def get_text(elem):
    return "".join(t.text or "" for t in elem.iter(f'{W}t')).strip()

def main():
    zf = zipfile.ZipFile(DOCX)
    raw = zf.read("word/document.xml")
    root = ET.fromstring(raw)
    body = root.find(f'{W}body')
    children = list(body)

    checks = {
        "A_postproc_switch": False,
        "B1_table_enhanced": False,
        "B1_table_raw": False,
        "B3_gain_analysis": False,
        "C_ablation_title": False,
        "C_ablation_table": False,
        "D1_abstract_postproc": False,
        "D2_abstract_ablation": False,
    }

    for i, child in enumerate(children):
        text = get_text(child)

        # A: 后处理开关段
        if "\u540e\u5904\u7406\u5f00\u5173\u53c2\u6570" in text:  # 后处理开关参数
            checks["A_postproc_switch"] = True
            print(f"  \u2705 A. \u540e\u5904\u7406\u5f00\u5173\u8bf4\u660e\u6bb5 @ #{i}: {text[:60]}...")

        # B1: 表5-13含增强/原始
        if child.tag == f'{W}tbl' and "MinerU" in text:
            if "\u589e\u5f3a" in text and "\u539f\u59cb" in text:
                checks["B1_table_enhanced"] = True
                checks["B1_table_raw"] = True
                rows = child.findall(f'{W}tr')
                print(f"  \u2705 B1. \u88685-13 @ #{i}: {len(rows)}\u884c")
                for ri, row in enumerate(rows):
                    cells = row.findall(f'{W}tc')
                    cell_texts = [get_text(c) for c in cells]
                    print(f"       \u884c{ri}: {cell_texts}")

        # B3: 增益分析段
        if "13.3\u4e2a\u767e\u5206\u70b9" in text:  # 13.3个百分点
            checks["B3_gain_analysis"] = True
            print(f"  \u2705 B3. \u589e\u76ca\u5206\u6790\u6bb5 @ #{i}: {text[:60]}...")

        # C: 消融实验
        if "\u51ed\u8bc1\u81ea\u6108\u6d88\u878d\u5b9e\u9a8c" in text:  # 凭证自愈消融实验
            checks["C_ablation_title"] = True
            print(f"  \u2705 C1. \u6d88\u878d\u5b9e\u9a8c\u6807\u9898 @ #{i}: {text}")

        if child.tag == f'{W}tbl' and "Level 0" in text:
            checks["C_ablation_table"] = True
            rows = child.findall(f'{W}tr')
            print(f"  \u2705 C2. \u6d88\u878d\u8868 @ #{i}: {len(rows)}\u884c")
            for ri, row in enumerate(rows):
                cells = row.findall(f'{W}tc')
                cell_texts = [get_text(c) for c in cells]
                print(f"       \u884c{ri}: {cell_texts}")

        # D1: 摘要后处理
        if "\u5e76\u8bbe\u8ba1\u540e\u5904\u7406\u589e\u5f3a\u7b56\u7565" in text:  # 并设计后处理增强策略
            checks["D1_abstract_postproc"] = True
            print(f"  \u2705 D1. \u6458\u8981\u540e\u5904\u7406 @ #{i}: ...{text[text.index(chr(38598)):text.index(chr(38598))+30]}...")

        # D2: 摘要消融
        if "\u6d88\u878d\u5b9e\u9a8c\u9a8c\u8bc1" in text:  # 消融实验验证
            if i < 60:  # 仅在摘要区域
                checks["D2_abstract_ablation"] = True
                print(f"  \u2705 D2. \u6458\u8981\u6d88\u878d @ #{i}: ...{text[:80]}...")

    print(f"\n{'='*50}")
    all_ok = all(checks.values())
    for k, v in checks.items():
        icon = "\u2705" if v else "\u274c"
        print(f"  {icon} {k}")
    print(f"{'='*50}")
    if all_ok:
        print("\u2705 \u5168\u90e8\u68c0\u67e5\u901a\u8fc7!")
    else:
        failed = [k for k, v in checks.items() if not v]
        print(f"\u274c \u672a\u901a\u8fc7: {failed}")

    zf.close()

if __name__ == "__main__":
    main()
