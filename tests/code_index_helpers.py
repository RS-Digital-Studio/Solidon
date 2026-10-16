"""Gemeinsamer Attrappenbauer für die unabhängigen Auflöser-Gegenproben."""

from __future__ import annotations

import textwrap
from pathlib import Path

from tools import code_facts, code_store
from tools.code_index import Index

#: Der kleine Quellbaum jeder Attrappe: ein gültiges Ziel und ein zweites Modul.
BASE = {
    "app/__init__.py": "",
    "app/mod.py": "def target():\n    return 1\n\ndef read():\n    return target()\n",
    "app/other.py": "def other():\n    return 2\n",
}


def build_index(extra: dict[str, str]) -> Index:
    """Ein kleiner Quellbaum mit gültigem Ziel und den fallbezogenen Ergänzungen."""
    sources = BASE | extra
    return Index(
        Path.cwd(),
        {
            path: code_facts.extract(path, textwrap.dedent(source).lstrip().encode())
            for path, source in sources.items()
        },
    )


def stored_index(root: Path, extra: dict[str, str]) -> Index:
    """Derselbe Baum auf der Platte, über den Ergebnisspeicher gelesen — den Weg von
    :func:`tools.code_index.shared`, den die Wächter am echten Baum gehen."""
    for path, source in (BASE | extra).items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    return code_store.load(root)
