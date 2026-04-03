import zipfile
from lxml import etree
import traceback

try:
    docx_path = r'D:\Onedrive\桌面\杨志诚毕业论文1_终稿v2.docx'
    with zipfile.ZipFile(docx_path, 'r') as z:
        # 处理重复条目：取最后一个
        names = z.namelist()
        target = [n for n in names if n == 'word/document.xml'][-1]
        xml_content = z.read(target)

    nsmap = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    root = etree.fromstring(xml_content)
    paragraphs = root.findall('.//w:p', nsmap)

    with open('thesis_full_v3.txt', 'w', encoding='utf-8') as f:
        for i, p in enumerate(paragraphs):
            texts = []
            for r in p.findall('.//w:r', nsmap):
                for t in r.findall('w:t', nsmap):
                    if t.text:
                        texts.append(t.text)
            text = ''.join(texts).strip()
            if text:
                f.write(f'{i:04d}\t{text}\n')

    print(f'Done, total paragraphs with text: extracted to thesis_full_v3.txt')
except Exception as e:
    traceback.print_exc()
