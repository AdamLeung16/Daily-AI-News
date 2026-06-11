from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus, urljoin
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": "DailyAINewsBot/1.0 (daily AI industry and technology digest)"
}

AI_KEYWORDS = [
    "ai",
    "artificial intelligence",
    "llm",
    "large language model",
    "agent",
    "rag",
    "multimodal",
    "reasoning",
    "model",
    "foundation model",
    "generative",
    "inference",
    "chip",
    "gpu",
    "robotics",
    "openai",
    "anthropic",
    "deepmind",
    "gemini",
    "claude",
    "chatgpt",
]


@dataclass
class NewsItem:
    title: str
    link: str
    summary: str
    source: str
    published: str | None = None
    category: str = "news"


def _get(url: str, *, params: dict[str, Any] | None = None, timeout: int = 20) -> requests.Response:
    response = requests.get(url, headers=DEFAULT_HEADERS, params=params, timeout=timeout)
    response.raise_for_status()
    return response


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", BeautifulSoup(value, "html.parser").get_text(" ")).strip()


def _matches_ai_keywords(*values: str) -> bool:
    text = " ".join(values).lower()
    return any(keyword in text for keyword in AI_KEYWORDS)


def _published_after_value(raw: str | None, days: int = 5) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    if not raw:
        return True
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= cutoff
    except (TypeError, ValueError):
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= cutoff
    except ValueError:
        pass
    return True


def _parse_xml_feed(xml_text: str) -> list[dict[str, str]]:
    namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "content": "http://purl.org/rss/1.0/modules/content/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    root = ET.fromstring(xml_text)
    entries: list[dict[str, str]] = []

    if root.tag.endswith("feed"):
        for entry in root.findall("atom:entry", namespaces):
            link_node = entry.find("atom:link[@rel='alternate']", namespaces) or entry.find("atom:link", namespaces)
            entries.append(
                {
                    "title": _clean_text(entry.findtext("atom:title", default="", namespaces=namespaces)),
                    "link": link_node.get("href", "") if link_node is not None else "",
                    "summary": _clean_text(
                        entry.findtext("atom:summary", default="", namespaces=namespaces)
                        or entry.findtext("atom:content", default="", namespaces=namespaces)
                    ),
                    "published": entry.findtext("atom:published", default="", namespaces=namespaces)
                    or entry.findtext("atom:updated", default="", namespaces=namespaces),
                }
            )
        return entries

    for item in root.findall(".//item"):
        entries.append(
            {
                "title": _clean_text(item.findtext("title", default="")),
                "link": item.findtext("link", default="").strip(),
                "summary": _clean_text(
                    item.findtext("description", default="")
                    or item.findtext("content:encoded", default="", namespaces=namespaces)
                ),
                "published": item.findtext("pubDate", default="").strip()
                or item.findtext("dc:date", default="", namespaces=namespaces).strip(),
            }
        )
    return entries


def _fetch_feed_items(
    source: str,
    url: str,
    *,
    category: str,
    max_results: int = 8,
    days: int = 5,
    keyword_filter: bool = True,
) -> list[NewsItem]:
    entries = _parse_xml_feed(_get(url).text)
    items: list[NewsItem] = []
    for entry in entries[: max_results * 3]:
        title = entry["title"]
        summary = entry["summary"]
        if not title or not entry["link"]:
            continue
        if not _published_after_value(entry["published"], days=days):
            continue
        if keyword_filter and not _matches_ai_keywords(title, summary, source):
            continue
        items.append(
            NewsItem(
                title=title,
                link=entry["link"],
                summary=summary[:900],
                source=source,
                published=entry["published"],
                category=category,
            )
        )
        if len(items) >= max_results:
            break
    return items


def fetch_company_updates(max_results: int = 24) -> list[NewsItem]:
    feeds = {
        "OpenAI": "https://openai.com/news/rss.xml",
        "Google AI": "https://blog.google/technology/ai/rss/",
        "NVIDIA AI": "https://blogs.nvidia.com/blog/category/deep-learning/feed/",
        "AWS Machine Learning": "https://aws.amazon.com/blogs/machine-learning/feed/",
    }
    pages = {
        "Google DeepMind": "https://deepmind.google/blog/",
        "Anthropic": "https://www.anthropic.com/news",
        "Meta AI": "https://ai.meta.com/blog/",
        "Microsoft AI": "https://news.microsoft.com/source/topics/ai/",
        "Apple Machine Learning": "https://machinelearning.apple.com/",
    }
    items: list[NewsItem] = []
    for source, url in feeds.items():
        try:
            items.extend(
                _fetch_feed_items(
                    source,
                    url,
                    category="company_update",
                    max_results=4,
                    days=10,
                    keyword_filter=False,
                )
            )
        except (requests.RequestException, ET.ParseError, ValueError) as exc:
            print(f"Warning: {source} feed failed: {exc}")
    for source, url in pages.items():
        try:
            items.extend(fetch_company_page(source, url, max_results=4))
        except requests.RequestException as exc:
            print(f"Warning: {source} page failed: {exc}")
    return _dedupe_items(items)[:max_results]


def fetch_company_page(source: str, url: str, max_results: int = 4) -> list[NewsItem]:
    soup = BeautifulSoup(_get(url).text, "html.parser")
    blocked_titles = {
        "research",
        "policy",
        "news",
        "blog",
        "products",
        "resources",
        "about",
        "careers",
        "privacy policy",
        "terms",
        "newsletter",
        "sign up",
        "learn more",
    }
    items: list[NewsItem] = []
    for anchor in soup.find_all("a", href=True):
        title = _clean_text(anchor.get_text(" "))
        normalized = title.lower().strip()
        if normalized in blocked_titles or len(title) < 18 or len(title) > 180:
            continue
        if title.lower().startswith(("image:", "tag:", "skip to ")):
            continue
        link = urljoin(url, anchor["href"])
        if not link.startswith(("http://", "https://")):
            continue
        items.append(
            NewsItem(
                title=title,
                link=link,
                summary=f"{source} 官方页面发布或展示的 AI 技术/产品动态。",
                source=source,
                category="company_update",
            )
        )
        if len(_dedupe_items(items)) >= max_results:
            break
    return _dedupe_items(items)[:max_results]


def fetch_hot_ai_news(max_results: int = 24) -> list[NewsItem]:
    query = quote_plus(
        '(AI OR "artificial intelligence" OR OpenAI OR Anthropic OR DeepMind OR Gemini OR ChatGPT OR Claude) when:3d'
    )
    feeds = {
        "Google News AI": f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en",
        "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
        "MIT Technology Review": "https://www.technologyreview.com/feed/",
    }
    items: list[NewsItem] = []
    for source, url in feeds.items():
        try:
            items.extend(
                _fetch_feed_items(
                    source,
                    url,
                    category="hot_news",
                    max_results=6,
                    days=4,
                    keyword_filter=True,
                )
            )
        except (requests.RequestException, ET.ParseError, ValueError) as exc:
            print(f"Warning: {source} feed failed: {exc}")
    return _dedupe_items(items)[:max_results]


def _dedupe_items(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    result: list[NewsItem] = []
    for item in items:
        key = item.link.lower().rstrip("/") or re.sub(r"\W+", "", item.title.lower())[:120]
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def collect_sources() -> dict[str, Any]:
    max_company_updates = int(os.getenv("MAX_COMPANY_UPDATES", "24"))
    max_hot_news = int(os.getenv("MAX_HOT_NEWS", "24"))

    def safe_fetch(fetcher: Any, *args: Any, **kwargs: Any) -> list[Any]:
        try:
            return fetcher(*args, **kwargs)
        except (requests.RequestException, ET.ParseError, ValueError) as exc:
            print(f"Warning: {fetcher.__name__} failed: {exc}")
            return []

    company_updates = safe_fetch(fetch_company_updates, max_results=max_company_updates)
    hot_news = safe_fetch(fetch_hot_ai_news, max_results=max_hot_news)

    return {
        "company_updates": [asdict(item) for item in company_updates],
        "hot_news": [asdict(item) for item in hot_news],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
