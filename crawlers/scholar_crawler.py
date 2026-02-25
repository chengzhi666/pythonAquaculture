import hashlib
import logging
import time
from typing import Any, Optional, Union

from crawlers.utils import DEFAULT_TIMEOUT, create_session

logger = logging.getLogger(__name__)

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

# 模块级共享 session（带 UA + 自动重试）
_session = create_session()


def _fallback_url(query: str, title: str) -> str:
    # Ensure source_url is never empty for deduplication.
    key = f"{query}||{title}".encode("utf-8", errors="ignore")
    h = hashlib.sha1(key).hexdigest()
    return f"semanticscholar:paper:{h}"


def crawl_scholar(
    query: str,
    limit: int = 20,
    year_from: Optional[int] = None,
    min_interval: float = 0.6,
) -> list[dict[str, Any]]:
    """
    Academic search source via Semantic Scholar API.
    Returns list[dict] aligned with intel_item fields:
      title/content/pub_time/region/org/source_type/source_url/extra(optional)
    """
    limit = max(1, min(int(limit), 100))
    params: dict[str, Union[str, int]] = {
        "query": query,
        "limit": limit,
        "fields": "title,abstract,year,authors,url,venue,citationCount,publicationDate,externalIds",
    }

    r = _session.get(API_URL, params=params, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    data = r.json()

    out: list[dict[str, Any]] = []
    for p in data.get("data", []) or []:
        title = (p.get("title") or "").strip()
        if not title:
            continue

        year = p.get("year")
        if year_from and year and int(year) < int(year_from):
            continue

        pub_time = (p.get("publicationDate") or "").strip()
        if not pub_time and year:
            pub_time = f"{year}-01-01"

        url = (p.get("url") or "").strip()
        source_url = url or _fallback_url(query, title)

        abstract = (p.get("abstract") or "").strip()
        content = abstract if abstract else title

        out.append(
            {
                "title": title,
                "content": content,
                "pub_time": pub_time,
                "region": "全球",
                "org": "Semantic Scholar",
                "source_type": "SCHOLAR",
                "source_url": source_url,
                "tags": [],
                "extra": {
                    "query": query,
                    "year": year,
                    "venue": p.get("venue"),
                    "citationCount": p.get("citationCount"),
                    "authors": [a.get("name") for a in (p.get("authors") or []) if a.get("name")],
                    "paper_url": url,
                    "externalIds": p.get("externalIds") or {},
                },
            }
        )

        time.sleep(min_interval)

    return out
