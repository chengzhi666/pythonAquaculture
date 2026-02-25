---
name: python-code-review
description: 对 Python 改动做“问题优先”的代码审查。适用于审查 diff、定位行为回归、评估风险、检查测试覆盖缺口，尤其是 crawlers、storage、fish_intel_mvp 相关改动。
---

# Python Code Review

## 概览

聚焦“会出错/会回归/会丢数据”的问题，先给结论再给证据。输出以发现项为主，摘要为辅。

## 中文输出风格

- 第一行先给审查结论：`存在阻断问题` / `可合并但有风险` / `未发现阻断问题`。
- 发现项按严重级别排序：`严重`、`高`、`中`、`低`。
- 每个发现项必须包含：`文件位置`、`问题原因`、`触发场景`、`最小修复建议`。
- 若无发现项，必须明确写出“未发现阻断问题”，并补充剩余风险或测试盲区。

## 命令习惯（Windows / PowerShell）

优先使用以下命令风格：

```powershell
git diff --name-only
git diff

rg -n "TODO|FIXME|timeout|retry|except|commit|rollback" crawlers fish_intel_mvp storage tests

.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m pytest tests/test_storage.py -v

.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy crawlers storage query --ignore-missing-imports
```

## 工作流

1. 确认范围。
- 明确改动文件、业务目标、潜在受影响模块。
2. 先读 diff，再读上下文。
- 从改动行扩展到调用链、异常处理、写库路径。
3. 标注风险等级。
- 严重：数据损坏、数据丢失、生产主路径不可用、安全问题。
- 高：常见路径崩溃或明显行为回归。
- 中：边界场景错误或稳定性风险。
- 低：可维护性问题或次要改进。
4. 核验证据。
- 每条发现必须有文件和行号定位，且给出可复现场景。
5. 检查测试缺口。
- 明确已覆盖与未覆盖的高风险路径，给最小测试建议。

## 输出约定

按以下顺序输出：
1. 审查结论
2. 发现项（按严重级别排序）
3. 开放问题或假设
4. 建议补测
5. 可选修复计划

## 仓库重点

优先关注：
- 爬虫稳定性：超时、重试、选择器漂移、反爬处理。
- 存储正确性：MySQL/SQLite 行为一致性、去重、事务边界。
- 配置安全性：环境变量默认值、回退路径、日志泄露敏感信息。
- 指标完整性：items 计数、run 状态、失败记录是否一致。

## 参考资料

- `references/review-checklist.md`
- `references/test-gap-patterns.md`
