# Ubuntu 24.04 老师演示操作手册

## 先记住目标

明天不要部署整套系统，只部署这一条最稳的流程：

1. 用已经下载好的 PDF 作为输入
2. 在 Ubuntu 上运行 `PDF -> Markdown`
3. 展示后处理效果
4. 展示结果文件和已有对比结果

也就是说，明天的目标不是“把所有爬虫都跑起来”，而是“把 OCR workflow 跑起来并让老师能试”。

---

## 你们现在已经做到哪一步

目前仓库里已经有这些模块：

1. PDF 下载
   - `fish_intel_mvp/jobs/download_cnki_fulltext.py`
2. PDF 解析和 Markdown 生成
   - `mineru_parser.py`
3. 对比实验和质量评估
   - `run_mineru_comparison.py`
4. 下游数据生成
   - `run_sft_generation.py`

而且已经有现成结果：

- `results/summary.json`
- `results/comparison_table.csv`
- `results/markdown/`

现有汇总结果里，`MinerU` 在 30 篇论文上的可用率已经是 `100%`，这就是你明天可以讲的核心结果之一。

---

## 今晚你要做什么

### 第 1 步：在你自己电脑上生成一个“老师演示包”

在项目根目录打开 PowerShell，运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_teacher_demo.ps1 -PdfCount 3 -IncludeExistingMarkdown
```

运行完以后，会生成：

- `dist\ubuntu24-teacher-demo`
- `dist\ubuntu24-teacher-demo.zip`

这个 zip 就是你明天要带去老师电脑上的东西。

默认会打包：

- `mineru_parser.py`
- `run_mineru_comparison.py`
- `requirements-ocr.txt`
- `scripts/setup_ubuntu24_ocr.sh`
- `scripts/run_ocr_demo.sh`
- `docs/ubuntu24_teacher_demo.md`
- `test_pdfs/` 里前 3 篇 PDF
- `results/summary.json`
- `results/comparison_table.csv`
- 3 份已有 Markdown 示例

### 第 2 步：检查 zip 是否真的生成了

在 PowerShell 里运行：

```powershell
Get-ChildItem .\dist
```

你应该能看到 `ubuntu24-teacher-demo.zip`。

### 第 3 步：准备带到老师电脑上的方式

你可以二选一：

1. 最稳：把 `dist\ubuntu24-teacher-demo.zip` 拷到 U 盘
2. 也可以：上传到私有 GitHub 仓库，明天现场再下载

如果你对 GitHub 不熟，建议直接用 U 盘。

### 第 4 步：把明天要讲的话准备好

你就记这句话：

“老师，我们这次先在 Ubuntu 24.04 上部署并演示 `PDF -> OCR/版面解析 -> Markdown -> 质量评估` 这条 workflow。完整爬虫系统目前还有部分 Windows 依赖，所以先演示最核心、最稳定的 OCR 模块。”

---

## 明天到老师电脑上怎么做

下面默认你已经把 `ubuntu24-teacher-demo.zip` 带过去了。

### 第 1 步：把压缩包放到 Ubuntu 桌面

假设你放在桌面，打开终端后输入：

```bash
cd ~/Desktop
unzip ubuntu24-teacher-demo.zip -d ubuntu24-teacher-demo
cd ubuntu24-teacher-demo
```

如果老师电脑没装 `unzip`，就先执行：

```bash
sudo apt update
sudo apt install -y unzip
```

### 第 2 步：给脚本执行权限

```bash
chmod +x scripts/setup_ubuntu24_ocr.sh scripts/run_ocr_demo.sh
```

### 第 3 步：安装依赖

直接运行：

```bash
bash scripts/setup_ubuntu24_ocr.sh
```

这一步会自动做这些事：

1. 安装 Ubuntu 系统依赖
2. 创建 `.venv-ocr`
3. 安装 `magic-pdf`、`modelscope`、`pymupdf`、`pdfplumber` 等依赖

这一步时间可能会稍微长一点，正常。

### 第 4 步：跑演示

安装完成后，运行：

```bash
bash scripts/run_ocr_demo.sh
```

它会自动读取：

- `test_pdfs/`

并把结果输出到：

- `results_ubuntu_demo/summary.json`
- `results_ubuntu_demo/comparison_table.csv`
- `results_ubuntu_demo/markdown/`

### 第 5 步：检查结果文件

先看输出目录：

```bash
ls results_ubuntu_demo
ls results_ubuntu_demo/markdown
```

再打开汇总结果：

```bash
cat results_ubuntu_demo/summary.json
```

如果想看某篇 Markdown：

```bash
less results_ubuntu_demo/markdown/文件名.md
```

不会用 `less` 的话，直接：

```bash
cat results_ubuntu_demo/markdown/文件名.md
```

---

## 明天给老师怎么展示

建议按这个顺序讲：

### 1. 先说你们做了什么

“我们已经把知网论文全文下载后的 PDF，接成了一条 `PDF -> Markdown` 的 workflow。”

### 2. 再说这个 workflow 分成哪些模块

你可以说：

- PDF 输入
- OCR/版面解析
- 后处理
- 质量评估
- Markdown 输出

### 3. 再说后处理具体做了什么

你可以说：

- 公式区域修复
- 跨页表格合并
- 页眉页脚过滤
- 图注分离

### 4. 再展示实际结果

重点给老师看：

- `results_ubuntu_demo/summary.json`
- `results_ubuntu_demo/comparison_table.csv`
- `results_ubuntu_demo/markdown/` 里的某篇文件

### 5. 最后说为什么这是 workflow

你可以这样说：

“这个流程每个环节都可以单独替换，比如 OCR 模型以后可以换成别的，后处理规则也可以单独更新，所以它是模块化 workflow。”

---

## 如果现场报错怎么办

### 情况 1：`python3-venv` 装不上

先试：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

然后再重新执行：

```bash
bash scripts/setup_ubuntu24_ocr.sh
```

### 情况 2：`magic-pdf` 安装慢或失败

先不要慌，先给老师看你们已经准备好的旧结果：

- `results_examples/summary.json`
- `results_examples/comparison_table.csv`

再说明：

“现场依赖安装有点慢，但我们本地和已有实验结果已经跑通，Ubuntu 部署这一步主要是把 workflow 迁移演示出来。”

### 情况 3：脚本执行权限不够

再执行一次：

```bash
chmod +x scripts/setup_ubuntu24_ocr.sh scripts/run_ocr_demo.sh
```

### 情况 4：跑完没看到结果

直接检查：

```bash
ls test_pdfs
ls results_ubuntu_demo
```

先确认输入 PDF 在不在。

---

## 最后一句最重要

明天你不要给自己定成“必须把全项目部署完”。

你明天真正要完成的是：

**把 OCR 模块在 Ubuntu 24.04 上跑起来，并让老师看到输入、处理、输出和结果。**

只要这件事完成了，你这次汇报就是成功的。
