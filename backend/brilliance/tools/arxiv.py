# arxiv_tool.py
import httpx
import feedparser
from typing import List, Any

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

def _fetch(q: str, max_results: int = 3) -> str:
    url = (
        "https://export.arxiv.org/api/query?"
        f"search_query=all:{q}&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    )
    
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        
        if not hasattr(feed, 'entries'):
            return "No papers found."
            
        entries = feed.entries[:max_results]
    except Exception as e:
        return f"Error fetching from arXiv: {str(e)}"

    if not entries:
        return "No papers found."

    parts: List[str] = []
    for entry in entries:
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
            
            parts.append(f"{title} ({year}) by {authors_str}\nAbstract: {summary}\nURL: {link}")
            
        except Exception:
            # Skip malformed entries but continue processing others
            continue

    return "\n\n".join(parts) if parts else "No papers found."

def search_arxiv(query: str, max_results: int = 3) -> str:
    """Search arXiv for papers matching the query."""
    return _fetch(query, max_results)
