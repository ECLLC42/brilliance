"""
query_optimizer_agent.py

Academic query optimizer agent using OpenAI Agents SDK.
Converts natural language research questions into optimized academic keyword searches.
"""

from agents import Agent, Runner
import os
from typing import List, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import re


@dataclass
class OptimizedQuery:
    """Optimized query structure for academic search."""
    keywords: List[str]
    preferred_year: int
    disease_terms: List[str]
    intervention_terms: List[str]
    outcome_terms: List[str]
    study_type_terms: List[str]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'keywords': self.keywords,
            'preferred_year': self.preferred_year,
            'disease_terms': self.disease_terms,
            'intervention_terms': self.intervention_terms,
            'outcome_terms': self.outcome_terms,
            'study_type_terms': self.study_type_terms
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "OptimizedQuery":
        """Create from dictionary for JSON deserialization."""
        return cls(**data)


# Create the academic query optimizer agent
_OPTIMIZER_INSTRUCTIONS = """
Role & Objective
• Role: Expert academic research librarian (Echo).
• Objective: Transform any natural‑language research query into precise, keyword‑rich search terms for scholarly APIs.

Persistence
• Keep going until the optimization step is complete; do not hand back early.
• When uncertain, choose the most reasonable assumption and proceed; note assumptions briefly.

Tool preambles (if tools available)
• Before any tool call: state a one‑line plan.
• After each call: one‑line reflection on adequacy and next step or stop.

Task Guidelines
1) Extract core concepts (topic, population/context, method/approach, outcome).
2) Rewrite vague queries into publication‑ready phrasing.
3) Prefer recency: set preferred_year = current_year − 1.
4) Use domain terminology and common abbreviations.
5) Add highly relevant adjacent keywords not explicitly mentioned.
6) Limit each keyword phrase to ≤ 3 words.
7) Output exactly one JSON object—nothing else.

Output Format
{
  "keywords": ["keyword 1", "keyword 2", "keyword 3", …]
}
"""


def _build_optimizer_agent(model: str) -> Agent:
    return Agent(
        name="academic_query_optimizer",
        instructions=_OPTIMIZER_INSTRUCTIONS,
        model=model,
        output_type=OptimizedQuery,
    )


async def optimize_query_with_agent(user_query: str, model: Optional[str] = None) -> OptimizedQuery:
    """
    Use the academic query optimizer agent to transform natural language into optimized keywords.
    
    Args:
        user_query: Natural language question from user
        
    Returns:
        OptimizedQuery with structured academic keywords
    """
    """Invoke the academic_query_optimizer agent asynchronously and return structured keywords."""
    try:
        # Force GPT-5
        chosen_model = "gpt-5"
        optimizer = _build_optimizer_agent(chosen_model)
        result = await Runner.run(optimizer, user_query)
        # Runner.run returns an AgentRun object; final_output holds the parsed output
        return result.final_output  # type: ignore[attr-defined]
    except Exception as e:
        # Surface error back to caller rather than silently reverting to heuristics
        raise RuntimeError(f"Agent optimizer failed: {e}") from e


def _fallback_optimization(user_query: str) -> OptimizedQuery:
    """Rule-based fallback for keyword extraction with medical term expansion."""
    current_year = datetime.now().year

    # --- Medical abbreviation expansion ---
    medical_abbreviations = {
        "dici": "drug induced cognitive impairment",
        "adr": "adverse drug reaction",
        "ae": "adverse event",
        "cns": "central nervous system",
        "cog": "cognitive",
        "neuro": "neurological",
        "psych": "psychiatric",
        "med": "medication",
        "rx": "prescription",
        "tx": "treatment"
    }
    
    # Expand abbreviations in the query
    expanded_query = user_query.lower()
    for abbrev, full_term in medical_abbreviations.items():
        # Use word boundaries to avoid partial matches
        expanded_query = re.sub(r'\b' + re.escape(abbrev) + r'\b', full_term, expanded_query)

    # --- Heuristic keyword extraction ---
    # 1. Split on non-letters and preserve multi-word terms
    
    # 2. Extract multi-word medical terms
    medical_phrases = [
        "drug induced cognitive impairment",
        "cognitive impairment", 
        "adverse drug reaction",
        "drug toxicity",
        "neurotoxicity",
        "central nervous system",
        "medication side effects",
        "drug adverse effects",
        "cognitive dysfunction",
        "memory impairment",
        "attention deficit",
        "executive dysfunction"
    ]
    
    # Find medical phrases in the query
    found_phrases = []
    for phrase in medical_phrases:
        if phrase in expanded_query:
            found_phrases.append(phrase)
    
    # 3. Extract single words
    words = re.split(r"[^a-zA-Z0-9]+", expanded_query)
    stop_words = {
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if", "in", "into", "is", "it", "no", "not", "of", "on", "or", "such", "that", "the", "their", "then", "there", "these", "they", "this", "to", "was", "will", "with", "what", "most", "recent", "new"
    }
    single_words = [w for w in words if w and w not in stop_words and len(w) > 2]
    
    # 4. Combine phrases and words
    all_keywords = found_phrases + single_words
    
    # 5. Deduplicate while preserving order
    seen = set()
    deduped_keywords: List[str] = []
    for kw in all_keywords:
        if kw not in seen:
            deduped_keywords.append(kw)
            seen.add(kw)

    # 6. Enhanced medical term classification
    disease_terms = [kw for kw in deduped_keywords if any(term in kw for term in [
        "cognitive", "impairment", "dysfunction", "deficit", "neuro", "brain", "memory", "attention"
    ])]
    
    intervention_terms = [kw for kw in deduped_keywords if any(term in kw for term in [
        "drug", "medication", "treatment", "therapy", "induced", "adverse", "side effect", "toxicity"
    ])]
    
    outcome_terms = [kw for kw in deduped_keywords if any(term in kw for term in [
        "impairment", "dysfunction", "deficit", "adverse", "toxicity", "effect"
    ])]

    return OptimizedQuery(
        keywords=deduped_keywords,
        preferred_year=current_year - 1,
        disease_terms=disease_terms,
        intervention_terms=intervention_terms,
        outcome_terms=outcome_terms,
        study_type_terms=["study", "research", "clinical", "trial"]
    )


# Convenience function for synchronous usage
async def optimize_academic_query(user_query: str, model: Optional[str] = None) -> OptimizedQuery:
    """Public API used by the rest of the codebase."""
    return await optimize_query_with_agent(user_query, model)
