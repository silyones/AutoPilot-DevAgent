"""GitHub integration tool for AutoPilot Dev.

Fetches PR metadata, unified diffs, and per-file patches from GitHub using
the PyGithub library authenticated with GITHUB_TOKEN from settings.

Cache key convention (wired in Phase 7 — Redis):
    f"pr_diff:{owner}_{repo}_{pr_number}"
"""

from __future__ import annotations

import re
from typing import Any

from github import Github, GithubException, RateLimitExceededException, UnknownObjectException
from github.PullRequest import PullRequest
from github.Repository import Repository

from backend.config import settings
from backend.utils.logger import get_logger
from cache.redis_client import cache_get, cache_set

logger = get_logger(__name__)

# ── GitHub client (single shared instance) ────────────────────────────────────
_gh_client: Github | None = None


def _get_client() -> Github:
    """Return (and lazily create) the authenticated GitHub client."""
    global _gh_client  # noqa: PLW0603
    if _gh_client is None:
        logger.info("Initialising GitHub client with provided token.")
        _gh_client = Github(settings.github_token, per_page=100)
    return _gh_client


# ── URL parsing ───────────────────────────────────────────────────────────────

# Matches both:
#   https://github.com/owner/repo/pull/123
#   github.com/owner/repo/pull/123
_PR_URL_PATTERN = re.compile(
    r"(?:https?://)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)",
    re.IGNORECASE,
)


def parse_pr_url(pr_url: str) -> tuple[str, int]:
    """Parse a GitHub PR URL and return (``"owner/repo"``, pr_number).

    Accepted formats
    ----------------
    - ``https://github.com/owner/repo/pull/123``
    - ``http://github.com/owner/repo/pull/123``
    - ``github.com/owner/repo/pull/123``

    Raises
    ------
    ValueError
        If the URL does not match the expected GitHub PR format.

    Examples
    --------
    >>> parse_pr_url("https://github.com/tiangolo/fastapi/pull/1")
    ('tiangolo/fastapi', 1)
    """
    pr_url = pr_url.strip().rstrip("/")
    match = _PR_URL_PATTERN.search(pr_url)
    if not match:
        raise ValueError(
            f"Invalid GitHub PR URL: {pr_url!r}. "
            "Expected format: https://github.com/<owner>/<repo>/pull/<number>"
        )
    owner = match.group("owner")
    repo = match.group("repo")
    pr_number = int(match.group("number"))
    repo_full = f"{owner}/{repo}"
    logger.debug("Parsed PR URL → repo=%s pr_number=%d", repo_full, pr_number)
    return repo_full, pr_number


# ── Diff builder ──────────────────────────────────────────────────────────────

def _build_unified_diff(pr: PullRequest) -> str:
    """Concatenate all per-file patches into a single unified diff string."""
    parts: list[str] = []
    for f in pr.get_files():
        header = f"diff --git a/{f.filename} b/{f.filename}"
        patch = f.patch or ""  # patch can be None for binary files
        parts.append(f"{header}\n{patch}")
    return "\n".join(parts)


def _build_files_changed(pr: PullRequest) -> list[dict[str, Any]]:
    """Return a structured list of every file touched by the PR."""
    files: list[dict[str, Any]] = []
    for f in pr.get_files():
        files.append(
            {
                "filename": f.filename,
                "status": f.status,          # "added" | "modified" | "deleted" | "renamed"
                "additions": f.additions,
                "deletions": f.deletions,
                "patch": f.patch or "",      # None for binary files → empty string
            }
        )
    return files


# ── Main public function ──────────────────────────────────────────────────────

def fetch_pr_data(pr_url: str) -> dict[str, Any]:
    """Fetch complete PR data from GitHub.

    Parameters
    ----------
    pr_url:
        A full GitHub PR URL, e.g. ``https://github.com/owner/repo/pull/42``.

    Returns
    -------
    dict with keys:
        ``pr_number``, ``title``, ``description``, ``author``,
        ``base_branch``, ``head_branch``, ``diff``, ``files_changed``, ``pr_url``

    Raises
    ------
    ValueError
        If the URL cannot be parsed.
    RuntimeError
        If the repo or PR cannot be found, or the API rate limit is exceeded.

    Cache key (Phase 7 — Redis)
    ---------------------------
    ``f"pr_diff:{owner}_{repo}_{pr_number}"``
    """
    logger.info("Fetching PR data for URL: %s", pr_url)

    # ── 1. Parse URL ──────────────────────────────────────────────────────────
    try:
        repo_full, pr_number = parse_pr_url(pr_url)
    except ValueError as exc:
        logger.error("URL parse error: %s", exc)
        raise

    owner, repo_name = repo_full.split("/", 1)

    # ── Cache check ───────────────────────────────────────────────────────────
    cache_key = f"pr_diff:{owner}_{repo_name}_{pr_number}"
    cached = cache_get(cache_key)
    if cached:
        logger.info("Cache hit for PR %d (%s) — skipping GitHub API call", pr_number, repo_full)
        return cached

    client = _get_client()

    # ── 2. Fetch repository ───────────────────────────────────────────────────
    try:
        logger.info("Fetching repository: %s", repo_full)
        repo: Repository = client.get_repo(repo_full)
    except RateLimitExceededException:
        msg = "GitHub API rate limit exceeded. Try again later or check your GITHUB_TOKEN."
        logger.error(msg)
        raise RuntimeError(msg) from None
    except UnknownObjectException:
        msg = f"Repository not found: {repo_full!r}. Check the URL and your GITHUB_TOKEN permissions."
        logger.error(msg)
        raise RuntimeError(msg) from None
    except GithubException as exc:
        msg = f"GitHub API error while fetching repo {repo_full!r}: {exc.status} {exc.data}"
        logger.error(msg)
        raise RuntimeError(msg) from exc

    # ── 3. Fetch pull request ─────────────────────────────────────────────────
    try:
        logger.info("Fetching PR #%d from %s", pr_number, repo_full)
        pr: PullRequest = repo.get_pull(pr_number)
    except RateLimitExceededException:
        msg = "GitHub API rate limit exceeded while fetching PR. Try again later."
        logger.error(msg)
        raise RuntimeError(msg) from None
    except UnknownObjectException:
        msg = f"PR #{pr_number} not found in {repo_full!r}."
        logger.error(msg)
        raise RuntimeError(msg) from None
    except GithubException as exc:
        msg = f"GitHub API error while fetching PR #{pr_number}: {exc.status} {exc.data}"
        logger.error(msg)
        raise RuntimeError(msg) from exc

    # ── 4. Build diff and files_changed ───────────────────────────────────────
    try:
        logger.info("Building unified diff for PR #%d …", pr_number)
        diff = _build_unified_diff(pr)
        files_changed = _build_files_changed(pr)
    except RateLimitExceededException:
        msg = "GitHub API rate limit exceeded while fetching diff."
        logger.error(msg)
        raise RuntimeError(msg) from None
    except GithubException as exc:
        msg = f"GitHub API error while fetching diff: {exc.status} {exc.data}"
        logger.error(msg)
        raise RuntimeError(msg) from exc

    # ── 5. Assemble result ────────────────────────────────────────────────────
    result: dict[str, Any] = {
        "pr_number": pr.number,
        "title": pr.title,
        "description": pr.body or "",
        "author": pr.user.login if pr.user else "unknown",
        "base_branch": pr.base.ref,
        "head_branch": pr.head.ref,
        "diff": diff,
        "files_changed": files_changed,
        "pr_url": pr_url,
    }

    logger.info(
        "Successfully fetched PR #%d — title=%r files_changed=%d diff_chars=%d",
        pr_number,
        result["title"],
        len(files_changed),
        len(diff),
    )

    # ── Cache store ───────────────────────────────────────────────────────────
    cache_set(cache_key, result, ttl_seconds=3600)

    return result
