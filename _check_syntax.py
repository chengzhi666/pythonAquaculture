import ast
import sys

path = r"c:\Users\qiaoruo\PycharmProjects\pythonAquaculture\run_mineru_comparison.py"
try:
    with open(path, encoding="utf-8") as f:
        ast.parse(f.read())
    print("OK")
except SyntaxError as e:
    print(f"Syntax error at line {e.lineno}: {e.msg}")
    sys.exit(1)
