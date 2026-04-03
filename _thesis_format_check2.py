"""深度检查：参考文献格式、前置部分、图表编号"""
import zipfile
import xml.etree.ElementTree as ET
import re

DOCX_PATH = r"D:\Onedrive\桌面\杨志诚毕业论文1.docx"
NSMAP = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

def get_text(elem):
    texts = []
    for t in elem.iter(f'{{{NSMAP["w"]}}}t'):
        texts.append(t.text or "")
    return "".join(texts).strip()

def get_run_info(run):
    rpr = run.find(f'{{{NSMAP["w"]}}}rPr')
    info = {}
    if rpr is None:
        return info
    rf = rpr.find(f'{{{NSMAP["w"]}}}rFonts')
    if rf is not None:
        info["eastAsia"] = rf.get(f'{{{NSMAP["w"]}}}eastAsia', '')
        info["ascii"] = rf.get(f'{{{NSMAP["w"]}}}ascii', '')
    sz = rpr.find(f'{{{NSMAP["w"]}}}sz')
    if sz is not None:
        info["sz_hp"] = int(sz.get(f'{{{NSMAP["w"]}}}val', '0'))
    return info

def main():
    zf = zipfile.ZipFile(DOCX_PATH)
    raw = zf.read("word/document.xml")
    root = ET.fromstring(raw)
    body = root.find(f'{{{NSMAP["w"]}}}body')

    all_paras = []
    for p in body.findall(f'{{{NSMAP["w"]}}}p'):
        text = get_text(p)
        runs = []
        for r in p.findall(f'{{{NSMAP["w"]}}}r'):
            ri = get_run_info(r)
            rt = ""
            for t in r.findall(f'{{{NSMAP["w"]}}}t'):
                rt += t.text or ""
            ri["text"] = rt
            runs.append(ri)
        all_paras.append((text, runs))

    # ---- 1. 查找前置部分完整顺序 ----
    print("=" * 60)
    print("【A】前置部分完整顺序（前100段）")
    print("=" * 60)
    for i, (text, _) in enumerate(all_paras[:100]):
        if text and len(text.strip()) > 0:
            print(f"  段{i+1:3d}: {text[:70]}")

    # ---- 2. 参考文献段落 ----
    print("\n" + "=" * 60)
    print("【B】参考文献段落（最后300段中查找）")
    print("=" * 60)
    ref_start = -1
    for i, (text, _) in enumerate(all_paras):
        if re.match(r"参\s*考\s*文\s*献", text):
            ref_start = i
            print(f"  参考文献标题在段落 {i+1}")

    if ref_start > 0:
        ref_entries = []
        for i in range(ref_start + 1, min(ref_start + 200, len(all_paras))):
            text = all_paras[i][0]
            runs = all_paras[i][1]
            if re.match(r"(致\s*谢|附\s*录|作者简介)", text):
                break
            if text and len(text) > 3:
                # 取第一个run的字体信息
                font_info = ""
                if runs:
                    r0 = runs[0]
                    ea = r0.get("eastAsia", "")
                    asc = r0.get("ascii", "")
                    sz = r0.get("sz_hp", 0)
                    font_info = f" [中文:{ea or '?'} 英文:{asc or '?'} 字号:{sz/2 if sz else '?'}pt]"
                ref_entries.append((i+1, text[:80], font_info))

        print(f"  共 {len(ref_entries)} 条")
        # 前5条和后5条
        for pidx, txt, fi in ref_entries[:5]:
            print(f"  段{pidx}: {txt}{fi}")
        if len(ref_entries) > 10:
            print(f"  ... 中间省略 {len(ref_entries) - 10} 条 ...")
        for pidx, txt, fi in ref_entries[-5:]:
            print(f"  段{pidx}: {txt}{fi}")

        # 检查是否为著者-出版年制
        print("\n  --- 格式制式检测 ---")
        seq_num_count = 0
        author_year_count = 0
        for _, txt, _ in ref_entries:
            if re.match(r"\[\d+\]", txt):
                seq_num_count += 1
            if re.search(r"[,，]\s*(19|20)\d{2}[a-z]?\.", txt):
                author_year_count += 1
        print(f"  顺序编码制 [n] 格式: {seq_num_count} 条")
        print(f"  著者-出版年制: {author_year_count} 条")
        if seq_num_count > author_year_count:
            print("  \u274c \u8bba\u6587\u4f7f\u7528\u4e86\u987a\u5e8f\u7f16\u7801\u5236\uff0c\u519c\u5927\u89c4\u8303\u8981\u6c42\u4f7f\u7528\u300c\u8457\u8005\u2014\u51fa\u7248\u5e74\u5236\u300d\uff01")

    # ---- 3. 图表编号格式扫描 ----
    print("\n" + "=" * 60)
    print("【C】图表编号格式扫描")
    print("=" * 60)
    fig_nums = []
    tbl_nums = []
    for i, (text, _) in enumerate(all_paras):
        for m in re.finditer(r"图\s*(\d+)[-‐–—]\s*(\d+)", text):
            fig_nums.append((i+1, m.group(0)))
        for m in re.finditer(r"图(\d+)\.(\d+)", text):
            fig_nums.append((i+1, m.group(0)))
        for m in re.finditer(r"表\s*(\d+)[-‐–—]\s*(\d+)", text):
            tbl_nums.append((i+1, m.group(0)))
        for m in re.finditer(r"表(\d+)\.(\d+)", text):
            tbl_nums.append((i+1, m.group(0)))

    print(f"  图编号: 共 {len(fig_nums)} 处")
    for pidx, num in fig_nums[:10]:
        print(f"    段{pidx}: {num}")
    print(f"  表编号: 共 {len(tbl_nums)} 处")
    for pidx, num in tbl_nums[:10]:
        print(f"    段{pidx}: {num}")

    # 检查图表编号用的是 "-" 还是 "."
    dash_count = sum(1 for _, n in fig_nums + tbl_nums if "-" in n or "–" in n or "—" in n or "‐" in n)
    dot_count = sum(1 for _, n in fig_nums + tbl_nums if "." in n)
    print(f"  使用横杠分隔: {dash_count} 处, 使用点号分隔: {dot_count} 处")
    print(f"  规范示例: 图 1-1, 表 2-2 (横杠分隔)")

    # ---- 4. 正文中引用格式检查（顺序编码 vs 著者出版年）----
    print("\n" + "=" * 60)
    print("【D】正文引用格式检查")
    print("=" * 60)
    bracket_refs = []
    paren_refs = []
    for i, (text, _) in enumerate(all_paras):
        for m in re.finditer(r"\[\d+(?:[,，-]\d+)*\]", text):
            bracket_refs.append((i+1, m.group(0), text[max(0,m.start()-10):m.end()+10]))
        for m in re.finditer(r"（[^）]*?(?:19|20)\d{2}[^）]*?）", text):
            paren_refs.append((i+1, m.group(0)[:40]))

    print(f"  [n] 顺序编码引用: {len(bracket_refs)} 处")
    for pidx, ref, ctx in bracket_refs[:5]:
        print(f"    段{pidx}: ...{ctx}...")
    print(f"  （著者, 年份）引用: {len(paren_refs)} 处")
    for pidx, ref in paren_refs[:5]:
        print(f"    段{pidx}: {ref}")

    if len(bracket_refs) > len(paren_refs):
        print("  \u274c \u6b63\u6587\u5f15\u7528\u4e3b\u8981\u4f7f\u7528\u987a\u5e8f\u7f16\u7801\u5236 [n]\uff0c\u519c\u5927\u89c4\u8303\u8981\u6c42\u300c\u8457\u8005\u2014\u51fa\u7248\u5e74\u5236\u300d\uff08\u62ec\u53f7\u5939\u6ce8\u4f5c\u8005\u3001\u51fa\u7248\u5e74\uff09")

    # ---- 5. 检查一级标题是否带了页码数字 ----
    print("\n" + "=" * 60)
    print("【E】一级标题末尾异常数字检查")
    print("=" * 60)
    for i, (text, _) in enumerate(all_paras):
        if re.match(r"第[一二三四五六七八九十]+章\s", text):
            # 检查末尾是否有数字
            if re.search(r"\d+$", text):
                print(f"  ❌ 段{i+1}: \"{text}\" — 标题末尾带有数字（疑似目录页码残留）")

    # ---- 6. 页眉详细检查 ----
    print("\n" + "=" * 60)
    print("【F】页眉详细内容")
    print("=" * 60)
    rels_raw = zf.read("word/_rels/document.xml.rels")
    rels_root = ET.fromstring(rels_raw)
    ns_rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    for rel in rels_root.findall(f'{{{ns_rel}}}Relationship'):
        target = rel.get("Target", "")
        if "header" not in target.lower():
            continue
        fpath = f"word/{target}"
        try:
            hraw = zf.read(fpath)
        except KeyError:
            continue
        hroot = ET.fromstring(hraw)
        texts = []
        for p in hroot.findall(f'.//{{{NSMAP["w"]}}}p'):
            t = get_text(p)
            texts.append(t)
        combined = " | ".join([t for t in texts if t])
        if combined:
            problems = []
            if "双击页眉修改此处" in combined:
                problems.append("含模板提示文字")
            if "博士/硕士" in combined:
                problems.append("应改为'硕士'（非'博士/硕士'）")
            flag = " ❌ " + ", ".join(problems) if problems else ""
            print(f"  {target}: {combined}{flag}")

    zf.close()

if __name__ == "__main__":
    main()
