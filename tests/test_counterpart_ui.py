"""Der Weg zu den Gegenstücken im Fenster (RM-147 E1, §18.5, §2.6).

Der Kern kann das Paar (``tests/test_counterpart.py``); hier steht, ob ein
Kunde dorthin kommt: Der Menüeintrag ist gesperrt, solange die Auswahl ihn
nicht trägt, und er sagt warum — und mit zwei markierten Stellen an zwei Teilen
entstehen beide Hälften und ihre Passung in einem Schritt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.scene.history import OperationDraft
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings


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
