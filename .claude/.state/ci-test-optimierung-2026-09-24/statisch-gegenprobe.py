"""Belegt, dass die neuen Traversierungsprüfungen die alte Suche ablehnen."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tests import test_directory_docs as docs


def old_maps() -> list[Path]:
    """Bisherige Suche: ausgeschlossene Bäume werden erst nach dem Besuch entfernt."""
    skip = {".venv", "build", "dist", "worktrees", "node_modules"}
    return sorted(
        path
        for path in docs.ROOT.rglob("CLAUDE.md")
        if not skip & set(path.relative_to(docs.ROOT).parts)
        and "3D Drucker" not in path.relative_to(docs.ROOT).parts
    )


def old_documented_folders() -> list[Path]:
    """Bisherige Suche: auch ein ausgeschlossener Vorfahr verdeckt eigenen Code."""
    folders: list[Path] = []
    for path in sorted((docs.ROOT / "app").rglob("*")):
        if not path.is_dir() or docs.EXEMPT & set(path.parts):
            continue
        if any(child.suffix == ".py" for child in path.iterdir() if child.is_file()):
            folders.append(path)
    return folders


for name, previous, current in (
    ("maps", old_maps, docs.maps),
    ("documented_folders", old_documented_folders, docs.documented_folders),
):
    before = previous()
    after = current()
    assert before == after, f"{name}: Mitgliedschaft im bestehenden Repository verändert"
    print(f"{name}: dieselben {len(after)} Bestandspfade, gleiche Reihenfolge")


with tempfile.TemporaryDirectory() as temporary:
    for name, previous, check in (
        ("maps", old_maps, docs.test_excluded_map_trees_are_not_entered),
        (
            "documented_folders",
            old_documented_folders,
            docs.test_foreign_code_trees_are_not_entered,
        ),
    ):
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(docs, name, previous)
            try:
                check(Path(temporary) / name, patch)
            except AssertionError as error:
                assert "excluded directory entered:" in str(error)
                print(f"{name}: alter Weg wie erwartet abgewiesen: {error}")
            else:
                raise AssertionError(f"{name}: Gegenprobe blieb grün")
