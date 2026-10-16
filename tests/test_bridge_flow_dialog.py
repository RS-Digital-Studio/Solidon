"""*Fluss bei Brücken* im Druckdialog: Prozent zeigen, Prozent annehmen, Anteil übergeben (FD-197).

In 0.6.0 stand die Vorgabe 100 % als „2 %“ da, 90 wurde mit „liegt über der
Obergrenze 2 %“ abgewiesen, und eine 1 ging als 0,01 an den Slicer. Hier am
gebauten Dialog: was das Feld zeigt, was es annimmt und ablehnt, und was danach
in der Datei für den Slicer steht.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
import trimesh
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.export.writer import write_assembly
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings
from app.core.types import SceneObject
from app.ui.labels import BoundedSpin
from app.ui.print_settings_dialog import PrintSettingsDialog
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.ui_helpers import session as session

PATH = "shell.bridge_flow"


@pytest.fixture
def dialog(qt_app: QApplication, session: Session) -> Iterator[PrintSettingsDialog]:
    made = PrintSettingsDialog(session, UiSettings())
    assert made.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    made.show()
    made._lift(PATH)
    qt_app.processEvents()
    yield made
    made.reject()
    made.wait_for_workers()
    made.deleteLater()
    qt_app.processEvents()


def _type(editor: BoundedSpin, text: str) -> None:
    line = editor.lineEdit()
    line.setFocus()
    line.selectAll()
    QTest.keyClicks(line, text)
    QTest.keyClick(line, Qt.Key.Key_Return)


def test_the_field_shows_the_default_as_one_hundred_percent(dialog: PrintSettingsDialog) -> None:
    editor = dialog._editors[PATH]
    assert isinstance(editor, BoundedSpin)
    assert print_settings.read_path(dialog.settings, PATH) == pytest.approx(1.0)
    assert editor.text() == "100 %"
    assert (editor.minimum(), editor.maximum()) == (50.0, 150.0)
    assert editor.singleStep() == pytest.approx(5.0)


def test_ninety_is_taken_and_reaches_the_slicer_file_as_a_ratio(
    dialog: PrintSettingsDialog, tmp_path: Path
) -> None:
    """90 getippt heißt 0,9 im Modell, als eigene Wahl — und ``bridge_flow`` 0,9
    in der Datei, die der Slicer der Orca-Familie liest."""
    editor = dialog._editors[PATH]
    assert isinstance(editor, BoundedSpin)
    _type(editor, "90")
    assert not editor.refusal()
    assert print_settings.read_path(dialog.settings, PATH) == pytest.approx(0.9)
    assert PATH in dialog.settings.chosen

    cube = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    cube.apply_translation((0.0, 0.0, 10.0))
    written, _findings = write_assembly(
        [SceneObject(id="obj_1", name="Wuerfel", mesh=MeshData.of(cube))],
        tmp_path,
        project_name="Bruecke",
        profile=dialog.session.profile,
        settings=dialog.settings,
        flavour="orca",
        for_slicer=False,
    )
    with zipfile.ZipFile(written) as archive:
        plate = json.loads(archive.read("Metadata/project_settings.config"))
    assert float(plate["bridge_flow"]) == pytest.approx(0.9)


@pytest.mark.parametrize(
    ("typed", "bound"), [("200", "Obergrenze 150 %"), ("40", "Untergrenze 50 %")]
)
def test_a_value_outside_names_the_percent_limits(
    dialog: PrintSettingsDialog, typed: str, bound: str
) -> None:
    """Die Ablehnung nennt die Grenze in der Einheit des Felds, und das Modell
    bleibt auf seinem Wert."""
    editor = dialog._editors[PATH]
    assert isinstance(editor, BoundedSpin)
    _type(editor, typed)
    refusal = editor.refusal()
    assert bound in refusal, refusal
    assert typed in refusal
    assert print_settings.read_path(dialog.settings, PATH) == pytest.approx(1.0)
    assert PATH not in dialog.settings.chosen
