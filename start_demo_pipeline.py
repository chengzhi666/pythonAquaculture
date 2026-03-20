"""
Run the demo data-collection pipeline and then launch the dashboard.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
MVP_ROOT = PROJECT_ROOT / "fish_intel_mvp"
PYTHON = sys.executable
APP_URL = "http://127.0.0.1:5000"

CRAWL_STEPS = [
    {
        "name": "salmon",
        "command": [PYTHON, "run_one.py", "salmon"],
        "cwd": MVP_ROOT,
        "success_message": "三文鱼数据入库成功",
    },
    {
        "name": "moa",
        "command": [PYTHON, "run_one.py", "moa"],
        "cwd": MVP_ROOT,
        "success_message": "农业部政策数据入库成功",
    },
    {
        "name": "cnki",
        "command": [PYTHON, "run_one.py", "cnki"],
        "cwd": MVP_ROOT,
        "success_message": "知网学术文献数据入库成功",
    },
    {
        "name": "moa_prices",
        "command": [PYTHON, "jobs/crawl_moa_prices.py"],
        "cwd": MVP_ROOT,
        "success_message": "农业部线下价格数据入库成功",
    },
]

# The current project dashboard is a Flask app.
DASHBOARD_CMD = [PYTHON, "app.py"]
# If you later switch to Streamlit, replace the line above with:
# DASHBOARD_CMD = [PYTHON, "-m", "streamlit", "run", "app.py"]


def print_banner(message: str) -> None:
    line = "=" * 88
    print(line)
    print(message)
    print(line)


def icon(emoji: str, fallback: str) -> str:
    encoding = (getattr(sys.stdout, "encoding", "") or "").lower()
    return emoji if "utf" in encoding else fallback


def run_job(step: dict[str, object], env: dict[str, str]) -> None:
    start_icon = icon("🚀", "[START]")
    ok_icon = icon("✅", "[OK]")
    job_name = str(step["name"])
    command = list(step["command"])
    cwd = Path(step["cwd"])
    success_message = str(step["success_message"])
    print_banner(f"{start_icon} 开始执行采集任务：{job_name}")
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(f"{job_name} 采集失败，退出码 {result.returncode}")

    print(f"{ok_icon} {success_message}")


def launch_dashboard(env: dict[str, str]) -> subprocess.Popen:
    start_icon = icon("🚀", "[START]")
    print_banner(f"{start_icon} 正在启动可视化看板...")
    return subprocess.Popen(
        DASHBOARD_CMD,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> int:
    start_icon = icon("🚀", "[START]")
    fail_icon = icon("❌", "[FAIL]")
    party_icon = icon("🎉", "[DONE]")

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")

    print_banner(f"{start_icon} 渔业情报系统：一键采集与看板启动流程")

    try:
        for step in CRAWL_STEPS:
            run_job(step, env)

        dashboard_process = launch_dashboard(env)
    except FileNotFoundError as exc:
        print(f"{fail_icon} 未找到命令或脚本：{exc}")
        return 1
    except Exception as exc:
        print(f"{fail_icon} 流程执行失败：{exc}")
        return 1

    print(
        f"{party_icon} 数据采完且看板已启动！请立即打开浏览器访问 "
        f"{APP_URL} 截图：1.价格趋势图 2.品种分布饼图 3.线上线下对比图"
    )
    print(f"Dashboard PID: {dashboard_process.pid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
