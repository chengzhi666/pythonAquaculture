# Ubuntu OCR 部署与交付说明

## 目标

这个包只部署论文 PDF 解析这一条链路：

`PDF -> MinerU/OCR 版面解析 -> 规则后处理 -> Markdown -> 质量评估`

它不包含完整爬虫系统，目的是让老师在 Ubuntu 机器上能快速复现实验流程。

## 文件说明

- `mineru_parser.py`：MinerU 调用、后处理规则、可用率评估。
- `run_mineru_comparison.py`：批量运行 MinerU、PyMuPDF、pdfplumber 对比。
- `requirements-ocr.txt`：Ubuntu Python 依赖。
- `scripts/setup_ubuntu24_ocr.sh`：安装系统依赖并创建 `.venv-ocr`。
- `scripts/download_mineru_models.py`：从 ModelScope 下载 MinerU 模型并写入 `~/magic-pdf.json`。
- `scripts/run_ocr_demo.sh`：运行 demo，默认只跑 1 篇 PDF，便于现场快速验证。
- `test_pdfs/`：演示 PDF。
- `results_examples/`：已有实验结果，可在现场安装较慢时先展示。

## 老师电脑上怎么运行

假设压缩包在桌面：

```bash
cd ~/Desktop
unzip ubuntu-ocr-teacher-demo.zip -d ubuntu-ocr-teacher-demo
cd ubuntu-ocr-teacher-demo
chmod +x scripts/setup_ubuntu24_ocr.sh scripts/run_ocr_demo.sh
```

安装依赖和 MinerU 模型：

```bash
bash scripts/setup_ubuntu24_ocr.sh
```

第一次安装会下载 MinerU 模型，时间会比较久。只想先跑 PyMuPDF/pdfplumber 基线时可以：

```bash
SKIP_MINERU_MODEL_DOWNLOAD=1 bash scripts/setup_ubuntu24_ocr.sh
```

建议预留：

- 磁盘空间：至少 12 GB。
- 时间：网络顺利时约 30 到 60 分钟，主要耗时在 PyTorch/MinerU 依赖和模型下载。
- 网络：ModelScope 可访问；脚本默认使用清华 PyPI 源。

快速跑 1 篇 PDF：

```bash
bash scripts/run_ocr_demo.sh
```

跑包里的全部 PDF：

```bash
MAX_PDFS=0 bash scripts/run_ocr_demo.sh
```

输出文件在：

- `results_ubuntu_demo/summary.json`
- `results_ubuntu_demo/comparison_table.csv`
- `results_ubuntu_demo/markdown/`

## 讲法

可以这样介绍：

> 这个包把论文全文 PDF 解析流程迁移到了 Ubuntu。流程输入是 PDF，输出是 Markdown，同时生成逐篇质量评估表。当前先用 MinerU 作为主要版面解析底座，并加入公式、跨页表格、页眉页脚和图注四类后处理规则。后续可以继续替换 OCR 模型，或加入人工 gold set 做更严格评估。

## 如果现场安装慢

先展示：

```bash
cat results_examples/summary.json
head -n 5 results_examples/comparison_table.csv
ls results_examples/markdown
```

然后说明已有结果已经跑通，现场安装主要是为了复现 Ubuntu 迁移环境。

## WSL 网络问题

如果是在 Windows 的 WSL Ubuntu 里部署，`apt update` 或 `pip install` 一直超时，可以在 Windows 用户目录创建 `%USERPROFILE%\.wslconfig`：

```ini
[wsl2]
networkingMode=mirrored
dnsTunneling=true
autoProxy=true
firewall=false
```

然后在 PowerShell 执行：

```powershell
wsl --shutdown
wsl -d Ubuntu-24.04
```
