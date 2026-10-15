"""„Passt bereits auf das Bett“ steht nur, wenn das Teil passt (FD-106).

``_split_done`` setzte den Satz, sobald die Teilung keine Transaktion
lieferte — gleich aus welchem Grund. Fand die Suche keine Trennebene, stand
„Dieses Objekt passt bereits auf das Bett.“ neben der Warnung, dass es über
den Bauraum hinausragt. Geprüft ohne Fenster: Die Methode bekommt einen
Stellvertreter mit genau dem, was sie liest.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.core.split import SplitApplied
from app.core.types import Finding
from app.i18n import tr
from app.ui.main_window import MainWindow

_FITS = "Dieses Objekt passt bereits auf das Bett."


def _done(applied: SplitApplied) -> list[str]:
    said: list[str] = []
    state: Any = SimpleNamespace(
        report=SimpleNamespace(add_findings=lambda findings: None),
        _split_findings=(-1, []),
        _split_turn=None,
        _split_turn_done=0,
        _split_protected=0,
        announce=lambda text, **_kwargs: said.append(str(text)),
        _queue_split_reveal=lambda object_ids: None,
        session=SimpleNamespace(project=SimpleNamespace(document=SimpleNamespace(ops=[]))),
    )
    MainWindow._split_done(state, applied)
    return said


def test_a_split_without_a_plane_says_why_and_not_that_it_fits() -> None:
    blocked = Finding(
        code="split.no_plane",
        severity="warning",
        message="Für dieses Teil war keine brauchbare Trennebene zu finden.",
        object_id="obj_1",
    )
    said = _done(SplitApplied(object_ids=["obj_1"], findings=[blocked]))
    assert said, "die Statuszeile sagt etwas"
    assert tr(_FITS) not in said[-1], said
    assert "Trennebene" in said[-1], said


def test_a_body_that_fits_still_says_so() -> None:
    said = _done(SplitApplied(object_ids=["obj_1"], findings=[]))
    assert said == [tr(_FITS)]
