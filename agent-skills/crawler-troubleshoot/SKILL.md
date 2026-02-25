---
name: crawler-troubleshoot
description: 对爬虫失败做快速排障并给出最小可验证修复。适用于任务失败、抓取量突降、选择器失效、Cookie 过期、反爬拦截、写库异常等问题。
---

# Crawler Troubleshoot

## 概览

目标是“尽快定位根因 + 最小改动恢复采集”。所有结论都要由日志、代码路径或复现实验支撑。

## 中文输出风格

- 第一段先给一句结论：`根因已定位` / `高概率根因` / `证据不足需补采样`。
- 固定用 5 段输出：`现象`、`根因`、`证据`、`最小修复`、`回归防护`。
- 证据必须包含可定位信息（日志关键词、文件路径、关键命令结果）。
- 不能泛泛建议“重试看看”，必须写清触发条件和预期结果。

## 命令习惯（Windows / PowerShell）

优先使用以下命令：

```powershell
.\.venv\Scripts\python fish_intel_mvp\run_one.py jd
.\.venv\Scripts\python fish_intel_mvp\run_one.py taobao
.\.venv\Scripts\python fish_intel_mvp\run_one.py salmon

rg -n "timeout|retry|cookie|selector|429|403|Traceback|FAIL" crawlers fish_intel_mvp logs

Get-ChildItem logs -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 20 FullName,LastWriteTime
Get-ChildItem logs -Recurse | Select-String -Pattern "ERROR|Traceback|timeout|429|403"
```

## 工作流

1. 重建故障上下文。
- 记录失败命令、时间、目标站点、环境配置。
2. 判断故障类型。
- 网络/DNS、Cookie/鉴权、反爬挑战、DOM 漂移、解析异常、写库异常。
3. 证据核验。
- 对照最近日志、堆栈、关键代码路径，做一次最小复现。
4. 提出最小修复。
- 优先局部修改，避免排障阶段的大重构。
5. 增加防回归措施。
- 补重试策略、分类错误、选择器降级或针对性测试。

## 输出约定

按以下顺序输出：
1. 现象
2. 根因
3. 证据
4. 最小修复
5. 回归防护

## 仓库重点

优先查看：
- `crawlers/`
- `fish_intel_mvp/jobs/`
- `storage/`
- `fish_intel_mvp/common/db.py`
- `.env` 与爬虫相关环境变量

## 参考资料

- `references/failure-patterns.md`
- `references/diagnostic-commands.md`
