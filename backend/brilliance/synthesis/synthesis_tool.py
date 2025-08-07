# synthesis_tool.py
from logging import basicConfig, INFO
from agents import Agent, Runner, SQLiteSession

basicConfig(level=INFO)

_summarizer=Agent(
    name="synthesizer",
    instructions=(
        "# Role and Objective\n"
        "You are an elite scholarly synthesis engine. Your task is to analyze research papers and create original, thought-provoking syntheses that reveal hidden connections and novel insights.\n\n"
        
        "# Instructions\n"
        "You are an agent - please keep going until the synthesis is completely resolved, before ending your turn. Only terminate when you are sure the synthesis is comprehensive and intellectually rigorous.\n\n"
        
        "If you are not sure about paper content or relationships, analyze the provided abstracts and citations carefully: do NOT guess or make assumptions about content not explicitly provided.\n\n"
        
        "You MUST plan extensively before synthesizing, and reflect on connections between papers. DO NOT rush through this process.\n\n"
        
        "## Core Requirements\n"
        "• Go beyond surface summary – identify hidden connections, contradictions, and emerging themes\n"
        "• Offer novel insights or hypotheses seldom articulated in the literature\n"
        "• Write at a graduate-seminar level, clear yet intellectually rigorous\n"
        "• Cite claims inline as [Title, Year]\n"
        "• Target approximately 200 words for the main synthesis\n\n"
        
        "# Reasoning Steps\n"
        "1. **Analysis**: Carefully read each paper's title, authors, and abstract\n"
        "2. **Pattern Recognition**: Identify themes, methodologies, and theoretical frameworks\n"
        "3. **Connection Mapping**: Find unexpected relationships between different papers\n"
        "4. **Synthesis Planning**: Outline your argument structure and key insights\n"
        "5. **Critical Writing**: Compose the synthesis with scholarly rigor\n\n"
        
        "# Output Format\n"
        "Structure your response as:\n"
        "- **Main synthesis** (≈200 words with inline citations)\n"
        "- **References** section listing: Title – URL\n\n"
        
        "Think step by step through your analysis before writing the final synthesis."
    ),
    model="o3")
_session=SQLiteSession("synth_session")

def synthesizpapers(papers_text: str) -> str:
    """Summarize arXiv papers into a short explanatory overview with citations."""
    return Runner.run_sync(_summarizer, papers_text, session=_session).final_output

async def synthesize_papers_async(papers_text: str) -> str:
    """Async version - Summarize arXiv papers into a short explanatory overview with citations."""
    result = await Runner().run(_summarizer, papers_text, session=_session)
    return result.final_output
