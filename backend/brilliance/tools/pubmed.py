# pubmed_tool.py
"""Tool for retrieving recent PubMed articles via NCBI E-utilities.
Returns a concise string with Title (Year), Authors, Abstract and URL for each hit.
"""
from __future__ import annotations

import httpx
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus
import os
from typing import List, Any


def _safe_get_text(element: Any, path: str, default: str = "") -> str:
    """Safely extract text from XML element with fallback."""
    if element is None:
        return default
    text = element.findtext(path, default=default)
    return str(text).strip() if text is not None else default


def _safe_get_authors(article: Any) -> str:
    """Safely extract authors from PubMed article."""
    if article is None:
        return "N/A"
    
    authors_el = article.findall(".//Author")
    if not authors_el:
        return "N/A"
    
    authors: List[str] = []
    for a in authors_el:
        if a is None:
            continue
        lname = a.findtext("LastName")
        fname = a.findtext("ForeName")
        if lname and fname:
            authors.append(f"{fname} {lname}")
        elif lname:
            authors.append(lname)
        elif fname:
            authors.append(fname)
    
    return ", ".join(authors) if authors else "N/A"


def _fetch(query: str, max_results: int = 3) -> str:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    # 1. ESearch – allow direct URL or construct from query
    if isinstance(query, str) and query.startswith("http"):
        esearch_url = query
    else:
        esearch_url = (
            f"{base}esearch.fcgi?db=pubmed&term={quote_plus(query)}"
            f"&retmax={max_results}&sort=pub+date&retmode=json"
        )

    # Add NCBI etiquette params if present (apply before first request)
    tool = os.getenv("PUBMED_TOOL", "brilliance")
    email = os.getenv("PUBMED_EMAIL", "")
    api_key = os.getenv("PUBMED_API_KEY", "")
    suffix = f"&tool={tool}" + (f"&email={quote_plus(email)}" if email else "") + (f"&api_key={api_key}" if api_key else "")
    esearch_url += suffix
    
    try:
        headers = {"User-Agent": os.getenv("HTTP_USER_AGENT", "Brilliance/1.0 (+contact@brilliance)")}
        for attempt in range(3):
            try:
                resp = httpx.get(esearch_url, headers=headers, timeout=httpx.Timeout(5.0, connect=3.0))
                resp.raise_for_status()
                break
            except Exception:
                if attempt == 2:
                    raise
                import time, random
                time.sleep((2 ** attempt) + random.random())
        search_data = resp.json()
        
        if not isinstance(search_data, dict):
            return "Error: Invalid response format from PubMed search."
            
        esearch_result = search_data.get("esearchresult", {})
        if not isinstance(esearch_result, dict):
            return "Error: Invalid search result format."
            
        ids = esearch_result.get("idlist", [])
        if not isinstance(ids, list):
            return "Error: Invalid ID list format."
            
    except Exception as e:
        return f"Error searching PubMed: {str(e)}"

    if not ids:
        return "No papers found."

    # 2. EFetch – retrieve the article metadata & abstract
    id_str = ",".join(str(id) for id in ids if str(id).strip())
    if not id_str:
        return "No valid paper IDs found."
        
    efetch_url = (
        f"{base}efetch.fcgi?db=pubmed&id={id_str}&retmode=xml"
    )
    efetch_url += suffix
    
    try:
        headers = {"User-Agent": os.getenv("HTTP_USER_AGENT", "Brilliance/1.0 (+contact@brilliance)")}
        for attempt in range(3):
            try:
                xml_resp = httpx.get(efetch_url, headers=headers, timeout=httpx.Timeout(8.0, connect=3.0))
                xml_resp.raise_for_status()
                break
            except Exception:
                if attempt == 2:
                    raise
                import time, random
                time.sleep((2 ** attempt) + random.random())
        xml_text = xml_resp.text
    except Exception as e:
        return f"Error fetching PubMed details: {str(e)}"

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        return f"Error parsing PubMed XML: {str(e)}"

    parts: List[str] = []
    for article in root.findall(".//PubmedArticle"):
        try:
            art = article.find(".//Article")
            if art is None:
                continue
                
            # Safely extract title
            title = _safe_get_text(art, "ArticleTitle", "No title")
            
            # Safely extract year
            year = article.findtext(".//PubDate/Year", default="N/A")
            
            # Safely extract authors
            authors_str = _safe_get_authors(article)
            
            # Safely extract abstract (join multiple AbstractText segments)
            abstract = "No abstract"
            abs_el = article.find(".//Abstract")
            if abs_el is not None:
                chunks = [el.text for el in abs_el.findall(".//AbstractText") if el is not None and el.text]
                if chunks:
                    abstract = " ".join(chunks).strip()
            
            # Safely extract PMID and create URL
            pmid = article.findtext(".//PMID")
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

            parts.append(
                f"{title} ({year}) by {authors_str}\nAbstract: {abstract}\nURL: {url}"
            )
            
        except Exception:
            # Skip malformed articles but continue processing others
            continue

    return "\n\n".join(parts) if parts else "No papers found."


def search_pubmed(query: str, max_results: int = 3) -> str:
    """Search PubMed for papers matching the query."""
    return _fetch(query, max_results)
