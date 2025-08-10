"""
Tool wrappers for Agents SDK to fetch papers from external sources.

All tools follow Pydantic v2-compatible type annotations and docstrings.
"""
from __future__ import annotations

from agents import function_tool
import time

# Simple in-process budget: max calls and global timebox
_BUDGET = {
    "max_calls": 3,
    "calls": 0,
    "started": 0.0,
    "global_seconds": 20,
    # enforce per-source cap regardless of what the LLM passes
    "per_source_max": 3,
}


def set_research_budget(max_calls: int, global_seconds: int, per_source_max: int | None = None) -> None:
    _BUDGET.update({
        "max_calls": max_calls,
        "calls": 0,
        "started": time.time(),
        "global_seconds": global_seconds,
        **({"per_source_max": int(per_source_max)} if per_source_max is not None else {}),
    })


def clear_research_budget() -> None:
    _BUDGET.update({"calls": 0, "started": 0.0, "per_source_max": 3})


def _check_budget() -> None:
    now = time.time()
    if _BUDGET["started"] and (now - _BUDGET["started"]) > _BUDGET["global_seconds"]:
        raise RuntimeError("Research budget exceeded (time)")
    if _BUDGET["calls"] >= _BUDGET["max_calls"]:
        raise RuntimeError("Research budget exceeded (tool calls)")
    _BUDGET["calls"] += 1

from brilliance.tools.arxiv import search_arxiv
from brilliance.tools.pubmed import search_pubmed
from brilliance.tools.openalex import search_openalex


@function_tool()
def arxiv_search(query: str, max_results: int = 3) -> str:
    """Search arXiv for papers.

    Args:
        query: Free-text or arXiv-compatible query string
        max_results: Maximum number of results to return

    Returns:
        A formatted string of papers with titles, years, and URLs
    """
    _check_budget()
    cap = min(int(max_results), int(_BUDGET.get("per_source_max", max_results)))
    return search_arxiv(query, cap)


@function_tool()
def pubmed_search(query: str, max_results: int = 3) -> str:
    """Search PubMed for papers.

    Args:
        query: Free-text query; function builds an e-utils search request
        max_results: Maximum number of results to return

    Returns:
        A formatted string of papers with titles, years, and URLs
    """
    _check_budget()
    cap = min(int(max_results), int(_BUDGET.get("per_source_max", max_results)))
    return search_pubmed(query, cap)


@function_tool()
def openalex_search(query: str, max_results: int = 3) -> str:
    """Search OpenAlex for works.

    Args:
        query: Free-text query string for OpenAlex
        max_results: Maximum number of results to return

    Returns:
        A formatted string of papers with titles, years, and URLs
    """
    _check_budget()
    cap = min(int(max_results), int(_BUDGET.get("per_source_max", max_results)))
    return search_openalex(query, cap)


