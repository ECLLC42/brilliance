"""
agents_workflow.py

Main orchestration workflow for multi-source scholarly research with query optimization.
"""
import argparse
import asyncio
import os
from datetime import datetime
from typing import Dict, Any, List, Tuple
from brilliance.tools.arxiv import search_arxiv
from brilliance.tools.pubmed import search_pubmed
from brilliance.tools.openalex import search_openalex
from brilliance.agents.query_optimizer_agent import optimize_academic_query, _fallback_optimization
from brilliance.agents.build_query import build_api_queries
from brilliance.synthesis.synthesis_tool import synthesize_papers_async


async def multi_source_search(query: str, max_results: int = 3) -> Dict[str, Any]:
    """
    Search across multiple scholarly sources using optimized queries.
    
    Args:
        query: Raw user query
        max_results: Maximum results per source
        
    Returns:
        Dictionary with results from all sources
    """
    # Step 1: Optimize the query (with fallback)
    try:
        optimized = await optimize_academic_query(query)
    except Exception:
        optimized = _fallback_optimization(query)

    # Normalize missing agent fields (agent may return keywords only)
    if not getattr(optimized, "preferred_year", None):
        optimized.preferred_year = datetime.now().year - 1
    for k in ("disease_terms", "intervention_terms", "outcome_terms", "study_type_terms"):
        if not getattr(optimized, k, None):
            setattr(optimized, k, [])

    # Step 2: Build API-specific queries (URLs)
    api_queries = build_api_queries(optimized, max_results)

    # Step 3: Search with builder URLs where available (tools accept full URLs)
    arxiv_query = api_queries.get("arxiv") or " ".join(optimized.keywords)
    pubmed_query = api_queries.get("pubmed", {}).get("search_url") if isinstance(api_queries.get("pubmed"), dict) else None
    openalex_query = api_queries.get("openalex") or " ".join(optimized.keywords)

    # Pass preferred year to arXiv via env when unset
    if not os.getenv("ARXIV_MIN_YEAR") and getattr(optimized, "preferred_year", None):
        os.environ["ARXIV_MIN_YEAR"] = str(optimized.preferred_year)
    arxiv_results = search_arxiv(arxiv_query, max_results)
    pubmed_results = search_pubmed(pubmed_query or " ".join(optimized.keywords), max_results)
    openalex_results = search_openalex(openalex_query, max_results)
    
    return {
        "arxiv": arxiv_results,
        "pubmed": pubmed_results,
        "openalex": openalex_results,
        "original_query": query,
        "optimized_query": {
            "keywords": optimized.keywords,
            "preferred_year": optimized.preferred_year,
            "disease_terms": optimized.disease_terms,
            "intervention_terms": optimized.intervention_terms,
            "outcome_terms": optimized.outcome_terms,
            "study_type_terms": optimized.study_type_terms
        }
    }


def prepare_results_for_synthesis(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare raw search results for agent-based synthesis.
    Let the agents handle prioritization and ranking intelligently.
    """
    # Count actual results by checking if strings contain meaningful content
    source_names = []
    total_papers = 0
    
    for source in ["arxiv", "pubmed", "openalex"]:
        if source in results and isinstance(results[source], str):
            content = results[source].strip()
            if content and not content.startswith("No papers found") and not content.startswith("Error"):
                source_names.append(source)
                
                # Count by URLs, which all tool outputs include
                paper_count = content.count("\nURL: ")
                if paper_count == 0 and "URL: " in content:
                    paper_count = content.count("URL: ")
                
                # If still no papers found but content exists, assume at least 1
                if paper_count == 0 and len(content) > 100:  # Substantial content
                    paper_count = 1
                    
                total_papers += paper_count
    
    # Ensure we have valid data structure
    raw_results = {
        "arxiv": results.get("arxiv", "No results"),
        "pubmed": results.get("pubmed", "No results"), 
        "openalex": results.get("openalex", "No results")
    }
    
    # Get original query safely
    original_query = results.get("original_query", "")
    if not original_query and "optimized_query" in results:
        # Fallback to keywords from optimized query
        opt_query = results["optimized_query"]
        if isinstance(opt_query, dict) and "keywords" in opt_query:
            original_query = " ".join(opt_query["keywords"])
    
    return {
        "raw_results": raw_results,
        "summary": {
            "total": total_papers,
            "sources": source_names,
            "query": original_query
        },
        "optimized_query": results.get("optimized_query", {})
    }


def _tokenize_for_scoring(text: str) -> List[str]:
    if not text:
        return []
    import re
    return [t for t in re.findall(r"[a-zA-Z0-9]+", text.lower()) if t]


def _parse_source_chunks(source_text: str) -> List[Tuple[str, Dict[str, Any]]]:
    """Split tool output into individual paper chunks and extract lightweight metadata.
    Returns list of (chunk_text, metadata) where metadata includes title, year, url.
    """
    if not isinstance(source_text, str) or not source_text.strip():
        return []
    chunks = [c.strip() for c in source_text.strip().split("\n\n") if c.strip()]
    parsed: List[Tuple[str, Dict[str, Any]]] = []
    for c in chunks:
        title_line = c.split("\n", 1)[0] if "\n" in c else c
        title = title_line.split(" (", 1)[0]
        year = "N/A"
        if "(" in title_line and ")" in title_line:
            try:
                year = title_line.split("(", 1)[1].split(")", 1)[0]
            except Exception:
                year = "N/A"
        url = ""
        if "URL:" in c:
            try:
                url = c.split("URL:", 1)[1].strip().split()[0]
            except Exception:
                url = ""
        parsed.append((c, {"title": title, "year": year, "url": url}))
    return parsed


def _score_chunk(query: str, meta: Dict[str, Any]) -> float:
    """Heuristic relevance score: keyword overlap (title weighted) + recency."""
    title = meta.get("title", "")
    year = meta.get("year", "N/A")
    query_tokens = set(_tokenize_for_scoring(query))
    title_tokens = set(_tokenize_for_scoring(title))
    overlap = len(query_tokens & title_tokens)
    # Title overlap weight 2.0
    score = overlap * 2.0
    # Recency boost
    try:
        y = int(year)
        from datetime import datetime
        age = max(0, datetime.now().year - y)
        score += max(0.0, 3.0 - (age * 0.5))  # up to +3, decays with age
    except Exception:
        pass
    return score


def rank_and_trim_results(all_results: Dict[str, Any], query: str, max_total: int) -> Dict[str, Any]:
    """Rank papers across sources and trim to max_total overall (not per source).
    Falls back to returning original results if parsing fails.
    """
    try:
        combined: List[Tuple[str, str, float]] = []  # (source, chunk_text, score)
        for source in ["arxiv", "pubmed", "openalex"]:
            for chunk_text, meta in _parse_source_chunks(all_results.get(source, "")):
                score = _score_chunk(query, meta)
                combined.append((source, chunk_text, score))
        if not combined:
            return all_results
        # Deduplicate by URL or title
        seen_keys = set()
        deduped: List[Tuple[str, str, float]] = []
        for source, chunk_text, score in combined:
            key = None
            if "URL:" in chunk_text:
                try:
                    key = chunk_text.split("URL:", 1)[1].strip()
                except Exception:
                    key = None
            if not key:
                key = chunk_text.split("\n", 1)[0]
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append((source, chunk_text, score))
        # Rank and take top K
        deduped.sort(key=lambda x: x[2], reverse=True)
        chosen = deduped[: max_total]
        # Rebuild per-source strings
        out: Dict[str, Any] = dict(all_results)
        grouped: Dict[str, List[str]] = {"arxiv": [], "pubmed": [], "openalex": []}
        for source, chunk_text, _ in chosen:
            grouped[source].append(chunk_text)
        for source in grouped:
            out[source] = "\n\n".join(grouped[source]) if grouped[source] else "No results"
        return out
    except Exception:
        return all_results


async def orchestrate_research(user_query: str, max_results: int = 3) -> Dict[str, Any]:
    """
    Main orchestration function for research queries with optimization.
    
    Args:
        user_query: Natural language research question
        max_results: Maximum results per source
        
    Returns:
        Comprehensive research results with optimization metadata and synthesis
    """
    print(f"🔍 Optimizing query (len={len(user_query)})")
    
    # Search across sources with optimization
    search_results = await multi_source_search(user_query, max_results)
    # Rank globally and trim to the requested max total
    trimmed_results = rank_and_trim_results(search_results, user_query, max_results)
    
    # Prepare results for agent synthesis (no manual ranking)
    final_results = prepare_results_for_synthesis(trimmed_results)
    
    # Add optimization summary
    final_results["optimization"] = {
        "original_query": search_results.get("original_query"),
        "optimized_query": search_results.get("optimized_query"),
        "api_queries_built": bool(search_results.get("optimized_query"))
    }
    
    # AI Synthesis Step
    if 'raw_results' in final_results and any(
        content and content != "No results" and not content.startswith("Error") 
        for content in final_results['raw_results'].values()
    ):
        print(f"🤖 Analyzing papers to answer: '{user_query}'")
        
        # Combine all paper data for synthesis
        combined_papers = ""
        for source, content in final_results['raw_results'].items():
            if content and content != "No results" and not content.startswith("Error"):
                combined_papers += f"\n=== {source.upper()} Results ===\n{content}\n"
        
        # Add user query context for synthesis
        max_chars = int(os.getenv("MAX_COMBINED_CHARS", "20000"))
        if len(combined_papers) > max_chars:
            combined_papers = combined_papers[:max_chars]
        synthesis_prompt = f"User Query: {user_query}\n\nPaper Data:\n{combined_papers}"
        
        # Generate AI synthesis
        synthesis = await synthesize_papers_async(synthesis_prompt)
        final_results["synthesis"] = synthesis
    else:
        final_results["synthesis"] = "No papers found to analyze."
    
    return final_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scholarly multi-source research assistant")
    parser.add_argument("query", nargs="?", help="Research question. If omitted, you will be prompted interactively.")
    parser.add_argument("--model", choices=["gpt-5-mini", "grok-4"], default="gpt-5-mini",
                        help="LLM model for query optimisation (default: gpt-5-mini)")
    args = parser.parse_args()

    # Configure xAI SDK if GROK selected. Users already set GROK_API_KEY in env.
    if args.model == "grok-4":
        # xAI python SDK expects XAI_API_KEY
        os.environ.setdefault("XAI_API_KEY", os.getenv("GROK_API_KEY", ""))

    # Model selection is driven by environment variables; no runtime mutation here

    query_input = args.query or input("Enter your research question: ")

    async def cli_main():
        results = await orchestrate_research(query_input)

        print(f"\n📊 Found {results['summary']['total']} papers from {len(results['summary']['sources'])} sources (model: {args.model})")
        if results.get("optimization", {}).get("optimized_query"):
            print("\n🎯 Optimized search terms:")
            opt = results["optimization"]["optimized_query"]
            print(f"   Keywords: {', '.join(opt['keywords'])}")
            print(f"   Target year: {opt['preferred_year']}")
            if opt['disease_terms']:
                print(f"   Disease terms: {', '.join(opt['disease_terms'])}")
            if opt['intervention_terms']:
                print(f"   Intervention terms: {', '.join(opt['intervention_terms'])}")

        # AI Synthesis Step
        if 'raw_results' in results and any(
            content and content != "No results" and not content.startswith("Error") 
            for content in results['raw_results'].values()
        ):
            print(f"\n🤖 Analyzing papers to answer: '{query_input}'")
            
            # Combine all paper data for synthesis
            combined_papers = ""
            for source, content in results['raw_results'].items():
                if content and content != "No results" and not content.startswith("Error"):
                    combined_papers += f"\n=== {source.upper()} Results ===\n{content}\n"
            
            # Add user query context for synthesis
            synthesis_prompt = f"User Query: {query_input}\n\nPaper Data:\n{combined_papers}"
            
            # Generate AI synthesis
            synthesis = await synthesize_papers_async(synthesis_prompt)
            
            print("\n**Research Synthesis:**")
            print(synthesis)
        else:
            print("\n❌ No papers found to analyze.")

        print("\n📄 **Raw Data Sources:**")
        
        # Display raw results from each source
        if 'raw_results' in results:
            raw_results = results['raw_results']
            for source, content in raw_results.items():
                if content and content != "No results" and not content.startswith("Error"):
                    print(f"\n=== {source.upper()} Results ===")
                    print(content)
        else:
            print("No results found.")

    asyncio.run(cli_main())