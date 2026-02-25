# Developer Onboarding (Windows + PowerShell)

This guide is for new contributors who need to start developing on `pythonAquaculture` quickly and safely.

## 1) Access And Tools

Before coding, make sure you have:

- GitHub repository access (collaborator role).
- Git for Windows installed.
- Python 3.9+ installed and available in PATH.
- A MySQL instance if you need crawler/job runs that write to MySQL.

## 2) Clone And Bootstrap

From PowerShell:

```powershell
git clone https://github.com/chengzhi666/pythonAquaculture.git
cd pythonAquaculture
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1
```

What `bootstrap.ps1` does:

- Creates `.venv` if missing.
- Installs project dependencies with dev tools: `pip install -e .[dev]`.
- Creates local config files if they do not exist:
  - `.env.local` from `.env.local.example`
  - `fish_intel_mvp/.env` from `fish_intel_mvp/.env.example`
- Installs pre-commit hooks (unless skipped).
- Runs `ruff`, `black --check`, and `pytest` (unless skipped).

Optional flags:

```powershell
# Skip lint/test checks
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 -SkipChecks

# Skip pre-commit hook install
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1 -SkipPreCommit
```

## 3) Required Local Config

After bootstrap, review:

- `fish_intel_mvp/.env`
- `.env.local`

Minimum values to update for local MySQL workflow:

- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PASS`
- `DB_NAME`

If you do not have MySQL yet, use tasks that do not require DB writes, or ask for a shared dev database.

## 4) Daily Development Workflow

Always develop on a feature branch, not directly on `main`.

```powershell
git checkout -b feat/short-description
```

Before commit, run:

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m black --check .
.\.venv\Scripts\python -m pytest
```

Commit and push:

```powershell
git add -A
git commit -m "feat: concise change summary"
git push origin feat/short-description
```

Open a PR and wait for CI to pass before merge.

## 5) Common Commands

Run Streamlit app:

```powershell
.\.venv\Scripts\python -m streamlit run app.py
```

Run one job:

```powershell
.\.venv\Scripts\python fish_intel_mvp\run_one.py jd
.\.venv\Scripts\python fish_intel_mvp\run_one.py taobao
.\.venv\Scripts\python fish_intel_mvp\run_one.py moa
.\.venv\Scripts\python fish_intel_mvp\run_one.py cnki
```

Refresh Taobao cookie:

```powershell
.\.venv\Scripts\python fish_intel_mvp\jobs\refresh_taobao_cookie.py
```

## 6) CI Expectations

Current CI gates include:

- Ruff lint
- Black format check
- Unit tests
- Type checking (currently non-blocking in workflow)
- Security scan (Bandit)

If CI fails, check the failed job logs first, then reproduce locally using the same command.

## 7) Troubleshooting

- `python` not found:
  - Reinstall Python and enable "Add Python to PATH".
- Virtual env activation blocked:
  - Use direct interpreter path: `.\.venv\Scripts\python ...` instead of activation.
- MySQL auth errors:
  - Recheck `fish_intel_mvp/.env` credentials and host/port.
- Import/path errors:
  - Ensure commands are run from repository root.

