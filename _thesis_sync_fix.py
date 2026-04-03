# -*- coding: utf-8 -*-
"""
终稿内容同步修改脚本：6处引导语/总结/英文摘要同步更新
输入: 杨志诚毕业论文1_终稿.docx
输出: 杨志诚毕业论文1_终稿v2.docx
"""
import zipfile
import xml.etree.ElementTree as ET
import shutil
import os
import re

SRC = r"D:\Onedrive\桌面\杨志诚毕业论文1_终稿.docx"
DST = r"D:\Onedrive\桌面\杨志诚毕业论文1_终稿v2.docx"
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f'{{{WNS}}}'

ET.register_namespace('', WNS)
# 注册所有常见命名空间
for prefix, uri in [
    ('w', WNS),
    ('r', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'),
    ('wp', 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'),
    ('a', 'http://schemas.openxmlformats.org/drawingml/2006/main'),
    ('pic', 'http://schemas.openxmlformats.org/drawingml/2006/picture'),
    ('mc', 'http://schemas.openxmlformats.org/markup-compatibility/2006'),
    ('w14', 'http://schemas.microsoft.com/office/word/2010/wordml'),
    ('w15', 'http://schemas.microsoft.com/office/word/2012/wordml'),
    ('wps', 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape'),
    ('m', 'http://schemas.openxmlformats.org/officeDocument/2006/math'),
    ('v', 'urn:schemas-microsoft-com:vml'),
    ('o', 'urn:schemas-microsoft-com:office:office'),
    ('wpc', 'http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas'),
    ('wpg', 'http://schemas.microsoft.com/office/word/2010/wordprocessingGroup'),
    ('wp14', 'http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing'),
    ('w10', 'urn:schemas-microsoft-com:office:word'),
]:
    ET.register_namespace(prefix, uri)

def get_text(elem):
    return "".join(t.text or "" for t in elem.iter(f'{W}t')).strip()

def replace_in_runs(para, old_str, new_str):
    """在段落的run文本中执行替换，保持原有格式"""
    runs = para.findall(f'.//{W}r')
    # 收集所有 run 的 t 元素
    t_elems = []
    for run in runs:
        for t in run.findall(f'{W}t'):
            t_elems.append(t)

    # 拼接全文找到位置
    full = ""
    positions = []  # (t_elem, start_in_full, end_in_full)
    for t in t_elems:
        txt = t.text or ""
        start = len(full)
        full += txt
        positions.append((t, start, start + len(txt)))

    idx = full.find(old_str)
    if idx == -1:
        return False

    new_full = full[:idx] + new_str + full[idx + len(old_str):]

    # 重新分配文本到各 t 元素
    cursor = 0
    for i, (t, orig_start, orig_end) in enumerate(positions):
        orig_len = orig_end - orig_start
        # 计算新长度: 按比例分配不太好，用位移
        new_start = orig_start
        if orig_start > idx:
            new_start = orig_start + (len(new_str) - len(old_str))
        elif orig_start < idx and orig_end > idx:
            # 替换跨越了这个t元素
            pass

        # 简单策略: 把所有文本放到第一个t中，其余清空
        if i == 0:
            t.text = new_full
            t.set(f'{{{http://www.w3.org/XML/1998/namespace}}}space', 'preserve')
        else:
            t.text = ""

    return True

def simple_replace_in_para(para, old_str, new_str):
    """简单直接的替换：拼接所有t文本，替换，然后放回第一个t"""
    runs = para.findall(f'.//{W}r')
    t_elems = []
    for run in runs:
        for t in run.findall(f'{W}t'):
            t_elems.append(t)

    full = "".join(t.text or "" for t in t_elems)
    if old_str not in full:
        return False

    new_full = full.replace(old_str, new_str, 1)

    # 放入第一个t，其余清空
    for i, t in enumerate(t_elems):
        if i == 0:
            t.text = new_full
            t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        else:
            t.text = ""
    return True


def main():
    zf = zipfile.ZipFile(SRC, 'r')
    raw = zf.read("word/document.xml")
    root = ET.fromstring(raw)
    body = root.find(f'{W}body')
    children = list(body)

    changes = []

    # ================================================================
    # 修改1: idx=651 5.2.4引导语 "四个方面" → "五个方面"
    # 并加上"凭证自愈消融实验"
    # ================================================================
    p651 = children[651]
    old1 = "\u5bb9\u9519\u9694\u79bb\u3001\u51ed\u8bc1\u81ea\u6108\u3001\u914d\u7f6e\u5b89\u5168\u548c\u8fd0\u884c\u6548\u80fd\u56db\u4e2a\u65b9\u9762"
    new1 = "\u5bb9\u9519\u9694\u79bb\u3001\u51ed\u8bc1\u81ea\u6108\u3001\u51ed\u8bc1\u81ea\u6108\u6d88\u878d\u5b9e\u9a8c\u3001\u914d\u7f6e\u5b89\u5168\u548c\u8fd0\u884c\u6548\u80fd\u4e94\u4e2a\u65b9\u9762"
    if simple_replace_in_para(p651, old1, new1):
        changes.append("1. 5.2.4\u5f15\u5bfc\u8bed: \u56db\u4e2a\u65b9\u9762\u2192\u4e94\u4e2a\u65b9\u9762+\u6d88\u878d\u5b9e\u9a8c")
    else:
        changes.append("1. \u274c 5.2.4\u5f15\u5bfc\u8bed\u66ff\u6362\u5931\u8d25")

    # ================================================================
    # 修改2: idx=598 5.2引导语
    # "容错能力与运行效能。" → "容错能力与运行效能，并通过消融实验量化凭证自愈各层级的独立贡献。"
    # ================================================================
    p598 = children[598]
    old2 = "\u5bb9\u9519\u80fd\u529b\u4e0e\u8fd0\u884c\u6548\u80fd\u3002"
    new2 = "\u5bb9\u9519\u80fd\u529b\u4e0e\u8fd0\u884c\u6548\u80fd\uff0c\u5e76\u901a\u8fc7\u6d88\u878d\u5b9e\u9a8c\u91cf\u5316\u51ed\u8bc1\u81ea\u6108\u5404\u5c42\u7ea7\u7684\u72ec\u7acb\u8d21\u732e\u3002"
    if simple_replace_in_para(p598, old2, new2):
        changes.append("2. 5.2\u5f15\u5bfc\u8bed: \u52a0\u6d88\u878d\u5b9e\u9a8c\u8bf4\u660e")
    else:
        changes.append("2. \u274c 5.2\u5f15\u5bfc\u8bed\u66ff\u6362\u5931\u8d25")

    # ================================================================
    # 修改3: idx=671 5.3引导语
    # "为管线选型决策提供量化依据。" → "为管线选型决策提供量化依据，并量化评估后处理规则的独立增益。"
    # ================================================================
    p671 = children[671]
    old3 = "\u4e3a\u7ba1\u7ebf\u9009\u578b\u51b3\u7b56\u63d0\u4f9b\u91cf\u5316\u4f9d\u636e\u3002"
    new3 = "\u4e3a\u7ba1\u7ebf\u9009\u578b\u51b3\u7b56\u63d0\u4f9b\u91cf\u5316\u4f9d\u636e\uff0c\u5e76\u91cf\u5316\u8bc4\u4f30\u540e\u5904\u7406\u89c4\u5219\u7684\u72ec\u7acb\u589e\u76ca\u3002"
    if simple_replace_in_para(p671, old3, new3):
        changes.append("3. 5.3\u5f15\u5bfc\u8bed: \u52a0\u540e\u5904\u7406\u589e\u76ca\u8bf4\u660e")
    else:
        changes.append("3. \u274c 5.3\u5f15\u5bfc\u8bed\u66ff\u6362\u5931\u8d25")

    # ================================================================
    # 修改4: idx=820 6.1总结第二点 - 采集层 加消融实验
    # "提升了长时间运行场景下的采集稳定性。" →
    # "提升了长时间运行场景下的采集稳定性；消融实验定量验证了三级递进策略中各层级的独立贡献，Level 2会话重建贡献了最大增益。"
    # ================================================================
    p820 = children[820]
    old4 = "\u63d0\u5347\u4e86\u957f\u65f6\u95f4\u8fd0\u884c\u573a\u666f\u4e0b\u7684\u91c7\u96c6\u7a33\u5b9a\u6027\u3002"
    new4 = "\u63d0\u5347\u4e86\u957f\u65f6\u95f4\u8fd0\u884c\u573a\u666f\u4e0b\u7684\u91c7\u96c6\u7a33\u5b9a\u6027\uff1b\u6d88\u878d\u5b9e\u9a8c\u5b9a\u91cf\u9a8c\u8bc1\u4e86\u4e09\u7ea7\u9012\u8fdb\u7b56\u7565\u4e2d\u5404\u5c42\u7ea7\u7684\u72ec\u7acb\u8d21\u732e\uff0cLevel\u00a02\u4f1a\u8bdd\u91cd\u5efa\u8d21\u732e\u4e86\u6700\u5927\u589e\u76ca\u3002"
    if simple_replace_in_para(p820, old4, new4):
        changes.append("4. 6.1\u603b\u7ed3\u7b2c\u4e8c\u70b9: \u52a0\u6d88\u878d\u5b9e\u9a8c\u7ed3\u679c")
    else:
        changes.append("4. \u274c 6.1\u603b\u7ed3\u7b2c\u4e8c\u70b9\u66ff\u6362\u5931\u8d25")

    # ================================================================
    # 修改5: idx=822 6.1总结第四点 - MinerU 加后处理增益
    # "有效克服了双栏排版与复杂表格的提取难题。" →
    # "有效克服了双栏排版与复杂表格的提取难题。对比实验进一步表明，后处理规则为全文可用率带来了13.3个百分点的增益，验证了后处理增强策略的有效性。"
    # ================================================================
    p822 = children[822]
    old5 = "\u6709\u6548\u514b\u670d\u4e86\u53cc\u680f\u6392\u7248\u4e0e\u590d\u6742\u8868\u683c\u7684\u63d0\u53d6\u96be\u9898\u3002"
    new5 = "\u6709\u6548\u514b\u670d\u4e86\u53cc\u680f\u6392\u7248\u4e0e\u590d\u6742\u8868\u683c\u7684\u63d0\u53d6\u96be\u9898\u3002\u5bf9\u6bd4\u5b9e\u9a8c\u8fdb\u4e00\u6b65\u8868\u660e\uff0c\u540e\u5904\u7406\u89c4\u5219\u4e3a\u5168\u6587\u53ef\u7528\u7387\u5e26\u6765\u4e86\u0031\u0033\u002e\u0033\u4e2a\u767e\u5206\u70b9\u7684\u589e\u76ca\uff0c\u9a8c\u8bc1\u4e86\u540e\u5904\u7406\u589e\u5f3a\u7b56\u7565\u7684\u6709\u6548\u6027\u3002"
    if simple_replace_in_para(p822, old5, new5):
        changes.append("5. 6.1\u603b\u7ed3\u7b2c\u56db\u70b9: \u52a0\u540e\u5904\u7406\u589e\u76ca")
    else:
        changes.append("5. \u274c 6.1\u603b\u7ed3\u7b2c\u56db\u70b9\u66ff\u6362\u5931\u8d25")

    # ================================================================
    # 修改6a: idx=60 英文摘要 - 加post-processing
    # "...that traditional tools cannot adequately address." →
    # "...that traditional tools cannot adequately address. A post-processing enhancement strategy is further designed to improve parsing availability."
    # ================================================================
    p60 = children[60]
    old6a = "that traditional tools cannot adequately address."
    new6a = "that traditional tools cannot adequately address. A post-processing enhancement strategy is further designed to improve full-text availability."
    if simple_replace_in_para(p60, old6a, new6a):
        changes.append("6a. \u82f1\u6587\u6458\u8981: \u52a0post-processing")
    else:
        changes.append("6a. \u274c \u82f1\u6587\u6458\u8981post-processing\u66ff\u6362\u5931\u8d25")

    # ================================================================
    # 修改6b: idx=59 英文摘要 - 加ablation
    # "three-level Token self-healing fault-tolerance mechanism" 后加ablation
    # 在 ", while introducing" 前加 ", and validates the independent contribution of each level through ablation experiments"
    # ================================================================
    p59 = children[59]
    old6b = "three-level Token self-healing fault-tolerance mechanism, while introducing"
    new6b = "three-level Token self-healing fault-tolerance mechanism\u2014whose effectiveness is validated through ablation experiments\u2014while introducing"
    if simple_replace_in_para(p59, old6b, new6b):
        changes.append("6b. \u82f1\u6587\u6458\u8981: \u52a0ablation")
    else:
        changes.append("6b. \u274c \u82f1\u6587\u6458\u8981ablation\u66ff\u6362\u5931\u8d25")

    # ================================================================
    # 修改6c: idx=61 英文摘要 - 加post-processing增益数据
    # "improves by 73.3 percentage points over PyMuPDF" →
    # "improves by 73.3 percentage points over PyMuPDF, with post-processing rules contributing a 13.3-percentage-point gain"
    # ================================================================
    p61 = children[61]
    old6c = "improves by 73.3 percentage points over PyMuPDF"
    new6c = "improves by 73.3 percentage points over PyMuPDF, with post-processing rules contributing a 13.3-percentage-point gain"
    if simple_replace_in_para(p61, old6c, new6c):
        changes.append("6c. \u82f1\u6587\u6458\u8981: \u52a0\u589e\u76ca\u6570\u636e")
    else:
        changes.append("6c. \u274c \u82f1\u6587\u6458\u8981\u589e\u76ca\u6570\u636e\u66ff\u6362\u5931\u8d25")

    # ================================================================
    # 写出
    # ================================================================
    new_xml = ET.tostring(root, encoding='unicode', xml_declaration=True)
    # 修补声明
    if not new_xml.startswith("<?xml"):
        new_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + new_xml

    shutil.copy2(SRC, DST)
    with zipfile.ZipFile(DST, 'a') as zout:
        zout.writestr("word/document.xml", new_xml.encode("utf-8"))

    print("\n" + "=" * 60)
    print(f"\u4fee\u6539\u7ed3\u679c ({len(changes)}\u9879):")
    print("=" * 60)
    for c in changes:
        print(f"  {c}")
    print(f"\n\u8f93\u51fa: {DST}")

    zf.close()

if __name__ == "__main__":
    main()
