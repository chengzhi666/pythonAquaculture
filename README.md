# pythonAquaculture

水产情报采集 MVP。目标是把多来源采集统一成一套流程：`跑批 -> 入 MySQL -> 可回溯 -> 可去重`。

## 项目简介

项目当前以 **MySQL 作为主存储**，并保留 SQLite 作为可选本地模式。包含两套运行方式：

| | Flask WebUI | 批量处理系统 |
|---|---|---|
| **入口** | `app.py` | `fish_intel_mvp/run_one.py` |
| **数据库** | MySQL（可切 SQLite） | MySQL |
| **用途** | 交互式展示、情报检索 | 生产级批量采集、日志审计 |
| **爬虫** | `crawlers/` | `fish_intel_mvp/jobs/` |

当前状态：

- `jd`：已可跑，入表 `product_snapshot`，含 `raw_event` 证据。
- `moa`：已可跑，入表 `intel_item`，含 `raw_event` 证据。
- `cnki`：已接入 `paper_meta`，可跑但依赖本机 Selenium/Edge 驱动环境。
- `taobao`：已实现（基于淘宝 H5 接口抓取，需有效 `TAOBAO_COOKIE`）。

---

## 快速上手

### 环境要求

- Windows 10/11
- Python 3.9 ~ 3.11
- Git
- MySQL 8.x

### 一键 Bootstrap

```powershell
git clone https://github.com/chengzhi666/pythonAquaculture.git
cd pythonAquaculture
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 -SkipChecks
```

`bootstrap.ps1` 会自动完成：创建 `.venv`、安装 `.[dev]` 及 `fish_intel_mvp/requirements.txt`、安装 Playwright Chromium、创建 `.env.local` 和 `fish_intel_mvp/.env`。

可选 flags：`-SkipPreCommit`、`-SkipPlaywrightInstall`、`-SkipFishIntelDeps`。

### 本地配置

编辑 `fish_intel_mvp/.env`，至少填写：

```dotenv
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASS=你的MySQL密码
DB_NAME=fish_intel
```

初始化数据库：

```powershell
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS fish_intel DEFAULT CHARSET utf8mb4;"
mysql -u root -p fish_intel < fish_intel_mvp\schema.sql
```

### 验证安装

推荐用 Playwright 后端避免 DrissionPage 端口冲突：

```powershell
$env:JD_BROWSER_BACKEND='playwright'
.\.venv\Scripts\python fish_intel_mvp\run_one.py jd
```

---

## 使用指南

### Flask WebUI

```powershell
.\.venv\Scripts\python app.py
```

访问 `http://localhost:5000`，包含 5 个 Tab：📥 数据采集 / 📄 论文数据 / 🛒 商品数据 / 🏪 线下价格 / 📋 渔业政策。

可选切换到本地 SQLite：`$env:STORAGE_BACKEND='sqlite'; python app.py`

### 批量处理系统

```powershell
python fish_intel_mvp\run_one.py jd
python fish_intel_mvp\run_one.py taobao
python fish_intel_mvp\run_one.py moa
python fish_intel_mvp\run_one.py cnki
# 刷新淘宝 Cookie
python fish_intel_mvp\jobs\refresh_taobao_cookie.py
```

### 微调实验

详见 [finetune/RUN_GUIDE.md](finetune/RUN_GUIDE.md)。

### 常用配置项

| 配置 | 说明 |
|------|------|
| `DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME` | MySQL 连接 |
| `CNKI_THEME` / `CNKI_PAPERS` / `CNKI_MAX_PAGES` | 知网采集参数 |
| `TAOBAO_COOKIE` / `TAOBAO_KEYWORDS` / `TAOBAO_PAGES` | 淘宝采集参数 |
| `TAOBAO_AUTO_REFRESH_COOKIE` | Cookie 失效时自动刷新（默认 1） |
| `JD_KEYWORDS` / `JD_PAGES` | 京东采集参数 |
| `EDGE_DRIVER_PATH` / `CHROME_DRIVER_PATH` | 浏览器驱动路径 |

### 重要页面

- 首页：`http://127.0.0.1:5000/`
- 三文鱼分析页：`http://127.0.0.1:5000/analysis/salmon?days=60`
- 价格趋势：`http://127.0.0.1:5000/analysis/salmon?days=60#trend`
- 品种/产地分布：`http://127.0.0.1:5000/analysis/salmon?days=30#distribution`
- 线上线下对比：`http://127.0.0.1:5000/analysis/salmon?days=30#compare`

---

## 目录结构

```text
pythonAquaculture/
  app.py                        # Flask WebUI 入口
  runner.py                     # 配置驱动的采集框架
  config_mgr.py                 # 统一配置管理
  config/
    sites.json                  # 采集源配置文件
  templates/
    index.html                  # 前端单页面（5 个 Tab）
  crawlers/                     # 爬虫模块
    cnki_crawler.py
    moa_fishery_crawler.py
    scholar_crawler.py
    utils.py                    # 公共工具函数
  storage/
    db.py                       # 统一存储层（MySQL / SQLite）
  fish_intel_mvp/               # 批量处理系统
    common/
      db.py
      logger.py
      parse_rules.py
    jobs/
      crawl_jd.py
      crawl_moa_fishery.py
      crawl_cnki.py
      crawl_taobao.py
    run_one.py
    schema.sql
    requirements.txt
  finetune/                     # 毕设微调实验
  tests/                        # 单元测试
  .vscode/                      # VS Code 配置
```

---

## 开发指南

### 分支与提交规范

始终在 feature 分支开发，不要直接提交 `main`：

```powershell
git checkout -b feat/short-description
# ... 开发 ...
git add -A
git commit -m "feat: concise change summary"
git push origin feat/short-description
```

提交前 PR 前确保本地检查通过。

### 代码质量工具

```powershell
# 代码检查
.\.venv\Scripts\python -m ruff check .

# 格式化
.\.venv\Scripts\python -m black --check .

# 类型检查
mypy crawlers/ storage/ query/ --ignore-missing-imports
```

### 运行测试

```powershell
# 全部测试 + 覆盖率
pytest

# 特定文件
pytest tests/test_storage.py -v

# 按标记
pytest -m unit
pytest -m integration

# 一键跑测试（含覆盖率报告）
python run_full_test.py
```

### 公共工具函数

`crawlers/utils.py` 提供常用工具：

```python
from crawlers.utils import clean_text, extract_keywords, extract_date, normalize_url
```

### 配置管理

```python
from config_mgr import get_config
config = get_config()
print(f"数据库：{config.DB_HOST}:{config.DB_PORT}")
```

### IDE 配置

项目已配置 VS Code 开发环境（`.vscode/` 目录），包含：

- 9 个调试配置（Flask、各爬虫、测试）
- 10 个运行任务
- 推荐扩展列表

运行 `.\setup_vscode.ps1 -All` 可一键安装扩展和配置环境。

快捷键：**F11** 启动 Flask / **F5** 调试 / **Ctrl+Shift+B** 格式化。

详细配置说明见 `.vscode/README.md`。

### CI 门控

当前 CI 包含：Ruff lint、Black 格式检查、单元测试、安全扫描（Bandit）。

---

## 架构与设计决策

- **批量事务优化**：`save_items()` 使用事务批量提交，性能提升 3-5 倍，保证原子性。
- **统一日志**：所有模块使用 `logging` 标准库，操作可追溯、错误可定位。
- **公共工具层**：文本清洗、关键词提取、日期提取、URL 标准化统一在 `crawlers/utils.py`，消除重复代码。
- **配置集中化**：`config_mgr.py` 作为单一事实来源，统一管理环境变量和配置验证。
- **Flask REST API**：前后端分离，前端单页面通过 `/api/...` 与后端交互。
- **项目规范化**：`pyproject.toml` + `pytest` + `pre-commit`，支持 `pip install -e ".[dev]"`。

---

## 验收 SQL

```sql
USE fish_intel;

-- 运行记录
SELECT id, source_name, status, items FROM crawl_run ORDER BY id DESC LIMIT 10;

-- 京东
SELECT platform, keyword, title, price, detail_url, raw_id FROM product_snapshot ORDER BY id DESC LIMIT 20;

-- 渔业渔政
SELECT pub_time, org, title, source_url, raw_id FROM intel_item ORDER BY id DESC LIMIT 20;

-- 知网
SELECT pub_date, title, source, url, raw_id FROM paper_meta ORDER BY id DESC LIMIT 20;

-- 原始证据
SELECT id, source_name, title, pub_time, url FROM raw_event ORDER BY id DESC LIMIT 20;
```

---

## 排错指南

| 问题 | 解决方案 |
|------|---------|
| `ModuleNotFoundError: No module named 'common'` | 从项目根目录运行：`python fish_intel_mvp\run_one.py <job>` |
| `Access denied for user 'root'@'localhost'` | 检查 `fish_intel_mvp/.env` 的 `DB_USER/DB_PASS` |
| JD 抓到 `items=0` | 先用 `JD_PAGES=1`，确认浏览器页面出现商品卡片 |
| MOA MySQL 断连 | 已有截断和 PDF 特殊处理，偶发时重跑即可 |
| CNKI 启动失败或超时 | Edge 与 EdgeDriver 版本不匹配，在 `.env` 设 `EDGE_DRIVER_PATH` |
| Taobao `FAIL_SYS_TOKEN_EXOIRED` | 默认自动刷新；禁用：`TAOBAO_AUTO_REFRESH_COOKIE=0`，手动运行 `refresh_taobao_cookie.py` |
| Taobao 扫码页跳回密码登录 | 设 `TAOBAO_COOKIE_REFRESH_USE_SYSTEM_PROFILE=1`，手动运行刷新脚本 |
| `python` not found | 重装 Python 并勾选 "Add Python to PATH" |
| 虚拟环境激活被阻止 | 改用直接路径：`.\.venv\Scripts\python ...` |
| Import/path 错误 | 确保从仓库根目录运行命令 |
