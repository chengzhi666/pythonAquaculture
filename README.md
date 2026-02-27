# pythonAquaculture

## New Contributor: 5-Minute Setup (Windows)

For handing this repo to a new teammate, use this quick path first:

```powershell
git clone https://github.com/chengzhi666/pythonAquaculture.git
cd pythonAquaculture
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 -SkipChecks
```

What the bootstrap now covers:

- Create `.venv` (if missing)
- Install `.[dev]`
- Install `fish_intel_mvp/requirements.txt` (includes `playwright`)
- Install Playwright Chromium runtime
- Create `.env.local` and `fish_intel_mvp/.env` from templates

Recommended first-run backend (avoids local DrissionPage port/profile issues):

```powershell
$env:JD_BROWSER_BACKEND='playwright'
$env:CNKI_BROWSER_BACKEND='playwright'
$env:TAOBAO_COOKIE_REFRESH_BACKEND='playwright'
```

Then run one job to verify environment:

```powershell
.\.venv\Scripts\python fish_intel_mvp\run_one.py jd
```

Detailed onboarding guide: see [ONBOARDING.md](ONBOARDING.md).
水产情报采集 MVP。
目标是把多来源采集统一成一套流程：`跑批 -> 入 MySQL -> 可回溯 -> 可去重`。

## 系统架构

项目当前以 **MySQL 作为主存储**，并保留 SQLite 作为可选本地模式：

### 系统一：Streamlit WebUI（默认 MySQL）

- **入口**：`app.py`
- **数据库**：默认 MySQL（可通过 `STORAGE_BACKEND=sqlite` 切换到本地 SQLite）
- **用途**：快速展示、交互式采集、情报检索
- **爬虫模块**：`crawlers/` 目录下的爬虫
- **运行方式**：`streamlit run app.py`

### 系统二：批量处理系统（MySQL）

- **入口**：`fish_intel_mvp/run_one.py`
- **数据库**：MySQL（需要预先配置和创建库表）
- **用途**：生产级批量数据采集、日志审计、完整数据溯源
- **爬虫模块**：`fish_intel_mvp/jobs/` 目录下的爬虫
- **运行方式**：`python fish_intel_mvp/run_one.py <job>`

> **注意**：从当前版本开始，`app.py` / `runner.py` 默认也写入 MySQL。只有显式设置 `STORAGE_BACKEND=sqlite` 才使用本地 SQLite。

## 当前状态

- `jd`：已可跑，入表 `product_snapshot`，含 `raw_event` 证据。
- `moa`：已可跑，入表 `intel_item`，含 `raw_event` 证据。
- `cnki`：已接入 `paper_meta`，可跑但依赖本机 Selenium/Edge 驱动环境。
- `taobao`：已实现（基于淘宝 H5 接口抓取，需有效 `TAOBAO_COOKIE`）。
- `bjform`：占位。

## 目录结构

```text
pythonAquaculture/
  app.py                        # Streamlit WebUI 入口
  runner.py                     # 配置驱动的采集框架
  config/
    sites.json                  # 采集源配置文件
  crawlers/                     # 爬虫模块（供 Streamlit / runner 使用）
    cnki_crawler.py
    moa_fishery_crawler.py
    scholar_crawler.py
  storage/
    db.py                       # 统一存储层（默认 MySQL，兼容 SQLite）
  fish_intel_mvp/               # 批量处理系统（MySQL）
    common/
      db.py
      logger.py
      parse_rules.py
    jobs/
      crawl_jd.py
      crawl_moa_fishery.py
      crawl_cnki.py
      crawl_taobao.py
      crawl_bj_form.py
    run_one.py
    schema.sql
    requirements.txt
    .env                        # MySQL系统配置
    .env.example                # 配置示例
```

## 环境准备

1. **Python 3.9+**
2. **MySQL**（主存储，系统一/二默认都使用）
3. 在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -U pip
pip install -r fish_intel_mvp\requirements.txt
```

## 快速开始

### 方案 A：Streamlit WebUI（默认走 MySQL）

```powershell
.\.venv\Scripts\activate
streamlit run app.py
```

然后在浏览器访问 `http://localhost:8501`。

**特点**：

- 与批处理系统共用 MySQL 数据
- 交互式操作，即时反馈
- 可选切换到本地 SQLite（`STORAGE_BACKEND=sqlite`）

### 方案 B：批量处理系统（推荐生产环境）

#### 1. 配置

拷贝并编辑 `fish_intel_mvp/.env`：

```dotenv
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASS=你的MySQL密码
DB_NAME=fish_intel

JD_KEYWORDS=大黄鱼
JD_PAGES=1
CNKI_THEME=水产养殖
CNKI_PAPERS=10
```

#### 2. 建库建表

```powershell
# 进入 MySQL 执行
mysql -u root -p

# 然后在 MySQL 中执行
CREATE DATABASE IF NOT EXISTS fish_intel DEFAULT CHARSET utf8mb4;
USE fish_intel;
SOURCE C:/Users/qiaoruo/PycharmProjects/pythonAquaculture/fish_intel_mvp/schema.sql;
```

#### 3. 运行任务

```powershell
.\.venv\Scripts\activate
python fish_intel_mvp\run_one.py jd
python fish_intel_mvp\run_one.py taobao
python fish_intel_mvp\run_one.py moa
python fish_intel_mvp\run_one.py cnki
# 仅刷新淘宝Cookie（会弹浏览器，手动登录后自动写回 fish_intel_mvp/.env）
python fish_intel_mvp\jobs\refresh_taobao_cookie.py
```

### 常见配置项

- `DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME` - MySQL 连接配置
- `CNKI_THEME` - 知网搜索主题（默认: aquaculture）
- `CNKI_PAPERS` - 想采集的论文数量（默认: 10）
- `CNKI_MAX_PAGES` - 最多检索多少页（默认: 5）
- `EDGE_DRIVER_PATH/CHROME_DRIVER_PATH` - 浏览器驱动路径（留空自动寻找）
- `TAOBAO_COOKIE` - 淘宝的登录Cookie（可选）
- `TAOBAO_KEYWORDS` - 淘宝抓取关键词（逗号分隔）
- `TAOBAO_PAGES` - 每个关键词抓取页数
- `TAOBAO_PAGE_SIZE` - 每页抓取条数（建议 <= 50）
- `TAOBAO_AUTO_REFRESH_COOKIE` - cookie 缺失/失效时是否自动拉起浏览器刷新（默认: 1）
- `TAOBAO_COOKIE_REFRESH_TIMEOUT_SECONDS` - 浏览器登录等待超时（默认: 180）

## 验收 SQL

### 运行记录

```sql
USE fish_intel;
SELECT id, source_name, status, items
FROM crawl_run
ORDER BY id DESC
LIMIT 10;
```

### 京东（product_snapshot）

```sql
SELECT platform, keyword, title, price, detail_url, raw_id
FROM product_snapshot
ORDER BY id DESC
LIMIT 20;
```

### 渔业渔政公告（intel_item）

```sql
SELECT pub_time, org, title, source_url, raw_id
FROM intel_item
ORDER BY id DESC
LIMIT 20;
```

### 知网（paper_meta）

```sql
SELECT pub_date, title, source, url, raw_id
FROM paper_meta
ORDER BY id DESC
LIMIT 20;
```

### 原始证据（raw_event）

```sql
SELECT id, source_name, title, pub_time, url
FROM raw_event
ORDER BY id DESC
LIMIT 20;
```

## 常见问题

1. `ModuleNotFoundError: No module named 'common'`
   请从项目根目录运行：`python fish_intel_mvp\run_one.py <job>`。

2. `Access denied for user 'root'@'localhost'`
   检查 `fish_intel_mvp/.env` 的 `DB_USER/DB_PASS`。

3. JD 抓到 `items=0`
   先用 `JD_PAGES=1`，并手动确认浏览器页面确实出现商品卡片。

4. MOA 出现 MySQL 断连
   任务里已对大内容做截断和 PDF 特殊处理。若仍偶发，重跑即可。

5. CNKI 启动失败或超时
   通常是 Edge 与 EdgeDriver 版本不匹配，或本机 webdriver 环境问题。
   可在 `.env` 设置 `EDGE_DRIVER_PATH`。

6. Taobao 提示 `FAIL_SYS_TOKEN_EXOIRED`
   默认会自动触发 cookie 刷新；若不想自动弹浏览器，可设置 `TAOBAO_AUTO_REFRESH_COOKIE=0`，再手动运行 `python fish_intel_mvp\jobs\refresh_taobao_cookie.py`。

7. Taobao 扫码页自动跳回账号密码
   可设置 `TAOBAO_COOKIE_REFRESH_USE_SYSTEM_PROFILE=1`（默认）并将 `TAOBAO_COOKIE_REFRESH_START_URL` 设为 `https://login.taobao.com/member/login.jhtml`；必要时手动运行刷新脚本再扫码。

## 开发指南

详见 [DEVELOPMENT.md](DEVELOPMENT.md)，包含：

- 环境设置和依赖安装
- 代码质量工具（Black、Flake8、MyPy、Pylint）
- 单元测试和覆盖率
- 公共工具函数使用
- 配置管理
- 数据库优化技巧

## 项目优化

最近的优化包括：

- ✅ **批量插入优化**：SQLite 使用事务提高性能
- ✅ **日志系统**：统一的日志记录和错误处理
- ✅ **工具函数**：提取公共的文本处理函数（`crawlers/utils.py`）
- ✅ **Streamlit 缓存**：查询结果缓存（1小时）
- ✅ **配置管理**：统一的环境变量管理（`config_mgr.py`）
- ✅ **项目规范**：`pyproject.toml` 和 `pytest` 测试框架
- ✅ **测试框架**：单元测试示例（`tests/test_storage.py`）

## Git 提交

```powershell
git add .
git commit -m "your message"
git push
```
