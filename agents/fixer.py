"""Fixer Agent — generates code patches for issues found by the Reviewer.

Returns a dict:
    {
        "patches": [
            {
                "file": str,
                "original": str,
                "fixed": str,
                "explanation": str
            }
        ]
    }

When ``previous_error`` is non-empty the prompt includes the prior failure so
the agent can self-correct — this is the self-improving retry loop behaviour.
"""

from __future__ import annotations


from crewai import Agent, Crew, Task

from agents.base import get_crewai_llm, kickoff_with_retry, parse_agent_json
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_MAX_DIFF_CHARS = 6000



def run_fixer(
    review_report: dict,
    pr_data: dict,
    previous_error: str = "",
) -> dict:
    """Run the Fixer Agent to generate patches for all reported issues.

    Parameters
    ----------
    review_report:
        The ``ReviewReport`` dict produced by ``run_reviewer``.
    pr_data:
        The original PR data dict (used for diff context).
    previous_error:
        When non-empty, the test output from the previous failed fix attempt.
        The agent is prompted to try a different approach.

    Returns
    -------
    dict
        ``{"patches": [{"file", "original", "fixed", "explanation"}, ...]}``
    """
    findings = review_report.get("findings", [])
    logger.info(
        "run_fixer: generating patches for %d finding(s)%s",
        len(findings),
        f" (retry — previous error supplied)" if previous_error else "",
    )

    llm = get_crewai_llm()

    # ── Self-improvement block ─────────────────────────────────────────────────
    retry_context = ""
    if previous_error:
        retry_context = f"""
IMPORTANT — YOUR PREVIOUS FIX ATTEMPT FAILED:
{previous_error}

You MUST try a completely different approach this time.
Do NOT repeat the same fix. Reason carefully about the root cause before writing code.
"""

    # Format findings for the prompt
    findings_text = "\n".join(
        f"  [{i+1}] [{f.get('severity','?').upper()}] {f.get('file','?')}:"
        f"{f.get('line','?')} — {f.get('description','?')} (category: {f.get('category','?')})"
        for i, f in enumerate(findings)
    ) or "  (no findings provided)"

    diff_truncated = pr_data.get("diff", "")[:_MAX_DIFF_CHARS]

    fixer = Agent(
        role="Senior Python Bug Fixer",
        goal=(
            "Fix every reported bug with minimal, surgical code changes. "
            "Preserve existing logic unless it is the direct cause of the bug. "
            "Always reason step-by-step before writing the patch."
        ),
        backstory=(
            "You are a principal engineer with deep expertise in Python, security hardening, "
            "and defensive programming. You write clear, minimal patches and always explain "
            "your reasoning. You think through edge cases carefully before committing to a fix. "
            "You always respond with valid JSON and nothing else."
        ),
        llm=llm,
        verbose=True,
    )

    task = Task(
        description=f"""You are fixing bugs in a GitHub PR.
{retry_context}
PR Title : {pr_data.get('title', 'N/A')}
Author   : {pr_data.get('author', 'N/A')}

Issues to fix:
{findings_text}

Relevant diff context (truncated to {_MAX_DIFF_CHARS} chars):
{diff_truncated}

Instructions:
1. Think step-by-step about each issue before writing the fix (chain-of-thought).
2. Write MINIMAL, targeted patches — change only what is necessary.
3. Each patch must specify the exact original code and the corrected replacement.
4. Provide a clear explanation for each patch.

Respond ONLY with a JSON object in this exact format — no markdown, no preamble:
{{
  "patches": [
    {{
      "file": "path/to/file.py",
      "original": "the exact original code snippet (as it appears in the diff)",
      "fixed": "the corrected replacement code",
      "explanation": "why this fix is correct and safe"
    }}
  ]
}}

Return ONLY the JSON object — no markdown backticks, no commentary.""",
        agent=fixer,
        expected_output="A JSON object with a 'patches' list containing file, original, fixed, explanation fields",
    )

    crew = Crew(agents=[fixer], tasks=[task], verbose=True)
    result = kickoff_with_retry(crew)

    parsed = parse_agent_json(str(result), context="fixer")
    parsed.setdefault("patches", [])

    logger.info("run_fixer: produced %d patch(es)", len(parsed["patches"]))
    return parsed
