"""Der Erzeugen-Dialog, und Weg 3, der durch ihn die Szene erreicht (§2.2,
§27).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QPushButton

from app.core.backends.mesh import GeneratedMesh
from app.core.errors import OperationCancelled
from app.core.scene import History
from app.core.scene.project import new_project
from app.ui.generate_dialog import GenerateDialog
from app.ui.session import Session
from tests.helpers import FakeMesh
from tests.scripted_backend import ScriptedMeshBackend
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def generator() -> ScriptedMeshBackend:
    return ScriptedMeshBackend(fallback=(MESHES / "cube_clean.stl").read_bytes())


def ok(dialog: GenerateDialog):
    return dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)


def wait_for_readiness(dialog: GenerateDialog, qt_app: QApplication) -> None:
    """Die äußere Generatorfrage beantworten lassen und ihr Signal zustellen."""
    assert dialog.wait_for_readiness(5000)
    qt_app.processEvents()


@pytest.mark.parametrize("image", [None, b"private image"])
@pytest.mark.parametrize("answer", ["back", "escape", "close", "host_change", "storage_failure"])
def test_comfy_disclosure_blocks_the_actual_generator(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, image: bytes | None, answer: str
) -> None:
    """Text und Bild erreichen den Erzeuger erst nach dem gültigen Hinweis für sein Ziel."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog

    from app.core.backends.mesh import ComfyBackend, Readiness
    from app.ui.ai_disclosure import AiDisclosureDialog
    from app.ui.settings import UiSettings

    called: list[object] = []
    backend = ComfyBackend(url="https://comfy.example")
    monkeypatch.setattr(ComfyBackend, "readiness", lambda *args: Readiness.READY)
    monkeypatch.setattr(ComfyBackend, "model_choices", lambda *args: {})

    def send(*args, **kwargs):
        called.append(args)
        raise OperationCancelled

    monkeypatch.setattr(ComfyBackend, "text_to_mesh", send)
    monkeypatch.setattr(ComfyBackend, "image_to_mesh", send)
    monkeypatch.setattr("app.ui.ai_disclosure.save_settings", lambda settings: None)

    def respond(notice: AiDisclosureDialog) -> int:
        notice.show()
        qt_app.processEvents()
        if answer == "escape":
            QTest.keyClick(notice, Qt.Key.Key_Escape)
        elif answer == "close":
            notice.close()
        elif answer == "back":
            notice.back_button.click()
        else:
            notice._content_was_shown = True
            if answer == "host_change":
                backend.url = "https://other.example"
                monkeypatch.setattr(
                    "app.ui.ai_disclosure.save_settings", lambda settings: Path("settings.json")
                )
            return int(QDialog.DialogCode.Accepted)
        return int(notice.result())

    monkeypatch.setattr(AiDisclosureDialog, "exec", respond)
    dialog = GenerateDialog(backend=backend, settings=UiSettings())
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.prompt.setText("private description")
        dialog._image = image
        dialog._start()
        if dialog._worker is not None:
            assert dialog._worker.wait(5000)
        assert called == []
        assert dialog._worker is None
        assert not dialog._busy
    finally:
        dialog.release()
        dialog.deleteLater()


@pytest.mark.parametrize("image", [None, b"private image"])
@pytest.mark.parametrize("address", ["http://127.0.0.1:8188", "https://comfy.example"])
def test_comfy_sends_only_after_the_separate_notice_and_reuses_its_record(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, image: bytes | None, address: str
) -> None:
    """Ein wirklicher Hinweis öffnet nur den gezeigten Erzeugerweg samt Startwert."""
    from PySide6.QtTest import QTest

    from app.core.backends.mesh import ComfyBackend, Readiness
    from app.ui.ai_disclosure import (
        AiDisclosureDialog,
        remember_disclosure,
        target_for_comfy,
        target_for_ollama,
    )
    from app.ui.settings import UiSettings

    settings = UiSettings()
    remember_disclosure(settings, target_for_ollama("https://chat.example"))
    calls: list[tuple[str, object, int]] = []
    shown: list[object] = []
    backend = ComfyBackend(url=address)
    monkeypatch.setattr(ComfyBackend, "readiness", lambda *args: Readiness.READY)
    monkeypatch.setattr(ComfyBackend, "model_choices", lambda *args: {})
    monkeypatch.setattr(
        "app.ui.ai_disclosure.save_settings", lambda settings: Path("settings.json")
    )

    def send(target: ComfyBackend, payload: object, *, seed: int, **kwargs):
        calls.append((target.url, payload, seed))
        return GeneratedMesh(
            mesh=FakeMesh(), payload=b"mesh", suffix=".stl", backend="comfyui", seed=seed
        )

    def accept(notice: AiDisclosureDialog) -> int:
        shown.append(notice.target)
        notice.show()
        for _ in range(20):
            qt_app.processEvents()
            if notice.continue_button.isEnabled():
                break
            QTest.qWait(5)
        assert notice.content_was_shown
        notice.continue_button.click()
        return int(notice.result())

    monkeypatch.setattr(ComfyBackend, "text_to_mesh", send)
    monkeypatch.setattr(ComfyBackend, "image_to_mesh", send)
    monkeypatch.setattr(AiDisclosureDialog, "exec", accept)
    dialog = GenerateDialog(backend=backend, settings=settings)
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.prompt.setText("private description")
        dialog._image = image
        dialog.seed.setValue(17)
        for _ in range(2):
            dialog._start()
            assert dialog._worker is not None
            assert dialog._worker.wait(5000)
            qt_app.processEvents()
        assert calls == [(address, image or "private description", 17)] * 2
        assert len(dialog.tries) == 2
        assert shown == [target_for_comfy(address)]
        assert settings.ai_disclosure_backend == "ollama"
    finally:
        dialog.release()
        dialog.deleteLater()


def finish(dialog: GenerateDialog, qt_app: QApplication) -> None:
    """Den Arbeiter zu Ende laufen lassen, ohne den Oberflächen-Thread zu
    blockieren.
    """
    wait_for_readiness(dialog, qt_app)
    dialog._start()
    worker = dialog._worker
    assert worker is not None
    # **Warten, bis der Arbeiter wirklich fertig ist — nicht fünf Sekunden.**
    # Sein erster Aufruf importiert trimesh (``app.core.deferred``), und der
    # Import dauert auf einer Maschine unter Last über fünf Sekunden; die
    # feste Frist lief dann ab, ``processEvents`` fand kein ``done`` vor, und
    # ``result_mesh`` blieb leer, obwohl der Arbeiter kurz darauf lieferte.
    assert worker.wait(60000), "the worker did not finish within a minute"
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
    wait_for_readiness(dialog, qt_app)
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
        wait_for_readiness(dialog, qt_app)
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
        wait_for_readiness(ready, qt_app)
        qt_app.processEvents()
        assert not ready.setup.isVisibleTo(ready), "wo nichts fehlt, steht auch kein Weg"
    finally:
        ready.wait_for_workers()
        ready.close()
        ready.deleteLater()
    qt_app.processEvents()


def test_the_answer_without_a_generator_does_not_squash_the_fields(qt_app: QApplication) -> None:
    """Der lange Satz nach der Antwort presste das Beschreibungsfeld zusammen.

    Befund Robert, 19.09.2026: Nach der Suche ohne Fund hatte das Feld
    „Beschreibung" noch 11 von 26 Punkten Höhe. Ein umbrochenes ``QLabel``
    meldet der Layoutrechnung eine Zeile, der Dialog blieb auf seiner
    Aufmachgröße stehen, und der Fehlbetrag kam aus den Nachbarn. Der Satz
    ist jetzt ein ``WrappedNote`` und fordert seine Höhe ein; das Fenster
    wächst einen Ereignisdurchlauf später mit.
    """
    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    try:
        dialog.show()
        qt_app.processEvents()
        before = dialog.prompt.height()
        wait_for_readiness(dialog, qt_app)
        # Zwei Zeitgeber mit null Millisekunden hintereinander: erst pinnt
        # der Satz seine Höhe, dann wächst das Fenster.
        for _ in range(6):
            qt_app.processEvents()
        assert dialog.state.text(), "die Antwort steht da"
        wanted = dialog.state.heightForWidth(dialog.state.width())
        assert dialog.state.height() >= wanted, "der Satz hat die Höhe, die er braucht"
        assert dialog.prompt.height() >= before, (
            f"das Beschreibungsfeld hat {dialog.prompt.height()} statt {before} Punkte"
        )
        assert dialog.prompt.height() >= dialog.prompt.minimumSizeHint().height()
        assert not dialog.prompt.geometry().intersects(dialog.picture.geometry()), (
            "und der Knopf darunter liegt nicht über dem Feld"
        )
    finally:
        dialog.wait_for_workers()
        dialog.close()
        dialog.deleteLater()
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
        dialog.release()
        dialog.deleteLater()


class _StubWorker:
    """Nur die Methoden, die der Weg nach draußen wirklich ruft.

    ``cancel`` kam mit dem Abbruchmerker dazu (§15.6): Wer den Dialog
    loslässt, sagt dem Wurf zuerst, dass niemand mehr wartet.
    """

    def __init__(self, seen: list[int]) -> None:
        self._seen = seen
        self.cancelled_here = False

    def cancel(self) -> None:
        self.cancelled_here = True

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
    wait_for_readiness(dialog, qt_app)
    after_build = backend.asked
    assert after_build == 1, "einmal beim Aufgehen, das ist der Anlass"

    for letter in "Halter mit 32 mm":
        dialog.prompt.insert(letter)

    assert backend.asked == after_build, "und danach kein weiteres Mal"

    dialog.recheck()
    wait_for_readiness(dialog, qt_app)
    assert backend.asked == after_build + 1, "wer nachsieht, sieht wirklich nach"


def test_a_slow_generator_check_does_not_hold_the_dialog_closed(qt_app: QApplication) -> None:
    """§2.8: Ein äußerer Dienst darf das erste sichtbare Fenster nicht aufhalten.

    ComfyUI kann auf einem zweiten Rechner oder hinter einem Reverse-Proxy
    liegen. Dann ist die Bereitschaftsfrage nicht mehr die 88-ms-Messung vom
    lokalen Dienst, sondern mehrere Zeitlimits. Der Dialog erscheint trotzdem
    und sagt bis zur Antwort ehrlich, dass er nachsieht.
    """

    class SlowBackend(CountingBackend):
        def __init__(self) -> None:
            super().__init__(available=True)
            self.entered = threading.Event()
            self.release = threading.Event()

        @property
        def available(self) -> bool:
            self.asked += 1
            self.entered.set()
            self.release.wait(5.0)
            return True

    backend = SlowBackend()
    started = time.perf_counter()
    dialog = GenerateDialog(backend=backend)
    built_in = time.perf_counter() - started

    assert built_in < 0.2, "die Netzfrage gehört nicht in den Konstruktor"
    assert "geprüft" in dialog.state.text(), "kein erfundener Zustand vor der Antwort"
    assert backend.entered.wait(2.0), "der Hintergrundlauf fragt wirklich nach"

    backend.release.set()
    wait_for_readiness(dialog, qt_app)
    assert dialog.available


def test_the_button_waits_for_something_to_generate_from(
    qt_app: QApplication, generator: ScriptedMeshBackend
) -> None:
    dialog = GenerateDialog(backend=generator)
    wait_for_readiness(dialog, qt_app)

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


def test_a_tiny_body_shows_its_real_volume_beside_closed(qt_app: QApplication) -> None:
    """Die Zeile, die der Kunde liest — nicht die Funktion, die sie formatiert.

    ``format_volume`` hat einen eigenen Test, und der reicht bis zur eigenen
    Klammer. Zugesagt ist aber die **Zeile** in der Versuchsliste: Volumen
    neben „geschlossen". Zwischen beidem liegen zwei Glieder — ``labels.volume``
    und ``_show_tries`` —, und ein halbes Kubikmillimeter stand dort als
    „0 mm³", während die Formatierung längst richtig rechnete.

    **Gemessen wird die Zahl, nicht ihre Schreibweise.** Ein ``assert`` auf
    „0,12 mm³" wäre ein Nachbau der Formatierung: Er bräche bei jeder
    Stellenänderung, ohne dass ein Kunde etwas verlöre, und er bliebe grün,
    wenn die Kette wieder auf feste Kubikzentimeter zurückfiele — dort steht
    dieselbe Zahl als „0,0". Geprüft wird deshalb, was die Zusage ausmacht:
    dass **etwas Positives** dort steht.
    """
    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    try:
        wait_for_readiness(dialog, qt_app)
        # 0,5 mm Kante — 0,125 mm³, der Wert aus einem echten Wurf.
        dialog.tries = [
            GeneratedMesh(
                mesh=FakeMesh(size=(0.5, 0.5, 0.5)),  # type: ignore[arg-type]
                payload=b"",
                suffix=".stl",
                backend="test",
            )
        ]
        dialog._show_tries()

        eintrag = dialog.attempts.item(0)
        assert eintrag is not None, "der Versuch steht in der Liste"
        zeile = eintrag.text()
        assert "geschlossen" in zeile, "die Zusage nennt beides in einer Zeile"

        # Das mittlere der drei Stücke ist das Volumen; die Trennung gehört
        # zur Zeile und nicht zur Formatierung, die hier geprüft wird.
        gemessen = zeile.split("·")[1].strip()
        zahl = float(gemessen.split()[0].replace(",", "."))
        assert zahl > 0.0, f"ein Körper mit Volumen zeigt keine Null: {zeile!r}"
    finally:
        dialog.deleteLater()


def _generated(size: tuple[float, float, float]) -> GeneratedMesh:
    return GeneratedMesh(
        mesh=FakeMesh(size=size),  # type: ignore[arg-type]
        payload=b"",
        suffix=".glb",
        backend="test",
    )


def test_a_try_that_fell_apart_says_so_and_names_the_way_to_another(
    qt_app: QApplication,
) -> None:
    """Ein Rohnetz, das schon im Generator zerfällt, repariert keine Kette (RM-550).

    TRELLIS.2 lieferte mit Startwert 8 ein Knäuel aus 690 Teilen; übernommen
    stand ein offener Körper mit Hunderten offener Stellen im Bericht. Die
    Zeile sagt deshalb „zerfallen“ statt „offen“, und die Zustandszeile nennt
    den Ausweg — „Noch ein Versuch“. Wählt der Kunde einen heilen Versuch,
    gilt wieder der gewöhnliche Satz. Geprüft am Ausschnitt des echten Netzes.
    """
    from app.core.geom.mesh import read_mesh

    def generated(name: str, seed: int) -> GeneratedMesh:
        payload = (MESHES / name).read_bytes()
        return GeneratedMesh(
            mesh=read_mesh(payload, ".glb"),
            payload=payload,
            suffix=".glb",
            backend="test",
            seed=seed,
        )

    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.tries = [
            generated("generated_touching.glb", 11),
            generated("generated_fell_apart.glb", 8),
        ]
        dialog._show_tries()

        zeile = dialog.attempts.item(1)
        assert zeile is not None
        assert "zerfallen" in zeile.text(), zeile.text()
        assert "offen" not in zeile.text(), "zerfallen ist mehr als offen"
        satz = dialog.state.text()
        assert "Versuch 2" in satz and "zerfallen" in satz, satz
        assert "„Noch ein Versuch“" in satz and "neu" in satz, "der Ausweg steht im Satz"
        assert dialog.again.isVisibleTo(dialog), "und sein Knopf steht darunter"

        dialog.attempts.setCurrentRow(0)
        assert "zerfallen" not in dialog.state.text(), "ein heiler Versuch trägt den alten Satz"
        assert "Prüfen Sie das Ergebnis" in dialog.state.text()
        heil = dialog.attempts.item(0)
        assert heil is not None and "zerfallen" not in heil.text()
    finally:
        dialog.wait_for_workers()
        dialog.deleteLater()
    qt_app.processEvents()


def test_the_list_reads_what_the_worker_already_judged(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Urteil über einen zerfallenen Versuch kostet Sekunden — im Arbeiter, einmal
    je Versuch, nie im Hauptthread (Review K, H1).

    Vorher rechnete die Liste es bei jedem Neuaufbau und jeder Zeilenwahl neu:
    drei Aufrufe nach jedem Wurf, je 2 bis 6 s an einem echten Rohnetz.
    """
    from app.core import generate
    from app.ui.generate_dialog import _Worker

    calls: list[object] = []
    real = generate.separate_touching_sheets

    def counted(mesh: object) -> object:
        calls.append(mesh)
        return real(mesh)  # type: ignore[arg-type]

    monkeypatch.setattr(generate, "separate_touching_sheets", counted)
    backend = ScriptedMeshBackend(
        fallback=(MESHES / "generated_fell_apart.glb").read_bytes(), suffix=".glb"
    )
    results: list[GeneratedMesh] = []
    worker = _Worker(backend, "Rakete", None, 8)
    worker.done.connect(results.append)
    worker.work()
    assert len(results) == 1 and len(calls) == 1, "der Arbeiter urteilt einmal"

    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.tries = [_generated((1.0, 2.0, 0.5)), results[0]]
        dialog._show_tries()
        dialog.attempts.setCurrentRow(0)
        dialog.attempts.setCurrentRow(1)
        dialog._show_tries()

        assert len(calls) == 1, "die Liste liest nur"
        assert "zerfallen" in dialog.state.text()
    finally:
        dialog.wait_for_workers()
        dialog.deleteLater()
    qt_app.processEvents()


def _skin() -> GeneratedMesh:
    """Die Haut aus der Messung vom 08.10.2026 (Text, Startwert 14), als Rohnetz."""
    import numpy as np
    import trimesh

    from app.core.geom.mesh import MeshData

    stored = np.load(MESHES / "generated_skin.npz")
    raw = trimesh.Trimesh(
        stored["vertices"].astype(float), stored["faces"].astype(np.int64), process=False
    )
    return GeneratedMesh(mesh=MeshData.of(raw), payload=b"", suffix=".glb", backend="test", seed=14)


def test_a_try_that_is_only_a_skin_says_so_before_it_is_taken(qt_app: QApplication) -> None:
    """Fünf von 17 TRELLIS.2-Läufen waren eine Haut von 0,3 mm um einen Hohlraum,
    geschlossen und ohne Befund (RM-577). Der Dialog sagt es je Versuch, gemessen
    gegen die dünnste Wand des Druckers, und nennt den neuen Versuch."""
    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.tries = [_skin()]
        dialog._show_tries()
        assert "Haut" not in dialog.attempts.item(0).text(), "ohne Profil kein Urteil"

        dialog.minimum_wall = lambda: 0.8
        dialog._show_tries()

        zeile = dialog.attempts.item(0)
        assert zeile is not None and "nur eine Haut" in zeile.text(), zeile.text()
        satz = dialog.state.text()
        assert "0,3 mm" in satz and "0,8 mm" in satz and "„Noch ein Versuch“" in satz, satz
    finally:
        dialog.wait_for_workers()
        dialog.deleteLater()
    qt_app.processEvents()


def test_choosing_an_older_try_keeps_the_failure_message(qt_app: QApplication) -> None:
    """Nach einem gescheiterten Wurf gehört die Zeile seiner Meldung — ein Klick auf
    einen älteren Versuch löschte sie (Review K, G8)."""
    from app.core.backends.mesh import GenerationFailed

    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.tries = [_generated((1.0, 2.0, 0.5)), _generated((1.0, 1.0, 1.0))]
        dialog._show_tries()
        dialog._say_failure(GenerationFailed(detail="ComfyUI hat abgebrochen."))
        said = dialog.state.text()

        dialog.attempts.setCurrentRow(0)

        assert dialog.state.text() == said, "die Meldung bleibt"
    finally:
        dialog.wait_for_workers()
        dialog.deleteLater()
    qt_app.processEvents()


def _settle(qt_app: QApplication) -> None:
    """Zwei Zeitgeber mit null Millisekunden hintereinander: erst pinnt der
    Satz seine Höhe, dann folgt das Fenster — mit Reserve."""
    for _ in range(6):
        qt_app.processEvents()


def test_a_try_names_the_volume_it_will_have_in_the_project(qt_app: QApplication) -> None:
    """Die Zeile nannte das Volumen des rohen Generatornetzes.

    „1. 440842 Dreiecke · 2 mm³ · geschlossen“ stand in der Aufnahme des
    Workshopfilms: Das Netz liegt auf einem Einheitswürfel, und zwei Schritte
    später hatte der Körper hundert Millimeter Kante. Verglichen wird mit
    derselben Anzeige (``labels.volume``) über einem Wert aus der
    Konstruktion — die längste Kante 2 wird 100 mm, Faktor 50.
    """
    from app.ui.labels import volume

    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.tries = [_generated((1.0, 2.0, 0.5))]
        dialog._show_tries()

        eintrag = dialog.attempts.item(0)
        assert eintrag is not None, "der Versuch steht in der Liste"
        gemessen = eintrag.text().split("·")[1].strip()
        assert gemessen == volume(50.0 * 100.0 * 25.0), eintrag.text()
    finally:
        dialog.wait_for_workers()
        dialog.deleteLater()
    qt_app.processEvents()


def test_after_a_run_a_taller_window_gives_its_room_to_the_list(qt_app: QApplication) -> None:
    """Nach dem Lauf stand eine leere Fläche zwischen den Feldern und dem Satz.

    In der Aufnahme des Workshopfilms rund 340 Punkte: Das Fenster war höher
    als sein Inhalt, der Platz sammelte sich vor dem Hinweis, und die Liste
    darunter blieb auf 120 Punkte gekappt. Jetzt nimmt die Liste ihn. Der
    Abstand zwischen Feldern und Hinweis ist derselbe wie in einem Fenster
    auf seiner eigenen Höhe, und die gezogene Höhe bleibt.
    """
    natural = GenerateDialog(backend=ScriptedMeshBackend())
    tall = GenerateDialog(backend=ScriptedMeshBackend())

    def gap(dialog: GenerateDialog) -> int:
        return dialog.state.geometry().top() - dialog.advanced.geometry().bottom()

    try:
        for dialog in (natural, tall):
            dialog.show()
            wait_for_readiness(dialog, qt_app)
        _settle(qt_app)
        # Wie von Hand gezogen, oder wie die Aufnahme ihn setzte.
        tall.resize(tall.width(), natural.height() + 340)
        _settle(qt_app)
        drawn = tall.height()
        assert gap(tall) > gap(natural) + 300, "vor dem Lauf sammelt sich der Platz am Hinweis"

        for dialog in (natural, tall):
            dialog.tries = [_generated((1.0, 2.0, 0.5))]
            dialog._show_tries()
        _settle(qt_app)

        assert tall.height() == drawn, "die gezogene Höhe bleibt"
        assert gap(tall) == gap(natural), (
            f"zwischen Feldern und Hinweis stehen {gap(tall)} statt {gap(natural)} Punkte"
        )
        assert tall.height() > natural.height() + 100, "das hohe Fenster ist noch höher"
        assert (
            tall.attempts.height() - natural.attempts.height() == tall.height() - natural.height()
        ), "den ganzen Überschuss nimmt die Liste"
        assert tall.state.geometry().bottom() < tall.attempts.geometry().top(), (
            "der Hinweis steht über der Liste, von der er spricht"
        )
    finally:
        for dialog in (natural, tall):
            dialog.wait_for_workers()
            dialog.close()
            dialog.deleteLater()
    qt_app.processEvents()


def test_the_main_button_stays_the_default_through_the_run(qt_app: QApplication) -> None:
    """Während des Laufs und danach bleibt „Erzeugen“/„Übernehmen“ der Hauptknopf.

    In der englischen Aufnahme ging der Fokus vom gesperrten „Erzeugen“ auf
    „Abbrechen“, das sich über ``autoDefault`` zum Default machte; nach dem
    Lauf stand „Übernehmen“ grau und „Abbrechen“ orange, und Enter hätte das
    Ergebnis verworfen. Hier geht der Fokus den Weg, den Qt ihn schickt:
    vom gesperrten Knopf zum nächsten.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont

    dialog = GenerateDialog(backend=ScriptedMeshBackend(fallback=b"solid x\n"))
    cancel = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
    try:
        dialog.show()
        dialog.activateWindow()
        wait_for_readiness(dialog, qt_app)
        dialog.prompt.setText("eine Eule")
        qt_app.processEvents()
        assert dialog.isActiveWindow(), "ohne aktives Fenster kommt kein Fokus an"

        for secondary in (dialog.picture, cancel):
            secondary.setFocus(Qt.FocusReason.TabFocusReason)
            qt_app.processEvents()
            assert qt_app.focusWidget() is secondary
            assert not secondary.isDefault(), f"„{secondary.text()}“ wird mit dem Fokus Default"
            assert ok(dialog).isDefault()

        ok(dialog).setFocus(Qt.FocusReason.TabFocusReason)
        qt_app.processEvents()
        dialog._running(True)
        qt_app.processEvents()
        assert not ok(dialog).isEnabled()
        assert qt_app.focusWidget() is not ok(dialog), (
            "der Fokus hat den gesperrten Knopf verlassen"
        )
        defaults = [
            button.text() for button in dialog.findChildren(QPushButton) if button.isDefault()
        ]
        assert defaults == [ok(dialog).text()], f"während des Laufs trägt {defaults} den Akzent"

        dialog._running(False)
        dialog.tries = [_generated((1.0, 2.0, 0.5))]
        dialog._show_tries()
        _settle(qt_app)
        take = ok(dialog)
        assert take.text() == "Übernehmen"
        assert take.isEnabled() and take.isDefault(), (
            "nach dem Lauf ist „Übernehmen“ der Hauptknopf"
        )
        assert take.font().weight() >= QFont.Weight.DemiBold, "mit dem Aussehen von make_primary"
        defaults = [
            button.text() for button in dialog.findChildren(QPushButton) if button.isDefault()
        ]
        assert defaults == [take.text()], f"nach dem Lauf tragen {defaults} den Akzent"
    finally:
        dialog.wait_for_workers()
        dialog.close()
        dialog.deleteLater()
    qt_app.processEvents()


def test_status_text_grows_the_dialog_once_and_stays_reachable(qt_app: QApplication) -> None:
    """Ein langer Status vergrößert den Rahmen bis zum Bildschirm, der Rest rollt;
    ein kurzer danach gibt nichts zurück, damit der Rahmen nicht springt (RM-487)."""
    dialog = GenerateDialog(backend=ScriptedMeshBackend(fallback=b"solid x\n"))
    long_text = "Ein langer Satz, der mehrere Zeilen braucht. " * 140
    short_text = "Bereit."
    try:
        dialog.show()
        wait_for_readiness(dialog, qt_app)
        _settle(qt_app)
        before = dialog.size()

        dialog.state.setText(long_text)
        _settle(qt_app)
        grown = dialog.size()
        assert grown.width() == before.width(), "die Breite bleibt"
        assert grown.height() > before.height(), "der lange Satz bekommt Platz"
        room = dialog.screen().availableGeometry()
        assert room.contains(dialog.frameGeometry()), "gewachsen wird nur bis zum Bildschirm"
        scroll = dialog._scroll
        bar = scroll.verticalScrollBar()
        assert bar.maximum() > 0, "der lange Text liegt im erreichbaren Rollbereich"
        bar.setValue(0)
        _settle(qt_app)
        top = dialog.state.mapTo(scroll.viewport(), dialog.state.rect().topLeft()).y()
        assert top >= 0, "der Anfang der Meldung ist erreichbar"
        bar.setValue(bar.maximum())
        _settle(qt_app)
        bottom = dialog.state.mapTo(scroll.viewport(), dialog.state.rect().bottomLeft()).y()
        assert bottom <= scroll.viewport().rect().bottom(), "das Ende der Meldung ist erreichbar"

        dialog.state.setText(short_text)
        _settle(qt_app)
        assert dialog.size() == grown, "der kurze Status gibt die Höhe nicht zurück"

        dialog.state.setText(long_text)
        _settle(qt_app)
        dialog.state.setText(short_text)
        _settle(qt_app)
        assert dialog.size() == grown, "wiederholte Statuswechsel bleiben stabil"

        # Von Hand gezogen: Das bleibt, auch nach einem langen Satz.
        dialog.resize(before.width(), before.height() + 40)
        _settle(qt_app)
        drawn = dialog.size()
        dialog.state.setText(long_text)
        _settle(qt_app)
        dialog.state.setText(short_text)
        _settle(qt_app)
        assert dialog.size() == drawn, "die gezogene Höhe gehört dem Nutzer"
    finally:
        dialog.wait_for_workers()
        dialog.close()
        dialog.deleteLater()
    qt_app.processEvents()


def test_a_failure_stays_in_the_dialog(qt_app: QApplication) -> None:
    """Ein Generator, der Nein sagt, ist kein Absturz — der Satz landet im
    Dialog.
    """
    dialog = GenerateDialog(backend=ScriptedMeshBackend(answers={"etwas": b"solid x\n"}))
    dialog.prompt.setText("etwas anderes")

    finish(dialog, qt_app)

    assert dialog.result_mesh is None
    assert dialog.buttons.isEnabled(), "the dialog can be tried again"
    assert "3D-Modell" in dialog.state.text()


def test_a_failure_says_why_and_what_helps(qt_app: QApplication) -> None:
    """§2.7 verlangt drei Dinge, und der Dialog zeigte nur eines.

    Der Titel allein — „Die 3D-Modell-Erzeugung konnte nicht starten" — lässt den
    Nutzer stehen. Der Grund steht im Detail, der Ausweg im Vorschlag; beide
    gehören in die Zeile, denn modal geht hier nichts.
    """
    from app.core.backends.mesh import GenerationFailed
    from app.core.errors import CANCEL, INSTALL_MISSING

    dialog = GenerateDialog(backend=ScriptedMeshBackend(fallback=b"solid x\n"))
    wait_for_readiness(dialog, qt_app)
    dialog._on_failed(
        GenerationFailed(
            title="Die 3D-Modell-Erzeugung konnte nicht starten.",
            detail="ComfyUI antwortet nicht.",
            suggestions=(INSTALL_MISSING, CANCEL),
        )
    )

    text = dialog.state.text()
    assert "konnte nicht starten" in text, "was nicht ging"
    assert "antwortet nicht" in text, "warum"
    assert str(INSTALL_MISSING.label) in text, "was jetzt hilft"
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
    assert session.wait_for_idle(60_000)

    # Vier Schritte, und die Reihenfolge ist keine Geschmacksfrage: was ein
    # Bildmodell liefert, ist auf einen Einheitswürfel normiert und misst als
    # Millimeter gelesen ein bis zwei. Erst auf Maß bringen, dann bereinigen —
    # andersherum verschweißt die Reparatur bei dieser Größe die halbe Lehne —,
    # und zuletzt aufsetzen, denn die Reparatur kann unter dem Körper etwas
    # wegnehmen.
    assert [entry.op for entry in session.project.document.ops] == [
        "load",
        "fit_to_size",
        "repair",
        "place_on_bed",
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
    wait_for_readiness(dialog, qt_app)
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


# --- ComfyUI einrichten, aus der Anwendung (§27, §36) -----------------------------


def _wait_for_comfy_probe(dialog: Any, qt_app: QApplication) -> None:
    """Stellt die entkoppelte Ordnerprüfung zu, statt synchrone Ergebnisse anzunehmen.

    **Gewartet wird mit freigegebener GIL** (``ui_helpers.wait_until``):
    ``QTest.qWait`` hält sie, und der Prüffaden bekam sie nach jedem Dateiblick
    erst zurück, wenn das Warten endete. ``shutil.which`` sucht ``nvidia-smi``
    unter Windows über jeden PATH-Eintrag und jede Endung — auf dem Läufer ohne
    Treiber rund tausend Blicke, die in fünf Sekunden nicht durchkamen.
    """
    deadline = time.monotonic() + 60
    while dialog._probe_pending and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    qt_app.processEvents()
    assert not dialog._probe_pending, "Ordnerprüfung blieb im Wartezustand"


def test_the_setup_dialog_prefills_what_it_finds(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Eine leere Zeile wäre eine Frage an jemanden, der die Antwort selten
    auswendig weiß.
    """
    from app.core.backends import comfy_setup
    from app.ui.comfy_dialog import ComfySetupDialog

    comfyui = tmp_path / "ComfyUI"
    (comfyui / "custom_nodes").mkdir(parents=True)
    monkeypatch.setattr(comfy_setup, "find_comfyui", lambda given=None: comfyui)

    dialog = ComfySetupDialog()
    try:
        assert not dialog.start_button.isEnabled()
        assert dialog.start_button.toolTip()
        assert not dialog.start_button.statusTip()
        assert dialog.start_button.accessibleDescription()
        _wait_for_comfy_probe(dialog, qt_app)
        assert dialog.folder.text() == str(comfyui)
        assert dialog.weights.isChecked(), "die Gewichte fehlen, also werden sie geholt"
        assert dialog.start_button.isEnabled()
    finally:
        dialog.release()
        dialog.deleteLater()


def test_leaving_a_verified_comfy_folder_does_not_repeat_the_check(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from PySide6.QtTest import QTest

    from app.core.backends import comfy_setup
    from app.ui.comfy_dialog import ComfySetupDialog

    comfyui = tmp_path / "ComfyUI"
    typed = tmp_path / "typed"
    find_calls = 0

    def find(given: str | Path | None = None) -> Path:
        nonlocal find_calls
        find_calls += 1
        return Path(given) if given else comfyui

    monkeypatch.setattr(comfy_setup, "find_comfyui", find)
    dialog = ComfySetupDialog()
    try:
        _wait_for_comfy_probe(dialog, qt_app)
        checked_generation = dialog._probe_generation
        checked_calls = find_calls

        dialog.folder.setText(str(typed))
        dialog.folder.textEdited.emit(str(typed))
        typed_generation = dialog._probe_generation
        dialog.folder.editingFinished.emit()
        assert dialog._probe_generation == typed_generation == checked_generation + 1
        _wait_for_comfy_probe(dialog, qt_app)
        assert find_calls == checked_calls + 1, "Tippen und Fokusverlust teilen sich eine Prüfung"

        checked_generation = dialog._probe_generation
        checked_calls = find_calls
        dialog.folder.editingFinished.emit()
        QTest.qWait(350)
        qt_app.processEvents()

        assert dialog._probe_generation == checked_generation
        assert find_calls == checked_calls, "Fokusverlust darf den geprüften Pfad nicht neu prüfen"
        assert dialog.start_button.isEnabled()
    finally:
        dialog.release()
        dialog.deleteLater()


def test_changing_the_comfy_folder_refreshes_model_status_and_keeps_choices(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ordnerwahl und Tippen entwerten Bestände sofort, auch bei einer späten Antwort."""
    from PySide6.QtWidgets import QFileDialog

    from app.core.backends import comfy_setup
    from app.ui.comfy_dialog import ComfySetupDialog, _FolderProbeResult

    image_folder = tmp_path / "image"
    weights_folder = tmp_path / "weights"
    image_folder.mkdir()
    weights_folder.mkdir()
    monkeypatch.setattr(
        comfy_setup,
        "find_comfyui",
        lambda given=None: Path(given) if given else image_folder,
    )
    monkeypatch.setattr(
        comfy_setup, "weights_present", lambda folder: Path(folder) == weights_folder
    )
    monkeypatch.setattr(
        comfy_setup, "image_model_present", lambda folder: Path(folder) == image_folder
    )

    dialog = ComfySetupDialog(image_model=True)
    try:
        _wait_for_comfy_probe(dialog, qt_app)
        assert not dialog.image_model.isEnabled()
        assert dialog.image_model.text() == "Bildmodell ist schon da"
        assert dialog.weights.isChecked()

        dialog.weights.setChecked(False)
        image_generation = dialog._probe_generation
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_args: str(weights_folder))
        dialog.choose.click()
        assert dialog._probe_pending and not dialog.start_button.isEnabled()
        assert dialog.image_model.text() == dialog._image_model_label
        assert not dialog.weights.isEnabled() and not dialog.image_model.isEnabled()
        dialog._probe_results.put(
            _FolderProbeResult(
                image_generation, str(image_folder), str(image_folder), image_model=True
            )
        )
        dialog._collect_folder_probe()
        assert dialog._probe_pending, "eine alte Antwort darf die neue Prüfung nicht beenden"
        assert dialog.image_model.text() == dialog._image_model_label
        _wait_for_comfy_probe(dialog, qt_app)
        assert not dialog.weights.isEnabled()
        assert dialog.weights.text() == "Modell ist schon da"
        assert dialog.image_model.isEnabled() and dialog.image_model.isChecked()

        weights_generation = dialog._probe_generation
        dialog.folder.selectAll()
        dialog.folder.insert(str(image_folder))
        assert dialog._probe_pending and not dialog.start_button.isEnabled()
        assert dialog.weights.text() == dialog._weights_label
        assert not dialog.weights.isEnabled() and not dialog.image_model.isEnabled()
        _wait_for_comfy_probe(dialog, qt_app)
        dialog._probe_results.put(
            _FolderProbeResult(
                weights_generation, str(weights_folder), str(weights_folder), weights=True
            )
        )
        dialog._collect_folder_probe()
        assert dialog.folder.text() == str(image_folder)
        assert dialog.start_button.isEnabled()
        assert dialog.weights.text() == dialog._weights_label
        assert dialog.weights.isEnabled() and not dialog.weights.isChecked()
        assert not dialog.image_model.isEnabled()
        assert dialog.image_model.text() == "Bildmodell ist schon da"
    finally:
        dialog.release()
        dialog.deleteLater()


def test_the_setup_dialog_says_where_to_point_it(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne Fund kein leeres Feld ohne Erklärung (Regel 17)."""
    from app.core.backends import comfy_setup
    from app.ui.comfy_dialog import ComfySetupDialog

    def nothing(given: object = None) -> object:
        raise comfy_setup.SetupFailed("nicht gefunden")

    monkeypatch.setattr(comfy_setup, "find_comfyui", nothing)

    dialog = ComfySetupDialog()
    try:
        _wait_for_comfy_probe(dialog, qt_app)
        assert not dialog.folder.text()
        assert "custom_nodes" in dialog.state.text(), "woran man den Ordner erkennt"
    finally:
        dialog.release()
        dialog.deleteLater()


def test_comfy_folder_poll_does_not_replace_the_debounce_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neue Eingaben entprellen; der Antwortpoll ersetzt den Termin nicht durch Retry."""
    from queue import Queue
    from types import SimpleNamespace

    from app.ui import comfy_dialog

    class ProbeTimer:
        def __init__(self) -> None:
            self.active = False
            self.delays: list[int] = []
            self.stop_count = 0

        def isActive(self) -> bool:  # noqa: N802 — Qt-API
            return self.active

        def start(self, delay: int = 0) -> None:
            self.delays.append(delay)
            self.active = True

        def stop(self) -> None:
            self.stop_count += 1
            self.active = False

    class PollTimer:
        def stop(self) -> None:
            raise AssertionError("Eine laufende Prüfung muss weiter abgeholt werden.")

    start_timer = ProbeTimer()
    slow_timer = ProbeTimer()
    dialog = SimpleNamespace(
        _worker=None,
        _probe_target="alter Pfad",
        _probe_pending=False,
        _probe_requested=False,
        _probe_succeeded=True,
        _probe_generation=0,
        _probe_timed_out_generation=None,
        _probe_running_generations={0},
        _probe_results=Queue(),
        _probe_timer=start_timer,
        _probe_slow_timer=slow_timer,
        _probe_poll=PollTimer(),
        _weights_present=True,
        _image_model_present=True,
        progress=SimpleNamespace(setVisible=lambda _visible: None),
        state=object(),
        _setup_is_running=lambda: False,
        _remember_model_choices=lambda: None,
        _set_start_enabled=lambda _enabled: None,
        _set_model_options=lambda _weights, _image: None,
        _show_legacy=lambda _folders, _size: None,
    )
    monkeypatch.setattr(comfy_dialog, "set_role", lambda *_args: None)

    comfy_dialog.ComfySetupDialog._queue_folder_probe(dialog, "neuer Pfad")
    comfy_dialog.ComfySetupDialog._collect_folder_probe(dialog)
    comfy_dialog.ComfySetupDialog._queue_folder_probe(dialog, "jüngster Pfad")
    comfy_dialog.ComfySetupDialog._collect_folder_probe(dialog)

    assert start_timer.delays == [
        comfy_dialog.FOLDER_PROBE_DELAY_MS,
        comfy_dialog.FOLDER_PROBE_DELAY_MS,
    ]
    assert start_timer.stop_count == 2
    assert dialog._probe_target == "jüngster Pfad"
    assert dialog._probe_requested


def test_slow_and_outdated_comfy_folder_probes_do_not_freeze_or_change_the_dialog(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from PySide6.QtCore import QTimer
    from PySide6.QtTest import QTest

    from app.core.backends import comfy_setup
    from app.ui.comfy_dialog import ComfySetupDialog

    initial = tmp_path / "initial"
    slow = tmp_path / "slow"
    current = tmp_path / "current"
    gate = threading.Event()
    gate.set()
    probe_threads: list[int] = []
    active_probes = 0
    peak_active_probes = 0
    slow_weights_calls = 0
    probe_lock = threading.Lock()
    setup_started = threading.Event()
    setup_paths: list[str] = []

    def find(given: str | Path | None = None) -> Path:
        return Path(given) if given else initial

    def weights(folder: Path) -> bool:
        nonlocal active_probes, peak_active_probes, slow_weights_calls
        if folder == slow:
            with probe_lock:
                slow_weights_calls += 1
                call = slow_weights_calls
                active_probes += 1
                peak_active_probes = max(peak_active_probes, active_probes)
            probe_threads.append(threading.get_ident())
            if call == 1:
                gate.wait(5)
            with probe_lock:
                active_probes -= 1
            return call > 1
        return False

    monkeypatch.setattr(comfy_setup, "find_comfyui", find)
    monkeypatch.setattr(comfy_setup, "weights_present", weights)
    monkeypatch.setattr(
        comfy_setup,
        "image_model_present",
        lambda folder: Path(folder) == current,
    )

    def setup(folder: str | Path | None, **_kwargs: object) -> comfy_setup.Result:
        setup_paths.append(str(folder))
        setup_started.set()
        return comfy_setup.Result(comfyui=Path(folder or slow), weights=True)

    monkeypatch.setattr(comfy_setup, "setup", setup)
    dialog = ComfySetupDialog(image_model=True)
    ticks: list[bool] = []
    timer = QTimer(dialog)
    timer.setInterval(20)
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start()
    try:
        _wait_for_comfy_probe(dialog, qt_app)
        gate.clear()
        dialog.folder.setText(str(slow))
        dialog.folder.editingFinished.emit()
        QTest.qWait(30)
        first_generation = next(iter(dialog._probe_running_generations))
        started = time.perf_counter()
        QTest.qWait(80)
        assert time.perf_counter() - started < 0.5, (
            "ein langsamer Dateiblick darf Qt nicht blockieren"
        )
        assert ticks, "die Ereignisschleife muss während der Dateiprüfung weiterlaufen"
        assert dialog._probe_pending

        dialog._folder_probe_timed_out()
        assert not dialog.start_button.isEnabled(), (
            "ein ungeprüfter Pfad darf Setup nicht erneut im Einrichtungsarbeiter prüfen"
        )
        assert dialog.start_button.accessibleDescription()
        assert "anderen erreichbaren Ordner" in dialog.state.text()
        dialog.start_button.click()
        assert dialog._worker is None, "Setup bleibt bis zur erfolgreichen Pfadprüfung gesperrt"

        dialog.folder.setText(str(current))
        dialog.folder.editingFinished.emit()
        _wait_for_comfy_probe(dialog, qt_app)
        assert dialog.folder.text() == str(current)
        assert not dialog.image_model.isEnabled(), "der erreichbare Ersatzordner ist geprüft"

        dialog.start_button.click()
        worker = dialog._worker
        assert worker is not None and worker.wait(5_000)
        qt_app.processEvents()
        assert setup_started.is_set()
        assert setup_paths == [str(current)], "Setup übernimmt den erfolgreich geprüften Ersatzpfad"

        dialog.folder.setText(str(slow))
        dialog.folder.editingFinished.emit()
        latest_generation = dialog._probe_generation
        assert first_generation < latest_generation
        assert dialog._probe_target == str(slow), (
            "erste und neueste Generation prüfen denselben eingegebenen Pfad"
        )
        _wait_for_comfy_probe(dialog, qt_app)
        assert probe_threads and probe_threads[0] != threading.get_ident()
        assert dialog.folder.text() == str(slow)
        assert slow_weights_calls == 2
        assert peak_active_probes == 2, "der zweite Platz prüft trotz des alten Dateiblicks weiter"
        assert not dialog.weights.isEnabled(), (
            "die alte Antwort desselben Pfades darf die neuere Modellprüfung nicht überholen"
        )
        assert dialog.weights.text() == "Modell ist schon da"

        gate.set()
        deadline = time.monotonic() + 5
        while dialog._probe_running_generations and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)
        qt_app.processEvents()
        assert not dialog._probe_running_generations
        assert not dialog.weights.isEnabled() and dialog.weights.text() == "Modell ist schon da", (
            "Eine verspätete Antwort desselben Pfads "
            "darf den aktuellen Modellbestand nicht überschreiben"
        )
    finally:
        gate.set()
        timer.stop()
        dialog.release()
        dialog.deleteLater()


def test_a_late_failed_comfy_folder_probe_keeps_setup_locked_until_retry(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:

    from app.core.backends import comfy_setup
    from app.ui.comfy_dialog import ComfySetupDialog

    initial = tmp_path / "initial"
    slow = tmp_path / "slow"
    probe_started = threading.Event()
    release_probe = threading.Event()
    slow_calls = 0
    setup_calls: list[str] = []

    def find(given: str | Path | None = None) -> Path:
        nonlocal slow_calls
        folder = Path(given) if given else initial
        if folder == slow:
            slow_calls += 1
            if slow_calls == 1:
                probe_started.set()
                release_probe.wait(5)
                raise comfy_setup.SetupFailed("Ordnerprüfung hat die Wartezeit überschritten")
        return folder

    monkeypatch.setattr(comfy_setup, "find_comfyui", find)
    monkeypatch.setattr(comfy_setup, "weights_present", lambda _folder: False)
    monkeypatch.setattr(comfy_setup, "image_model_present", lambda _folder: False)
    monkeypatch.setattr(
        comfy_setup, "setup", lambda folder, **_kwargs: setup_calls.append(str(folder))
    )

    dialog = ComfySetupDialog()
    try:
        _wait_for_comfy_probe(dialog, qt_app)
        dialog.folder.setText(str(slow))
        dialog.folder.editingFinished.emit()

        deadline = time.monotonic() + 2
        while not probe_started.is_set() and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)
        assert probe_started.is_set(), "die langsame Prüfung muss tatsächlich laufen"

        generation = dialog._probe_generation
        dialog._folder_probe_timed_out()
        assert not dialog.start_button.isEnabled()
        assert dialog.start_button.accessibleDescription()

        release_probe.set()
        deadline = time.monotonic() + 2
        while generation in dialog._probe_running_generations and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)
        qt_app.processEvents()

        assert not dialog._probe_pending
        assert not dialog.start_button.isEnabled(), (
            "eine verspätete Fehlerantwort derselben Generation darf Setup nicht freigeben"
        )
        assert "anderen erreichbaren Ordner" in dialog.state.text()
        dialog._start()
        assert dialog._worker is None and not setup_calls, (
            "auch ein direkter Startaufruf darf den Timeout-Pfad nicht wiederholen"
        )

        failed_generation = dialog._probe_generation
        dialog.folder.editingFinished.emit()
        assert dialog._probe_generation == failed_generation + 1, (
            "erneutes Prüfen muss eine neue Generation starten"
        )
        _wait_for_comfy_probe(dialog, qt_app)
        assert slow_calls == 2, "der Nutzer kann denselben Ordner ausdrücklich erneut prüfen"
        assert dialog.start_button.isEnabled(), "eine neue erfolgreiche Prüfung gibt Setup frei"
    finally:
        release_probe.set()
        dialog.release()
        dialog.deleteLater()


def test_a_late_successful_comfy_folder_probe_unlocks_setup_after_timeout(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:

    from app.core.backends import comfy_setup
    from app.ui.comfy_dialog import ComfySetupDialog

    initial = tmp_path / "initial"
    slow = tmp_path / "slow"
    probe_started = threading.Event()
    release_probe = threading.Event()

    def find(given: str | Path | None = None) -> Path:
        folder = Path(given) if given else initial
        if folder == slow:
            probe_started.set()
            release_probe.wait(5)
        return folder

    monkeypatch.setattr(comfy_setup, "find_comfyui", find)
    monkeypatch.setattr(comfy_setup, "weights_present", lambda _folder: False)
    monkeypatch.setattr(comfy_setup, "image_model_present", lambda _folder: False)

    dialog = ComfySetupDialog()
    try:
        _wait_for_comfy_probe(dialog, qt_app)
        dialog.folder.setText(str(slow))
        dialog.folder.editingFinished.emit()

        deadline = time.monotonic() + 2
        while not probe_started.is_set() and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)
        assert probe_started.is_set(), "die langsame Prüfung muss tatsächlich laufen"

        generation = dialog._probe_generation
        dialog._folder_probe_timed_out()
        assert not dialog.start_button.isEnabled()

        release_probe.set()
        deadline = time.monotonic() + 2
        while generation in dialog._probe_running_generations and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)
        qt_app.processEvents()

        assert dialog._probe_succeeded
        assert dialog._probe_timed_out_generation is None
        assert dialog.start_button.isEnabled(), (
            "eine verspätete erfolgreiche Antwort derselben Generation darf Setup freigeben"
        )
    finally:
        release_probe.set()
        dialog.release()
        dialog.deleteLater()


def test_comfy_folder_probes_are_bounded_across_dialogs(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:

    from app.core.backends import comfy_setup
    from app.ui.comfy_dialog import ComfySetupDialog

    gate = threading.Event()
    probe_started = threading.Event()
    active_probes = 0
    peak_active_probes = 0
    probe_lock = threading.Lock()

    def slow_weights(_folder: Path) -> bool:
        nonlocal active_probes, peak_active_probes
        with probe_lock:
            active_probes += 1
            peak_active_probes = max(peak_active_probes, active_probes)
            if active_probes == 2:
                probe_started.set()
        gate.wait(5)
        with probe_lock:
            active_probes -= 1
        return False

    monkeypatch.setattr(comfy_setup, "find_comfyui", lambda _given=None: Path("ComfyUI"))
    monkeypatch.setattr(comfy_setup, "weights_present", slow_weights)
    monkeypatch.setattr(comfy_setup, "image_model_present", lambda _folder: False)
    dialogs = [ComfySetupDialog() for _ in range(3)]
    try:
        deadline = time.monotonic() + 3
        while not probe_started.is_set() and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)
        assert probe_started.is_set(), "zwei Dateiblicke dürfen unabhängig geprüft werden"
        assert peak_active_probes == 2

        gate.set()
        for dialog in dialogs:
            _wait_for_comfy_probe(dialog, qt_app)
        assert peak_active_probes == 2, "weitere Fenster dürfen keinen dritten Prüffaden starten"
    finally:
        gate.set()
        deadline = time.monotonic() + 3
        while active_probes and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.01)
        for dialog in dialogs:
            dialog.release()
            dialog.deleteLater()


def test_a_setup_that_cannot_start_says_why_and_offers_the_run_again(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Fehlschlag endet nicht mit „fehlgeschlagen", und der Knopf ist
    danach wieder der, der einrichtet.
    """
    from app.core.backends import comfy_setup
    from app.ui.comfy_dialog import ComfySetupDialog

    monkeypatch.setattr(comfy_setup, "find_comfyui", lambda given=None: Path("nirgendwo"))

    def refuse(*_args: object, **_kwargs: object) -> object:
        raise comfy_setup.SetupFailed("Dort liegt kein ComfyUI — erwartet wird custom_nodes.")

    monkeypatch.setattr(comfy_setup, "setup", refuse)
    dialog = ComfySetupDialog()
    try:
        _wait_for_comfy_probe(dialog, qt_app)

        dialog.start_button.click()
        for _ in range(100):
            qt_app.processEvents()
            if dialog._worker is None:
                break
            dialog._worker.wait(20)
        qt_app.processEvents()

        assert "custom_nodes" in dialog.state.text()
        assert dialog.start_button.text() == "Einrichten", "der Weg zurück ist derselbe Knopf"
        assert dialog.progress.isHidden()
    finally:
        dialog.release()
        dialog.deleteLater()


def test_closing_the_setup_while_it_runs_cancels_it_without_waiting(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Esc während der Einrichtung: abbrechen, ja — aber nicht zwei Sekunden
    auf den Thread warten. Den hält die Halteleine; eine späte Antwort bewegt
    den geschlossenen Dialog nicht mehr."""
    import threading
    import time

    from app.core.backends import comfy_setup
    from app.ui.comfy_dialog import ComfySetupDialog

    comfyui = tmp_path / "ComfyUI"
    (comfyui / "custom_nodes").mkdir(parents=True)
    monkeypatch.setattr(comfy_setup, "find_comfyui", lambda given=None: comfyui)
    gate = threading.Event()
    asked: list[bool] = []
    setup_paths: list[object] = []
    setup_choices: list[tuple[object, object]] = []
    setup_entered = threading.Event()

    def slow(
        comfyui: object,
        *_args: object,
        weights: object = None,
        image_model: object = None,
        cancelled: object = None,
        **_kwargs: object,
    ) -> object:
        setup_paths.append(comfyui)
        setup_choices.append((weights, image_model))
        setup_entered.set()
        gate.wait(10)
        asked.append(bool(callable(cancelled) and cancelled()))
        raise comfy_setup.SetupFailed("abgebrochen")

    monkeypatch.setattr(comfy_setup, "setup", slow)
    dialog = ComfySetupDialog()
    try:
        _wait_for_comfy_probe(dialog, qt_app)
        dialog.start_button.click()
        worker = dialog._worker
        assert worker is not None and worker.isRunning()
        for _ in range(100):
            qt_app.processEvents()
            if setup_entered.is_set():
                break
            worker.wait(10)
        assert setup_entered.is_set(), (
            "der Einrichtungsarbeiter muss den sichtbaren Zielpfad erhalten"
        )
        assert setup_paths == [str(comfyui)]
        assert setup_choices == [(True, True)], "gesperrte Häkchen müssen zur Einrichtung passen"
        assert not dialog.folder.isEnabled(), "der sichtbare Zielpfad bleibt beim Lauf fest"
        assert not dialog.choose.isEnabled(), "die Ordnerwahl bleibt beim Lauf gesperrt"
        assert not dialog.weights.isEnabled() and not dialog.image_model.isEnabled()
        started = time.perf_counter()
        dialog.reject()
        waited = time.perf_counter() - started
        assert waited < 0.5, f"Esc wartete {waited:.2f} s"
        gate.set()
        assert worker.wait(10_000)
        qt_app.processEvents()
        assert asked == [True], "der Lauf hat den Abbruch gesehen"
        assert dialog.state.text() != "abgebrochen", "eine späte Antwort bewegt den Dialog nicht"
    finally:
        gate.set()
        dialog.release()


def test_the_dialog_names_the_middle_state_before_the_run(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Drei Lagen, und die mittlere war die schlimmste.**

    „Bereit" stand da, sobald ein Port antwortete. Wer ComfyUI installiert und
    gestartet hatte, ohne die Knoten einzurichten, tippte seinen Satz, drückte
    *Erzeugen*, wartete — und erfuhr es danach.
    """
    from app.core.backends import mesh

    class Halb:
        """Ein ComfyUI, das läuft und die Knoten nicht kennt."""

        id = "scripted"
        available = True

        def readiness(self) -> mesh.Readiness:
            return mesh.Readiness.NO_NODES

    dialog = GenerateDialog(backend=Halb())
    wait_for_readiness(dialog, qt_app)

    assert dialog.readiness is mesh.Readiness.NO_NODES
    assert not dialog.available, "bereit ist es damit nicht"
    # Seit TRELLIS.2 sind alle Knoten eingebaut: Fehlt einer, ist ComfyUI zu
    # alt, und der Satz nennt die Version, ab der es geht (Regel 17).
    assert "zu alt" in dialog.state.text()
    assert mesh.MINIMUM_COMFYUI_TEXT in dialog.state.text()
    assert not dialog.setup.isHidden(), "und der Weg dorthin steht daneben"
    assert "Programme" in dialog.setup.text()


def test_the_button_leads_where_the_state_says(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwei Ziele: die Liste der Programme, wo ComfyUI fehlt oder zu alt ist, die
    Einrichtung, wo ein Modell fehlt — Knoten kann Solidon nicht nachlegen."""
    from app.core.backends import mesh

    class Lage:
        id = "scripted"

        def __init__(self, readiness: mesh.Readiness) -> None:
            self._readiness = readiness
            self.available = readiness is not mesh.Readiness.ABSENT

        def readiness(self) -> mesh.Readiness:
            return self._readiness

    for state, expected in (
        (mesh.Readiness.ABSENT, "programs"),
        (mesh.Readiness.NO_NODES, "programs"),
        (mesh.Readiness.NO_MODEL, "nodes"),
    ):
        dialog = GenerateDialog(backend=Lage(state))
        wait_for_readiness(dialog, qt_app)
        asked: list[str] = []
        # Die Liste wird ausdrücklich gebunden: ein Lambda, das sie aus dem
        # Schleifenkörper aufliest, zeigt beim zweiten Durchgang noch auf die
        # erste — und der Test wäre grün, ohne etwas zu prüfen.
        dialog.setupRequested.connect(lambda box=asked: box.append("programs"))
        dialog.nodesRequested.connect(lambda box=asked: box.append("nodes"))

        dialog.setup.click()

        assert asked == [expected], state


def test_an_unknown_answer_does_not_lock_the_button(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auf dem Port kann alles liegen — ein gesperrter Knopf wäre eine
    Behauptung darüber.
    """
    from PySide6.QtWidgets import QDialogButtonBox

    from app.core.backends import mesh

    class Fremd:
        id = "scripted"
        available = True

        def readiness(self) -> mesh.Readiness:
            return mesh.Readiness.UNKNOWN

    dialog = GenerateDialog(backend=Fremd())
    wait_for_readiness(dialog, qt_app)
    dialog.prompt.setText("ein Halter")

    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
    assert "Versuchen lässt es sich" in dialog.state.text()
    assert dialog.setup.isHidden(), "es gibt nichts einzurichten, was wir kennen"


def test_an_unexpected_error_does_not_leave_the_generator_waiting(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Lauf dauert Minuten — ein stillstehender Balken ist davon nicht zu
    unterscheiden.

    Der Arbeiter fing ``AppError``; alles andere — ein Netz, das trimesh nicht
    liest, eine Antwort in unbekannter Form — riss den Thread ab.
    """

    class Bricht:
        id = "scripted"
        available = True

        def text_to_mesh(self, prompt: str, *, seed: int = 0, progress: object = None) -> object:
            raise KeyError("outputs")

    monkeypatch.setattr("app.ui.generate_dialog.show_error", lambda *args: None)
    dialog = GenerateDialog(backend=Bricht())
    wait_for_readiness(dialog, qt_app)
    dialog.prompt.setText("ein Halter")
    dialog._start()
    for _ in range(200):
        qt_app.processEvents()
        if dialog._worker is None:
            break
        dialog._worker.wait(20)
    qt_app.processEvents()

    assert "unerwartet" in dialog.state.text()
    assert dialog.progress.isHidden(), "kein Balken über einem Lauf, den es nicht gibt"


@pytest.mark.parametrize("kind", ["generate", "setup"])
def test_an_unexpected_generator_error_offers_a_working_report_action(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Beide Dialoge reichen den Programmfehler an die wirklich geklickte Berichtshandlung."""
    from PySide6.QtWidgets import QMessageBox, QWidget

    from app.core.backends import comfy_setup
    from app.core.errors import REPORT_ERROR, InternalError
    from app.ui.comfy_dialog import ComfySetupDialog

    reported: list[object] = []

    class Host(QWidget):
        def error_handlers(self):
            return {REPORT_ERROR.id: reported.append}

    def choose_report(box: QMessageBox) -> int:
        next(button for button in box.buttons() if button.text() == str(REPORT_ERROR.label)).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", choose_report)
    monkeypatch.setattr(comfy_setup, "find_comfyui", lambda: Path("comfy"))
    host = Host()
    dialog = (
        GenerateDialog(backend=ScriptedMeshBackend(), parent=host)
        if kind == "generate"
        else ComfySetupDialog(host)
    )
    try:
        dialog._crashed("missing output")
        assert len(reported) == 1
        assert isinstance(reported[0], InternalError)
        assert str(reported[0].detail) == "missing output"
        assert dialog.progress.isHidden()
    finally:
        dialog.release()
        host.deleteLater()


def test_the_setup_dialog_says_how_long_a_step_has_been_running(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Einer der Schritte lädt mehrere Gigabyte.

    Die Zeit beginnt je Schritt neu: „Modell für den Weg aus Bild laden — rund
    8,0 GB (240 s)" sagt mehr als eine Gesamtzeit, denn nur dieser eine Schritt
    dauert.
    """
    from app.core.backends import comfy_setup
    from app.ui.comfy_dialog import ComfySetupDialog

    monkeypatch.setattr(comfy_setup, "find_comfyui", lambda given=None: Path("C:/ComfyUI"))
    monkeypatch.setattr(comfy_setup, "weights_present", lambda folder: False)
    dialog = ComfySetupDialog()
    try:
        _wait_for_comfy_probe(dialog, qt_app)
        dialog._note_step("Modell für den Weg aus Bild laden — rund 8,0 GB, das dauert")

        assert "Modell für den Weg aus Bild laden" in dialog.state.text()
        assert "(0 s)" in dialog.state.text(), "und wie lange er schon läuft"

        dialog._idle()
        assert not dialog._tick.isActive(), "danach zählt nichts mehr"
    finally:
        dialog.release()
        dialog.deleteLater()


def test_the_setup_dialog_names_version_licences_and_sizes_before_loading(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Vor dem ersten Download steht da, was geladen wird und unter welcher Lizenz.

    RM-003: Die Modelle stammen aus drei Lizenzen (MIT, Metas DINOv3-Lizenz,
    Apache-2.0); wer sie lädt, liest das im Dialog, nicht erst im Handbuch. Die
    Mindestfassung von ComfyUI steht daneben, weil die Knoten seit TRELLIS.2 aus
    ComfyUI selbst kommen, und jede Größe kommt aus den Modelldateien — kein
    Satz nennt mehr TripoSG oder SDXL.
    """
    from PySide6.QtWidgets import QCheckBox, QLabel

    from app.core.backends import comfy_setup, mesh
    from app.i18n import format_decimal
    from app.ui.comfy_dialog import ComfySetupDialog

    monkeypatch.setattr(comfy_setup, "find_comfyui", lambda given=None: Path("C:/ComfyUI"))
    monkeypatch.setattr(comfy_setup, "weights_present", lambda folder: False)
    monkeypatch.setattr(comfy_setup, "image_model_present", lambda folder: False)
    dialog = ComfySetupDialog()
    try:
        _wait_for_comfy_probe(dialog, qt_app)
        texts = [label.text() for label in dialog.findChildren(QLabel)]
        intro = next((text for text in texts if "DINOv3" in text), "")

        assert mesh.MINIMUM_COMFYUI_TEXT in intro, "ab welcher Fassung ComfyUI reicht"
        for licence in ("MIT", "TRELLIS.2", "BiRefNet", "DINOv3", "Apache-2.0", "FLUX.2 [klein]"):
            assert licence in intro, licence
        assert format_decimal(comfy_setup.WEIGHT_GIGABYTES, 1) in dialog.weights.text()
        assert format_decimal(comfy_setup.IMAGE_MODEL_GIGABYTES, 1) in dialog.image_model.text()
        assert dialog.weights.isEnabled() and dialog.image_model.isEnabled()
        said = " ".join(texts + [box.text() for box in dialog.findChildren(QCheckBox)])
        assert "TripoSG" not in said and "SDXL" not in said
    finally:
        dialog.release()
        dialog.deleteLater()


@pytest.mark.parametrize("apple", [False, True])
def test_the_setup_dialog_names_space_and_duration_before_loading(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, apple: bool
) -> None:
    """Voraussetzungen, ob dieser Rechner sie erfüllt, und die Dauer stehen da,
    bevor ein Byte geladen wird (RM-564, Entscheidung Robert 08.10.2026).

    Ein Kunde mit MacBook las erst beim Laden, dass es Dutzende Gigabyte
    werden. Die Zeile rechnet mit den gewählten Häkchen und dem freien Platz,
    warnt, wenn er nicht reicht, nennt Karte und gemessene Dauer — und auf
    einem Mac, dass beides dort gerechnet bzw. nicht gemessen ist.
    """
    from app.core.backends import comfy_setup, machine
    from app.i18n import format_decimal
    from app.ui.comfy_dialog import ComfySetupDialog

    monkeypatch.setattr(comfy_setup, "find_comfyui", lambda given=None: Path("C:/ComfyUI"))
    monkeypatch.setattr(comfy_setup, "weights_present", lambda folder: False)
    monkeypatch.setattr(comfy_setup, "image_model_present", lambda folder: False)
    monkeypatch.setattr(comfy_setup, "free_gigabytes", lambda _where: 12.0)
    found = (
        machine.Machine(apple_silicon=True, memory_gb=16.0)
        if apple
        else machine.Machine(memory_gb=32.0, card_name="RTX 4080", card_gb=16.0)
    )
    monkeypatch.setattr(machine, "this_machine", lambda: found)
    dialog = ComfySetupDialog()
    try:
        _wait_for_comfy_probe(dialog, qt_app)
        headroom = comfy_setup.HEADROOM_GIGABYTES
        both = comfy_setup.WEIGHT_GIGABYTES + comfy_setup.IMAGE_MODEL_GIGABYTES + headroom
        said = dialog.needs.text()
        assert "Voraussetzung: eine Grafikkarte" in said, said
        assert f"{format_decimal(both, 1)} GB freier Platz" in said, said
        assert "nur 12,0 GB" in said and "nur das Modell für den Weg aus Bild" in said
        assert "RTX 4080" in said and "Minuten" in said, "Karte und gemessene Dauer"
        assert ("nicht gemessen" in said) is apple, "auf dem Mac steht, dass es offen ist"

        dialog.image_model.setChecked(False)
        alone = dialog.needs.text()
        single = comfy_setup.WEIGHT_GIGABYTES + headroom
        assert f"{format_decimal(single, 1)} GB freier Platz" in alone, alone
        assert "Frei: 12,0 GB." in alone, "eines passt"
    finally:
        dialog.release()
        dialog.deleteLater()


@pytest.mark.parametrize(("language", "words"), [("de", "rund 7,5 GB"), ("en", "about 7.5 GB")])
def test_the_setup_dialog_says_which_old_folders_it_removes_before_it_does(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, language: str, words: str
) -> None:
    """Entscheidung Robert (07.10.2026): Die Einrichtung räumt Solidons alte
    TripoSG-Einrichtung weg — und sagt vorher, welche Ordner und wie viel.

    Der Hinweis steht nur da, wo es die alte Einrichtung gibt; ein ComfyUI
    ohne sie bekommt keinen Satz über etwas, das nicht da ist.
    """
    from app.core.backends import comfy_setup
    from app.i18n import set_language
    from app.i18n.catalog import install_language
    from app.ui.comfy_dialog import ComfySetupDialog

    old = tmp_path / "alt"
    nodes = old / comfy_setup.LEGACY_NODES
    nodes.mkdir(parents=True)
    for name in ("nodes.py", "__init__.py"):
        (nodes / name).write_text("# alt", encoding="utf-8")
    weights = old / comfy_setup.LEGACY_WEIGHTS
    weights.mkdir(parents=True)
    (weights / comfy_setup.LEGACY_MARKER).write_text("{}", encoding="utf-8")
    clean = tmp_path / "neu"
    (clean / "custom_nodes").mkdir(parents=True)

    monkeypatch.setattr(comfy_setup, "find_comfyui", lambda given=None: Path(given or old))
    monkeypatch.setattr(comfy_setup, "weights_present", lambda folder: False)
    monkeypatch.setattr(comfy_setup, "image_model_present", lambda folder: False)
    monkeypatch.setattr(comfy_setup, "legacy_gigabytes", lambda found: 7.5 if found else 0.0)
    install_language(language)
    set_language(language)
    dialog = ComfySetupDialog()
    try:
        _wait_for_comfy_probe(dialog, qt_app)
        said = dialog.legacy.text()
        assert not dialog.legacy.isHidden(), "vor dem Einrichten steht da, was geht"
        assert comfy_setup.LEGACY_NODES in said and comfy_setup.LEGACY_WEIGHTS in said
        assert words in said, "und wie viel Platz das macht"
        assert dialog.start_button.isEnabled(), "angesagt, nicht gesperrt"

        dialog.folder.setText(str(clean))
        dialog._refresh_folder_state()
        _wait_for_comfy_probe(dialog, qt_app)
        assert dialog.legacy.isHidden(), "ohne alte Einrichtung kein Satz darüber"
    finally:
        set_language("de")
        dialog.release()
        dialog.deleteLater()


def test_the_setup_dialog_promises_only_what_the_removal_keeps(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Die genannten Ordner gehen ganz; versprochen wird nur, dass andere bleiben (G-6).

    Der Satz „Was Sie selbst dorthin gelegt haben, bleibt“ stimmte nicht:
    ``remove_legacy`` löscht einen erkannten Ordner samt allem darin.
    """
    from app.core.backends import comfy_setup
    from app.ui.comfy_dialog import ComfySetupDialog

    old = tmp_path / "alt"
    nodes = old / comfy_setup.LEGACY_NODES
    nodes.mkdir(parents=True)
    for name in ("nodes.py", "__init__.py"):
        (nodes / name).write_text("# alt", encoding="utf-8")
    monkeypatch.setattr(comfy_setup, "find_comfyui", lambda given=None: Path(given or old))
    monkeypatch.setattr(comfy_setup, "weights_present", lambda folder: False)
    monkeypatch.setattr(comfy_setup, "image_model_present", lambda folder: False)
    dialog = ComfySetupDialog()
    try:
        _wait_for_comfy_probe(dialog, qt_app)
        said = dialog.legacy.text()
        assert "Andere Ordner bleiben unberührt." in said, said
        assert "selbst dorthin gelegt" not in said
    finally:
        dialog.release()
        dialog.deleteLater()


@pytest.mark.parametrize("done", [True, False])
def test_the_setup_dialog_names_an_old_folder_that_stayed_and_the_way_out(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, done: bool
) -> None:
    """Blieb von der alten Einrichtung etwas stehen, meldet der Dialog keinen Erfolg (G-6).

    Ein laufendes ComfyUI hält den alten Knoten offen und lädt den
    TripoSG-Quelltext weiter. Bis dahin las der Kunde „Eingerichtet“ und
    erfuhr nichts davon; jetzt nennt die Zeile den Ordner und den Ausweg —
    auch nach einem Abbruch.
    """
    from app.core.backends import comfy_setup
    from app.ui.comfy_dialog import ComfySetupDialog

    monkeypatch.setattr(comfy_setup, "find_comfyui", lambda given=None: tmp_path)
    monkeypatch.setattr(comfy_setup, "weights_present", lambda folder: True)
    monkeypatch.setattr(comfy_setup, "image_model_present", lambda folder: True)
    dialog = ComfySetupDialog()
    try:
        _wait_for_comfy_probe(dialog, qt_app)
        dialog._finished(
            comfy_setup.Result(
                comfyui=tmp_path,
                weights=True,
                image_model=True,
                reason="" if done else "Abgebrochen.",
                legacy_left=(comfy_setup.LEGACY_NODES,),
            )
        )
        said = dialog.state.text()
        assert comfy_setup.LEGACY_NODES in said, said
        assert "ComfyUI beenden und Einrichten erneut starten" in said, said
        assert dialog.state.property("role") == "warning"
        assert "Eingerichtet. ComfyUI einmal neu starten" not in said

        dialog._finished(comfy_setup.Result(comfyui=tmp_path, weights=True, image_model=True))
        assert dialog.state.property("role") == "ok", "ohne Rest der gewohnte Satz"
    finally:
        dialog.release()
        dialog.deleteLater()


def test_the_dialog_asks_for_the_way_it_would_actually_run(qt_app: QApplication) -> None:
    """**Ein Bild wechselt den Weg, also auch die Frage.**

    Derselbe Dialog fährt beide Wege: Mit gewähltem Bild ``image_to_mesh``,
    ohne ``text_to_mesh``. Gefragt wurde immer der Bildweg — wer aus Text
    erzeugen wollte und kein Bildmodell hatte, las „Bereit" und erfuhr es beim
    Abschicken.
    """
    from app.ui.generate_dialog import GenerateDialog

    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    wait_for_readiness(dialog, qt_app)

    assert dialog._workflow() == "text_to_mesh", "ohne Bild ist es der Textweg"
    dialog._image = b"ein Bild"
    assert dialog._workflow() == "image_to_mesh"


def test_a_missing_model_gets_its_own_sentence_and_a_button(qt_app: QApplication) -> None:
    """Vier Lagen, vier Sätze — und der vierte nennt den Ausweg.

    Ein Bild zu wählen umgeht das fehlende Bildmodell vollständig, und genau das
    steht dort: Aus Text wird erst ein Bild, und dafür braucht ComfyUI ein
    Bildmodell.
    """
    from app.core.backends import mesh
    from app.ui.generate_dialog import GenerateDialog

    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    wait_for_readiness(dialog, qt_app)
    dialog._readiness = mesh.Readiness.NO_MODEL
    dialog._missing_roles = frozenset({"image", "text_encoder"})
    dialog._update_state()

    gesagt = dialog.state.text()
    assert "Bildmodell" in gesagt
    assert "Bild zu wählen" in gesagt, "Regel 17: was jetzt hilft"
    assert dialog.setup.isVisible() or not dialog.isVisible(), "und ein Knopf dazu"

    # **Und der Knopf holt es** (21.09.2026). Bis dahin nannte der Satz Datei
    # und Ordner, und der Kunde sollte das Modell selbst besorgen — Robert
    # tippte einen Satz und las, dass ein Bild verlangt wird. Jetzt steht die
    # Größe im Satz, und der Knopf führt in die Einrichtung, die das Bildmodell
    # lädt: derselbe Weg wie bei fehlenden Knoten.
    from app.core.backends import comfy_setup

    assert f"{comfy_setup.IMAGE_MODEL_GIGABYTES:g}".replace(".", ",") in gesagt, "die Größe"
    assert "Bildmodell" in dialog.setup.text()
    wege: list[str] = []
    dialog.nodesRequested.connect(lambda: wege.append("nodes"))
    dialog.setupRequested.connect(lambda: wege.append("setup"))
    dialog._ask_for_setup()
    assert wege == ["nodes"], "das Bildmodell holt die Einrichtung, nicht die Programmliste"


def test_a_missing_shape_model_is_not_called_the_image_model(qt_app: QApplication) -> None:
    """Fehlt TRELLIS.2, fehlt beiden Wegen etwas — und das ist nicht das Bildmodell.

    Der Satz nannte bei jeder fehlenden Rolle das Bildmodell des Textwegs und
    schickte zum Ausweg „ein Bild wählen“, der hier nichts hilft. Er nennt
    jetzt das Modell, das fehlt, und seine Größe; der Knopf führt in dieselbe
    Einrichtung.
    """
    from app.core.backends import comfy_setup, mesh
    from app.ui.generate_dialog import GenerateDialog

    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    wait_for_readiness(dialog, qt_app)
    dialog._readiness = mesh.Readiness.NO_MODEL
    dialog._missing_roles = frozenset({"shape", "image"})
    dialog._update_state()

    gesagt = dialog.state.text()
    assert "Bild zu wählen" not in gesagt
    assert f"{comfy_setup.WEIGHT_GIGABYTES:g}".replace(".", ",") in gesagt, "die Größe"
    wege: list[str] = []
    dialog.nodesRequested.connect(lambda: wege.append("nodes"))
    dialog.setupRequested.connect(lambda: wege.append("setup"))
    dialog._ask_for_setup()
    assert wege == ["nodes"]


class WaitingBackend:
    """Ein Generator, der wartet, bis jemand abbricht — wie ComfyUI beim Fragen.

    ``ScriptedMeshBackend`` fragt seinen Rückruf einmal und ist dann fertig;
    hier geht es um den Zustand *dazwischen*, in dem der echte Weg Minuten
    verbringt. Die Schranke aus fünf Sekunden ist keine Wartezeit, sondern eine
    Reißleine: Bricht niemand ab, endet der Wurf mit einem Fehler statt mit
    einem hängenden Testlauf.
    """

    def __init__(self) -> None:
        self.started = threading.Event()
        self.asked = 0

    @property
    def id(self) -> str:
        return "scripted"

    @property
    def available(self) -> bool:
        return True

    def _poll(self, cancelled: object) -> None:
        self.started.set()
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            self.asked += 1
            if callable(cancelled) and cancelled():
                raise OperationCancelled
            time.sleep(0.005)
        raise AssertionError("niemand hat abgebrochen — der Merker kam nie an")

    def text_to_mesh(self, prompt: str, **kwargs: object) -> object:
        self._poll(kwargs.get("cancelled"))
        raise AssertionError("unerreichbar")

    def image_to_mesh(self, image: bytes, **kwargs: object) -> object:
        self._poll(kwargs.get("cancelled"))
        raise AssertionError("unerreichbar")


def test_cancelling_stops_the_worker_instead_of_leaving_it_polling(qt_app: QApplication) -> None:
    """§15.6: *Abbrechen* schloss den Dialog und ließ den Arbeiter laufen.

    Der Rückruf, den die Schnittstelle dafür vorsieht, wurde nicht gereicht —
    der Arbeiter fragte ComfyUI bis zu einer Stunde weiter
    (``mesh.STUCK_SECONDS``) und meldete sein Ergebnis an ein Fenster, das es
    nicht mehr gab. Geprüft wird über den Knopf und nicht über die Methode
    dahinter: Die Verbindung ist der Teil, der fehlen kann.

    Und der Ausgang ist **still**. ``OperationCancelled`` ist kein
    ``AppError`` (``tests/test_errors.py``); ungefangen käme sie über
    ``crashed`` als „Dabei ist etwas schiefgegangen, womit hier niemand
    gerechnet hat" beim Kunden an — für etwas, das er selbst ausgelöst hat.
    """
    backend = WaitingBackend()
    dialog = GenerateDialog(backend=backend)
    wait_for_readiness(dialog, qt_app)
    dialog.prompt.setText("eine Figur")

    crashes: list[str] = []
    problems: list[object] = []
    dialog._start()
    worker = dialog._worker
    assert worker is not None
    worker.crashed.connect(crashes.append)
    worker.failed.connect(problems.append)
    assert backend.started.wait(5.0), "der Wurf läuft"
    assert not worker.cancelled(), "und niemand hat abgebrochen"

    dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).click()

    assert worker.cancelled(), "der Knopf setzt den Merker"
    assert worker.wait(5000), "und der Arbeiter endet, statt weiterzufragen"
    qt_app.processEvents()
    assert not crashes, "ein Abbruch ist kein Absturz"
    assert not problems, "und kein Fehler"


def test_letting_the_dialog_go_stops_the_worker_too(qt_app: QApplication) -> None:
    """Der zweite Ausgang: Ein Dialog wird nicht nur geschlossen, er wird auch
    weggeräumt (``release``, die Aufräumhilfe in ``tests/conftest.py``).

    Ein Arbeiter, der nur den einen Weg kennt, überlebt den anderen — und ein
    Thread, der sein Fenster überlebt, nimmt den Prozess mit.
    """
    backend = WaitingBackend()
    dialog = GenerateDialog(backend=backend)
    wait_for_readiness(dialog, qt_app)
    dialog.prompt.setText("eine Figur")
    dialog._start()
    worker = dialog._worker
    assert worker is not None
    assert backend.started.wait(5.0)

    dialog.release()

    assert worker.cancelled()
    assert worker.wait(5000)
    qt_app.processEvents()


class LageMitZaehler:
    """Ein Generator in einer bestimmten Lage, der mitzählt, ob er läuft.

    Der Unterschied zu :class:`CountingBackend` ist die Frage: Dort geht es
    darum, wie oft die Bereitschaft erhoben wird, hier darum, ob ein Klick auf
    *Erzeugen* wirklich einen Wurf auslöst.
    """

    id = "scripted"
    available = True

    def __init__(self, lage: object) -> None:
        self._lage = lage
        self.runs = 0

    def readiness(self, workflow: str = "image_to_mesh") -> object:
        return self._lage

    def text_to_mesh(self, prompt: str, *, seed: int = 0, progress=None, cancelled=None) -> object:
        self.runs += 1
        raise OperationCancelled


def test_the_generate_button_either_works_or_says_why(qt_app: QApplication) -> None:
    """**Ein Knopf, der klickbar ist und nichts tut, ist schlimmer als einer,
    der gesperrt ist.**

    Der Knopf hing an „alles außer ABSENT", :meth:`_start` an ``available``
    („genau READY"). Dazwischen lagen drei Lagen, in denen *Erzeugen*
    klickbar war und der Klick folgenlos blieb: kein Wurf, kein Balken, kein
    Satz — gemessen mit einer Attrappe je Lage.

    Der gesperrte Knopf hat den Satz daneben, der ihn erklärt, und den zweiten
    Knopf, der die Lage behebt (Regel 17). ``UNKNOWN`` bleibt klickbar: Dort
    antwortet etwas, das wir nicht kennen, und ein gesperrter Knopf wäre eine
    Behauptung darüber — er muss dann aber auch starten.
    """
    from app.core.backends import mesh

    for lage, laeuft in (
        (mesh.Readiness.READY, True),
        (mesh.Readiness.UNKNOWN, True),
        (mesh.Readiness.NO_NODES, False),
        (mesh.Readiness.NO_MODEL, False),
    ):
        backend = LageMitZaehler(lage)
        dialog = GenerateDialog(backend=backend)
        wait_for_readiness(dialog, qt_app)
        dialog.prompt.setText("ein Halter")

        knopf = ok(dialog)
        assert knopf.isEnabled() is laeuft, f"{lage}: Knopf und Wirkung müssen zusammenpassen"

        # Über den Klick und nicht über ``_start``: Die Verbindung dazwischen
        # ist der Teil, der auseinanderlaufen kann.
        knopf.click()
        worker = dialog._worker
        if worker is not None:
            worker.wait(5000)
        qt_app.processEvents()

        assert (backend.runs > 0) is laeuft, f"{lage}: geklickt heißt gelaufen, oder gesperrt"
        if not laeuft:
            assert not dialog.setup.isHidden(), f"{lage}: und der Weg zur Behebung steht daneben"
        dialog.release()


def test_the_dialog_shows_what_comfyui_said(qt_app: QApplication) -> None:
    """Der Satz verweist auf Angaben daneben — also müssen sie daneben stehen.

    ``mesh._failed`` schreibt „Was es dazu sagt, steht daneben" und legt
    Knotennamen und ComfyUIs eigene Fehlerzeile in ``values``: „Torch not
    compiled with CUDA enabled", „No module named …", Speichermangel. Der
    Dialog zeigte Titel, ``detail`` und die Vorschläge — die Werte fielen
    weg, und ausgerechnet die Zeile, mit der jemand zum Support geht, kam nie
    an. Elf Fehlerpfade in ``backends/mesh.py`` tragen solche Werte.
    """
    from app.core.backends import mesh
    from app.i18n import _

    grund = "Torch not compiled with CUDA enabled"

    class Bricht:
        id = "scripted"
        available = True

        def readiness(self, workflow: str = "image_to_mesh") -> mesh.Readiness:
            return mesh.Readiness.READY

        def text_to_mesh(
            self, prompt: str, *, seed: int = 0, progress=None, cancelled=None
        ) -> object:
            raise mesh.GenerationFailed(
                title=_("Der Generator hat den Auftrag abgebrochen."),
                detail=_("ComfyUI hat die Erzeugung mit einem Fehler beendet."),
                values={"node": "Trellis2ShapeStage", "reason": grund},
            )

    dialog = GenerateDialog(backend=Bricht())
    wait_for_readiness(dialog, qt_app)
    dialog.prompt.setText("ein Halter")
    ok(dialog).click()
    worker = dialog._worker
    assert worker is not None
    worker.wait(5000)
    qt_app.processEvents()

    gesagt = dialog.state.text()
    assert grund in gesagt, "der Grund, mit dem jemand zum Support geht"
    assert "Trellis2ShapeStage" in gesagt, "und der Schritt, in dem es riss"
    assert dialog.progress.isHidden(), "kein Balken über einem Lauf, den es nicht gibt"
    dialog.release()


class MitAuswahl:
    """Ein ComfyUI, das für zwei Rollen mehrere Dateien anbietet."""

    id = "scripted"
    available = True

    def __init__(self, choices: dict[str, tuple[str, ...]]) -> None:
        self._choices = choices

    def readiness(self, workflow: str = "image_to_mesh") -> object:
        from app.core.backends import mesh

        return mesh.Readiness.READY

    def model_choices(self, workflow: str = "image_to_mesh") -> dict[str, tuple[str, ...]]:
        return dict(self._choices)

    def text_to_mesh(self, prompt: str, *, seed: int = 0, progress=None, cancelled=None) -> object:
        from app.core.errors import OperationCancelled

        raise OperationCancelled


def test_a_role_with_a_real_choice_gets_a_field(qt_app: QApplication) -> None:
    """**Wie beim Sprachmodell: Die Wahl gehört dem Kunden.**

    Die Rollenauflösung trifft das Übliche, und wer drei Feintunings
    nebeneinander hat, hat sie aus einem Grund, der in keinem Muster steht.

    Ein Feld gibt es nur, wo es wirklich etwas zu wählen gibt: Eine Auswahl
    ohne Alternative ist keine (§2.4), und eine Rolle ohne Namen wäre eine
    Frage nach einem Schlüssel (Regel 20).
    """
    from PySide6.QtWidgets import QComboBox

    dialog = GenerateDialog(
        backend=MitAuswahl(
            {
                "image": ("a_sdxl.safetensors", "b_sdxl.safetensors"),
                "shape": ("nur_trellis.safetensors",),
                "shape_vae": ("eins.safetensors", "zwei.safetensors"),
            }
        )
    )
    wait_for_readiness(dialog, qt_app)

    assert "image" in dialog._model_fields, "zwei Dateien, also eine Wahl"
    assert "shape" not in dialog._model_fields, "eine Datei ist keine Wahl"
    assert "shape_vae" not in dialog._model_fields, "eine Rolle ohne Namen steht nicht zur Wahl"

    box = dialog._model_fields["image"]
    assert isinstance(box, QComboBox)
    assert box.itemData(0) == "", "die Vorgabe steht zuerst und heißt „Automatisch“"
    assert [box.itemData(i) for i in range(1, box.count())] == [
        "a_sdxl.safetensors",
        "b_sdxl.safetensors",
    ], "in ComfyUIs Reihenfolge, nicht in unserer"
    dialog.release()


def test_the_choice_is_remembered_before_the_run(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gemerkt wird **vor** dem Wurf, denn der Wurf liest sie.

    ``ComfyBackend._pick`` holt die Wahl aus den Einstellungen und nicht aus
    diesem Dialog — der Kern kennt kein Fenster (§7). Ein zweiter Weg, ihm den
    Wert mitzugeben, wäre ein zweiter Weg zu derselben Sache.
    """
    from app.core.backends import mesh

    gemerkt: dict[str, str] = {}
    monkeypatch.setattr(mesh, "remember_model", lambda role, name: gemerkt.update({role: name}))
    monkeypatch.setattr(mesh, "configured_model", lambda role: "")

    dialog = GenerateDialog(
        backend=MitAuswahl({"image": ("a_sdxl.safetensors", "b_sdxl.safetensors")})
    )
    wait_for_readiness(dialog, qt_app)
    dialog.prompt.setText("ein Halter")

    box = dialog._model_fields["image"]
    box.setCurrentIndex(box.findData("b_sdxl.safetensors"))
    ok(dialog).click()
    worker = dialog._worker
    if worker is not None:
        worker.wait(5000)
    qt_app.processEvents()

    assert gemerkt == {"image": "b_sdxl.safetensors"}, (
        "die Wahl liegt vor dem Wurf in den Einstellungen"
    )
    dialog.release()


def test_no_choice_no_section(qt_app: QApplication) -> None:
    """Ein leerer Abschnitt in „Weitere Einstellungen“ wäre ein Versprechen
    ohne Inhalt.

    Der Testdoppel kennt die Frage gar nicht — ein Backend nach §27 muss sie
    nicht beantworten, und dann gibt es nichts zu wählen.
    """
    dialog = GenerateDialog(backend=ScriptedMeshBackend(fallback=b""))
    wait_for_readiness(dialog, qt_app)

    assert not dialog._model_fields
    assert dialog._models.isHidden() or not dialog.isVisible()
    dialog.release()


def test_the_check_shows_that_it_is_running(qt_app: QApplication) -> None:
    """„Generator wird geprüft …" stand als nackte Zeile im leeren Dialog.

    Ob die Prüfung läuft oder hängengeblieben ist, sah man ihr nicht an —
    gemessen am gebauten Dialog: eine Wartezeile, **null** sichtbare Balken.
    Zum Vergleich hat der Zusatzprogramme-Dialog daneben einen laufenden;
    deshalb bekommt nur diese Stelle einen, und nicht alle vier Wartezeilen
    der Anwendung einen zweiten Anzeiger.

    Unbestimmt, weil eine Prüfung keinen Fortschritt hat, den jemand ehrlich
    beziffern könnte — und danach zurückgestellt: Der Erzeugungslauf setzt
    nur ``setValue`` und erbte sonst einen Balken, der bei fünfzig Prozent
    weiterläuft, als wüsste er nichts.
    """
    from app.ui.generate_dialog import GenerateDialog

    dialog = GenerateDialog()
    try:
        dialog.show()
        qt_app.processEvents()
        assert dialog.progress.isVisibleTo(dialog), "die Prüfung läuft ohne jedes Zeichen"
        assert dialog.progress.minimum() == dialog.progress.maximum() == 0, (
            "ein Balken mit Prozenten behauptet einen Fortschritt, den niemand kennt"
        )
    finally:
        dialog.hide()
        release = getattr(type(dialog), "release", None)
        if release is not None:
            release(dialog)
        for _ in range(3):
            qt_app.processEvents()


class _HeldBackend(ScriptedMeshBackend):
    """Ein Generator, der erst liefert, wenn der Test ihn lässt — und zählt."""

    def __init__(self, gate: threading.Event) -> None:
        super().__init__(fallback=(MESHES / "cube_clean.stl").read_bytes())
        self.gate = gate
        self.started = 0

    def text_to_mesh(self, prompt: str, **kwargs: object) -> object:
        self.started += 1
        self.gate.wait(10.0)
        return super().text_to_mesh(prompt, **kwargs)  # type: ignore[arg-type]


def test_editing_the_prompt_keeps_the_running_generation_visible(qt_app: QApplication) -> None:
    """Ein geänderter nächster Auftrag lässt Fortschritt und Schritt des laufenden stehen."""
    gate = threading.Event()
    dialog = GenerateDialog(backend=_HeldBackend(gate))
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.prompt.setText("Würfel")
        dialog._start()
        assert dialog._worker is not None
        dialog._on_step(0.37, "Geometrie wird erzeugt")
        dialog.prompt.setText("Würfel mit Füßen")
        assert not dialog.progress.isHidden()
        assert (dialog.progress.minimum(), dialog.progress.maximum()) == (0, 100)
        assert dialog.progress.value() == 37
        assert dialog.state.text() == "Geometrie wird erzeugt"
        assert not ok(dialog).isEnabled()
        assert dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).isEnabled()
    finally:
        gate.set()
        dialog.release()
        dialog.deleteLater()


def test_another_attempt_during_a_run_does_not_start_a_second_job(qt_app: QApplication) -> None:
    """Gesamtreview 05.09.2026, UI-23: ``_running`` sperrte nur den Hauptknopf;
    „Noch ein Versuch" blieb bedienbar, und ``_start`` hatte keinen eigenen
    Wächter — zwei schnelle Klicks starteten zwei Aufträge, und Abbrechen
    erreichte nur den zuletzt gemerkten."""
    gate = threading.Event()
    backend = _HeldBackend(gate)
    dialog = GenerateDialog(backend=backend)
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.prompt.setText("Würfel")
        dialog._start()
        first = dialog._worker
        assert first is not None, "der erste Auftrag läuft"
        assert not dialog.again.isEnabled(), "der Wiederholknopf ist während des Laufs gesperrt"

        dialog._try_again()

        assert dialog._worker is first, "kein zweiter Auftrag, solange der erste läuft"
        gate.set()
        assert first.wait(10_000)
        qt_app.processEvents()
        assert backend.started == 1
        assert dialog.again.isEnabled(), "nach dem Lauf steht der Knopf wieder"
    finally:
        gate.set()
        dialog.release()
        dialog.deleteLater()


def test_an_unreadable_image_is_said_not_thrown(qt_app: QApplication, tmp_path: Path) -> None:
    """Ein Bild, das inzwischen fehlt oder gesperrt ist, warf ``OSError`` aus
    dem Slot — beim Ablegen aus dem Chatfenster bis ins Hauptfenster."""
    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.set_image(tmp_path / "weg.png")

        assert dialog._image is None, "kein halbes Bild"
        assert "weg.png" in dialog.state.text(), dialog.state.text()
    finally:
        dialog.release()
        dialog.deleteLater()


def test_a_chosen_image_can_be_taken_back_and_rests_the_description(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """Mit Bild fährt der Dialog den Bildweg, und die Beschreibung ging still
    verloren; zurück zum Textweg führte nur ein neuer Dialog.

    Jetzt ruht das Beschreibungsfeld mit Grund, und *Bild entfernen* führt
    zurück.
    """
    picture = tmp_path / "skizze.png"
    picture.write_bytes(b"\x89PNG\r\n\x1a\n")
    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    try:
        wait_for_readiness(dialog, qt_app)
        assert not dialog.drop_picture.isVisibleTo(dialog)

        dialog.set_image(picture)
        wait_for_readiness(dialog, qt_app)

        assert dialog._workflow() == "image_to_mesh"
        assert not dialog.prompt.isEnabled(), "die Beschreibung ruht, solange ein Bild gilt"
        assert dialog.prompt.toolTip(), "und sagt, warum"
        assert dialog.drop_picture.isVisibleTo(dialog)

        dialog.drop_picture.click()
        wait_for_readiness(dialog, qt_app)

        assert dialog._workflow() == "text_to_mesh"
        assert dialog.prompt.isEnabled()
        assert not dialog.drop_picture.isVisibleTo(dialog)
        assert dialog.picture_label.text() == "Kein Bild gewählt"
    finally:
        dialog.release()
        dialog.deleteLater()


def test_cancelling_a_further_try_keeps_the_finished_ones(qt_app: QApplication) -> None:
    """Abbrechen während „Noch ein Versuch“ nahm den ganzen Dialog mit, und der
    fertige erste Versuch war verloren (RM-362, W3-2). Jetzt endet nur der
    laufende Wurf; ein zweites Abbrechen schließt."""
    dialog = GenerateDialog(backend=WaitingBackend())
    cancel = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
    closed: list[int] = []
    dialog.finished.connect(closed.append)
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.prompt.setText("eine Figur")
        dialog.tries = [_generated((1.0, 2.0, 0.5))]
        dialog._show_tries()
        backend = dialog.backend
        assert isinstance(backend, WaitingBackend)
        dialog._try_again()
        worker = dialog._worker
        assert worker is not None
        assert backend.started.wait(5.0), "der weitere Wurf läuft"

        cancel.click()
        assert worker.wait(5000), "der laufende Wurf endet"
        _settle(qt_app)

        assert not closed, "der Dialog bleibt offen"
        assert len(dialog.tries) == 1, "der fertige Versuch bleibt"
        assert ok(dialog).isEnabled(), "und lässt sich übernehmen"
        assert ok(dialog).text() == "Übernehmen"

        cancel.click()
        assert closed == [GenerateDialog.DialogCode.Rejected.value], "das zweite Abbrechen schließt"
    finally:
        dialog.release()
        dialog.deleteLater()
    qt_app.processEvents()


class SlowStopBackend(WaitingBackend):
    """Ein Generator, dessen Abbruch ausläuft: Er sieht den Merker und braucht
    bis zum Ende, bis ``stop`` gesetzt ist — wie ein Diffusionsschritt, der
    noch fertig rechnet."""

    def __init__(self) -> None:
        super().__init__()
        self.seen = threading.Event()
        self.stop = threading.Event()

    def _poll(self, cancelled: object) -> None:
        self.started.set()
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if callable(cancelled) and cancelled():
                self.seen.set()
                self.stop.wait(5.0)
                raise OperationCancelled
            time.sleep(0.005)
        raise AssertionError("niemand hat abgebrochen — der Merker kam nie an")


def test_a_second_cancel_while_the_first_runs_out_discards_nothing(qt_app: QApplication) -> None:
    """Solange der Abbruch eines weiteren Versuchs noch auslief, schloss ein
    zweiter Klick auf *Abbrechen* den Dialog und verwarf Versuch 1 (RM-418).
    Der Knopf ist in dieser Zeit gesperrt und sagt warum; auch Esc verwirft
    nichts. Danach schließt *Abbrechen* wie gewohnt."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    dialog = GenerateDialog(backend=SlowStopBackend())
    cancel = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
    closed: list[int] = []
    dialog.finished.connect(closed.append)
    backend = dialog.backend
    assert isinstance(backend, SlowStopBackend)
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.show()
        dialog.prompt.setText("eine Figur")
        dialog.tries = [_generated((1.0, 2.0, 0.5))]
        dialog._show_tries()
        dialog._try_again()
        worker = dialog._worker
        assert worker is not None
        assert backend.started.wait(5.0), "der weitere Wurf läuft"

        QTest.mouseClick(cancel, Qt.MouseButton.LeftButton)
        assert backend.seen.wait(5.0), "der Abbruch ist angekommen und läuft aus"
        _settle(qt_app)
        assert not cancel.isEnabled(), "während des Auslaufens ist Abbrechen gesperrt"
        assert cancel.toolTip(), "und sagt warum"
        QTest.mouseClick(cancel, Qt.MouseButton.LeftButton)
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        _settle(qt_app)
        assert not closed, "ein zweites Abbrechen verwirft nichts"
        assert len(dialog.tries) == 1

        backend.stop.set()
        assert worker.wait(5000), "der laufende Wurf endet"
        _settle(qt_app)
        assert not closed and len(dialog.tries) == 1, "der fertige Versuch bleibt"
        assert cancel.isEnabled() and not cancel.toolTip(), "danach ist Abbrechen wieder frei"
        QTest.mouseClick(cancel, Qt.MouseButton.LeftButton)
        assert closed == [GenerateDialog.DialogCode.Rejected.value], "und schließt"
    finally:
        backend.stop.set()
        dialog.release()
        dialog.deleteLater()
    qt_app.processEvents()


def test_a_failure_that_names_the_setup_offers_it_as_a_button(qt_app: QApplication) -> None:
    """Der Ausweg stand nur als Text da; die Bereitschaft meldete weiter
    „bereit“, und die Menüs lagen hinter dem Dialog (RM-362, W3-3)."""
    from app.core.backends.mesh import GenerationFailed
    from app.core.errors import CANCEL, INSTALL_MISSING, RETRY

    dialog = GenerateDialog(backend=ScriptedMeshBackend(fallback=b"solid x\n"))
    asked: list[bool] = []
    dialog.setupRequested.connect(lambda: asked.append(True))
    try:
        wait_for_readiness(dialog, qt_app)
        assert not dialog.setup.isVisibleTo(dialog), "bereit: kein Einrichten-Knopf"
        dialog._on_failed(
            GenerationFailed(
                title="Die 3D-Modell-Erzeugung konnte nicht starten.",
                detail="ComfyUI antwortet nicht.",
                suggestions=(INSTALL_MISSING, CANCEL),
            )
        )
        assert dialog.setup.isVisibleTo(dialog), "der Ausweg ist ein Knopf"
        assert dialog.setup.text() == str(INSTALL_MISSING.label)
        dialog.prompt.setText("weiter getippt")
        assert dialog.setup.isVisibleTo(dialog), "Tippen nimmt den Ausweg nicht weg"
        dialog.setup.click()
        assert asked == [True], "der Knopf führt zur Einrichtung"

        dialog._on_failed(
            GenerationFailed(
                title="Die 3D-Modell-Erzeugung ist gescheitert.",
                detail="Speicher voll.",
                suggestions=(RETRY, CANCEL),
            )
        )
        assert not dialog.setup.isVisibleTo(dialog), "ohne Einrichtung als Rat kein Knopf"
    finally:
        dialog.release()
        dialog.deleteLater()
    qt_app.processEvents()


def test_after_a_run_the_tries_and_the_next_button_are_in_view(qt_app: QApplication) -> None:
    """Nach dem Lauf lagen Versuchsliste und „Noch ein Versuch“ unter dem
    sichtbaren Bereich, neben dem Satz, der auf den Knopf verweist (RM-340)."""
    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    try:
        dialog.show()
        wait_for_readiness(dialog, qt_app)
        _settle(qt_app)
        dialog.tries = [_generated((1.0, 2.0, 0.5))]
        dialog._show_tries()
        _settle(qt_app)

        viewport = dialog._scroll.viewport()
        for widget in (dialog.attempts, dialog.again):
            top_left = widget.mapTo(viewport, widget.rect().topLeft())
            bottom = widget.mapTo(viewport, widget.rect().bottomLeft()).y()
            assert top_left.y() >= 0 and bottom <= viewport.rect().bottom(), (
                f"{widget.objectName() or type(widget).__name__} liegt außerhalb "
                f"({top_left.y()}…{bottom} in {viewport.height()})"
            )
    finally:
        dialog.wait_for_workers()
        dialog.close()
        dialog.deleteLater()
    qt_app.processEvents()


def test_a_long_setup_failure_stays_in_the_scroll_area(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein gescheiterter pip- oder git-Schritt meldet jede Ausgabezeile. Der
    Status stand außerhalb des Rollbereichs, das Fenster wuchs über den
    Bildschirm, und *Schließen* war nicht mehr erreichbar (RM-339)."""
    from app.core.backends import comfy_setup
    from app.ui.comfy_dialog import ComfySetupDialog

    monkeypatch.setattr(comfy_setup, "find_comfyui", lambda given=None: Path("nirgendwo"))
    dialog = ComfySetupDialog()
    try:
        dialog.show()
        _wait_for_comfy_probe(dialog, qt_app)
        _settle(qt_app)
        before = dialog.size()

        dialog._refused("Ein Paket ließ sich nicht installieren.\n" + "pip: Zeile\n" * 200)
        _settle(qt_app)

        assert dialog.width() == before.width(), "die Meldung verbreitert nichts"
        room = dialog.screen().availableGeometry()
        assert room.contains(dialog.frameGeometry()), "gewachsen wird nur bis zum Bildschirm"
        assert dialog.content_scroll.isAncestorOf(dialog.state), "der Status rollt mit"
        assert dialog.content_scroll.verticalScrollBar().maximum() > 0
        close = dialog.findChild(QDialogButtonBox)
        assert close is not None
        assert dialog.rect().contains(close.geometry()), "Schließen bleibt im Fenster"
        assert dialog.rect().contains(dialog.start_button.geometry())
    finally:
        dialog.release()
        dialog.deleteLater()
    qt_app.processEvents()


def _run_once(dialog: GenerateDialog, qt_app: QApplication) -> None:
    """Einen weiteren Wurf zu Ende laufen lassen, wie „Noch ein Versuch“ ihn startet."""
    dialog._start()
    worker = dialog._worker
    assert worker is not None
    assert worker.wait(60000), "the worker did not finish within a minute"
    qt_app.processEvents()


def _rows(dialog: GenerateDialog) -> list[str]:
    return [dialog.attempts.item(row).text() for row in range(dialog.attempts.count())]


def test_tries_from_different_sentences_say_which_sentence_and_seed(
    qt_app: QApplication, generator: ScriptedMeshBackend
) -> None:
    """Zwei Sätze, zwei Zeilen, die man auseinanderhält (RM-373).

    Die Zeile nannte nur Dreiecke, Volumen und dicht; zwei Würfe aus
    verschiedenen Sätzen sahen gleich aus. Jetzt nennt jede ihren Satzanfang
    und den Startwert, den der Schritt im Projekt speichert. Wer danach den
    Satz ändert, liest über *Übernehmen*, dass der gewählte alte Versuch kommt
    — und genau der kommt, mit seinem Startwert.
    """
    long_sentence = "eine kleine Figur mit Hut, Mantel und einem Regenschirm in der Hand"
    dialog = GenerateDialog(backend=generator)
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.prompt.setText(long_sentence)
        dialog.seed.setValue(12)
        _run_once(dialog, qt_app)
        dialog.prompt.setText("ein Becher")
        dialog.seed.setValue(40)
        _run_once(dialog, qt_app)

        first, second = _rows(dialog)
        assert first != second
        assert "„eine kleine Figur mit Hut" in first and "Startwert 12" in first, first
        assert "Regenschirm" not in first, "lange Sätze kommen gekürzt in die Zeile"
        assert dialog.attempts.item(0).toolTip() == long_sentence, "der ganze Satz im Tooltip"
        assert "„ein Becher“" in second and "Startwert 40" in second, second
        assert not dialog.taken.isVisibleTo(dialog), "der letzte Versuch passt zur Eingabe"

        dialog.attempts.setCurrentRow(0)
        assert dialog.taken.isVisibleTo(dialog), "Versuch 1 stammt aus einem anderen Satz"
        assert "Versuch 1" in dialog.taken.text()
        dialog.attempts.setCurrentRow(1)
        assert not dialog.taken.isVisibleTo(dialog)
        dialog.prompt.setText("ein Becher mit Henkel")
        assert dialog.taken.isVisibleTo(dialog), "der Satz ist seit dem Versuch geändert"
        assert "Versuch 2" in dialog.taken.text()

        dialog.attempts.setCurrentRow(0)
        dialog._accept_or_start()
        assert dialog.result() == GenerateDialog.DialogCode.Accepted
        assert dialog.result_mesh is dialog.tries[0], "übernommen wird der gewählte Versuch"
        assert dialog.result_mesh.seed == 12, "mit seinem Startwert, nicht dem im Feld"
    finally:
        dialog.wait_for_workers()
        dialog.deleteLater()
    qt_app.processEvents()


def test_tries_from_pictures_name_the_picture(
    qt_app: QApplication, generator: ScriptedMeshBackend, tmp_path: Path
) -> None:
    """Die Bildreihe: Jede Zeile nennt ihr Bild, und ein anderes Bild sagt es (RM-373)."""
    katze = tmp_path / "katze.png"
    katze.write_bytes(b"erstes Bild")
    hund = tmp_path / "hund.png"
    hund.write_bytes(b"zweites Bild")
    dialog = GenerateDialog(backend=generator)
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.set_image(katze)
        dialog.seed.setValue(3)
        wait_for_readiness(dialog, qt_app)
        _run_once(dialog, qt_app)
        dialog.set_image(hund)
        wait_for_readiness(dialog, qt_app)
        _run_once(dialog, qt_app)

        first, second = _rows(dialog)
        assert "katze.png" in first and "Startwert 3" in first, first
        assert "hund.png" in second, second
        assert not dialog.taken.isVisibleTo(dialog)

        dialog.attempts.setCurrentRow(0)
        assert dialog.taken.isVisibleTo(dialog), "Versuch 1 kam aus dem anderen Bild"
        assert "Bild" in dialog.taken.text()

        dialog.set_image(katze)
        assert not dialog.taken.isVisibleTo(dialog), "dasselbe Bild wieder gewählt"
        dialog.clear_image()
        dialog.prompt.setText("eine Katze")
        assert dialog.taken.isVisibleTo(dialog), "der Weg wechselte vom Bild zum Satz"
    finally:
        dialog.wait_for_workers()
        dialog.deleteLater()
    qt_app.processEvents()


def test_variants_of_one_sentence_differ_by_their_seed(
    qt_app: QApplication, generator: ScriptedMeshBackend
) -> None:
    """Die Variantenreihe: derselbe Satz, „Noch ein Versuch“ zählt den Startwert
    hoch, und die Zeilen unterscheiden sich daran (RM-373). Ein Wechsel
    zwischen ihnen ist kein geänderter Satz — die Zeile über *Übernehmen*
    bleibt weg."""
    dialog = GenerateDialog(backend=generator)
    try:
        wait_for_readiness(dialog, qt_app)
        dialog.prompt.setText("ein Becher")
        dialog.seed.setValue(7)
        _run_once(dialog, qt_app)
        for _ in range(2):
            dialog._try_again()
            assert dialog._worker is not None
            assert dialog._worker.wait(60000)
            qt_app.processEvents()

        rows = _rows(dialog)
        assert len(set(rows)) == 3, rows
        for row, seed in zip(rows, (7, 8, 9), strict=True):
            assert f"Startwert {seed}" in row and "„ein Becher“" in row, row
        for index in range(3):
            dialog.attempts.setCurrentRow(index)
            assert not dialog.taken.isVisibleTo(dialog), index
    finally:
        dialog.wait_for_workers()
        dialog.deleteLater()
    qt_app.processEvents()


# --- Übernehmen an einer Einfügemarke oder hinter der Lizenzsperre (RM-361) ---


def _two_steps(window: Any) -> None:
    """Zwei Quader — davor lässt sich eine Einfügemarke setzen."""
    from app.core.scene import OperationDraft

    session = window.session
    assert session.apply("Quader", [OperationDraft(op="create_box")])
    assert session.wait_for_idle()
    assert session.apply("Quader", [OperationDraft(op="create_box", params={"width": 30.0})])
    assert session.wait_for_idle()


def _insert_before_the_last(window: Any) -> None:
    """Die Einfügemarke vor den letzten Schritt — wie ein Klick auf *Einfügen*."""
    session = window.session
    assert session.start_inserting(session.history.operations[-1].id)
    assert session.wait_for_idle()


def _generated_sources(window: Any) -> list[str]:
    return [
        key
        for key, source in window.session.project.document.sources.items()
        if source.kind == "generated"
    ]


@pytest.mark.parametrize("answer", ["way", "cancel"])
@pytest.mark.parametrize("cause", ["insertion", "licence"])
def test_taking_a_generation_that_is_refused_keeps_the_mesh_and_names_the_way(
    qt_app: QApplication,
    window: Any,
    generator: ScriptedMeshBackend,
    monkeypatch: pytest.MonkeyPatch,
    cause: str,
    answer: str,
) -> None:
    """RM-361: *Übernehmen* bei gesetzter Einfügemarke oder Lizenzsperre.

    ``add_generated`` sagte ab, ``_generate`` fing es nicht, und die Absage
    landete bei ``sys.excepthook``: kein Satz, der Dialog zu, das minutenlang
    erzeugte Netz verloren. Jetzt steht die Absage als Vorschlag über dem
    Dialog, der Dialog bleibt mit seinen Versuchen offen, und an der
    Einfügemarke führt *Einfügen beenden und übernehmen* in einem Klick weiter.

    Marke und Sperre kommen hier **während** des Laufs: Vorher fragt schon der
    Start (der Test darunter), und die Absage beim Übernehmen ist der Fall,
    der danach noch bleibt — eine Marke über den Verlauf oder die Fernsteuerung,
    ein Testzeitraum, der während der Minuten abläuft.
    """
    import sys

    from app.core import activation
    from app.core.errors import STOP_INSERTING
    from app.ui import main_window as main_window_module
    from tests.ui_helpers import expire_trial

    # Im Arbeitsbereich, wie beim Kunden: Vom Startbildschirm aus beginnt
    # *Übernehmen* ein neues Projekt (RM-371).
    window._show_start_screen(False)
    if cause == "insertion":
        _two_steps(window)
    unlocked = activation._cached
    hooked: list[object] = []
    monkeypatch.setattr(sys, "excepthook", lambda *args: hooked.append(args))
    shown: list[tuple[str, dict[str, str], object]] = []
    spoken: list[str] = []

    def fake_show_error(error: Any, parent: Any = None, handlers: Any = None) -> None:
        from app.ui.dialogs import spoken_values

        shown.append((str(error.title), {a.id: str(a.label) for a in error.suggestions}, parent))
        spoken.extend(spoken_values(error))
        if answer == "way" and STOP_INSERTING.id in {a.id for a in error.suggestions}:
            handlers[STOP_INSERTING.id](error)

    monkeypatch.setattr(main_window_module, "show_error", fake_show_error)
    seen: dict[str, object] = {}

    class Scripted(GenerateDialog):
        def __init__(self, parent: Any = None, settings: Any = None) -> None:
            super().__init__(backend=generator, parent=parent, settings=settings)

    monkeypatch.setattr(main_window_module, "GenerateDialog", Scripted)
    # Der Dialog ist nichtmodal (RM-371): Der Menüweg kehrt zurück, und der
    # Test bedient den offenen Dialog wie der Kunde.
    window.action_generate()
    dialog = window._generator
    assert isinstance(dialog, Scripted)
    dialog.prompt.setText("eine Figur")
    finish(dialog, qt_app)
    if cause == "licence":
        expire_trial(monkeypatch)
    else:
        _insert_before_the_last(window)
    ok(dialog).click()
    seen["parent"] = dialog
    seen["accepted"] = dialog.result() == GenerateDialog.DialogCode.Accepted
    seen["tries"] = len(dialog.tries)
    seen["sources"] = _generated_sources(window)
    if not seen["accepted"]:
        # Der Weg danach: Marke ans Ende oder Schlüssel eingetragen,
        # und derselbe Versuch geht ohne neuen Lauf hinein.
        monkeypatch.setattr(activation, "_cached", unlocked)
        window.session.stop_inserting()
        assert window.session.wait_for_idle()
        ok(dialog).click()
        seen["later"] = dialog.result() == GenerateDialog.DialogCode.Accepted
    dialog.release()
    assert window.session.wait_for_idle()
    assert window._generator is None, "übernommen schließt den Dialog"

    assert not hooked, "eine Absage gehört in einen Satz, nicht an sys.excepthook"
    assert len(shown) == 1, shown
    title, labels, parent = shown[0]
    assert parent is seen["parent"], "die Absage steht über dem Dialog, der offen bleibt"
    if cause == "insertion":
        assert title == "Das geht nicht mitten im Verlauf."
        assert labels[STOP_INSERTING.id] == "Einfügen beenden und übernehmen"
    else:
        assert labels, "die Lizenzsperre nennt ihren Weg"
        assert not any("change" in line for line in spoken), (
            "RM-456: keine interne Handlungskennung in der Meldung",
            spoken,
        )
    if cause == "insertion" and answer == "way":
        assert seen["accepted"], "ein Klick: Marke ans Ende, Modell übernommen"
    else:
        assert not seen["accepted"], "die Absage schließt den Dialog nicht"
        assert seen["tries"] == 1, "das erzeugte Netz bleibt übernehmbar"
        assert seen["sources"] == [], "eine Absage schreibt nichts ins Projekt"
        assert seen["later"], "derselbe Versuch geht danach hinein"
    assert window.session.inserting is None
    assert len(_generated_sources(window)) == 1
    transaction = window.session.project.document.transactions[-1]
    assert str(transaction.title) == "Modell erzeugen"


@pytest.mark.parametrize("entry", ["menu", "chat"])
@pytest.mark.parametrize("cause", ["insertion", "licence"])
def test_generating_is_checked_before_the_dialog_opens(
    qt_app: QApplication,
    window: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cause: str,
    entry: str,
) -> None:
    """RM-361, vor dem Start — über das Menü und über das Chatfenster.

    *Modell erzeugen* blieb bei gesetzter Einfügemarke frei, und ein ins
    Chatfenster gezogenes Bild prüfte weder Marke noch Lizenz: Beide liefen
    nach Minuten in dieselbe Absage. Jetzt fragt das Fenster vorher, wie beim
    Import, und an der Einfügemarke öffnet *Einfügen beenden und Modell
    erzeugen* den Dialog — mit dem Bild, wenn eines abgelegt wurde."""
    from PySide6.QtGui import QImage

    from app.core.errors import STOP_INSERTING
    from app.ui import main_window as main_window_module
    from tests.ui_helpers import expire_trial

    picture = tmp_path / "skizze.png"
    image = QImage(16, 16, QImage.Format.Format_RGB32)
    image.fill(0x808080)
    assert image.save(str(picture))
    if cause == "insertion":
        _two_steps(window)
        _insert_before_the_last(window)
    else:
        expire_trial(monkeypatch)
    opened: list[bool] = []

    class Recorded(GenerateDialog):
        def __init__(self, parent: Any = None, settings: Any = None) -> None:
            super().__init__(backend=ScriptedMeshBackend(), parent=parent, settings=settings)

        def show(self) -> None:
            # Nichtmodal (RM-371): Das Fenster zeigt den Dialog mit ``show``.
            opened.append(self._image is not None)
            self.release()
            self.reject()

    shown: list[tuple[str, dict[str, str], int]] = []
    spoken: list[str] = []

    def fake_show_error(error: Any, parent: Any = None, handlers: Any = None) -> None:
        from app.ui.dialogs import spoken_values

        shown.append(
            (str(error.title), {a.id: str(a.label) for a in error.suggestions}, len(opened))
        )
        spoken.extend(spoken_values(error))
        if STOP_INSERTING.id in {a.id for a in error.suggestions}:
            handlers[STOP_INSERTING.id](error)

    monkeypatch.setattr(main_window_module, "GenerateDialog", Recorded)
    monkeypatch.setattr(main_window_module, "show_error", fake_show_error)
    if entry == "chat":
        window.chat.imageDropped.emit(str(picture))
    elif cause == "licence":
        # Am Menü steht die Sperre schon am Eintrag, mit Grund; der Weg an
        # ihm vorbei sagt trotzdem ab, statt den Dialog zu öffnen.
        window._update_actions()
        assert not window.generate_action.isEnabled()
        assert window.generate_action.toolTip()
        window.action_generate()
    else:
        window._update_actions()
        assert window.generate_action.isEnabled(), "die Marke sagt ihren Weg erst beim Klick"
        window.generate_action.trigger()

    assert len(shown) == 1, shown
    title, labels, dialogs_before = shown[0]
    assert dialogs_before == 0, "gefragt wird, bevor der Dialog aufgeht"
    if cause == "insertion":
        assert title == "Das geht nicht mitten im Verlauf."
        assert labels[STOP_INSERTING.id] == "Einfügen beenden und Modell erzeugen"
        assert opened == [entry == "chat"], "danach geht der Dialog auf, mit dem Bild"
        assert window.session.inserting is None
    else:
        assert labels, "die Lizenzsperre nennt ihren Weg"
        assert opened == [], "gesperrt öffnet kein Dialog, der erst nach Minuten absagt"
        assert not any("change" in line for line in spoken), (
            "RM-456: keine interne Handlungskennung in der Meldung",
            spoken,
        )


# --- Der Befund „Auf Maß gebracht“ trägt *Größe ändern* (RM-374) ---------------


def test_the_fitted_finding_of_a_generation_changes_its_size(
    qt_app: QApplication, window: Any, generator: ScriptedMeshBackend
) -> None:
    """RM-374, Abnahme am Fenster: Erzeugung → Befund mit *Größe ändern*; der
    Klick öffnet ``fit_to_size`` dieses Körpers mit dem aktuellen Maß, und
    150 mm dort machen den Körper 150 mm groß — ein normaler Parameter."""
    import time

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDoubleSpinBox

    session = window.session
    object_id = session.add_generated(generator.text_to_mesh("eine kleine Figur", seed=3))
    assert session.wait_for_idle()
    window.report.show_result(session.last_result, session.project.document)

    listing = window.report.list
    item = next(
        (
            listing.item(row)
            for row in range(listing.count())
            if listing.item(row).data(Qt.ItemDataRole.UserRole).code == "transform.fitted"
        ),
        None,
    )
    assert item is not None, "der Befund steht im Bericht"
    listing.setCurrentItem(item)
    qt_app.processEvents()
    button = next(
        (
            child
            for child in window.report._offers.findChildren(QPushButton)
            if child.text() == "Größe ändern"
        ),
        None,
    )
    assert button is not None, [b.text() for b in window.report._offers.findChildren(QPushButton)]
    button.click()
    qt_app.processEvents()

    dialog = window._op_dialog
    assert dialog is not None, "der Klick öffnet den Schritt"
    try:
        assert dialog.spec.name == "fit_to_size"
        spin = dialog._editors["largest"].findChild(QDoubleSpinBox)
        assert spin is not None
        assert spin.value() == pytest.approx(100.0), "mit dem aktuellen Maß"
        spin.setValue(150.0)
        assert session.wait_for_idle(30_000)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not (
            dialog._accept_button.isEnabled() and dialog.can_accept()
        ):
            qt_app.processEvents()
            time.sleep(0.01)
        assert dialog._accept_button.isEnabled(), "die Vorschau steht, Übernehmen frei"
        dialog.accept()
    finally:
        if window._op_dialog is dialog:
            dialog.reject()
    assert session.wait_for_idle()

    body = session.last_result.scene.objects[object_id]
    assert max(body.mesh.bounds.size) == pytest.approx(150.0, abs=1e-3)
    sizing = next(entry for entry in session.history.operations if entry.op == "fit_to_size")
    assert sizing.params["largest"] == pytest.approx(150.0)


# --- Interne Werte bleiben aus der Meldung (RM-456) ----------------------------


@pytest.mark.parametrize(
    "error_type",
    [
        "LicenceRequired",
        "DeviceActivationRequired",
        "DeviceDeactivationPending",
        "InstallationDamaged",
    ],
)
def test_an_activation_refusal_names_no_internal_action(error_type: str) -> None:
    """RM-456: Die Lizenzabsage beim Erzeugen zeigte „Handlung: change“.

    ``action`` ist eine Kennung fürs Protokoll (``change``, ``export``,
    ``slicer``, ``chat``); der Titel sagt schon, was fehlt. Ohne Fenster: Die
    Zeilen unter einer Meldung kommen aus ``spoken_values``.
    """
    from app.core import errors
    from app.ui.dialogs import spoken_values

    error = getattr(errors, error_type)(action="change")
    lines = spoken_values(error)
    assert not any("change" in line or "Handlung" in line for line in lines), lines


# --- Die Oberfläche bleibt während der Erzeugung bedienbar (RM-371) -----------


def test_generating_never_holds_the_window_in_a_modal_loop() -> None:
    """RM-371, ohne Fenster: Der Erzeugen-Weg öffnet seinen Dialog nichtmodal.

    ``dialog.exec()`` hielt die Anwendung an, solange der Generator rechnete —
    vierzig Sekunden bis Minuten. Gelesen wird der Quelltext von
    ``MainWindow._generate`` und dem Dialog: kein ``exec``, kein ``setModal``.
    """
    import ast
    import inspect
    import textwrap

    from app.ui import generate_dialog
    from app.ui.main_window import MainWindow

    def calls(tree: ast.AST) -> set[str]:
        return {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }

    def source_of(function: Any) -> ast.AST:
        return ast.parse(textwrap.dedent(inspect.getsource(function)))

    assert "exec" not in calls(source_of(MainWindow._generate)), "nichtmodal geöffnet"
    assert "show" in calls(source_of(MainWindow._show_generator))
    dialog_calls = calls(ast.parse(inspect.getsource(generate_dialog)))
    assert not {"exec", "setModal", "setWindowModality"} & dialog_calls


class _GatedBackend(ScriptedMeshBackend):
    """Ein langsamer Generator: meldet Fortschritt und liefert erst, wenn der Test es sagt.

    Er fragt den Abbruch regelmäßig wie ComfyUI. Die Frist ist eine Reißleine,
    keine Wartezeit: Gibt niemand frei, endet der Wurf mit einem Fehler statt
    mit einem hängenden Lauf.
    """

    def __init__(self) -> None:
        super().__init__(fallback=(MESHES / "cube_clean.stl").read_bytes())
        self.gate = threading.Event()
        self.started = threading.Event()
        self.ignore_cancel = False
        """Wie ein ComfyUI, das nach dem Abbruch weiterrechnet."""

    def _hold(self, kwargs: dict[str, Any]) -> None:
        progress = kwargs.get("progress")
        cancelled = kwargs.get("cancelled")
        self.started.set()
        if callable(progress):
            progress(0.25, "Modell wird erzeugt (1 s)")
        deadline = time.monotonic() + 30.0
        while not self.gate.wait(0.01):
            if callable(cancelled) and cancelled() and not self.ignore_cancel:
                raise OperationCancelled
            if time.monotonic() > deadline:
                raise AssertionError("niemand hat den Generator freigegeben")

    def text_to_mesh(self, prompt: str, **kwargs: Any) -> GeneratedMesh:  # type: ignore[override]
        self._hold(kwargs)
        return super().text_to_mesh(prompt, **kwargs)

    def image_to_mesh(self, image: bytes, **kwargs: Any) -> GeneratedMesh:  # type: ignore[override]
        self._hold(kwargs)
        return super().image_to_mesh(image, **kwargs)


def _run_in_window(
    window: Any,
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    backend: _GatedBackend,
    image: Path | None = None,
) -> GenerateDialog:
    """Über das Menü (oder ein abgelegtes Bild) öffnen und *Erzeugen* klicken."""
    from app.ui import main_window as main_window_module

    class Gated(GenerateDialog):
        def __init__(self, parent: Any = None, settings: Any = None) -> None:
            super().__init__(backend=backend, parent=parent, settings=settings)

    monkeypatch.setattr(main_window_module, "GenerateDialog", Gated)
    window._show_start_screen(False)
    if image is None:
        window.generate_action.trigger()
    else:
        window.chat.imageDropped.emit(str(image))
    dialog = window._generator
    assert isinstance(dialog, Gated), "der Menüweg kehrt mit offenem Dialog zurück"
    # Ein abgelegtes Bild fragt den Bildweg neu; gewartet wird auf die Antwort
    # für den Weg, der gilt, nicht auf die erste.
    deadline = time.monotonic() + 10.0
    while dialog.readiness is None and time.monotonic() < deadline:
        wait_for_readiness(dialog, qt_app)
        time.sleep(0.01)
    assert dialog.readiness is not None
    if image is None:
        dialog.prompt.setText("eine kleine Figur")
    ok(dialog).click()
    assert backend.started.wait(10.0), "der Wurf läuft"
    for _ in range(3):
        qt_app.processEvents()
    return dialog


def _wait_for_run(dialog: GenerateDialog, qt_app: QApplication) -> None:
    worker = dialog._worker
    if worker is not None:
        assert worker.wait(30_000), "der Wurf endet"
    for _ in range(3):
        qt_app.processEvents()


def _picture(tmp_path: Path) -> Path:
    from PySide6.QtGui import QImage

    picture = tmp_path / "skizze.png"
    image = QImage(16, 16, QImage.Format.Format_RGB32)
    image.fill(0x808080)
    assert image.save(str(picture))
    return picture


@pytest.mark.parametrize("way", ["text", "image"])
def test_the_window_stays_usable_while_a_model_is_generated(
    qt_app: QApplication,
    window: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    way: str,
) -> None:
    """RM-371, Abnahme Text und Bild: Während der Generator rechnet, ist kein
    Fenster modal, ein Menüeintrag wirkt, die Statusleiste zeigt Fortschritt,
    verstrichene Zeit und *Abbrechen*. Danach kommt der Dialog mit dem
    Versuch wieder, *Übernehmen* legt ihn als einen Schritt ab, dessen Gruppe
    offen steht (RM-456), und Strg+Z nimmt ihn als Ganzes zurück."""
    backend = _GatedBackend()
    picture = _picture(tmp_path) if way == "image" else None
    dialog = _run_in_window(window, qt_app, monkeypatch, backend, picture)
    try:
        assert QApplication.activeModalWidget() is None, "kein Fenster hält die Anwendung an"
        assert dialog.isHidden(), "der Dialog tritt zur Seite"
        assert not window.progress.isHidden(), "der Balken steht in der Statusleiste"
        assert not window.cancel_button.isHidden()
        assert window.cancel_button.isEnabled()
        deadline = time.monotonic() + 5.0
        while "Verstrichen" not in window.status_message.text() and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.02)
        status = window.status_message.text()
        assert "Verstrichen" in status, status
        assert "Modell wird erzeugt" in status, status

        bed = window.settings.bed_visible
        window._bed_action.trigger()
        assert window.settings.bed_visible is not bed, "ein Menüeintrag wirkt während des Laufs"
        window._bed_action.trigger()

        window.generate_action.trigger()
        assert window._generator is dialog, "ein zweiter Aufruf holt denselben Dialog"
        assert not dialog.isHidden()
        running = dialog._worker
        assert running is not None and running.isRunning(), "und startet keinen zweiten Wurf"
        dialog.hide()

        backend.gate.set()
        _wait_for_run(dialog, qt_app)
        assert not dialog.isHidden(), "mit dem Ergebnis kommt der Dialog wieder"
        assert window.progress.isHidden()
        assert window.cancel_button.isHidden()
        assert len(dialog.tries) == 1
        assert ok(dialog).text() == "Übernehmen"
        assert dialog.destination.isHidden(), "dasselbe Projekt braucht keinen Hinweis"

        before = len(window.session.project.document.transactions)
        ok(dialog).click()
        assert window.session.wait_for_idle()
        qt_app.processEvents()
        assert window._generator is None, "übernommen schließt den Dialog"
        assert window.status_message.text() == (
            "Das erzeugte Modell liegt im Projekt. Strg+Z nimmt es zurück."
        ), "die Ansage „fertig — Übernehmen“ bleibt nicht über dem übernommenen Modell stehen"
        document = window.session.project.document
        assert len(document.transactions) == before + 1, "eine Erzeugung ist ein Schritt"
        assert len(document.transactions[-1].ops) > 1
        listing = window.history_panel.list
        children = [
            listing.item(row)
            for row in range(listing.count())
            if listing.item(row).text().startswith("    ")
        ]
        assert children, "die Erzeugung steht als Gruppe im Verlauf"
        assert not any(row.isHidden() for row in children), (
            "RM-456: die Schritte der neuen Erzeugung stehen offen da"
        )

        window.undo_action.trigger()
        assert window.session.wait_for_idle()
        assert len(window.session.project.document.transactions) == before
    finally:
        backend.gate.set()
        if window._generator is not None:
            window._generator.release()


@pytest.mark.parametrize("finished_before", [False, True])
def test_cancel_in_the_status_bar_stops_the_generation(
    qt_app: QApplication,
    window: Any,
    monkeypatch: pytest.MonkeyPatch,
    finished_before: bool,
) -> None:
    """RM-371, Abnahme Abbruch: *Abbrechen* in der Statusleiste hält den Wurf an.

    Ohne fertigen Versuch geht der Dialog zu und die Statuszeile sagt es; mit
    einem kommt er mit diesem wieder, und der lässt sich übernehmen."""
    backend = _GatedBackend()
    dialog = _run_in_window(window, qt_app, monkeypatch, backend)
    closed: list[int] = []
    dialog.finished.connect(closed.append)
    try:
        if finished_before:
            backend.gate.set()
            _wait_for_run(dialog, qt_app)
            backend.gate.clear()
            backend.started.clear()
            dialog.again.click()
            assert backend.started.wait(10.0)
            qt_app.processEvents()
            assert dialog.isHidden()
        worker = dialog._worker
        assert worker is not None
        window.cancel_button.click()
        assert worker.cancelled(), "der Knopf erreicht den Arbeiter"
        assert not window.cancel_button.isEnabled(), "kein zweites Abbrechen im Auslaufen"
        _wait_for_run(dialog, qt_app)
        assert window.progress.isHidden()
        assert window.cancel_button.isHidden()
        if finished_before:
            assert not closed, "die fertigen Versuche bleiben"
            assert not dialog.isHidden()
            assert len(dialog.tries) == 1
            assert ok(dialog).isEnabled()
            ok(dialog).click()
            assert window.session.wait_for_idle()
            assert len(_generated_sources(window)) == 1
        else:
            assert closed, "ohne Versuch gibt es nichts zu zeigen"
            assert window._generator is None
            assert window.status_message.text() == "Die Erzeugung wurde abgebrochen."
            assert _generated_sources(window) == []
    finally:
        backend.gate.set()
        if window._generator is not None:
            window._generator.release()


@pytest.mark.parametrize("answer", ["back", "close"])
@pytest.mark.parametrize("state", ["running", "finished"])
def test_closing_the_window_names_what_a_generation_would_lose(
    qt_app: QApplication,
    window: Any,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    answer: str,
) -> None:
    """RM-499: Das Fenster schloss während einer Erzeugung ohne Frage.

    Seit der Dialog nichtmodal ist (RM-371), brach Schließen den Lauf ab, und
    fertige, nicht übernommene Versuche gingen wortlos verloren — kein Strg+Z
    holt sie zurück. Jetzt fragt das Fenster; *Zur Erzeugung* holt den Dialog
    nach vorn und lässt das Fenster offen, *Trotzdem schließen* schließt.
    """
    from app.ui import main_window as main_window_module

    backend = _GatedBackend()
    dialog = _run_in_window(window, qt_app, monkeypatch, backend)
    asked: list[tuple[bool, int]] = []

    def confirm(running: bool, tries: int, _parent: Any = None) -> str:
        asked.append((running, tries))
        return answer

    monkeypatch.setattr(main_window_module, "confirm_generation_loss", confirm)
    try:
        if state == "finished":
            backend.gate.set()
            _wait_for_run(dialog, qt_app)
        window.close()
        qt_app.processEvents()
        expected = (True, 0) if state == "running" else (False, 1)
        assert asked == [expected], asked
        if answer == "back":
            assert not getattr(window, "_close_requested", False), "das Fenster bleibt offen"
            assert window._generator is dialog
            assert not dialog.isHidden(), "Zur Erzeugung holt den Dialog nach vorn"
        else:
            assert getattr(window, "_close_requested", False), "Trotzdem schließen schließt"
    finally:
        backend.gate.set()
        if window._generator is not None:
            window._generator.release()


def test_closing_without_a_generation_asks_nothing_about_it(
    window: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-499: Ohne Erzeugung bleibt das Schließen, wie es war."""
    from app.ui import main_window as main_window_module

    asked: list[object] = []
    monkeypatch.setattr(
        main_window_module, "confirm_generation_loss", lambda *args: asked.append(args) or "back"
    )
    assert window._may_lose_the_generation()
    assert not asked


def test_a_project_opened_during_the_run_is_named_before_taking(
    qt_app: QApplication, window: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-371: Während des Laufs bleibt das Fenster bedienbar, auch für ein
    anderes Projekt. *Übernehmen* legt das Modell dorthin, wo der Kunde jetzt
    ist — und der Dialog sagt das vorher."""
    backend = _GatedBackend()
    dialog = _run_in_window(window, qt_app, monkeypatch, backend)
    try:
        window.open_path(Path(__file__).parent / "data" / "projects" / "drilled_v6.p3d")
        assert window.session.wait_for_idle(60_000)
        bodies = len(window.session.last_result.scene.objects)
        backend.gate.set()
        _wait_for_run(dialog, qt_app)
        assert not dialog.destination.isHidden(), "der Wechsel steht über Übernehmen"
        assert "anderes Projekt" in dialog.destination.text()
        assert "drilled_v6" in dialog.destination.text()
        ok(dialog).click()
        assert window.session.wait_for_idle()
        assert window._generator is None
        assert len(_generated_sources(window)) == 1, "im jetzt offenen Projekt"
        assert len(window.session.last_result.scene.objects) == bodies + 1
    finally:
        backend.gate.set()
        if window._generator is not None:
            window._generator.release()


def test_a_hanging_cancel_lets_the_dialog_step_aside_and_keeps_the_tries(
    qt_app: QApplication, window: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-371 mit RM-418: Hängt der Generator nach *Abbrechen* eines weiteren
    Versuchs, ist *Abbrechen* gesperrt und verwirft nichts — aber Esc und das
    Fensterkreuz halten den Kunden nicht im Dialog fest. Er tritt zur Seite,
    die Statusleiste nennt das Auslaufen, und das Ende holt ihn mit allen
    Versuchen zurück."""
    backend = _GatedBackend()
    dialog = _run_in_window(window, qt_app, monkeypatch, backend)
    closed: list[int] = []
    dialog.finished.connect(closed.append)
    cancel = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
    try:
        backend.gate.set()
        _wait_for_run(dialog, qt_app)
        backend.gate.clear()
        backend.started.clear()
        backend.ignore_cancel = True
        dialog.again.click()
        assert backend.started.wait(10.0)
        qt_app.processEvents()
        window.generate_action.trigger()
        assert not dialog.isHidden(), "der Menüweg holt den laufenden Dialog nach vorn"

        cancel.click()
        worker = dialog._worker
        assert worker is not None and worker.cancelled()
        assert not cancel.isEnabled(), "RM-418: das zweite Abbrechen verwirft nichts"
        assert cancel.toolTip(), "und sagt, warum"
        assert not window.cancel_button.isEnabled(), "die Statusleiste weiß es auch"
        assert "Wird abgebrochen" in window.status_message.text()

        dialog.reject()  # Esc oder das Fensterkreuz
        qt_app.processEvents()
        assert dialog.isHidden(), "der Dialog tritt zur Seite"
        assert not closed, "und verwirft nichts"
        assert len(dialog.tries) == 1
        assert not window.progress.isHidden(), "der Lauf steht weiter in der Statusleiste"
        assert QApplication.activeModalWidget() is None

        backend.gate.set()
        _wait_for_run(dialog, qt_app)
        assert not dialog.isHidden(), "das Ende holt ihn zurück"
        assert len(dialog.tries) == 1, "der fertige Versuch bleibt übernehmbar"
        assert ok(dialog).isEnabled()
        assert cancel.isEnabled()
        assert window.progress.isHidden()
    finally:
        backend.gate.set()
        if window._generator is not None:
            window._generator.release()
