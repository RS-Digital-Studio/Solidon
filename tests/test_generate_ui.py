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
    """Ein Wurf, und der Dialog bleibt offen (Konzept P15, E8).

    Bis hierher schloss er sich beim ersten Ergebnis. Die Generierung enthält
    Zufall, und der erste Wurf ist selten der beste — wer ihn nicht mag, musste
    den Dialog neu öffnen und alles noch einmal eintippen.
    """
    dialog = GenerateDialog(backend=generator)
    dialog.prompt.setText("eine kleine Figur")
    dialog.seed.setValue(12)

    finish(dialog, qt_app)

    assert dialog.result_mesh is not None
    assert dialog.result_mesh.mesh.triangle_count == 12
    assert generator.calls == [("eine kleine Figur", 12)]
    assert dialog.result() != GenerateDialog.DialogCode.Accepted, "er bleibt offen"
    assert dialog.tries == [dialog.result_mesh], "der Wurf steht in der Reihe"

    # Erst der zweite Griff übernimmt.
    dialog._accept_or_start()
    assert dialog.result() == GenerateDialog.DialogCode.Accepted


def test_a_second_try_counts_the_seed_up_and_keeps_the_first(
    qt_app: QApplication, generator: ScriptedMeshBackend
) -> None:
    """Meshy rät, mehrere Varianten zu erzeugen und die sauberste zu nehmen.

    Nacheinander und nicht zu viert gleichzeitig: ComfyUI läuft auf derselben
    Grafikkarte, an der jemand sitzt, und vier parallele Läufe wären vierfache
    Wartezeit für drei Ergebnisse, die niemand bestellt hat.

    Der Startwert zählt hoch statt zu würfeln — derselbe Dialog zweimal
    geöffnet liefert dieselbe Reihe (Regel 9).
    """
    dialog = GenerateDialog(backend=generator)
    dialog.prompt.setText("eine kleine Figur")
    dialog.seed.setValue(12)
    finish(dialog, qt_app)

    dialog._try_again()
    dialog._worker.wait(5000)
    qt_app.processEvents()

    assert dialog.seed.value() == 13, "der nächste Startwert, nicht ein zufälliger"
    assert len(dialog.tries) == 2, "der erste Wurf bleibt stehen"
    assert generator.calls == [("eine kleine Figur", 12), ("eine kleine Figur", 13)]

    # Gewählt wird über die Liste; ohne Auswahl gilt der letzte.
    dialog.attempts.setCurrentRow(0)
    assert dialog.chosen() is dialog.tries[0]


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


def test_a_failure_says_why_and_what_helps(qt_app: QApplication) -> None:
    """§2.7 verlangt drei Dinge, und der Dialog zeigte nur eines.

    Der Titel allein — „Die Mesh-Erzeugung konnte nicht starten" — lässt den
    Nutzer stehen. Der Grund steht im Detail, der Ausweg im Vorschlag; beide
    gehören in die Zeile, denn modal geht hier nichts.
    """
    from app.core.backends.mesh import GenerationFailed
    from app.core.errors import CANCEL, OPEN_SETTINGS

    dialog = GenerateDialog(backend=ScriptedMeshBackend(fallback=b"solid x\n"))
    dialog._on_failed(
        GenerationFailed(
            title="Die Mesh-Erzeugung konnte nicht starten.",
            detail="ComfyUI antwortet nicht.",
            suggestions=(OPEN_SETTINGS, CANCEL),
        )
    )

    text = dialog.state.text()
    assert "konnte nicht starten" in text, "was nicht ging"
    assert "antwortet nicht" in text, "warum"
    assert str(OPEN_SETTINGS.label) in text, "was jetzt hilft"
    assert str(CANCEL.label) not in text, "der Ausgang ist kein Rat"


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

    # Drei Schritte, und die Reihenfolge ist keine Geschmacksfrage: was ein
    # Bildmodell liefert, ist auf einen Einheitswürfel normiert und misst als
    # Millimeter gelesen ein bis zwei. Erst auf Maß bringen, dann bereinigen —
    # andersherum verschweißt die Reparatur bei dieser Größe die halbe Lehne.
    assert [entry.op for entry in session.project.document.ops] == [
        "load",
        "fit_to_size",
        "repair",
    ]
    assert object_id == "obj_1"
    assert session.project.document.sources["src_1"].kind == "generated"
