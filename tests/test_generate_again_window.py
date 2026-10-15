"""„Neu erzeugen“ öffnet den Generator mit der Beschreibung des erzeugten Modells (FD-117).

Der Befund „nur eine Haut“ an einem erzeugten Körper bietet *Neu erzeugen*.
Der Handler rief ``_generate(None)``: Der Dialog kam leer, ohne Satz, und wer
noch einmal wollte, tippte die Beschreibung neu. Hier steht danach die alte
Beschreibung im Feld, der nächste Startwert und ein Satz, was geschieht.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import trimesh
from PySide6.QtWidgets import QApplication

from app.core.backends.mesh import GeneratedMesh
from app.core.generate import into_project
from app.core.geom.mesh import MeshData
from app.core.types import Finding
from app.ui.main_window import MainWindow
from app.ui.panels import as_error
from app.ui.session import Session
from app.ui.settings import UiSettings

CUBE = Path(__file__).parent / "data" / "meshes" / "cube_clean.stl"
PROMPT = "eine kleine Figur"


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    built = MainWindow(Session(), UiSettings())
    yield built
    built.release()


def _generated(window: MainWindow) -> str:
    payload = CUBE.read_bytes()
    result = GeneratedMesh(
        mesh=MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0))),
        payload=payload,
        suffix=".stl",
        backend="test",
        prompt=PROMPT,
        seed=7,
    )
    return str(into_project(window.session.project, result).object_id)


def test_the_origin_of_a_generated_body_is_found(window: MainWindow) -> None:
    from app.ui.generate_dialog import generated_origin

    object_id = _generated(window)
    origin = generated_origin(window.session.project.document, object_id)
    assert origin is not None and origin.prompt == PROMPT and origin.seed == 7
    assert generated_origin(window.session.project.document, "obj_99") is None


def test_generate_again_brings_back_the_description(
    window: MainWindow, qt_app: QApplication
) -> None:
    object_id = _generated(window)
    finding = Finding(
        code="scene.thin_skin",
        severity="warning",
        message="Das erzeugte Modell ist nur eine Haut.",
        object_id=object_id,
    )
    window.error_handlers()["generate_again"](as_error(finding, window.session.project.document))
    qt_app.processEvents()
    dialog = window._generator
    assert dialog is not None, "der Generator ist offen"
    try:
        assert dialog.prompt.text() == PROMPT, "die Beschreibung steht wieder da"
        assert dialog.seed.value() == 8, "der nächste Startwert, nicht derselbe Wurf"
        assert dialog.lead.text() and not dialog.lead.isHidden(), "ein Satz sagt, was geschieht"
    finally:
        dialog.discard()
