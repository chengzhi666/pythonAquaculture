"""爬虫通用工具函数"""

import logging
import re
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# ===== 请求默认配置 =====
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

DEFAULT_TIMEOUT = 15  # 秒


def create_session(
    retries: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: tuple[int, ...] = (500, 502, 503, 504),
) -> requests.Session:
    """
    创建带有默认 UA 和自动重试的 requests.Session。

    - retries: 最大重试次数
    - backoff_factor: 重试间隔因子（0.5 → 0s, 0.5s, 1s, ...）
    - status_forcelist: 对哪些 HTTP 状态码自动重试
    """
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["GET", "HEAD", "OPTIONS"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def clean_text(text: Optional[str]) -> str:
    """清理文本：去除多余空格、特殊字符"""
    if not text:
        return ""
    # 去除全角空格
    text = text.replace("\u3000", " ")
    # 去除多余换行和前后空格
    text = text.replace("\n", " ").strip()
    # 去除多余空格
    text = re.sub(r"\s+", " ", text)
    return text


def extract_keywords(text: str, separator: str = ";,") -> list[str]:
    """从文本中提取关键词（支持多种分隔符）"""
    text = clean_text(text)
    if not text:
        return []

    # 移除"关键词："等前缀
    text = re.sub(
        r"^(?:keywords?|key\s*words?|\u5173\u952e\u8bcd|\u5173\u952e\u5b57)[:：\s]*",
        "",
        text,
        flags=re.I,
    )

    # 标准化分隔符
    for sep in separator:
        text = text.replace(chr(0xFF01 + ord(sep) - ord(",")), sep)  # 全角转半角

    # 按分隔符分割
    parts = re.split(f"[{separator}\\s]+", text)
    return [p.strip() for p in parts if p.strip()]


def extract_date(text: str) -> Optional[str]:
    """从文本中提取日期（YYYY-MM-DD 格式）"""
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else None


def normalize_url(href: Optional[str], base_url: str = "") -> str:
    """标准化 URL"""
    if not href:
        return ""

    href = href.strip()

    # 协议相对 URL
    if href.startswith("//"):
        return f"https:{href}"

    # 绝对 URL
    if href.startswith("http://") or href.startswith("https://"):
        return href

    # 根路径
    if href.startswith("/"):
        if base_url:
            from urllib.parse import urlparse

            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{href}"
        return href

    # 相对 URL
    if base_url:
        from urllib.parse import urljoin

        return urljoin(base_url, href)

    return href
