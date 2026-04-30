# Ubuntu OCR WSL 验证记录

验证环境：

- Windows WSL2
- Ubuntu 24.04.4 LTS
- Python 3.12.3
- magic-pdf 1.3.12

已完成：

1. 新建并启动 `Ubuntu-24.04` WSL。
2. 修复 WSL 网络为 mirrored networking。
3. 安装 OCR 系统依赖、Python 依赖和 MinerU 模型。
4. 运行 `PDF -> MinerU -> Markdown -> CSV/JSON 评估` demo。

验证命令：

```bash
cd /root/ubuntu-ocr-teacher-demo
MAX_PDFS=1 bash scripts/run_ocr_demo.sh
```

验证结果：

- 输入：`test_pdfs/sample_01.pdf`
- 输出：`results_ubuntu_demo/summary.json`
- 输出：`results_ubuntu_demo/comparison_table.csv`
- 输出：`results_ubuntu_demo/markdown/sample_01.md`

关键指标：

| 方法 | 可用篇数 | 可用率 | 噪声率 | 耗时 |
|---|---:|---:|---:|---:|
| mineru_raw | 1/1 | 100.0% | 1.9% | 98.708s |
| mineru_enhanced | 1/1 | 100.0% | 0.0% | 98.708s |
| pymupdf | 0/1 | 0.0% | 100.0% | 0.051s |
| pdfplumber | 1/1 | 100.0% | 11.1% | 1.488s |

说明：

- Ubuntu 链路已经跑通。
- Demo 默认只跑 1 篇 PDF，便于现场快速验证。
- 若要跑包内全部 PDF，执行 `MAX_PDFS=0 bash scripts/run_ocr_demo.sh`。
