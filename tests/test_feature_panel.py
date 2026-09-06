"""Das Merkmal-Panel: was man mit dem gewählten Merkmal tun kann, als Felder.

Robert am 03.09.2026: „evtl noch ein eigenes Panel, damit man nicht für alles
Rechtsklick machen muss — übersichtlich, verständlich, innovativ und intuitiv."

Geprüft wird, dass das Panel die Auskunft des Kerns rendert und **keine
zweite Tabelle führt**: Was gilt, welche Felder es hat und was ihr heutiger
Wert ist, sagt ``app.core.perceive.actions.actions_for``.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
)

from app.core.geom.mesh import MeshData, read_mesh
from app.core.perceive import features
from app.core.perceive.actions import actions_for
from app.core.registry import REGISTRY, validate
from app.core.types import Feature
from app.core.units import LengthUnit
from app.ui.labels import LengthSpin
from app.ui.panels import FeaturePanel

MESHES = Path(__file__).parent / "data" / "meshes"


def test_a_manual_fit_needs_a_choice_and_an_explicit_click(qt_app: QApplication) -> None:
    """Die Art allein schreibt nichts; der ausdrückliche Klick wird einmal weitergereicht."""
    panel = FeaturePanel()
    seen: list[tuple[str, object]] = []
    token = object()
    panel.fitRequested.connect(lambda kind, context: seen.append((kind, context)))
    panel.show_fit_choices({"clearance": "PLA: 0,20 mm", "press": "PLA: −0,10 mm"}, token)
    assert panel._fit_choice is not None and panel._fit_button is not None
    assert panel._fit_choice.accessibleName() == "Passungsart"
    assert not panel._fit_button.isEnabled()
    panel._fit_choice.setCurrentIndex(panel._fit_choice.findData("press"))
    assert not seen and panel._fit_button.isEnabled()
    panel.limit_fit("Die Auswertung läuft.")
    assert not panel._fit_button.isEnabled()
    assert panel._fit_button.toolTip() == "Die Auswertung läuft."
    panel.limit_fit("")
    panel._fit_button.click()
    panel._fit_button.click()
    assert seen == [("press", token)]
    assert panel._fit_button.accessibleDescription()


@pytest.mark.parametrize("selected", ["hole_1", "pin_1"])
@pytest.mark.parametrize("unit", ["mm", "in"])
def test_the_feature_panel_shows_both_sides_of_a_sleeve(
    qt_app: QApplication, selected: str, unit: LengthUnit
) -> None:
    """Die gemessene Hülle liefert beide Durchmesser und dieselbe Wand, auch in Zoll."""
    from app.ui.labels import length, set_display_unit

    bore = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={
            "diameter": 34.0,
            "depth": 27.0,
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
        },
    )
    wall = replace(bore, id="pin_1", kind="pin", params={**bore.params, "diameter": 40.8})
    found = {bore.id: bore, wall.id: wall}
    panel = FeaturePanel()
    try:
        set_display_unit(unit)
        panel.show_feature(selected, found[selected], features=found)
        values = {
            label.accessibleName(): label.text()
            for row in panel._built
            for label in row.findChildren(QLabel)
            if label.accessibleName()
        }
        assert values["Innendurchmesser"] == length(34.0)
        assert values["Außendurchmesser"] == length(40.8)
        assert values["Wandstärke"] == length(3.4)
        # Koaxial, aber ohne Längsüberdeckung: Die Auskunft darf nicht fortleben.
        apart = replace(wall, params={**wall.params, "centre": (0.0, 0.0, 100.0)})
        panel.show_feature(bore.id, bore, features={bore.id: bore, apart.id: apart})
        assert not any(
            label.accessibleName() == "Wandstärke"
            for row in panel._built
            for label in row.findChildren(QLabel)
        )
    finally:
        set_display_unit("mm")


def test_regrouping_keeps_the_selected_feature_current_and_visible(qt_app: QApplication) -> None:
    """Neue Gruppenknoten dürfen weder Tastaturziel noch sichtbare Auswahl verlieren."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.panels import ObjectTree, _feature_item

    found = {
        f"fillet_{index}": Feature(
            id=f"fillet_{index}",
            kind="fillet",
            provenance="detected",
            params={"radius": float(index + 1), "recess": True},
        )
        for index in range(60)
    }
    entry = SceneObject(id="obj_1", name="Viele Merkmale", mesh=plate(), features=found)
    tree = ObjectTree()
    tree.set_room(180)
    tree.resize(420, 220)
    tree.show_scene(EvaluationResult(Scene(objects={entry.id: entry})))
    tree.show()
    tree.select_feature(entry.id, "fillet_59")
    QApplication.processEvents()
    grouped = {
        identifier: replace(feature, params={**feature.params, "radius": 100.0})
        if int(identifier.split("_")[1]) >= 54
        else feature
        for identifier, feature in found.items()
    }
    result = EvaluationResult(Scene(objects={entry.id: replace(entry, features=grouped)}))
    tree.show_scene(result)
    QApplication.processEvents()
    selected = _feature_item(tree.tree.topLevelItem(0), "fillet_59")
    assert selected is not None and selected.parent() is not tree.tree.topLevelItem(0)
    assert tree.tree.currentItem() is selected and selected.isSelected()
    assert selected.parent().isExpanded()
    assert tree.tree.viewport().rect().contains(tree.tree.visualItemRect(selected).center())
    assert tree.tree.verticalScrollBar().value() > 0
    tree.tree.setFocus()
    QTest.keyClick(tree.tree, Qt.Key.Key_Up)
    assert tree.tree.currentItem() is not selected, (
        "die Tastatur setzt an der wiederhergestellten Zeile an"
    )
    tree.close()


def plate() -> MeshData:
    return read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl")


def a_hole() -> tuple[str, Feature]:
    found = features.detect(plate())
    return next((key, value) for key, value in found.items() if value.kind == "hole")


def buttons(panel: FeaturePanel) -> list[str]:
    return [knopf.text() for row in panel._built for knopf in row.findChildren(QPushButton)]


def fields(row: QWidget) -> list[QWidget]:
    return [
        widget
        for widget in row.findChildren(QWidget)
        if isinstance(widget, (LengthSpin, QComboBox, QCheckBox))
    ]


def test_without_a_selection_the_panel_says_what_brings_you_here(qt_app: QApplication) -> None:
    """Ein leeres Feld erklärt nichts; ein Satz schon (§2.7)."""
    panel = FeaturePanel()
    assert panel._empty.isVisibleTo(panel)
    assert panel._empty.text().strip(), "der leere Zustand trägt einen Satz"
    assert not panel._built, "und keine Zeilen"


def test_the_panel_offers_what_the_core_says_and_nothing_else(qt_app: QApplication) -> None:
    """Die Zeilen kommen aus ``actions_for`` — eine Stelle, nicht zwei.

    Verglichen wird gegen die Auskunft selbst und nicht gegen eine Liste im
    Test: Sobald der Kern eine Handlung dazubekommt, wächst das Panel mit, und
    dieser Test bleibt richtig.
    """
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)

    expected = [str(action.title) for action in actions_for(feature) if action.op is not None]
    assert expected, "ohne Handlungen prüft dieser Test nichts"
    assert buttons(panel) == expected


def test_every_number_starts_on_what_was_measured(qt_app: QApplication) -> None:
    """Roberts „sinnvolle Einstellungen": Die Vorgabe jedes Feldes ist der
    heutige Wert, damit der Kunde die eine Zahl ändert, die er meint."""
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)

    centre = feature.params["centre"]
    move = next(
        row
        for row in panel._built
        if any(k.text() == "Merkmal verschieben" for k in row.findChildren(QPushButton))
    )
    spins = [widget for widget in fields(move) if isinstance(widget, LengthSpin)]
    assert len(spins) == 3, "Ort heißt drei Achsen"
    for spin, measured in zip(spins, centre, strict=True):
        assert spin.value_mm() == pytest.approx(float(measured))


@pytest.mark.parametrize(
    ("mesh_name", "scale", "kind", "operation"),
    [
        ("plate_holes.stl", 42.0, "hole", "resize_hole"),
        ("sphere_socket.stl", 14.0, "sphere", "resize_feature"),
    ],
)
def test_a_large_detected_diameter_reaches_the_edit_unchanged(
    qt_app: QApplication,
    mesh_name: str,
    scale: float,
    kind: str,
    operation: str,
) -> None:
    """Ein vorhandenes Maß ist keine Erzeugungsgrenze.

    Die beiden Korpusmodelle liefern echte erkannte Merkmale. Vergrößert man
    sie über 200 mm, muss der gemessene Durchmesser sichtbar im Feld stehen,
    unverändert aus dem Panel kommen und vom Parameterschema angenommen
    werden. Sonst macht schon das bloße Übernehmen das Merkmal kleiner.
    """
    body = read_mesh((MESHES / mesh_name).read_bytes(), ".stl").raw.copy()
    body.apply_scale(scale)
    found = features.detect(MeshData.of(body))
    identifier, feature = next(
        (feature_id, detected) for feature_id, detected in found.items() if detected.kind == kind
    )
    measured = float(feature.params["diameter"])
    assert measured > 200.0, "der Fall erreicht die alte Klemmgrenze nicht"

    action = next(entry for entry in actions_for(feature) if entry.op == operation)
    diameter = next(field for field in action.fields if field.name == "diameter")
    assert diameter.value == pytest.approx(measured)

    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    panel.show()
    QApplication.processEvents()
    row = next(
        entry
        for entry in panel._built
        if any(button.text() == str(action.title) for button in entry.findChildren(QPushButton))
    )
    spin = next(widget for widget in fields(row) if isinstance(widget, LengthSpin))
    assert spin.isVisibleTo(panel), "der gemessene Durchmesser steht nicht sichtbar im Panel"
    assert spin.value_mm() == pytest.approx(measured), "das Panel klemmt den Messwert"

    emitted: list[tuple[str, dict[str, object]]] = []
    panel.operationRequested.connect(lambda op, params: emitted.append((op, params)))
    next(
        button for button in row.findChildren(QPushButton) if button.text() == str(action.title)
    ).click()

    assert len(emitted) == 1
    emitted_op, params = emitted[0]
    assert emitted_op == operation
    assert float(params["diameter"]) == pytest.approx(measured)
    accepted = validate(REGISTRY.get(operation).params, params)
    assert accepted.diameter == pytest.approx(measured)


def test_pressing_an_action_names_the_operation_and_its_feature(qt_app: QApplication) -> None:
    """Das Panel rechnet nichts — es nennt Operation und Werte, wie der
    Operationsdialog auch. ``at_feature`` steht dabei nicht als Feld: Welches
    Merkmal gemeint ist, sagt die Auswahl."""
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    seen: list[tuple[str, dict[str, object]]] = []
    panel.operationRequested.connect(lambda op, params: seen.append((op, params)))

    move = next(
        knopf
        for row in panel._built
        for knopf in row.findChildren(QPushButton)
        if knopf.text() == "Merkmal verschieben"
    )
    move.click()

    assert len(seen) == 1
    op, params = seen[0]
    assert op == "move_feature"
    assert params["at_feature"] == identifier
    assert set(params) >= {"at_feature", "x", "y", "z"}


def test_a_linked_countersink_is_named_before_the_bore_moves(qt_app: QApplication) -> None:
    """Das Panel sagt vor dem Klick, dass beide Teile des Hohlraums mitgehen."""
    bore = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 6.0,
            "depth": 10.0,
        },
    )
    sink = Feature(
        id="cone_1",
        kind="cone",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 5.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 12.0,
            "recess": True,
        },
    )
    linked = {bore.id: bore, sink.id: sink}
    panel = FeaturePanel()

    panel.show_feature(bore.id, bore, features=linked)

    move = next(
        row
        for row in panel._built
        if any(button.text() == "Merkmal verschieben" for button in row.findChildren(QPushButton))
    )
    text = " ".join(label.text() for label in move.findChildren(QLabel))
    assert "Bohrung und Senkung" in text
    assert "gemeinsam verschoben" in text


@pytest.mark.parametrize("pick_widening", [False, True])
def test_the_panel_uses_the_mesh_for_a_complete_cavity_chain(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, pick_widening: bool
) -> None:
    """Auch eine mehrteilige Senkung nennt vor dem Klick den gemeinsamen Weg.

    Die Kettenauskunft braucht das Netz für den gemeinsamen Randring. Bleibt es
    auf dem Weg vom Fenster zum Kern liegen, sieht das Panel drei passende
    Zahlen und verschiebt hinterher trotzdem nur die ausgewählte Fläche.
    """
    bore = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 6.0,
            "depth": 10.0,
        },
    )
    transition = Feature(
        id="cone_1",
        kind="cone",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 5.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 11.0,
            "recess": True,
        },
    )
    counterbore = Feature(
        id="hole_2",
        kind="hole",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 8.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 11.0,
            "depth": 6.0,
        },
    )
    linked = {feature.id: feature for feature in (bore, transition, counterbore)}
    body = plate()
    asked: list[tuple[Feature, object, MeshData]] = []

    from app.core.perceive import relations

    def chain_at(selected: Feature, available: object, mesh: MeshData) -> tuple[Feature, ...]:
        asked.append((selected, available, mesh))
        return bore, transition, counterbore

    monkeypatch.setattr(relations, "cavity_chain_at", chain_at)
    panel = FeaturePanel()

    selected = counterbore if pick_widening else bore
    panel.show_feature(selected.id, selected, features=linked, mesh=body)

    assert asked == [(selected, linked, body)], (
        "das Panel reicht Netz und Merkmale genau einmal durch"
    )
    if pick_widening:
        explanations = [widget.text() for widget in panel._built if isinstance(widget, QLabel)]
        assert any("Aufweitung misst 11,00 mm" in text for text in explanations)
        assert not any("Zu welcher Schraube" in text for text in explanations)
        assert any("engeren Bohrung" in text for text in explanations)
    move = next(
        row
        for row in panel._built
        if any(button.text() == "Merkmal verschieben" for button in row.findChildren(QPushButton))
    )
    text = " ".join(label.text() for label in move.findChildren(QLabel))
    assert "Bohrung und Senkung" in text
    assert "gemeinsam verschoben" in text


def test_a_handling_that_does_not_apply_brings_its_reason(qt_app: QApplication) -> None:
    """Was nicht geht, steht als Satz und nicht als graues Feld.

    Eine Kantenschleife ist ein Netzfehler und kein Körper; für sie gilt keine
    der Handlungen. Das Panel zeigt sie trotzdem — mit dem Grund, sonst rät
    der Kunde, ob sie fehlt oder vergessen wurde.
    """
    loop = Feature(
        id="edge_loop_1",
        kind="edge_loop",
        provenance="detected",
        params={"centre": (0.0, 0.0, 0.0), "open_edges": 4},
    )
    ungültig = [action for action in actions_for(loop) if action.op is None]
    assert ungültig, "ohne abgelehnte Handlungen prüft dieser Test nichts"
    assert all(str(action.reason).strip() for action in ungültig), "jede nennt ihren Grund"

    panel = FeaturePanel()
    panel.show_feature("edge_loop_1", loop)

    assert not buttons(panel), "keine Handlung ist anklickbar"
    reasons = [
        label for row in panel._built for label in row.findChildren(QLabel) if "—" in label.text()
    ]
    assert reasons and all(label.isEnabled() for label in reasons), "Erklärungen bleiben lesbar"
    texte = " ".join(
        label.text()
        for row in panel._built
        for label in row.findChildren(QWidget)
        if hasattr(label, "text")
    )
    for action in ungültig:
        assert str(action.reason) in texte, f"der Grund von {action.title} fehlt"


def test_a_changed_number_is_reported_before_it_is_done(qt_app: QApplication) -> None:
    """Robert am 03.09.2026: „eine live vorschau wäre noch gut."

    Das Panel meldet jede Änderung über ein **eigenes** Signal — getrennt vom
    Ausführen, damit ein Empfänger ohne Nachdenken weiß, ob er rechnen oder
    ändern soll. Ein Empfänger, der beim falschen Signal ausführt, schriebe
    einen Schritt, den niemand ausgelöst hat.
    """
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    gemeldet: list[tuple[str, dict[str, object]]] = []
    getan: list[tuple[str, dict[str, object]]] = []
    panel.valuesChanged.connect(lambda op, params: gemeldet.append((op, params)))
    panel.operationRequested.connect(lambda op, params: getan.append((op, params)))

    spin = next(
        widget for row in panel._built for widget in fields(row) if isinstance(widget, LengthSpin)
    )
    spin.set_value_mm(spin.value_mm() + 2.0)

    assert gemeldet, "die Änderung wurde nicht gemeldet"
    assert gemeldet[-1][1]["at_feature"] == identifier, "das Merkmal steht dabei"
    assert not getan, "gemeldet heißt nicht getan"


def test_a_length_is_reported_in_millimetres(qt_app: QApplication) -> None:
    """Qts ``valueChanged`` trägt den Anzeigewert; gemeldet wird der des Kerns.

    Wer das verwechselt, schickt bei Zoll 0,1969 statt 5 — derselbe Fehler,
    für den ``LengthSpin`` sein eigenes Signal hat.
    """
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    gemeldet: list[dict[str, object]] = []
    panel.valuesChanged.connect(lambda _op, params: gemeldet.append(params))

    spin = next(
        widget for row in panel._built for widget in fields(row) if isinstance(widget, LengthSpin)
    )
    spin.set_value_mm(12.5)

    assert gemeldet, "nichts gemeldet"
    werte = [wert for name, wert in gemeldet[-1].items() if name != "at_feature"]
    assert any(abs(float(wert) - 12.5) < 1e-6 for wert in werte if isinstance(wert, (int, float)))


def a_face() -> tuple[str, Feature]:
    found = features.detect(plate())
    return next((key, value) for key, value in found.items() if value.kind == "face")


def test_a_face_gets_the_catalogue_instead_of_a_dead_end(qt_app: QApplication) -> None:
    """An einer Fläche gilt keine der vier Handlungen — dort setzen dafür
    fünfundzwanzig Bausteine an.

    Vier graue Zeilen mit Begründung sind eine Sackgasse mit Erklärung; eine
    Sackgasse bleibt es trotzdem. Der Katalog lag hinter Rechtsklick und
    Untermenü.
    """
    identifier, feature = a_face()
    assert all(action.op is None for action in actions_for(feature)), "sonst prüft das nichts"

    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    gerufen: list[bool] = []
    panel.catalogRequested.connect(lambda: gerufen.append(True))

    knopf = next(widget for widget in panel._built if isinstance(widget, QPushButton))
    knopf.click()

    assert gerufen == [True], "der Knopf öffnet den Katalog"


def test_the_all_alike_box_appears_only_with_siblings(qt_app: QApplication) -> None:
    """„Auf alle 1 anwenden" wäre eine Frage ohne Unterschied."""
    identifier, feature = a_hole()
    allein = FeaturePanel()
    allein.show_feature(identifier, feature)
    assert not [
        widget
        for row in allein._built
        for widget in row.findChildren(QCheckBox)
        if "alle" in widget.text()
    ], "ohne Geschwister kein Haken"

    mit = FeaturePanel()
    from app.core.perceive.relations import alike_for_actions

    mesh = plate()
    available = features.detect(mesh)
    groups = alike_for_actions(
        (str(action.op) for action in actions_for(feature) if action.op),
        identifier,
        available,
        mesh,
    )
    mit.show_feature(identifier, feature, features=available, mesh=mesh)
    haken = [
        widget
        for row in mit._built
        for widget in row.findChildren(QCheckBox)
        if "alle" in widget.text()
    ]
    assert haken, "mit Geschwistern schon"
    expected = [len(group.members) for group in groups if len(group.members) > 1]
    assert len(haken) == len(expected)
    assert all(str(count) in box.text() for count, box in zip(expected, haken, strict=True))


def test_the_all_alike_box_names_every_sibling(qt_app: QApplication) -> None:
    """Gesetzt gilt die Handlung allen — und das Panel nennt sie einzeln,
    damit das Fenster eine Transaktion daraus machen kann (Regel 16)."""
    identifier, feature = a_hole()
    panel = FeaturePanel()
    mesh = plate()
    available = features.detect(mesh)
    panel.show_feature(identifier, feature, features=available, mesh=mesh)
    fuer_alle: list[tuple[str, dict[str, object], list[str]]] = []
    einzeln: list[tuple[str, dict[str, object]]] = []
    panel.operationRequestedForEach.connect(
        lambda op, params, ids: fuer_alle.append((op, params, ids))
    )
    panel.operationRequested.connect(lambda op, params: einzeln.append((op, params)))

    row = next(
        row for row in panel._built if row.findChildren(QCheckBox) and row.findChildren(QPushButton)
    )
    next(box for box in row.findChildren(QCheckBox) if "alle" in box.text()).setChecked(True)
    row.findChildren(QPushButton)[0].click()

    assert not einzeln, "gesetzt heißt: nicht nur dieses eine"
    assert fuer_alle, "die Sammelhandlung wurde nicht gemeldet"
    op, _params, ids = fuer_alle[-1]
    from app.core.perceive.relations import alike_for_action

    group = alike_for_action(op, identifier, available, mesh)
    assert ids[0] == identifier
    assert set(ids) == {member.target for member in group.members}


def spread(panel: FeaturePanel, scroller: QScrollArea, height: int) -> int:
    """Der Abstand zwischen dem obersten und dem untersten Knopf, in Punkten.

    Gemessen wird über den **Rollbereich**, weil die Anwendung es so baut: Er
    trägt ``setWidgetResizable(True)`` und zieht das Panel auf seine Höhe. Wer
    das Panel stattdessen selbst vergrößert, misst eine Lage, die kein Fenster
    herstellt — nachgemessen am 03.09.2026: Dort antwortet die Messung auf jede
    Höhe gleich, und der Fehler bliebe unsichtbar.
    """
    scroller.resize(320, height)
    QApplication.processEvents()
    layout = panel.layout()
    assert layout is not None
    layout.activate()
    lagen = [
        knopf.mapTo(panel, knopf.rect().topLeft()).y()
        for row in panel._built
        for knopf in row.findChildren(QPushButton)
    ]
    assert len(lagen) >= 2, "mehrere Handlungen, sonst misst der Test nichts"
    return max(lagen) - min(lagen)


def test_a_tall_window_does_not_pull_the_handlings_apart(qt_app: QApplication) -> None:
    """Der Restplatz gehört nach unten, nicht zwischen die Handlungen.

    Das Panel steckt in einem Rollbereich mit ``setWidgetResizable`` und wird
    damit auf dessen Höhe gezogen. Ohne eine Dehnung am Ende verteilt Qt den
    Überschuss auf die Zeilen: In einem 1255 Punkte hohen Fenster wollte der
    Inhalt 581 und stand am Ende 179 Punkte je Handlung auseinander. Vier
    Knöpfe mit so viel Luft dazwischen gehören sichtbar nicht mehr zu den
    Feldern über ihnen.

    Die Höhe ist der **Eingang** der Messung: Eine Antwort, die sich mit ihr
    ändert, ist der Fehler. Gegengeprüft, dass der Test ihn auch fängt — ohne
    die Dehnung wuchs die Spanne von 319 auf 725 Punkte.
    """
    key, feature = a_hole()
    panel = FeaturePanel()
    scroller = QScrollArea()
    scroller.setWidget(panel)
    scroller.setWidgetResizable(True)
    scroller.show()
    panel.show_feature(key, feature)
    QApplication.processEvents()
    wanted = panel.sizeHint().height()

    tight = spread(panel, scroller, wanted)
    roomy = spread(panel, scroller, wanted * 3)

    assert tight > 0, "die Knöpfe stehen überhaupt untereinander"
    assert roomy == tight, (
        f"die Handlungen wandern mit der Fensterhöhe auseinander: {tight} -> {roomy} Punkte"
    )


def two_holes() -> tuple[tuple[str, Feature], tuple[str, Feature]]:
    found = features.detect(plate())
    holes = [(key, value) for key, value in found.items() if value.kind == "hole"]
    assert len(holes) >= 2, "die Platte hat mehrere Bohrungen"
    return holes[0], holes[1]


def test_two_features_show_how_far_apart_they_stand(qt_app: QApplication) -> None:
    """Robert am 03.09.2026 zum Ausbau: der Abstand zweier Bohrungen ist das,
    was man vor jedem Druck wissen will.

    Bis dahin ging das nur über das Messwerkzeug und zwei Klicks ins Bild. Zwei
    Zeilen im Baum anzuklicken ist der kürzere Weg — markiert hat man sie
    ohnehin schon.
    """
    (first_id, first), (second_id, second) = two_holes()
    panel = FeaturePanel()
    panel.show_pair(first_id, first, second_id, second)

    texte = " ".join(
        label.text()
        for row in panel._built
        for label in row.findChildren(QLabel)
        if hasattr(label, "text")
    ) + " ".join(row.text() for row in panel._built if isinstance(row, QLabel))
    # Der Kundenname und nicht die rohe Kennung: „Bohrung 1", nicht „hole_1".
    from app.ui.labels import feature_name

    assert feature_name(first_id, first) in texte, "das erste steht dabei"
    assert feature_name(second_id, second) in texte, "und das zweite"

    here = first.params["centre"]
    there = second.params["centre"]
    erwartet = math.sqrt(sum((float(b) - float(a)) ** 2 for a, b in zip(here, there, strict=True)))
    # Die Zahl steht als Text mit Einheit; geprüft wird, dass sie vorkommt.
    assert (
        f"{erwartet:.2f}".replace(".", ",") in texte or f"{erwartet:.1f}".replace(".", ",") in texte
    ), texte


def test_a_pair_writes_no_step(qt_app: QApplication) -> None:
    """Eine Auskunft und keine Handlung (Regel 2): kein Knopf, kein Signal."""
    (first_id, first), (second_id, second) = two_holes()
    panel = FeaturePanel()
    getan: list[object] = []
    panel.operationRequested.connect(lambda *_a: getan.append(True))
    panel.operationRequestedForEach.connect(lambda *_a: getan.append(True))
    panel.show_pair(first_id, first, second_id, second)

    assert not [knopf for row in panel._built for knopf in row.findChildren(QPushButton)], (
        "kein Knopf unter einer Auskunft"
    )
    assert not getan


def test_a_pair_without_a_measured_centre_says_so(qt_app: QApplication) -> None:
    """Ein erfundener Abstand wäre schlimmer als keiner."""
    (first_id, first), _zweites = two_holes()
    ohne = Feature(
        id="edge_loop_1",
        kind="edge_loop",
        provenance="detected",
        params={"open_edges": 4},
    )
    panel = FeaturePanel()
    panel.show_pair(first_id, first, "edge_loop_1", ohne)

    texte = " ".join(row.text() for row in panel._built if isinstance(row, QLabel))
    assert "kein Abstand" in texte, texte


def test_a_hole_says_which_screw_fits(qt_app: QApplication) -> None:
    """Die Anwendung kennt die Antwort und sagte sie nur im Bohrdialog.

    „Ist das eine M5?" ist die Frage vor jedem Druck. Der Durchmesser steht im
    Panel ohnehin; ihn zu zeigen und die Normgröße zu verschweigen wäre die
    halbe Auskunft.
    """
    from app.core.scene.placement import bore_advice

    identifier, feature = a_hole()
    from app.ui.labels import localised

    diameter = float(feature.params["diameter"])
    erwartet, _choices = bore_advice(diameter, ask=False, measured=localised(f"{diameter:.2f}"))

    panel = FeaturePanel()
    panel.show_feature(identifier, feature)

    texte = " ".join(row.text() for row in panel._built if isinstance(row, QLabel))
    assert erwartet in texte, texte


def test_only_a_hole_gets_the_screw_line(qt_app: QApplication) -> None:
    """Die Gegenprobe: Eine Fläche hat keinen Durchmesser und keine Schraube.

    Ein Satz über Normgrößen an einer Fläche wäre eine Auskunft über etwas,
    das dort nicht gemessen wurde.
    """
    identifier, feature = a_face()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)

    texte = " ".join(row.text() for row in panel._built if isinstance(row, QLabel))
    assert "Bohrung misst" not in texte, texte


def test_the_same_refusal_is_said_once(qt_app: QApplication) -> None:
    """Fünf graue Zeilen mit demselben Satz sind eine Sackgasse mit Echo.

    **Gemessen am 04.09.2026 an Roberts Besenhalter.** Er trägt zehn Flächen
    und neun Verrundungen; wer eine Fläche anklickt, bekommt fünf Zeilen, und
    alle fünf sagen wörtlich „Eine Fläche gehört zur Oberfläche des Körpers …".
    Bei der Verrundung sind es vier von fünf. Jede Zeile für sich ist richtig —
    `actions_for` begründet zu Recht, warum eine Handlung fehlt, statt sie
    still wegzulassen —, und zusammen liest es sich als fünf Absagen auf
    dieselbe Frage.

    Gefaltet wird nur, was **denselben** Grund trägt, und weggelassen wird
    nichts: Die Zeile nennt weiter jede Handlung beim Namen. An der Verrundung
    bleiben deshalb drei Zeilen und nicht eine — ihre drei Gründe sind
    verschieden, und einer davon ist die Ankündigung, dass der Radius kommt.

    Was gilt, wird nie gefaltet: An einer Bohrung stehen alle fünf Handlungen
    einzeln, mit ihren Feldern und ihrem Knopf.
    """
    from app.core.perceive.actions import FeatureAction
    from app.ui.panels import _folded

    gleich = "Eine Fläche gehört zur Oberfläche des Körpers."
    anders = "Den Radius zu ändern ist noch nicht gebaut."
    actions = [
        FeatureAction(title="Merkmal verschieben", op=None, reason=gleich),
        FeatureAction(title="Merkmal ändern", op=None, reason=anders),
        FeatureAction(title="Merkmal drehen", op=None, reason=gleich),
        FeatureAction(title="Merkmal verdoppeln", op=None, reason=gleich),
    ]

    gefaltet = _folded(actions)

    assert len(gefaltet) == 2, [str(entry.title) for entry in gefaltet]
    assert str(gefaltet[0].title) == "Merkmal verschieben, drehen und verdoppeln", (
        "die drei mit demselben Grund stehen zusammen, ohne das Wort dreimal"
    )
    assert str(gefaltet[0].reason) == gleich
    # Die Reihenfolge des Kerns bleibt: Die zusammengelegte Zeile steht dort,
    # wo die erste ihrer Handlungen stand.
    assert str(gefaltet[1].title) == "Merkmal ändern"
    assert str(gefaltet[1].reason) == anders


def test_what_works_is_never_folded_away(qt_app: QApplication) -> None:
    """Eine Handlung mit Feldern und Knopf teilt keine Zeile mit einer anderen."""
    from app.core.perceive.actions import FeatureAction
    from app.ui.panels import _folded

    actions = [
        FeatureAction(title="Bohrung ändern", op="resize_hole"),
        FeatureAction(title="Merkmal verschieben", op="move_feature"),
        FeatureAction(title="Merkmal drehen", op=None, reason="geht hier nicht"),
        FeatureAction(title="Merkmal verdoppeln", op=None, reason="geht hier nicht"),
    ]

    gefaltet = _folded(actions)

    assert [entry.op for entry in gefaltet] == ["resize_hole", "move_feature", None]


def test_every_field_group_says_what_it_belongs_to(qt_app: QApplication) -> None:
    """Zweimal X/Y/Z untereinander, und nur der Knopf darunter sagt, welche.

    **Der Fall.** An einer Bohrung stehen vier Gruppen untereinander: X/Y/Z für
    *Verschieben*, ein Durchmesser für *Ändern*, Achse und Winkel für *Drehen*,
    wieder X/Y/Z für *Verdoppeln*. Benannt wurden sie nur vom Knopf **unter**
    ihnen, und das trägt genau einmal — beim ersten Feldpaar liest man die
    Bedeutung noch von unten nach, beim zweiten nicht mehr (Alexanders
    Bildschirmfoto, gemessen von 3d-druck-4d am 04.09.2026).

    Geprüft wird an der Reihenfolge im Layout: Vor den Feldern muss eine
    Beschriftung mit dem Titel der Handlung stehen, und zwar **über** ihnen und
    nicht nur als Knopf darunter.
    """
    from app.core.perceive.actions import ActionField, FeatureAction
    from app.ui.panels import FeaturePanel

    panel = FeaturePanel()
    try:
        action = FeatureAction(
            title="Merkmal verschieben",
            op="move_feature",
            fields=(
                ActionField(name="x", label="X", unit="mm", value=1.0, kind="length"),
                ActionField(name="y", label="Y", unit="mm", value=2.0, kind="length"),
            ),
        )

        row = panel._build_action(action)
        beschriftungen = [
            kind.text() for kind in row.findChildren(QLabel) if kind.text() == "Merkmal verschieben"
        ]
        assert beschriftungen, (
            "über den Feldern steht kein Titel — dann sagt nur der Knopf darunter, wozu sie gehören"
        )

        # Und sie steht **vor** den Feldern, nicht irgendwo im Kasten.
        layout = row.layout()
        erstes = layout.itemAt(0).widget()
        assert isinstance(erstes, QLabel) and erstes.text() == "Merkmal verschieben", (
            f"zuerst steht {erstes!r} statt der Überschrift"
        )
    finally:
        panel.deleteLater()


def test_a_nearly_nominal_bore_explains_why_it_is_not_assigned(qt_app: QApplication) -> None:
    """Gleich gerundete 2-mm-Maße dürfen keine unerklärlich verschiedenen Normaussagen tragen."""
    from dataclasses import replace

    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, replace(feature, params={**feature.params, "diameter": 1.9999}))
    text = " ".join(label.text() for label in panel.findChildren(QLabel))
    assert "knapp unter dem Nennmaß von M2" in text
    assert "Zu welcher Schraube" not in text


def test_every_group_literal_of_the_core_has_a_sentence_in_the_panel() -> None:
    """Ein neuer Nachweis oder Grund im Kern war sonst ein ``KeyError`` in der Auswahl."""
    from typing import get_args

    from app.core.perceive.relations import (
        FeatureActionGroup,
        FeatureGroupEvidence,
        FeatureGroupMember,
        FeatureGroupReason,
        FeatureGroupUncertainty,
    )
    from app.ui.panels import _feature_group_note, _group_evidence_texts, _group_reason_texts

    assert set(get_args(FeatureGroupEvidence)) == set(_group_evidence_texts())
    assert set(get_args(FeatureGroupReason)) == set(_group_reason_texts())
    group = FeatureActionGroup(
        id="g",
        action="resize_feature",
        selected="hole_1",
        members=(
            FeatureGroupMember(target="hole_1", scope=("hole_1",)),
            FeatureGroupMember(target="hole_2", scope=("hole_2",)),
        ),
        evidence=tuple(get_args(FeatureGroupEvidence)),
        uncertain=tuple(
            FeatureGroupUncertainty(feature_ids=("hole_9",), reason=reason)
            for reason in get_args(FeatureGroupReason)
        ),
    )
    note = _feature_group_note(group)
    for text in (*_group_evidence_texts().values(), *_group_reason_texts().values()):
        assert str(text) in note


def test_the_fit_hint_needs_a_second_body(qt_app: QApplication) -> None:
    """Im Einzelkörperprojekt gibt es kein Gegenstück — der Satz dazu entfällt.

    Bis zum 06.09.2026 stand er unter jedem Merkmal, auch wenn der Klick im
    Objektbaum, zu dem er riet, nichts hätte finden können.
    """
    from PySide6.QtWidgets import QLabel

    def hints(panel: FeaturePanel) -> list[str]:
        return [
            label.text()
            for label in panel.findChildren(QLabel)
            if label.text().startswith("Für eine Passung")
        ]

    identifier, feature = a_hole()
    single = FeaturePanel()
    single.show_feature(identifier, feature, alone=True)
    assert hints(single) == [], "ohne zweiten Körper gibt es kein Gegenstück"

    several = FeaturePanel()
    several.show_feature(identifier, feature)
    assert len(hints(several)) == 1
