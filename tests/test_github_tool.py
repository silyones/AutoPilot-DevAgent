"""Tests for tools/github_tool.py and tools/code_analysis_tool.py.

These tests are fully offline — no GitHub API calls are made.
All network-dependent functions are mocked where needed.
"""

from __future__ import annotations

import pytest

from tools.github_tool import parse_pr_url
from tools.code_analysis_tool import detect_security_patterns


# ── parse_pr_url ──────────────────────────────────────────────────────────────

class TestParsePrUrl:
    def test_standard_https_url(self):
        repo, number = parse_pr_url("https://github.com/tiangolo/fastapi/pull/123")
        assert repo == "tiangolo/fastapi"
        assert number == 123

    def test_owner_repo_pull_1(self):
        repo, number = parse_pr_url("https://github.com/owner/repo/pull/1")
        assert repo == "owner/repo"
        assert number == 1

    def test_http_url(self):
        repo, number = parse_pr_url("http://github.com/alice/myproject/pull/42")
        assert repo == "alice/myproject"
        assert number == 42

    def test_url_without_scheme(self):
        repo, number = parse_pr_url("github.com/org/service/pull/99")
        assert repo == "org/service"
        assert number == 99

    def test_trailing_slash_stripped(self):
        repo, number = parse_pr_url("https://github.com/owner/repo/pull/7/")
        assert repo == "owner/repo"
        assert number == 7

    def test_invalid_url_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_pr_url("https://example.com/not-a-pr")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_pr_url("")

    def test_non_github_domain_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_pr_url("https://gitlab.com/owner/repo/pull/1")


# ── detect_security_patterns ──────────────────────────────────────────────────

class TestDetectSecurityPatterns:
    def test_hardcoded_password_flagged(self):
        code = "password = '12345'"
        warnings = detect_security_patterns(code)
        assert len(warnings) >= 1
        assert any("hardcoded" in w.lower() or "secret" in w.lower() or "credential" in w.lower()
                   for w in warnings)

    def test_hardcoded_api_key_flagged(self):
        code = 'api_key = "sk-abc123def456"'
        warnings = detect_security_patterns(code)
        assert len(warnings) >= 1

    def test_eval_flagged(self):
        code = "result = eval(user_input)"
        warnings = detect_security_patterns(code)
        assert len(warnings) >= 1
        assert any("eval" in w.lower() for w in warnings)

    def test_sql_injection_via_fstring_flagged(self):
        code = 'query = f"SELECT * FROM users WHERE id = {user_id}"'
        warnings = detect_security_patterns(code)
        assert len(warnings) >= 1
        assert any("sql" in w.lower() or "injection" in w.lower() for w in warnings)

    def test_pickle_load_flagged(self):
        code = "obj = pickle.loads(data)"
        warnings = detect_security_patterns(code)
        assert len(warnings) >= 1
        assert any("pickle" in w.lower() for w in warnings)

    def test_clean_code_returns_empty_list(self):
        code = """
def add(a: int, b: int) -> int:
    return a + b

result = add(1, 2)
print(result)
"""
        warnings = detect_security_patterns(code)
        assert warnings == []

    def test_empty_string_returns_empty_list(self):
        assert detect_security_patterns("") == []

    def test_multiple_issues_all_reported(self):
        code = """
password = 'hunter2'
result = eval(user_input)
"""
        warnings = detect_security_patterns(code)
        assert len(warnings) >= 2
