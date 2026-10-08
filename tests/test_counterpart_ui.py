"""Der Weg zu den Gegenstücken im Fenster (RM-147 E1, §18.5, §2.6).

Der Kern kann das Paar (``tests/test_counterpart.py``); hier steht, ob ein
Kunde dorthin kommt: Der Menüeintrag ist gesperrt, solange die Auswahl ihn
nicht trägt, und er sagt warum — und mit zwei markierten Stellen an zwei Teilen
entstehen beide Hälften und ihre Passung in einem Schritt.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.core.scene.history import OperationDraft
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings

THREADS = Path(__file__).parent / "data" / "threads"


def _two_plates(window: MainWindow) -> tuple[str, str]:
    """Zwei Platten nebeneinander, gerechnet — die Ausgangslage."""
    window.session.start_new("centauri-carbon-2", "petg")
    window.session.history.apply(
        "Zwei Platten",
        [
            OperationDraft(op="create_box", params={"width": 40.0, "depth": 30.0, "height": 10.0}),
            OperationDraft(
                op="create_box",
                params={"width": 40.0, "depth": 30.0, "height": 10.0, "x": 60.0},
            ),
        ],
    )
    window.session.evaluate_now()
    result = window.session.last_result
    assert result is not None
    return tuple(result.scene.objects)[:2]  # type: ignore[return-value]


def _top_face(window: MainWindow, object_id: str) -> str:
    """Die Kennung der Oberseite — die Stelle, an die ein Gegenstück kommt."""
    result = window.session.last_result
    assert result is not None
    entry = result.scene.objects[object_id]
    for name, feature in entry.features.items():
        if feature.kind == "face" and name.startswith("face_top"):
            return name
    raise AssertionError(f"{object_id} hat keine Oberseite — dann prüft der Test nichts")


def test_the_entry_stays_locked_until_two_places_are_marked(qt_app: QApplication) -> None:
    """Ein Menü, das die Frage selbst beantworten kann, beantwortet sie (§2.6).

    Ohne Auswahl, mit einer Stelle und mit zwei Stellen **an demselben** Teil
    ist ein Gegenstück nicht möglich — und jedes Mal aus demselben Grund, den
    der Eintrag nennt, statt ihn nach dem Klick als Dialog zu zeigen.

    Und wenn die Auswahl steht, kommt der **eigene** Satz zurück: Der erste
    Anlauf leerte den Hinweistext und nahm dem Eintrag damit die Erklärung,
    die ``_add_action`` ihm mitgegeben hat — bedienbar und stumm.
    """
    window = MainWindow(Session(), UiSettings())
    try:
        first, second = _two_plates(window)
        eintrag = window.counterpart_action

        window._update_actions()
        assert not eintrag.isEnabled(), "ohne Auswahl gibt es kein Paar"
        assert "Stelle" in eintrag.toolTip(), f"ohne Grund: {eintrag.toolTip()!r}"
        assert eintrag.statusTip() == eintrag.toolTip(), "der Grund steht an beiden Stellen"

        window.object_tree.select_feature(first, _top_face(window, first))
        window._update_actions()
        assert not eintrag.isEnabled(), "eine Stelle ist eine Hälfte"

        window.object_tree.select_features(
            ((first, _top_face(window, first)), (second, _top_face(window, second)))
        )
        QApplication.processEvents()
        window._update_actions()
        assert eintrag.isEnabled(), "zwei Stellen an zwei Teilen tragen ein Gegenstück"
        hinweis = eintrag.toolTip()
        assert "Markieren Sie" not in hinweis, f"der Grund bleibt am freien Eintrag: {hinweis!r}"
        assert "Beide Hälften" in hinweis, f"der eigene Satz kommt nicht zurück: {hinweis!r}"
        assert eintrag.statusTip() == hinweis, "und er steht wieder an beiden Stellen"
    finally:
        release = getattr(type(window), "release", None)
        if release is not None:
            release(window)
        window.deleteLater()


@pytest.mark.parametrize("unit", ["mm", "in"])
def test_both_halves_and_their_fit_come_from_one_click(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, unit: str
) -> None:
    """Der ganze Weg: zwei Stellen, ein Dialog, ein Schritt, eine Passung.

    **Der echte Dialog, nur ohne Klick auf „Übernehmen".** Eine Attrappe an
    seiner Stelle hätte hier zwei Dinge nicht geprüft, die zwischen Fenster und
    Kern liegen: dass seine Maße überhaupt zu den Bausteinschritten passen, und
    dass die Vorschau daran hängt. Gemessen wird, dass daraus **ein**
    Verlaufsschritt und eine Passung werden, deren Merkmale es wirklich gibt.
    """
    from app.ui import counterpart_dialog as module

    window = MainWindow(Session(), UiSettings(display_unit=unit))
    try:
        first, second = _two_plates(window)
        window.object_tree.select_features(
            ((first, _top_face(window, first)), (second, _top_face(window, second)))
        )
        QApplication.processEvents()

        monkeypatch.setattr(
            module.CounterpartDialog,
            "exec",
            lambda self: int(module.CounterpartDialog.DialogCode.Accepted),
        )
        document = window.session.project.document
        before = len(document.transactions)

        window.action_counterpart()

        assert len(document.transactions) == before + 1, "beide Hälften sind eine Handlung"
        assert [step.params["kind"] for step in document.ops[-2:]] == ["pin", "bore"]
        for step in document.ops[-2:]:
            assert step.params["diameter"] == pytest.approx(4.0)
            assert step.params["length"] == pytest.approx(8.0)
        assert document.ops[-2].params["at_feature"] == _top_face(window, first)
        # Die Passung braucht die Kennungen der erzeugten Merkmale, und die
        # kennt erst die Auswertung — sie läuft im Arbeiter, nicht im Klick.
        assert window.session.wait_for_idle(30_000)
        assert len(document.fits) == 1, "und ihre Passung gehört dazu"

        result = window.session.last_result
        assert result is not None
        passung = document.fits[0]
        assert passung.a.feature_id in result.scene.objects[passung.a.object_id].features
        assert passung.b.feature_id in result.scene.objects[passung.b.object_id].features
    finally:
        release = getattr(type(window), "release", None)
        if release is not None:
            release(window)
        window.deleteLater()


def test_a_counterpart_pair_marks_the_saved_project_for_recovery(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ein angenommenes Paar gehört in Speichernachfrage und automatische Sicherung."""
    from app.core.scene.project import autosave_path, load
    from app.ui import counterpart_dialog as module

    window = MainWindow(Session(), UiSettings())
    try:
        first, second = _two_plates(window)
        path = window.session.save_project(tmp_path / "counterparts.p3d")
        assert not window.session.modified
        window.object_tree.select_features(
            ((first, _top_face(window, first)), (second, _top_face(window, second)))
        )
        QApplication.processEvents()
        monkeypatch.setattr(
            module.CounterpartDialog,
            "exec",
            lambda self: int(module.CounterpartDialog.DialogCode.Accepted),
        )
        before = len(window.session.project.document.ops)

        window.action_counterpart()
        assert window.session.wait_for_idle(30_000)

        assert len(window.session.project.document.ops) == before + 2
        assert window.session.modified, "das Paar muss eine Speichernachfrage auslösen"
        window.session.autosave()
        saved = load(autosave_path(path))
        assert len(saved.document.ops) == before + 2
        assert len(saved.document.fits) == 1, "die Sicherung enthält auch die Passung"
        assert len(load(path).document.ops) == before, "die gespeicherte Datei blieb unverändert"
        window.session.undo()
        assert window.session.wait_for_idle(30_000)
        assert len(window.session.project.document.ops) == before
        assert not window.session.project.document.fits, "ein Undo nimmt das ganze Paar zurück"
    finally:
        window.release()
        window.deleteLater()


def test_the_preview_shows_both_halves_before_anything_is_built(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Was entstünde, steht im Bild, bevor etwas entsteht (§18.7).

    Bei einem Paar ist das die Lage, in der eine Vorschau am meisten wert ist:
    Ob Stift und Bohrung zueinander passen, sieht man den beiden an und den
    Zahlen nicht. Geprüft wird deshalb beides — dass **beide** Hälften an ihren
    markierten Stellen angefordert werden, und dass ein abgebrochener Dialog
    nichts hinterlässt.
    """
    from app.ui import counterpart_dialog as module

    window = MainWindow(Session(), UiSettings())
    try:
        first, second = _two_plates(window)
        window.object_tree.select_features(
            ((first, _top_face(window, first)), (second, _top_face(window, second)))
        )
        QApplication.processEvents()

        angefordert: list[list[OperationDraft]] = []
        monkeypatch.setattr(
            window.session,
            "preview_async",
            lambda then, drafts=None, **rest: angefordert.append(list(drafts or [])),
        )
        monkeypatch.setattr(
            module.CounterpartDialog,
            "exec",
            lambda self: int(module.CounterpartDialog.DialogCode.Rejected),
        )
        document = window.session.project.document
        before = len(document.transactions)

        window.action_counterpart()

        assert angefordert, "ohne Anforderung zeigt das Fenster gar nichts"
        entwuerfe = angefordert[-1]
        assert [entry.op for entry in entwuerfe] == ["insert_dowel", "insert_dowel"]
        assert [entry.params["kind"] for entry in entwuerfe] == ["pin", "bore"]
        assert entwuerfe[0].params["at_feature"] == _top_face(window, first)
        assert entwuerfe[1].params["at_feature"] == _top_face(window, second)
        assert entwuerfe[0].params["diameter"] == entwuerfe[1].params["diameter"], (
            "die Vorschau zeigt dasselbe Maß, das der Schritt bekäme"
        )
        assert len(document.transactions) == before, "ein Abbruch hinterlässt nichts"
    finally:
        release = getattr(type(window), "release", None)
        if release is not None:
            release(window)
        window.deleteLater()


@pytest.mark.parametrize("unit", ["mm", "in"])
def test_the_dialog_shows_the_shared_measurements_of_the_chosen_pair(
    qt_app: QApplication,
    unit: str,
) -> None:
    """Die Maße kommen aus dem Bausteinschema, nicht aus einer zweiten Liste.

    Und ein Paarwechsel tauscht sie vollständig: Der Passstift hat Durchmesser
    und Länge, Schraube und Mutter haben eine Größe. Was stehenbliebe,
    verspräche eine Wirkung, die die andere Hälfte nicht kennt.
    """
    from app.core.bootstrap import load_operations
    from app.ui.counterpart_dialog import CounterpartDialog
    from app.ui.labels import LengthSpin, set_display_unit

    load_operations()
    set_display_unit(unit)
    dialog = CounterpartDialog("Oberseite", "Oberseite")
    try:
        assert set(dialog.shared()) >= {"diameter", "length"}
        assert [
            dialog.shared()[name] for name in ("diameter", "length", "chamfer")
        ] == pytest.approx((4.0, 8.0, 0.6)), (
            "die Vorgaben bleiben in jeder Anzeigeeinheit dieselben Millimetermaße"
        )
        diameter = dialog._fields["diameter"]
        assert isinstance(diameter, LengthSpin)
        factor = 25.4 if unit == "in" else 1.0
        precision = 0.5 * 10 ** -diameter.decimals() * factor
        assert diameter.minimum() * factor == pytest.approx(1.0, abs=precision)
        assert diameter.maximum() * factor == pytest.approx(30.0, abs=precision)
        diameter.setValue(6.35 / factor)
        assert dialog.shared()["diameter"] == pytest.approx(6.35)

        dialog.pairs.setCurrentIndex(dialog.pairs.findData("screw_and_nut"))
        werte = dialog.shared()
        assert "size" in werte, "Schraube und Mutter teilen ihre Größe"
        assert "diameter" not in werte, "was die Hälften nicht teilen, steht nicht da"
    finally:
        dialog.deleteLater()


def test_a_thread_brings_its_half_and_the_dialog_stays_closed(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ist eine der zwei Stellen ein Gewinde, gibt es nichts zu wählen (P2.6, Entscheidung 15).

    Das Gegenstück ist das gegengleiche Gewinde am anderen Teil, im Maß des
    vorhandenen — der Dialog bliebe eine Frage ohne Antwortmöglichkeit und
    wird deshalb gar nicht geöffnet. Gemessen wird der ganze Weg vom Klick:
    ein Verlaufsschritt, ein Innengewinde M6 auf der zweiten Platte, eine
    Gewindepassung zwischen beiden.
    """
    from app.ui import counterpart_dialog as module

    window = MainWindow(Session(), UiSettings())
    try:
        first, second = _two_plates(window)
        window.session.history.apply(
            "Bolzen auf der ersten Platte",
            [
                OperationDraft(
                    op="insert_printed_thread",
                    inputs=(first,),
                    params={"size": "M6", "length": 8.0, "internal": False, "z": 10.0},
                )
            ],
        )
        window.session.evaluate_now()
        result = window.session.last_result
        assert result is not None
        threads = [
            name
            for name, feature in result.scene.objects[first].features.items()
            if feature.kind == "thread" and feature.provenance == "generated"
        ]
        assert len(threads) == 1
        window.object_tree.select_features(
            ((first, threads[0]), (second, _top_face(window, second)))
        )
        QApplication.processEvents()

        def no_dialog(self: object) -> int:
            raise AssertionError("am Gewinde gibt es nichts zu wählen — kein Dialog")

        monkeypatch.setattr(module.CounterpartDialog, "exec", no_dialog)
        document = window.session.project.document
        before = len(document.transactions)

        window.action_counterpart()

        assert len(document.transactions) == before + 1, "das Gegenstück ist eine Handlung"
        step = document.ops[-1]
        assert step.op == "insert_printed_thread" and step.inputs == (second,)
        assert step.params["size"] == "M6" and step.params["internal"] is True
        assert step.params["at_feature"] == _top_face(window, second)
        assert window.session.wait_for_idle(30_000)
        assert len(document.fits) == 1 and document.fits[0].kind == "thread"
        passung = document.fits[0]
        assert passung.a.object_id == first and passung.a.feature_id == threads[0]
        result = window.session.last_result
        assert result is not None
        assert passung.b.feature_id in result.scene.objects[passung.b.object_id].features
    finally:
        release = getattr(type(window), "release", None)
        if release is not None:
            release(window)
        window.deleteLater()


def test_the_thread_counterpart_does_not_hold_the_window_while_it_is_evaluated(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Klick kehrt zurück, bevor gerechnet ist — und die Passung kommt nach.

    Bis zum 21.09.2026 rief ``create_thread_counterpart`` die Auswertung
    synchron im Hauptthread: 0,34 s an zwei Netzplatten, 18,6 s an zwei
    exakten, ohne Balken und ohne Abbrechen (Review Fenster #2). Gemessen mit
    einer Auswertung, die im Arbeiter wartet, bis der Test sie freigibt: Der
    Klick ist vorher zurück, der Schritt steht, die Passung fehlt noch — und
    nach der Freigabe ist sie da, mit der Ansage dazu.
    """
    import threading

    from app.ui import counterpart_dialog as module

    window = MainWindow(Session(), UiSettings())
    try:
        first, second = _two_plates(window)
        window.session.history.apply(
            "Bolzen auf der ersten Platte",
            [
                OperationDraft(
                    op="insert_printed_thread",
                    inputs=(first,),
                    params={"size": "M6", "length": 8.0, "internal": False, "z": 10.0},
                )
            ],
        )
        window.session.evaluate_now()
        result = window.session.last_result
        assert result is not None
        thread = next(
            name
            for name, feature in result.scene.objects[first].features.items()
            if feature.kind == "thread" and feature.provenance == "generated"
        )
        window.object_tree.select_features(((first, thread), (second, _top_face(window, second))))
        QApplication.processEvents()
        monkeypatch.setattr(
            module.CounterpartDialog,
            "exec",
            lambda self: (_ for _ in ()).throw(AssertionError("kein Dialog am Gewinde")),
        )
        gate = threading.Event()
        original = type(window.session).run_evaluation

        def held(self: Session, quality: object = None) -> object:
            """Die Auswertung wartet auf den Test — im Arbeiter, nicht im Klick."""
            assert threading.current_thread() is not threading.main_thread()
            assert gate.wait(30.0), "der Test hat die Auswertung nie freigegeben"
            return original(self, quality)  # type: ignore[arg-type]

        monkeypatch.setattr(type(window.session), "run_evaluation", held)
        said: list[str] = []
        monkeypatch.setattr(window, "announce", lambda text, **_kw: said.append(str(text)))
        document = window.session.project.document
        before = len(document.transactions)

        window.action_counterpart()

        assert len(document.transactions) == before + 1, "der Schritt steht sofort"
        assert not document.fits, "die Passung wartet auf die Auswertung"
        assert window.session.busy, "die im Arbeiter läuft, mit Balken und Abbrechen"
        gate.set()
        assert window.session.wait_for_idle(30_000)
        assert len(document.fits) == 1 and document.fits[0].kind == "thread"
        assert any("Passung" in text for text in said), said
    finally:
        window.release()
        window.deleteLater()


def test_a_result_from_before_the_counterpart_does_not_use_up_its_fit(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Ergebnis, das schon beim Eintreffen überholt ist, trägt keine Passung nach.

    Die Passung eines Gegenstücks wartet auf die nächste Auswertung
    (``Session._finish_after``). Läuft beim Einsetzen schon eine, bricht
    ``evaluate_async`` sie ab und reiht einen Nachlauf ein — kommt ihr
    Ergebnis trotzdem an (``result_current`` ist dann falsch), fehlten darin
    die neuen Hälften. Bis zum 22.09.2026 verbrauchte genau dieses Ergebnis
    den Abschluss: ``attach_fit`` fand die Merkmale nicht, meldete „nicht
    nachgetragen", und der Nachlauf mit den echten Hälften hatte nichts mehr
    nachzutragen. Nachgestellt, indem der gehaltene Lauf sein altes Ergebnis
    zustellt, während der Nachlauf schon eingereiht ist.
    """
    import threading

    from app.ui import counterpart_dialog as module

    window = MainWindow(Session(), UiSettings())
    try:
        first, second = _two_plates(window)
        session = window.session
        session.history.apply(
            "Bolzen auf der ersten Platte",
            [
                OperationDraft(
                    op="insert_printed_thread",
                    inputs=(first,),
                    params={"size": "M6", "length": 8.0, "internal": False, "z": 10.0},
                )
            ],
        )
        session.evaluate_now()
        stale = session.last_result
        assert stale is not None
        thread = next(
            name
            for name, feature in stale.scene.objects[first].features.items()
            if feature.kind == "thread" and feature.provenance == "generated"
        )
        window.object_tree.select_features(((first, thread), (second, _top_face(window, second))))
        QApplication.processEvents()
        monkeypatch.setattr(
            module.CounterpartDialog,
            "exec",
            lambda self: (_ for _ in ()).throw(AssertionError("kein Dialog am Gewinde")),
        )
        gate = threading.Event()
        original = type(session).run_evaluation

        def held(self: Session, quality: object = None) -> object:
            assert gate.wait(30.0), "der Test hat die Auswertung nie freigegeben"
            return original(self, quality)  # type: ignore[arg-type]

        monkeypatch.setattr(type(session), "run_evaluation", held)
        document = session.project.document

        window.action_counterpart()
        session.evaluate_async()
        assert session._rerun_pending, "der Nachlauf ist eingereiht"

        # Der laufende Arbeiter meldet sich mit dem Stand von vorher.
        session._on_finished(stale, finished=session._worker)
        assert not document.fits
        assert session._after_evaluation, "der Abschluss wartet weiter auf ein gültiges Ergebnis"

        gate.set()
        assert session.wait_for_idle(30_000)
        assert len(document.fits) == 1 and document.fits[0].kind == "thread"
    finally:
        window.release()
        window.deleteLater()


def test_the_counterpart_labels_carry_no_colon(qt_app: QApplication) -> None:
    """„Paar“ stand ohne, „Durchmesser:“, „Länge:“ und die übrigen Maße mit
    Doppelpunkt — dieselbe Form wie jede andere Formularzeile (RM-342, C-N1)."""
    from PySide6.QtWidgets import QLabel

    from app.core.bootstrap import load_operations
    from app.ui.counterpart_dialog import CounterpartDialog

    load_operations()
    dialog = CounterpartDialog("Oberseite", "Oberseite")
    try:
        captions = [
            caption.text()
            for field in dialog._fields.values()
            if isinstance(caption := dialog.form.labelForField(field), QLabel)
        ]
        assert captions, "die Maße stehen da"
        assert not [text for text in captions if text.rstrip().endswith(":")], captions
    finally:
        dialog.deleteLater()


def test_a_measured_thread_keeps_its_size_note_in_the_report(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Satz über das Maß des Gegenstücks steht im Prüfbericht und bleibt dort.

    Ein eingelesener Bolzen Ø 7 x 1 ist keine Normgröße; das Gegenstück nimmt
    das gemessene Maß, und der Satz dazu stand nur in der Statuszeile (Review
    RM-532 Runde 2, K-N4). Jetzt sagt ihn die Prüfung der Gewindepassung — nach
    dem Klick und nach jeder weiteren Auswertung.
    """
    import hashlib

    from app.core.brep.profiles import threaded_rod
    from app.core.brep.step import write
    from app.core.types import Source
    from app.ui import counterpart_dialog as module

    window = MainWindow(Session(), UiSettings())
    try:
        first, second = _two_plates(window)
        project = window.session.project
        payload = write(threaded_rod(7.0, 1.0, 12.0))
        project.sources["bolt"] = payload
        project.document.sources["bolt"] = Source(
            id="bolt",
            kind="import",
            path="sources/bolt.step",
            sha256=hashlib.sha256(payload).hexdigest(),
        )
        window.session.history.apply(
            "Bolzen", [OperationDraft(op="load_step", params={"source": "bolt"})]
        )
        result = window.session.evaluate_now()
        # Der Baum kennt den Bolzen erst mit dem neuen Stand; ohne ihn fand die
        # Auswahl nur die Fläche, und *Gegenstück* hielt modal mit „Markieren
        # Sie an jedem der beiden Teile …“ an (Review P2: der Test hing).
        window._on_scene(result)
        qt_app.processEvents()
        bolt = next(name for name in result.scene.objects if name not in (first, second))
        threads = [
            name
            for name, feature in result.scene.objects[bolt].features.items()
            if feature.kind == "thread"
        ]
        assert len(threads) == 1, "der eingelesene Bolzen trägt ein erkanntes Gewinde"
        window.object_tree.select_features(
            ((bolt, threads[0]), (second, _top_face(window, second)))
        )
        QApplication.processEvents()
        assert len(window.object_tree.selected_features()) > 2, (
            "das Gewinde bündelt seine Flanken — sonst prüft der Test die Stellen nicht"
        )
        assert len(window.object_tree.selected_places()) == 2, "zwei Stellen sind markiert"

        def no_dialog(self: object) -> int:
            raise AssertionError("am Gewinde gibt es nichts zu wählen — kein Dialog")

        monkeypatch.setattr(module.CounterpartDialog, "exec", no_dialog)
        window.action_counterpart()
        assert window.session.wait_for_idle(60_000)
        qt_app.processEvents()
        document = window.session.project.document
        assert len(document.fits) == 1 and document.fits[0].kind == "thread"

        def noted() -> list[str]:
            return [
                finding.object_id or ""
                for finding in window.report._findings
                if finding.code == "parts.counterpart_own_measure"
            ]

        assert noted() == [bolt], [finding.code for finding in window.report._findings]
        window.session.evaluate_now()
        assert window.session.wait_for_idle(60_000)
        qt_app.processEvents()
        assert noted() == [bolt], "der Satz übersteht die nächste Auswertung"
    finally:
        release = getattr(type(window), "release", None)
        if release is not None:
            release(window)
        window.deleteLater()


def test_the_pin_for_a_bore_is_offered_at_an_internal_thread_only(qt_app: QApplication) -> None:
    """Am Innengewinde steht *Stift für Bohrung* in der Karte, am Außengewinde nicht (RM-536).

    Der Stift baut das passende Außengewinde in eine Gewindebohrung; an einem
    Bolzen gibt es keine Bohrung, in die er gehört (``actions.not_offered_at``).
    **Erkannte Gewinde aus dem Korpus** (Review P2, G5): Der frühere Aufbau
    stellte den Bolzen neben die Platte; das gedruckte Gewinde prüft
    ``test_a_printed_inner_thread_offers_only_the_pin_in_the_card``.
    """
    from tests.helpers import exact_kernel

    exact_kernel()
    offered: dict[bool, bool] = {}
    for name, internal in (("m8_innen.step", True), ("m6_rechts.step", False)):
        window = MainWindow(Session(), UiSettings())
        try:
            window.open_path(THREADS / name)
            assert window.session.wait_for_idle(60_000)
            result = window.session.evaluate_now()
            object_id, entry = next(iter(result.scene.objects.items()))
            [thread] = [key for key, feature in entry.features.items() if feature.kind == "thread"]
            assert bool(entry.features[thread].params.get("internal")) is internal
            window.object_tree.select_object(object_id)
            window.object_tree.select_feature(object_id, thread)
            QApplication.processEvents()
            panel = window.selection_operations
            assert not panel.isHidden(), "die Karte steht da, kein Baustein darüber"
            assert panel.chosen_level() == "thread"
            offered[internal] = panel._fits_the_level("pin_for_bore")
        finally:
            window.wait_for_workers()
            release = getattr(type(window), "release", None)
            if release is not None:
                release(window)
            window.deleteLater()
    assert offered == {True: True, False: False}


def test_a_printed_inner_thread_offers_only_the_pin_in_the_card(qt_app: QApplication) -> None:
    """Am gedruckten Innengewinde steht in der Karte genau *Stift für Bohrung* (RM-536).

    An einem Merkmal eines Bausteins bedienen die Bausteinfelder den Schritt,
    die Karte war deshalb ganz verborgen — auch der Stift, den der Kunde gerade
    zu seinem selbst gedruckten Gewinde will (Entscheidung Robert, 07.10.2026).
    Jetzt steht er dort allein; am gedruckten Außengewinde bleibt die Karte zu.
    """
    window = MainWindow(Session(), UiSettings())
    try:
        first, second = _two_plates(window)
        window.session.history.apply(
            "Gewinde",
            [
                OperationDraft(
                    op="insert_printed_thread",
                    inputs=(first,),
                    params={"size": "M6", "length": 8.0, "internal": True, "z": 10.0},
                ),
                OperationDraft(
                    op="insert_printed_thread",
                    inputs=(second,),
                    params={"size": "M6", "length": 8.0, "internal": False, "x": 60.0, "z": 10.0},
                ),
            ],
        )
        window.session.evaluate_now()
        result = window.session.last_result
        assert result is not None
        assert not [entry for entry in result.scene.report.findings if entry.severity == "error"]

        def thread_of(object_id: str) -> str:
            [name] = [
                name
                for name, feature in result.scene.objects[object_id].features.items()
                if feature.kind == "thread" and feature.provenance == "generated"
            ]
            return name

        panel = window.selection_operations
        window.object_tree.select_object(first)
        window.object_tree.select_feature(first, thread_of(first))
        QApplication.processEvents()
        assert window._common_part_step(window.object_tree.selected_features()) is not None, (
            "das Gewinde ist ein Bausteinmerkmal — sonst prüft der Test nichts"
        )
        assert not panel.isHidden(), "die Karte steht da"
        assert panel.chosen_level() == "thread"
        offered = {name for name in panel._buttons if panel._fits_the_level(name)}
        assert offered == {"pin_for_bore"}
        button = panel._buttons["pin_for_bore"]
        assert "pin_for_bore" in panel._quick_shown or not button.isHidden()
        assert button.isEnabled()
        assert panel.catalog_button.isHidden(), "kein Katalog an einem Bausteinmerkmal"

        window.object_tree.select_object(second)
        window.object_tree.select_feature(second, thread_of(second))
        QApplication.processEvents()
        assert panel.isHidden(), "am Außengewinde gibt es keinen Stift, und die Karte bleibt zu"
    finally:
        release = getattr(type(window), "release", None)
        if release is not None:
            release(window)
        window.deleteLater()


def _a_pin_on_a_short_thread(window: MainWindow) -> None:
    """Ein gedrucktes M6 von 2 mm und darauf der Stift, der dafür zu wenig Gewinde hat."""
    window.session.start_new("centauri-carbon-2", "petg")
    window.session.history.apply(
        "Quader mit Gewinde",
        [
            OperationDraft(op="create_box", params={"width": 30.0, "depth": 30.0, "height": 12.0}),
            OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": 5.0, "z": 12.0}),
            OperationDraft(
                op="insert_printed_thread",
                inputs=("obj_1",),
                params={"size": "M6", "length": 2.0, "internal": True, "at_feature": "hole_1"},
            ),
        ],
    )
    window.session.evaluate_now()
    result = window.session.last_result
    assert result is not None
    [thread] = [
        name
        for name, feature in result.scene.objects["obj_1"].features.items()
        if feature.kind == "thread" and feature.provenance == "generated"
    ]
    window.session.history.apply(
        "Stift",
        [OperationDraft(op="pin_for_bore", inputs=("obj_1",), params={"at_feature": thread})],
    )
    window.session.evaluate_now()


def _length_has_the_cursor(window: MainWindow) -> None:
    """Offen ist der Dialog des Gewindes, und der Cursor steht in *Länge*."""
    from PySide6.QtWidgets import QDoubleSpinBox

    dialog = window._op_dialog
    assert dialog is not None, "der Dialog ging nicht auf"
    try:
        assert dialog.spec.name == "insert_printed_thread"
        inner = dialog._editors["length"].findChild(QDoubleSpinBox)
        assert inner is not None and inner.hasFocus()
    finally:
        dialog.reject()


def test_a_thread_too_short_for_the_pin_opens_the_thread_step_at_its_length(
    qt_app: QApplication,
) -> None:
    """*Gewindeschritt öffnen* am Stift öffnet das Gewinde, nicht den Stift (Review P2, M2).

    Ein gedrucktes M6 von 2 mm lässt dem Stift weniger als die kürzeste
    druckbare Gewindelänge; zu ändern ist das Gewinde. Geprüft an der ganzen
    Kette: Befund, Knopf, Dialog des früheren Schritts, Cursor in *Länge*.
    """
    from app.ui.panels import as_error

    window = MainWindow(Session(), UiSettings())
    try:
        _a_pin_on_a_short_thread(window)
        result = window.session.last_result
        assert result is not None
        [finding] = [
            entry for entry in result.scene.report.findings if entry.code.startswith("op.pin")
        ]
        assert "change_creating_step" in {action.id for action in finding.suggestions}

        window.error_handlers()["change_creating_step"](as_error(finding))
        QApplication.processEvents()
        _length_has_the_cursor(window)
    finally:
        release = getattr(type(window), "release", None)
        if release is not None:
            release(window)
        window.deleteLater()


def test_the_pin_dialog_offers_to_open_the_thread_step(qt_app: QApplication) -> None:
    """Im Dialog des Stifts steht *Gewindeschritt öffnen* an der Absage (Review P2 N6).

    Wo der Kunde die Absage zuerst sieht, in der Vorschau des Dialogs, stand
    der Satz ohne Knopf: Der Dialog zeigt nur Handlungen, die er selbst
    einlöst. Der Knopf schließt ihn jetzt und öffnet das Gewinde an *Länge*.
    """
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton

    from app.core.errors import CHANGE_THREAD_STEP

    window = MainWindow(Session(), UiSettings())
    try:
        _a_pin_on_a_short_thread(window)
        pin_step = window.session.history.operations[-1].id
        window.edit_operation(pin_step)
        pin_dialog = window._op_dialog
        assert pin_dialog is not None and pin_dialog.spec.name == "pin_for_bore"
        # Übernehmen vor dem Bild fordert die Vorschau an und wartet auf sie
        # (``preview_defer``); sie sagt ab, und nichts wird übernommen.
        QTest.qWait(100)
        assert window.session.wait_for_idle(60_000)
        pin_dialog.accept()
        label = str(CHANGE_THREAD_STEP.label)
        button = None
        for _round in range(100):
            QTest.qWait(100)
            assert window.session.wait_for_idle(60_000)
            button = next(
                (
                    entry
                    for entry in pin_dialog.findChildren(QPushButton)
                    if entry.text() == label and entry.isVisible()
                ),
                None,
            )
            if button is not None:
                break
        assert button is not None, "die Absage im Dialog trägt keinen Knopf zum Gewinde"
        button.click()
        QApplication.processEvents()
        assert window._op_dialog is not pin_dialog, "der Dialog des Stifts ging nicht zu"
        _length_has_the_cursor(window)
    finally:
        release = getattr(type(window), "release", None)
        if release is not None:
            release(window)
        window.deleteLater()
