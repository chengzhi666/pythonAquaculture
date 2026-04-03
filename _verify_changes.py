"""Verify that the two modified files can be imported without errors."""
import ast
import sys
import os
import importlib

# --- 1. Syntax check ---
files = [
    r"fish_intel_mvp\jobs\crawl_taobao.py",
    r"run_mineru_comparison.py",
]
for f in files:
    try:
        with open(f, encoding="utf-8") as fh:
            ast.parse(fh.read())
        print(f"[SYNTAX OK] {f}")
    except SyntaxError as e:
        print(f"[SYNTAX FAIL] {f}: line {e.lineno} - {e.msg}")
        sys.exit(1)

# --- 2. Import check: crawl_taobao ---
sys.path.insert(0, "fish_intel_mvp")
os.environ.setdefault("TAOBAO_COOKIE", "")  # avoid interactive prompt
try:
    mod = importlib.import_module("jobs.crawl_taobao")
    # Check key symbols exist
    assert hasattr(mod, "HealStats"), "HealStats class missing"
    assert hasattr(mod, "run"), "run() function missing"
    assert hasattr(mod, "TokenExpiredError"), "TokenExpiredError missing"

    # Instantiate HealStats
    hs = mod.HealStats()
    assert hs.pages_attempted == 0
    assert hs.page_success_rate == 0.0
    d = hs.to_dict()
    assert "page_success_rate" in d
    print(f"[IMPORT OK] crawl_taobao  |  HealStats().to_dict() = {d}")
except Exception as exc:
    print(f"[IMPORT FAIL] crawl_taobao: {exc}")
    import traceback; traceback.print_exc()
    sys.exit(1)

# --- 3. Import check: run_mineru_comparison ---
sys.path.insert(0, ".")
try:
    mod2 = importlib.import_module("run_mineru_comparison")
    assert hasattr(mod2, "METHODS"), "METHODS list missing"
    print(f"[IMPORT OK] run_mineru_comparison  |  METHODS = {mod2.METHODS}")
except Exception as exc:
    print(f"[IMPORT FAIL] run_mineru_comparison: {exc}")
    import traceback; traceback.print_exc()
    sys.exit(1)

print("\n=== ALL CHECKS PASSED ===")
