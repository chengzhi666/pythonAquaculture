import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

from DrissionPage import ChromiumOptions, ChromiumPage

try:
    from common.logger import get_logger
except ModuleNotFoundError:
    # Support direct execution: python fish_intel_mvp/jobs/refresh_taobao_cookie.py
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from common.logger import get_logger

LOGGER = get_logger(__name__)

DEFAULT_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
DEFAULT_START_URL = "https://login.taobao.com/member/login.jhtml"

TAOBAO_COOKIE_REQUIRED_KEYS = ("_m_h5_tk", "_m_h5_tk_enc")
TAOBAO_COOKIE_PRIORITY = (
    "_m_h5_tk",
    "_m_h5_tk_enc",
    "cookie2",
    "t",
    "_tb_token_",
    "cna",
)


def _is_true(value: str) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_taobao_url(url: str) -> bool:
    text = (url or "").strip().lower()
    return "taobao.com" in text or "tmall.com" in text


def _build_browser() -> ChromiumPage:
    use_system_profile = _is_true(os.getenv("TAOBAO_COOKIE_REFRESH_USE_SYSTEM_PROFILE", "1"))
    user_data_path = os.getenv("TAOBAO_COOKIE_REFRESH_USER_DATA_PATH", "").strip()
    profile_name = os.getenv("TAOBAO_COOKIE_REFRESH_PROFILE", "").strip()
    enable_stealth = _is_true(os.getenv("TAOBAO_COOKIE_REFRESH_STEALTH", "0"))
    no_proxy = _is_true(os.getenv("TAOBAO_COOKIE_REFRESH_NO_PROXY", "0"))
    headless = _is_true(os.getenv("TAOBAO_COOKIE_REFRESH_HEADLESS", "0"))

    def _new_options(use_system: bool) -> ChromiumOptions:
        opts = ChromiumOptions()
        opts.auto_port(True)
        if use_system:
            opts.use_system_user_path(True)
        if user_data_path:
            opts.set_user_data_path(user_data_path)
        if profile_name:
            opts.set_user(profile_name)
        if enable_stealth:
            opts.set_argument("--disable-blink-features=AutomationControlled")
        if no_proxy:
            opts.set_argument("--no-proxy-server")
        opts.set_argument("--disable-gpu")
        if headless:
            opts.headless(True)
        return opts

    attempts = [("primary", use_system_profile), ("fallback_no_system_profile", False)]
    seen = set()
    last_exc: Optional[Exception] = None

    for label, use_system in attempts:
        if use_system in seen:
            continue
        seen.add(use_system)
        try:
            return ChromiumPage(_new_options(use_system))
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            LOGGER.warning("build browser failed (%s): %s", label, exc)

    raise RuntimeError(f"cannot start chromium for taobao cookie refresh: {last_exc}")


def _navigate_to_start_url(page: ChromiumPage, url: str) -> None:
    ok = False
    try:
        ok = bool(page.get(url, retry=1, timeout=25))
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("initial page.get failed: %s", exc)

    current_url = str(getattr(page, "url", "") or "")
    if ok and _is_taobao_url(current_url):
        LOGGER.info("opened url=%s", current_url)
        return

    LOGGER.warning(
        "initial navigation not ready (ok=%s current=%s), trying new-tab fallback",
        ok,
        current_url,
    )
    try:
        page.new_tab(url=url, background=False)
        time.sleep(1.0)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("new_tab fallback failed: %s", exc)

    current_url = str(getattr(page, "url", "") or "")
    if _is_taobao_url(current_url):
        LOGGER.info("opened url=%s", current_url)
        return

    LOGGER.warning("fallback still not on taobao, trying js redirect")
    try:
        page.run_js(f"window.location.href = '{url}'")
        time.sleep(1.0)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("js redirect failed: %s", exc)

    LOGGER.info("current page url=%s", str(getattr(page, "url", "") or ""))


def _cookie_items_from_page(page: ChromiumPage) -> list[dict]:
    raw = page.cookies(all_domains=True, all_info=False) or []
    rows: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "").strip()
        domain = str(item.get("domain") or "").strip().lower()
        if not name or not value:
            continue
        if "taobao.com" not in domain and "tmall.com" not in domain:
            continue
        rows.append({"name": name, "value": value, "domain": domain})
    return rows


def _cookie_map(rows: list[dict]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for row in rows:
        merged[row["name"]] = row["value"]
    return merged


def _build_cookie_string(cookie_map: dict[str, str]) -> str:
    keys: list[str] = []
    seen = set()

    for name in TAOBAO_COOKIE_PRIORITY:
        if name in cookie_map and name not in seen:
            keys.append(name)
            seen.add(name)

    for name in sorted(cookie_map):
        if name in seen:
            continue
        keys.append(name)
        seen.add(name)

    return "; ".join(f"{name}={cookie_map[name]}" for name in keys)


def _has_required_cookie(cookie_map: dict[str, str]) -> bool:
    for key in TAOBAO_COOKIE_REQUIRED_KEYS:
        if not cookie_map.get(key):
            return False
    return True


def _quote_env_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _upsert_env_key(path: Path, key: str, value: str) -> None:
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    assign_re = re.compile(rf"^\s*{re.escape(key)}\s*=")
    new_line = f"{key}={_quote_env_value(value)}"

    found = False
    out: list[str] = []
    for line in lines:
        if assign_re.match(line):
            out.append(new_line)
            found = True
        else:
            out.append(line)

    if not found:
        if out and out[-1].strip():
            out.append("")
        out.append(new_line)

    text = "\n".join(out).rstrip() + "\n"
    path.write_text(text, encoding="utf-8")


def refresh_taobao_cookie(
    *,
    env_path: Optional[str] = None,
    timeout_seconds: int = 180,
    poll_interval: float = 1.0,
    start_url: Optional[str] = None,
) -> str:
    env_file = Path(env_path) if env_path else DEFAULT_ENV_PATH
    timeout_seconds = max(10, int(timeout_seconds))
    poll_interval = max(0.2, float(poll_interval))
    url = start_url or DEFAULT_START_URL

    page = _build_browser()
    try:
        _navigate_to_start_url(page, url)
        LOGGER.info(
            "taobao cookie refresh started. Please login in opened browser within %ss.",
            timeout_seconds,
        )

        deadline = time.time() + timeout_seconds
        next_log_at = 0.0

        while time.time() < deadline:
            rows = _cookie_items_from_page(page)
            cookie_map = _cookie_map(rows)
            if _has_required_cookie(cookie_map):
                cookie = _build_cookie_string(cookie_map)
                _upsert_env_key(env_file, "TAOBAO_COOKIE", cookie)
                os.environ["TAOBAO_COOKIE"] = cookie
                LOGGER.info("taobao cookie refreshed and saved to %s", env_file)
                return cookie

            now = time.time()
            if now >= next_log_at:
                LOGGER.info(
                    "waiting login... found keys=%s",
                    ",".join(sorted(cookie_map.keys())[:8]),
                )
                next_log_at = now + 15

            time.sleep(poll_interval)

        raise TimeoutError(
            f"taobao cookie refresh timeout after {timeout_seconds}s; "
            "please ensure login is completed in browser."
        )
    finally:
        try:
            page.quit()
        except Exception:
            pass


if __name__ == "__main__":
    cookie = refresh_taobao_cookie(
        timeout_seconds=int(os.getenv("TAOBAO_COOKIE_REFRESH_TIMEOUT_SECONDS", "180")),
        poll_interval=float(os.getenv("TAOBAO_COOKIE_REFRESH_POLL_SECONDS", "1.0")),
    )
    print(f"[OK] taobao cookie refreshed, length={len(cookie)}")
