# pythonAquaculture VS Code 快速配置摘要

本项目已完成以下 VS Code 配置：

## ✅ 完成的任务

### 1. 创建 VS Code 配置文件

| 文件                       | 功能                                    | 状态    |
| -------------------------- | --------------------------------------- | ------- |
| `.vscode/settings.json`    | Python 环境、格式化、扩展路径设置       | ✅ 完成 |
| `.vscode/launch.json`      | 9 个调试配置（Streamlit、爬虫、测试等） | ✅ 完成 |
| `.vscode/tasks.json`       | 10 个运行任务（爬虫、测试、格式化等）   | ✅ 完成 |
| `.vscode/extensions.json`  | 7 个推荐扩展                            | ✅ 完成 |
| `.vscode/keybindings.json` | F11 快速启动 Streamlit 等快捷键         | ✅ 完成 |
| `.vscode/README.md`        | 详细配置文档                            | ✅ 完成 |

### 2. 创建自动化脚本

| 文件               | 功能                                   | 状态    |
| ------------------ | -------------------------------------- | ------- |
| `setup_vscode.ps1` | 一键部署脚本（安装扩展、配置虚拟环境） | ✅ 完成 |

## 🚀 立即开始

### 步骤 1: 安装扩展（3 种方式）

**方式 A - 一键安装脚本：**

```powershell
.\setup_vscode.ps1 -All
```

**方式 B - VS Code 命令面板：**

1. `Ctrl+Shift+X` 打开扩展
2. 搜索 `@recommended`
3. 点击"安装"

**方式 C - 手动安装指定扩展：**

```powershell
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension ms-python.black-formatter
code --install-extension charliermarsh.ruff
```

### 步骤 2: 配置虚拟环境

```powershell
# 如果还没有虚拟环境
python -m venv .venv

# 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r fish_intel_mvp/requirements.txt
```

### 步骤 3: 打开项目

```powershell
code .
```

## ⌨️ 快捷键速查表

| 按键              | 功能                       |
| ----------------- | -------------------------- |
| **F11**           | 🚀 快速启动 Streamlit 应用 |
| **F5**            | 🐛 启动调试器              |
| **Ctrl+Shift+B**  | 🎨 使用 Black 格式化代码   |
| **Ctrl+`**        | 📺 打开/关闭集成终端       |
| **Ctrl+Shift+P**  | 🔍 打开命令面板            |
| **Ctrl+K Ctrl+C** | 💬 快速注释                |

## 📦 调试配置概览

在 `.vscode/launch.json` 中配置了以下运行/调试配置：

1. **Run Streamlit (app.py)** - 启动 Streamlit 应用
2. **Run update_all.py** - 执行数据更新脚本
3. **Run crawler - CNKI** - 调试 CNKI 爬虫
4. **Run crawler - Taobao** - 调试淘宝爬虫
5. **Run crawler - MOA Fishery** - 调试农业部爬虫
6. **Run crawler - JD** - 调试 JD 爬虫
7. **Run pytest** - 执行单元测试
8. **Python: Current File** - 运行当前打开的文件
9. **Remote Debug** - 远程调试连接

### 选择调试配置

按 **F5** 后在下拉菜单中选择相应配置。

## 🛠️ 可用任务

按 **Ctrl+Shift+B** 查看所有任务，常用任务：

- **Run Streamlit (app.py)** - 启动 Streamlit 服务器
- **Run pytest** - 运行所有测试
- **Lint with Ruff** - 代码检查
- **Format with Black** - 代码格式化

## 🐍 Python 环境验证

```powershell
# 检查 Python 版本
python --version

# 检查解释器位置（应该在 .venv 中）
python -c "import sys; print(sys.executable)"

# 检查已安装的包
pip list

# 确认虚拟环境已激活（提示符应该显示 (.venv)）
```

## 📝 配置文件位置

所有配置文件都在 `.vscode/` 目录中：

```
pythonAquaculture/
├── .vscode/
│   ├── settings.json          # 编辑器和 Python 设置
│   ├── launch.json            # 调试配置
│   ├── tasks.json             # 运行任务
│   ├── extensions.json        # 推荐扩展
│   ├── keybindings.json       # 快捷键
│   └── README.md              # 详细文档
├── setup_vscode.ps1           # 自动化安装脚本
├── pyproject.toml             # 项目配置
├── pytest.ini                 # Pytest 配置
└── ...
```

## 🔧 常见配置调整

### 修改 Python 解释器

如果自动检测失败：

1. `Ctrl+Shift+P`
2. "Python: Select Interpreter"
3. 选择 `.\.venv\Scripts\python.exe`

### 禁用某些 Ruff 规则

编辑 `.vscode/settings.json`：

```json
"ruff.lint.args": ["--extend-ignore=E501,W503"]
```

### 修改代码格式化宽度

编辑 `.vscode/settings.json`：

```json
"[python]": {
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "ms-python.black-formatter"
}
```

## 💡 使用建议

1. **首次启动**: 运行 `setup_vscode.ps1 -All` 完成所有配置
2. **日常工作**: 使用 F11 快速启动 Streamlit，F5 调试代码
3. **提交代码**: 格式化后使用 Ruff 检查代码质量
4. **测试**: 按 Ctrl+Shift+B 运行测试任务
5. **扩展管理**: 定期检查 `@recommended` 扩展是否已安装

## ❓ 需要帮助？

参考详细文档：[.vscode/README.md](.vscode/README.md)

---

**配置完成于**: 2026 年 2 月 9 日
**虚拟环境**: `.venv/`
**Python 版本**: 3.8+
**编辑器**: Visual Studio Code 1.80+
