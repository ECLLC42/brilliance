# arxiv_tool.py
import httpx
import feedparser
from typing import List, Any, Optional
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

def _extract_phrases_and_terms(query: str) -> tuple[list[str], list[str]]:
    """Extract quoted phrases and informative terms from a natural language query."""
    import re
    text = (query or "").strip()
    if not text:
        return [], []

    # Extract quoted phrases
    phrases = [p.strip() for p in re.findall(r'"([^"]+)"', text) if p.strip()]

    # Remove quoted phrases from text to avoid duplication
    text_wo_quotes = re.sub(r'"[^"]+"', ' ', text)

    # Tokenize and filter stopwords/short tokens
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-_.+]{1,}", text_wo_quotes.lower())
    stop = set([
        'the','a','an','and','or','for','with','of','in','on','to','by','from','at','as','is','are','be','being',
        'into','that','this','these','those','using','use','based','about','what','which','when','how','why','can',
        'state','art','state-of-the-art','sota','towards','toward','new','novel','recent','improved','improving',
        'long','context','memory','paper','study','approach','method','methods','framework','system','systems'
    ])
    terms: list[str] = []
    for t in tokens:
        if t in stop:
            continue
        if len(t) <= 2:
            continue
        terms.append(t)

    return phrases, terms


def _guess_categories(terms: list[str]) -> list[str]:
    """Guess arXiv subject categories from terms (very lightweight heuristic)."""
    lowered = " ".join(terms)
    cats: list[str] = []
    if any(k in lowered for k in ["transformer","bert","gpt","llm","rag","retrieval","nlp","language","token"]):
        cats += ["cs.CL", "cs.LG", "cs.AI"]
    if any(k in lowered for k in ["graph","gnn","message passing","graph neural"]):
        cats += ["cs.LG", "cs.AI"]
    # Deduplicate while preserving order
    seen = set()
    uniq: list[str] = []
    for c in cats:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


def _build_fielded_query_from_nl(query: str) -> Optional[str]:
    """Build a fielded arXiv query from a natural-language question. Returns None if not enough signal."""
    phrases, terms = _extract_phrases_and_terms(query)
    if not phrases and not terms:
        return None

    must_groups: list[str] = []
    optional_groups: list[str] = []

    # Require up to two phrases as anchors
    for p in phrases[:2]:
        # Escape quotes inside phrase (rare)
        safe_p = p.replace('"', '\\"')
        must_groups.append(f'(ti:"{safe_p}" OR abs:"{safe_p}")')

    # Use up to four informative terms as optional signals
    if terms:
        head = terms[:4]
        scoped = [f'ti:"{w}"' for w in head] + [f'abs:"{w}"' for w in head]
        optional_groups.append("(" + " OR ".join(scoped) + ")")

    # Add guessed categories as optional
    cats = _guess_categories(terms + [p.lower() for p in phrases])
    if cats:
        optional_groups.append("(" + " OR ".join(f"cat:{c}" for c in cats) + ")")

    if must_groups:
        if optional_groups:
            return " AND ".join(must_groups + ["(" + " OR ".join(optional_groups) + ")"])
        return " AND ".join(must_groups)
    # Only optional groups
    if optional_groups:
        return "(" + " OR ".join(optional_groups) + ")"
    return None


def _build_search_query(query: str) -> str:
    """Build an optimized arXiv search query string (without URL)."""
    # If query already contains field specifiers (ti:, au:, abs:, cat:, all:), use as-is
    if any(field in query.lower() for field in ['ti:', 'au:', 'abs:', 'cat:', 'all:']):
        return query

    # Try a fielded query synthesized from natural language. Fallback to all:
    fielded = _build_fielded_query_from_nl(query)
    if fielded:
        return fielded
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
                # Prefer relevance if using fielded ti:/abs:/cat:, else recency for all:
                "sortBy": ("relevance" if any(k in search_query for k in ["ti:", "abs:", "cat:"]) else "submittedDate"),
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

    # Build attempt list: primary (possibly fielded) then fallback to broad all:
    attempts: List[str]
    if isinstance(q, str) and not q.startswith("http"):
        primary = _build_search_query(q)
        fallback = f"all:{q}"
        attempts = [primary]
        if fallback != primary:
            attempts.append(fallback)
    else:
        attempts = [q]

    attempt_index = 0
    while len(collected_parts) < max_results and pages_tried < max_pages and not last_batch_empty:
        url = _build_url(attempts[attempt_index], start, page_size)
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
            # If first page of this attempt is empty and we have a fallback, switch attempts once
            if start == 0 and attempt_index == 0 and len(attempts) > 1:
                try:
                    import logging
                    logging.getLogger(__name__).info(
                        "arxiv: primary attempt yielded 0 entries; switching to fallback",
                    )
                except Exception:
                    pass
                attempt_index = 1
                # reset paging for fallback attempt
                pages_tried = 0
                last_batch_empty = False
                continue
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
