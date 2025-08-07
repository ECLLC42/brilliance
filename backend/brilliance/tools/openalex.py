# openalex_tool.py
"""Tool for retrieving recent OpenAlex works (papers) relevant to a query.
Returns a concise string with Title (Year), Authors, Abstract and URL for each hit.
"""
from __future__ import annotations

import httpx
from urllib.parse import quote_plus
from typing import List, Any, Dict


def _safe_get(obj: Dict[str, Any], key: str, default: str = "") -> str:
    """Safely get string value from dict, handling None values."""
    value = obj.get(key, default)
    return str(value) if value is not None else str(default)


def _safe_get_nested(obj: Dict[str, Any], path: List[str], default: str = "") -> str:
    """Safely get nested value from dict using path of keys."""
    current = obj
    for key in path:
        if not isinstance(current, dict):
            return str(default)
        current = current.get(key)
        if current is None:
            return str(default)
    return str(current) if current is not None else str(default)


def _fetch(query: str, max_results: int = 3) -> str:
    url = (
        "https://api.openalex.org/works?"
        f"search={quote_plus(query)}&per_page={max_results}&sort=publication_year:desc"
    )
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()  # Raise exception for bad status codes
        data = resp.json()
    except Exception as e:
        return f"Error fetching from OpenAlex: {str(e)}"

    results = data.get("results", [])
    if not isinstance(results, list) or not results:
        return "No papers found."

    parts: List[str] = []
    for work in results[:max_results]:
        if not isinstance(work, dict):
            continue
            
        # Safely extract all fields with defensive programming
        title = _safe_get(work, "display_name", "No title").strip()
        year = _safe_get(work, "publication_year", "N/A")
        
        # Handle authors safely
        authorships = work.get("authorships", [])
        authors: List[str] = []
        if isinstance(authorships, list):
            for auth in authorships:
                if isinstance(auth, dict):
                    author_data = auth.get("author", {})
                    if isinstance(author_data, dict):
                        author_name = _safe_get(author_data, "display_name")
                        if author_name and author_name.strip():
                            authors.append(author_name.strip())
        authors_str = ", ".join(authors) if authors else "N/A"
        
        # Handle abstract safely
        abstract = work.get("abstract_inverted_index")
        abstract_text = "No abstract"
        if isinstance(abstract, dict):
            try:
                max_pos = max(max(idxs) for idxs in abstract.values()) if abstract else 0
                abstract_list = [""] * (max_pos + 1)
                for word, idxs in abstract.items():
                    if isinstance(idxs, list):
                        for idx in idxs:
                            if isinstance(idx, int) and 0 <= idx < len(abstract_list):
                                abstract_list[idx] = str(word)
                abstract_text = " ".join(abstract_list).strip() or "No abstract"
            except (ValueError, TypeError):
                abstract_text = "No abstract"
        
        # Handle URL safely
        primary = work.get("primary_location", {})
        if not isinstance(primary, dict):
            primary = {}
        
        source = primary.get("source", {})
        if not isinstance(source, dict):
            source = {}
            
        url_work = _safe_get(source, "url") or _safe_get(work, "id", "")
        
        parts.append(f"{title} ({year}) by {authors_str}\nAbstract: {abstract_text}\nURL: {url_work}")

    return "\n\n".join(parts) or "No papers found."


def search_openalex(query: str, max_results: int = 3) -> str:
    """Search OpenAlex for papers matching the query."""
    return _fetch(query, max_results)
