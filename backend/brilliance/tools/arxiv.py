# arxiv_tool.py
import httpx
import feedparser
from typing import List, Any
from urllib.parse import quote_plus

def _safe_get_text(entry: Any, attr: str, default: str = "") -> str:
    """Safely get text attribute from feedparser entry."""
    if not hasattr(entry, attr):
        return default
    value = getattr(entry, attr)
    return str(value).strip() if value is not None else default

def _safe_get_authors(entry: Any) -> str:
    """Safely extract authors from feedparser entry."""
    authors = getattr(entry, 'authors', [])
    if not isinstance(authors, list):
        return "N/A"
    
    author_names = []
    for author in authors:
        if hasattr(author, 'name'):
            name = str(author.name).strip()
            if name:
                author_names.append(name)
    
    return ", ".join(author_names) if author_names else "N/A"

def _build_search_query(query: str) -> str:
    """Build an optimized arXiv search query."""
    # If query already contains field specifiers (ti:, au:, abs:, cat:), use as-is
    if any(field in query.lower() for field in ['ti:', 'au:', 'abs:', 'cat:', 'all:']):
        return query
    
    # For natural language queries, use 'all:' which searches all fields
    # This is more reliable than complex field-specific queries
    return f"all:{query}"

def _fetch(q: str, max_results: int = 3) -> str:
    """
    Fetch from arXiv. Accepts either a full API URL or a natural-language/fielded query.
    Adds polite pagination when ARXIV_MIN_YEAR is set so we can still return up to max_results
    after client-side year filtering. Extracts PDF links when present.
    """
    import os
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

    def _build_url(query_or_url: str, start: int, page_size: int) -> str:
        # If a full URL was provided, patch its start/max_results; otherwise build from query.
        if isinstance(query_or_url, str) and query_or_url.startswith("http"):
            parsed = urlparse(query_or_url)
            qs = parse_qs(parsed.query, keep_blank_values=True)
            qs["start"] = [str(start)]
            qs["max_results"] = [str(page_size)]
            # Ensure sort parameters are present for recency
            qs.setdefault("sortBy", ["submittedDate"])
            qs.setdefault("sortOrder", ["descending"])
            new_q = urlencode(qs, doseq=True)
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_q, parsed.fragment))
        else:
            search_query = _build_search_query(query_or_url)
            base_url = "https://export.arxiv.org/api/query"
            params = {
                "search_query": search_query,
                "start": start,
                "max_results": page_size,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
            return f"{base_url}?" + "&".join([f"{k}={quote_plus(str(v))}" for k, v in params.items()])

    def _pdf_link(entry: Any) -> str:
        try:
            for link in getattr(entry, "links", []):
                if getattr(link, "type", "") == "application/pdf":
                    href = getattr(link, "href", "")
                    if href:
                        return str(href).strip()
        except Exception:
            pass
        # Fallback: some feeds include entry.id that can be transformed into a pdf URL
        try:
            arx_id = _safe_get_text(entry, "id", "")
            if arx_id and "/abs/" in arx_id:
                return arx_id.replace("/abs/", "/pdf/") + ".pdf"
        except Exception:
            pass
        return ""

    # Config / headers
    headers = {"User-Agent": os.getenv("HTTP_USER_AGENT", "Brilliance/1.0 (+contact@brilliance)")}
    min_year = 0
    try:
        min_year = int(os.getenv("ARXIV_MIN_YEAR", "0"))
    except Exception:
        min_year = 0

    collected_parts: List[str] = []
    start = 0
    # Page size: request a bit more than needed to improve chances after filtering
    page_size = max(10, min(50, max_results * 2))
    max_pages = 5  # hard cap to remain polite

    pages_tried = 0
    last_batch_empty = False

    while len(collected_parts) < max_results and pages_tried < max_pages and not last_batch_empty:
        url = _build_url(q, start, page_size)
        try:
            for attempt in range(3):
                try:
                    resp = httpx.get(url, headers=headers, timeout=httpx.Timeout(10.0, connect=5.0))
                    resp.raise_for_status()
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    import time, random
                    time.sleep((2 ** attempt) + random.random())
            feed = feedparser.parse(resp.text)
            if hasattr(feed, "feed") and hasattr(feed.feed, "title"):
                if "error" in str(feed.feed.title).lower():
                    return f"arXiv API Error: {feed.feed.title}"
            entries = getattr(feed, "entries", [])
        except Exception as e:
            return f"Error fetching from arXiv: {str(e)}"

        if not entries:
            last_batch_empty = True
            break

        # Collect, applying optional year filter
        for entry in entries:
            try:
                title = _safe_get_text(entry, "title", "No title")
                published = _safe_get_text(entry, "published", "")
                year = published[:4] if len(published) >= 4 else "N/A"
                authors_str = _safe_get_authors(entry)
                summary = _safe_get_text(entry, "summary", "No abstract")
                link = _safe_get_text(entry, "link", "")
                pdf = _pdf_link(entry)

                if min_year:
                    try:
                        if year != "N/A" and int(year) < min_year:
                            continue
                    except Exception:
                        # If year can't be parsed, keep it
                        pass

                part = f"{title} ({year}) by {authors_str}\nAbstract: {summary}\nURL: {link}"
                if pdf:
                    part += f"\nPDF: {pdf}"
                collected_parts.append(part)

                if len(collected_parts) >= max_results:
                    break
            except Exception:
                continue

        pages_tried += 1
        start += page_size

    if not collected_parts:
        return "No papers found."

    # Trim to requested count
    return "\n\n".join(collected_parts[:max_results])

def search_arxiv(query: str, max_results: int = 3) -> str:
    """Search arXiv for papers matching the query."""
    return _fetch(query, max_results)
