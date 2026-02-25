# Antigravity 协作指南 (Chinese Guide)

欢迎使用 Antigravity！为了让你获得最舒适的开发体验，这里有一些专为中国开发者准备的建议和最佳实践。

## 1. 沟通技巧 (Communication Tips)

### 使用中文提问
Antigravity 完全支持中文交互。你可以直接用中文描述你的需求、问题或修改建议。
- **推荐**: "请帮我重构这个函数，使其更易读。"
- **推荐**: "这个报错是什么意思？怎么解决？"

### 上下文明确
当指代特定代码或文件时，尽量明确。
- **推荐**: "修改 `app.py` 中的 `main` 函数..."
- **推荐**: "根据 `setup_vscode.ps1` 的逻辑..."

## 2. 环境配置 (Environment Setup)

### Pip 镜像加速
我们在 `setup_vscode.ps1` 中添加了自动配置清华源的功能。
运行以下命令即可快速配置：
```powershell
.\setup_vscode.ps1 -All
```
这会将你的 pip 源设置为 `https://pypi.tuna.tsinghua.edu.cn/simple`，显著提升国内下载速度。

### 中文乱码问题
如果你在运行 `pytest` 时发现测试用例名称是乱码（如 `\u6d4b\u8bd5`），不用担心，我们已经在 `pytest.ini` 中修复了这个问题：
```ini
disable_test_id_escaping_and_forfeit_all_rights_to_community_support = True
```
现在的测试报告将直接显示中文名称。

## 3. 推荐 VS Code 插件

除了 Python 基础插件外，以下插件对中文开发者非常有用：

- **Chinese (Simplified) (简体中文)**: 将 VS Code 界面设置为中文。
- **Translation** (by Starlab): 划词翻译，方便阅读英文文档。

## 4. 常见问题 (FAQ)

**Q: Antigravity 生成的代码注释是英文的，我想要中文的。**
A: 你可以在提问时明确要求："请用中文添加注释"。或者在 `.gemini/antigravity/brain/task.md` (如果有的话) 或项目根目录创建一个 `RULES.md` 文件，写入 "Always use Chinese for code comments."。

**Q: 下载依赖库超时怎么办？**
A: 确保你已经运行了 `setup_vscode.ps1` 配置了国内镜像源。如果仍然超时，可以尝试临时使用阿里云源：`pip install -i https://mirrors.aliyun.com/pypi/simple/ <package_name>`。

---
祝你在 Antigravity 的辅助下编码愉快！
