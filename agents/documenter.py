"""Documenter Agent — generates docstrings, changelog, and PR summary.

Returns a dict matching ``backend.models.schemas.Documentation``:
    {
        "docstrings": str,   # Generated docstrings for changed functions
        "changelog": str,    # CHANGELOG.md entry for this PR
        "summary": str       # Plain-English summary of changes and rationale
    }
"""

from __future__ import annotations

import json
import re

from crewai import Agent, Crew, Task

from agents.base import get_crewai_llm
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_MAX_DIFF_CHARS = 4000
_MAX_PATCH_CHARS = 4000


def _parse_json_response(raw: str, context: str = "") -> dict:
    """Strip markdown fences and parse JSON."""
    clean = re.sub(r"```(?:json)?", "", raw).strip().rstrip(",")
    try:
        return json.loads(clean)
    except json.JSONDecodeError as exc:
        logger.error(
            "JSON parse error in %s — raw:\n%s\nerror: %s",
            context or "response",
            raw[:500],
            exc,
        )
        raise ValueError(f"Documenter returned non-JSON output: {exc}") from exc


def run_documenter(patches: list, pr_data: dict, review_report: dict) -> dict:
    """Run the Documenter Agent to produce documentation for a reviewed PR.

    Parameters
    ----------
    patches:
        List of patch dicts produced by ``run_fixer``.
    pr_data:
        Original PR data dict.
    review_report:
        The ``ReviewReport`` dict from ``run_reviewer``.

    Returns
    -------
    dict
        A ``Documentation``-shaped dict with ``docstrings``, ``changelog``,
        and ``summary``.
    """
    logger.info(
        "run_documenter: generating documentation for PR '%s' with %d patch(es)",
        pr_data.get("title", "N/A"),
        len(patches),
    )

    llm = get_crewai_llm()

    # Format patches for the prompt
    patches_text = ""
    for i, patch in enumerate(patches, 1):
        patches_text += (
            f"\n--- Patch {i}: {patch.get('file', '?')} ---\n"
            f"ORIGINAL:\n{patch.get('original', '')}\n"
            f"FIXED:\n{patch.get('fixed', '')}\n"
            f"EXPLANATION: {patch.get('explanation', '')}\n"
        )
    patches_text = patches_text[:_MAX_PATCH_CHARS] or "(no patches)"

    # Format findings for context
    findings_text = "\n".join(
        f"  [{f.get('severity','?').upper()}] {f.get('file','?')}:"
        f"{f.get('line','?')} — {f.get('description','?')}"
        for f in review_report.get("findings", [])
    ) or "  (no findings)"

    diff_truncated = pr_data.get("diff", "")[:_MAX_DIFF_CHARS]

    documenter = Agent(
        role="Technical Writer and Documentation Specialist",
        goal=(
            "Produce clear, professional documentation for code changes: "
            "accurate docstrings, a structured CHANGELOG entry, and a concise "
            "plain-English summary that any developer can understand."
        ),
        backstory=(
            "You are a senior technical writer with 10 years of experience documenting "
            "open-source Python projects. You write Google-style docstrings, clear CHANGELOG "
            "entries following Keep-a-Changelog conventions, and executive summaries that "
            "explain both the what and the why of every change. "
            "You always respond with valid JSON and nothing else."
        ),
        llm=llm,
        verbose=True,
    )

    task = Task(
        description=f"""Generate comprehensive documentation for the following PR changes.

PR Title   : {pr_data.get('title', 'N/A')}
Author     : {pr_data.get('author', 'N/A')}
Base branch: {pr_data.get('base_branch', 'N/A')}
PR URL     : {pr_data.get('pr_url', 'N/A')}

Issues found during review:
{findings_text}

Patches applied:
{patches_text}

Original diff (truncated to {_MAX_DIFF_CHARS} chars):
{diff_truncated}

Generate the following three documents:

1. DOCSTRINGS — Write Google-style Python docstrings for every function or class
   that was modified in the patches. Include Args, Returns, Raises sections where
   relevant. Format as a single multi-line string.

2. CHANGELOG — Write a CHANGELOG.md entry following Keep-a-Changelog format:
   ## [Unreleased] — <PR title>
   ### Fixed
   - bullet for each bug fix
   ### Security (if applicable)
   - bullet for each security fix

3. SUMMARY — Write a concise 3–5 sentence plain-English summary explaining:
   - What the PR changes
   - Why the changes were necessary (root cause)
   - What tests or validation confirm the fix is correct

Respond ONLY with a JSON object in this exact format — no markdown, no preamble:
{{
  "docstrings": "<complete docstring text, use \\n for newlines>",
  "changelog": "<complete CHANGELOG entry, use \\n for newlines>",
  "summary": "<3-5 sentence plain-English summary>"
}}

Return ONLY the JSON object — no markdown backticks, no commentary.""",
        agent=documenter,
        expected_output=(
            "A JSON object with keys: docstrings (str), changelog (str), summary (str)"
        ),
    )

    crew = Crew(agents=[documenter], tasks=[task], verbose=True)
    result = crew.kickoff()

    parsed = _parse_json_response(str(result), context="documenter")

    # Safe defaults
    parsed.setdefault("docstrings", "")
    parsed.setdefault("changelog", f"## [Unreleased] — {pr_data.get('title', 'N/A')}\n")
    parsed.setdefault("summary", "Documentation could not be generated.")

    logger.info("run_documenter: documentation complete for PR '%s'", pr_data.get("title", "N/A"))
    return parsed
