# -*- coding: utf-8 -*-
"""
先探查修正版 docx 中关键段落的位置和 XML 结构，
为后续精准插入提供参考。
"""
import zipfile
import xml.etree.ElementTree as ET
import re

DOCX = r"D:\Onedrive\桌面\杨志诚毕业论文1_格式修正.docx"
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

def get_text(elem):
    return "".join(t.text or "" for t in elem.iter(f'{{{WNS}}}t')).strip()

def main():
    zf = zipfile.ZipFile(DOCX)
    raw = zf.read("word/document.xml")
    root = ET.fromstring(raw)
    body = root.find(f'{{{WNS}}}body')

    # 搜索关键段落
    targets = [
        "4.6 大模型",
        "4.5.3",
        "解析可用率评估",
        "凭证自愈验证",
        "配置安全验证",
        "运行效能",
        "表5-13",
        "表 5-13",
        "全文可用率综合对比",
        "全文可用率",
        "100.0",
        "73.3 个百分点",
        "验证了第4.5节选型",
        "表5-8",
        "表 5-8",
        "5.3.3",
        "常见错误类型",
    ]

    children = list(body)
    print(f"body 共有 {len(children)} 个顶级子元素\n")

    for i, child in enumerate(children):
        tag_short = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        text = get_text(child)

        # 看是否匹配目标
        matched = False
        for t in targets:
            if t in text:
                matched = True
                break

        if matched:
            # 打印元素信息
            print(f"=== 元素 #{i} [{tag_short}] ===")
            print(f"  文本: {text[:100]}")
            # 打印样式信息
            if tag_short == "p":
                ppr = child.find(f'{{{WNS}}}pPr')
                if ppr is not None:
                    pstyle = ppr.find(f'{{{WNS}}}pStyle')
                    if pstyle is not None:
                        print(f"  pStyle: {pstyle.get(f'{{{WNS}}}val', '')}")
                    jc = ppr.find(f'{{{WNS}}}jc')
                    if jc is not None:
                        print(f"  jc: {jc.get(f'{{{WNS}}}val', '')}")
                # 第一个run的字体
                for run in child.findall(f'{{{WNS}}}r')[:1]:
                    rpr = run.find(f'{{{WNS}}}rPr')
                    if rpr is not None:
                        rf = rpr.find(f'{{{WNS}}}rFonts')
                        sz = rpr.find(f'{{{WNS}}}sz')
                        b = rpr.find(f'{{{WNS}}}b')
                        if rf is not None:
                            print(f"  rFonts: ea={rf.get(f'{{{WNS}}}eastAsia','')}, ascii={rf.get(f'{{{WNS}}}ascii','')}")
                        if sz is not None:
                            print(f"  sz: {sz.get(f'{{{WNS}}}val','')}")
                        if b is not None:
                            print(f"  bold: True")

            elif tag_short == "tbl":
                # 打印表格前几行
                rows = child.findall(f'.//{{{WNS}}}tr')
                print(f"  表格共 {len(rows)} 行")
                for ri, row in enumerate(rows[:4]):
                    cells = row.findall(f'{{{WNS}}}tc')
                    cell_texts = [get_text(c)[:20] for c in cells]
                    print(f"  行{ri}: {cell_texts}")
            print()

    # 额外：在"4.6"附近看看上下文
    print("\n--- 4.6 附近的元素 ---")
    for i, child in enumerate(children):
        text = get_text(child)
        if "4.6" in text and "SFT" in text:
            for j in range(max(0,i-3), min(len(children), i+3)):
                tag_j = children[j].tag.split("}")[-1]
                txt_j = get_text(children[j])[:80]
                print(f"  #{j} [{tag_j}]: {txt_j}")
            break

    # 在"凭证自愈"附近
    print("\n--- 凭证自愈 附近 ---")
    for i, child in enumerate(children):
        text = get_text(child)
        if "凭证自愈验证" in text:
            for j in range(max(0,i-2), min(len(children), i+5)):
                tag_j = children[j].tag.split("}")[-1]
                txt_j = get_text(children[j])[:80]
                print(f"  #{j} [{tag_j}]: {txt_j}")
            break

    # 表5-13附近
    print("\n--- 表5-13 附近 ---")
    for i, child in enumerate(children):
        text = get_text(child)
        if "全文可用率综合对比" in text or "表5-13" in text or "表 5-13" in text:
            for j in range(max(0,i-2), min(len(children), i+6)):
                tag_j = children[j].tag.split("}")[-1]
                txt_j = get_text(children[j])[:80]
                print(f"  #{j} [{tag_j}]: {txt_j}")
            break

    zf.close()

if __name__ == "__main__":
    main()
