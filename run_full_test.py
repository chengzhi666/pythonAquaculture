"""
Run the full pytest suite with coverage and print screenshot-friendly summaries.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
PYTEST_CMD = [
    sys.executable,
    "-m",
    "pytest",
    "-v",
    "--cov=.",
    "--cov-report=term-missing",
    "--cov-report=html",
]


def print_banner(message: str) -> None:
    line = "=" * 88
    print(line)
    print(message)
    print(line)


def icon(emoji: str, fallback: str) -> str:
    encoding = (getattr(sys.stdout, "encoding", "") or "").lower()
    return emoji if "utf" in encoding else fallback


def safe_write(text: str) -> None:
    if not text:
        return
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(text.encode(encoding, errors="replace"))
        if not text.endswith("\n"):
            sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
        return
    print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def extract_passed_count(output: str) -> int | None:
    match = re.search(r"(\d+)\s+passed", output)
    if match:
        return int(match.group(1))
    return None


def main() -> int:
    start_icon = icon("🚀", "[START]")
    ok_icon = icon("✅", "[OK]")
    fail_icon = icon("❌", "[FAIL]")

    print_banner(f"{start_icon} 渔业情报系统：全量自动化测试启动...")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Command: {' '.join(PYTEST_CMD)}")

    try:
        result = subprocess.run(
            PYTEST_CMD,
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        print(f"{fail_icon} 未找到可用的 Python/pytest 解释器，请先确认虚拟环境是否安装完整。")
        return 1
    except Exception as exc:
        print(f"{fail_icon} 测试启动失败：{exc}")
        return 1

    if result.stdout:
        safe_write(result.stdout)
    if result.stderr:
        safe_write(result.stderr)

    if result.returncode == 0:
        passed_count = extract_passed_count(result.stdout or "")
        if passed_count is not None:
            print_banner(
                f"{ok_icon} 测试执行完毕，{passed_count} 个用例已通过，请查看 htmlcov/ 目录获取详细报告。"
            )
        else:
            print_banner(f"{ok_icon} 测试执行完毕，请查看 htmlcov/ 目录获取详细覆盖率报告。")
        return 0

    if "No module named pytest" in (result.stderr or ""):
        print(f"{fail_icon} pytest 未安装，请先在当前虚拟环境中执行：pip install pytest pytest-cov")
    else:
        print_banner(f"{fail_icon} 测试执行失败，请根据上方 pytest 输出定位失败用例。")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
