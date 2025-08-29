# synthesis_tool.py
from logging import basicConfig, INFO
from agents import Agent, Runner, output_guardrail, GuardrailFunctionOutput, RunContextWrapper, RunConfig
from typing import Any, List, Tuple, Optional
import os

basicConfig(level=INFO)

_INSTRUCTIONS=(
        "# Role & Objective\n"
        "You are an elite, research-grade synthesis engine. Analyze ONLY the provided corpus (papers/notes/figures). Produce a rigorous, decision-ready report rooted in the corpus. No external fetching; no speculation.\n\n"
        "# Output Discipline\n"
        "• OUTPUT ONLY THE FINAL REPORT (no preambles/status/method chatter)\n"
        "• NO TOOL ANNOUNCEMENTS\n"
        "• START DIRECTLY WITH THE SECTIONS BELOW\n\n"
        "# Persistence & Reasoning\n"
        "Complete the synthesis before ending your turn. Do not ask the user to clarify; choose the most reasonable assumption and state it explicitly as the LAST sentence of the Main synthesis. Keep reasoning compact and evidence-anchored; no chain-of-thought exposition.\n\n"
        "# Evidence & Language Rules (cross-domain)\n"
        "• Badge claims inline with evidence tier and, when available, N or setting:\n"
        "  – ML/AI: (benchmark/ablation/simulation/field)\n"
        "  – Biomed: (in vitro/in vivo/observational/RCT/meta-analysis, N=…)\n"
        "  – Physics/Materials/Systems: (theory/simulation/bench/wind-tunnel/field)\n"
        "  – Econ/SocSci: (theory/observational/quasi-experimental/RCT/meta)\n"
        "• Calibrate verbs by tier:\n"
        "  – theory/simulation ⇒ “suggests/indicates/predicts”\n"
        "  – bench/field/RCT ⇒ “measures/demonstrates/observes/estimates”\n"
        "• Causality gate: use “causes” ONLY for RCT/valid IV; otherwise “associated with.”\n"
        "• Use numbers and units wherever possible (%, dB, W/m², s, Hz, mT, m⁻³, eV, params/FLOPs, N, CI/p). Use “≈” for approximations; never “~”.\n"
        "• If a metric (e.g., SOTA delta, S21, Δq″, effect size) is not reported, say “not quantified” rather than implying magnitude.\n"
        "• Cross-regime use must be labeled **analogy** (e.g., fusion edge → atmospheric).\n\n"
        "# Structure & Required Inclusions\n"
        "• Main synthesis must contain, near the top, a one-line OPERATING PARAMETERS line appropriate to the domain, e.g.:\n"
        "  “Operating parameters: {dataset(s)/metric(s) | N/endpoint | frequency/B | temp/pressure | design/identification}.”\n"
        "• End Main synthesis with:\n"
        "  “Assumption: {one explicit assumption}. Confidence: {High/Moderate/Low}.”\n"
        "• Inline citations use short keys that MATCH the “References” keys exactly, e.g., [Short Title, 2024].\n\n"
        "# Length & Focus\n"
        "Target ≈500–600 words for Main synthesis (may exceed only if needed for correctness). Push details to bullets.\n\n"
        "# Final Output Format (exact headers)\n"
        "- **Title** (1 sentence)\n"
        "- **Main synthesis** (inline badges + short-key citations; include Operating parameters line; end with Assumption + Confidence)\n"
        "- **Key tensions & gaps** (3–5 bullets)\n"
        "- **Hypotheses & minimal tests** (max 2 bullets: Hypothesis → minimal Test with endpoint + success criterion)\n"
        "- **References** (Short Title, Year — URL or URL unavailable)\n\n"
        "Produce ONLY these sections in the exact order above. No additional commentary."
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

    # 2) Word budget ~550 (500–600)
    main_wc = _word_count(sections.get("Main synthesis", ""))
    if not (500 <= main_wc <= 600):
        issues.append(f"Main synthesis length {main_wc} words (expected 500–600)")

    # 2a) Require Operating parameters line
    main_text = sections.get("Main synthesis", "")
    if "Operating parameters:" not in main_text:
        issues.append("Main synthesis is missing required 'Operating parameters:' line")

    # 2b) Require Assumption + Confidence at the end
    if "Assumption:" not in main_text or "Confidence:" not in main_text:
        issues.append("Main synthesis must end with 'Assumption:' and 'Confidence:'")

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
    if reasoning_effort is None:
        reasoning_effort = "high"
    if verbosity is None:
        verbosity = "low"
    # Force GPT-5
    chosen_model = "gpt-5"
    summarizer = _build_summarizer(chosen_model)
    try:
        # Standard run config compatible with OpenAI Agents SDK + optional model settings
        from agents import ModelSettings
        ms = ModelSettings()
        # No explicit cap on output tokens; allow the model to emit full 500–600 word Main synthesis + sections
        try:
            ms.max_output_tokens = 100000
        except Exception:
            pass
        if reasoning_effort:
            ms.reasoning = {"effort": reasoning_effort}
        if verbosity:
            ms.verbosity = verbosity
        run_cfg = RunConfig(trace_include_sensitive_data=False, model_settings=ms)
        result = await Runner.run(summarizer, papers_text, session=None, run_config=run_cfg)
        return result.final_output
    except Exception as exc:
        return f"Synthesis unavailable: {exc}"
