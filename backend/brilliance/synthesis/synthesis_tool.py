# synthesis_tool.py
from logging import basicConfig, INFO
from agents import Agent, Runner, output_guardrail, GuardrailFunctionOutput, RunContextWrapper, RunConfig
from typing import Any, List, Tuple, Optional
import os

basicConfig(level=INFO)

_INSTRUCTIONS=(
        "# Role and Objective\n"
        "You are an elite scholarly synthesis engine. Analyze ONLY the provided corpus (papers/notes/figures) to produce a rigorous, concise final report. Do not use external sources unless they are included in the corpus.\n\n"

        "# Critical Output Requirements\n"
        "• **OUTPUT ONLY THE FINAL REPORT** — no status updates or process notes\n"
        "• **NO TOOL PREAMBLES** — do not announce actions or progress\n"
        "• **DIRECT TO FINAL ANSWER** — go straight to the structured report\n\n"

        "# Persistence and Reasoning\n"
        "You are an agent — continue until the synthesis is complete before ending your turn. "
        "Do not ask the human to clarify; choose the most reasonable assumption, proceed, and document it at the end of the Main synthesis as an explicit assumption.\n\n"

        "# Context Gathering Approach (Corpus-Only)\n"
        "Work strictly within the provided corpus. Retrieve broadly once, then narrow. "
        "Deduplicate evidence and avoid repeating method descriptions; name a method stack once, then reference it.\n\n"

        "# Evidence and Citation Requirements (Engineering Taxonomy)\n"
        "• Badge each substantive claim with evidence tier: (theory), (simulation), (bench), (wind-tunnel), (arc-jet/ICP), (flight test), (field). Add N or run conditions when available, e.g., (wind-tunnel, h0≈20 MJ/kg).\n"
        "• Use calibrated verbs by tier: "
        "  — (simulation): “indicates/suggests/predicts”; "
        "  — (bench/wind-tunnel/arc-jet/flight): “measures/demonstrates/observes”.\n"
        "• Quantify with units and references: dB (link margin or S21, state baseline), q″ (W/m²), B (T), f (Hz), ne (m⁻³), Te (eV), angle( B, k ). If a study shows field penetration but not S21, write “field penetration observed; link-budget gain unquantified.”\n"
        "• Heat-flux guardrail: do NOT infer “no increase” without reported Δq″; if absent, state “effect on q″ unknown.”\n"
        "• Normalize terminology: replace biology terms like “in vitro” with “in simulation/bench/wind-tunnel/flight” as appropriate.\n"
        "• Citations: short titles + year inline, e.g., [Whistler Window CFD-EM, 2014]. The short title must EXACTLY match the key used in References.\n"
        "• Collapse weak/indirect items into one ‘supporting signals’ sentence when helpful.\n"
        "• Define acronyms once and standardize units; use ≈ for approximate values, never ~.\n\n"

        "# Final Output Format\n"
        "Use Markdown only where semantically correct. Structure the response exactly as:\n"
        "- **Title** (1 sentence)\n"
        "- **Main synthesis** (inline badges + short-title citations; include any explicit assumptions at the end as a single sentence)\n"
        "- **Key tensions & gaps** (3–5 bullets)\n"
        "- **Hypotheses & minimal tests** (max 2 bullets: Hypothesis → Test with model, endpoint, success criterion)\n"
        "- **References** (Title — URL or URL unavailable)\n\n"

        "# Domain Guardrails for RF-through-plasma Topics\n"
        "• Do not claim specific dB recovery unless S21/link margin is given or computable from reported baselines; otherwise, state directional result only.\n"
        "• State frequency–B-field regime (e.g., whistler) and coupling geometry when reported; if not, mark as unspecified.\n"
        "• Separate EM mitigation effects from aerothermal baselines; never attribute thermal changes to EM fields without measured Δq″.\n\n"

        "Produce ONLY these sections in the exact format shown. No additional commentary."
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

    # 2) Word count (informational only; no enforcement)
    main_wc = _word_count(sections.get("Main synthesis", ""))

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
