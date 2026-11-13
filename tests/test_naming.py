"""Тесты naming-утилит."""

from __future__ import annotations

import pytest

from eggpipe import NamingStyle, transform


@pytest.mark.parametrize(
    ("name", "style", "expected"),
    [
        ("HTTPServer", NamingStyle.SNAKE, "http_server"),
        ("HTTPServer", NamingStyle.KEBAB, "http-server"),
        ("HTTPServer", NamingStyle.PASCAL, "HttpServer"),
        ("HTTPServer", NamingStyle.CAMEL, "httpServer"),
        ("user_profile", NamingStyle.PASCAL, "UserProfile"),
        ("user-profile", NamingStyle.SNAKE, "user_profile"),
    ],
)
def test_transform(name: str, style: NamingStyle, expected: str) -> None:
    assert transform(name, style) == expected
