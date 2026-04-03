# -*- coding: utf-8 -*-
import zipfile
from lxml import etree
import sys
import os
import io

# Write output directly to file with UTF-8 encoding
outfile = open('_thesis_output.txt', 'w', encoding='utf-8')

# Try extracting text via raw XML to bypass corrupted parts
docx_path = r'D:\Onedrive\桌面\杨志诚毕业论文1.docx'

with zipfile.ZipFile(docx_path, 'r') as z:
    names = z.namelist()
    # Print all entries for debugging
    for n in names:
        if 'document' in n.lower():
            print(f"  entry: {n}")
    
    # word/document.xml is the main document
    doc_xml = 'word/document.xml'
    xml_content = z.read(doc_xml)

# Parse XML
nsmap = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
root = etree.fromstring(xml_content)

paragraphs = root.findall('.//w:p', nsmap)
for i, p in enumerate(paragraphs):
    # Get style
    pPr = p.find('w:pPr', nsmap)
    style = ''
    if pPr is not None:
        pStyle = pPr.find('w:pStyle', nsmap)
        if pStyle is not None:
            style = pStyle.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '')
    
    # Get all text in paragraph
    texts = []
    for r in p.findall('.//w:r', nsmap):
        for t in r.findall('w:t', nsmap):
            if t.text:
                texts.append(t.text)
    
    text = ''.join(texts).strip().replace('\xa0', ' ')
    if text:
        outfile.write(f'[{i}][{style}] {text}\n')

outfile.close()
print("Done")
