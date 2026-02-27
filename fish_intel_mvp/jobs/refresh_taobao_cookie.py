import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

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


def _resolve_chrome_path() -> str:
    env_path = os.getenv("TAOBAO_COOKIE_REFRESH_CHROME_PATH", "").strip()
    if env_path:
        return env_path

    candidates = [
        str((Path(__file__).resolve().parents[2] / ".chrome-for-testing" / "chrome-win64" / "chrome.exe")),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def _build_browser() -> ChromiumPage:
    use_system_profile = _is_true(os.getenv("TAOBAO_COOKIE_REFRESH_USE_SYSTEM_PROFILE", "0"))
    user_data_path = os.getenv("TAOBAO_COOKIE_REFRESH_USER_DATA_PATH", "").strip()
    profile_name = os.getenv("TAOBAO_COOKIE_REFRESH_PROFILE", "").strip()
    enable_stealth = _is_true(os.getenv("TAOBAO_COOKIE_REFRESH_STEALTH", "0"))
    no_proxy = _is_true(os.getenv("TAOBAO_COOKIE_REFRESH_NO_PROXY", "0"))
    headless = _is_true(os.getenv("TAOBAO_COOKIE_REFRESH_HEADLESS", "0"))
    chrome_path = _resolve_chrome_path()

    def _new_options(use_system: bool) -> ChromiumOptions:
        opts = ChromiumOptions()
        opts.auto_port(True)
        if chrome_path and os.path.exists(chrome_path):
            opts.set_browser_path(chrome_path)
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

    attempts = [
        ("primary", use_system_profile),
        ("fallback_toggle_system_profile", not use_system_profile),
    ]
    seen = set()
    last_exc: Optional[Exception] = None

    for label, use_system in attempts:
        if use_system in seen:
            continue
        seen.add(use_system)
        try:
            LOGGER.info(
                "taobao cookie browser opts: backend=drission label=%s use_system_profile=%s headless=%s chrome_path=%s",
                label,
                use_system,
                headless,
                chrome_path or "<default>",
            )
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


def _playwright_goto(page, url: str, timeout_ms: int = 25000, retries: int = 3) -> None:
    for i in range(1, retries + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            return
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "interrupted by another navigation" in msg:
                LOGGER.warning(
                    "playwright goto interrupted: attempt=%s/%s target=%s current=%s",
                    i,
                    retries,
                    url,
                    page.url,
                )
                page.wait_for_timeout(1200)
                if _is_taobao_url(page.url or ""):
                    return
            if i >= retries:
                raise
            page.wait_for_timeout(1200)


def _build_playwright_browser():
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("playwright is not installed. run: pip install playwright") from exc

    headless = _is_true(os.getenv("TAOBAO_COOKIE_REFRESH_HEADLESS", "0"))
    no_proxy = _is_true(os.getenv("TAOBAO_COOKIE_REFRESH_NO_PROXY", "0"))
    chrome_path = _resolve_chrome_path()

    launch_args = [
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if no_proxy:
        launch_args.append("--no-proxy-server")

    launch_kwargs: dict[str, Any] = {"headless": headless, "args": launch_args}
    if chrome_path and os.path.exists(chrome_path):
        launch_kwargs["executable_path"] = chrome_path

    LOGGER.info(
        "taobao cookie browser opts: backend=playwright headless=%s chrome_path=%s",
        headless,
        chrome_path or "<default>",
    )

    pw = sync_playwright().start()
    browser = pw.chromium.launch(**launch_kwargs)
    context = browser.new_context()
    page = context.new_page()
    return pw, browser, context, page


def _navigate_to_start_url_playwright(page, url: str) -> None:
    ok = False
    try:
        _playwright_goto(page, url, timeout_ms=25000, retries=2)
        ok = True
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("initial page.goto failed: %s", exc)

    current_url = str(page.url or "")
    if ok and _is_taobao_url(current_url):
        LOGGER.info("opened url=%s", current_url)
        return

    LOGGER.warning(
        "initial navigation not ready (ok=%s current=%s), trying js redirect",
        ok,
        current_url,
    )
    try:
        page.evaluate(f"window.location.href = {json.dumps(url, ensure_ascii=False)}")
        page.wait_for_timeout(1000)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("js redirect failed: %s", exc)

    LOGGER.info("current page url=%s", str(page.url or ""))


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


def _cookie_items_from_playwright(page) -> list[dict]:
    raw = page.context.cookies() or []
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
    backend = os.getenv("TAOBAO_COOKIE_REFRESH_BACKEND", "auto").strip().lower()
    if backend not in {"auto", "drission", "playwright"}:
        LOGGER.warning("unknown TAOBAO_COOKIE_REFRESH_BACKEND=%s, fallback to auto", backend)
        backend = "auto"

    page: Any = None
    close_browser_fn: Callable[[], None]
    rows_from_page_fn: Callable[[Any], list[dict]]
    navigate_fn: Callable[[Any, str], None]
    active_backend = ""

    if backend in {"auto", "drission"}:
        try:
            page = _build_browser()
            rows_from_page_fn = _cookie_items_from_page
            navigate_fn = _navigate_to_start_url
            active_backend = "drission"

            def _close_drission() -> None:
                try:
                    page.quit()
                except Exception:
                    pass

            close_browser_fn = _close_drission
        except Exception as exc:
            if backend == "drission":
                raise
            LOGGER.warning("drission browser init failed, fallback to playwright: %s", exc)

    if page is None:
        pw, browser, context, page = _build_playwright_browser()
        rows_from_page_fn = _cookie_items_from_playwright
        navigate_fn = _navigate_to_start_url_playwright
        active_backend = "playwright"

        def _close_playwright() -> None:
            for obj, method in ((context, "close"), (browser, "close"), (pw, "stop")):
                try:
                    getattr(obj, method)()
                except Exception:
                    pass

        close_browser_fn = _close_playwright

    LOGGER.info("taobao cookie refresh backend in use: %s", active_backend)
    try:
        navigate_fn(page, url)
        LOGGER.info(
            "taobao cookie refresh started. Please login in opened browser within %ss.",
            timeout_seconds,
        )

        deadline = time.time() + timeout_seconds
        next_log_at = 0.0

        while time.time() < deadline:
            rows = rows_from_page_fn(page)
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
        close_browser_fn()


if __name__ == "__main__":
    cookie = refresh_taobao_cookie(
        timeout_seconds=int(os.getenv("TAOBAO_COOKIE_REFRESH_TIMEOUT_SECONDS", "180")),
        poll_interval=float(os.getenv("TAOBAO_COOKIE_REFRESH_POLL_SECONDS", "1.0")),
    )
    print(f"[OK] taobao cookie refreshed, length={len(cookie)}")
