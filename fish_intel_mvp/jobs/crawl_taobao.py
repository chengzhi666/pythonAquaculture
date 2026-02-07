import os

from common.logger import get_logger

LOGGER = get_logger(__name__)


def run(conn) -> int:
    cookie = os.getenv("TAOBAO_COOKIE", "").strip()
    if not cookie:
        LOGGER.warning("taobao skipped: TAOBAO_COOKIE is empty")
        return 0
    LOGGER.warning("taobao crawler is not implemented yet")
    return 0
