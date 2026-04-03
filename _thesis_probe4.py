# -*- coding: utf-8 -*-
"""获取需要修改的段落完整文本"""
import zipfile
import xml.etree.ElementTree as ET

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

for idx in [59, 60, 61, 651, 598, 671, 820, 822]:
    t = get_text(children[idx])
    print(f"\n===== idx={idx} =====")
    print(t)

zf.close()
