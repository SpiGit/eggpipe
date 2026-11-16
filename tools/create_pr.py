#!/usr/bin/env python3
"""Create or update a pull request for the current branch."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

API = "https://api.github.com"


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
    args = parser.parse_args(argv)

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

    title = args.title or default_title(subjects, branch)
    body = args.body or build_body(subjects)
    token = _token()

    existing = find_open_pr(repo, branch, token)
    if existing is not None:
        number = existing
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
