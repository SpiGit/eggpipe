#!/usr/bin/env python3
"""Проверка согласованности документации Eggpipe.

Скрипт не требует внешних зависимостей и рассчитан на Python 3.11+.

Проверяется:
- наличие обязательных файлов и валидность JSON-конфигурации;
- относительные ссылки и структура Markdown;
- реестр версий ТЗ и синхронизация версии в README/System Design/session context;
- запрет правок исторических версий в opencode.json;
- контракты harness: frontmatter агентов, команд и skills;
- базовые термины, диагностические коды и недопустимые флаги.

Запуск:
    python tools/check_docs.py
    python tools/check_docs.py --strict
    python tools/check_docs.py --verbose
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
REQUIRED_FILES = (
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    ".github/workflows/docs.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "AGENTS.md",
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "opencode.json",
    "pyproject.toml",
    "pyrightconfig.json",
    "uv.lock",
    "tools/check_docs.py",
    "tools/check_wheel.py",
    "src/eggpipe/__init__.py",
    "src/eggpipe/py.typed",
    "tests/test_check_docs.py",
    "tests/test_check_wheel.py",
    "tests/test_package.py",
    "docs/requirements/index.md",
    "docs/requirements/v2.0.md",
    "docs/system-design/index.md",
    "docs/adr/0001-composition-merge-semantics.md",
    "docs/adr/0002-type-checker-pyrefly.md",
    "docs/adr/0003-null-semantics.md",
    "docs/adr/0004-ownership-manifest-cleanup.md",
    "docs/adr/0005-library-api.md",
    "docs/adr/0006-format-extension.md",
    "docs/adr/0007-format-inheritance.md",
    "docs/adr/0008-model-units-and-source-layouts.md",
    "docs/adr/0009-global-manifest-ownership.md",
    "docs/adr/0010-decorator-generator-api.md",
    "docs/adr/index.md",
    "docs/index.md",
    "docs/eggpipe.md",
    "docs/plan-v2.md",
    "docs/reviews/2026-11-12-v2-review.md",
    "docs/reviews/2026-11-13-code-quality-review.md",
    "docs/reviews/2026-11-13-patterns-review.md",
    "docs/reference/diagnostics.md",
    "docs/plugin-guide.md",
    "docs/release.md",
    "mkdocs.yml",
    ".opencode/agents/spec-reviewer.md",
    ".opencode/commands/spec-check.md",
    ".opencode/commands/spec-release.md",
    ".opencode/commands/adr-new.md",
    ".opencode/skills/spec-consistency/SKILL.md",
    ".opencode/skills/plugin-contract/SKILL.md",
    ".opencode/skills/clean-code/SKILL.md",
    ".opencode/skills/python-patterns/SKILL.md",
)
FRONTMATTER_DIRS = (
    ".opencode/agents",
    ".opencode/commands",
    ".opencode/skills",
)
FrontmatterValue = str | list[dict[str, str]]
Frontmatter = dict[str, FrontmatterValue]


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    path: Path
    line: int | None
    message: str

    def render(self, root: Path) -> str:
        try:
            path = self.path.relative_to(root)
        except ValueError:
            path = self.path
        location = f"{path}:{self.line}" if self.line else str(path)
        return f"{location}: {self.level}: {self.code} {self.message}"


@dataclass(frozen=True)
class VersionRow:
    version: str
    status: str
    link: str | None
    line: int


def iter_outside_fences(text: str) -> Iterator[tuple[int, str]]:
    """Yield (line_number, line) for lines outside fenced code blocks."""
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield number, line


def clean_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_frontmatter(text: str) -> tuple[Frontmatter, str] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    closing = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing = index
            break
    if closing is None:
        return None

    data: Frontmatter = {}
    current: str | None = None
    for raw in lines[1:closing]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith((" ", "\t")):
            match = re.match(r"^\s+-\s+([A-Za-z0-9_-]+):\s*(.*)$", raw)
            if match and current:
                current_value = data.get(current)
                if not isinstance(current_value, list):
                    current_value = []
                    data[current] = current_value
                key, value = match.group(1), clean_scalar(match.group(2))
                if not current_value or key in current_value[-1]:
                    current_value.append({})
                current_value[-1][key] = value
                continue
            nested = re.match(r"^\s+([A-Za-z0-9_-]+):\s*(.*)$", raw)
            if nested and current:
                current_value = data.get(current)
                if isinstance(current_value, list) and current_value:
                    current_value[-1][nested.group(1)] = clean_scalar(nested.group(2))
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", raw)
        if match:
            key, value = match.group(1), clean_scalar(match.group(2))
            if value:
                data[key] = value
            else:
                data[key] = []
            current = key
    return data, "\n".join(lines[closing + 1 :])


class Checker:
    def __init__(self, root: Path, strict: bool = False) -> None:
        self.root = root
        self.strict = strict
        self.findings: list[Finding] = []
        self.checked_files = 0
        self.versions: list[VersionRow] = []
        self.current_version: str | None = None

    def add(self, level: str, code: str, path: Path, line: int | None, message: str) -> None:
        self.findings.append(Finding(level, code, path, line, message))

    def error(self, code: str, path: Path, line: int | None, message: str) -> None:
        self.add("error", code, path, line, message)

    def warning(self, code: str, path: Path, line: int | None, message: str) -> None:
        self.add("warning", code, path, line, message)

    def read(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            self.error("DOC001", path, None, f"не удалось прочитать файл: {exc}")
            return None

    def markdown_files(self) -> Iterator[Path]:
        for path in sorted(self.root.rglob("*.md")):
            relative = path.relative_to(self.root)
            if any(part in SKIP_PARTS for part in relative.parts):
                continue
            yield path

    def run(self) -> None:
        self.check_required_files()
        for path in self.markdown_files():
            text = self.read(path)
            if text is None:
                continue
            self.checked_files += 1
            prompt_file = ".opencode" in path.parts and (
                "agents" in path.parts or "commands" in path.parts
            )
            self.check_markdown_structure(path, text, require_h1=not prompt_file)
            self.check_links(path, text)
        self.check_versions()
        self.check_version_references()
        self.check_opencode_json()
        self.check_frontmatter()
        self.check_terms()
        self.check_diagnostic_codes()

    def check_required_files(self) -> None:
        for name in REQUIRED_FILES:
            if not (self.root / name).is_file():
                self.error("DOC100", self.root / name, None, "обязательный файл отсутствует")

    def check_markdown_structure(self, path: Path, text: str, require_h1: bool = True) -> None:
        headings = 0
        fence: str | None = None
        for line in text.splitlines():
            match = re.match(r"^\s*(`{3,}|~{3,})", line)
            if match:
                marker = match.group(1)
                if fence is None:
                    fence = marker
                elif marker[0] == fence[0] and len(marker) >= len(fence):
                    fence = None
                continue
            if fence is None and re.match(r"^#\s+\S", line):
                headings += 1
        if fence is not None:
            self.error("DOC101", path, None, "незакрытый блок кода")
        if require_h1 and headings != 1:
            self.error("DOC102", path, None, f"ожидался один заголовок H1, найдено: {headings}")

    def check_links(self, path: Path, text: str) -> None:
        pattern = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
        for number, line in iter_outside_fences(text):
            for match in pattern.finditer(line):
                target = match.group(1).strip("<>")
                if target.startswith("#") or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                    continue
                raw_path = unquote(target.split("#", 1)[0])
                if not raw_path:
                    continue
                resolved = (path.parent / raw_path).resolve()
                if not resolved.exists():
                    self.error("DOC103", path, number, f"битая относительная ссылка: {target}")

    def check_versions(self) -> None:
        index = self.root / "docs/requirements/index.md"
        text = self.read(index)
        if text is None:
            return

        header_seen = False
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if header_seen and self.versions and not stripped.startswith("|"):
                break
            if not stripped.startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 4:
                continue
            if cells[0].lower().startswith("версия"):
                header_seen = True
                continue
            if not header_seen or not re.fullmatch(r"\d+\.\d+", cells[0]):
                continue
            link = re.search(r"\]\(([^)]+)\)", cells[3])
            self.versions.append(
                VersionRow(
                    version=cells[0],
                    status=cells[2].replace("*", ""),
                    link=link.group(1) if link else None,
                    line=number,
                )
            )

        if not self.versions:
            self.error("DOC110", index, None, "не найден реестр версий ТЗ")
            return

        current = [item for item in self.versions if "Актуальная" in item.status]
        if len(current) != 1:
            self.error(
                "DOC111",
                index,
                None,
                f"ожидалась одна актуальная версия ТЗ, найдено: {len(current)}",
            )
        else:
            self.current_version = current[0].version

        for item in self.versions:
            if "Актуальная" not in item.status and "Замещена" not in item.status:
                self.warning(
                    "DOC112",
                    index,
                    item.line,
                    f"неизвестный статус версии {item.version}: {item.status}",
                )
            if not item.link:
                self.error(
                    "DOC113",
                    index,
                    item.line,
                    f"нет ссылки на файл версии {item.version}",
                )
                continue
            target = (index.parent / item.link).resolve()
            if not target.is_file():
                self.error(
                    "DOC114",
                    index,
                    item.line,
                    f"файл версии {item.version} не найден: {item.link}",
                )

    def check_version_references(self) -> None:
        version = self.current_version
        if version is None:
            return
        expected = (
            ("docs/system-design/index.md", rf"Версия документа:\s*{re.escape(version)}\b"),
            ("README.md", rf"v{re.escape(version)}\b"),
            (".session-context.md", rf"\*\*Статус ТЗ:\*\*\s*v{re.escape(version)}\b"),
            ("AGENTS.md", rf"v{re.escape(version)}\.md"),
        )
        for name, pattern in expected:
            path = self.root / name
            text = self.read(path)
            if text is None:
                continue
            if not re.search(pattern, text):
                self.error("DOC120", path, None, f"нет ссылки на актуальную версию v{version}")

    def check_opencode_json(self) -> None:
        path = self.root / "opencode.json"
        text = self.read(path)
        if text is None:
            return
        try:
            config = json.loads(text)
        except json.JSONDecodeError as exc:
            self.error("DOC130", path, exc.lineno, f"невалидный JSON: {exc.msg}")
            return

        if config.get("$schema") != "https://opencode.ai/config.json":
            self.error("DOC131", path, None, "неверный или отсутствующий $schema")

        for index, entry in enumerate(config.get("instructions", [])):
            if (
                isinstance(entry, str)
                and not re.match(r"^https?://", entry)
                and not (self.root / entry).exists()
            ):
                self.error(
                    "DOC132",
                    path,
                    None,
                    f"instructions[{index}] не существует: {entry}",
                )

        rules = config.get("permissions", [])
        if not isinstance(rules, list):
            self.error("DOC133", path, None, "permissions должен быть массивом")
            return
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                self.error("DOC134", path, None, f"permissions[{index}] должен быть объектом")
                continue
            if set(rule) != {"action", "resource", "effect"}:
                self.error(
                    "DOC134",
                    path,
                    None,
                    f"permissions[{index}] должен содержать action/resource/effect",
                )
            elif rule["effect"] not in {"allow", "ask", "deny"}:
                self.error(
                    "DOC135",
                    path,
                    None,
                    f"permissions[{index}]: недопустимый effect {rule['effect']}",
                )

        deny_edits = [
            rule
            for rule in rules
            if isinstance(rule, dict)
            and rule.get("action") == "edit"
            and rule.get("effect") == "deny"
            and isinstance(rule.get("resource"), str)
        ]

        for item in self.versions:
            if "Замещена" not in item.status:
                continue
            relative = f"docs/requirements/v{item.version}.md"
            if not any(fnmatch.fnmatch(relative, rule["resource"]) for rule in deny_edits):
                self.error(
                    "DOC136",
                    path,
                    None,
                    f"историческая версия v{item.version} не защищена deny-правилом",
                )

        if self.current_version:
            relative = f"docs/requirements/v{self.current_version}.md"
            if any(fnmatch.fnmatch(relative, rule["resource"]) for rule in deny_edits):
                self.error(
                    "DOC137",
                    path,
                    None,
                    f"актуальная версия v{self.current_version} ошибочно запрещена",
                )

    def check_frontmatter(self) -> None:
        for directory in FRONTMATTER_DIRS:
            base = self.root / directory
            if not base.is_dir():
                self.error("DOC140", base, None, "каталог harness отсутствует")
                continue
            for path in sorted(base.rglob("*.md")):
                text = self.read(path)
                if text is None:
                    continue
                parsed = parse_frontmatter(text)
                if parsed is None:
                    self.error("DOC141", path, None, "отсутствует или не закрыт frontmatter")
                    continue
                data, body = parsed
                if not data.get("description"):
                    self.error("DOC142", path, None, "во frontmatter нет description")
                if not body.strip():
                    self.error("DOC143", path, None, "пустое тело файла")

                if "agents" in path.parts:
                    self.check_agent(path, data)
                elif "commands" in path.parts:
                    self.check_command(path, data)
                elif "skills" in path.parts:
                    self.check_skill(path, data)

    def check_agent(self, path: Path, data: Frontmatter) -> None:
        if data.get("mode") not in {"primary", "subagent", "all"}:
            self.error("DOC144", path, None, "mode агента должен быть primary/subagent/all")
        if path.name != "spec-reviewer.md":
            return
        permissions = data.get("permissions")
        if not isinstance(permissions, list):
            self.error("DOC145", path, None, "у spec-reviewer нет permissions")
            return
        required = ("edit", "shell", "webfetch", "websearch")
        for action in required:
            if not any(
                isinstance(rule, dict)
                and rule.get("action") == action
                and rule.get("effect") == "deny"
                for rule in permissions
            ):
                self.error("DOC146", path, None, f"spec-reviewer должен запрещать {action}")

    def check_command(self, path: Path, data: Frontmatter) -> None:
        if path.name == "spec-check.md" and data.get("agent") != "spec-reviewer":
            self.error("DOC147", path, None, "spec-check должен запускаться через spec-reviewer")

    def check_skill(self, path: Path, data: Frontmatter) -> None:
        if path.name != "SKILL.md":
            self.error("DOC148", path, None, "skill должен называться SKILL.md")
            return
        skill_id = path.parent.name
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", skill_id):
            self.error("DOC149", path, None, f"некорректный id skill: {skill_id}")

    def check_terms(self) -> None:
        if self.current_version is None:
            return
        current = self.root / f"docs/requirements/v{self.current_version}.md"
        text_files = [
            current,
            self.root / "docs/system-design/index.md",
            self.root / "README.md",
            self.root / "AGENTS.md",
        ]
        for path in text_files:
            text = self.read(path)
            if text is None:
                continue
            for number, line in iter_outside_fences(text):
                if re.match(r"^\s*required_by_default\s*:", line):
                    self.error(
                        "DOC150",
                        path,
                        number,
                        "required_by_default не должен использоваться",
                    )
                if re.search(r"\bmg\s+[^\n]*--format\b(?!-)", line):
                    self.error(
                        "DOC151",
                        path,
                        number,
                        "флаг --format переименован в --output-format",
                    )
                for match in re.finditer(r"\b(Field|Enum)\b", line):
                    self.error(
                        "DOC152",
                        path,
                        number,
                        f"устаревший термин {match.group(1)}; используйте FieldDef/EnumDef",
                    )

        terms = ("ModelDocument", "SourceModel", "ModelSlice", "FieldDef", "EnumDef")
        for path in (current, self.root / "docs/system-design/index.md"):
            text = self.read(path)
            if text is None:
                continue
            for term in terms:
                if term not in text:
                    self.error("DOC153", path, None, f"отсутствует ключевой термин {term}")

    def check_diagnostic_codes(self) -> None:
        if self.current_version is None:
            return
        current = self.root / f"docs/requirements/v{self.current_version}.md"
        text = self.read(current)
        if text is None:
            return
        known = set(re.findall(r"MG\d{3}", text))
        reference = self.root / "docs/reference/diagnostics.md"
        reference_text = self.read(reference)
        if reference_text is not None:
            known |= set(re.findall(r"MG\d{3}", reference_text))
        targets = [
            self.root / "docs/system-design/index.md",
            self.root / "README.md",
            self.root / "AGENTS.md",
        ]
        targets.extend(sorted((self.root / "docs/adr").glob("*.md")))
        targets.extend(sorted((self.root / ".opencode").rglob("*.md")))
        for path in targets:
            text = self.read(path)
            if text is None:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                for code in re.findall(r"MG\d{3}", line):
                    if code not in known:
                        self.error(
                            "DOC160",
                            path,
                            number,
                            f"неизвестный диагностический код {code}",
                        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Проверка согласованности документации")
    parser.add_argument("--root", type=Path, default=ROOT, help="корень репозитория")
    parser.add_argument("--strict", action="store_true", help="считать warnings ошибками")
    parser.add_argument("--verbose", action="store_true", help="показать статистику")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    checker = Checker(root, strict=args.strict)
    checker.run()

    for finding in checker.findings:
        print(finding.render(root))

    errors = sum(finding.level == "error" for finding in checker.findings)
    warnings = sum(finding.level == "warning" for finding in checker.findings)
    exit_errors = errors + (warnings if args.strict else 0)

    if args.verbose:
        print(f"Проверено Markdown-файлов: {checker.checked_files}")

    if exit_errors:
        print(f"Документация не согласована: {errors} ошибок, {warnings} предупреждений.")
        return 1
    print(f"Документация согласована: {checker.checked_files} файлов, {warnings} предупреждений.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
