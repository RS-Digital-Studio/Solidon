"""Sichert die vollständige pytest-Sammlung vor und nach fachlichen Testumzügen."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path
import sys

import pytest

STATE = Path(__file__).resolve().parent
ROOT = STATE.parents[2]
sys.path.insert(0, str(ROOT))


class CollectionSnapshot:
    def __init__(self, label: str) -> None:
        self.label = label

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        entries = []
        for item in session.items:
            fixture_details = {}
            for name, definitions in item._fixtureinfo.name2fixturedefs.items():
                fixture_details[name] = [
                    {
                        "scope": definition.scope,
                        "source": hashlib.sha256(
                            ast.dump(ast.parse(inspect.getsource(definition.func))).encode()
                        ).hexdigest(),
                    }
                    for definition in definitions
                ]
            entries.append(
                {
                    "nodeid": item.nodeid,
                    "name": item.nodeid.split("::", 1)[1],
                    "markers": [
                        {"name": mark.name, "args": mark.args, "kwargs": mark.kwargs}
                        for mark in item.iter_markers()
                    ],
                    "fixtures": sorted(item.fixturenames),
                    "fixture_details": fixture_details,
                }
            )
        (STATE / f"ui-collection-{self.label}.json").write_text(
            json.dumps(entries, indent=2, ensure_ascii=False, default=repr), encoding="utf-8"
        )


if __name__ == "__main__":
    label, *paths = sys.argv[1:]
    raise SystemExit(
        pytest.main(["--collect-only", "-q", *paths], plugins=[CollectionSnapshot(label)])
    )
