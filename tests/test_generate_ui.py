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


class CountingBackend:
    """Ein Generator, der mitzählt, wie oft jemand nach ihm fragt.

    ``ComfyBackend.available`` ist ein Socket mit Zeitlimit; hier kostet die
    Frage nichts, und genau darum lässt sich zählen, wie oft sie gestellt
    wird.
    """

    def __init__(self, available: bool = False) -> None:
        self._available = available
        self.asked = 0

    @property
    def id(self) -> str:
        return "counting"

    @property
    def available(self) -> bool:
        self.asked += 1
        return self._available

    def text_to_mesh(self, prompt: str, **kwargs: object) -> object:
        raise AssertionError("dieser Test erzeugt nichts")

    def image_to_mesh(self, image: bytes, **kwargs: object) -> object:
        raise AssertionError("dieser Test erzeugt nichts")


def test_without_a_generator_the_dialog_explains_itself(qt_app: QApplication) -> None:
    """§27: kein Backend heißt ausgegraut und ein Satz, kein versteckter
    Menüeintrag.
    """
    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    dialog.prompt.setText("eine Figur")

    assert not dialog.available
    assert not ok(dialog).isEnabled()
    assert "ComfyUI" in dialog.state.text()


def test_the_missing_generator_comes_with_the_way_to_one(qt_app: QApplication) -> None:
    """Regel 17: Der Satz sagte, was fehlt, und bot nichts an.

    „Es läuft kein Generator" stand allein über einem gesperrten Knopf — der
    Weg zu ComfyUI steht in der Liste der zusätzlichen Programme, und von hier
    führte nichts dorthin. Der Chat macht es an derselben Stelle richtig
    („Chat einrichten …" neben dem Hinweis).

    **Ein gezeigter Dialog wird hier auch wieder geschlossen**, und das ist
    keine Kosmetik: Ohne die beiden ``finally``-Zweige brachte dieser Test den
    Prozess um — nicht sich selbst, sondern die *nächste* Datei. Gemessen,
    dreimal von drei: ``pytest tests/test_generate_ui.py tests/test_way_three.py``
    starb nach fünfzehn Sekunden mit einer Zugriffsverletzung im Teardown, und
    mit diesem einen Test ausgenommen lief dasselbe Paar grün. Wer ein Fenster
    zeigt und fallen lässt, hinterlässt eine Zustellung an ein Objekt, das der
    Speicherbereiniger schon abgeräumt hat; das nächste ``processEvents`` liefert
    sie aus. Das ist derselbe Absturz, den die Aufräumhilfe in
    ``tests/conftest.py`` jagt — hier ist er in fünfzehn Sekunden reproduzierbar.
    """
    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    try:
        dialog.show()
        qt_app.processEvents()

        assert dialog.setup.isVisibleTo(dialog), "ohne Generator steht der Weg dorthin da"
        asked: list[bool] = []
        dialog.setupRequested.connect(lambda: asked.append(True))
        dialog.setup.click()
        assert asked, "und der Knopf sagt es dem Fenster"
    finally:
        dialog.wait_for_workers()
        dialog.close()
        dialog.deleteLater()

    ready = GenerateDialog(backend=ScriptedMeshBackend(fallback=b"solid x\n"))
    try:
        ready.show()
        qt_app.processEvents()
        assert not ready.setup.isVisibleTo(ready), "wo nichts fehlt, steht auch kein Weg"
    finally:
        ready.wait_for_workers()
        ready.close()
        ready.deleteLater()
    qt_app.processEvents()


def test_the_dialog_can_be_asked_to_let_go_of_its_worker(qt_app: QApplication) -> None:
    """Es gibt zwei Wege, einen Dialog loszuwerden: schließen und wegräumen.

    ``reject`` wartet seit je — das ist der erste Weg, und das Schließkreuz
    führt über ihn. Der zweite ist der Weg der Suite: Dort wird ein Dialog
    weggeräumt, und die Aufräumhilfe in ``tests/conftest.py`` sucht dafür
    ``wait_for_workers`` an jedem obersten Fenster. Wer den Namen nicht führt,
    bleibt unbeachtet, mit laufendem Arbeiter — und ein Thread, der sein
    Fenster überlebt, nimmt den Prozess mit. Eine Generierung läuft Minuten.
    """
    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    try:
        assert hasattr(dialog, "wait_for_workers"), "die Aufräumhilfe sucht diesen Namen"
        dialog.wait_for_workers()  # ohne Arbeiter tut es nichts und wirft nicht

        seen: list[int] = []
        dialog._worker = _StubWorker(seen)  # type: ignore[assignment]
        dialog.wait_for_workers()
        assert seen, "auf einen laufenden Arbeiter wird gewartet"
    finally:
        dialog.deleteLater()


class _StubWorker:
    """Nur die zwei Methoden, die ``wait_for_workers`` wirklich ruft."""

    def __init__(self, seen: list[int]) -> None:
        self._seen = seen

    def isRunning(self) -> bool:  # noqa: N802 — Qt gibt den Namen vor
        return not self._seen

    def wait(self, timeout_ms: int = 0) -> bool:
        self._seen.append(timeout_ms)
        return True


def test_typing_does_not_ask_the_generator_again(qt_app: QApplication) -> None:
    """Gemessen: jeder Tastendruck kostete 510 ms im Qt-Hauptthread.

    ``available`` hing an ``textChanged``, und ``ComfyBackend.available``
    öffnet einen Socket mit einer Viertelsekunde Zeitlimit. „Halter" zu tippen
    hieß drei Sekunden stehendes Fenster — und das war der Zustand, in dem der
    Dialog aufgeht, wenn kein Generator läuft: genau dann, wenn jemand ihn zum
    ersten Mal öffnet und nichts versteht (§2.8).
    """
    backend = CountingBackend()
    dialog = GenerateDialog(backend=backend)
    after_build = backend.asked
    assert after_build == 1, "einmal beim Aufgehen, das ist der Anlass"

    for letter in "Halter mit 32 mm":
        dialog.prompt.insert(letter)

    assert backend.asked == after_build, "und danach kein weiteres Mal"

    dialog.recheck()
    assert backend.asked == after_build + 1, "wer nachsieht, sieht wirklich nach"


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


def test_the_way_out_stays_open_while_it_runs(
    qt_app: QApplication, generator: ScriptedMeshBackend
) -> None:
    """Ein Lauf dauert Minuten — und sperrte ausgerechnet den Abbrechen-Knopf.

    ``self.buttons.setEnabled(False)`` traf die ganze Leiste, also auch den
    einen Knopf, den man waehrend einer Rechnung braucht. Der Ausgang selbst
    war fertig gebaut (``reject`` wartet auf den Thread), unerreichbar war nur
    sein Knopf: Es blieb Esc, eine Taste, die niemand sucht, solange der Weg
    daneben grau dasteht (§2.8).
    """
    dialog = GenerateDialog(backend=generator)
    dialog.prompt.setText("eine kleine Figur")
    dialog._running(True)

    cancel = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
    assert cancel.isEnabled(), "waehrend des Laufs ist Abbrechen der einzige sinnvolle Knopf"
    assert not ok(dialog).isEnabled(), "zweimal erzeugen waere zwei Arbeiter"

    # Und Weitertippen darf ihn nicht wieder aufmachen: ``_update_state`` haengt
    # am Textfeld, und das bleibt bedienbar. Vorher deckte die gesperrte Leiste
    # das zu, statt es zu verhindern.
    dialog.prompt.setText("eine kleine Figur mit Hut")
    assert not ok(dialog).isEnabled(), "wer weitertippt, startet sonst einen zweiten Wurf"

    dialog._running(False)
    assert ok(dialog).isEnabled(), "danach geht es weiter"
