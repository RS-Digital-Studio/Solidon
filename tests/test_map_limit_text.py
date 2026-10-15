"""Große Dreieckszahlen der abgelehnten Analysekarte stehen in Dreiergruppen (FD-124).

„2103472 Dreiecke, möglich sind 900000“ liest niemand auf einen Blick. Die
Zahlen gehen durch ``labels.count_text``, dieselbe Schreibweise wie in der
Vorschau eines Netzschritts. Ohne Fenster: Die Methode bekommt einen
Stellvertreter mit genau dem, was sie liest.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.ui.labels import count_text
from app.ui.main_window import MainWindow


class _Window:
    """Ein Stellvertreter, auf den ein schwacher Verweis zeigen darf (``weak_slot``)."""


@pytest.mark.parametrize("chosen", ["thickness", "deviation"])
def test_the_refused_map_names_its_numbers_in_groups(chosen: str) -> None:
    said: list[str] = []
    state: Any = _Window()
    state.viewport = SimpleNamespace(set_analysis_map=lambda *args: None)
    state.analysis_bar = SimpleNamespace(
        chosen=lambda: chosen,
        show_problem=lambda text, *args: said.append(str(text)),
    )
    MainWindow._map_too_large(state, 2_103_472, 900_000)
    assert said, "die Leiste sagt etwas"
    assert count_text(2_103_472) in said[-1] and count_text(900_000) in said[-1], said[-1]
    assert "2103472" not in said[-1]
