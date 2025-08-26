"""
Research agent that selects minimal relevant sources and fetches papers via tools.

Returns structured output suitable for downstream synthesis.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from agents import Agent, Runner, AgentOutputSchema, ToolsToFinalOutputResult

from brilliance.agents.tools import (
    arxiv_search,
    pubmed_search,
    openalex_search,
    set_research_budget,
    clear_research_budget,
)
from brilliance.tools.arxiv import search_arxiv as _search_arxiv
from brilliance.tools.pubmed import search_pubmed as _search_pubmed
from brilliance.tools.openalex import search_openalex as _search_openalex


@dataclass
class ResearchOutput:
    """Structured output for research agent.

    sources: mapping of source name to formatted string of results.
    used_sources: list of sources actually queried.
    summary: short human-readable summary of what was retrieved.
    """
    sources: Dict[str, str]
    used_sources: List[str]
    summary: str


RESEARCH_INSTRUCTIONS = (
    "You are a scholarly research planner and fetcher.\n\n"
    "Objective: Retrieve recent, relevant papers with predictable agentic behavior and concise progress updates.\n\n"
    "Persistence (agentic behavior):\n"
    "- Keep going until the user's research request is fully resolved for this step; do not hand back early.\n"
    "- When uncertain, choose the most reasonable assumption and proceed; document assumptions briefly in your summary.\n\n"
    "Tool preambles (progress updates):\n"
    "- Before any tool call: rephrase the user's goal in one sentence and list a short plan of the tool calls you intend (up to the budget).\n"
    "- For each tool call: emit a one‑line preamble of why you're calling it and what you expect.\n"
    "- After each call: briefly reflect in one line on whether the result is sufficient to stop or whether another call is warranted.\n"
    "- Finish with a short summary of which sources returned content.\n\n"
    "Context gathering (calibrated eagerness):\n"
    "- Start broad, then fan out only as needed. Deduplicate queries.\n"
    "- Early‑stop when ~70% of signals converge on the same sources or you can name the exact content to return.\n"
    "- Parallelize thinking but keep tool calls within the budget.\n\n"
    "Domain heuristics (guidance, not rules):\n"
    "- Astronomy/Physics: prefer arXiv and OpenAlex; avoid PubMed.\n"
    "- Biomedical/health: include PubMed; optionally arXiv/OpenAlex if clearly relevant.\n"
    "- ML/CS: prefer arXiv and OpenAlex.\n"
    "- General science: search across arXiv, PubMed, OpenAlex.\n\n"
    "Query optimization tips:\n"
    "- arXiv: Use specific technical terms, acronyms, and key concepts. Natural language works well.\n"
    "- PubMed: Include medical/biological terms, disease names, treatment types.\n"
    "- OpenAlex: Broader interdisciplinary terms work well.\n"
    "- Avoid overly generic terms; be specific about the research domain.\n\n"
    "Constraints & budgets:\n"
    "- Respect max_results per source exactly as provided.\n"
    "- Absolute maximum of 3 tool calls in total; stop earlier if sufficient.\n"
    "- Do not summarize or transform tool outputs; copy them verbatim into the per‑source fields.\n"
    "- Do not invent fields or nested objects.\n\n"
    "Output: The system assembles JSON; just select tools and call them.\n"
)


def _build_research_agent(model: str, enabled_sources: Optional[List[str]] = None) -> Agent:
    # Default to arxiv + openalex if none specified
    if enabled_sources is None:
        enabled_sources = ["arxiv", "openalex"]
    
    # Build tools list based on enabled sources
    tools = []
    if "arxiv" in enabled_sources:
        tools.append(arxiv_search)
    if "pubmed" in enabled_sources:
        tools.append(pubmed_search)
    if "openalex" in enabled_sources:
        tools.append(openalex_search)
    
    # Custom tool-to-output: Convert tool results directly into our schema to avoid LLM formatting drift
    async def _tools_to_output(ctx, tool_results):
        sources: Dict[str, str] = {"arxiv": "No results", "pubmed": "No results", "openalex": "No results"}
        used: List[str] = []
        for r in tool_results:
            name = getattr(r.tool, "name", "")
            out = str(getattr(r, "output", "")).strip() or "No results"
            if name.endswith("arxiv_search") or name == "arxiv_search":
                sources["arxiv"] = out
                if "arxiv" not in used:
                    used.append("arxiv")
            elif name.endswith("pubmed_search") or name == "pubmed_search":
                sources["pubmed"] = out
                if "pubmed" not in used:
                    used.append("pubmed")
            elif name.endswith("openalex_search") or name == "openalex_search":
                sources["openalex"] = out
                if "openalex" not in used:
                    used.append("openalex")

        # Attach tool context note so downstream synthesis knows what was actually retrieved
        context_note = "; ".join([f"{s}: {('yes' if sources[s] != 'No results' else 'no')}" for s in ["arxiv","pubmed","openalex"]])
        summary = f"Fetched results from {', '.join(used) if used else 'no'} sources. Context presence -> {context_note}."
        return ToolsToFinalOutputResult(
            is_final_output=True,
            final_output=ResearchOutput(sources=sources, used_sources=used, summary=summary),
        )

    return Agent(
        name="research_agent",
        instructions=RESEARCH_INSTRUCTIONS,
        model=model,
        tools=tools,
        output_type=AgentOutputSchema(ResearchOutput, strict_json_schema=False),
        tool_use_behavior=_tools_to_output,
    )


async def run_research_agent(query: str, max_results: int, model: Optional[str] = None, user_api_key: Optional[str] = None, reasoning_effort: Optional[str] = None, verbosity: Optional[str] = None, enabled_sources: Optional[List[str]] = None) -> ResearchOutput:
    """Run the research agent with budgets/guardrails and return structured output."""
    # Use a known model supported by the default OpenAI provider in the Agents SDK
    # Force GPT-5
    chosen_model = "gpt-5"
    # No budget restrictions - allow unlimited tool calls and time
    max_calls = 999999  # Effectively unlimited
    global_secs = 999999  # Effectively unlimited
    per_source_cap = max(1, int(max_results))
    set_research_budget(max_calls=max_calls, global_seconds=global_secs, per_source_max=per_source_cap)
    try:
        agent = _build_research_agent(chosen_model, enabled_sources)
        user_msg = (
            f"User Query: {query}\n\n"
            f"max_results: {max_results}\n"
            "When calling tools, pass max_results exactly as provided."
        )
        # Build a RunConfig that disables sensitive data in tracing and, if needed, injects a per-run model provider
        from agents import RunConfig, ModelSettings
        # Apply reasoning/verbosity if provided
        ms = ModelSettings()
        if reasoning_effort:
            ms.reasoning = {"effort": reasoning_effort}
        if verbosity:
            ms.verbosity = verbosity  # 'low' | 'medium' | 'high'
        run_cfg = RunConfig(trace_include_sensitive_data=False, model_settings=ms)
        # TODO: if we decide to bind the user's key to the model provider, do it here
        result = await Runner.run(agent, user_msg, run_config=run_cfg)
        return result.final_output  # type: ignore[attr-defined]
    except Exception:
        # Fallback: run lightweight heuristic fetch without LLM (no API key required)
        lowered = query.lower()
        chosen_sources: list[str] = []
        if any(t in lowered for t in [
            "biomed", "biomedical", "health", "disease", "clinical", "trial", "patient",
            "medicine", "pubmed", "randomized", "cohort", "drug", "therapy"
        ]):
            chosen_sources = ["pubmed", "arxiv"]
        elif any(t in lowered for t in [
            "ml", "machine learning", "deep learning", "neural", "computer science", "ai"
        ]):
            chosen_sources = ["arxiv", "openalex"]
        else:
            chosen_sources = ["arxiv", "openalex"]

        sources: Dict[str, str] = {"arxiv": "No results", "pubmed": "No results", "openalex": "No results"}
        used: list[str] = []
        try:
            if "arxiv" in chosen_sources:
                sources["arxiv"] = _search_arxiv(query, max_results)
                used.append("arxiv")
            if "pubmed" in chosen_sources:
                sources["pubmed"] = _search_pubmed(query, max_results)
                used.append("pubmed")
            if "openalex" in chosen_sources:
                sources["openalex"] = _search_openalex(query, max_results)
                used.append("openalex")
        except Exception:
            # Best-effort even if one source fails
            pass

        summary = (
            f"Fetched up to {max_results} results from {', '.join(used) if used else 'no'} sources."
        )
        return ResearchOutput(sources=sources, used_sources=used, summary=summary)
    finally:
        clear_research_budget()


