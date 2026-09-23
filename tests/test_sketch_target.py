"""Zeichnen gilt genau einem Körper — Zielkörper, Nachbarn, Wege aus dem Modus.

Robert, 23.09.2026: „Beim Zeichnen wäre es auch gut, wenn man nur einen Körper
hat und nicht alle, also am besten den ausgewählten; oder wenn keiner
ausgewählt ist, ist man beim neu Zeichnen." Die Soll-Abläufe stehen im Bericht
„Bedienabnahme Zeichnen" (Abschnitt 7, Paket Z1); dazu die Befunde aus Z0, die
die Oberfläche betreffen: die Vorbelegung aus der Auswahl (F1, F2), *Fertig*
mit einer Bedeutung (E2), die veraltete Statuszeile (B3), der Satz über das
Abtragen im leeren Projekt (E9) und Escape, das nicht mehr verwirft (R5).

Die Fälle ohne Fenster stehen oben; alles mit ``qt_app`` ist ein Fenstertest
und läuft beim Release (``tests/conftest.py`` markiert ihn).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

pytest.importorskip("PySide6")

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY
from app.core.sketch import shapes
from app.core.sketch.serialize import sketch_to_text

load_operations()


# --- ohne Fenster -------------------------------------------------------------------


def test_a_drawing_keeps_the_selection_out_of_the_dialog() -> None:
    """F1 und F2: Mit Zeichnung übernimmt der Dialog aus der Auswahl weder
    „Bis zur Fläche" noch X/Y/Oberkante — die Zeichnung trägt ihren Ort."""
    from app.ui.main_window import _carries_a_drawing

    text = sketch_to_text(shapes.rectangle(10.0, 10.0))
    for name in ("sketch_extrude", "sketch_join", "sketch_pocket"):
        spec = REGISTRY.get(name)
        assert _carries_a_drawing(spec, {"sketch": text}), name
        assert not _carries_a_drawing(spec, {"sketch": ""}), name
        assert not _carries_a_drawing(spec, None), name
    assert not _carries_a_drawing(REGISTRY.get("drill_hole"), {"sketch": text})


def test_the_join_stands_beside_the_pull_in_the_variant_group() -> None:
    """*An Körper anfügen* ist die zweite Art des Hochziehens (E4) — im
    Dialog umschaltbar, ohne eigene Menüzeile."""
    from app.core.registry import VARIANT_GROUPS

    members = VARIANT_GROUPS[0].members
    assert members.index("sketch_join") == members.index("sketch_extrude") + 1
    join = REGISTRY.get("sketch_join")
    pull = REGISTRY.get("sketch_extrude")
    assert join.consumes == 1 and pull.consumes == 0
    assert {entry.name for entry in pull.params.spec()} - {"name"} == {
        entry.name for entry in join.params.spec()
    }, "beide Arten tragen dasselbe Schema, der Umschalter verliert keine Zahl"


# --- Fenster --------------------------------------------------------------------------


def _window_with_three_bodies():
    """Clip und Keil exakt, ein Stift als Netz — wie der Messaufbau der Abnahme."""
    from app.core.scene import OperationDraft
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    window.session.apply(
        "Szene",
        [
            OperationDraft(
                op="create_brep_box",
                params={"width": 40.0, "depth": 30.0, "height": 10.0, "name": "Clip"},
            ),
            OperationDraft(
                op="create_brep_box",
                params={"width": 20.0, "depth": 20.0, "height": 20.0, "x": 80.0, "name": "Keil"},
            ),
            OperationDraft(
                op="create_cylinder",
                params={"diameter": 8.0, "height": 30.0, "x": -60.0, "name": "Stift"},
            ),
        ],
    )
    assert window.session.wait_for_idle(60000)
    names = {entry.name: key for key, entry in window.session.last_result.scene.objects.items()}
    return window, names


def _close(window) -> None:
    if window._sketch_panel is not None:
        window.finish_sketch(keep=False)
    window.wait_for_workers()
    window.deleteLater()


def test_the_selected_body_is_the_only_one_while_drawing(qt_app) -> None:
    """Abnahme 7.4 (1): Clip gewählt, *Zeichnen* — Ebenenfeld nur mit
    Flächen des Clips (höchstens zwölf Einträge), *Projizieren* sieht nur ihn,
    die anderen sind ausgeblendet und kein Klickziel."""
    window, names = _window_with_three_bodies()
    try:
        clip, keil, stift = names["Clip"], names["Keil"], names["Stift"]
        window.object_tree.select_object(clip)
        window.action_sketch_free()
        panel = window._sketch_panel
        assert window.sketch_body() == clip
        assert window.viewport.sketch_focus == (clip, False)
        entries = [panel.plane_choice.itemText(i) for i in range(panel.plane_choice.count())]
        assert len(entries) <= 12, entries
        assert all("Clip" in entry for entry in entries if "Fläche" in entry), entries
        scene = window.session.last_result.scene
        assert not window.viewport._in_view(keil, scene.objects[keil])
        assert not window.viewport._in_view(stift, scene.objects[stift])
        assert window.viewport._in_view(clip, scene.objects[clip])
        assert len(panel.canvas._bodies) == 1, "Projizieren sieht nur den Zielkörper"
        assert window.sketch_body_choice.currentText() == "Clip"
        card = window.viewport.plane_picker._buttons.get("face")
        assert card is not None and not card.isHidden(), "die Oberseite steht als Karte da"
    finally:
        _close(window)


def test_showing_the_neighbours_keeps_them_out_of_reach(qt_app) -> None:
    """*Nachbarn zeigen*: durchscheinend und ohne Kanten im Bild, aber weder
    Klickziel noch Ebene noch Projektionsvorlage (Entscheidung Robert,
    23.09.2026). Ein zweiter Klick blendet sie wieder aus."""
    from tests.render_fakes import RecordingRenderer

    window, names = _window_with_three_bodies()
    try:
        clip, keil, stift = names["Clip"], names["Keil"], names["Stift"]
        renderer = RecordingRenderer()
        window.viewport.renderer = renderer
        window.object_tree.select_object(clip)
        window.action_sketch_free()
        panel = window._sketch_panel
        window.toggle_sketch_neighbours()
        assert window.viewport.sketch_focus == (clip, True)
        assert window.sketch_neighbours_button.isChecked()
        assert window.sketch_neighbours_button.text() == "Nachbarn ausblenden", (
            "der Zustand steht im Wort, nicht nur in der Farbe (Regel 18)"
        )
        scene = window.session.last_result.scene
        assert not window.viewport._in_view(keil, scene.objects[keil])
        drawn = window.viewport.sketch_neighbours_drawn()
        assert set(drawn) == {keil, stift}, drawn
        styles = [renderer.style_of(f"neighbour:{keil}")]
        assert styles[0].pickable is False and styles[0].show_edges is False
        assert len(panel.canvas._bodies) == 1, "an Nachbarn richtet man aus, man zeichnet nicht"
        window.toggle_sketch_neighbours()
        assert window.viewport.sketch_focus == (clip, False)
        assert not window.viewport.sketch_neighbours_drawn()
    finally:
        _close(window)


def test_nothing_selected_means_drawing_a_new_body(qt_app) -> None:
    """Abnahme 7.4 (2): Nichts gewählt, Rechteck, *Fertig* — ein neuer
    Körper; die alten bleiben unverändert. *Abtragen* steht nicht da, das
    Ebenenfeld nennt nur die Grundebenen, und die Karte im Bild spricht nicht
    vom Abtragen (E9)."""
    from app.ui.main_window import PULL_OP

    window, _names = _window_with_three_bodies()
    try:
        window.object_tree.select_object(None)
        window.action_sketch_free()
        panel = window._sketch_panel
        assert window.sketch_body() is None
        scene = window.session.last_result.scene
        assert not any(window.viewport._in_view(key, entry) for key, entry in scene.objects.items())
        assert window.sketch_cut_button.isHidden()
        entries = [panel.plane_choice.itemText(i) for i in range(panel.plane_choice.count())]
        assert not any("Fläche" in entry for entry in entries), entries
        panel.canvas.set_sketch(shapes.rectangle(20.0, 20.0))
        window._update_sketch_hint()
        assert "Abtragen" not in window.viewport.sketch_action.text()
        assert window._pull_op() == PULL_OP
        opened: list[str] = []
        window.run_operation = lambda spec, given=None, **kw: opened.append(spec.name)
        window.sketch_finish_button.click()
        assert opened == [PULL_OP], "ohne Ziel wird Fertig ein neuer Körper"
    finally:
        _close(window)


def test_pulling_on_the_target_joins_it(qt_app) -> None:
    """E4: Auf der Oberseite des Ziels heißt *Hochziehen* anfügen — ein
    Körper, ein Schritt. Die Liste unter *Mehr* bietet das Hochziehen als
    neuer Körper ausdrücklich an und wiederholt die Knöpfe daneben nicht."""
    from app.ui.main_window import JOIN_OP, POCKET_OP, PULL_OP

    window, names = _window_with_three_bodies()
    try:
        clip = names["Clip"]
        window.object_tree.select_object(clip)
        window.action_sketch_free()
        window.viewport.plane_picker._buttons["face"].click()
        panel = window._sketch_panel
        assert panel.canvas.sketch.plane.startswith(f"feature:{clip}:")
        panel.canvas.set_sketch(
            replace(shapes.rectangle(10.0, 10.0), plane=panel.canvas.sketch.plane)
        )
        window._update_sketch_hint()
        assert window._pull_op() == JOIN_OP
        hidden = {name for name, action in window._finish_actions.items() if not action.isVisible()}
        assert hidden == {JOIN_OP, POCKET_OP}
        assert window._finish_actions[PULL_OP].isVisible()
        opened: list[tuple[str, tuple[str, ...]]] = []
        window.run_operation = lambda spec, given=None, **kw: opened.append(
            (spec.name, window.object_tree.selected_objects())
        )
        window.sketch_pull_button.click()
        assert opened == [(JOIN_OP, (clip,))], "angefügt wird an das Ziel, und es ist gewählt"
    finally:
        _close(window)


def test_several_selected_bodies_are_a_question(qt_app) -> None:
    """Regel 21: Zwei gewählte Körper — die Leiste fragt mit ihren Namen und
    *Neuer Körper*, statt still einen zu nehmen."""
    window, names = _window_with_three_bodies()
    try:
        window.object_tree.select_object(names["Clip"])
        window.object_tree.select_object(names["Keil"], add=True)
        window.action_sketch_free()
        assert window.sketch_body() is None
        assert not window._sketch_question.isHidden()
        from PySide6.QtWidgets import QPushButton

        buttons = {
            button.text(): button
            for button in window._sketch_question.findChildren(QPushButton)
            if not button.isHidden()
        }
        assert {"Clip", "Keil", "Neuer Körper"} <= set(buttons)
        buttons["Keil"].click()
        assert window.sketch_body() == names["Keil"]
        assert window._sketch_question.isHidden()
    finally:
        _close(window)


def test_a_vanished_target_leaves_the_drawing_and_says_so(qt_app) -> None:
    """Abschnitt 7.3: Verschwindet der Zielkörper im Modus (ein Agent, die
    Fernsteuerung), bleibt die Zeichnung, die Leiste sagt es, und *Fertig*
    legt einen neuen Körper an."""
    from app.core.scene import OperationDraft

    window, names = _window_with_three_bodies()
    try:
        keil = names["Keil"]
        window.object_tree.select_object(keil)
        window.action_sketch_free()
        window._sketch_panel.canvas.set_sketch(shapes.rectangle(5.0, 5.0))
        window.session.apply("weg", [OperationDraft(op="delete_object", inputs=(keil,))])
        assert window.session.wait_for_idle(60000)
        assert window.sketch_body() is None
        assert window.sketching() and window._sketch_panel.canvas.sketch.elements
        assert "Keil" in window.status_message.text()
    finally:
        _close(window)


def test_leaving_restores_the_view(qt_app) -> None:
    """Abschnitt 7.2 (4): Nach dem Verlassen ist alles wieder zu sehen, und
    die Nachbarregel gilt nicht mehr."""
    window, names = _window_with_three_bodies()
    try:
        window.object_tree.select_object(names["Clip"])
        window.action_sketch_free()
        window.finish_sketch(keep=False)
        scene = window.session.last_result.scene
        assert window.viewport.sketch_focus is None
        assert all(window.viewport._in_view(key, entry) for key, entry in scene.objects.items())
    finally:
        _close(window)


def test_escape_never_discards_the_drawing(qt_app) -> None:
    """R5 (Entscheidung Robert, 23.09.2026): Escape legt Werkzeug und Auswahl
    ab und verwirft nie. Verlassen wird über *Fertig* oder *Verwerfen*."""
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.start_sketch("", sketch_to_text(shapes.rectangle(20.0, 10.0)))
        for _ in range(5):
            window._escape()
        assert window.sketching()
        assert window._sketch_panel.canvas.sketch.elements
        assert "Verwerfen" in window.status_message.text()
    finally:
        _close(window)


def test_finish_has_one_meaning_under_a_real_press(qt_app, monkeypatch) -> None:
    """E2: *Fertig* trug ein Menü **und** ``clicked``. Welche Bedeutung eine
    Geste traf, hing daran, wer das Loslassen bekam — mit ``QTest`` ging der
    Dialog der Vorgabe auf und das Menü nie. Jetzt ist *Fertig* ein Knopf ohne
    Menü, die übrigen Arten stehen unter *Mehr*, und *Mehr* schließt nichts ab.
    Geprüft mit Drücken und Loslassen am sichtbaren Knopf."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.resize(1400, 900)
        window.show()
        window.start_sketch("", sketch_to_text(shapes.rectangle(20.0, 10.0)))
        assert window.sketch_finish_button.menu() is None
        assert window.sketch_more_button.menu() is window._finish_menu
        finished: list[bool] = []
        monkeypatch.setattr(window, "finish_sketch", lambda keep=True, **kw: finished.append(keep))
        QTest.mousePress(window.sketch_more_button, Qt.MouseButton.LeftButton)
        QTest.mouseRelease(window.sketch_more_button, Qt.MouseButton.LeftButton)
        window._finish_menu.close()
        assert finished == [], "Mehr schließt nichts ab"
        QTest.mousePress(window.sketch_finish_button, Qt.MouseButton.LeftButton)
        QTest.mouseRelease(window.sketch_finish_button, Qt.MouseButton.LeftButton)
        assert finished == [True], "ein Klick, eine Handlung"
    finally:
        monkeypatch.undo()
        _close(window)


def test_entering_clears_a_stale_grip_sentence(qt_app) -> None:
    """B3: Der Satz über den Flächengriff blieb im Zeichenmodus stehen —
    einen solchen Griff gibt es dort nicht."""
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.announce("Der Griff versetzt die gewählte Fläche entlang ihrer Normalen.")
        window.start_sketch("")
        assert window.status_message.text() == ""
    finally:
        _close(window)


def test_the_face_panel_offers_drawing_and_cutting(qt_app) -> None:
    """B2/S2: Das Auswahlfenster einer ebenen Fläche bietet *Hier zeichnen*
    und *Loch oder Aussparung zeichnen …*; beide beginnen den Modus auf der
    Fläche mit ihrem Körper als Ziel, die zweite mit der Tasche als Art."""
    from PySide6.QtWidgets import QPushButton

    from app.ui.main_window import POCKET_OP

    window, names = _window_with_three_bodies()
    try:
        clip = names["Clip"]
        entry = window.session.last_result.scene.objects[clip]
        face = next(
            key
            for key, feature in entry.features.items()
            if feature.kind == "face" and feature.params["normal"][2] > 0.99
        )
        window.object_tree.select_feature(clip, face)
        texts = {
            button.text(): button
            for button in window.feature_panel.findChildren(QPushButton)
            if not button.isHidden()
        }
        assert "Hier zeichnen" in texts and "Loch oder Aussparung zeichnen …" in texts
        texts["Loch oder Aussparung zeichnen …"].click()
        assert window.sketching()
        assert window._sketch_target == POCKET_OP
        assert window.sketch_body() == clip
        assert window._sketch_panel.canvas.sketch.plane == f"feature:{clip}:{face}"
    finally:
        _close(window)


def test_reusing_a_drawing_opens_a_copy_for_a_new_step(qt_app) -> None:
    """E6 (Entscheidung Robert, 23.09.2026): „Zeichnung weiterverwenden" am
    Verlaufsschritt öffnet eine Kopie als freie Zeichnung — *Fertig* legt
    einen neuen Schritt an, der alte bleibt."""
    from app.core.scene import OperationDraft

    window, names = _window_with_three_bodies()
    try:
        clip = names["Clip"]
        text = sketch_to_text(shapes.rectangle(6.0, 6.0))
        window.session.apply(
            "Zapfen",
            [OperationDraft(op="sketch_join", inputs=(clip,), params={"sketch": text})],
        )
        assert window.session.wait_for_idle(60000)
        step = window.session.project.document.ops[-1].id
        assert step in window.history_panel._drawn
        window.reuse_drawing(step)
        assert window.sketching()
        assert window._sketch_step is None, "kein Schritt gebunden — Fertig legt einen neuen an"
        assert window.sketch_body() == clip, "Ziel ist der Körper des Schritts"
        assert window._sketch_panel.sketch_text().strip()
    finally:
        _close(window)
