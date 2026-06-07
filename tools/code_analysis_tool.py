"""Code analysis helpers for the AutoPilot Dev Reviewer agent.

All functions are pure (no side effects) and operate on raw string input
so they can be applied to diff patches, file contents, or arbitrary code
snippets without requiring a language runtime.
"""

from __future__ import annotations

import re

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ── Regex patterns (compiled once at module load) ──────────────────────────────

# Matches Python / JS / TS / Java / Go function / method definitions in a diff.
# Covers:
#   def foo(           — Python
#   async def foo(     — Python async
#   function foo(      — JS/TS
#   const foo = (      — JS/TS arrow (named)
#   func foo(          — Go
#   public void foo(   — Java (simplified)
_FUNC_DEF_PATTERN = re.compile(
    r"""
    (?:
        (?:async\s+)?def\s+          # Python / Python async
        | function\s+                # JS/TS named function
        | (?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\(  # JS/TS arrow
        | func\s+                    # Go
        | (?:public|private|protected|static|\s)+\w+\s+  # Java-style
    )
    (?P<name>[A-Za-z_]\w*)          # function name
    \s*\(
    """,
    re.VERBOSE | re.MULTILINE,
)

# Lines added in a diff start with "+"; strip them for analysis.
_ADDED_LINE_PATTERN = re.compile(r"^\+(?!\+\+)", re.MULTILINE)

# Cyclomatic complexity keywords (branch points)
_BRANCH_KEYWORDS = re.compile(
    r"\b(if|elif|else|for|while|try|except|finally|case|catch|&&|\|\|)\b",
    re.MULTILINE,
)

# ── Security patterns ─────────────────────────────────────────────────────────

_SECURITY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r'(?i)(?:password|passwd|pwd|api_key|apikey|secret|token|auth)\s*=\s*["\'][^"\']{4,}["\']',
            re.MULTILINE,
        ),
        "Possible hardcoded secret/credential detected (password=, api_key=, secret=, etc.)",
    ),
    (
        re.compile(
            r'f["\'].*\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)\b.*["\']',
            re.IGNORECASE | re.MULTILINE,
        ),
        "Potential SQL injection: f-string used to build a SQL query",
    ),
    (
        re.compile(r"\beval\s*\(", re.MULTILINE),
        "Dangerous use of eval() — arbitrary code execution risk",
    ),
    (
        re.compile(
            r"\bos\.system\s*\(|\bsubprocess\.(call|run|Popen)\s*\([^)]*shell\s*=\s*True",
            re.MULTILINE,
        ),
        "Shell injection risk: os.system() or subprocess with shell=True",
    ),
    (
        re.compile(r"\bpickle\.loads?\s*\(", re.MULTILINE),
        "Insecure deserialisation: pickle.load() can execute arbitrary code",
    ),
    (
        re.compile(
            r"\b(?:md5|sha1)\s*\(",
            re.IGNORECASE | re.MULTILINE,
        ),
        "Weak cryptographic hash function used (MD5 or SHA-1)",
    ),
    (
        re.compile(r"\bassert\s+.+,?\s*#?.*\b(auth|permission|access)\b", re.IGNORECASE),
        "Security check using assert — disabled in optimised Python (-O flag)",
    ),
]


# ── Public API ────────────────────────────────────────────────────────────────


def extract_functions(patch: str) -> list[str]:
    """Extract function / method names from a diff patch string.

    Only considers *added* lines (lines beginning with ``+`` that are not
    the ``+++`` header line) so we focus on new or modified code rather
    than the removed context.

    Parameters
    ----------
    patch:
        A unified-diff patch string (as returned by GitHub's API).

    Returns
    -------
    Deduplicated list of function names found in added lines, in order of
    first appearance.
    """
    if not patch:
        logger.debug("extract_functions: empty patch received, returning []")
        return []

    # Extract only the added lines and strip the leading "+"
    added_lines = "\n".join(
        line[1:] for line in patch.splitlines() if _ADDED_LINE_PATTERN.match(line)
    )

    matches = _FUNC_DEF_PATTERN.findall(added_lines)
    # _FUNC_DEF_PATTERN has a single named group "name"; findall returns strings
    # when there is exactly one group.
    seen: set[str] = set()
    unique: list[str] = []
    for name in matches:
        if name and name not in seen:
            seen.add(name)
            unique.append(name)

    logger.debug("extract_functions: found %d unique function(s): %s", len(unique), unique)
    return unique


def count_complexity(code: str) -> int:
    """Estimate cyclomatic complexity as a simple branch-keyword count.

    This is a **proxy metric**, not a true McCabe complexity calculation
    (which requires CFG analysis). It counts the number of branch keywords
    (``if``, ``elif``, ``else``, ``for``, ``while``, ``try``, ``except``,
    ``finally``, ``case``, ``catch``, ``&&``, ``||``) in the provided code
    and adds 1 for the base path.

    Parameters
    ----------
    code:
        Source code or diff patch as a raw string.

    Returns
    -------
    Integer complexity score (≥ 1).
    """
    if not code:
        return 1

    matches = _BRANCH_KEYWORDS.findall(code)
    complexity = 1 + len(matches)
    logger.debug("count_complexity: score=%d (branches=%d)", complexity, len(matches))
    return complexity


def detect_security_patterns(code: str) -> list[str]:
    """Detect common security anti-patterns using regex heuristics.

    Checks for:
    - Hardcoded secrets / credentials (``password=``, ``api_key=``, etc.)
    - SQL injection via f-strings (``f"SELECT ... {var} ..."``")
    - Dangerous ``eval()`` usage
    - Shell injection (``os.system()``, ``subprocess`` with ``shell=True``)
    - Insecure deserialisation via ``pickle``
    - Weak cryptographic hashes (MD5, SHA-1)
    - Security assertions that are disabled in optimised Python

    Parameters
    ----------
    code:
        Source code, diff patch, or any text to scan.

    Returns
    -------
    List of human-readable warning strings. Empty list means no issues found.
    """
    if not code:
        return []

    warnings: list[str] = []
    for pattern, message in _SECURITY_PATTERNS:
        hits = pattern.findall(code)
        if hits:
            # Include the number of occurrences in the warning for clarity
            count = len(hits)
            detail = f"{message} ({count} occurrence{'s' if count > 1 else ''})"
            warnings.append(detail)
            logger.warning("Security pattern detected: %s", detail)

    if not warnings:
        logger.debug("detect_security_patterns: no issues found.")
    else:
        logger.info(
            "detect_security_patterns: %d issue(s) detected.", len(warnings)
        )

    return warnings
