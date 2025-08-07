"""
agents_workflow.py

Main orchestration workflow for multi-source scholarly research with query optimization.
"""
import argparse
import asyncio
import os
from typing import Dict, Any
from brilliance.tools.arxiv import search_arxiv
from brilliance.tools.pubmed import search_pubmed
from brilliance.tools.openalex import search_openalex
from brilliance.agents.query_optimizer_agent import optimize_academic_query
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
    # Step 1: Optimize the query
    optimized = await optimize_academic_query(query)

    # Step 2: Build API-specific queries
    api_queries = build_api_queries(optimized, max_results)

    # Step 3: Search with optimized queries
    arxiv_results = search_arxiv(
            api_queries["arxiv"].split("search_query=")[1].split("&")[0] if "arxiv" in api_queries else query,
            max_results
        )
    
    pubmed_results = search_pubmed(
            " ".join(optimized.keywords),
            max_results
        )
    
    openalex_results = search_openalex(
            " ".join(optimized.keywords),
            max_results
        )
    
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
                
                # More robust paper counting - look for multiple title patterns
                title_patterns = ["Title:", "title:", "**Title:**", "## Title", "Paper Title:"]
                paper_count = 0
                for pattern in title_patterns:
                    paper_count = max(paper_count, content.count(pattern))
                
                # Also count by looking for common paper metadata patterns
                if paper_count == 0:
                    # Fallback: count by author patterns or DOI patterns
                    author_count = content.count("Authors:") + content.count("Author:")
                    doi_count = content.count("DOI:") + content.count("doi:")
                    paper_count = max(author_count, doi_count)
                
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


async def orchestrate_research(user_query: str, max_results: int = 3) -> Dict[str, Any]:
    """
    Main orchestration function for research queries with optimization.
    
    Args:
        user_query: Natural language research question
        max_results: Maximum results per source
        
    Returns:
        Comprehensive research results with optimization metadata and synthesis
    """
    print(f"🔍 Optimizing query: {user_query}")
    
    # Search across sources with optimization
    search_results = await multi_source_search(user_query, max_results)
    
    # Prepare results for agent synthesis (no manual ranking)
    final_results = prepare_results_for_synthesis(search_results)
    
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
    parser.add_argument("--model", choices=["o3-mini", "grok-4"], default="o3-mini",
                        help="LLM model for query optimisation (default: o3-mini)")
    args = parser.parse_args()

    # Configure xAI SDK if GROK selected. Users already set GROK_API_KEY in env.
    if args.model == "grok-4":
        # xAI python SDK expects XAI_API_KEY
        os.environ.setdefault("XAI_API_KEY", os.getenv("GROK_API_KEY", ""))

    # Use Grok only for synthesis; keep optimizer on default OpenAI model
    from synthesis_tool import _summarizer
    _summarizer.model = args.model

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
            
            print("\n� **Research Synthesis:**")
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