# -*- coding: utf-8 -*-
"""
终稿同步修改脚本v2：修改6处引导语/总结/英文摘要，使其与新增消融实验+后处理对比内容一致。
基于文本匹配而非硬编码索引，更可靠。
输入: D:\Onedrive\桌面\杨志诚毕业论文1_终稿.docx
输出: D:\Onedrive\桌面\杨志诚毕业论文1_终稿v2.docx
"""
import zipfile
import shutil
from lxml import etree

SRC = r"D:\Onedrive\桌面\杨志诚毕业论文1_终稿.docx"
DST = r"D:\Onedrive\桌面\杨志诚毕业论文1_终稿v2.docx"
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{WNS}}}"
NSMAP = {"w": WNS}
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def get_text(elem):
    return "".join(t.text or "" for t in elem.iter(f"{W}t"))


def simple_replace_in_para(para, old_str, new_str):
    """拼接所有t文本，替换后写回第一个t，其余清空"""
    runs = list(para.iter(f"{W}r"))
    t_elems = []
    for run in runs:
        for t in run.findall(f"{W}t"):
            t_elems.append(t)
    if not t_elems:
        return False

    full = "".join(t.text or "" for t in t_elems)
    if old_str not in full:
        return False

    new_full = full.replace(old_str, new_str, 1)
    for i, t in enumerate(t_elems):
        if i == 0:
            t.text = new_full
            t.set(XML_SPACE, "preserve")
        else:
            t.text = ""
    return True


# 定义所有替换规则: (描述, 匹配条件, old_str, new_str)
REPLACEMENTS = [
    # 修改1: 5.2.4引导语 "四个方面" → "五个方面" + 加"凭证自愈消融实验"
    (
        "5.2.4\u5f15\u5bfc\u8bed: \u56db\u4e2a\u65b9\u9762\u2192\u4e94\u4e2a\u65b9\u9762",
        lambda t: "\u5bb9\u9519\u9694\u79bb\u3001\u51ed\u8bc1\u81ea\u6108\u3001\u914d\u7f6e\u5b89\u5168\u548c\u8fd0\u884c\u6548\u80fd\u56db\u4e2a\u65b9\u9762" in t,
        "\u5bb9\u9519\u9694\u79bb\u3001\u51ed\u8bc1\u81ea\u6108\u3001\u914d\u7f6e\u5b89\u5168\u548c\u8fd0\u884c\u6548\u80fd\u56db\u4e2a\u65b9\u9762",
        "\u5bb9\u9519\u9694\u79bb\u3001\u51ed\u8bc1\u81ea\u6108\u3001\u51ed\u8bc1\u81ea\u6108\u6d88\u878d\u5b9e\u9a8c\u3001\u914d\u7f6e\u5b89\u5168\u548c\u8fd0\u884c\u6548\u80fd\u4e94\u4e2a\u65b9\u9762",
    ),
    # 修改2: 5.2节引导语 加消融实验说明
    (
        "5.2\u5f15\u5bfc\u8bed: \u52a0\u6d88\u878d\u5b9e\u9a8c",
        lambda t: "\u5bb9\u9519\u80fd\u529b\u4e0e\u8fd0\u884c\u6548\u80fd\u3002" in t and "5.2.4" in t,
        "\u5bb9\u9519\u80fd\u529b\u4e0e\u8fd0\u884c\u6548\u80fd\u3002",
        "\u5bb9\u9519\u80fd\u529b\u4e0e\u8fd0\u884c\u6548\u80fd\uff0c\u5e76\u901a\u8fc7\u6d88\u878d\u5b9e\u9a8c\u91cf\u5316\u51ed\u8bc1\u81ea\u6108\u5404\u5c42\u7ea7\u7684\u72ec\u7acb\u8d21\u732e\u3002",
    ),
    # 修改3: 5.3节引导语 加后处理增益
    (
        "5.3\u5f15\u5bfc\u8bed: \u52a0\u540e\u5904\u7406\u589e\u76ca",
        lambda t: "\u4e3a\u7ba1\u7ebf\u9009\u578b\u51b3\u7b56\u63d0\u4f9b\u91cf\u5316\u4f9d\u636e\u3002" in t and "5.3.1" in t,
        "\u4e3a\u7ba1\u7ebf\u9009\u578b\u51b3\u7b56\u63d0\u4f9b\u91cf\u5316\u4f9d\u636e\u3002",
        "\u4e3a\u7ba1\u7ebf\u9009\u578b\u51b3\u7b56\u63d0\u4f9b\u91cf\u5316\u4f9d\u636e\uff0c\u5e76\u91cf\u5316\u8bc4\u4f30\u540e\u5904\u7406\u89c4\u5219\u7684\u72ec\u7acb\u589e\u76ca\u3002",
    ),
    # 修改4: 6.1总结第二点 加消融验证
    (
        "6.1\u603b\u7ed3\u7b2c\u4e8c\u70b9: \u52a0\u6d88\u878d\u9a8c\u8bc1",
        lambda t: "\u4e09\u7ea7\u51ed\u8bc1\u81ea\u6108\u673a\u5236\uff0c\u63d0\u5347\u4e86\u957f\u65f6\u95f4\u8fd0\u884c\u573a\u666f\u4e0b\u7684\u91c7\u96c6\u7a33\u5b9a\u6027\u3002" in t,
        "\u4e09\u7ea7\u51ed\u8bc1\u81ea\u6108\u673a\u5236\uff0c\u63d0\u5347\u4e86\u957f\u65f6\u95f4\u8fd0\u884c\u573a\u666f\u4e0b\u7684\u91c7\u96c6\u7a33\u5b9a\u6027\u3002",
        "\u4e09\u7ea7\u51ed\u8bc1\u81ea\u6108\u673a\u5236\uff0c\u5e76\u901a\u8fc7\u6d88\u878d\u5b9e\u9a8c\u5b9a\u91cf\u9a8c\u8bc1\u4e86\u4e09\u7ea7\u9012\u8fdb\u7b56\u7565\u4e2d\u5404\u5c42\u7ea7\u7684\u72ec\u7acb\u6709\u6548\u6027\uff0c\u63d0\u5347\u4e86\u957f\u65f6\u95f4\u8fd0\u884c\u573a\u666f\u4e0b\u7684\u91c7\u96c6\u7a33\u5b9a\u6027\u3002",
    ),
    # 修改5: 6.1总结第四点 加后处理增益
    (
        "6.1\u603b\u7ed3\u7b2c\u56db\u70b9: \u52a0\u540e\u5904\u7406\u589e\u76ca",
        lambda t: "\u6709\u6548\u514b\u670d\u4e86\u53cc\u680f\u6392\u7248\u4e0e\u590d\u6742\u8868\u683c\u7684\u63d0\u53d6\u96be\u9898\u3002" in t and "MinerU" in t,
        "\u6709\u6548\u514b\u670d\u4e86\u53cc\u680f\u6392\u7248\u4e0e\u590d\u6742\u8868\u683c\u7684\u63d0\u53d6\u96be\u9898\u3002",
        "\u6709\u6548\u514b\u670d\u4e86\u53cc\u680f\u6392\u7248\u4e0e\u590d\u6742\u8868\u683c\u7684\u63d0\u53d6\u96be\u9898\uff1b\u5bf9\u6bd4\u5b9e\u9a8c\u8fdb\u4e00\u6b65\u8868\u660e\uff0c\u540e\u5904\u7406\u89c4\u5219\u4e3a\u5168\u6587\u53ef\u7528\u7387\u5e26\u6765\u4e8613.3\u4e2a\u767e\u5206\u70b9\u7684\u589e\u76ca\u3002",
    ),
    # 修改6a: 英文摘要 加 ablation
    (
        "\u82f1\u6587\u6458\u8981: \u52a0ablation",
        lambda t: "three-level Token self-healing fault-tolerance mechanism" in t and "DrissionPage" in t,
        "three-level Token self-healing fault-tolerance mechanism, while introducing",
        "three-level Token self-healing fault-tolerance mechanism\u2014whose effectiveness is validated through ablation experiments\u2014while introducing",
    ),
    # 修改6b: 英文摘要 加 post-processing enhancement
    (
        "\u82f1\u6587\u6458\u8981: \u52a0post-processing",
        lambda t: "The MinerU visual parsing pipeline is integrated" in t,
        "The MinerU visual parsing pipeline is integrated,",
        "The MinerU visual parsing pipeline is integrated with a post-processing enhancement strategy,",
    ),
    # 修改6c: 英文摘要 加增益数据
    (
        "\u82f1\u6587\u6458\u8981: \u52a013.3pp\u589e\u76ca",
        lambda t: "improves by 73.3 percentage points over PyMuPDF" in t,
        "improves by 73.3 percentage points over PyMuPDF",
        "improves by 73.3 percentage points over PyMuPDF, with post-processing rules contributing a 13.3-percentage-point gain",
    ),
]


def main():
    zin = zipfile.ZipFile(SRC, "r")
    raw_xml = zin.read("word/document.xml")
    root = etree.fromstring(raw_xml)
    body = root.find(f"{W}body")
    children = list(body)

    results = []

    for desc, match_fn, old_str, new_str in REPLACEMENTS:
        found = False
        for child in children:
            text = get_text(child)
            if match_fn(text):
                ok = simple_replace_in_para(child, old_str, new_str)
                results.append((desc, ok))
                found = True
                break
        if not found:
            results.append((desc, False))

    # 写出
    new_xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

    shutil.copy2(SRC, DST)
    with zipfile.ZipFile(DST, "a") as zout:
        zout.writestr("word/document.xml", new_xml)
    zin.close()

    # 打印结果
    print("=" * 60)
    print("\u4fee\u6539\u7ed3\u679c")
    print("=" * 60)
    all_ok = True
    for desc, ok in results:
        status = "\u2705" if ok else "\u274c"
        print(f"  {status} {desc}")
        if not ok:
            all_ok = False

    print(f"\n\u5171 {len(results)} \u9879\u4fee\u6539\uff0c{'ALL PASS' if all_ok else 'HAS FAILURES'}")
    print(f"\u8f93\u51fa: {DST}")


if __name__ == "__main__":
    main()
