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
    # Allow passing a full arXiv API URL; otherwise build an optimized query
    if isinstance(q, str) and q.startswith("http"):
        url = q
    else:
        search_query = _build_search_query(q)
        # Build URL with proper parameter encoding
        base_url = "https://export.arxiv.org/api/query"
        params = {
            'search_query': search_query,
            'max_results': max_results,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending'
        }
        # Let httpx handle URL encoding properly
        url = f"{base_url}?" + "&".join([f"{k}={quote_plus(str(v))}" for k, v in params.items()])
    
    try:
        import os
        headers = {"User-Agent": os.getenv("HTTP_USER_AGENT", "Brilliance/1.0 (+contact@brilliance)")}
        
        for attempt in range(3):
            try:
                resp = httpx.get(url, headers=headers, timeout=httpx.Timeout(10.0, connect=5.0))
                resp.raise_for_status()
                break
            except Exception as e:
                if attempt == 2:
                    raise
                import time, random
                time.sleep((2 ** attempt) + random.random())
        
        feed = feedparser.parse(resp.text)
        
        # Check for arXiv API errors in the feed
        if hasattr(feed, 'feed') and hasattr(feed.feed, 'title'):
            if 'error' in feed.feed.title.lower():
                return f"arXiv API Error: {feed.feed.title}"
        
        if not hasattr(feed, 'entries'):
            return "No papers found."
            
        entries = feed.entries
            
    except Exception as e:
        return f"Error fetching from arXiv: {str(e)}"

    if not entries:
        return "No papers found."

    parts: List[str] = []
    # Optional post-filter by min year
    import os
    try:
        min_year = int(os.getenv("ARXIV_MIN_YEAR", "0"))
    except Exception:
        min_year = 0

    for entry in entries[:max_results*2]:  # read a bit more, then filter down
        try:
            # Safely extract all fields
            title = _safe_get_text(entry, 'title', 'No title')
            
            # Handle year safely
            published = _safe_get_text(entry, 'published', '')
            year = published[:4] if len(published) >= 4 else "N/A"
            
            # Handle authors safely
            authors_str = _safe_get_authors(entry)
            
            # Handle abstract safely
            summary = _safe_get_text(entry, 'summary', 'No abstract')
            
            # Handle URL safely
            link = _safe_get_text(entry, 'link', '')
            
            # Apply year filter if set
            if min_year:
                try:
                    if year != "N/A" and int(year) < min_year:
                        continue
                except Exception:
                    pass

            parts.append(f"{title} ({year}) by {authors_str}\nAbstract: {summary}\nURL: {link}")
            
        except Exception:
            # Skip malformed entries but continue processing others
            continue

    # Trim to desired max_results after filtering
    parts = parts[:max_results]
    return "\n\n".join(parts) if parts else "No papers found."

def search_arxiv(query: str, max_results: int = 3) -> str:
    """Search arXiv for papers matching the query."""
    return _fetch(query, max_results)
