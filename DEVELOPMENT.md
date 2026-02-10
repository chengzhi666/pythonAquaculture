# 开发指南

## 项目环境设置

### 1. 创建虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 2. 安装依赖

```powershell
# 安装基础依赖
pip install -r fish_intel_mvp\requirements.txt

# 或使用 pyproject.toml（推荐）
pip install -e ".[dev]"
```

### 3. 本地配置

```powershell
# 复制本地开发配置（可选）
copy .env.local.example .env.local
```

## 代码质量工具

### 代码格式化（Black）

```powershell
black .
```

### 代码检查（Flake8）

```powershell
flake8 crawlers/ storage/ query/ --max-line-length=100
```

### 类型检查（MyPy）

```powershell
mypy crawlers/ storage/ query/ --ignore-missing-imports
```

### 代码分析（Pylint）

```powershell
pylint crawlers/ storage/ query/
```

## 单元测试

### 运行所有测试

```powershell
pytest
```

### 运行特定测试

```powershell
pytest tests/test_storage.py -v
```

### 生成覆盖率报告

```powershell
pytest --cov=crawlers --cov=storage --cov-report=html
```

### 运行标记的测试

```powershell
pytest -m unit
pytest -m integration
```

## 调试技巧

### 1. 启用详细日志

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
```

### 2. 使用 IPython 调试

```powershell
pip install ipython
```

### 3. 打印配置

```python
from config_mgr import get_config
config = get_config()
print(config.to_dict())
```

## 公共工具函数

项目在 `crawlers/utils.py` 中提供了通用工具函数：

```python
from crawlers.utils import clean_text, extract_keywords, extract_date, normalize_url

# 清理文本
text = clean_text("  hello   world  ")  # → "hello world"

# 提取关键词
keywords = extract_keywords("关键词：A;B;C")  # → ["A", "B", "C"]

# 提取日期
date = extract_date("发布于 2026-02-09 12:00")  # → "2026-02-09"

# 标准化 URL
url = normalize_url("//example.com/page", "http://test.com")  # → "http://example.com/page"
```

## 配置管理

使用统一的配置管理类 `config_mgr.Config`：

```python
from config_mgr import get_config

config = get_config()
print(f"数据库：{config.DB_HOST}:{config.DB_PORT}")
print(f"日志级别：{config.LOG_LEVEL}")
print(f"CNKI 主题：{config.CNKI_THEME}")

# 导出所有配置
all_config = config.to_dict()
```

## 数据库优化

### SQLite 批量操作

```python
from storage.db import save_items

items = [
    {"title": "项目1", "source_url": "http://example.com/1", ...},
    {"title": "项目2", "source_url": "http://example.com/2", ...},
]

# 使用事务一次性保存多条记录（自动去重）
save_items(items)
```

### Streamlit 缓存查询

```python
import streamlit as st

@st.cache_data(ttl=3600)
def _cached_query(keyword: str, order_by: str):
    """缓存查询结果（1小时）"""
    return query_intel(keyword=keyword, order_by=order_by)

# 使用
rows = _cached_query(keyword="水产", order_by="time")

# 手动清除缓存
_cached_query.clear()
```

## 常见问题排查

### 1. pytest 找不到模块

确保在项目根目录运行测试：

```powershell
cd pythonAquaculture
pytest
```

### 2. 导入错误

确保虚拟环境已激活且依赖已安装：

```powershell
pip install -e ".[dev]"
```

### 3. 数据库连接失败

检查配置管理类的验证：

```python
from config_mgr import get_config
config = get_config()
config.validate()  # 抛出异常如果配置错误
```
