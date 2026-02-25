---
name: release-readiness-check
description: 在发版前执行发布门禁检查，并输出“可发布/带条件可发布/不可发布”结论与阻断项。适用于部署前、打 tag 前、发布分支合并前。
---

# Release Readiness Check

## 概览

对当前版本做一次可执行的发布检查，优先识别阻断项和高风险项，给出明确发布结论。

## 中文输出风格

- 第一行直接给结论：`可发布`、`带条件可发布`、`不可发布`。
- 阻断项必须放在最前，并按影响面排序。
- 每个阻断项包含：`证据`、`影响`、`最小处置`、`负责人`（若可确定）。
- 最后必须给出 `发布后观察项`，避免“通过就结束”。

## 命令习惯（Windows / PowerShell）

优先使用以下命令：

```powershell
git diff --name-only
git diff

.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m pytest -m integration
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy crawlers storage query --ignore-missing-imports

.\.venv\Scripts\python fish_intel_mvp\run_one.py jd
.\.venv\Scripts\python fish_intel_mvp\run_one.py moa
```

## 工作流

1. 确认发布范围。
- 分支、commit 范围、目标环境、发布时间窗口。
2. 执行质量门禁。
- Lint、类型检查、关键测试是否通过。
3. 配置与密钥安全检查。
- 环境变量齐全、无本地调试残留、无敏感信息入库或入日志。
4. 数据路径安全检查。
- 写库兼容性、幂等性、迁移与回滚可行性。
5. 运维可观测性检查。
- 关键任务日志、告警、失败重试是否可用。
6. 输出发布结论与行动项。
- 明确阻断项、条件项、发布前必须完成动作。

## 输出约定

按以下顺序输出：
1. 发布结论
2. 阻断项
3. 高风险警告
4. 发布前必须完成
5. 发布后观察项

## 仓库重点

优先关注：
- `crawlers/`、`fish_intel_mvp/jobs/` 的行为变更。
- `storage/`、`fish_intel_mvp/common/db.py`、`schema.sql` 的数据安全。
- `.env.example`、`.env.local.example` 的配置一致性。
- `pyproject.toml`、`pytest.ini` 对质量门禁的要求。

## 参考资料

- `references/release-gates.md`
- `references/report-template.md`
