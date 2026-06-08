from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": (
        "DailyAINewsBot/1.0 "
        "(daily AI research and tech digest)"
    )
}

AI_KEYWORDS = [
    "ai",
    "artificial intelligence",
    "llm",
    "large language model",
    "agent",
    "rag",
    "retrieval",
    "multimodal",
    "diffusion",
    "transformer",
    "vision-language",
    "vla",
    "reasoning",
    "alignment",
    "inference",
    "benchmark",
]


@dataclass
class Paper:
    title: str
    link: str
    summary: str
    source: str
    published: str | None = None
    authors: list[str] | None = None


@dataclass
class Project:
    name: str
    link: str
    description: str
    stars: int | None = None
    language: str | None = None
    source: str = "GitHub"


@dataclass
class TechUpdate:
    title: str
    link: str
    summary: str
    source: str
    published: str | None = None


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


def _parse_stars(value: str) -> int | None:
    value = value.strip().lower().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)(k?)", value)
    if not match:
        return None
    number = float(match.group(1))
    if match.group(2) == "k":
        number *= 1000
    return int(number)


def _published_after_value(raw: str | None, days: int = 3) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    if not raw:
        return True
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= cutoff
    except (TypeError, ValueError):
        return True


def _parse_xml_feed(xml_text: str) -> list[dict[str, Any]]:
    namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    root = ET.fromstring(xml_text)
    entries: list[dict[str, Any]] = []

    if root.tag.endswith("feed"):
        for entry in root.findall("atom:entry", namespaces):
            link_node = entry.find("atom:link[@rel='alternate']", namespaces) or entry.find("atom:link", namespaces)
            authors = [
                _clean_text(author.findtext("atom:name", default="", namespaces=namespaces))
                for author in entry.findall("atom:author", namespaces)
            ]
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
                    "authors": [author for author in authors if author],
                }
            )
        return entries

    for item in root.findall(".//item"):
        entries.append(
            {
                "title": _clean_text(item.findtext("title", default="")),
                "link": item.findtext("link", default="").strip(),
                "summary": _clean_text(item.findtext("description", default="")),
                "published": item.findtext("pubDate", default="").strip(),
                "authors": [
                    _clean_text(item.findtext("dc:creator", default="", namespaces=namespaces))
                ],
            }
        )
    return entries


def fetch_arxiv(categories: list[str] | None = None, max_results: int = 20) -> list[Paper]:
    categories = categories or ["cs.AI", "cs.LG", "cs.CL", "cs.CV"]
    query = " OR ".join(f"cat:{category}" for category in categories)
    url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    entries = _parse_xml_feed(_get(url, params=params).text)
    papers: list[Paper] = []
    for entry in entries:
        papers.append(
            Paper(
                title=entry["title"],
                link=entry["link"],
                summary=entry["summary"],
                source="arXiv",
                published=entry["published"],
                authors=entry["authors"][:8],
            )
        )
    return papers


def fetch_github_trending(max_results: int = 10) -> list[Project]:
    projects: list[Project] = []
    try:
        soup = BeautifulSoup(_get("https://github.com/trending?since=daily").text, "html.parser")
    except requests.RequestException:
        return projects

    for article in soup.select("article.Box-row"):
        title_tag = article.select_one("h2 a")
        if not title_tag:
            continue
        repo_path = re.sub(r"\s+", "", title_tag.get_text("/")).strip("/")
        description = _clean_text(article.select_one("p").get_text(" ") if article.select_one("p") else "")
        language_tag = article.select_one("[itemprop='programmingLanguage']")
        stars_tag = article.select_one("a[href$='/stargazers']")
        project = Project(
            name=repo_path,
            link=f"https://github.com/{repo_path}",
            description=description,
            stars=_parse_stars(stars_tag.get_text(" ")) if stars_tag else None,
            language=_clean_text(language_tag.get_text(" ")) if language_tag else None,
        )
        if _matches_ai_keywords(project.name, project.description):
            projects.append(project)
    time.sleep(0.3)

    return _dedupe_projects(projects)[:max_results]


def fetch_github_search(max_results: int = 10) -> list[Project]:
    token = os.getenv("GITHUB_TOKEN")
    headers = {**DEFAULT_HEADERS}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    since = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    query = (
        "(LLM OR agent OR RAG OR multimodal OR artificial-intelligence) "
        f"created:>={since} stars:>20"
    )
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": max_results,
    }
    try:
        response = requests.get(
            "https://api.github.com/search/repositories",
            headers=headers,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException:
        return []

    projects: list[Project] = []
    for item in response.json().get("items", []):
        projects.append(
            Project(
                name=item["full_name"],
                link=item["html_url"],
                description=item.get("description") or "",
                stars=item.get("stargazers_count"),
                language=item.get("language"),
                source="GitHub Search",
            )
        )
    return projects


def fetch_papers_with_code(max_results: int = 10) -> list[Paper]:
    try:
        entries = _parse_xml_feed(_get("https://paperswithcode.com/rss").text)
    except (requests.RequestException, ET.ParseError):
        return []
    papers: list[Paper] = []
    for entry in entries:
        title = entry["title"]
        summary = entry["summary"]
        if _published_after_value(entry["published"], days=7) and _matches_ai_keywords(title, summary):
            papers.append(
                Paper(
                    title=title,
                    link=entry["link"],
                    summary=summary,
                    source="Papers with Code",
                    published=entry["published"],
                )
            )
    return papers[:max_results]


def fetch_hugging_face_papers(max_results: int = 10) -> list[Paper]:
    try:
        soup = BeautifulSoup(_get("https://huggingface.co/papers").text, "html.parser")
    except requests.RequestException:
        return []

    papers: list[Paper] = []
    for anchor in soup.select("a[href^='/papers/']"):
        title = _clean_text(anchor.get_text(" "))
        href = anchor.get("href", "")
        if not title or len(title) < 12:
            continue
        papers.append(
            Paper(
                title=title,
                link=f"https://huggingface.co{href}",
                summary="Hugging Face Papers 今日/近期热门论文条目。",
                source="Hugging Face Papers",
            )
        )
    return _dedupe_papers(papers)[:max_results]


def fetch_hugging_face_models(max_results: int = 10) -> list[TechUpdate]:
    try:
        response = _get(
            "https://huggingface.co/api/models",
            params={"sort": "trendingScore", "direction": -1, "limit": max_results},
        )
    except requests.RequestException:
        return []

    updates: list[TechUpdate] = []
    for item in response.json():
        tags = ", ".join(item.get("tags", [])[:8])
        updates.append(
            TechUpdate(
                title=item.get("modelId", "Unknown model"),
                link=f"https://huggingface.co/{item.get('modelId')}",
                summary=f"Trending model. Tags: {tags}".strip(),
                source="Hugging Face Models",
            )
        )
    return updates


def fetch_official_blogs(max_results: int = 12) -> list[TechUpdate]:
    feeds = {
        "OpenAI": "https://openai.com/news/rss.xml",
        "Google DeepMind": "https://deepmind.google/discover/blog/rss.xml",
        "Anthropic": "https://www.anthropic.com/news/rss.xml",
        "Meta AI": "https://ai.meta.com/blog/rss/",
    }
    updates: list[TechUpdate] = []
    for source, url in feeds.items():
        try:
            entries = _parse_xml_feed(_get(url).text)
        except (requests.RequestException, ET.ParseError):
            continue
        for entry in entries[:8]:
            title = entry["title"]
            summary = entry["summary"]
            if _published_after_value(entry["published"], days=14) and _matches_ai_keywords(title, summary, source):
                updates.append(
                    TechUpdate(
                        title=title,
                        link=entry["link"],
                        summary=summary[:600],
                        source=source,
                        published=entry["published"],
                    )
                )
    return updates[:max_results]


def _dedupe_papers(papers: list[Paper]) -> list[Paper]:
    seen: set[str] = set()
    result: list[Paper] = []
    for paper in papers:
        key = re.sub(r"\W+", "", paper.title.lower())[:100]
        if key and key not in seen:
            seen.add(key)
            result.append(paper)
    return result


def _dedupe_projects(projects: list[Project]) -> list[Project]:
    seen: set[str] = set()
    result: list[Project] = []
    for project in projects:
        key = project.link.lower().rstrip("/")
        if key not in seen:
            seen.add(key)
            result.append(project)
    return result


def collect_sources() -> dict[str, Any]:
    max_papers = int(os.getenv("MAX_PAPERS", "20"))
    max_projects = int(os.getenv("MAX_PROJECTS", "10"))

    def safe_fetch(fetcher: Any, *args: Any, **kwargs: Any) -> list[Any]:
        try:
            return fetcher(*args, **kwargs)
        except (requests.RequestException, ET.ParseError, ValueError) as exc:
            print(f"Warning: {fetcher.__name__} failed: {exc}")
            return []

    papers = []
    papers.extend(safe_fetch(fetch_arxiv, max_results=max_papers))
    papers.extend(safe_fetch(fetch_papers_with_code, max_results=10))
    papers.extend(safe_fetch(fetch_hugging_face_papers, max_results=10))

    projects = []
    projects.extend(safe_fetch(fetch_github_search, max_results=max_projects))
    projects.extend(safe_fetch(fetch_github_trending, max_results=max_projects))

    updates = []
    updates.extend(safe_fetch(fetch_hugging_face_models, max_results=8))
    updates.extend(safe_fetch(fetch_official_blogs, max_results=12))

    return {
        "papers": [asdict(paper) for paper in _dedupe_papers(papers)[: max_papers + 10]],
        "projects": [asdict(project) for project in _dedupe_projects(projects)[: max_projects + 10]],
        "updates": [asdict(update) for update in updates[:20]],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
