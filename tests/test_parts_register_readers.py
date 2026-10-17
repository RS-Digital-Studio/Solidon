"""Wer das Bausteinregister in der Oberfläche liest, liest es zur Aufrufzeit.

**Warum es diese Datei gibt** (Review I, A-4; CS-11). ``from app.core.knowledge.parts
import PARTS`` auf Modulebene bindet über den trägen Export und ``builtin.__getattr__``
dasselbe Objekt wie ``registry.PARTS`` — eine Kopfkopie, die ein Ersatz am Original nie
erreicht. W2 c) sieht sie nicht, weil die Kette des Index an ``builtin.__getattr__`` endet
(CS-45). Katalog und Rezeptdialog lesen das Register deshalb über das Paket zur Aufrufzeit;
dieser Test hält das an beiden fest.
"""

from __future__ import annotations

import pytest

from app.core.knowledge.parts import registry as parts_registry


def _empty_register(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein leeres Register an der Stelle des mitgelieferten — nach dessen Laden."""
    from app.core.knowledge.parts import builtin

    assert builtin.load().has("dowel"), "das mitgelieferte Register kennt den Dübel nicht"
    monkeypatch.setattr(parts_registry, "PARTS", parts_registry.PartRegistry())


def test_the_catalog_reads_the_register_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ui import catalog

    assert catalog.parts_for_feature("hole"), "an einer Bohrung bietet der Katalog nichts an"
    _empty_register(monkeypatch)
    assert catalog.parts_for_feature("hole") == frozenset()


def test_the_recipe_dialog_reads_the_register_at_call_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ui import recipe_dialog

    assert recipe_dialog.taken_name("dowel")
    _empty_register(monkeypatch)
    assert not recipe_dialog.taken_name("dowel"), "der Name gilt im ersetzten Register als frei"
