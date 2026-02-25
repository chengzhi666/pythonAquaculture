# Company Crawler Project

This is a standalone delivery package that unifies three crawlers into one runnable project:

- `crawlers/cnki_crawler.py`
- `crawlers/moa_fishery_crawler.py`
- `crawlers/scholar_crawler.py`

The project provides one entry point (`main.py`), one source config (`config/sources.json`), and one SQLite database (`intel.db`).

## 1. Quick Start

```powershell
cd company_crawler_project
python -m venv .venv
.\.venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
```

Run all enabled sources:

```powershell
python main.py
```

Run only one source:

```powershell
python main.py --source scholar
```

Override params from command line:

```powershell
python main.py --source cnki --set cnki.theme="water quality" --set cnki.papers_need=10
python main.py --source moa_yyj_tzgg --set moa_yyj_tzgg.max_pages=2
```

Collect without writing DB:

```powershell
python main.py --no-save --source scholar
```

## 2. Project Layout

```text
company_crawler_project/
  main.py
  runner.py
  requirements.txt
  config/
    sources.json
  crawlers/
    __init__.py
    utils.py
    cnki_crawler.py
    moa_fishery_crawler.py
    scholar_crawler.py
  storage/
    __init__.py
    db.py
```

## 3. Output

Data is saved into `intel.db` table `intel_item` with deduplication by `source_url`.

Main output fields:

- `title`
- `content`
- `pub_time`
- `region`
- `org`
- `source_type`
- `source_url`
- `tags`
- `extra`

## 4. Notes

- CNKI crawler depends on local Selenium + Edge browser runtime.
- If your environment blocks external requests, source crawling may fail but the project structure is still valid.

