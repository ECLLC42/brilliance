"""
build_query.py

API-specific query builder for scholarly APIs.
Converts optimized keywords into precise API queries per official documentation.
"""

from typing import List, Dict, Any, Union
from urllib.parse import quote_plus
from datetime import datetime
import re


class APIQueryBuilder:
    """Builds API-specific queries for scholarly search APIs."""
    
    @staticmethod
    def build_arxiv_query(keywords: List[str], year: int, max_results: int = 10) -> str:
        """
        Build ArXiv API query using official documentation.
        
        Args:
            keywords: List of search keywords
            year: Target publication year
            max_results: Maximum results to return
            
        Returns:
            ArXiv API query string
        """
        if not keywords:
            return ""
        
        # Separate single words and phrases
        single_words = [kw for kw in keywords if " " not in kw]
        phrases = [kw for kw in keywords if " " in kw]

        # Heuristic: require 1–2 core phrases (AND) to tighten relevance
        must_groups: List[str] = []
        optional_groups: List[str] = []

        if phrases:
            # Prefer domain-anchoring phrases (materials/chemistry) as required terms
            def _is_domain_anchor(p: str) -> bool:
                pl = p.lower()
                return any(tok in pl for tok in [
                    "material", "catalyst", "alloy", "crystal", "molecule", "molecular",
                    "synthesis", "adsorption", "band gap", "formation energy", "surfaces",
                ])

            def _is_gnn_anchor(p: str) -> bool:
                pl = p.lower()
                return ("graph" in pl) and any(t in pl for t in ["neural", "gnn", "message passing", "convolution", "attention"])

            anchors = [p for p in phrases if _is_domain_anchor(p)]
            gnn_phrases = [p for p in phrases if _is_gnn_anchor(p)]

            if anchors:
                # Require one domain anchor and (if available) one GNN anchor
                core_phrases = [anchors[0]]
                if gnn_phrases:
                    gchoice = gnn_phrases[0]
                    if gchoice != anchors[0]:
                        core_phrases.append(gchoice)
            else:
                # No domain anchors: require only the first phrase to keep recall high
                core_phrases = phrases[:1]

            for p in core_phrases:
                must_groups.append(f"(ti:\"{p}\" OR abs:\"{p}\")")

            # Remaining phrases become optional signals
            rem_phrases = [p for p in phrases if p not in core_phrases]
            if rem_phrases:
                scoped = [f'ti:"{p}"' for p in rem_phrases] + [f'abs:"{p}"' for p in rem_phrases]
                optional_groups.append("(" + " OR ".join(scoped) + ")")

        # Single-word tokens are optional signals (OR)
        if single_words:
            scoped = [f'ti:"{w}"' for w in single_words] + [f'abs:"{w}"' for w in single_words]
            optional_groups.append("(" + " OR ".join(scoped) + ")")

        # Detect arXiv subject category codes like cs.LG, stat.ML, math.PR and add as optional cat: filters
        cat_codes = [kw for kw in keywords if re.match(r"^[a-z-]+\.[A-Za-z]{2,3}$", kw)]
        if cat_codes:
            cat_part = " OR ".join(f'cat:{code}' for code in cat_codes)
            optional_groups.append("(" + cat_part + ")")

        # Build the final boolean search expression
        if must_groups:
            # Require must groups; append a single optional OR bucket if present
            if optional_groups:
                search_query = " AND ".join(must_groups + ["(" + " OR ".join(optional_groups) + ")"])
            else:
                search_query = " AND ".join(must_groups)
        else:
            # No phrases -> fall back to broad OR across all tokens
            if optional_groups:
                search_query = "(" + " OR ".join(optional_groups) + ")"
            else:
                search_query = " OR ".join(f'"{kw}"' for kw in keywords)

        # arXiv does not filter by submittedDate inside search_query reliably; rely on sort
        combined_query = f"({search_query})"

        # Build final URL
        base_url = "https://export.arxiv.org/api/query"
        params = {
            "search_query": combined_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }

        query_string = "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())
        return f"{base_url}?{query_string}"
    
    @staticmethod
    def build_pubmed_query(keywords: List[str], year: int, max_results: int = 10) -> Dict[str, str]:
        """
        Build PubMed E-utilities query using official documentation.
        
        Args:
            keywords: List of search keywords
            year: Target publication year
            max_results: Maximum results to return
            
        Returns:
            Dictionary with search and fetch URLs
        """
        if not keywords:
            return {}
        
        # Separate single words and phrases
        single_words = [kw for kw in keywords if " " not in kw]
        phrases = [kw for kw in keywords if " " in kw]
        
        # Build query parts
        parts = []
        
        # Add phrases with exact matching in title and abstract
        if phrases:
            phrase_query = " OR ".join(f'"{phrase}"[Title/Abstract]' for phrase in phrases)
            parts.append(phrase_query)
        
        # Add single words with broader search
        if single_words:
            word_query = " OR ".join(f'"{word}"[Title/Abstract]' for word in single_words)
            parts.append(word_query)
        
        # Combine all parts
        if parts:
            keyword_query = " OR ".join(parts)
        else:
            keyword_query = " OR ".join(f'"{kw}"[Title/Abstract]' for kw in keywords)
        
        # Add date filter
        date_filter = f"({year}[Date - Publication] : 3000[Date - Publication])"
        
        # Combine queries
        search_query = f"({keyword_query}) AND {date_filter}"
        
        # Build search URL
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": search_query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance"
        }
        
        search_url = f"{base_url}?{'&'.join(f'{k}={quote_plus(str(v))}' for k, v in search_params.items())}"
        
        # Build fetch URL for details
        fetch_params = {
            "db": "pubmed",
            "retmode": "xml",
            "rettype": "abstract"
        }
        
        return {
            "search_url": search_url,
            "fetch_base": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            "fetch_params": fetch_params
        }
    
    @staticmethod
    def build_openalex_query(keywords: List[str], year: int, max_results: int = 10) -> str:
        """
        Build OpenAlex API query using official documentation.
        
        Args:
            keywords: List of search keywords
            year: Target publication year
            max_results: Maximum results to return
            
        Returns:
            OpenAlex API query string
        """
        if not keywords:
            return ""
        
        # OpenAlex uses space-separated keywords
        keyword_query = " ".join(keywords)
        
        # Build query with filters
        base_url = "https://api.openalex.org/works"
        params = {
            "search": keyword_query,
            "per_page": max_results,
            "sort": "publication_year:desc",
            "filter": f"publication_year:>{year-1}"
        }
        
        query_string = "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())
        return f"{base_url}?{query_string}"
    
    @staticmethod
    def build_google_scholar_query(keywords: List[str], year: int) -> str:
        """
        Build Google Scholar-compatible query (for reference).
        
        Args:
            keywords: List of search keywords
            year: Target publication year
            
        Returns:
            Google Scholar query string
        """
        if not keywords:
            return ""
        
        # Google Scholar uses space-separated keywords
        keyword_query = " ".join(f'"{kw}"' for kw in keywords)
        
        # Add year filter
        year_filter = f"after:{year-1}"
        
        return f"{keyword_query} {year_filter}"
    
    @staticmethod
    def optimize_keywords_for_api(keywords: List[str], api_type: str) -> List[str]:
        """
        Optimize keywords for specific API requirements.
        
        Args:
            keywords: Original keywords
            api_type: Target API ('arxiv', 'pubmed', 'openalex')
            
        Returns:
            API-optimized keywords
        """
        optimized = []
        
        for keyword in keywords:
            # Clean and standardize
            cleaned = keyword.strip().lower()
            
            # API-specific optimizations
            if api_type == "pubmed":
                # PubMed prefers MeSH terms and abbreviations
                cleaned = re.sub(r'\btherapy\b', 'therapeutic', cleaned)
                cleaned = re.sub(r'\btreatment\b', 'therapeutic', cleaned)
            elif api_type == "arxiv":
                # ArXiv prefers technical terms
                cleaned = re.sub(r'\bnew\b', 'novel', cleaned)
                cleaned = re.sub(r'\bbest\b', 'optimal', cleaned)
            
            optimized.append(cleaned)
        
        return optimized


def build_api_queries(optimized_query, max_results: int = 10) -> Dict[str, Union[str, Dict[str, Any]]]:
    """
    Build API-specific queries for all supported scholarly APIs.
    
    Args:
        optimized_query: OptimizedQuery object from query optimizer
        max_results: Maximum results per API
        
    Returns:
        Dictionary mapping API names to query strings
    """
    queries = {}
    
    # Get optimized keywords
    keywords = optimized_query.keywords
    year = optimized_query.preferred_year
    
    # Build queries for each API
    queries["arxiv"] = APIQueryBuilder.build_arxiv_query(keywords, year, max_results)
    queries["pubmed"] = APIQueryBuilder.build_pubmed_query(keywords, year, max_results)
    queries["openalex"] = APIQueryBuilder.build_openalex_query(keywords, year, max_results)
    queries["google_scholar"] = APIQueryBuilder.build_google_scholar_query(keywords, year)
    
    return queries


# Convenience functions for direct API usage
def build_arxiv_query(keywords: List[str], year: int, max_results: int = 10) -> str:
    """Build ArXiv query string."""
    return APIQueryBuilder.build_arxiv_query(keywords, year, max_results)


def build_pubmed_query(keywords: List[str], year: int, max_results: int = 10) -> Dict[str, str]:
    """Build PubMed query."""
    return APIQueryBuilder.build_pubmed_query(keywords, year, max_results)


def build_openalex_query(keywords: List[str], year: int, max_results: int = 10) -> str:
    """Build OpenAlex query."""
    return APIQueryBuilder.build_openalex_query(keywords, year, max_results)
