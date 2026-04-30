# 硕士答辩 Live Demo 脚本

## 演示目标

3 到 5 分钟内，向评委展示这 4 个能力：

1. 采集调度可运行，而且失败不会拖垮全流程
2. `PDF -> Markdown` 解析链路可运行，而且有可解释的后处理规则
3. SFT 语料构建不是手工拼凑，而是模板化自动生成
4. 结果已经真正落到数据库和本地语料文件中

---

## 建议演示顺序

### 第 1 段：先刷测试，建立信任

在项目根目录执行：

```powershell
.\.venv\Scripts\python -m pytest tests\test_config_storage.py tests\test_sft_generator.py tests\test_mineru_parser.py -k "not TestAvailabilityWithRealPdfs" -q
```

预期：

- 55 passed
- 3 deselected

你可以说：

“我先不直接展示界面，而是先用自动化测试证明核心模块是可复现、可验证的。这里覆盖了调度存储、MinerU 后处理和 SFT 语料生成三条主链路。”

---

### 第 2 段：展示调度与采集

如果现场网络稳定，执行：

```powershell
$env:JD_BROWSER_BACKEND="playwright"
$env:JD_SALMON_PAGES="1"
$env:JD_SALMON_KEYWORDS="三文鱼"
cd fish_intel_mvp
..\.venv\Scripts\python run_one.py jd_salmon
```

如果你不想切目录，也可以：

```powershell
$env:JD_BROWSER_BACKEND="playwright"
$env:JD_SALMON_PAGES="1"
$env:JD_SALMON_KEYWORDS="三文鱼"
.\.venv\Scripts\python fish_intel_mvp\run_one.py jd_salmon
```

你可以说：

“这里我单跑的是 `jd_salmon` 任务，不是普通爬虫脚本。它会走统一调度入口、自动写入 `crawl_run`、`raw_event` 和 `product_snapshot`，同时做三文鱼领域增强和价格变化回填。”

---

### 第 3 段：展示 OCR / MinerU 解析

执行：

```powershell
.\.venv\Scripts\python run_mineru_comparison.py --pdf-dir .\test_pdfs --output .\results\demo_live
```

如果你担心现场时间太长，改成先准备 1 到 3 篇 PDF 的小目录再跑。

你可以说：

“这一段对应论文里的 PDF 全文解析链路。核心不是简单 OCR，而是 `MinerU + 后处理规则`，最后输出结构化 Markdown，并做可用率评估。”

---

### 第 4 段：展示 SFT 语料生成

执行一个小样本版本：

```powershell
.\.venv\Scripts\python run_sft_generation.py --output-dir results\sft_dataset_demo_live --total-samples 30
```

如果你要展示正式结果，不现场重跑，直接说：

“正式实验版本已经生成完成，当前仓库中真实结果为 852 条样本。”

---

### 第 5 段：展示成果文件和数据库

执行数据库总览：

```powershell
.\.venv\Scripts\python validate_end_to_end.py
```

执行最近运行记录展示：

```powershell
.\.venv\Scripts\python -c "from query.dashboard_queries import get_recent_crawl_runs; import json; print(json.dumps(get_recent_crawl_runs(limit=5), ensure_ascii=False, indent=2))"
```

执行商品快照展示：

```powershell
.\.venv\Scripts\python -c "from query.dashboard_queries import get_product_snapshots; from pprint import pprint; pprint(get_product_snapshots(platform='jd', keyword='三文鱼', limit=5))"
```

---

## IDE 打开顺序

### 1. 调度入口

打开：

- `fish_intel_mvp/run_one.py`

重点看：

- `JOB_MAP`
- `insert_crawl_run`
- `finish_crawl_run`

你可以说：

“我把所有采集任务统一挂到一个调度入口里，所以答辩现场不是直接跑某个零散脚本，而是跑统一任务编排入口。每次任务都会自动登记开始、结束、状态和条数，便于追踪和复现实验过程。”

### 2. 配置式调度容错

打开：

- `runner.py`

重点看：

- `run_from_config`
- `_normalize_items`

你可以说：

“这个模块体现的是工程化思路。我的采集不是写死在单个脚本里，而是支持按配置动态加载；其中一个源失败，不会把整个流程拖垮。”

### 3. JD Playwright 采集

打开：

- `fish_intel_mvp/jobs/crawl_jd.py`

重点看：

- `_playwright_goto`
- `_run_with_playwright`
- `run`

你可以说：

“这里我做了浏览器后端抽象，支持 Playwright 路径，现场我用它来演示真实页面采集。`run` 会根据环境变量切换采集后端，而不是把爬虫逻辑写死。”

### 4. 三文鱼领域增强

打开：

- `fish_intel_mvp/jobs/crawl_salmon.py`

重点看：

- `_backfill_price_changes`
- `crawl_jd_salmon`

你可以说：

“我并不是只抓标题和价格，而是在采集后做了领域增强，比如商品类型识别、价格变化回填。这样数据库里的记录不是原始噪声，而是可分析的领域数据。”

### 5. 数据库写入层

打开：

- `fish_intel_mvp/common/db.py`

重点看：

- `insert_crawl_run`
- `finish_crawl_run`
- `insert_raw_event`
- `upsert_product_snapshot`

你可以说：

“这层把原始证据、过程状态和清洗结果分层存储。`raw_event` 保证可追溯，`product_snapshot` 保证可分析，`crawl_run` 保证过程可审计。”

### 6. MinerU 解析与规则过滤

打开：

- `mineru_parser.py`

重点看：

- `_call_mineru`
- `fix_formula_regions`
- `merge_cross_page_tables`
- `filter_header_footer`
- `separate_figure_captions`
- `parse_pdf_with_mineru`
- `evaluate_availability`

你可以说：

“我不是直接把 OCR 原文拿来下游使用，而是补了四类规则修复：公式、跨页表格、页眉页脚和图注。这样输出的 Markdown 才能真正进入后续语料生成流程。”

### 7. SFT 自动构造

打开：

- `sft_generator.py`

重点看：

- `load_parsed_docs`
- `inject_cot`
- `build_sample`
- `quality_filter_sample`
- `generate_sft_dataset`
- `export_jsonl`
- `export_sharegpt`

你可以说：

“这部分是论文里最核心的语料构建链路。输入不是人工整理的问答，而是 OCR 后的 Markdown 和 CNKI 摘要。系统会自动按模板生成定义、推理、对比、摘要、应用五类样本，并对 CoT、去重和领域相关性做过滤。”

### 8. 一键生成脚本

打开：

- `run_sft_generation.py`

重点看：

- `main`
- `resolve_input_paths`

你可以说：

“为了保证复现性，我把整条生成链路封成了一个一键脚本，不是手工点 GUI 或人工拷文件。”

---

## 成果展示路径

### 1. 数据库展示

总览：

```powershell
.\.venv\Scripts\python validate_end_to_end.py
```

当前本机真实结果：

- `product_snapshot`: 1664
- `intel_item`: 20
- `offline_price_snapshot`: 150

最近运行记录：

```powershell
.\.venv\Scripts\python -c "from query.dashboard_queries import get_recent_crawl_runs; import json; print(json.dumps(get_recent_crawl_runs(limit=5), ensure_ascii=False, indent=2))"
```

过滤后的商品快照：

```powershell
.\.venv\Scripts\python -c "from query.dashboard_queries import get_product_snapshots; from pprint import pprint; pprint(get_product_snapshots(platform='jd', keyword='三文鱼', limit=5))"
```

### 2. OCR 成果展示

打开：

- `results/summary.json`
- `results/comparison_table.csv`
- `results/markdown/`

你可以说：

“这一部分证明 PDF 不是只做了下载，而是已经完成了结构化解析和质量评估。”

### 3. SFT 语料展示

打开：

- `results/sft_dataset_real/source_summary.json`
- `results/sft_dataset_real/generation_report.json`
- `results/sft_dataset_real/sft_dataset.jsonl`

当前仓库真实结果：

- 总样本数：852
- 含 CoT 标记样本数：567

### 4. 微调效果展示

打开：

- `finetune/saves/evaluation_results.json`

你可以说：

“这说明语料构造不是停留在生成阶段，而是已经进入微调和评测闭环。当前真实结果中，微调后 `ROUGE-1 F1` 从 0.2893 提升到 0.8005。”

---

## Plan B

### 1. 网络断开时

不要强行跑线上采集，直接展示：

- `validate_end_to_end.py`
- `results/summary.json`
- `results/comparison_table.csv`
- `results/sft_dataset_real/*.json`

### 2. 京东出现验证码时

不要卡在登录页，立即切换成：

1. 展示 `crawl_jd.py` 的 Playwright 代码路径
2. 展示 `crawl_run` 历史成功记录
3. 展示 `product_snapshot` 现有结果

### 3. MinerU 现场跑太慢时

只讲链路，然后直接打开：

- `results/markdown/`
- `results/summary.json`

### 4. 语料生成来不及跑完时

只跑小样本：

```powershell
.\.venv\Scripts\python run_sft_generation.py --output-dir results\sft_dataset_demo_live --total-samples 30
```

如果时间还是不够，直接打开正式结果目录：

- `results/sft_dataset_real/`

---

## 最后一句

答辩现场不要贪多。你真正要让老师记住的是：

“这不是一个单点爬虫项目，而是一条从采集、解析、清洗、语料构建到微调评测的完整闭环系统。”
