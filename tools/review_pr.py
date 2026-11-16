#!/usr/bin/env python3
"""Submit a review comment to a pull request."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.create_pr import (
    _api,
    _run_git,
    _token,
    find_open_pr,
    repo_from_remote,
)


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
    if args.pr is not None:
        number = args.pr
    else:
        number = find_open_pr(repo, _run_git("rev-parse", "--abbrev-ref", "HEAD"), token)
        if number is None:
            raise SystemExit("no open pull request for the current branch")
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
