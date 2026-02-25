# Diagnostic Command Patterns

Run commands from repository root unless noted.

## 1. Reproduce a Job

```powershell
python fish_intel_mvp/jobs/crawl_salmon.py
```

If repo uses venv:

```powershell
.\.venv\Scripts\python fish_intel_mvp/jobs/crawl_salmon.py
```

## 2. Find Recent Errors

```powershell
Get-ChildItem logs -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 20 FullName,LastWriteTime
```

```powershell
Get-ChildItem logs -Recurse | Select-String -Pattern "ERROR|Traceback|timeout|429|403"
```

## 3. Inspect Crawler Modules Quickly

```powershell
rg -n "requests|timeout|retry|selector|BeautifulSoup|xpath" crawlers fish_intel_mvp/jobs
```

## 4. Verify Config Inputs

```powershell
rg -n "os\\.environ|getenv|ENV|DATABASE|COOKIE|TOKEN" fish_intel_mvp
```

## 5. Validate DB Touchpoints

```powershell
rg -n "INSERT|UPDATE|executemany|commit|rollback" fish_intel_mvp storage
```

Use these commands to gather evidence before proposing code changes.
