# -*- coding: utf-8 -*-
"""
终稿综合审查脚本：格式 + 内容一致性 + 交叉引用 + 摘要字数
"""
import zipfile
import xml.etree.ElementTree as ET
import re
from collections import defaultdict, Counter

DOCX = r"D:\Onedrive\桌面\杨志诚毕业论文1_终稿v2.docx"
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f'{{{WNS}}}'

def get_text(elem):
    return "".join(t.text or "" for t in elem.iter(f'{W}t')).strip()

def get_run_info(run):
    rpr = run.find(f'{W}rPr')
    info = {}
    if rpr is None:
        return info
    rf = rpr.find(f'{W}rFonts')
    if rf is not None:
        info["eastAsia"] = rf.get(f'{W}eastAsia', '')
        info["ascii"] = rf.get(f'{W}ascii', '')
    sz = rpr.find(f'{W}sz')
    if sz is not None:
        info["sz_hp"] = int(sz.get(f'{W}val', '0'))
    b = rpr.find(f'{W}b')
    if b is not None:
        info["bold"] = True
    return info

def main():
    zf = zipfile.ZipFile(DOCX)
    raw = zf.read("word/document.xml")
    root = ET.fromstring(raw)
    body = root.find(f'{W}body')
    children = list(body)

    all_text = []
    issues = []
    warnings = []

    # 收集所有段落
    paras = []
    for i, child in enumerate(children):
        text = get_text(child)
        tag = child.tag.split("}")[-1]
        runs = []
        if tag == "p":
            for r in child.findall(f'{W}r'):
                runs.append(get_run_info(r))
        paras.append({"idx": i, "tag": tag, "text": text, "runs": runs, "elem": child})
        all_text.append(text)

    full_text = "\n".join(all_text)

    # ================================================================
    # 1. 页眉残留检查
    # ================================================================
    print("=" * 60)
    print("[1] \u9875\u7709\u6b8b\u7559\u68c0\u67e5")
    print("=" * 60)
    rels_raw = zf.read("word/_rels/document.xml.rels")
    rels_root = ET.fromstring(rels_raw)
    ns_rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    header_ok = True
    for rel in rels_root.findall(f'{{{ns_rel}}}Relationship'):
        target = rel.get("Target", "")
        if "header" not in target.lower():
            continue
        try:
            hraw = zf.read(f"word/{target}")
        except KeyError:
            continue
        hroot = ET.fromstring(hraw)
        htexts = [get_text(p) for p in hroot.findall(f'.//{W}p') if get_text(p)]
        combined = " | ".join(htexts)
        if not combined:
            continue
        probs = []
        if "\u53cc\u51fb\u9875\u7709" in combined:
            probs.append("\u6a21\u677f\u6b8b\u7559")
        if "\u535a\u58eb/\u7855\u58eb" in combined:
            probs.append("\u535a\u58eb/\u7855\u58eb")
        if "\u5fae\u670d\u52a1\u67b6\u6784" in combined:
            probs.append("\u7ae0\u540d\u9519\u8bef")
        if "\u5316\u5b66\u54c1\u5546\u57ce" in combined:
            probs.append("\u7ae0\u540d\u9519\u8bef")
        if probs:
            issues.append(f"\u9875\u7709 {target}: {', '.join(probs)}")
            header_ok = False
    if header_ok:
        print("  \u2705 \u9875\u7709\u65e0\u6b8b\u7559\u95ee\u9898")
    else:
        for iss in issues:
            print(f"  \u274c {iss}")

    # ================================================================
    # 2. Segoe UI 检查
    # ================================================================
    print(f"\n{'='*60}")
    print("[2] Segoe UI \u68c0\u67e5")
    print("=" * 60)
    segoe = raw.decode("utf-8", errors="ignore").count("Segoe UI")
    if segoe:
        print(f"  \u274c \u4ecd\u6709 {segoe} \u5904 Segoe UI")
        issues.append(f"Segoe UI {segoe}\u5904")
    else:
        print("  \u2705 \u65e0 Segoe UI")

    # ================================================================
    # 3. [n] 引用检查
    # ================================================================
    print(f"\n{'='*60}")
    print("[3] [n] \u5f15\u7528\u68c0\u67e5")
    print("=" * 60)
    bracket_refs = re.findall(r'\[\d+\]', full_text)
    if bracket_refs:
        unique = sorted(set(bracket_refs))
        print(f"  \u26a0\ufe0f \u4ecd\u6709 {len(bracket_refs)} \u5904: {', '.join(unique[:10])}")
        warnings.append(f"[n]\u5f15\u7528\u6b8b\u7559 {len(bracket_refs)}\u5904")
    else:
        print("  \u2705 \u65e0 [n] \u5f15\u7528")

    # ================================================================
    # 4. 中文摘要字数
    # ================================================================
    print(f"\n{'='*60}")
    print("[4] \u4e2d\u6587\u6458\u8981\u5b57\u6570")
    print("=" * 60)
    in_abs = False
    abs_text = []
    for p in paras:
        t = p["text"]
        if re.match(r"\u6458\s*\u8981", t) and len(t) < 10:
            in_abs = True
            continue
        if in_abs:
            if re.match(r"(\u5173\s*\u952e\s*\u8bcd|ABSTRACT|Abstract|\u76ee\s*\u5f55)", t):
                break
            if t:
                abs_text.append(t)
    abs_chars = sum(len(t) for t in abs_text)
    if abs_chars > 800:
        print(f"  \u26a0\ufe0f \u4e2d\u6587\u6458\u8981\u7ea6 {abs_chars} \u5b57\uff08\u8d85\u8fc7800\u5b57\u4e0a\u9650\uff09")
        warnings.append(f"\u6458\u8981{abs_chars}\u5b57>\u200b800")
    else:
        print(f"  \u2705 \u4e2d\u6587\u6458\u8981\u7ea6 {abs_chars} \u5b57")

    # ================================================================
    # 5. 图表编号连续性检查
    # ================================================================
    print(f"\n{'='*60}")
    print("[5] \u56fe\u8868\u7f16\u53f7\u8fde\u7eed\u6027")
    print("=" * 60)
    fig_nums = defaultdict(list)
    tbl_nums = defaultdict(list)
    for p in paras:
        t = p["text"]
        for m in re.finditer(r'\u56fe\s*(\d+)-(\d+)', t):
            ch, num = int(m.group(1)), int(m.group(2))
            fig_nums[ch].append(num)
        for m in re.finditer(r'\u8868\s*(\d+)-(\d+)', t):
            ch, num = int(m.group(1)), int(m.group(2))
            tbl_nums[ch].append(num)

    for ch in sorted(fig_nums):
        nums = sorted(set(fig_nums[ch]))
        expected = list(range(1, max(nums) + 1))
        missing = set(expected) - set(nums)
        if missing:
            print(f"  \u26a0\ufe0f \u56fe{ch}-x: \u7f3a\u5c11 {sorted(missing)}")
            warnings.append(f"\u56fe{ch}\u7f16\u53f7\u7f3a{missing}")
        else:
            print(f"  \u2705 \u56fe{ch}-1~{max(nums)} \u8fde\u7eed")

    for ch in sorted(tbl_nums):
        nums = sorted(set(tbl_nums[ch]))
        expected = list(range(1, max(nums) + 1))
        missing = set(expected) - set(nums)
        if missing:
            msg = f"\u8868{ch}-x: \u7f3a\u5c11 {sorted(missing)}"
            # 表5-7b 是新加的消融表，不在主序列中
            if ch == 5 and 8 not in missing:
                pass  # 可能是5-7b的问题
            print(f"  \u26a0\ufe0f {msg}")
            warnings.append(msg)
        else:
            print(f"  \u2705 \u88685-1~{max(nums)} \u8fde\u7eed" if ch == 5 else f"  \u2705 \u8868{ch}-1~{max(nums)} \u8fde\u7eed")

    # ================================================================
    # 6. 新增内容与原文衔接检查
    # ================================================================
    print(f"\n{'='*60}")
    print("[6] \u65b0\u589e\u5185\u5bb9\u4e0e\u539f\u6587\u884d\u63a5\u68c0\u67e5")
    print("=" * 60)

    # 6a: 4.5.3后处理开关段 → 下一段应是"4.6"
    for i, p in enumerate(paras):
        if "\u540e\u5904\u7406\u5f00\u5173\u53c2\u6570" in p["text"]:
            next_text = paras[i+1]["text"] if i+1 < len(paras) else ""
            if "4.6" in next_text:
                print(f"  \u2705 4.5.3\u540e\u5904\u7406\u6bb5 \u2192 \u4e0b\u4e00\u6bb5\u662f 4.6 \u2705")
            else:
                print(f"  \u274c 4.5.3\u540e\u5904\u7406\u6bb5\u540e\u4e0d\u662f4.6\uff0c\u800c\u662f: {next_text[:40]}")
                issues.append("4.5.3\u540e\u5904\u7406\u6bb5\u540e\u7eed\u8854\u63a5\u5f02\u5e38")
            break

    # 6b: 消融实验 → 前面应是"凭证自愈验证"，后面应是"配置安全验证"
    for i, p in enumerate(paras):
        if "\u51ed\u8bc1\u81ea\u6108\u6d88\u878d\u5b9e\u9a8c" in p["text"] and len(p["text"]) < 30:
            prev_texts = [paras[j]["text"] for j in range(max(0,i-3), i)]
            found_prev = any("\u51ed\u8bc1\u81ea\u6108\u9a8c\u8bc1" in t for t in prev_texts)
            # 找后面的"配置安全验证"
            found_next = False
            for j in range(i+1, min(i+10, len(paras))):
                if "\u914d\u7f6e\u5b89\u5168\u9a8c\u8bc1" in paras[j]["text"]:
                    found_next = True
                    break
            if found_prev:
                print(f"  \u2705 \u6d88\u878d\u5b9e\u9a8c\u524d\u65b9\u662f\u201c\u51ed\u8bc1\u81ea\u6108\u9a8c\u8bc1\u201d")
            else:
                print(f"  \u274c \u6d88\u878d\u5b9e\u9a8c\u524d\u65b9\u672a\u627e\u5230\u201c\u51ed\u8bc1\u81ea\u6108\u9a8c\u8bc1\u201d")
                issues.append("\u6d88\u878d\u5b9e\u9a8c\u4f4d\u7f6e\u5f02\u5e38")
            if found_next:
                print(f"  \u2705 \u6d88\u878d\u5b9e\u9a8c\u540e\u65b9\u662f\u201c\u914d\u7f6e\u5b89\u5168\u9a8c\u8bc1\u201d")
            else:
                print(f"  \u274c \u6d88\u878d\u5b9e\u9a8c\u540e\u65b9\u672a\u627e\u5230\u201c\u914d\u7f6e\u5b89\u5168\u9a8c\u8bc1\u201d")
                issues.append("\u6d88\u878d\u5b9e\u9a8c\u540e\u7eed\u8854\u63a5\u5f02\u5e38")
            break

    # 6c: 表5-13增益分析段 → 后面应是"以上结果表明"
    for i, p in enumerate(paras):
        if "13.3\u4e2a\u767e\u5206\u70b9" in p["text"]:
            next_text = paras[i+1]["text"] if i+1 < len(paras) else ""
            if "\u4ee5\u4e0a\u7ed3\u679c\u8868\u660e" in next_text:
                print(f"  \u2705 \u589e\u76ca\u5206\u6790\u6bb5 \u2192 \u4e0b\u4e00\u6bb5\u662f\u201c\u4ee5\u4e0a\u7ed3\u679c\u8868\u660e\u201d")
            else:
                print(f"  \u274c \u589e\u76ca\u5206\u6790\u6bb5\u540e\u4e0d\u662f\u201c\u4ee5\u4e0a\u7ed3\u679c\u201d\uff0c\u800c\u662f: {next_text[:40]}")
            break

    # ================================================================
    # 7. 新增段落字体格式检查
    # ================================================================
    print(f"\n{'='*60}")
    print("[7] \u65b0\u589e\u6bb5\u843d\u5b57\u4f53\u683c\u5f0f\u68c0\u67e5")
    print("=" * 60)

    new_content_markers = [
        "\u540e\u5904\u7406\u5f00\u5173\u53c2\u6570",  # 后处理开关参数
        "\u51ed\u8bc1\u81ea\u6108\u6d88\u878d\u5b9e\u9a8c",  # 凭证自愈消融实验
        "13.3\u4e2a\u767e\u5206\u70b9",  # 13.3个百分点
        "Level 0\u914d\u7f6e\u4e0b",  # Level 0配置下
    ]
    for marker in new_content_markers:
        for p in paras:
            if marker in p["text"] and p["runs"]:
                r0 = p["runs"][0]
                ea = r0.get("eastAsia", "")
                asc = r0.get("ascii", "")
                sz = r0.get("sz_hp", 0)
                ok = True
                details = []
                if ea and "\u5b8b" not in ea:
                    ok = False
                    details.append(f"\u4e2d\u6587={ea}")
                if asc and "Times" not in asc:
                    ok = False
                    details.append(f"\u82f1\u6587={asc}")
                if sz and sz != 24:
                    ok = False
                    details.append(f"\u5b57\u53f7={sz/2}pt")
                if ok:
                    print(f"  \u2705 \u201c{marker[:15]}\u201d: \u5b8b\u4f53/TNR/\u5c0f\u56db")
                else:
                    print(f"  \u274c \u201c{marker[:15]}\u201d: {', '.join(details)}")
                    issues.append(f"\u65b0\u589e\u6bb5\u843d\u683c\u5f0f: {marker[:15]}")
                break

    # ================================================================
    # 8. 目录一致性（检查目录中章标题数字是否粘连）
    # ================================================================
    print(f"\n{'='*60}")
    print("[8] \u76ee\u5f55\u7ae0\u6807\u9898\u68c0\u67e5")
    print("=" * 60)
    toc_issues = []
    for p in paras:
        t = p["text"]
        if re.match(r'\u7b2c[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d]\u7ae0\s', t):
            if re.search(r'\d+$', t):
                toc_issues.append(f"\u201c{t}\u201d \u2014 \u672b\u5c3e\u7c98\u8fde\u9875\u7801")
    if toc_issues:
        for ti in toc_issues:
            print(f"  \u26a0\ufe0f {ti}")
        # 区分目录区和正文区
        print("  \u2192 \u8fd9\u4e9b\u5728\u76ee\u5f55\u533a\u57df\uff0c\u8bf7\u5728Word\u4e2d\u66f4\u65b0\u76ee\u5f55\u57df")
        warnings.append("\u76ee\u5f55\u7ae0\u6807\u9898\u9875\u7801\u7c98\u8fde")
    else:
        print("  \u2705 \u65e0\u95ee\u9898")

    # ================================================================
    # 9. 5.2.4节引导语检查（是否提到了消融实验）
    # ================================================================
    print(f"\n{'='*60}")
    print("[9] 5.2.4\u8282\u5f15\u5bfc\u8bed\u4e00\u81f4\u6027")
    print("=" * 60)
    for p in paras:
        t = p["text"]
        if "\u5bb9\u9519\u9694\u79bb\u3001\u51ed\u8bc1\u81ea\u6108\u3001\u914d\u7f6e\u5b89\u5168\u548c\u8fd0\u884c\u6548\u80fd" in t:
            print(f"  \u26a0\ufe0f 5.2.4\u5f15\u5bfc\u8bed\u4ec5\u63d0\u53ca\u201c\u5bb9\u9519\u9694\u79bb\u3001\u51ed\u8bc1\u81ea\u6108\u3001\u914d\u7f6e\u5b89\u5168\u548c\u8fd0\u884c\u6548\u80fd\u56db\u4e2a\u65b9\u9762\u201d")
            print(f"    \u2192 \u5efa\u8bae\u6539\u4e3a\u201c\u4e94\u4e2a\u65b9\u9762\u201d\u5e76\u52a0\u4e0a\u201c\u51ed\u8bc1\u81ea\u6108\u6d88\u878d\u5b9e\u9a8c\u201d")
            warnings.append("5.2.4\u5f15\u5bfc\u8bed\u672a\u63d0\u53ca\u6d88\u878d\u5b9e\u9a8c")
            break

    # ================================================================
    # 10. 5.2节引导语检查
    # ================================================================
    print(f"\n{'='*60}")
    print("[10] 5.2\u8282\u5f15\u5bfc\u8bed\u4e00\u81f4\u6027")
    print("=" * 60)
    for p in paras:
        t = p["text"]
        if "5.2.4\u8282\u9a8c\u8bc1\u7cfb\u7edf\u5728\u591a\u6e90\u5e76\u884c" in t:
            if "\u6d88\u878d" not in t:
                print(f"  \u26a0\ufe0f 5.2\u8282\u5f15\u5bfc\u8bed\u63d0\u53ca5.2.4\u8282\u65f6\u672a\u5305\u542b\u6d88\u878d\u5b9e\u9a8c")
                print(f"    \u2192 \u5efa\u8bae\u5728\u201c\u5bb9\u9519\u80fd\u529b\u4e0e\u8fd0\u884c\u6548\u80fd\u201d\u540e\u52a0\u201c\uff0c\u5e76\u901a\u8fc7\u6d88\u878d\u5b9e\u9a8c\u91cf\u5316\u51ed\u8bc1\u81ea\u6108\u5404\u5c42\u7ea7\u7684\u72ec\u7acb\u8d21\u732e\u201d")
                warnings.append("5.2\u8282\u5f15\u5bfc\u8bed\u672a\u63d0\u53ca\u6d88\u878d")
            break

    # ================================================================
    # 11. 5.3节引导语检查（是否提到了原始vs增强对比）
    # ================================================================
    print(f"\n{'='*60}")
    print("[11] 5.3\u8282\u5f15\u5bfc\u8bed\u4e00\u81f4\u6027")
    print("=" * 60)
    for p in paras:
        t = p["text"]
        if "5.3.1\u8282\u4ecb\u7ecd\u5b9e\u9a8c\u8bbe\u8ba1" in t:
            if "\u539f\u59cb" not in t and "\u589e\u5f3a" not in t and "\u540e\u5904\u7406" not in t:
                print(f"  \u26a0\ufe0f 5.3\u8282\u5f15\u5bfc\u8bed\u672a\u63d0\u53ca\u539f\u59cb/\u589e\u5f3a\u5bf9\u6bd4")
                print(f"    \u2192 \u5efa\u8bae\u5728\u201c\u4e3a\u7ba1\u7ebf\u9009\u578b\u201d\u540e\u52a0\u201c\u5e76\u91cf\u5316\u8bc4\u4f30\u540e\u5904\u7406\u89c4\u5219\u7684\u72ec\u7acb\u589e\u76ca\u201d")
                warnings.append("5.3\u8282\u5f15\u5bfc\u8bed\u672a\u63d0\u53ca\u540e\u5904\u7406\u5bf9\u6bd4")
            break

    # ================================================================
    # 12. 6.1全文总结检查
    # ================================================================
    print(f"\n{'='*60}")
    print("[12] 6.1\u5168\u6587\u603b\u7ed3\u68c0\u67e5")
    print("=" * 60)
    in_61 = False
    summary_text = ""
    for p in paras:
        t = p["text"]
        if "6.1" in t and "\u5168\u6587\u603b\u7ed3" in t:
            in_61 = True
            continue
        if in_61:
            if re.match(r"6\.2", t):
                break
            summary_text += t

    has_postproc = "\u540e\u5904\u7406\u589e\u5f3a" in summary_text or "\u539f\u59cb\u4e0e\u589e\u5f3a" in summary_text or "\u540e\u5904\u7406\u89c4\u5219" in summary_text
    has_ablation = "\u6d88\u878d" in summary_text or "\u4e09\u7ea7\u9012\u8fdb" in summary_text

    if has_postproc:
        print(f"  \u2705 \u603b\u7ed3\u4e2d\u63d0\u53ca\u4e86\u540e\u5904\u7406\u589e\u5f3a")
    else:
        print(f"  \u26a0\ufe0f \u603b\u7ed3\u4e2d\u672a\u63d0\u53ca\u540e\u5904\u7406\u589e\u5f3a\u7b56\u7565")
        print(f"    \u2192 \u5efa\u8bae\u5728\u7b2c\u56db\u70b9\u603b\u7ed3\u4e2d\u52a0\u201c\u901a\u8fc7\u5bf9\u6bd4\u5b9e\u9a8c\u9a8c\u8bc1\u4e86\u540e\u5904\u7406\u89c4\u5219\u5e26\u676513.3\u4e2a\u767e\u5206\u70b9\u7684\u53ef\u7528\u7387\u589e\u76ca\u201d")
        warnings.append("\u603b\u7ed3\u672a\u63d0\u540e\u5904\u7406\u589e\u5f3a")

    if has_ablation:
        print(f"  \u2705 \u603b\u7ed3\u4e2d\u63d0\u53ca\u4e86\u6d88\u878d\u5b9e\u9a8c")
    else:
        print(f"  \u26a0\ufe0f \u603b\u7ed3\u4e2d\u672a\u63d0\u53ca\u51ed\u8bc1\u81ea\u6108\u6d88\u878d\u5b9e\u9a8c")
        print(f"    \u2192 \u5efa\u8bae\u5728\u603b\u7ed3\u91c7\u96c6\u5c42\u90e8\u5206\u52a0\u201c\u6d88\u878d\u5b9e\u9a8c\u5b9a\u91cf\u9a8c\u8bc1\u4e86\u4e09\u7ea7\u9012\u8fdb\u7b56\u7565\u7684\u6709\u6548\u6027\u201d")
        warnings.append("\u603b\u7ed3\u672a\u63d0\u6d88\u878d")

    # ================================================================
    # 13. 英文摘要一致性
    # ================================================================
    print(f"\n{'='*60}")
    print("[13] \u82f1\u6587\u6458\u8981\u4e00\u81f4\u6027")
    print("=" * 60)
    in_en = False
    en_abs = ""
    for p in paras:
        t = p["text"]
        if t.strip() == "Abstract":
            in_en = True
            continue
        if in_en:
            if re.match(r"Key\s*words", t) or re.match(r"\u76ee\s*\u5f55", t):
                break
            en_abs += t + " "

    if "post-processing" in en_abs.lower() or "postprocessing" in en_abs.lower():
        print(f"  \u2705 \u82f1\u6587\u6458\u8981\u542b post-processing")
    else:
        print(f"  \u26a0\ufe0f \u82f1\u6587\u6458\u8981\u672a\u63d0\u53ca post-processing/\u540e\u5904\u7406\u589e\u5f3a")
        warnings.append("\u82f1\u6587\u6458\u8981\u672a\u540c\u6b65\u540e\u5904\u7406")

    if "ablation" in en_abs.lower():
        print(f"  \u2705 \u82f1\u6587\u6458\u8981\u542b ablation")
    else:
        print(f"  \u26a0\ufe0f \u82f1\u6587\u6458\u8981\u672a\u63d0\u53ca ablation/\u6d88\u878d\u5b9e\u9a8c")
        warnings.append("\u82f1\u6587\u6458\u8981\u672a\u540c\u6b65\u6d88\u878d")

    # ================================================================
    # 汇总
    # ================================================================
    print(f"\n{'='*60}")
    print("\u7efc\u5408\u5ba1\u67e5\u6c47\u603b")
    print("=" * 60)
    if issues:
        print(f"\n\u274c \u5fc5\u987b\u4fee\u6539 ({len(issues)}\u9879):")
        for iss in issues:
            print(f"  \u2022 {iss}")
    else:
        print(f"\n\u2705 \u65e0\u5fc5\u987b\u4fee\u6539\u9879")

    if warnings:
        print(f"\n\u26a0\ufe0f \u5efa\u8bae\u4fee\u6539 ({len(warnings)}\u9879):")
        for w in warnings:
            print(f"  \u2022 {w}")
    else:
        print(f"\n\u2705 \u65e0\u5efa\u8bae\u4fee\u6539\u9879")

    zf.close()

if __name__ == "__main__":
    main()
