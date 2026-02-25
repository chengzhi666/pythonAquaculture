"""项目配置管理"""

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv


def _load_project_dotenv() -> None:
    """
    Load project dotenv files with a predictable precedence (high -> low):
      1) .env.local (local overrides)
      2) fish_intel_mvp/.env (batch system config)
      3) .env (generic config)

    Notes:
      - We keep dotenv's default override=False so OS env vars always win.
      - To make .env.local override others without override=True, we load it first.
    """
    project_root = Path(__file__).resolve().parent
    candidates = [
        project_root / ".env.local",
        project_root / "fish_intel_mvp" / ".env",
        project_root / ".env",
    ]

    loaded_any = False
    for path in candidates:
        if path.exists():
            load_dotenv(dotenv_path=path)
            loaded_any = True

    if not loaded_any:
        # Fallback to python-dotenv's default search for ".env" in CWD/parents.
        load_dotenv()


_load_project_dotenv()


class Config:
    """项目配置类"""

    # ===== 存储后端 =====
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "mysql").strip().lower()

    # ===== 数据库配置 =====
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASS: str = os.getenv("DB_PASS", "")
    DB_NAME: str = os.getenv("DB_NAME", "fish_intel")

    # ===== 日志配置 =====
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # ===== CNKI 爬虫配置 =====
    CNKI_THEME: str = os.getenv("CNKI_THEME", "aquaculture")
    CNKI_PAPERS: int = int(os.getenv("CNKI_PAPERS", "10"))
    CNKI_MAX_PAGES: int = int(os.getenv("CNKI_MAX_PAGES", "5"))
    CNKI_LOGIN_WAIT_SECONDS: int = int(os.getenv("CNKI_LOGIN_WAIT_SECONDS", "20"))
    CNKI_RAW_HTML_MAX_CHARS: int = int(os.getenv("CNKI_RAW_HTML_MAX_CHARS", "150000"))
    CNKI_HEADLESS: bool = os.getenv("CNKI_HEADLESS", "0").strip() == "1"

    # ===== 浏览器驱动配置 =====
    EDGE_DRIVER_PATH: Optional[str] = os.getenv("EDGE_DRIVER_PATH", "").strip() or None
    CHROME_DRIVER_PATH: Optional[str] = os.getenv("CHROME_DRIVER_PATH", "").strip() or None

    # ===== JD 爬虫配置 =====
    JD_KEYWORDS: str = os.getenv("JD_KEYWORDS", "大黄鱼")
    JD_PAGES: int = int(os.getenv("JD_PAGES", "1"))
    JD_MAX_ITEMS_PER_PAGE: int = int(os.getenv("JD_MAX_ITEMS_PER_PAGE", "40"))

    # ===== MOA 爬虫配置 =====
    MOA_MAX_PAGES: int = int(os.getenv("MOA_MAX_PAGES", "1"))
    MOA_MAX_ITEMS: int = int(os.getenv("MOA_MAX_ITEMS", "200"))

    # ===== Taobao 配置 =====
    TAOBAO_COOKIE: Optional[str] = os.getenv("TAOBAO_COOKIE", "").strip() or None
    TAOBAO_KEYWORDS: str = os.getenv("TAOBAO_KEYWORDS", "")
    TAOBAO_PAGES: int = int(os.getenv("TAOBAO_PAGES", "1"))

    @classmethod
    def _is_sensitive_key(cls, key: str) -> bool:
        upper = key.upper()
        if upper in {"DB_PASS", "TAOBAO_COOKIE"}:
            return True
        return upper.endswith(("_PASS", "_PASSWORD", "_TOKEN", "_COOKIE", "_SECRET"))

    @classmethod
    def _redact_value(cls, value: Any) -> Any:
        if value in (None, ""):
            return value
        return "***REDACTED***"

    @classmethod
    def validate(cls) -> None:
        """验证关键配置"""
        if cls.STORAGE_BACKEND not in {"mysql", "sqlite"}:
            raise RuntimeError("STORAGE_BACKEND must be one of: mysql, sqlite")

        if cls.STORAGE_BACKEND == "mysql" and cls.DB_PASS == "change_me":
            raise RuntimeError(
                "DB_PASS is still 'change_me'. "
                "Please update fish_intel_mvp/.env with your real MySQL password."
            )

    @classmethod
    def to_dict(cls, *, redact: bool = True) -> dict:
        """导出所有配置为字典（默认脱敏敏感字段）"""
        keys = list(getattr(cls, "__annotations__", {}).keys())
        out: dict = {}
        for key in keys:
            value = getattr(cls, key)
            if redact and cls._is_sensitive_key(key):
                out[key] = cls._redact_value(value)
            else:
                out[key] = value
        return out


def get_config() -> Config:
    """获取配置实例"""
    return Config()
