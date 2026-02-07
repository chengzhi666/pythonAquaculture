# pythonAquaculture

水产情报采集 MVP。  
目标是把多来源采集统一成一套流程：`跑批 -> 入 MySQL -> 可回溯 -> 可去重`。

## 当前状态

- `jd`：已可跑，入表 `product_snapshot`，含 `raw_event` 证据。
- `moa`：已可跑，入表 `intel_item`，含 `raw_event` 证据。
- `cnki`：已接入 `paper_meta`，可跑但依赖本机 Selenium/Edge 驱动环境。
- `taobao`：占位（无 `TAOBAO_COOKIE` 时自动跳过）。
- `bjform`：占位。

## 目录结构

```text
pythonAquaculture/
  fish_intel_mvp/
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
    .env
```

## 环境准备

1. Python 3.9+。
2. MySQL（本项目已兼容 MySQL 5.6 的索引长度限制）。
3. 在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -U pip
pip install -r fish_intel_mvp\requirements.txt
```

## 配置

编辑 `fish_intel_mvp/.env`：

```dotenv
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASS=你的密码
DB_NAME=fish_intel

JD_KEYWORDS=大黄鱼
JD_PAGES=1
CNKI_THEME=水产养殖
CNKI_PAPERS=10
```

说明：

- `.env` 不要提交到远程仓库。
- `TAOBAO_COOKIE` 为空时，淘宝任务会自动跳过。

## 建库建表

进入 MySQL 后执行：

```sql
CREATE DATABASE IF NOT EXISTS fish_intel DEFAULT CHARSET utf8mb4;
USE fish_intel;
SOURCE C:/Users/qiaoruo/PycharmProjects/pythonAquaculture/fish_intel_mvp/schema.sql;
```

## 运行任务

在项目根目录执行：

```powershell
.\.venv\Scripts\activate
python fish_intel_mvp\run_one.py jd
python fish_intel_mvp\run_one.py moa
python fish_intel_mvp\run_one.py cnki
```

可用任务名：

- `jd`
- `moa`
- `cnki`
- `taobao`
- `bjform`

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

## Git 提交

```powershell
git add .
git commit -m "your message"
git push
```

