"""Тесты Python-чекера документации."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.check_docs import ROOT, Checker, VersionRow, iter_outside_fences, parse_frontmatter

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
Тело агента.
"""


class TestHelpers(unittest.TestCase):
    def test_iter_outside_fences(self) -> None:
        text = "до\n```python\n[bad](missing.md)\n```\nпосле\n"
        lines = [line for _, line in iter_outside_fences(text)]
        self.assertEqual(lines, ["до", "после"])

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
        self.assertEqual(body.strip(), "Тело агента.")


class TestChecker(unittest.TestCase):
    def test_repository_is_consistent(self) -> None:
        checker = Checker(ROOT)
        checker.run()
        self.assertEqual(checker.findings, [])

    def test_broken_relative_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = root / "README.md"
            document.write_text("[битая](./missing.md)\n", encoding="utf-8")
            checker = Checker(root)
            checker.check_links(document, document.read_text(encoding="utf-8"))
            self.assertEqual([finding.code for finding in checker.findings], ["DOC103"])

    def test_unknown_diagnostic_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirements = root / "docs/requirements"
            design = root / "docs/system-design"
            requirements.mkdir(parents=True)
            design.mkdir(parents=True)
            (requirements / "v1.0.md").write_text("MG000\n", encoding="utf-8")
            (design / "index.md").write_text("MG999\n", encoding="utf-8")
            checker = Checker(root)
            checker.current_version = "1.0"
            checker.check_diagnostic_codes()
            codes = [finding.code for finding in checker.findings]
            self.assertIn("DOC160", codes)

    def test_superseded_version_requires_deny(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "opencode.json").write_text(
                '{"$schema": "https://opencode.ai/config.json", "permissions": []}',
                encoding="utf-8",
            )
            checker = Checker(root)
            checker.versions = [
                VersionRow(version="1.0", status="Замещена", link="./v1.0.md", line=2)
            ]
            checker.current_version = "1.1"
            checker.check_opencode_json()
            codes = [finding.code for finding in checker.findings]
            self.assertIn("DOC136", codes)


if __name__ == "__main__":
    unittest.main()
