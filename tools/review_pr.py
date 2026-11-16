#!/usr/bin/env python3
"""Submit a review comment to a pull request."""

from __future__ import annotations

import argparse
import sys
from urllib.parse import quote

from tools.create_pr import _api, _run_git, _token, repo_from_remote


def _find_pr(repo: str, branch: str, token: str) -> int:
    owner = repo.split("/", 1)[0]
    data = _api(
        "GET",
        f"/repos/{repo}/pulls?head={quote(owner)}:{quote(branch)}&state=open",
        token,
    )
    if not isinstance(data, list) or not data:
        raise SystemExit(f"no open pull request for branch: {branch}")
    return int(data[0]["number"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submit a pull request review")
    parser.add_argument("--pr", type=int, help="pull request number")
    parser.add_argument(
        "--event",
        choices=("COMMENT", "APPROVE", "REQUEST_CHANGES"),
        default="COMMENT",
        help="review event; COMMENT works for your own PRs",
    )
    parser.add_argument("--body", help="review body; reads stdin when omitted")
    args = parser.parse_args(argv)

    body = args.body if args.body is not None else sys.stdin.read()
    if not body.strip():
        raise SystemExit("review body is empty")

    repo = repo_from_remote(_run_git("remote", "get-url", "origin"))
    token = _token()
    number = args.pr or _find_pr(repo, _run_git("rev-parse", "--abbrev-ref", "HEAD"), token)
    result = _api(
        "POST",
        f"/repos/{repo}/pulls/{number}/reviews",
        token,
        {"body": body, "event": args.event},
    )
    if not isinstance(result, dict):
        raise SystemExit("unexpected GitHub API response")
    print(f"review {result.get('id')} on PR #{number}: {result.get('html_url', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
