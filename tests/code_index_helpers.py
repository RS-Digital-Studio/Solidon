"""Gemeinsamer Attrappenbauer für die unabhängigen Auflöser-Gegenproben."""

from __future__ import annotations

import textwrap
from pathlib import Path

from tools import code_facts
from tools.code_index import Index


def build_index(extra: dict[str, str]) -> Index:
    """Ein kleiner Quellbaum mit gültigem Ziel und den fallbezogenen Ergänzungen."""
    sources = {
        "app/__init__.py": "",
        "app/mod.py": "def target():\n    return 1\n\ndef read():\n    return target()\n",
        "app/other.py": "def other():\n    return 2\n",
    } | extra
    return Index(
        Path.cwd(),
        {
            path: code_facts.extract(path, textwrap.dedent(source).lstrip().encode())
            for path, source in sources.items()
        },
    )
