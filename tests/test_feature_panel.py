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
from typing import Any

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

from app.core.bootstrap import load_operations
from app.core.geom.mesh import MeshData, read_mesh
from app.core.perceive import actions, features
from app.core.perceive.actions import EDGE_OPERATIONS, actions_for
from app.core.registry import REGISTRY, validate
from app.core.types import Feature
from app.core.units import LengthUnit
from app.ui.labels import LengthSpin, NumberSpin
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
    """Die Handlungen, die das Panel anbietet.

    Seit dem 10.09.2026 steht kein Knopf mehr in jeder Zeile: Einer unten führt
    die aus, an der zuletzt jemand etwas angefasst hat. Was angeboten wird,
    steht deshalb in ``_runs`` und nicht mehr im Widgetbaum.
    """
    return [entry.title for entry in panel._runs.values()]


def press(panel: FeaturePanel, title: str) -> None:
    """Eine Handlung scharfschalten und den Knopf unten wirklich drücken.

    Der Weg der Oberfläche in zwei Schritten: ``_arm`` ist die Methode, die
    eine Feldberührung ruft, und danach wird der echte Knopf geklickt — nicht
    die Funktion dahinter (`.claude/rules/tests.md`, „Am Weg vorbei").
    """
    for op, entry in panel._runs.items():
        if entry.title == title:
            panel._arm(op)
            panel._apply.click()
            return
    raise AssertionError(f"keine Handlung {title!r} — angeboten sind {buttons(panel)}")


def spoken(row: QWidget) -> str:
    """Was diese Zeile sagt — sichtbar und hinter ihrem Info-Zeichen.

    Seit dem 10.09.2026 steht die Erklärung im Tooltip der Überschrift statt
    als Absatz darunter (Robert: „in einen tooltipp … mit einem i für infos").
    Ein Test, der nur ``text()`` liest, misst seither die halbe Zeile.
    """
    stuecke: list[str] = []
    for widget in row.findChildren(QWidget):
        for teil in (
            getattr(widget, "text", lambda: "")(),
            widget.toolTip(),
            widget.accessibleDescription(),
        ):
            if teil and teil not in stuecke:
                stuecke.append(teil)
    return " ".join(stuecke)


def row_of(panel: FeaturePanel, title: str) -> QWidget:
    """Die Zeile, deren Überschrift diese Handlung nennt.

    Bis zum 10.09.2026 fand man sie an ihrem Knopf; den gibt es nicht mehr,
    und die Überschrift trug den Titel schon immer daneben.
    """
    for row in panel._built:
        if any(label.text() == title for label in row.findChildren(QLabel)):
            return row
    raise AssertionError(f"keine Zeile für {title!r} — angeboten sind {buttons(panel)}")


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


def test_every_field_of_a_handling_says_what_it_is(qt_app: QApplication) -> None:
    """Ein Feld ohne Namen ist für einen Bildschirmleser ein leeres Kästchen.

    Gemessen am 09.09.2026 an einer gewählten Bohrung: zehn Bedienelemente,
    alle mit leerem ``accessibleName`` — darunter zweimal X, Y und Z, einmal
    für *Merkmal verschieben* und einmal für *verdoppeln*. Vorgelesen wurde
    „Drehfeld, 0,00", sechsmal hintereinander; auseinanderhalten ließ sich das
    nur, wer die Beschriftungen daneben **sieht**.

    Die Zusage steht in §19.1 und in der Regel „jedes Feld sagt, was es tut" —
    sie galt bisher dem Operationsdialog und den Druckeinstellungen, und die
    Schnellbearbeitung am Merkmal war die dritte Stelle, an der Felder stehen.

    **Der Name trägt die Handlung mit**, weil „Durchmesser" allein nicht sagt,
    welcher: An einer Bohrung stehen vier Handlungen mit je eigenen Feldern.
    """
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)

    felder = [
        widget
        for widget in panel.findChildren(QWidget)
        if isinstance(widget, QCheckBox | QComboBox | LengthSpin | NumberSpin)
        and widget.isVisibleTo(panel)
    ]
    assert felder, "ohne Felder prüft der Test nichts"
    ohne = [type(widget).__name__ for widget in felder if not widget.accessibleName()]
    assert not ohne, f"{len(ohne)} von {len(felder)} Feldern ohne Namen: {ohne}"

    # **Und der Name unterscheidet die Handlungen.** Ohne sie stünde „X"
    # dreimal doppelt da — der Fall, an dem der Befund aufgefallen ist.
    namen = [widget.accessibleName() for widget in felder]
    assert len(set(namen)) == len(namen), f"zwei Felder heißen gleich: {namen}"


def test_fieldless_remove_action_has_a_visible_working_button(qt_app: QApplication) -> None:
    """Die gebaute Oberfläche macht die feldlose Handlung tatsächlich erreichbar."""
    identifier, feature = a_hole()
    panel = FeaturePanel()
    seen = []
    panel.operationRequested.connect(lambda *args: seen.append(args))
    panel.show_feature(identifier, feature)
    buttons = [
        button
        for button in panel.findChildren(QPushButton)
        if button.isVisibleTo(panel) and button.text() == "Merkmal entfernen"
    ]
    assert len(buttons) == 1
    buttons[0].click()
    assert seen and seen[0][0] == "remove_feature"


def test_focusing_a_field_names_the_action_above_apply(qt_app: QApplication) -> None:
    """Ein Fokuswechsel wählt die Handlung, ohne eine Maßänderung zu verlangen."""
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QFocusEvent

    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    editor = next(
        widget
        for widget in panel.findChildren(LengthSpin)
        if widget.property("handlingKey") != panel._armed
    )
    qt_app.sendEvent(editor, QFocusEvent(QEvent.Type.FocusIn))
    assert panel._armed == editor.property("handlingKey")
    assert panel._armed_title.isVisibleTo(panel)
    assert panel._armed_title.text() == panel._apply.accessibleName()


def test_the_panel_offers_what_the_core_says_and_nothing_else(qt_app: QApplication) -> None:
    """Die Zeilen kommen aus ``actions_for`` — eine Stelle, nicht zwei.

    Verglichen wird gegen die Auskunft selbst und nicht gegen eine Liste im
    Test: Sobald der Kern eine Handlung dazubekommt, wächst das Panel mit, und
    dieser Test bleibt richtig.

    **Zwei Knöpfe je Handlung, wo sie im Bild einzustellen ist** (10.09.2026):
    Der erste führt aus, der zweite öffnet die Flächenplatzierung mit ihren
    Maßlinien. Welche das sind, sagt wieder der Kern
    (``placement.supports_surface_placement``) und keine Liste hier.
    """
    from app.core.scene import placement
    from app.i18n import tr

    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)

    # **Je Handlung genau ein Knopf, und keiner mehr.** Ein zweiter *Im Bild
    # einstellen …* stand bis zum 10.09.2026 an jeder Handlung, die auf einer
    # Fläche sitzt — an einer Bohrung also mehrfach untereinander —, und was
    # er anbot, geschieht seither von selbst: Ein angeklicktes Loch bringt
    # seine Maße in die Szene (Robert: „können wir uns den button im bild
    # einstellen sparen, da wir das sofort können … steht mehrmals da").
    #
    # Die Gegenprobe steht darunter: Mindestens eine dieser Handlungen sitzt
    # auf einer Fläche, sonst wäre die Zusage leer und der Test grün, ohne
    # etwas zu messen.
    expected: list[str] = []
    auf_einer_flaeche = 0
    for action in actions_for(feature):
        if action.op is None:
            continue
        expected.append(str(action.title))
        if REGISTRY.has(str(action.op)) and placement.supports_surface_placement(
            REGISTRY.get(str(action.op))
        ):
            auf_einer_flaeche += 1
    assert expected, "ohne Handlungen prüft dieser Test nichts"
    assert auf_einer_flaeche, "an einer Bohrung sitzt mindestens eine Handlung auf einer Fläche"
    assert buttons(panel) == expected
    assert str(tr("Im Bild einstellen …")) not in buttons(panel)


def test_every_number_starts_on_what_was_measured(qt_app: QApplication) -> None:
    """Roberts „sinnvolle Einstellungen": Die Vorgabe jedes Feldes ist der
    heutige Wert, damit der Kunde die eine Zahl ändert, die er meint."""
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)

    centre = feature.params["centre"]
    move = row_of(panel, "Merkmal verschieben")
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
    row = row_of(panel, str(action.title))
    spin = next(widget for widget in fields(row) if isinstance(widget, LengthSpin))
    assert spin.isVisibleTo(panel), "der gemessene Durchmesser steht nicht sichtbar im Panel"
    assert spin.value_mm() == pytest.approx(measured), "das Panel klemmt den Messwert"

    # **Beide Wege zählen.** *Bohrung ändern* führt seit dem 10.09.2026 ins
    # Bild statt sofort auszuführen (``LEADS_INTO_THE_VIEW``); was der Knopf
    # dabei weiterreicht, ist dieselbe Wertetabelle — und genau die prüft
    # dieser Test.
    emitted: list[tuple[str, dict[str, object]]] = []
    panel.operationRequested.connect(lambda op, params: emitted.append((op, params)))
    panel.inViewRequested.connect(lambda op, params: emitted.append((op, params)))
    press(panel, str(action.title))

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

    press(panel, "Merkmal verschieben")

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
        if any(label.text() == "Merkmal verschieben" for label in row.findChildren(QLabel))
    )
    text = spoken(move)
    assert "3 Abschnitte dieser Öffnung" in text
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
        if any(label.text() == "Merkmal verschieben" for label in row.findChildren(QLabel))
    )
    text = spoken(move)
    assert "2 Abschnitte dieser Öffnung" in text
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
    # **Ein Haken für alle Handlungen, unten über dem Knopf** (10.09.2026). Er
    # gehört der, die gerade scharf ist; welche Zahl er nennt, wechselt mit ihr.
    mengen = {group.action: len(group.members) for group in groups}
    with_group = [
        schluessel for schluessel, eintrag in mit._runs.items() if mengen.get(eintrag.op, 0) > 1
    ]
    assert with_group, "mit Geschwistern schon"
    for schluessel in with_group:
        mit._arm(schluessel)
        assert mit._every.isVisibleTo(mit), f"{schluessel} hat Geschwister und keinen Haken"
        assert str(mengen[mit._runs[schluessel].op]) in mit._every.text()


def test_the_group_evidence_stands_once_and_not_at_every_handling(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Vier Handlungen an derselben Kette tragen dieselben Nachweise — der
    Absatz dazu steht einmal.

    Befund Robert, 07.09.2026, an einer Senkung in ``weg2-halter-konstruieren``:
    „im merkmalpanel ist zu viel text." Gezählt waren es vier Absätze
    untereinander, wörtlich gleich, einer je Handlung. Die Nachweise gehören
    der Gruppe und nicht der Handlung; dasselbe Muster wie ``_folded`` für den
    Grund einer Absage.

    **Die Auskunft geht dabei nicht verloren**, sie wiederholt sich nur nicht:
    Ab der zweiten Handlung trägt der Haken sie, denn er ist das Feld, über das
    sie entscheidet.

    **Und sie verdrängt die Rücknahmezusage nicht.** Der Nachweis ersetzte die
    Statuszeile des Hakens, und damit stand ab der zweiten Handlung nichts mehr
    von Strg+Z dort — zwei gleich beschriftete Haken sagten im selben Panel
    Verschiedenes. Genau diese Zusage erlaubt den Verzicht auf eine Rückfrage
    (Regel 19), also wird sie hier für **jeden** Haken geprüft.
    """
    from app.core.perceive import relations
    from app.core.perceive.relations import (
        FeatureActionGroup,
        FeatureGroupMember,
    )

    identifier, feature = a_hole()
    mesh = plate()
    available = features.detect(mesh)

    def same_group_everywhere(
        ops: object, selected: str, found: object, body: object
    ) -> tuple[FeatureActionGroup, ...]:
        """Je Handlung eine Gruppe, und alle mit denselben Nachweisen.

        Genau die Lage des Befunds: Wer eine Bohrungskette versetzt, dreht,
        ändert und verdoppelt, bekommt viermal dieselbe Begründung.
        """
        return tuple(
            FeatureActionGroup(
                id=f"g-{name}",
                action=name,
                selected=selected,
                members=(
                    FeatureGroupMember(target=selected, scope=(selected,)),
                    FeatureGroupMember(target="hole_other", scope=("hole_other",)),
                ),
                evidence=("parallel_axes", "shared_boundary_role"),
            )
            for name in ops
        )

    monkeypatch.setattr(relations, "alike_for_actions", same_group_everywhere)
    panel = FeaturePanel()
    panel.show_feature(identifier, feature, features=available, mesh=mesh)

    mit_gruppe = [schluessel for schluessel, eintrag in panel._runs.items() if eintrag.members > 1]
    assert len(mit_gruppe) > 1, (
        "der Fall braucht mehrere Handlungen mit Gruppe, sonst prüft er nichts"
    )

    said = next(iter(panel._said_notes))
    # **Er steht einmal, und seit dem 10.09.2026 hinter einem Info-Zeichen.**
    # Gezählt wird deshalb nicht mehr über ``text()``, sondern über die
    # Erklärungen, die das Panel führt — eine je Zeile, die eine hat.
    absaetze = [gathered for gathered in panel._explanations.values() if said in gathered]
    assert len(absaetze) == 1, f"der Absatz steht {len(absaetze)}-mal statt einmal"

    # **Und die Rücknahmezusage steht an jedem Stand des einen Hakens.** Sie
    # ist der Grund, aus dem es keine Rückfrage gibt (Regel 19).
    for schluessel in mit_gruppe:
        panel._arm(schluessel)
        assert "Strg+Z" in panel._every.statusTip(), f"{schluessel} ohne Rücknahmezusage"


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

    # Der Weg der Oberfläche: Handlung scharfschalten, den Haken unten setzen,
    # dann übernehmen — er gehört seit dem 10.09.2026 dem Knopf und nicht mehr
    # der Zeile.
    schluessel = next(
        key for key, eintrag in panel._runs.items() if eintrag.title == "Merkmal verschieben"
    )
    panel._arm(schluessel)
    assert panel._every.isVisibleTo(panel), "die Bohrung hat gleichartige Geschwister"
    panel._every.setChecked(True)
    panel._apply.click()

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
    # **Gemessen an den Zeilen, nicht an ihren Knöpfen.** Die gibt es seit dem
    # 10.09.2026 nur noch einmal, unten; auseinandergezogen würden aber die
    # Handlungen, und das sind die Zeilen. Die Frage ist dieselbe geblieben.
    lagen = [row.mapTo(panel, row.rect().topLeft()).y() for row in panel._built]
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

    assert tight > 0, "die Handlungen stehen überhaupt untereinander"
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
            "über den Feldern steht kein Titel — dann sagt nichts mehr, wozu sie gehören"
        )

        # Und sie steht **vor** den Feldern, nicht irgendwo im Kasten. Seit dem
        # 10.09.2026 teilt sie ihre Zeile mit dem Info-Zeichen, steht also in
        # einem Layout und nicht mehr unmittelbar im Kasten.
        layout = row.layout()
        kopf = layout.itemAt(0).layout()
        assert kopf is not None, "die Überschrift steht nicht mehr zuerst"
        erstes = kopf.itemAt(0).widget()
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


def test_a_part_shows_its_step_and_writes_back_into_it(qt_app: QApplication) -> None:
    """Das Panel zeigt den Baustein und ändert **seinen Schritt**, nicht mehr.

    Der ganze Weg an einem Stück: die drei Handlungen aus dem Kern, ihre
    Felder mit den Werten des Schritts, und was der Knopf meldet. Geprüft wird
    das Signal und nicht die Sitzung — welcher Schritt mit welchen Werten
    gemeint ist, entscheidet sich hier; dass ``change_params`` daraus eine
    Transaktion macht, ist die Zusage des Verlaufs und hat dort ihre Tests.

    **``stepChangeRequested`` und nicht ``operationRequested``** ist der Kern
    der Sache: Über den zweiten stünde nach jeder Maßkorrektur ein weiteres
    Schlüsselloch im Verlauf, an derselben Stelle über dem alten.
    """
    from types import SimpleNamespace

    from app.core.bootstrap import load_operations
    from app.ui.panels import FeaturePanel

    load_operations()
    spec = REGISTRY.get("insert_keyhole")
    step = SimpleNamespace(id=7, op="insert_keyhole", params={"size": "M5", "drop": 9.0, "x": 4.0})

    panel = FeaturePanel()
    changed: list[tuple[int, dict]] = []
    removed: list[int] = []
    panel.stepChangeRequested.connect(lambda op_id, params: changed.append((op_id, params)))
    panel.stepRemoveRequested.connect(removed.append)
    try:
        panel.show_part(step, spec)

        titles = buttons(panel)
        assert titles == ["Maße ändern", "Baustein verschieben", "Baustein entfernen"], titles

        # **Der zweite Knopf schreibt nur die Lage.** Wer beim Verschieben die
        # Maße mitschickte, setzte die Schraubengröße auf ihre Vorgabe zurück.
        press(panel, "Baustein verschieben")
        assert len(changed) == 1, "ein Zug, eine Meldung"
        op_id, params = changed[0]
        assert op_id == 7, "der Schritt, der den Baustein gesetzt hat"
        assert set(params) == {"x", "y", "z"}, params
        assert params["x"] == pytest.approx(4.0), "der Wert aus dem Schritt steht im Feld"

        # Und Entfernen fragt nichts und nennt nur den Schritt.
        press(panel, "Baustein entfernen")
        assert removed == [7]
        assert len(changed) == 1, "Entfernen ist keine Wertänderung"
    finally:
        panel.deleteLater()


def test_a_part_step_keeps_the_values_it_was_not_asked_about(qt_app: QApplication) -> None:
    """Verschieben lässt die Maße stehen — geprüft am Fenster, nicht am Panel.

    Das Panel meldet je Handlung ihren Ausschnitt; erst das Fenster legt ihn
    über die Werte, die im Schritt stehen. Ohne diesen Schritt verlöre ein Zug
    an der Lage die Schraubengröße, und das fiele erst beim nächsten Öffnen
    auf.
    """
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow

    schritt = SimpleNamespace(id=3, op="insert_keyhole", params={"size": "M5", "drop": 9.0})
    geschrieben: list[tuple[int, dict]] = []

    fenster = SimpleNamespace(
        session=SimpleNamespace(
            project=SimpleNamespace(document=SimpleNamespace(ops=[schritt])),
            change_params=lambda op_id, params: geschrieben.append((op_id, params)),
        )
    )
    MainWindow._change_part_step(fenster, 3, {"x": 12.0})

    assert geschrieben == [(3, {"size": "M5", "drop": 9.0, "x": 12.0})], geschrieben


def test_removing_a_part_uses_the_history_dependency_confirmation(qt_app: QApplication) -> None:
    """Auch vom Bausteinknopf aus wird die Folgeauskunft des Verlaufs benutzt."""
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow

    called = []
    said = []
    document = SimpleNamespace(ops=[SimpleNamespace(id=12)])
    window = SimpleNamespace(
        remove_history_operations=lambda ids: called.append(ids),
        session=SimpleNamespace(project=SimpleNamespace(document=document)),
        statusBar=lambda: SimpleNamespace(showMessage=lambda text: said.append(text)),
    )
    MainWindow._remove_part_step(window, 12)
    assert called == [[12]]
    document.ops = []
    MainWindow._remove_part_step(window, 12)
    assert called == [[12]]
    assert said and "nicht mehr vorhanden" in said[0]


def test_only_a_part_step_answers_for_the_feature_that_came_from_it() -> None:
    """Wer den Baustein erkennt, entscheidet, was rechts steht — also wird er geprüft.

    ``part_actions`` hat seinen eigenen Test; hier geht es um die Frage davor:
    **gehört dieses Merkmal zu einem Baustein?** Sie fällt an zwei Stellen —
    beim einzeln angeklickten Merkmal (``part_step_of``) und bei der Auswahl
    im Baum, wo ein Dach seine zwölf Kinder mitwählt (``_common_part_step``).

    Vier Fälle, und die letzten beiden sind die, an denen eine bequemere
    Fassung fiele:

    * Ein Merkmal aus dem Bausteinschritt → der Schritt.
    * Ein **erkanntes** Merkmal ohne Provenienz → nichts; zu ihm gibt es
      keinen Schritt, den man ändern könnte.
    * Ein Merkmal aus ``drill_hole`` → nichts. Auch das trägt Provenienz und
      ist kein Baustein; deshalb hängt die Frage an der Kategorie ``parts``
      und nicht an einem Namen wie ``insert_*``.
    * Eine Auswahl aus **zwei** Schritten → nichts. Wer eine Bohrung des
      Schlüssellochs und eine fremde daneben markiert, meint zwei Dinge.
    """
    from types import SimpleNamespace

    from app.core.bootstrap import load_operations
    from app.ui.main_window import MainWindow

    load_operations()

    def fenster(*schritte: object) -> Any:
        objekt = SimpleNamespace(
            features={
                "keyhole_bore_1": Feature(
                    id="keyhole_bore_1",
                    kind="hole",
                    provenance="generated",
                    params={},
                    created_by=2,
                ),
                "hole_1": Feature(
                    id="hole_1",
                    kind="hole",
                    provenance="generated",
                    params={},
                    created_by=3,
                ),
                "face_1": Feature(
                    id="face_1",
                    kind="face",
                    provenance="detected",
                    params={},
                    created_by=None,
                ),
            }
        )
        window = SimpleNamespace(
            session=SimpleNamespace(
                project=SimpleNamespace(document=SimpleNamespace(ops=list(schritte))),
                last_result=SimpleNamespace(scene=SimpleNamespace(objects={"obj_1": objekt})),
            )
        )
        # ``_common_part_step`` fragt über ``self`` weiter — das Doppel muss
        # denselben Weg anbieten, sonst prüft der Test nur die halbe Kette.
        window.part_step_of = lambda feature: MainWindow.part_step_of(window, feature)
        return window

    baustein = SimpleNamespace(id=2, op="insert_keyhole", params={"size": "M4"})
    bohrung = SimpleNamespace(id=3, op="drill_hole", params={"diameter": 5.0})
    window = fenster(baustein, bohrung)
    features = window.session.last_result.scene.objects["obj_1"].features

    step = MainWindow.part_step_of(window, features["keyhole_bore_1"])
    assert step is not None and step[0] is baustein, (
        "das Merkmal des Bausteins nennt seinen Schritt"
    )
    assert step[1].name == "insert_keyhole"

    assert MainWindow.part_step_of(window, features["face_1"]) is None, (
        "ein erkanntes Merkmal trägt keine Provenienz und keinen änderbaren Schritt"
    )
    assert MainWindow.part_step_of(window, features["hole_1"]) is None, (
        "drill_hole trägt Provenienz und ist trotzdem kein Baustein — die Kategorie "
        "entscheidet, nicht der Name"
    )

    # Und ein Schritt, den es im Dokument nicht mehr gibt, ist keiner.
    assert MainWindow.part_step_of(fenster(bohrung), features["keyhole_bore_1"]) is None

    # Der Baum: Ein Dach wählt seine Kinder mit, eine gemischte Auswahl nicht.
    zusammen = [("obj_1", "keyhole_bore_1"), ("obj_1", "keyhole_bore_1")]
    gemischt = [("obj_1", "keyhole_bore_1"), ("obj_1", "hole_1")]
    gemeinsam = MainWindow._common_part_step(window, zusammen)
    assert gemeinsam is not None and gemeinsam[0] is baustein
    assert MainWindow._common_part_step(window, gemischt) is None, (
        "zwei Schritte sind zwei Dinge und kein Baustein"
    )
    assert MainWindow._common_part_step(window, []) is None


def test_the_live_preview_of_a_part_changes_its_step(qt_app: QApplication) -> None:
    """Beim Tippen wird der Schritt gerechnet, nicht ein zweiter Baustein daneben.

    Der Knopf machte diesen Unterschied schon (``stepChangeRequested``), die
    **Vorschau** ging noch den alten Weg: Sie baute aus denselben Werten einen
    Entwurf, und dem fehlen Ort und Ansatzpunkt. Beim Drehen an der
    Schraubengröße erschien damit ein zweites Schlüsselloch an der
    Vorgabelage, während das echte unverändert danebenstand.

    Beide Richtungen, denn eine allein wäre auch dann grün, wenn die Weiche
    immer dasselbe täte.
    """
    from types import SimpleNamespace

    from app.ui.main_window import MainWindow

    gerufen: list[dict[str, Any]] = []
    panel = SimpleNamespace(shown_part_step=lambda: 5)
    fenster = SimpleNamespace(
        _feature_pending=("insert_keyhole", {"size": "M5"}),
        feature_panel=panel,
        _show_preview=object(),
        object_tree=SimpleNamespace(selected=lambda: "obj_1"),
        session=SimpleNamespace(
            preview_async=lambda then, drafts=None, **rest: gerufen.append(
                {"drafts": drafts, **rest}
            )
        ),
    )

    MainWindow._preview_feature_change(fenster)
    assert gerufen == [{"drafts": None, "change_op": 5, "change_values": {"size": "M5"}}], gerufen

    # Und ohne Baustein bleibt es beim Entwurf neben der Szene.
    gerufen.clear()
    panel.shown_part_step = lambda: None
    fenster._feature_pending = ("resize_hole", {"diameter": 6.0})
    MainWindow._preview_feature_change(fenster)
    assert len(gerufen) == 1 and gerufen[0]["drafts"] is not None, gerufen
    assert "change_op" not in gerufen[0]


def test_the_edge_panel_carries_the_key_the_customer_never_sees(qt_app: QApplication) -> None:
    """Eine angeklickte Kante bietet Verrunden, Fasen und den Wulst an.

    Die zwei Werte, die der Kunde **nicht** eingibt, reisen als ``fixed``
    mit: Die Auswahl ``named`` hat er mit dem Klick beantwortet, und der
    Schlüssel ist eine Kennung aus sechs Zahlen und keine Beschriftung
    (§2.4). Stünden sie als Felder da, wäre das Fenster eine Abschrift des
    Dialogs, den es ersetzt.

    **Die Gegenprobe zum Schlüssel steht im Test selbst:** Er darf in keinem
    sichtbaren Text auftauchen. Ohne diese Zeile wäre ein Panel grün, das
    ``e:-20.00,0.00,20.00:0.000,1.000,0.000`` als Beschriftung zeigt.
    """
    from app.core.bootstrap import load_operations

    # Ohne geladenes Register ist die Grundmenge leer, und der Test wäre grün,
    # ohne eine Handlung gesehen zu haben.
    load_operations()
    if not REGISTRY.has("fillet_edges"):
        pytest.skip("OpenCASCADE is an optional dependency")
    schluessel = "e:-20.00,0.00,20.00:0.000,1.000,0.000"
    panel = FeaturePanel()
    gerufen: list[tuple[str, dict[str, Any]]] = []
    panel.operationRequested.connect(lambda op, werte: gerufen.append((op, dict(werte))))

    panel.show_edge(schluessel, "Waagerecht · 30,00 mm · x -20,00, y 0,00")

    knoepfe = buttons(panel)
    # **Die Menge kommt aus dem Register und steht nicht hier als Liste.**
    # Am 10.09.2026 kam *Wulst anlegen* als dritte Handlung dazu, und ein Test
    # mit zwei aufgezählten Titeln wäre daran rot geworden, ohne dass etwas
    # kaputt war — er hätte die Gewohnheit geprüft und nicht die Zusage
    # (`.claude/rules/tests.md`, „Prüft dieser Test eine Zusage?").
    assert set(knoepfe) == {str(REGISTRY.get(name).title) for name, _feld in EDGE_OPERATIONS}, (
        "an einer Kante steht genau, was EDGE_OPERATIONS nennt"
    )

    for beschriftung in panel.findChildren(QLabel):
        assert schluessel not in beschriftung.text(), "der Schlüssel ist keine Beschriftung"

    press(panel, str(REGISTRY.get("fillet_edges").title))

    assert len(gerufen) == 1
    op, werte = gerufen[0]
    assert op == "fillet_edges"
    assert werte["edges"] == "named", "der Klick hat die Auswahl beantwortet"
    assert werte["edge_keys"] == schluessel
    # Und der Radius kommt aus dem Register, nicht aus einer Zahl hier.
    vorgabe = next(e for e in REGISTRY.get("fillet_edges").params.spec() if e.name == "radius")
    assert werte["radius"] == pytest.approx(float(vorgabe.default))


def test_no_feature_kind_falls_back_to_the_sentence_that_says_nothing() -> None:
    """Jede erkennbare Art begründet ihre Absagen selbst (Regel 17).

    Der Fallback ``_UNKNOWN_KIND`` — „Für diese Art von Merkmal gibt es noch
    keine Handlung." — ist genau das Ende ohne Weg nach vorn, das Regel 17
    verbietet. Bis zum 10.09.2026 stand er an **jeder** der fünf Zeilen eines
    Gewindes, obwohl es zwei Wege gibt: den Schritt des Bausteins, aus dem es
    stammt (§21.2), und bei einem eingelesenen Modell das Verschließen.

    Gefunden bei einer Durchsicht aller zehn Arten auf Roberts Bitte („auch
    alle anderen mal gründlich kontrollieren"). Der Test hält sie fest: Wer
    eine Merkmalsart ergänzt, ohne ihr einen Satz zu geben, bekommt hier einen
    roten Lauf statt eines Panels aus fünf nichtssagenden Zeilen.
    """
    load_operations()
    speechless = []
    for kind in sorted(features.DETECTABLE_KINDS | {"thread"}):
        feature = Feature(id="x_1", kind=kind, provenance="detected", params={})
        for action in actions_for(feature):
            if action.op is None and str(action.reason) == str(actions._UNKNOWN_KIND):
                speechless.append(f"{kind}/{action.title}")
    assert not speechless, (
        f"Absagen ohne eigenen Grund: {speechless} — ein Fehler endet nie mit "
        "„geht nicht“ (Regel 17)"
    )


def test_the_one_button_stands_below_every_handling(qt_app: QApplication) -> None:
    """Der Knopf und sein Haken stehen unten, nicht über den Zeilen.

    Sie entstehen beim Aufbau des Panels und lagen damit **vor** allem, was
    ``show_feature`` später einfügt — im Fenster stand „Übernehmen" ganz
    oben, über der Überschrift der Auswahl (Robert, 10.09.2026: „ich hab doch
    gesagt der button soll unten sein nicht ganz oben"; „das übernehmen steht
    noch oben").

    Gemessen an den **Layoutplätzen**, nicht an Bildpunkten: Offscreen hat Qt
    keine Schrift, und jede Höhe wäre damit erfunden
    (`.claude/rules/ansicht.md`).
    """
    identifier, feature = a_hole()
    panel = FeaturePanel()
    mesh = plate()
    available = features.detect(mesh)
    panel.show_feature(identifier, feature, features=available, mesh=mesh)

    rows = panel.layout()
    assert rows is not None
    plaetze = {rows.itemAt(index).widget(): index for index in range(rows.count())}
    zeilen = [plaetze[row] for row in panel._built if row in plaetze]
    assert zeilen, "ohne Zeilen prüft dieser Test nichts"
    assert plaetze[panel._apply] > max(zeilen), "der Knopf steht über den Handlungen"
    assert plaetze[panel._every] == plaetze[panel._apply] - 1, (
        "der Haken gehört unmittelbar über den Knopf"
    )
    # **Und der Weg ins Bild steht davor, nicht dazwischen** (11.09.2026): Der
    # Haken ändert den Umfang des Übernehmens, also gehört er an dessen Seite;
    # ein Knopf zwischen beiden machte aus „für alle" eine Frage, auf die zwei
    # Knöpfe antworten.
    assert plaetze[panel._in_view] < plaetze[panel._every], "der Weg ins Bild steht davor"
    assert plaetze[panel._in_view] > max(zeilen), "aber auch er gehört nach unten"


def test_the_all_alike_box_follows_the_armed_handling(qt_app: QApplication) -> None:
    """Ein Haken für alle Handlungen — und er nennt die Zahl der scharfen.

    Vier gleich beschriftete Haken untereinander sagten nicht, welcher welchen
    Zug meint (Robert, 10.09.2026: „alle 4 gleichzeitig dann auch vor dem
    übernehmen"). Der eine unten wechselt mit der Handlung, und wo es keine
    Geschwister gibt, ist er weg statt ausgegraut.
    """
    identifier, feature = a_hole()
    panel = FeaturePanel()
    mesh = plate()
    available = features.detect(mesh)
    panel.show_feature(identifier, feature, features=available, mesh=mesh)

    mit = [key for key, eintrag in panel._runs.items() if eintrag.members > 1]
    ohne = [key for key, eintrag in panel._runs.items() if eintrag.members <= 1]
    assert mit, "an dieser Platte hat mindestens eine Handlung Geschwister"

    for key in mit:
        panel._arm(key)
        assert panel._every.isVisibleTo(panel)
        assert str(panel._runs[key].members) in panel._every.text()
    for key in ohne:
        panel._arm(key)
        assert not panel._every.isVisibleTo(panel), f"{key} hat keine Geschwister"


def test_every_handling_carries_its_explanation_behind_one_sign(qt_app: QApplication) -> None:
    """Jede Handlung trägt ein „i", und dahinter steht ihr Satz.

    Der Absatz stand bis zum 10.09.2026 unter der Überschrift und füllte an
    einer Bohrung vier Zeilen; er sitzt jetzt im Tooltip. Zwei Dinge sind
    daran am 11.09.2026 nachgebessert worden, beide von Robert am laufenden
    Fenster gefunden: Das Zeichen stand nur an *einer* Handlung („ist nur
    hinter material verschieben") — wo ``note`` fehlt, gilt jetzt der eigene
    Satz —, und es war ein ``QLabel``, dessen Tooltip bei achtzehn
    Bildpunkten kaum aufging („der tooltip bei i geht auch nicht auf").

    **Der Text bleibt für den Bildschirmleser an der Überschrift.** Ein
    Tooltip wird nicht vorgelesen; ein zugänglicher Name schon (§19.1).
    """
    from PySide6.QtWidgets import QToolButton

    identifier, feature = a_hole()
    panel = FeaturePanel()
    mesh = plate()
    available = features.detect(mesh)
    panel.show_feature(identifier, feature, features=available, mesh=mesh)

    mit_feldern = [row for row in panel._built if fields(row)]
    assert mit_feldern, "ohne Handlungen mit Feldern prüft dieser Test nichts"
    for row in mit_feldern:
        zeichen = [
            widget for widget in row.findChildren(QToolButton) if widget.objectName() == "infoDot"
        ]
        assert len(zeichen) == 1, f"{row}: {len(zeichen)} Zeichen statt einem"
        dot = zeichen[0]
        assert dot.isVisibleTo(panel), "ein Zeichen ohne Text wäre eine leere Ankündigung"
        assert dot.toolTip(), "und hinter ihm steht etwas"
        titel = next(
            label for label in row.findChildren(QLabel) if label.toolTip() == dot.toolTip()
        )
        assert titel.accessibleDescription() == dot.toolTip(), (
            "der Bildschirmleser bekommt den Satz an der Überschrift"
        )
