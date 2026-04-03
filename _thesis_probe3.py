# -*- coding: utf-8 -*-
"""探查6.1总结和英文摘要的完整内容"""
import zipfile
import xml.etree.ElementTree as ET
import re

DOCX = r"D:\Onedrive\桌面\杨志诚毕业论文1_终稿.docx"
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f'{{{WNS}}}'

def get_text(elem):
    return "".join(t.text or "" for t in elem.iter(f'{W}t')).strip()

zf = zipfile.ZipFile(DOCX)
raw = zf.read("word/document.xml")
root = ET.fromstring(raw)
body = root.find(f'{W}body')
children = list(body)

paras = []
for i, child in enumerate(children):
    text = get_text(child)
    tag = child.tag.split("}")[-1]
    paras.append({"idx": i, "tag": tag, "text": text})

# 找真正的6.1全文总结(不是目录里的)
print("=" * 60)
print("搜索所有包含'全文总结'的段落:")
for p in paras:
    if "全文总结" in p["text"]:
        print(f"  idx={p['idx']}: [{p['tag']}] {p['text'][:60]}")

# 输出idx 700-end附近 寻找第六章
print("\n" + "=" * 60)
print("idx 750+ 的段落:")
for p in paras:
    if p["idx"] >= 750 and p["text"]:
        print(f"  idx={p['idx']}: [{p['tag']}] {p['text'][:80]}")

# 英文摘要完整内容
print("\n" + "=" * 60)
print("英文摘要完整内容:")
for idx in [58, 59, 60, 61]:
    p = paras[idx]
    print(f"\n  idx={idx}: {p['text']}")

zf.close()
