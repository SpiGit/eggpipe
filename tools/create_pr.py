#!/usr/bin/env python3
"""Create or update a pull request for the current branch."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

API = "https://api.github.com"
MAX_PR_LINES = 500
MAX_PR_FILES = 15
GENERATED_PREFIXES = ("docs/ai/",)
GENERATED_PATTERNS = ("engineering/requirements/v*.md", "uv.lock")
SIZE_EXCEPTION_HEADING = "## Size exception"
SIZE_HEADING = "## Размер"
SIZE_BLOCK_START = "<!-- pr-size:start -->"
SIZE_BLOCK_END = "<!-- pr-size:end -->"
RENAME_SEPARATOR = " => "
BRACE_RENAME = re.compile(r"\{([^{}]*)" + re.escape(RENAME_SEPARATOR) + r"([^{}]*)\}")
PATH_ESCAPES = {"t": "\t", "n": "\n", "r": "\r", '"': '"', "\\": "\\"}


@dataclass(frozen=True)
class DiffSize:
    """Hand-written diff size, excluding generated and full-copy files."""

    lines: int = 0
    files: int = 0
    generated_lines: int = 0
    generated_files: int = 0

    @property
    def too_large(self) -> bool:
        return self.lines > MAX_PR_LINES or self.files > MAX_PR_FILES


def is_generated(path: str) -> bool:
    """Return True for files that do not count towards the PR size budget."""
    return path.startswith(GENERATED_PREFIXES) or any(
        fnmatchcase(path, pattern) for pattern in GENERATED_PATTERNS
    )


def parse_numstat(output: str) -> DiffSize:
    """Parse ``git diff --numstat`` output into a hand-written size summary."""
    lines = files = generated_lines = generated_files = 0
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added, deleted = parts[0], parts[1]
        path = _numstat_path(parts[2])
        count = _numstat_count(added) + _numstat_count(deleted)
        if is_generated(path):
            generated_lines += count
            generated_files += 1
        else:
            lines += count
            files += 1
    return DiffSize(lines, files, generated_lines, generated_files)


def _numstat_path(raw: str) -> str:
    """Return the destination path of a numstat entry, resolving renames and quotes."""
    brace = BRACE_RENAME.search(raw)
    if brace is not None:
        path = f"{raw[: brace.start()]}{brace.group(2)}{raw[brace.end() :]}"
    elif RENAME_SEPARATOR in raw:
        path = raw.rsplit(RENAME_SEPARATOR, 1)[1]
    else:
        path = raw
    return _unquote_path(path)


def _unquote_path(path: str) -> str:
    """Strip the surrounding quotes git adds for special characters and unescape them."""
    if len(path) < 2 or not (path.startswith('"') and path.endswith('"')):
        return path
    unquoted: list[str] = []
    body = path[1:-1]
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\" and index + 1 < len(body):
            index += 1
            escaped = body[index]
            unquoted.append(PATH_ESCAPES.get(escaped, f"\\{escaped}"))
        else:
            unquoted.append(char)
        index += 1
    return "".join(unquoted)


def _numstat_count(value: str) -> int:
    return int(value) if value.isdigit() else 0


def size_warning(size: DiffSize) -> str | None:
    """Return a warning for oversized PRs, or None when the PR fits the budget."""
    if not size.too_large:
        return None
    return (
        f"PR is large: {size.lines} hand-written lines across {size.files} files "
        f"(budget: {MAX_PR_LINES} lines / {MAX_PR_FILES} files).\n"
        f"Generated/full-copy excluded: {size.generated_lines} lines / "
        f"{size.generated_files} files.\n"
        'Split into stacked PRs, or pass --allow-large "reason".'
    )


def _run_git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def repo_from_remote(remote: str) -> str:
    """Extract owner/repo from an SSH or HTTPS GitHub remote."""
    match = re.search(r"[:/]([^/:]+/[^/:]+?)(?:\.git)?$", remote)
    if match is None:
        raise SystemExit(f"cannot parse GitHub repository from remote: {remote}")
    return match.group(1)


def build_body(subjects: list[str]) -> str:
    """Build a short PR body from commit subjects."""
    lines = "\n".join(f"- {subject}" for subject in subjects)
    return f"## Что изменено\n\n{lines}\n"


def default_title(subjects: list[str], branch: str) -> str:
    """Use the first commit subject, or the branch name as a fallback."""
    return subjects[0] if subjects else branch


def size_block(size: DiffSize) -> str:
    """Render the machine-maintained size block."""
    return (
        f"{SIZE_BLOCK_START}\n"
        f"- Hand-written diff: {size.lines} строк, {size.files} файлов\n"
        f"- Generated/full-copy: {size.generated_lines} строк, "
        f"{size.generated_files} файлов\n"
        f"{SIZE_BLOCK_END}"
    )


def upsert_size_block(body: str, size: DiffSize) -> str:
    """Replace the size block or add a new section to the PR body."""
    block = size_block(size)
    if SIZE_BLOCK_START in body and SIZE_BLOCK_END in body:
        start = body.index(SIZE_BLOCK_START)
        end = body.index(SIZE_BLOCK_END, start) + len(SIZE_BLOCK_END)
        return f"{body[:start]}{block}{body[end:]}"
    if SIZE_HEADING in body:
        start = body.index(SIZE_HEADING) + len(SIZE_HEADING)
        following = re.search(r"\n## ", body[start:])
        end = start + following.start() if following is not None else len(body)
        return f"{body[:start]}\n\n{block}{body[end:]}"
    return f"{body.rstrip()}\n\n{SIZE_HEADING}\n\n{block}\n"


def with_size_exception(body: str, reason: str | None) -> str:
    """Append a persistent size-exception section once."""
    if not reason or SIZE_EXCEPTION_HEADING in body:
        return body
    return f"{body.rstrip()}\n\n{SIZE_EXCEPTION_HEADING}\n\n{reason}\n"


def preserve_size_exception(body: str, previous: str) -> str:
    """Carry the size-exception section over from a previous PR body."""
    if SIZE_EXCEPTION_HEADING in body:
        return body
    section = _size_exception_section(previous)
    if section is None:
        return body
    return f"{body.rstrip()}\n\n{section}\n"


def _size_exception_section(body: str) -> str | None:
    """Return the size-exception section of a PR body, without trailing headings."""
    index = body.find(SIZE_EXCEPTION_HEADING)
    if index == -1:
        return None
    rest = body[index + len(SIZE_EXCEPTION_HEADING) :]
    following = re.search(r"\n## ", rest)
    section = rest if following is None else rest[: following.start()]
    return f"{SIZE_EXCEPTION_HEADING}{section}".strip()


def find_open_pr(repo: str, branch: str, token: str) -> int | None:
    """Return the open PR number for a head branch, if any."""
    owner = repo.split("/", 1)[0]
    data = _api(
        "GET",
        f"/repos/{repo}/pulls?head={quote(owner)}:{quote(branch)}&state=open",
        token,
    )
    if isinstance(data, list) and data:
        return int(data[0]["number"])
    return None


def pr_body(repo: str, number: int, token: str) -> str:
    """Return the current body of a pull request, or an empty string."""
    data = _api("GET", f"/repos/{repo}/pulls/{number}", token)
    if not isinstance(data, dict):
        return ""
    body = data.get("body")
    return body if isinstance(body, str) else ""


def _token() -> str:
    token = os.environ.get("GH_TOKEN")
    if token:
        return token
    path = Path.home() / ".config" / "eggpipe" / "github-token"
    if not path.is_file():
        raise SystemExit(f"GitHub token not found: set GH_TOKEN or create {path}")
    return path.read_text(encoding="utf-8").strip()


def _api(method: str, path: str, token: str, payload: dict[str, object] | None = None) -> object:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "eggpipe-pr-tool",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GitHub API {method} {path} failed: {exc.code} {detail}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or update a pull request")
    parser.add_argument("--base", default="main", help="base branch (default: main)")
    parser.add_argument("--title", help="PR title; defaults to the first commit subject")
    parser.add_argument("--body", help="PR body; defaults to commit subjects")
    parser.add_argument("--no-fetch", action="store_true", help="do not fetch the base branch")
    parser.add_argument(
        "--allow-large",
        metavar="REASON",
        help="acknowledge a PR above the size budget",
    )
    args = parser.parse_args(argv)
    if args.allow_large is not None:
        args.allow_large = args.allow_large.strip()
        if not args.allow_large:
            parser.error("--allow-large requires a non-empty reason")

    branch = _run_git("rev-parse", "--abbrev-ref", "HEAD")
    if branch in {"main", "master"}:
        raise SystemExit("refusing to create a PR from the base branch")

    if not args.no_fetch:
        _run_git("fetch", "origin", args.base)

    remote = _run_git("remote", "get-url", "origin")
    repo = repo_from_remote(remote)

    heads = _run_git("ls-remote", "--heads", "origin", branch)
    if not heads:
        raise SystemExit(f"branch is not pushed: {branch}")

    subjects = [
        line
        for line in _run_git("log", "--format=%s", f"origin/{args.base}..HEAD").splitlines()
        if line
    ]
    if not subjects:
        raise SystemExit(f"no commits ahead of origin/{args.base}")

    size = parse_numstat(_run_git("diff", "--numstat", f"origin/{args.base}...HEAD"))
    warning = size_warning(size)
    if warning is not None:
        if args.allow_large:
            print(f"note: {warning}\nreason: {args.allow_large}", file=sys.stderr)
        else:
            print(f"warning: {warning}", file=sys.stderr)

    title = args.title or default_title(subjects, branch)
    token = _token()
    existing = find_open_pr(repo, branch, token)
    previous = pr_body(repo, existing, token) if existing is not None else ""
    body = args.body or (previous if existing is not None else build_body(subjects))
    body = upsert_size_block(body, size)
    if warning is not None:
        body = with_size_exception(body, args.allow_large)

    if existing is not None:
        number = existing
        body = preserve_size_exception(body, previous)
        result = _api(
            "PATCH",
            f"/repos/{repo}/pulls/{number}",
            token,
            {"title": title, "body": body},
        )
    else:
        result = _api(
            "POST",
            f"/repos/{repo}/pulls",
            token,
            {"title": title, "head": branch, "base": args.base, "body": body},
        )

    if not isinstance(result, dict):
        raise SystemExit("unexpected GitHub API response")
    print(f"PR #{result['number']}: {result['html_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
