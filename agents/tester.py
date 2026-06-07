"""Tester Agent — LLM-based test reasoning and simulation.

Since no sandbox (E2E) execution environment is available, the Tester agent:
1. Analyses each patch and reasons about whether it is logically correct.
2. Generates new pytest-style test cases covering the fixed behaviour.
3. Simulates test execution via LLM reasoning and produces a pytest-style output.

Returns a dict matching ``backend.models.schemas.TestReport``:
    {
        "passed": int,
        "failed": int,
        "new_tests_added": int,
        "output": str,   # simulated pytest-style output
        "status": "PASS" | "FAIL"
    }
"""

from __future__ import annotations

import json
import re

from crewai import Agent, Crew, Task

from agents.base import get_crewai_llm
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_MAX_PATCH_CHARS = 5000


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
        raise ValueError(f"Tester returned non-JSON output: {exc}") from exc


def run_tester(patches: list, pr_data: dict) -> dict:
    """Run the Tester Agent to evaluate patches and simulate test results.

    Parameters
    ----------
    patches:
        List of patch dicts produced by ``run_fixer``.
    pr_data:
        Original PR data dict for context.

    Returns
    -------
    dict
        A ``TestReport``-shaped dict.
    """
    logger.info(
        "run_tester: evaluating %d patch(es) for PR '%s'",
        len(patches),
        pr_data.get("title", "N/A"),
    )

    llm = get_crewai_llm()

    # Format patches for the prompt
    patches_text = ""
    for i, patch in enumerate(patches, 1):
        patches_text += (
            f"\n--- Patch {i}: {patch.get('file', '?')} ---\n"
            f"ORIGINAL:\n{patch.get('original', '')}\n\n"
            f"FIXED:\n{patch.get('fixed', '')}\n\n"
            f"EXPLANATION: {patch.get('explanation', '')}\n"
        )
    patches_text = patches_text[:_MAX_PATCH_CHARS] or "(no patches provided)"

    tester = Agent(
        role="Senior QA Engineer",
        goal=(
            "Rigorously evaluate code patches for correctness, safety, and test coverage. "
            "Generate meaningful pytest test cases and simulate their execution results."
        ),
        backstory=(
            "You are a principal QA engineer with 12 years of experience in test-driven development. "
            "You excel at finding edge cases that simple fixes miss, writing clean pytest test cases, "
            "and reasoning about whether a code change truly resolves the root cause without introducing "
            "regressions. You always respond with valid JSON and nothing else."
        ),
        llm=llm,
        verbose=True,
    )

    task = Task(
        description=f"""You are evaluating code patches applied to a GitHub PR.

PR Title: {pr_data.get('title', 'N/A')}
Author  : {pr_data.get('author', 'N/A')}

Patches to evaluate:
{patches_text}

Your job:
1. REASON about each patch — does it correctly fix the bug without introducing regressions?
2. GENERATE pytest test cases that verify the fix works (at least 1 test per patch).
3. SIMULATE test execution — predict pass/fail for each test based on patch correctness.
4. A patch FAILS if:
   - It doesn't address the root cause of the bug.
   - It introduces a new bug or regression.
   - It breaks existing expected behaviour.
   - The fix is syntactically or logically incorrect.

Respond ONLY with a JSON object in this exact format — no markdown, no preamble:
{{
  "passed": <integer — number of tests that would pass>,
  "failed": <integer — number of tests that would fail>,
  "new_tests_added": <integer — number of new test cases you generated>,
  "output": "<simulated pytest output, multi-line string, realistic format>",
  "status": "PASS" | "FAIL"
}}

Set "status" to "PASS" only if all patches are correct and failed == 0.
Set "status" to "FAIL" if any patch is incorrect or introduces a regression.
Return ONLY the JSON object — no markdown backticks, no commentary.""",
        agent=tester,
        expected_output=(
            "A JSON object with keys: passed (int), failed (int), "
            "new_tests_added (int), output (str), status ('PASS'|'FAIL')"
        ),
    )

    crew = Crew(agents=[tester], tasks=[task], verbose=True)
    result = crew.kickoff()

    parsed = _parse_json_response(str(result), context="tester")

    # Safe defaults
    parsed.setdefault("passed", 0)
    parsed.setdefault("failed", 0)
    parsed.setdefault("new_tests_added", 0)
    parsed.setdefault("output", "No test output available.")
    parsed.setdefault("status", "FAIL" if parsed.get("failed", 0) > 0 else "PASS")

    logger.info(
        "run_tester: status=%s passed=%d failed=%d new_tests=%d",
        parsed["status"],
        parsed["passed"],
        parsed["failed"],
        parsed["new_tests_added"],
    )
    return parsed
