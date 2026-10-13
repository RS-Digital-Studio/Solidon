"""Was die Auswahl ins Bild holt, ist rechts die scharfe Handlung (FD-34).

Eine Auswahl, die eine Maßgruppe ins Bild bringt (``FeaturePanel.request_in_view``),
nimmt denselben Weg wie der Knopf *Im Bild einstellen*: Die Handlung der Maßgruppe
wird auch im Merkmalfenster scharf. An einer erkannten Bohrung blieb bis dahin
*Merkmal verschieben* scharf und rechts offen, während im Bild die Maße von
*Bohrung ändern* standen — genau der Zustand, den der Knopf schon vermied.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QApplication

from app.core.bootstrap import load_operations
from app.core.geom.mesh import read_mesh
from app.core.perceive import features
from app.core.types import Feature
from app.ui.panels import FeaturePanel
from tests import qt_roots
from tests.helpers import MESHES

#: Baut die Merkmalfenster ab (``tests/qt_roots.py``); pytest sammelt die Fixture
#: unter diesem Namen im Modul.
roots = qt_roots.roots


def _recognised_hole() -> tuple[str, Feature]:
    """Eine Bohrung, die kein Schritt gebohrt hat: erkannt an ``plate_holes.stl``."""
    found = features.detect(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"))
    return next((key, value) for key, value in found.items() if value.kind == "hole")


def _panel_at_the_hole(roots: Callable[[Any], Any]) -> tuple[FeaturePanel, list[str]]:
    """Das Merkmalfenster an der erkannten Bohrung und die Handlungen, die es ins Bild holt."""
    load_operations()
    identifier, hole = _recognised_hole()
    panel = roots(FeaturePanel())
    asked: list[str] = []
    panel.inViewRequested.connect(lambda op, _values: asked.append(op))
    panel.show_feature(identifier, hole)
    assert panel.preview_values()[0] == "move_feature", (
        "vorher ist die erste Handlung scharf, nicht die im Bild — sonst prüft der Test nichts"
    )
    return panel, asked


def test_a_selection_that_brings_measures_into_view_arms_their_action(
    qt_app: QApplication, roots: Callable[[Any], Any]
) -> None:
    """Die Auswahl holt *Bohrung ändern* ins Bild, und rechts ist dieselbe Handlung scharf."""
    panel, asked = _panel_at_the_hole(roots)

    panel.request_in_view()

    assert asked == ["resize_hole"]
    assert panel.preview_values()[0] == "resize_hole", "im Bild und rechts dieselbe Handlung"


def test_the_selection_takes_the_way_of_the_button(
    qt_app: QApplication, roots: Callable[[Any], Any]
) -> None:
    """Auswahl und Knopf *Im Bild einstellen* sind ein Weg: dieselbe Handlung ins Bild,
    dieselbe scharf."""
    by_selection, selected = _panel_at_the_hole(roots)
    by_button, clicked = _panel_at_the_hole(roots)

    by_selection.request_in_view()
    by_button._in_view.click()

    assert selected == clicked == ["resize_hole"]
    assert by_selection.preview_values()[0] == by_button.preview_values()[0] == "resize_hole"


def test_the_armed_action_still_comes_first(
    qt_app: QApplication, roots: Callable[[Any], Any]
) -> None:
    """Wer *Zum Langloch ziehen* scharfgeschaltet hat, bekommt dessen Maße ins Bild,
    nicht die der ersten Handlung mit Weg dorthin — und es bleibt scharf."""
    panel, asked = _panel_at_the_hole(roots)
    slot = next(key for key, entry in panel._runs.items() if entry.op == "slot_hole")
    panel._arm(slot)

    panel.request_in_view()

    assert asked == ["slot_hole"]
    assert panel.preview_values()[0] == "slot_hole"
