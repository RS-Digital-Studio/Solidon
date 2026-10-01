"""Der Weg „heruntergeladene STL als STEP weitergeben" im Fenster (P4.0).

Menüort, Exportdialog, Absage mit Knopf, Karte „Formabweichung" — was der Kunde
an der Oberfläche von der Umwandlung sieht. Der Kern ist in
``tests/test_mesh_to_exact.py`` abgenommen; hier steht, dass die Anwendung ihn
erreicht.
"""

# ruff: noqa: E402

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.helpers import exact_kernel

exact_kernel()

from PySide6.QtWidgets import QApplication, QFileDialog

from app.core.errors import CONVERT_TO_EXACT
from app.core.registry import REGISTRY
from app.core.scene.history import OperationDraft
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    # Aufgeräumt wird zentral: ``tests/conftest.py`` wartet nach jedem Test
    # auf die Arbeiter jedes offenen Fensters.
    return MainWindow(Session(), UiSettings())


def _asked(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Der Dateidialog antwortet „abgebrochen“ und merkt sich, was er zeigen sollte."""
    asked: list[tuple[str, str]] = []

    def remember(_parent: Any, _title: str, start: str, filters: str) -> tuple[str, str]:
        asked.append((start, filters))
        return "", ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(remember))
    return asked


def _plate(window: MainWindow) -> str:
    window.open_path(MESHES / "plate_holes.stl")
    assert window.session.wait_for_idle(60_000)
    result = window.session.last_result
    assert result is not None
    return next(iter(result.scene.objects))


def test_the_conversion_stands_next_to_its_opposite(window: MainWindow) -> None:
    """Menüort (§9.5): in der Gruppe *Netz glätten und vereinfachen*, neben
    *Flächenbearbeitung beenden* — offen für ein Netz, grau für einen exakten Körper."""
    from app.ui.labels import kind_requirement

    spec = REGISTRY.get("mesh_to_exact")
    assert spec.category == REGISTRY.get("brep_to_mesh").category == "mesh"
    assert kind_requirement(spec, ["mesh"]) is None
    assert kind_requirement(spec, ["brep"]) == "Der Körper hat bereits echte Flächen und Kanten."


def test_the_export_names_the_way_to_step_for_a_mesh(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An einem Netz steht STEP mit dem Weg dorthin in der Liste — nicht stumm weggelassen,
    und nicht vorgeschlagen, auch wenn das Projekt zuletzt STEP schrieb."""
    _plate(window)
    window.session.set_export_choice("step", None)
    asked = _asked(monkeypatch)

    window.action_export()

    assert len(asked) == 1
    start, filters = asked[0]
    entries = filters.split(";;")
    assert entries[0] == "3MF (*.3mf)" and start.endswith(".3mf")
    hint = entries[-1]
    assert hint.endswith("(*.step)") and "In Flächen und Kanten umwandeln" in hint
    assert "STEP (*.step)" not in entries


def test_the_step_refusal_converts_the_meshes_it_was_about(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Knopf der Absage führt zur Umwandlung — an dem Körper, um den es ging."""
    from app.core.export.writer import _needs_solid

    object_id = _plate(window)
    handlers = window.error_handlers()
    assert CONVERT_TO_EXACT.id in handlers

    called: list[tuple[str, tuple[str, ...]]] = []

    def run(spec: Any, given: Any = None, *, on_bodies: Any = None) -> None:
        called.append((spec.name, tuple(window.object_tree.selected_objects())))

    monkeypatch.setattr(window, "run_operation", run)
    handlers[CONVERT_TO_EXACT.id](_needs_solid())

    assert called == [("mesh_to_exact", (object_id,))]


def test_a_converted_plate_is_exact_reports_itself_and_maps_its_deviation(
    window: MainWindow,
) -> None:
    """Der ganze Weg: umwandeln, exakter Körper im Baum, Befunde im Bericht, die Karte
    „Formabweichung“ misst gegen das Netz, und ein Undo holt das Netz zurück."""
    from app.core.perceive import maps

    object_id = _plate(window)
    assert window.session.apply(
        "Umwandeln", [OperationDraft(op="mesh_to_exact", inputs=(object_id,))]
    )
    assert window.session.wait_for_idle(120_000)
    result = window.session.last_result
    assert result is not None
    entry = result.scene.objects[object_id]
    assert entry.kind == "brep"
    codes = [finding.code for finding in result.scene.report.findings]
    assert "brep.from_mesh" in codes and "brep.from_mesh.deviation" in codes
    deviation = next(
        finding
        for finding in result.scene.report.findings
        if finding.code == "brep.from_mesh.deviation"
    )
    assert maps.map_for(deviation) == "deviation"

    analysis = maps.build("deviation", entry)
    assert analysis.maximum_interval is None
    assert "Umwandlung" in str(analysis.note)

    window.session.undo()
    assert window.session.wait_for_idle(60_000)
    again = window.session.last_result
    assert again is not None and again.scene.objects[object_id].kind == "mesh"
