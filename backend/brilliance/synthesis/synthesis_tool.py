# synthesis_tool.py
from logging import basicConfig, INFO
from agents import Agent, Runner, output_guardrail, GuardrailFunctionOutput, RunContextWrapper, RunConfig
from typing import Any, List, Tuple, Optional
import os

basicConfig(level=INFO)

_INSTRUCTIONS=(
        "# Role and Objective\n"
        "You are an ultra‑capable scholarly synthesis engine. Analyze ONLY the provided paper data to produce a rigorous, decision‑grade final report.\n\n"

        "# Critical Output Requirements\n"
        "• **OUTPUT ONLY THE FINAL REPORT** — no internal notes, no status updates, no method descriptions\n"
        "• **NO PREAMBLES** — do not announce actions; start directly with the required sections\n"
        "• **DIRECT TO FINAL ANSWER** — present the structured report without commentary outside the sections\n\n"

        "# Persistence and Autonomy\n"
        "You are an agent — keep going until the synthesis is complete before ending your turn. "
        "Never stop or hand back to the user when you encounter uncertainty — deduce the most reasonable approach and continue. "
        "Do not ask the human to confirm assumptions — choose the most reasonable assumption, proceed, and note it only in the final output if material.\n\n"

        "# Ultra‑intelligence Protocol (internal)\n"
        "Before writing, run a fast multi‑pass process:\n"
        "- Construct a compact evidence table: design (in vitro/animal/human observational/human RCT/meta‑analysis), N, population, intervention, comparator, dose, duration, primary endpoints, effect direction/magnitude, uncertainty (CI/p).\n"
        "- Normalize units/doses; compute approximate standardized effects or percent deltas when feasible; otherwise encode directionality (↑/↓/↔).\n"
        "- Weigh evidence by hierarchy and sample size; prefer pre‑registered RCTs/meta‑analyses; down‑weight small or biased studies.\n"
        "- Actively surface contradictions; identify heterogeneity sources (dose, matrix, timing, population, measurement, risk of bias).\n"
        "- Separate mechanistic plausibility from clinical outcomes; link mechanisms to effects cautiously.\n"
        "- Extract safety/AE signals and contraindications; if absent, mark Not reported.\n"
        "- Internally calibrate confidence (High/Moderate/Low) for major claims based on design quality, consistency, and effect robustness.\n\n"

        "# Context Gathering Approach\n"
        "Goal: Get enough context fast. Parallelize discovery and stop as soon as you can act.\n"
        "Method:\n"
        "- Start broad, then fan out to focused subqueries.\n"
        "- In parallel, launch varied queries; read top hits per query. Deduplicate paths and cache; don't repeat queries.\n"
        "- Avoid over searching for context. If needed, run targeted searches in one parallel batch.\n"
        "Early stop criteria:\n"
        "- You can name exact content to change.\n"
        "- Top hits converge (≈70%) on one area/path.\n"
        "Loop: Batch search → minimal plan → complete task.\n\n"

        "# Evidence and Citation Requirements\n"
        "• Badge each substantive claim with evidence tier: (in vitro), (animal), (human observational), or (human RCT); add N if available, e.g., (human RCT, N=108).\n"
        "• Quantify when possible: direction and order of magnitude, or at least arrows (e.g., ↑ NO bioavailability in rat model).\n"
        "• Add a **Key tensions & gaps** section (3–5 bullets): contradictions, heterogeneity, and open variables (dose, matrix, timing).\n"
        "• Label extrapolations explicitly as **Hypothesis** and pair each with a minimal test (model, endpoint, success criterion). Keep ≤2 hypotheses (pick the two with highest expected value).\n"
        "• Tighten the **Main synthesis** to ≈260 words (stay within 220–300); move details to bullets.\n"
        "• Citations: short titles + year inline, e.g., [Garlic BP Meta‑analysis, 2025]. The short title must EXACTLY match the key used in References.\n"
        "• Collapse weaker/indirect items (e.g., anti‑sickling, aquaculture, in‑silico) into a single 'supporting signals' sentence to save words.\n"
        "• Normalize symbols: use ≈ for approximate values; do not use ~.\n"
        "• References: full `Title — URL` (or `URL unavailable`).\n"
        "• Define acronyms once and standardize units.\n\n"

        "# Efficiency Discipline\n"
        "Within the provided corpus, scan titles/abstracts → methods/results first; deduplicate studies; avoid redundant rereads; stop internal search once conclusions stabilize.\n\n"

        "# Final Output Format\n"
        "Use Markdown only where semantically correct (lists, inline code). Structure your response as:\n"
        "- **Title** (1 Sentence)\n"
        "- **Main synthesis** (≈260 words; inline badges + short‑title citations)\n"
        "- **Key tensions & gaps** (3–5 bullets)\n"
        "- **Hypotheses & minimal tests** (max 2 bullets: Hypothesis → Test)\n"
        "- **References** (Title — URL)\n\n"

        "Produce ONLY these sections in the exact format shown. No additional commentary, explanations, or status updates."
    )

def _build_summarizer(model: str) -> Agent:
    return Agent(
        name="synthesizer",
        instructions=_INSTRUCTIONS,
        model=model,
        output_guardrails=[synthesis_output_guardrail],
    )
_session=None


# --- Output guardrail: enforce sections, word count, citations, hypotheses cap, symbol normalization ---

def _extract_sections(text: str) -> dict:
    sections = {"Main synthesis": "", "Key tensions & gaps": "", "Hypotheses & minimal tests": "", "References": ""}
    order = list(sections.keys())
    current = None
    lines = text.splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped in sections:
            current = stripped
            continue
        if current:
            sections[current] += (line + "\n")
    return {k: v.strip() for k, v in sections.items()}


def _word_count(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def _parse_references(block: str) -> List[str]:
    keys: List[str] = []
    for line in block.splitlines():
        if not line.strip():
            continue
        # Expect "Title — URL"; take Title as key
        title = line.split(" — ", 1)[0].strip()
        if title:
            keys.append(title)
    return keys


def _find_inline_citations(main_text: str) -> List[str]:
    cites: List[str] = []
    tmp = main_text
    while True:
        start = tmp.find("[")
        if start == -1:
            break
        end = tmp.find("]", start + 1)
        if end == -1:
            break
        content = tmp[start + 1 : end].strip()
        if "," in content:
            short = content.rsplit(",", 1)[0].strip()
        else:
            short = content
        if short:
            cites.append(short)
        tmp = tmp[end + 1 :]
    return cites


@output_guardrail
async def synthesis_output_guardrail(
    ctx: RunContextWrapper[Any], agent: Agent, output: str
) -> GuardrailFunctionOutput:
    issues: List[str] = []
    sections = _extract_sections(output or "")

    # 1) Sections present
    required = ["Main synthesis", "Key tensions & gaps", "Hypotheses & minimal tests", "References"]
    missing = [s for s in required if not sections.get(s)]
    if missing:
        issues.append(f"Missing sections: {', '.join(missing)}")

    # 2) Word budget ~260 (220–300)
    main_wc = _word_count(sections.get("Main synthesis", ""))
    if not (220 <= main_wc <= 300):
        issues.append(f"Main synthesis length {main_wc} words (expected 220–300)")

    # 3) Hypotheses ≤2 bullets
    hyp_block = sections.get("Hypotheses & minimal tests", "")
    hyp_bullets = [ln for ln in hyp_block.splitlines() if ln.strip().startswith("-") or ln.strip().startswith("•")]
    if len(hyp_bullets) > 2:
        issues.append(f"Too many hypotheses ({len(hyp_bullets)} > 2)")

    # 4) Normalize symbols: no '~'
    if "~" in sections.get("Main synthesis", ""):
        issues.append("Use ≈ for approximate values; '~' found")

    # 5) Citations must match reference keys
    ref_keys = set(_parse_references(sections.get("References", "")))
    cites = _find_inline_citations(sections.get("Main synthesis", ""))
    if cites and ref_keys:
        unmatched = [c for c in cites if c not in ref_keys]
        if unmatched:
            issues.append(f"Inline citations not found in References: {', '.join(unmatched)}")

    # Do not hard-fail on formatting issues; surface them as info only
    return GuardrailFunctionOutput(output_info={"issues": issues, "word_count": main_wc}, tripwire_triggered=False)

async def synthesize_papers_async(papers_text: str, model: Optional[str] = None, user_api_key: Optional[str] = None, reasoning_effort: Optional[str] = None, verbosity: Optional[str] = None) -> str:
    """Async version - Summarize arXiv papers into a short explanatory overview with citations."""
    # Force GPT-5
    chosen_model = "gpt-5"
    summarizer = _build_summarizer(chosen_model)
    try:
        # Standard run config compatible with OpenAI Agents SDK + optional model settings
        from agents import ModelSettings
        ms = ModelSettings()
        if reasoning_effort:
            ms.reasoning = {"effort": reasoning_effort}
        if verbosity:
            ms.verbosity = verbosity
        run_cfg = RunConfig(trace_include_sensitive_data=False, model_settings=ms)
        result = await Runner.run(summarizer, papers_text, session=None, run_config=run_cfg)
        return result.final_output
    except Exception as exc:
        return f"Synthesis unavailable: {exc}"
