from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib import parse
from urllib import error as url_error
from urllib import request as url_request

try:
    from turtle_corpus import CorpusSource, chunk_text, estimate_embedding_tokens, normalize_text
except ModuleNotFoundError:  # pragma: no cover - package import path used by unittest
    from scripts.turtle_corpus import CorpusSource, chunk_text, estimate_embedding_tokens, normalize_text


WIKISOURCE_API = "https://zh.wikisource.org/w/api.php"
HISTORY_BOOKS = [
    "史記",
    "漢書",
    "後漢書",
    "三國志",
    "晉書",
    "宋書",
    "南齊書",
    "梁書",
    "陳書",
    "魏書",
    "北齊書",
    "周書",
    "隋書",
    "南史",
    "北史",
    "舊唐書",
    "新唐書",
    "舊五代史",
    "新五代史",
    "宋史",
    "遼史",
    "金史",
    "元史",
    "明史",
    "清史稿",
]


JsonFetcher = Callable[[dict[str, str]], dict[str, Any]]
TextFetcher = Callable[[str], str]


@dataclass(frozen=True)
class HistoryPage:
    book: str
    title: str
    volume: str


@dataclass(frozen=True)
class HistoryBatch:
    sources: list[CorpusSource]
    failures: list[dict[str, Any]]
    budget: dict[str, Any]


def mediawiki_json_fetcher(
    params: dict[str, str],
    api_url: str = WIKISOURCE_API,
    retries: int = 4,
    backoff_seconds: float = 3.0,
) -> dict[str, Any]:
    query = parse.urlencode(params)
    req = url_request.Request(
        f"{api_url}?{query}",
        headers={"User-Agent": "guess-figure-turtle-rag/1.0"},
    )
    for attempt in range(retries + 1):
        try:
            with url_request.urlopen(req, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except url_error.HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt >= retries:
                raise
            retry_after = error.headers.get("Retry-After")
            wait = float(retry_after) if retry_after and retry_after.isdigit() else backoff_seconds * (attempt + 1)
            time.sleep(wait)
    raise RuntimeError("MediaWiki API retry exhausted")


def discover_book_pages(
    book: str,
    fetch_json: JsonFetcher = mediawiki_json_fetcher,
    max_pages: int | None = None,
) -> list[HistoryPage]:
    pages: list[HistoryPage] = []
    params = {
        "action": "query",
        "format": "json",
        "list": "allpages",
        "apnamespace": "0",
        "apprefix": f"{book}/卷",
        "aplimit": "max",
    }
    while True:
        data = fetch_json(params)
        for item in data.get("query", {}).get("allpages", []):
            title = str(item.get("title", ""))
            if not title.startswith(f"{book}/"):
                continue
            pages.append(HistoryPage(book=book, title=title, volume=title.split("/", 1)[1]))
            if max_pages is not None and len(pages) >= max_pages:
                return pages
        cont = data.get("continue", {})
        if not cont or "apcontinue" not in cont:
            return pages
        params["apcontinue"] = str(cont["apcontinue"])


def discover_history_pages(
    books: list[str],
    fetch_json: JsonFetcher = mediawiki_json_fetcher,
    max_books: int | None = None,
    max_pages_per_book: int | None = None,
    sleep_seconds: float = 0.0,
) -> list[HistoryPage]:
    selected_books = books[:max_books] if max_books is not None else books
    pages: list[HistoryPage] = []
    for book in selected_books:
        pages.extend(discover_book_pages(book, fetch_json=fetch_json, max_pages=max_pages_per_book))
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
    return pages


def fetch_wikisource_text(title: str, fetch_json: JsonFetcher = mediawiki_json_fetcher) -> str:
    data = fetch_json(
        {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "explaintext": "1",
            "redirects": "1",
            "titles": title,
        }
    )
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        extract = page.get("extract")
        if isinstance(extract, str):
            return normalize_text(extract)
    return ""


def source_budget(text: str) -> dict[str, int]:
    chunks = chunk_text(text)
    return {
        "tokens": sum(estimate_embedding_tokens(chunk.text) for chunk in chunks),
        "vectors": len(chunks),
    }


def build_history_batch(
    pages: list[HistoryPage],
    fetch_text: TextFetcher,
    token_budget: int,
    vector_budget: int,
    resume_after: str | None = None,
) -> HistoryBatch:
    sources: list[CorpusSource] = []
    failures: list[dict[str, Any]] = []
    tokens_used = 0
    vectors_used = 0
    processed_pages = 0
    failed_pages = 0
    skipped_pages = 0
    budget_exhausted = False
    cursor_reached = resume_after is None
    next_resume_after = resume_after

    for page in pages:
        if not cursor_reached:
            cursor_reached = page.title == resume_after
            continue
        try:
            text = normalize_text(fetch_text(page.title))
            if not text:
                raise ValueError("页面正文为空")
            budget = source_budget(text)
            if (
                tokens_used + budget["tokens"] > token_budget
                or vectors_used + budget["vectors"] > vector_budget
            ):
                if (
                    tokens_used == 0
                    and vectors_used == 0
                    and token_budget > 0
                    and vector_budget > 0
                    and (budget["tokens"] > token_budget or budget["vectors"] > vector_budget)
                ):
                    failed_pages += 1
                    next_resume_after = page.title
                    failures.append(
                        {
                            "source_type": "wikisource",
                            "source_id": page.title,
                            "title": page.title,
                            "source_ref": page.title,
                            "source_url": f"https://zh.wikisource.org/wiki/{parse.quote(page.title)}",
                            "book": page.book,
                            "volume": page.volume,
                            "reason": "source_over_budget",
                            "error": (
                                f"单页预算超过本批限额：tokens={budget['tokens']}/{token_budget}, "
                                f"vectors={budget['vectors']}/{vector_budget}"
                            ),
                        }
                    )
                    continue
                budget_exhausted = True
                skipped_pages += 1
                break
            sources.append(
                CorpusSource(
                    source_type="wikisource",
                    source_id=page.title,
                    title=page.title,
                    text=text,
                    source_url=f"https://zh.wikisource.org/wiki/{parse.quote(page.title)}",
                    source_ref=page.title,
                    book=page.book,
                    volume=page.volume,
                )
            )
            tokens_used += budget["tokens"]
            vectors_used += budget["vectors"]
            processed_pages += 1
            next_resume_after = page.title
        except Exception as error:
            failed_pages += 1
            next_resume_after = page.title
            failures.append(
                {
                    "source_type": "wikisource",
                    "source_id": page.title,
                    "title": page.title,
                    "source_ref": page.title,
                    "source_url": f"https://zh.wikisource.org/wiki/{parse.quote(page.title)}",
                    "book": page.book,
                    "volume": page.volume,
                    "reason": "fetch_failed",
                    "error": str(error),
                }
            )

    budget = {
        "token_budget_limit": token_budget,
        "token_budget_used": tokens_used,
        "vector_budget_limit": vector_budget,
        "vector_budget_used": vectors_used,
        "processed_pages": processed_pages,
        "failed_pages": failed_pages,
        "skipped_pages": skipped_pages,
        "budget_exhausted": budget_exhausted,
        "resume_after": resume_after,
        "next_resume_after": next_resume_after,
    }
    return HistoryBatch(sources=sources, failures=failures, budget=budget)
