"""Der Erzeugen-Dialog, und Weg 3, der durch ihn die Szene erreicht (§2.2,
§27).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from app.core.backends.mesh import ScriptedMeshBackend
from app.core.scene import History
from app.core.scene.project import new_project
from app.ui.generate_dialog import GenerateDialog
from app.ui.session import Session

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def generator() -> ScriptedMeshBackend:
    return ScriptedMeshBackend(fallback=(MESHES / "cube_clean.stl").read_bytes())


def ok(dialog: GenerateDialog):
    return dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)


def finish(dialog: GenerateDialog, qt_app: QApplication) -> None:
    """Den Arbeiter zu Ende laufen lassen, ohne den Oberflächen-Thread zu
    blockieren.
    """
    dialog._start()
    worker = dialog._worker
    assert worker is not None
    worker.wait(5000)
    qt_app.processEvents()


def test_without_a_generator_the_dialog_explains_itself(qt_app: QApplication) -> None:
    """§27: kein Backend heißt ausgegraut und ein Satz, kein versteckter
    Menüeintrag.
    """
    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    dialog.prompt.setText("eine Figur")

    assert not dialog.available
    assert not ok(dialog).isEnabled()
    assert "ComfyUI" in dialog.state.text()


def test_the_button_waits_for_something_to_generate_from(
    qt_app: QApplication, generator: ScriptedMeshBackend
) -> None:
    dialog = GenerateDialog(backend=generator)

    assert not ok(dialog).isEnabled(), "nothing said yet"
    dialog.prompt.setText("eine kleine Figur")
    assert ok(dialog).isEnabled()


def test_generating_hands_back_a_body(qt_app: QApplication, generator: ScriptedMeshBackend) -> None:
    dialog = GenerateDialog(backend=generator)
    dialog.prompt.setText("eine kleine Figur")
    dialog.seed.setValue(12)

    finish(dialog, qt_app)

    assert dialog.result_mesh is not None
    assert dialog.result_mesh.mesh.triangle_count == 12
    assert generator.calls == [("eine kleine Figur", 12)]
    assert dialog.result() == GenerateDialog.DialogCode.Accepted


def test_a_failure_stays_in_the_dialog(qt_app: QApplication) -> None:
    """Ein Generator, der Nein sagt, ist kein Absturz — der Satz landet im
    Dialog.
    """
    dialog = GenerateDialog(backend=ScriptedMeshBackend(answers={"etwas": b"solid x\n"}))
    dialog.prompt.setText("etwas anderes")

    finish(dialog, qt_app)

    assert dialog.result_mesh is None
    assert dialog.buttons.isEnabled(), "the dialog can be tried again"
    assert "Mesh" in dialog.state.text()


def test_the_session_puts_a_generated_body_on_the_stack(
    qt_app: QApplication, generator: ScriptedMeshBackend
) -> None:
    """Die Oberfläche fügt Weg 3 nichts hinzu — sie ruft den Kern und zeichnet
    neu.
    """
    session = Session()
    session.project = new_project("centauri-carbon-2", "petg")
    session.history = History(session.project.document)
    result = generator.text_to_mesh("eine kleine Figur", seed=3)

    object_id = session.add_generated(result)
    session.wait_for_idle()

    assert [entry.op for entry in session.project.document.ops] == ["load", "repair"]
    assert object_id == "obj_1"
    assert session.project.document.sources["src_1"].kind == "generated"
