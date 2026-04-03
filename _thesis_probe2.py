# -*- coding: utf-8 -*-
"""探查终稿中6处修改点的精确上下文"""
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

# 1. 5.2.4引导语 - "四个方面"
print("=" * 60)
print("修改点1: 5.2.4引导语")
for p in paras:
    if "容错隔离" in p["text"] and "四个方面" in p["text"]:
        print(f"  idx={p['idx']}: {p['text']}")
        break

# 2. 5.2引导语 - "5.2.4节验证系统在多源并行"
print("\n修改点2: 5.2引导语")
for p in paras:
    if "5.2.4节验证系统在多源并行" in p["text"]:
        print(f"  idx={p['idx']}: {p['text']}")
        break

# 3. 5.3引导语 - "为管线选型"
print("\n修改点3: 5.3引导语")
for p in paras:
    if "5.3.1节介绍实验设计" in p["text"]:
        print(f"  idx={p['idx']}: {p['text']}")
        break

# 4. 6.1总结 - 找"第四章"/"第四"相关总结段
print("\n修改点4&5: 6.1全文总结")
in_61 = False
for p in paras:
    t = p["text"]
    if "6.1" in t and "全文总结" in t:
        in_61 = True
        print(f"  === 6.1开始 idx={p['idx']}: {t}")
        continue
    if in_61:
        if re.match(r"6\.2", t):
            print(f"  === 6.2开始 idx={p['idx']}")
            break
        if t:
            print(f"  idx={p['idx']}: {t[:100]}...")

# 5. 英文摘要
print("\n修改点6: 英文摘要")
in_en = False
for p in paras:
    t = p["text"]
    if t.strip() == "Abstract":
        in_en = True
        print(f"  === Abstract idx={p['idx']}")
        continue
    if in_en:
        if re.match(r"Key\s*words", t) or re.match(r"目\s*录", t):
            print(f"  === End idx={p['idx']}: {t[:40]}")
            break
        if t:
            print(f"  idx={p['idx']}: {t[:120]}...")

zf.close()
