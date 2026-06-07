"""Reviewer Agent — analyses a PR diff and returns structured findings.

Returns a dict matching ``backend.models.schemas.ReviewReport``:
    {
        "findings": [
            {
                "severity": "high|medium|low|critical",
                "description": str,
                "file": str,
                "line": int | null,
                "category": "logic_bug|security|style|error_handling"
            }
        ],
        "total_issues": int,
        "has_bugs": bool
    }
"""

from __future__ import annotations

import json
import re

from crewai import Agent, Crew, Task

from agents.base import get_crewai_llm
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Maximum diff characters sent to the LLM to stay within context window
_MAX_DIFF_CHARS = 8000


def _parse_json_response(raw: str, context: str = "") -> dict:
    """Strip markdown fences and parse JSON from an LLM response.

    Raises
    ------
    ValueError
        If the cleaned string cannot be decoded as valid JSON.
    """
    # Remove ```json ... ``` or ``` ... ``` fences
    clean = re.sub(r"```(?:json)?", "", raw).strip()
    # Sometimes the LLM wraps output in extra whitespace or trailing commas
    clean = clean.strip().rstrip(",")
    try:
        return json.loads(clean)
    except json.JSONDecodeError as exc:
        logger.error(
            "JSON parse error in %s — raw output:\n%s\nerror: %s",
            context or "response",
            raw[:500],
            exc,
        )
        raise ValueError(f"Reviewer returned non-JSON output: {exc}") from exc


def run_reviewer(pr_data: dict) -> dict:
    """Run the Reviewer Agent against a PR diff.

    Parameters
    ----------
    pr_data:
        Dict returned by ``tools.github_tool.fetch_pr_data``.

    Returns
    -------
    dict
        A ``ReviewReport``-shaped dict with ``findings``, ``total_issues``,
        and ``has_bugs``.
    """
    logger.info(
        "run_reviewer: analysing PR '%s' (%d file(s) changed)",
        pr_data.get("title", "N/A"),
        len(pr_data.get("files_changed", [])),
    )

    llm = get_crewai_llm()

    reviewer = Agent(
        role="Senior Code Reviewer",
        goal=(
            "Find all bugs, security vulnerabilities, and code quality issues "
            "in this PR diff and report them in structured JSON."
        ),
        backstory=(
            "You are an expert software engineer with 15 years of experience in code review. "
            "You specialise in finding logic bugs, security vulnerabilities (OWASP Top 10), "
            "missing error handling, and code style violations. "
            "You always respond with valid JSON and nothing else."
        ),
        llm=llm,
        verbose=True,
    )

    diff_truncated = pr_data.get("diff", "")[:_MAX_DIFF_CHARS]
    files_summary = "\n".join(
        f"  - {f['filename']} ({f['status']}, +{f['additions']}/-{f['deletions']})"
        for f in pr_data.get("files_changed", [])
    ) or "  (no files listed)"

    task = Task(
        description=f"""Review the following GitHub PR diff carefully.

PR Title : {pr_data.get('title', 'N/A')}
Author   : {pr_data.get('author', 'N/A')}
Base     : {pr_data.get('base_branch', 'N/A')} ← {pr_data.get('head_branch', 'N/A')}
Files changed:
{files_summary}

Full Diff (truncated to {_MAX_DIFF_CHARS} chars):
{diff_truncated}

Analyse for:
1. Logic bugs (null pointer, off-by-one, wrong conditions, division by zero)
2. Security issues (injection, hardcoded secrets, unsafe eval, shell injection)
3. Missing error handling (uncaught exceptions, unvalidated inputs)
4. Code complexity issues (deeply nested logic, duplicated code)

Respond ONLY with a JSON object in this exact format — no markdown, no explanation:
{{
  "findings": [
    {{
      "severity": "high|medium|low|critical",
      "description": "clear description of the issue",
      "file": "filename.py",
      "line": 42,
      "category": "logic_bug|security|style|error_handling"
    }}
  ],
  "total_issues": <integer>,
  "has_bugs": true|false
}}

If no issues are found return findings as an empty list and has_bugs as false.
Return ONLY the JSON object — no markdown backticks, no commentary.""",
        agent=reviewer,
        expected_output=(
            "A JSON object with keys: findings (list), total_issues (int), has_bugs (bool)"
        ),
    )

    crew = Crew(agents=[reviewer], tasks=[task], verbose=True)
    result = crew.kickoff()

    parsed = _parse_json_response(str(result), context="reviewer")

    # Ensure required keys are present with safe defaults
    parsed.setdefault("findings", [])
    parsed.setdefault("total_issues", len(parsed["findings"]))
    parsed.setdefault("has_bugs", bool(parsed["findings"]))

    logger.info(
        "run_reviewer: complete — total_issues=%d has_bugs=%s",
        parsed["total_issues"],
        parsed["has_bugs"],
    )
    return parsed
