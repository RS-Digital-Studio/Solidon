"""Der Variantendialog (Bauplan §28.3, §2.8).

Zwölf vollständige Auswertungen desselben Stapels sind über zwei Sekunden, und
über zwei Sekunden verlangt §2.8 einen Fortschritt mit Abbrechen und eine
Oberfläche, die bedienbar bleibt. Gerechnet wurde vorher in der
Ereignisschleife: das Fenster stand, bis der letzte Lauf durch war, und ein
Zeichen dafür, dass überhaupt etwas läuft, gab es nicht.

**Geprüft wird über die echten Wege**, nicht an ihnen vorbei. Die erste Version
dieser Datei rief ``_stop_or_close`` von Hand und baute den Arbeiter selbst —
damit blieb sie grün, als die Verbindung des Knopfes und das ``start()`` des
Dialogs versuchsweise zurückgedreht wurden. Ein Test, der den Weg nicht geht,
prüft ihn nicht.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialogButtonBox

from app.core.scene import History, OperationDraft
from app.core.types import Parameter
from app.ui.session import Session
from app.ui.variants_dialog import VariantsDialog


def session_with_parameter() -> Session:
    """Eine Sitzung mit einem Projektparameter und einem Schritt darauf.

    Der Schritt liest den Parameter — sonst wäre jede Variante dieselbe, und der
    Test prüfte eine Rechnung, die nichts zu rechnen hat.
    """
    session = Session()
    document = session.project.document
    document.parameters["spiel"] = Parameter(name="spiel", value=0.2, unit="mm")
    History(document).apply(
        "Zapfen",
        [OperationDraft(op="create_cylinder", params={"diameter": "=@spiel*10", "height": 8.0})],
    )
    return session


def _empty_set(parameter: str) -> Any:
    """Ein Variantensatz ohne Varianten — für einen Lauf, der abgebrochen wird."""
    from app.core.scene.variants import VariantSet

    return VariantSet(parameter=parameter)


def test_the_dialog_computes_off_the_interface_thread(
    qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Rechnung lief in der Ereignisschleife.

    Bis zu zwölf Auswertungen hintereinander, mit stehendem Fenster. Gegangen
    wird hier der Weg des Knopfes: ``_build`` fragt den Ordner, startet den
    Arbeiter, und der rechnet — belegt wird der Thread, in dem das geschieht.
    Anders herum wäre jede weitere Zusage aus §2.8 nur Fassade.

    Und der Ordner wird **vorher** gefragt: er wurde danach gefragt, also war
    jede abgebrochene Ordnerwahl bis zu zwölf weggeworfene Auswertungen.
    """
    from app.ui import variants_dialog as module

    session = session_with_parameter()
    dialog = VariantsDialog(session)
    try:
        asked: list[bool] = []

        def choose(*_args: Any, **_kwargs: Any) -> str:
            asked.append(True)
            return str(tmp_path)

        monkeypatch.setattr(module.QFileDialog, "getExistingDirectory", staticmethod(choose))

        threads: list[int] = []
        real = module.build_variants

        def watching(*args: Any, **kwargs: Any) -> Any:
            threads.append(threading.get_ident())
            return real(*args, **kwargs)

        monkeypatch.setattr(module, "build_variants", watching)

        dialog.count.setValue(2)
        dialog._build()
        assert asked == [True], "der Ordner wird gefragt, bevor gerechnet wird"
        worker = dialog._worker
        assert worker is not None, "es wurde kein Arbeiter gestartet"
        assert worker.wait(30_000), "der Arbeiter wurde nicht fertig"
        QApplication.processEvents()

        assert threads, "gerechnet wurde nicht"
        assert threading.get_ident() not in threads, "gerechnet wurde im Oberflächen-Thread"
    finally:
        dialog.deleteLater()


def test_cancelling_stops_the_run_instead_of_closing_the_dialog(
    qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Knopf, zwei Bedeutungen — und die richtige gilt.

    Der Abbrechen-Knopf schloss den Dialog. Während einer laufenden Rechnung
    wäre das eine Sackgasse: der Dialog ginge zu, und der Thread rechnete
    weiter. Läuft nichts, schließt er weiterhin.

    Gedrückt wird der Knopf und nicht die Methode gerufen — die Verbindung ist
    Teil der Aussage. Genau daran ist die erste Version dieses Tests
    vorbeigelaufen.
    """
    from app.ui import variants_dialog as module

    session = session_with_parameter()
    dialog = VariantsDialog(session)
    try:
        cancel = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        assert cancel is not None
        closed: list[bool] = []
        dialog.rejected.connect(lambda: closed.append(True))

        cancel.click()
        assert closed == [True], "ohne Rechnung muss der Knopf schließen"

        # Jetzt mit laufender Rechnung. Der Arbeiter wartet auf ein Ereignis,
        # damit der Test nicht um Millisekunden rennt.
        held = threading.Event()
        monkeypatch.setattr(
            module.QFileDialog,
            "getExistingDirectory",
            staticmethod(lambda *_args, **_kwargs: str(tmp_path)),
        )
        monkeypatch.setattr(
            module,
            "build_variants",
            lambda *_args, **kwargs: (held.wait(30), _empty_set(kwargs["parameter"]))[1],
        )

        closed.clear()
        dialog._build()
        assert dialog._worker is not None, "es wurde kein Arbeiter gestartet"

        cancel.click()
        assert dialog._cancel.is_cancelled, "der Abbruch wurde nicht verlangt"
        assert closed == [], "der Dialog ging zu, während gerechnet wurde"
        assert dialog.state.text(), "und sagt nicht, dass abgebrochen wird"

        held.set()
        worker = dialog._worker
        if worker is not None:
            worker.wait(30_000)
        QApplication.processEvents()
    finally:
        dialog.deleteLater()


def test_the_progress_bar_appears_only_while_something_runs(
    qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Balken, der von Anfang an auf null steht, sagt nichts.

    Und „Erzeugen" ist gesperrt, solange gerechnet wird: ein zweiter Druck
    startete einen zweiten Lauf auf denselben Ordner.
    """
    from app.ui import variants_dialog as module

    session = session_with_parameter()
    dialog = VariantsDialog(session)
    try:
        assert not dialog.progress.isVisibleTo(dialog), "vor dem Start gibt es nichts zu zeigen"

        held = threading.Event()
        monkeypatch.setattr(
            module.QFileDialog,
            "getExistingDirectory",
            staticmethod(lambda *_args, **_kwargs: str(tmp_path)),
        )
        monkeypatch.setattr(
            module,
            "build_variants",
            lambda *_args, **kwargs: (held.wait(30), _empty_set(kwargs["parameter"]))[1],
        )

        dialog._build()
        assert dialog.progress.isVisibleTo(dialog), "während der Rechnung fehlt der Balken"
        ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok is not None and not ok.isEnabled(), (
            "ein zweiter Druck auf „Erzeugen“ würde einen zweiten Lauf starten"
        )

        held.set()
        worker = dialog._worker
        assert worker is not None
        assert worker.wait(30_000)
        QApplication.processEvents()
        assert not dialog.progress.isVisibleTo(dialog), "und danach steht er noch da"
        assert ok.isEnabled(), "danach muss „Erzeugen“ wieder gehen"
    finally:
        dialog.deleteLater()


def test_the_progress_reaches_the_widgets_on_the_interface_thread(
    qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gesamtreview 05.09.2026, UI-14: Der Dialog reichte seine gebundene
    Widgetmethode als ``progress`` in den Arbeiter, und ``build_variants``
    rief sie synchron aus dem Arbeits-Thread — ``QProgressBar`` und
    ``QLabel`` wurden aus einem fremden Thread gesetzt, während der Kommentar
    daneben ein Signal behauptete, das es nicht gab. Gemessen an den
    Thread-Kennungen: jeder Aufruf von ``_advance`` gehört dem
    Oberflächen-Thread."""
    from app.ui import variants_dialog as module

    seen: list[int] = []
    real_advance = VariantsDialog._advance

    def watching(self: VariantsDialog, share: float, text: str) -> None:
        seen.append(threading.get_ident())
        real_advance(self, share, text)

    monkeypatch.setattr(VariantsDialog, "_advance", watching)
    monkeypatch.setattr(
        module.QFileDialog, "getExistingDirectory", staticmethod(lambda *_a, **_k: str(tmp_path))
    )
    session = session_with_parameter()
    dialog = VariantsDialog(session)
    try:
        dialog.count.setValue(2)
        dialog._build()
        worker = dialog._worker
        assert worker is not None
        assert worker.wait(30_000), "der Arbeiter wurde nicht fertig"
        QApplication.processEvents()

        assert seen, "der Fortschritt kam nie an"
        assert set(seen) == {threading.get_ident()}, "ein Widget aus einem fremden Thread"
    finally:
        dialog.deleteLater()
