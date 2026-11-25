"""Tests for the Python documentation checker."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.check_docs import (
    ROOT,
    SUPERSEDED_STATUS,
    Checker,
    Frontmatter,
    VersionRow,
    effective_effect,
    iter_outside_fences,
    parse_frontmatter,
)

DENY_ACTIONS = ("edit", "subagent", "webfetch", "websearch", "shell")
NARROW_READ_RULES = (
    {"action": "read", "resource": "/tmp/opencode/*", "effect": "deny"},
    {"action": "read", "resource": "/tmp/opencode/pr-*.md", "effect": "allow"},
    {"action": "read", "resource": "*.env", "effect": "deny"},
)


def agent_rules(*extra: dict[str, str]) -> Frontmatter:
    rules: list[dict[str, str]] = [
        {"action": action, "resource": "*", "effect": "deny"} for action in DENY_ACTIONS
    ]
    return {"mode": "subagent", "permissions": [*rules, *extra]}


FRONTMATTER = """---
description: test agent
mode: subagent
permissions:
  - action: edit
    resource: "*"
    effect: deny
  - action: shell
    resource: "*"
    effect: deny
---
Agent body.
"""


class TestHelpers(unittest.TestCase):
    def test_iter_outside_fences(self) -> None:
        text = "before\n```python\n[bad](missing.md)\n```\nafter\n"
        lines = [line for _, line in iter_outside_fences(text)]
        self.assertEqual(lines, ["before", "after"])

    def test_parse_frontmatter_nested_permissions(self) -> None:
        parsed = parse_frontmatter(FRONTMATTER)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        data, body = parsed
        self.assertEqual(data["mode"], "subagent")
        permissions = data["permissions"]
        self.assertIsInstance(permissions, list)
        assert isinstance(permissions, list)
        self.assertEqual(permissions[0], {"action": "edit", "resource": "*", "effect": "deny"})
        self.assertEqual(body.strip(), "Agent body.")


class TestChecker(unittest.TestCase):
    def test_repository_is_consistent(self) -> None:
        checker = Checker(ROOT)
        checker.run()
        self.assertEqual(checker.findings, [])

    def test_effective_effect_uses_last_match(self) -> None:
        rules = [
            {"action": "edit", "resource": "*", "effect": "deny"},
            {"action": "edit", "resource": "*", "effect": "allow"},
        ]
        self.assertEqual(effective_effect(rules, "edit", "model.yaml"), "allow")
        self.assertIsNone(effective_effect(rules, "read", "model.yaml"))

    def test_agent_narrow_review_permissions_pass(self) -> None:
        data = agent_rules(
            {"action": "edit", "resource": "/tmp/opencode/pr-*.md", "effect": "allow"},
            *NARROW_READ_RULES,
        )
        checker = Checker(ROOT)
        checker.check_agent(ROOT / ".opencode/agents/pr-reviewer.md", data)
        self.assertEqual(checker.findings, [])

    def test_agent_late_broad_allow_is_rejected(self) -> None:
        data = agent_rules(
            {"action": "edit", "resource": "*", "effect": "allow"},
            *NARROW_READ_RULES,
        )
        checker = Checker(ROOT)
        checker.check_agent(ROOT / ".opencode/agents/pr-reviewer.md", data)
        messages = [finding.message for finding in checker.findings]
        self.assertIn("pr-reviewer.md must deny edit", messages)

    def test_agent_broad_tmp_allow_is_rejected(self) -> None:
        data = agent_rules(
            {"action": "edit", "resource": "/tmp/opencode/**", "effect": "allow"},
            {"action": "read", "resource": "/tmp/opencode/*", "effect": "deny"},
            {"action": "read", "resource": "/tmp/opencode/**", "effect": "allow"},
            {"action": "read", "resource": "*.env", "effect": "deny"},
        )
        checker = Checker(ROOT)
        checker.check_agent(ROOT / ".opencode/agents/pr-reviewer.md", data)
        messages = [finding.message for finding in checker.findings]
        self.assertIn("pr-reviewer must not edit files outside /tmp/opencode/pr-*.md", messages)
        self.assertIn("pr-reviewer must not read files outside /tmp/opencode/pr-*.md", messages)

    def test_agent_must_deny_secret_reads(self) -> None:
        data = agent_rules(
            {"action": "edit", "resource": "/tmp/opencode/pr-*.md", "effect": "allow"},
            {"action": "read", "resource": "/tmp/opencode/*", "effect": "deny"},
            {"action": "read", "resource": "/tmp/opencode/pr-*.md", "effect": "allow"},
        )
        checker = Checker(ROOT)
        checker.check_agent(ROOT / ".opencode/agents/pr-reviewer.md", data)
        messages = [finding.message for finding in checker.findings]
        self.assertIn("pr-reviewer.md must deny secret file reads", messages)

    def test_stale_ai_docs_detected(self) -> None:
        from tools import build_ai_docs

        stale = dict(build_ai_docs.build())
        first = next(iter(stale))
        stale[first] += "\n"
        with patch.object(build_ai_docs, "build", return_value=stale):
            checker = Checker(ROOT)
            checker.check_ai_docs_freshness()
        self.assertEqual([finding.code for finding in checker.findings], ["DOC170"])

    def test_freshness_skipped_without_package(self) -> None:
        missing = ModuleNotFoundError("No module named 'eggpipe'", name="eggpipe")
        with patch("tools.check_docs._load_builder", side_effect=missing):
            checker = Checker(ROOT)
            checker.check_ai_docs_freshness()
        self.assertEqual(checker.findings, [])

    def test_freshness_reports_broken_import(self) -> None:
        missing = ModuleNotFoundError("No module named 'pydantic'", name="pydantic")
        with patch("tools.check_docs._load_builder", side_effect=missing):
            checker = Checker(ROOT)
            checker.check_ai_docs_freshness()
        self.assertEqual([finding.code for finding in checker.findings], ["DOC171"])

    def test_freshness_skipped_for_foreign_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checker = Checker(Path(directory))
            checker.check_ai_docs_freshness()
            self.assertEqual(checker.findings, [])

    def test_broken_relative_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = root / "README.md"
            document.write_text("[broken](./missing.md)\n", encoding="utf-8")
            checker = Checker(root)
            checker.check_links(document, document.read_text(encoding="utf-8"))
            self.assertEqual([finding.code for finding in checker.findings], ["DOC103"])

    def test_unknown_diagnostic_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirements = root / "engineering/requirements"
            design = root / "engineering/system-design"
            requirements.mkdir(parents=True)
            design.mkdir(parents=True)
            (requirements / "v1.0.md").write_text("EG000\n", encoding="utf-8")
            (design / "index.md").write_text("EG999\n", encoding="utf-8")
            checker = Checker(root)
            checker.current_version = "1.0"
            checker.check_diagnostic_codes()
            codes = [finding.code for finding in checker.findings]
            self.assertIn("DOC160", codes)

    def test_hardcoded_package_version_in_prose(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "eggpipe"\nversion = "1.2.3"\n', encoding="utf-8"
            )
            (root / "README.md").write_text("Стадия: Eggpipe 1.2.3.\n", encoding="utf-8")
            checker = Checker(root)
            checker.check_package_version_literals()
            self.assertEqual([finding.code for finding in checker.findings], ["DOC161"])

    def test_package_version_in_code_fence_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "eggpipe"\nversion = "1.2.3"\n', encoding="utf-8"
            )
            (root / "README.md").write_text(
                "```text\n$ eggpipe format list\n1.2.3\n```\n", encoding="utf-8"
            )
            checker = Checker(root)
            checker.check_package_version_literals()
            self.assertEqual(checker.findings, [])

    def test_package_version_in_allowlisted_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "eggpipe"\nversion = "1.2.3"\n', encoding="utf-8"
            )
            (root / "CHANGELOG.md").write_text("## [1.2.3] - 2026-11-20\n", encoding="utf-8")
            checker = Checker(root)
            checker.check_package_version_literals()
            self.assertEqual(checker.findings, [])

    def test_package_version_in_allowlisted_historical_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "eggpipe"\nversion = "1.2.3"\n', encoding="utf-8"
            )
            archive = root / "engineering/backlog-archive.md"
            spikes = root / "engineering/spikes"
            archive.parent.mkdir(parents=True)
            spikes.mkdir(parents=True)
            archive.write_text("| B-001 | done | релиз 1.2.3 |\n", encoding="utf-8")
            (spikes / "2026-11-23-cache.md").write_text("Сделано в 1.2.3.\n", encoding="utf-8")
            checker = Checker(root)
            checker.check_package_version_literals()
            self.assertEqual(checker.findings, [])

    def test_hardcoded_package_version_in_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "eggpipe"\nversion = "1.2.3"\n', encoding="utf-8"
            )
            workflow = root / ".github/workflows/pages.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("run: mike deploy 1.2.3 latest\n", encoding="utf-8")
            checker = Checker(root)
            checker.check_package_version_literals()
            self.assertEqual([finding.code for finding in checker.findings], ["DOC161"])

    def test_invalid_pyproject_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text('[project]\nname = "eggpipe"\n', encoding="utf-8")
            checker = Checker(root)
            self.assertIsNone(checker.package_version())
            self.assertEqual([finding.code for finding in checker.findings], ["DOC162"])

    def test_superseded_version_requires_deny(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "opencode.json").write_text(
                '{"$schema": "https://opencode.ai/config.json", "permissions": []}',
                encoding="utf-8",
            )
            checker = Checker(root)
            checker.versions = [
                VersionRow(version="1.0", status=SUPERSEDED_STATUS, link="./v1.0.md", line=2)
            ]
            checker.current_version = "1.1"
            checker.check_opencode_json()
            codes = [finding.code for finding in checker.findings]
            self.assertIn("DOC136", codes)


if __name__ == "__main__":
    unittest.main()
