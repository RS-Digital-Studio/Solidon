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
from itertools import pairwise
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
    QToolButton,
    QWidget,
)

from app.core.bootstrap import load_operations
from app.core.geom.mesh import MeshData, as_mesh_data, read_mesh
from app.core.perceive import actions, features
from app.core.perceive.actions import EDGE_OPERATIONS, EDGE_VARIANTS, actions_for
from app.core.registry import REGISTRY, validate
from app.core.types import Feature, FeatureKind
from app.core.units import LengthUnit
from app.i18n import tr
from app.ui.labels import BoundedLengthSpin, BoundedSpin, LengthSpin, NumberSpin
from app.ui.panels import FeaturePanel

MESHES = Path(__file__).parent / "data" / "meshes"


def test_measuring_keeps_footer_actions_hidden_through_a_feature_switch(qt_app) -> None:
    """Kein kurzes Zeigen/Verbergen derselben Fußzeile in einer Auswahlrunde."""
    from PySide6.QtCore import QEvent, QObject

    class Watch(QObject):
        def __init__(self):
            super().__init__()
            self.shown = []

        def eventFilter(self, watched, event):  # noqa: N802
            if event.type() in (QEvent.Type.Show, QEvent.Type.ShowToParent):
                self.shown.append(watched)
            return False

    load_operations()
    mesh = read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl")
    found = features.detect(mesh)
    holes = [key for key, feature in found.items() if feature.kind == "hole"]
    panel = FeaturePanel()
    watcher = Watch()
    try:
        panel.show_feature(holes[0], found[holes[0]], features=found, mesh=mesh)
        panel.set_measuring(True, op="resize_hole")
        for widget in (panel._in_view, panel._every, panel._apply):
            widget.installEventFilter(watcher)
        panel.set_locked("")
        panel.show_feature(holes[1], found[holes[1]], features=found, mesh=mesh)
        panel.set_measuring(True, op="resize_hole")
        assert not watcher.shown
        panel.set_measuring(False)
        assert not panel._in_view.isHidden()
        assert not panel._every.isHidden()
        assert not panel._apply.isHidden()
    finally:
        panel.close()
        panel.deleteLater()


def test_one_action_is_open_and_it_is_the_one_apply_takes(qt_app: QApplication) -> None:
    """RM-510: Am Merkmal ein Akkordeon — genau eine Handlung offen, die scharfe.

    An einer Bohrung standen sechs Handlungen mit allen Feldern zugleich offen,
    1579 Punkte Inhalt in 877 sichtbaren. Offen ist jetzt die, die *Übernehmen*
    meint; die anderen nennen zugeklappt ihre Werte. Ein Klick auf einen Kopf
    öffnet seine Handlung und macht sie scharf, ein zweiter Klick auf den
    offenen schließt sie nicht — offen ist immer genau eine.
    """
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    rows = [row for row in panel._shown_rows.values() if row.toggle is not None]
    assert len(rows) > 2, "ohne mehrere Handlungen prüft der Test nichts"

    def open_keys() -> list[str]:
        return [row.key for row in rows if row.body is not None and not row.body.isHidden()]

    assert open_keys() == [panel._armed], "offen ist genau die scharfe"
    other = next(row for row in rows if row.key != panel._armed)
    assert other.summary is not None and other.summary.text(), "zugeklappt nennt sie ihre Werte"
    assert not other.summary.isHidden()

    assert other.toggle is not None
    other.toggle.click()
    assert panel._armed == other.key, "der Kopf macht seine Handlung scharf"
    assert open_keys() == [other.key]
    assert other.summary.isHidden(), "offen stehen die Felder, nicht ihre Zusammenfassung"

    other.toggle.click()
    assert open_keys() == [other.key], "ein Klick auf die offene schließt sie nicht"


def test_a_place_stands_on_one_line_where_the_card_has_room(qt_app: QApplication) -> None:
    """X, Y und Z einer Stelle nebeneinander, wo die Zeile ihr Mindestmaß hat (RM-511).

    Robert, 05.10.2026: die rechte Karte breiter machen „und es dann auch
    sinnvoll nutzen“. An einer Bohrung spart die Zeile bei *Verschieben* und
    *Verdoppeln* je zwei Zeilen. In einer schmalen Karte stehen die drei Felder
    wieder untereinander, statt eine Zahl abzuschneiden — und die Zeile
    verlangt nie mehr Mindestbreite als ein Paar, sonst erzwänge sie selbst die
    breite Karte. Verschwinden alle drei Felder, geht die Zeile mit.
    """
    from app.ui.panels import _CoordinateRow

    load_operations()
    mesh = read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl")
    found = features.detect(mesh)
    hole = next(key for key, feature in found.items() if feature.kind == "hole")
    panel = FeaturePanel()
    try:
        panel.show_feature(hole, found[hole], features=found, mesh=mesh)
        rows = [row for row in panel._shown_rows.values() if row.op == "move_feature"]
        assert rows, "an einer Bohrung steht *Merkmal verschieben*"
        (place,) = rows[0].coordinates
        assert isinstance(place, _CoordinateRow)
        assert [label.buddy() for label, _editor in place._pairs] == [
            rows[0].widgets[name] for name in ("x", "y", "z")
        ], "jede Beschriftung gehört weiter zu ihrem Feld"

        # **Gezeigt, sonst entscheidet nichts:** Die Zeile ordnet sich in ihrem
        # ``resizeEvent``, und ein nie gezeigtes Widget bekommt es erst beim
        # Zeigen — ungezeigt blieb sie in jeder Breite nebeneinander.
        panel.show()
        qt_app.processEvents()
        place.resize(place._needed() + 20, place.sizeHint().height())
        assert place.across(), "mit Platz in einer Zeile"
        place.resize(place._needed() - 20, place.sizeHint().height())
        assert not place.across(), "zu eng: untereinander"
        assert place.minimumSizeHint().width() < place._needed(), (
            "die Zeile erzwingt nicht selbst die breite Karte"
        )

        for _label, editor in place._pairs:
            editor.hide()
        place.follow_fields()
        assert place.isHidden(), "ohne Felder keine leere Lücke"
    finally:
        panel.close()
        panel.deleteLater()


def test_texture_fields_keep_expressions_and_hidden_parameters(qt_app: QApplication) -> None:
    """Ein vorhandenes Rechteck behält seine Breitenbindung und seinen Ort."""
    from types import SimpleNamespace

    from app.ui.op_dialog import ValueField

    step = SimpleNamespace(
        id=8,
        op="apply_texture",
        params={"width": "=@span", "height": 17.0, "x": 12.0, "nx": 1.0, "nz": 0.0},
    )
    panel = FeaturePanel()
    seen = []
    panel.stepChangeRequested.connect(lambda *args: seen.append(args))
    panel.show_texture([step], parameter_values={"span": 30.0})
    fields = {
        field._entry.name: field for row in panel._built for field in row.findChildren(ValueField)
    }
    assert {"width", "height", "pitch", "depth", "angle"} == set(fields)
    assert fields["width"].value() == "=@span"
    panel._apply.click()
    assert seen[0][0] == 8
    assert seen[0][1]["width"] == "=@span"
    assert seen[0][1]["x"] == pytest.approx(12.0)
    assert "at_feature" not in seen[0][1]
    pattern = next(box for box in panel.findChildren(QComboBox) if box.findData("voronoi") >= 0)
    assert not pattern.itemIcon(pattern.findData("voronoi")).isNull()


def test_ambiguous_textures_require_a_choice_and_clear_the_previous_preview(
    qt_app: QApplication,
) -> None:
    """Zwei Texturen werden benannt; keine wird still als letzte ausgewählt."""
    from types import SimpleNamespace

    steps = [SimpleNamespace(id=number, op="apply_texture", params={}) for number in (3, 7)]
    panel = FeaturePanel()
    cleared = []
    panel.stepSelectionChanged.connect(lambda: cleared.append(True))
    panel.show_texture(steps)
    assert panel.shown_part_step() is None
    assert panel._apply.isHidden()
    choice = panel.findChild(QComboBox, "texture-step-choice")
    choice.setCurrentIndex(choice.findData(3))
    assert panel.shown_part_step() == 3
    assert len(cleared) == 2


def test_a_texture_can_be_removed_directly_from_its_panel(qt_app: QApplication) -> None:
    """Der sichtbare Knopf entfernt den ursprünglichen Schritt über den bestehenden Signalweg."""
    from types import SimpleNamespace

    step = SimpleNamespace(id=8, op="apply_texture", params={})
    panel = FeaturePanel()
    removed: list[int] = []
    changed: list[object] = []
    operations: list[object] = []
    panel.stepRemoveRequested.connect(removed.append)
    panel.stepChangeRequested.connect(lambda *args: changed.append(args))
    panel.operationRequested.connect(lambda *args: operations.append(args))
    panel.show_texture([step])
    remove = next(
        button
        for button in panel.findChildren(QPushButton)
        if button.text() == tr("Textur entfernen")
    )
    assert not remove.isHidden() and remove.isEnabled()
    remove.click()
    assert removed == [step.id]
    assert not changed and not operations


def test_texture_steps_follow_object_ancestry_and_provenance() -> None:
    """Gleiche Flächennamen fremder Körper und jüngere andere Texturen werden getrennt."""
    from app.core.types import Document, Operation
    from app.ui.panels import texture_steps_of

    document = Document(
        format_version=1,
        app_version="test",
        ops=[
            Operation(
                id=1,
                op="apply_texture",
                inputs=("a",),
                outputs=("a",),
                params={"coverage": "whole_face", "face": "top"},
            ),
            Operation(
                id=2,
                op="apply_texture",
                inputs=("b",),
                outputs=("b",),
                params={"coverage": "whole_face", "face": "top"},
            ),
            Operation(id=3, op="split_bodies", inputs=("a",), outputs=("a", "child")),
            Operation(
                id=4,
                op="apply_texture",
                inputs=("child",),
                outputs=("child",),
                params={"face": "bottom"},
            ),
        ],
    )
    pattern = Feature(
        id="texture_1",
        kind="pattern",
        provenance="generated",
        created_by=1,
        params={},
        face_indices=(0, 1),
    )
    face = Feature(id="top", kind="face", provenance="detected", params={})
    candidates, certain = texture_steps_of("child", pattern, document)
    assert certain and [entry.id for entry in candidates] == [1]
    candidates, certain = texture_steps_of("b", replace(pattern, created_by=2), document)
    assert certain and [entry.id for entry in candidates] == [2]
    candidates, certain = texture_steps_of(
        "child", replace(face, id="unknown", created_by=None), document
    )
    assert not certain and [entry.id for entry in candidates] == [1, 4]
    document.ops.append(
        Operation(id=5, op="apply_texture", inputs=("a",), outputs=("a",), params={"face": "top"})
    )
    candidates, certain = texture_steps_of("child", pattern, document)
    assert certain and [entry.id for entry in candidates] == [1]
    # Ein historisches Rechteck kann noch die inzwischen unwirksame
    # Flächenvorwahl tragen. Sie belegt seine heutige Lage nicht.
    document.ops[1] = replace(document.ops[1], params={"face": "top"})
    candidates, certain = texture_steps_of("b", replace(face, created_by=None), document)
    assert not certain and [entry.id for entry in candidates] == [2]


@pytest.mark.parametrize(
    "kind,created_by,recognised,indices,certain",
    [
        ("face", None, True, (0, 1), False),
        ("face", 7, True, (0, 1), False),
        ("hole", 7, True, (0, 1), False),
        ("pattern", 7, False, (), False),
        ("pattern", 7, True, (), False),
        ("pattern", 7, True, (0, 1), True),
    ],
)
def test_texture_steps_require_an_existing_pattern_for_direct_editing(
    kind: FeatureKind,
    created_by: int | None,
    recognised: bool,
    indices: tuple[int, ...],
    certain: bool,
) -> None:
    """Ohne belegtes Muster bleiben wirkungslose Schritte und alte Einzelzellen wählbar."""
    from app.core.types import Document, Operation
    from app.ui.panels import texture_steps_of

    step = Operation(
        id=7,
        op="apply_texture",
        inputs=("body",),
        outputs=("body",),
        params={"coverage": "whole_face", "face": "top"},
    )
    document = Document(format_version=1, app_version="test", ops=[step])
    feature = Feature(
        id="top",
        kind=kind,
        provenance="detected",
        created_by=created_by,
        params={},
        recognised=recognised,
        face_indices=indices,
    )
    candidates, proven = texture_steps_of("body", feature, document, completed=(7,))
    assert candidates == [step]
    assert proven is certain
    assert texture_steps_of("body", feature, document, completed=()) == ([], False)


@pytest.mark.parametrize("changed", [{"cell_depth": 1.2}, {"style": "wave"}])
@pytest.mark.parametrize(
    "target,owner,after_split,completed,suppressed,certain",
    [
        ("op2.texture_1", "body", False, None, False, False),
        ("body:op2.texture_1", "body", False, None, False, False),
        ("op2.texture_1", "child", True, None, False, False),
        ("child:op2.texture_1", "child", True, None, False, False),
        ("op2.texture_1", "body", True, None, False, True),
        ("op2.texture_1", "other", False, None, False, True),
        ("other:op2.texture_1", "body", False, None, False, True),
        ("op4.texture_1", "body", False, None, False, True),
        ("op2.texture_1", "body", False, (2, 4), False, True),
        ("op2.texture_1", "body", False, (2, 3, 4), True, True),
    ],
)
def test_texture_steps_keep_later_feature_changes_in_the_current_panel(
    changed: dict[str, float | str],
    target: str,
    owner: str,
    after_split: bool,
    completed: tuple[int, ...] | None,
    suppressed: bool,
    certain: bool,
) -> None:
    """Nach 0,6 → 1,2 mm zeigt die Auswahl aktuelle Maße; der Erzeuger bleibt separat wählbar."""
    from app.core.types import Document, Operation, Suppression
    from app.ui.panels import texture_steps_of

    texture = Operation(
        id=2,
        op="apply_texture",
        inputs=("body",),
        outputs=("body",),
        params={"depth": 0.6},
    )
    change = Operation(
        id=3,
        op="resize_feature",
        inputs=(owner,),
        outputs=(owner,),
        params={"at_feature": target, **changed},
        suppressed=Suppression() if suppressed else None,
    )
    split = Operation(id=4, op="split_bodies", inputs=("body",), outputs=("body", "child"))
    document = Document(
        format_version=1,
        app_version="test",
        ops=[texture, split, change] if after_split else [texture, change, split],
    )
    feature = Feature(
        id="op2.texture_1",
        kind="pattern",
        provenance="generated",
        created_by=2,
        params={"cell_depth": 1.2},
        face_indices=(0, 1),
    )
    candidates, proven = texture_steps_of("child", feature, document, completed=completed)
    assert candidates == [texture]
    assert proven is certain
    # Schrittnummern sind keine Reihenfolge: Eine Änderung vor dem Erzeuger
    # überschreibt dessen heutige Werte nicht.
    before = replace(document, ops=[change, texture, split])
    assert texture_steps_of("child", feature, before, completed=completed) == ([texture], True)
    # Ein ausgeschalteter Erzeuger ist keine vorhandene Textur.
    off = replace(document, ops=[replace(texture, suppressed=Suppression()), split])
    assert texture_steps_of("child", feature, off, completed=completed) == ([], False)


@pytest.mark.parametrize("combine", ["union_objects", "intersect_objects"])
@pytest.mark.parametrize("owner,certain", [("body", False), ("other", True)])
def test_texture_steps_follow_feature_names_before_combined_bodies(
    combine: str, owner: str, certain: bool
) -> None:
    """Vor einer Vereinigung geänderte Texturen behalten ihren Bezug trotz neuer Namensräume."""
    from app.core.types import Document, Operation
    from app.ui.panels import texture_steps_of

    texture = Operation(id=2, op="apply_texture", inputs=("body",), outputs=("body",))
    change = Operation(
        id=3,
        op="resize_feature",
        inputs=(owner,),
        outputs=(owner,),
        params={"at_feature": "op2.texture_1", "cell_depth": 1.2},
    )
    first = Operation(id=4, op=combine, inputs=("other", "body"), outputs=("joined",))
    second = Operation(id=5, op=combine, inputs=("last", "joined"), outputs=("final",))
    document = Document(format_version=1, app_version="test", ops=[texture, change, first, second])
    feature = Feature(
        id="joined.body.op2.texture_1",
        kind="pattern",
        provenance="generated",
        created_by=2,
        params={"cell_depth": 1.2},
        face_indices=(0, 1),
    )
    assert texture_steps_of("final", feature, document) == ([texture], certain)


def test_a_stopped_texture_is_not_presented_as_an_existing_surface(qt_app: QApplication) -> None:
    """Ein gescheiterter Texturschritt hat die weiterhin glatte Fläche nicht geprägt."""
    from app.core.scene import OperationDraft
    from app.core.scene.placement import top_face
    from app.ui.panels import texture_steps_of
    from app.ui.session import Session

    session = Session()
    session.apply("Körper", [OperationDraft(op="create_box")])
    assert session.wait_for_idle()
    body = next(iter(session.last_result.scene.objects.values()))
    face = top_face(body.features)
    assert face is not None
    session.apply(
        "Muster",
        [
            OperationDraft(
                op="apply_texture",
                inputs=(body.id,),
                params={"coverage": "whole_face", "face": face.id, "pitch": 0.1},
            )
        ],
    )
    assert session.wait_for_idle()
    result = session.last_result
    assert result.stopped_at is not None
    candidates, _certain = texture_steps_of(
        body.id, face, session.project.document, completed=result.completed
    )
    assert not candidates


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


def test_choosing_another_feature_reports_it_once_without_an_empty_step(
    qt_app: QApplication,
) -> None:
    """Ein Klick auf ein anderes Merkmal meldet genau dieses — kein „nichts" davor.

    ``select_feature`` leerte die Baumauswahl ungeblockt und setzte danach die
    neue. Jeder Empfänger bekam damit zwei Runden: „nichts gewählt"
    (Merkmalfenster geleert, Handlungskarte, Menüs, Maßgruppe beendet) und
    gleich danach das neue Merkmal — am Halter mit Wabenmuster ein Drittel
    eines Bohrungsklicks (22.09.2026). Gemeldet wird jetzt der neue Stand,
    einmal; dasselbe gilt für Körper und Mehrfachauswahl.
    """
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.panels import ObjectTree

    mesh = plate()
    found = features.detect(mesh)
    holes = [key for key, value in found.items() if value.kind == "hole"]
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=found)
    other = SceneObject(id="obj_2", name="Zweite", mesh=mesh, features={})
    tree = ObjectTree()
    tree.show_scene(EvaluationResult(Scene(objects={entry.id: entry, other.id: other})))
    tree.select_feature(entry.id, holes[0])
    heard: list[object] = []
    bodies: list[object] = []
    tree.featureSelected.connect(heard.append)
    tree.selectionChanged.connect(bodies.append)

    tree.select_feature(entry.id, holes[1])
    assert heard == [holes[1]], heard
    assert bodies == [entry.id], bodies

    heard.clear()
    bodies.clear()
    tree.select_object(other.id)
    assert heard == [None] and bodies == [other.id], (heard, bodies)

    bodies.clear()
    tree.select_objects([entry.id, other.id])
    assert bodies == [entry.id], bodies
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
        # ``text`` ist nicht überall eine Methode: Der Namensfeld-Träger des
        # Dialogs führt sein Zeilenfeld unter diesem Namen.
        text = getattr(widget, "text", None)
        for teil in (
            text() if callable(text) else "",
            widget.toolTip(),
            widget.accessibleDescription(),
        ):
            if teil and teil not in stuecke:
                stuecke.append(teil)
    return " ".join(stuecke)


def row_of(panel: FeaturePanel, title: str) -> QWidget:
    """Die Zeile, deren Überschrift diese Handlung nennt — aufgeklappt.

    Bis zum 10.09.2026 fand man sie an ihrem Knopf; den gibt es nicht mehr,
    und die Überschrift trug den Titel schon immer daneben. Seit RM-510 ist
    die Überschrift der Kopf eines Akkordeons, und offen ist nur die scharfe
    Handlung; geöffnet wird die gesuchte wie vom Kunden, mit einem Klick.
    """
    for row in panel._built:
        if any(label.text() == title for label in row.findChildren(QLabel)):
            toggle = next(
                (
                    head
                    for head in row.findChildren(QToolButton)
                    if head.objectName() == "actionHeading"
                ),
                None,
            )
            if toggle is not None and not toggle.isChecked():
                toggle.click()
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


def test_a_locked_panel_says_why_before_anyone_clicks(qt_app: QApplication) -> None:
    """Hält die Kette an, nimmt das Merkmalfenster nichts mehr an — und sagt es.

    Bis zum 13.09.2026 blieben Felder und beide Knöpfe aktiv, während Menü,
    Werkzeugzeile und Befehlspalette längst mit Grund gesperrt waren; der
    Versuch endete in einem modalen „Das hat so nicht funktioniert". Das ist
    die Sackgasse aus Regel 19 — die Oberfläche konnte die Frage vorher
    beantworten und tat es nicht.

    Zwei Kodierungen (Regel 18): der graue Knopf **und** derselbe Satz als
    sichtbare Zeile, dazu in Kurzhilfe und zugänglicher Beschreibung.
    """
    grund = "Die Kette hält an Schritt 2 (Bohrung setzen) an."
    identifier, feature = a_hole()
    panel = FeaturePanel()
    mesh = plate()
    panel.show_feature(identifier, feature, features=features.detect(mesh), mesh=mesh)

    felder = [
        widget
        for widget in panel.findChildren(QWidget)
        if isinstance(widget, LengthSpin | NumberSpin) and widget.isVisibleTo(panel)
    ]
    assert felder, "ohne Felder prüft dieser Test nichts"
    assert panel._apply.isEnabled(), "Voraussetzung: ohne Halt geht es"

    panel.set_locked(grund)

    assert not panel._apply.isEnabled(), "Übernehmen nimmt hinter einem Halt nichts an"
    assert not panel._in_view.isEnabled(), "und der Weg ins Bild führt in dieselbe Absage"
    gesperrt = [feld.accessibleName() for feld in felder if feld.isEnabled()]
    assert not gesperrt, f"{len(gesperrt)} Felder nehmen weiter Zahlen an: {gesperrt}"
    assert panel._apply.toolTip() == grund and panel._apply.accessibleDescription() == grund
    assert panel._lock_note.text() == grund, "der Grund steht als Zeile, nicht nur im Tooltip"
    assert panel._lock_note.isVisibleTo(panel), "und er steht sichtbar da"

    # **Und der Weg zurück braucht keine neue Auswahl.** Nach einem Strg+Z
    # rechnet die Kette wieder; das Fenster meldet den leeren Grund, und die
    # Knöpfe tragen wieder ihre eigene Auskunft statt der Absage von vorhin.
    panel.set_locked("")

    assert panel._apply.isEnabled() and panel._in_view.isEnabled()
    assert all(feld.isEnabled() for feld in felder)
    assert not panel._lock_note.isVisibleTo(panel)
    assert panel._apply.toolTip() == panel._armed_title.text(), "wieder der Titel der Handlung"


def test_preview_block_keeps_fields_and_cancel_available(qt_app: QApplication) -> None:
    """Die Vorschau sperrt nur Übernehmen und überlebt Feld- und Sperrwechsel.

    *Abbrechen* steht, solange das Fenster eine wartende Vorschau aus diesem
    Panel anbietet (``offer_cancel``) — beim Messen im Bild trägt die
    Maßgruppe beide Knöpfe (``set_measuring``). Ohne Fenster bietet niemand
    sie an; geprüft wird deshalb, dass Felder und der Weg ins Bild frei
    bleiben, während Übernehmen mit dem Grund sperrt, und dass das Angebot
    den Knopf zeigt und mit dem Messen wieder nimmt.
    """
    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    requested: list[Any] = []
    panel.operationRequested.connect(lambda *args: requested.append(args))
    spin = next(
        field
        for field in panel.findChildren(LengthSpin)
        if "Bohrung ändern" in field.accessibleName() and "Durchmesser" in field.accessibleName()
    )
    reason = "Die Vorschau wird berechnet. Bitte das Ergebnis abwarten."
    panel.block_apply(reason)
    spin.set_value_mm(6.0)
    panel.set_locked("Die Kette hält an Schritt 2 an.")
    panel.set_locked("")

    assert spin.isEnabled() and panel._in_view.isEnabled()
    assert not panel.can_accept() and not panel._apply.isEnabled()
    assert panel._apply.toolTip() == reason
    assert panel._apply.accessibleDescription() == reason
    assert panel._lock_note.isVisibleTo(panel) and panel._lock_note.text() == reason
    panel._apply.click()
    panel._run_armed()
    assert not requested

    panel.block_apply(None)
    assert panel.can_accept() and panel._apply.isEnabled()
    assert panel._apply.toolTip() == panel._armed_title.text()
    assert not panel._lock_note.isVisibleTo(panel)
    panel.preview_check = lambda: False
    panel._apply.click()
    assert not requested
    panel.preview_check = None

    assert panel._cancel.isHidden(), "ohne Angebot steht kein Abbrechen"
    panel.offer_cancel(True)
    assert not panel._cancel.isHidden(), "eine wartende Vorschau bietet Abbrechen an"
    panel.set_measuring(True, op="resize_hole")
    assert panel._cancel.isHidden(), "beim Messen trägt die Maßgruppe den Knopf"
    panel.set_measuring(False)
    panel.offer_cancel(False)
    assert panel._cancel.isHidden()
    panel._apply.click()
    assert len(requested) == 1
    assert requested[0][0] == "resize_hole"
    assert requested[0][1]["diameter"] == pytest.approx(6.0)


def test_changed_handling_arms_without_reporting_a_value_change(qt_app: QApplication) -> None:
    """Ein Fokuswechsel nennt die neue Handlung — und meldet keine Wertänderung.

    Bis zum 21.09.2026 kam ein Klick in ein Feld als ``valuesChanged`` an, und
    das Fenster rechnete darauf eine Vorschau mit unveränderten Zahlen (Review
    Fenster #3). Was der Wechsel sagt, ist ``handlingArmed``: die Handlung,
    ihre heutigen Werte, die Ziele der Gruppe — damit das Fenster den Auftrag
    bindet. Gerechnet wird erst bei einem echten Wert.
    """
    identifier, feature = a_hole()
    panel = FeaturePanel()
    mesh = plate()
    panel.show_feature(identifier, feature, features=features.detect(mesh), mesh=mesh)
    resize = next(key for key, entry in panel._runs.items() if entry.op == "resize_hole")
    move = next(key for key, entry in panel._runs.items() if entry.op == "move_feature")
    panel._arm(resize)
    panel._every.setChecked(True)
    armed: list[Any] = []
    changed: list[Any] = []
    panel.handlingArmed.connect(
        lambda op, params: armed.append(
            (op, params, panel.preview_targets(op), panel._armed_title.text())
        )
    )
    panel.valuesChanged.connect(lambda op, params: changed.append((op, params)))
    panel._arm(move)
    assert not changed, "ein Fokuswechsel ist keine Wertänderung"
    assert len(armed) == 1
    assert armed[0][0] == "move_feature"
    assert armed[0][1]["at_feature"] == identifier
    assert armed[0][2][0] == identifier
    assert armed[0][3] == "Merkmal verschieben"
    panel._arm(move)
    assert len(armed) == 1, "dieselbe Handlung noch einmal ist kein Wechsel"


def test_a_feature_field_keeps_an_out_of_range_number_and_blocks_apply(
    qt_app: QApplication,
) -> None:
    """Die Merkmalzeile nennt ihre Grenze, bevor sie einen Wert übernehmen kann."""
    from PySide6.QtTest import QTest

    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    row_box = row_of(panel, "Merkmal drehen")
    row = panel._shown_rows[row_box]
    panel._arm(row.key)
    field = next(field for field in row.entries if field.maximum is not None)
    name = str(field.name)
    editor = row.widgets[name]
    assert isinstance(editor, BoundedSpin)
    line = editor.lineEdit()
    line.setFocus()
    line.selectAll()
    QTest.keyClicks(line, editor.textFromValue(float(field.maximum) + 5.0))

    refusal = row.refusals[name]
    assert editor.refused_value() is not None
    assert "Obergrenze" in refusal.text(), refusal.text()
    assert editor.textFromValue(float(field.maximum)) in refusal.text(), refusal.text()
    assert refusal.isVisibleTo(panel)
    assert not panel._apply.isEnabled(), "eine abgelehnte Eingabe sperrt den gemeinsamen Knopf"
    # Am Fußknopf steht das Feld davor, weit weg von der Zeile (RM-342, D-N2).
    named = tr("{name}: {value}", name=editor.accessibleName(), value=refusal.text())
    assert panel._lock_note.text() == named
    assert editor.accessibleName() and str(field.label) in editor.accessibleName()
    assert panel._lock_note.isVisibleTo(panel), "der Sperrgrund bleibt auch am Fußknopf sichtbar"
    assert not panel.can_accept()
    panel.block_apply("Die Vorschau wird berechnet.")
    assert panel._lock_note.text() == named, "die Grenzangabe bleibt vor dem Fußknopf"
    line.selectAll()
    QTest.keyClicks(line, editor.textFromValue(float(field.maximum)))
    assert panel._lock_note.text() == "Die Vorschau wird berechnet."
    assert not panel._apply.isEnabled(), "nach Eingabekorrektur gilt weiter die Vorschau-Sperre"


def test_a_refusal_hides_with_its_field_and_returns_with_it(qt_app: QApplication) -> None:
    """RM-342 D-N1: Verschwindet ein Feld mit abgelehnter Zahl, geht sein Satz mit.

    Der gemeldete Weg: *Zum Langloch ziehen* X = 1500 mm, dann trägt die
    Maßgruppe von *Bohrung ändern* die gemeinsamen Felder im Bild, und unter
    der Zeile stand der Satz ohne Feld. Geprüft wird jedes Paar aus
    ``LEADS_INTO_THE_VIEW`` und jedes gemeinsame begrenzte Feld, nicht nur X.
    """
    from PySide6.QtTest import QTest

    from app.ui.panels import LEADS_INTO_THE_VIEW

    identifier, feature = a_hole()
    panel = FeaturePanel()
    mesh = plate()
    panel.show_feature(identifier, feature, features=features.detect(mesh), mesh=mesh)
    panel.show()
    QApplication.processEvents()
    rows = {row.op: row for row in panel._shown_rows.values()}
    checked = 0
    for op in sorted(LEADS_INTO_THE_VIEW & set(rows)):
        row = rows[op]
        for other in sorted(LEADS_INTO_THE_VIEW & set(rows) - {op}):
            shared = set(row.widgets) & set(rows[other].widgets)
            for name in sorted(shared):
                editor = row.widgets[name]
                field = next(entry for entry in row.entries if str(entry.name) == name)
                bounded = isinstance(editor, (BoundedSpin, BoundedLengthSpin))
                if not bounded or field.maximum is None:
                    continue
                panel._arm(row.key)
                line = editor.lineEdit()
                line.setFocus()
                line.selectAll()
                QTest.keyClicks(line, editor.textFromValue(float(field.maximum) + 5.0))
                refusal = row.refusals[name]
                assert refusal.isVisibleTo(panel), (op, name)
                panel.set_measuring(True, op=other)
                assert not editor.isVisibleTo(panel), (op, name, "die Maßgruppe trägt das Feld")
                assert not refusal.isVisibleTo(panel), f"{op}.{name}: Satz ohne Feld"
                panel.set_measuring(False)
                assert editor.isVisibleTo(panel)
                assert refusal.isVisibleTo(panel), f"{op}.{name}: der Satz kommt mit dem Feld"
                line.selectAll()
                QTest.keyClicks(line, editor.textFromValue(float(field.maximum)))
                checked += 1
    assert checked, "kein gemeinsames begrenztes Feld zwischen Zeile und Maßgruppe gefunden"


def test_a_rejected_length_survives_a_display_unit_change(qt_app: QApplication) -> None:
    """Eine Einheit umzurechnen darf den getippten Grenzverstoß nicht verlieren."""
    from app.core.units import from_mm
    from app.ui.labels import BoundedLengthSpin, display_unit, set_display_unit

    previous_unit = display_unit()
    editor = BoundedLengthSpin()
    try:
        set_display_unit("mm")
        editor.set_range_mm(0.0, 100.0)
        editor.set_value_mm(40.0)
        editor.lineEdit().setText(editor.textFromValue(150.0))
        assert editor.refused_value() == pytest.approx(150.0)

        set_display_unit("in")
        editor.refresh_unit()

        # Die abgelehnte Zahl ist der Text im Feld, und der steht in der
        # Stellenzahl der Einheit (``decimals_for``): 150 mm sind „5,9055 in“,
        # nicht 5,905511811 — genauer als seine Anzeige kann sie nicht sein.
        refusal = editor.refusal()
        shown_step = 10.0 ** -editor.decimals()
        assert editor.refused_value() == pytest.approx(from_mm(150.0, "in"), abs=shown_step / 2)
        assert "in" in refusal and "Obergrenze" in refusal, refusal
        assert editor.textFromValue(editor.maximum()) in refusal, refusal

        # Und zurück: Die Rundung der Zollanzeige kostet in Millimetern nichts.
        set_display_unit("mm")
        editor.refresh_unit()
        assert editor.lineEdit().text() == editor.textFromValue(150.0) + editor.suffix()
        assert editor.refused_value() == pytest.approx(150.0)
    finally:
        set_display_unit(previous_unit)
        editor.refresh_unit()
        editor.deleteLater()


def test_return_rechecks_preview_permission_after_interpreting_text(qt_app: QApplication) -> None:
    """Enter schreibt den Text fest und darf dabei keine alte Freigabe verwenden."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    identifier, feature = a_hole()
    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    requested: list[Any] = []
    changed: list[Any] = []
    panel.operationRequested.connect(lambda *args: requested.append(args))

    def changed_values(op: str, values: dict[str, Any]) -> None:
        changed.append((op, values))
        panel.block_apply("Die Vorschau wird berechnet. Bitte das Ergebnis abwarten.")

    panel.valuesChanged.connect(changed_values)
    spin = next(
        field
        for field in panel.findChildren(LengthSpin)
        if "Bohrung ändern" in field.accessibleName() and "Durchmesser" in field.accessibleName()
    )
    spin.setKeyboardTracking(False)
    editor = spin.lineEdit()
    assert editor is not None
    editor.setText("6")
    assert not changed and panel.can_accept()
    QTest.keyClick(editor, Qt.Key.Key_Return)

    assert changed and changed[-1][1]["diameter"] == pytest.approx(6.0)
    assert not requested and not panel.can_accept()
    panel.block_apply(None)
    QTest.keyClick(editor, Qt.Key.Key_Return)
    assert len(requested) == 1
    assert requested[0][1]["diameter"] == pytest.approx(6.0)


def test_a_locked_panel_stays_locked_when_the_next_feature_is_shown(
    qt_app: QApplication,
) -> None:
    """Der Grund gilt der Kette, nicht der Auswahl.

    Das Panel baut seine Zeilen bei jedem Merkmal neu auf. Eine Sperre, die
    nur die gerade stehenden Widgets kennt, wäre nach dem nächsten Klick im
    Objektbaum weg — und der Kunde stünde wieder vor bedienbaren Feldern
    hinter einem Halt.
    """
    identifier, feature = a_hole()
    panel = FeaturePanel()
    mesh = plate()
    available = features.detect(mesh)
    panel.show_feature(identifier, feature, features=available, mesh=mesh)
    panel.set_locked("Die Kette hält an Schritt 2 (Bohrung setzen) an.")

    zweites = next(
        (key, value)
        for key, value in available.items()
        if value.kind == "hole" and key != identifier
    )
    panel.show_feature(*zweites, features=available, mesh=mesh)

    felder = [
        widget
        for widget in panel.findChildren(QWidget)
        if isinstance(widget, LengthSpin | NumberSpin) and widget.isVisibleTo(panel)
    ]
    assert felder, "ohne Felder prüft dieser Test nichts"
    assert not panel._apply.isEnabled(), "das neue Merkmal steht hinter demselben Halt"
    assert not any(feld.isEnabled() for feld in felder)
    assert panel._lock_note.isVisibleTo(panel)


def test_the_return_key_in_a_field_does_what_the_button_below_does(
    qt_app: QApplication,
) -> None:
    """Wer eine Zahl tippt und Enter drückt, meint den Schritt.

    Gemessen am gebauten Fenster (13.09.2026): Durchmesser auf 6,0 gesetzt,
    ``Return`` im Feld — der Verlauf blieb bei einem Schritt. Erst der Klick
    auf *Übernehmen* schrieb ihn, und der stand an dieser Fensterhöhe unter
    dem Rand (F1).

    Geprüft wird über das echte Tastenereignis und nicht über die Methode
    dahinter: Das Feld liegt hinter einem Ereignisfilter, und ob der greift,
    sagt nur der Weg durch Qt.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    identifier, feature = a_hole()
    panel = FeaturePanel()
    gesehen: list[tuple[str, dict[str, Any]]] = []
    panel.operationRequested.connect(lambda op, werte: gesehen.append((op, werte)))
    panel.show_feature(identifier, feature)

    feld = next(
        widget
        for widget in panel.findChildren(LengthSpin)
        if "Bohrung ändern" in widget.accessibleName() and "Durchmesser" in widget.accessibleName()
    )
    feld.set_value_mm(6.0)
    QTest.keyClick(feld, Qt.Key.Key_Return)

    assert len(gesehen) == 1, f"genau ein Schritt, nicht {len(gesehen)}"
    op, werte = gesehen[0]
    assert op == "resize_hole", "und zwar die Handlung des Feldes, in dem getippt wurde"
    assert werte["diameter"] == pytest.approx(6.0)

    # **Gesperrt tut sie nichts.** Eine Taste, die etwas anderes tut als der
    # Knopf daneben, wäre schlimmer als eine, die schweigt.
    panel.set_locked("Die Kette hält an Schritt 2 (Bohrung setzen) an.")
    QTest.keyClick(feld, Qt.Key.Key_Return)
    assert len(gesehen) == 1, "hinter einem Halt schreibt auch die Eingabetaste nichts"


def test_the_tab_key_reaches_every_heading_and_arrow_on_every_platform(
    qt_app: QApplication,
) -> None:
    """Klappen und Akkordeon-Pfeile erreicht die Tabulatortaste auch am Mac.

    macOS lässt ohne „Tastaturnavigation“ nur Textfelder anspringen
    (``TabFocusTextControls``); Werkzeugknöpfe mit ``TabFocus`` fielen aus der
    Kette, und hinter ihnen lagen seit RM-510/RM-514 Felder, die nur die Maus
    erreichte (Durchsicht 0.5.3, Fund 5). Die Anwendung schaltet die Kette auf
    alle Bedienelemente (``app.reach_every_control_by_tab``), in ``main`` und
    in ``build_application``. Nachgestellt wird die Mac-Vorgabe über
    ``QStyleHints``.
    """
    import inspect

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLineEdit, QToolButton, QVBoxLayout

    import app.ui.app as app_module
    from app.ui.panels import collapsible

    hints = qt_app.styleHints()
    before = hints.tabFocusBehavior()
    hints.setTabFocusBehavior(Qt.TabFocusBehavior.TabFocusTextControls)
    root = QWidget()
    try:
        app_module.reach_every_control_by_tab(qt_app)
        layout = QVBoxLayout(root)
        first = QLineEdit(root)
        arrow = QToolButton(root)
        arrow.setObjectName("actionHeading")
        section = collapsible("Weitere Einstellungen", QLineEdit(), open_now=False)
        section.setParent(root)
        for widget in (first, arrow, section):
            layout.addWidget(widget)
        root.show()
        qt_app.processEvents()
        first.setFocus()
        qt_app.processEvents()
        reached = []
        for _ in range(3):
            root.focusNextChild()
            qt_app.processEvents()
            reached.append(qt_app.focusWidget())
        heading = section.findChild(QToolButton, "sectionHeading")
        assert arrow in reached, "der Pfeil einer Handlung"
        assert heading is not None and heading in reached, "der Kopf einer Klappe"
    finally:
        hints.setTabFocusBehavior(before)
        root.hide()
        root.deleteLater()
    for start in (app_module.main, app_module.build_application):
        assert "reach_every_control_by_tab(application)" in inspect.getsource(start)


def test_the_tab_key_goes_down_the_panel_like_the_eye(qt_app: QApplication) -> None:
    """Die Fokuskette folgt dem Layout, nicht der Entstehungsreihenfolge.

    Die Halte unten — *Im Bild einstellen*, der Haken, *Übernehmen* und beim
    Messen *Abbrechen* — entstehen im Aufbau des Panels und liegen damit vor jedem
    Feld, das ``show_feature`` später einfügt. Sie im Layout ans Ende zu hängen
    verschiebt sie in der Fokuskette **nicht**: Gemessen am gebauten Fenster
    an einer Bohrung mit drei gleichartigen Geschwistern kam *Im Bild
    einstellen* mit der Tabulatortaste erst **nach** dem Haken, während es im
    Layout davor steht — der Nachbartest darüber hält genau diese Anordnung
    fest.

    Gemessen an der Kette und an den Layoutplätzen, nicht an Bildpunkten: Was
    das Auge sieht, sagt das Layout; offscreen wäre jede Höhe erfunden.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLineEdit

    # Ohne geladenes Register gibt es keinen Weg ins Bild, und ohne
    # Geschwister keinen Haken — beides ist die Stelle, an der es klemmte.
    load_operations()
    identifier, feature = a_hole()
    panel = FeaturePanel()
    mesh = plate()
    panel.show_feature(identifier, feature, features=features.detect(mesh), mesh=mesh)
    # *Abbrechen* gehört dem Messen im Bild (``set_measuring``) und steht
    # ohne Maßgruppe nicht da; gemessen wird die Kette über die Halte, die
    # man sieht — und die drei bleiben die Stelle, an der es klemmte.
    unten = (panel._in_view, panel._every, panel._apply)
    for widget in unten:
        assert widget.isVisibleTo(panel), f"{widget.accessibleName()} steht gar nicht da"
    assert not panel._cancel.isVisibleTo(panel), "ohne Maße im Bild kein Abbrechen"

    stops: list[QWidget] = []
    node = panel.nextInFocusChain()
    for _ in range(4000):
        if node is panel:
            break
        if (
            node.focusPolicy() != Qt.FocusPolicy.NoFocus
            and node.isVisibleTo(panel)
            and panel.isAncestorOf(node)
            and not isinstance(node, QLineEdit)
        ):
            stops.append(node)
        node = node.nextInFocusChain()
    assert len(stops) > len(unten), "ohne Felder prüft dieser Test nichts"

    # Die Kette ist ein Ring: gedreht wird auf den ersten Halt, der zu einer
    # Handlung gehört — danach muss sie von oben nach unten laufen.
    start = next(index for index, widget in enumerate(stops) if widget not in unten)
    ordered = stops[start:] + stops[:start]
    places = {widget: index for index, widget in enumerate(ordered)}
    namen = [widget.accessibleName() or widget.text() for widget in ordered]
    assert [places[widget] for widget in unten] == sorted(places[widget] for widget in unten), (
        f"die vier unten kommen in anderer Reihenfolge als im Layout: {namen}"
    )
    assert min(places[widget] for widget in unten) > max(
        places[widget] for widget in stops if widget not in unten
    ), f"ein Feld kommt erst nach dem Knopf: {namen}"


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
    # Der Ort ebenso: Die vergrößerte Platte trägt ihre Bohrungen über einen
    # Meter vom Ursprung. Eine Ortsgrenze von ±1000 mm lehnte den Messwert ab
    # oder versetzte die Bohrung still an die Grenze.
    centre = [float(value) for value in feature.params["centre"]]
    if kind == "hole":
        assert max(abs(value) for value in centre) > 1000.0, "der Fall erreicht die alte Ortsgrenze"
    for axis, value in zip("xyz", centre, strict=True):
        if axis in params:
            assert float(params[axis]) == pytest.approx(value), axis
    accepted = validate(REGISTRY.get(operation).params, params)
    assert accepted.diameter == pytest.approx(measured)


@pytest.mark.parametrize("recess", [False, True], ids=["fillet", "groove"])
@pytest.mark.parametrize("unit", ["mm", "in"])
def test_a_rounding_shows_its_radius_and_sends_the_diameter(
    qt_app: QApplication, recess: bool, unit: LengthUnit
) -> None:
    """Das angezeigte Rundungsmaß gilt für Vorschau und Übernehmen, auch in Zoll."""
    from app.ui.labels import set_display_unit

    # Eine Kantenrundung hat eine Achse; ohne sie ist es die Kugel einer
    # verrundeten Ecke, an der *Merkmal ändern* absagt (RM-226).
    feature = Feature(
        id="fillet_1",
        kind="fillet",
        provenance="detected",
        params={
            "radius": 11.96,
            "recess": recess,
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
        },
    )
    panel = FeaturePanel()
    try:
        set_display_unit(unit)
        panel.show_feature(feature.id, feature)
    finally:
        set_display_unit("mm")
    panel.show()
    QApplication.processEvents()
    row = row_of(panel, "Merkmal ändern")
    spin = next(widget for widget in fields(row) if isinstance(widget, LengthSpin))
    assert spin.isVisibleTo(panel)
    assert spin.accessibleName() == "Merkmal ändern — Radius"
    assert spin.value_mm() == pytest.approx(11.96)
    assert panel.take_values("resize_feature", {"diameter": 10.0})
    assert spin.value_mm() == pytest.approx(5.0)

    previews: list[tuple[str, dict[str, Any]]] = []
    applied: list[tuple[str, dict[str, Any]]] = []
    panel.valuesChanged.connect(lambda op, values: previews.append((op, values)))
    panel.operationRequested.connect(lambda op, values: applied.append((op, values)))
    spin.set_value_mm(8.5)
    press(panel, "Merkmal ändern")
    expected = ("resize_feature", {"at_feature": feature.id, "diameter": 17.0})
    assert previews[-1] == expected
    assert applied == [expected]
    assert "Merkmal entfernen" in buttons(panel)


def test_a_round_wall_offers_radius_instead_of_removing_a_corner(
    qt_app: QApplication,
) -> None:
    """Eine offene Klemme hat einen änderbaren Radius, aber keine scharfe Ersatzkante."""
    feature = Feature(
        id="fillet_1",
        kind="fillet",
        provenance="detected",
        params={"radius": 12.0, "recess": True, "radial": True},
    )
    panel = FeaturePanel()
    panel.show_feature(feature.id, feature)
    assert "Merkmal ändern" in buttons(panel)
    assert "Merkmal entfernen" not in buttons(panel)
    removal = next(
        action for action in actions_for(feature) if str(action.title) == "Merkmal entfernen"
    )
    assert removal.op is None
    assert "Radius" in str(removal.reason)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_the_radius_panel_edits_a_detected_rounding_without_changing_its_neighbours(
    qt_app: QApplication, kind: str
) -> None:
    """Anklicken und unverändert übernehmen bewahrt das Teil; ein neuer Radius wirkt lokal."""
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.types import SceneObject
    from tests.test_mesh_edges import run

    exact = edit.fillet(edit.box(40.0, 30.0, 20.0), 3.0, "vertical")
    body = exact if kind == "brep" else as_mesh_data(exact)
    found = features_of(exact) if kind == "brep" else features.detect(body)
    rounding = next(feature for feature in found.values() if feature.kind == "fillet")
    source = SceneObject(id="obj_1", name="Prüfteil", kind=kind, mesh=body, features=found)
    panel = FeaturePanel()
    panel.show_feature(rounding.id, rounding)
    sent: list[tuple[str, dict[str, Any]]] = []
    panel.operationRequested.connect(lambda op, values: sent.append((op, values)))
    press(panel, "Merkmal ändern")
    op, values = sent.pop()
    assert run(op, source, **values).outputs[0] is source

    row = row_of(panel, "Merkmal ändern")
    spin = next(widget for widget in fields(row) if isinstance(widget, LengthSpin))
    spin.set_value_mm(1.5)
    press(panel, "Merkmal ändern")
    op, values = sent.pop()
    changed = run(op, source, **values).outputs[0]
    result_mesh = as_mesh_data(changed.mesh)
    result_features = features_of(changed.mesh) if kind == "brep" else features.detect(result_mesh)
    radii = sorted(
        float(feature.params["radius"])
        for feature in result_features.values()
        if feature.kind == "fillet"
    )
    assert radii == pytest.approx([1.5, 3.0, 3.0, 3.0], abs=0.04)
    assert result_mesh.is_watertight and result_mesh.component_count == 1
    assert result_mesh.volume > as_mesh_data(source.mesh).volume


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


def test_a_honeycomb_pattern_stands_in_the_panel_with_its_own_fields(qt_app: QApplication) -> None:
    """Die Abnahme am Halter im Fenster (RM-207): angeklickt steht das Muster mit
    Teilung, Zellbreite und Tiefe da, Ändern und Entfernen gehen an genau dieses
    Merkmal, und was nicht gilt, steht grau mit Satz.

    Der Halter selbst liegt nicht im Korpus; seine Zahlen (9 mm Schlüsselweite,
    10,4 mm Teilung, durchgehend) stehen als Wabenplatte nach, wie in
    ``tests/test_pattern_features.py``.
    """
    import trimesh
    from shapely.geometry import Polygon

    from app.core.geom.boolean import boolean
    from app.core.scene.cancel import NeverCancelled
    from app.ui.labels import feature_label

    pitch, across_flats, thickness = 10.4, 9.0, 20.0
    columns, rows = 6, 4
    body = MeshData.of(
        trimesh.creation.box(
            extents=(
                columns * pitch + 1.5 * pitch,
                rows * pitch * 3**0.5 / 2 + 1.5 * pitch,
                thickness,
            )
        )
    )
    radius = across_flats / 3**0.5
    cells = []
    for row in range(rows):
        for column in range(columns):
            x = (column - (columns - 1) / 2.0) * pitch + (pitch / 2.0 if row % 2 else 0.0)
            y = (row - (rows - 1) / 2.0) * pitch * 3**0.5 / 2
            corners = [
                (
                    x + radius * math.cos(math.radians(60.0 * k)),
                    y + radius * math.sin(math.radians(60.0 * k)),
                )
                for k in range(6)
            ]
            prism = trimesh.creation.extrude_polygon(Polygon(corners), height=thickness + 2.0)
            prism.apply_translation((0.0, 0.0, -thickness / 2.0 - 1.0))
            cells.append(prism)
    tools = MeshData.of(trimesh.util.concatenate(cells))
    mesh = boolean("difference", [body, tools], quality="fine", cancelled=NeverCancelled()).mesh
    found = features.detect(mesh)
    identifier, pattern = next(
        (key, value) for key, value in found.items() if value.kind == "pattern"
    )
    assert pattern.params["count"] == columns * rows

    panel = FeaturePanel()
    panel.show_feature(identifier, pattern, features=found, mesh=mesh)

    # Die Felder des Musters — und nur die: Teilung, Zellbreite, Zelltiefe.
    fields = [
        widget
        for widget in panel.findChildren(QWidget)
        if isinstance(widget, LengthSpin | NumberSpin) and widget.isVisibleTo(panel)
    ]
    names = [field.accessibleName() for field in fields]
    assert any("Teilung" in name for name in names), names
    assert any("Zellbreite" in name for name in names), names
    assert any("Zelltiefe" in name for name in names), names
    assert not any("Durchmesser" in name for name in names), names
    assert "Merkmal ändern" in buttons(panel) and "Merkmal entfernen" in buttons(panel), buttons(
        panel
    )
    assert feature_label(identifier, pattern).startswith("Wabenmuster 1")

    seen: list[tuple[str, dict[str, object]]] = []
    panel.operationRequested.connect(lambda op, params: seen.append((op, params)))
    press(panel, "Merkmal entfernen")
    assert seen and seen[0][0] == "remove_feature" and seen[0][1]["at_feature"] == identifier
    press(panel, "Merkmal ändern")
    assert seen[-1][0] == "resize_feature" and seen[-1][1]["at_feature"] == identifier
    assert math.isclose(float(seen[-1][1]["pitch"]), pitch, abs_tol=0.01)


def test_textures_from_other_bodies_have_distinct_visible_numbers() -> None:
    """Gleichnamige Texturen bleiben nach einer Vereinigung sichtbar unterscheidbar."""
    from app.ui.labels import feature_name

    names = []
    for identifier in ("texture_1", "obj_2.texture_1", "obj_3.obj_2.texture_1"):
        pattern = Feature(
            id=identifier,
            kind="pattern",
            provenance="generated",
            params={"texture": True, "style": "rib"},
        )
        names.append(feature_name(identifier, pattern))
    assert len(set(names)) == 3
    assert all("obj_" not in name and "texture_" not in name for name in names)
    assert [name.rsplit(" ", 1)[-1] for name in names] == ["1", "2.1", "3.2.1"]


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
    assert "2 Abschnitte dieser Öffnung" in text
    assert "gemeinsam verschoben" in text


def _run_op(op: str, entry: Any, profile: Any, **params: object) -> Any:
    """Eine Operation fahren, wie der Verlauf sie fährt — der kleine Bruder
    von ``tests/test_prepare.py::_run_op``, ohne dessen Fragehaken."""
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_a_shared_cavity_greys_out_what_would_fail_on_it(profile: Any) -> None:
    """Gemessen am 14.09.2026 an ``plate_countersunk.stl``: *Zum Langloch
    ziehen* an der gesenkten Bohrung öffnete eine Vorschau ohne Bild und hielt
    beim Übernehmen die Kette an. Die Zeile sagt es jetzt vorher, mit dem Satz
    der Operation, und die Operation sagt es beim Rechnen mit demselben Satz.

    *Drehen* und *Verdoppeln* standen einen Tag lang mit auf der Liste — sie
    hatten an der **Bohrung** nur den Stumpf unter der Senkung gekippt oder
    kopiert. Seit dem 15.09.2026 nehmen sie die Kette mit (RM-172, gemessen in
    ``test_prepare``), und die Zeile bleibt an Bohrung und Senkung bedienbar.

    Am echten Netz, nicht an Merkmalen von Hand: Die Sperre kommt aus dem
    Netz (``cavity_chain_state_at``), und dieselbe Bedingung
    (``relations.cavity_is_shared``) entscheidet in Zeile und Operation — beide
    werden hier an demselben Körper gefahren, damit keine sich lösen kann,
    ohne dass es rot wird.
    """
    import trimesh

    from app.core.errors import ValidationError
    from app.core.geom.prepare import countersink, drill
    from app.core.geom.prepare_ops import NEEDS_A_PLAIN_BORE
    from app.core.perceive.features import detect
    from app.core.perceive.relations import cavity_chain_state_at
    from app.core.types import SceneObject

    # Dieselbe Platte wie in ``test_prepare``: 60 mal 40 mal 10, Bohrung Ø 8,
    # Senkung Ø 16 — gebaut, damit die Erkennung Bohrung und Kegel sicher
    # findet (die STL aus dem Korpus braucht dafür den Importweg).
    plate = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0)))
    bored = drill(
        plate, position=(0.0, 0.0, 5.0), axis="z", diameter=8.0, profile=profile, compensate=False
    ).mesh
    mesh = countersink(
        bored, position=(0.0, 0.0, 5.0), axis="z", diameter=16.0, profile=profile
    ).mesh
    found = detect(mesh)
    bore = next(f for f in found.values() if f.kind == "hole")
    sink = next(f for f in found.values() if f.kind == "cone")
    state = cavity_chain_state_at(bore, found, mesh)
    chain, touches_other = state.chain, state.touches_other
    assert chain is not None and {f.id for f in chain} == {bore.id, sink.id}, "die Voraussetzung"

    # Wie das Fenster fragt: mit der Kette aus dem Netz.
    at_sink = {
        str(a.title): a
        for a in actions_for(sink, found, mesh=mesh, cavity=chain, touches_other=touches_other)
    }
    at_bore = {
        str(a.title): a
        for a in actions_for(bore, found, mesh=mesh, cavity=chain, touches_other=touches_other)
    }
    for rows, feature in ((at_sink, sink), (at_bore, bore)):
        for title, op in (
            ("Merkmal drehen", "rotate_feature"),
            ("Merkmal verdoppeln", "duplicate_feature"),
        ):
            assert rows[title].op == op, (feature.kind, title, rows[title].reason)
    assert at_bore["Zum Langloch ziehen"].op is None
    assert str(at_bore["Zum Langloch ziehen"].reason) == str(NEEDS_A_PLAIN_BORE)
    assert at_sink["Merkmal verschieben"].op == "move_feature", "die Kette wandert gemeinsam"
    assert at_sink["Merkmal ändern"].op == "resize_feature"

    # Ohne die zwei Schlüsselwörter fragt ``actions_for`` das Netz selbst —
    # dieselbe Antwort (Review 14.09.2026: die Zusage hing am Aufrufer).
    derived = {str(a.title): a for a in actions_for(bore, found, mesh=mesh)}
    assert derived["Zum Langloch ziehen"].op is None
    assert derived["Merkmal drehen"].op == "rotate_feature"

    # Ohne Netz keine Sperre: ``bore_and_widening_at`` schätzt, und eine
    # Schätzung stellt keine Zeile grau, die die Operation liefe.
    guessed = {str(a.title): a for a in actions_for(bore, found, cavity=chain)}
    assert guessed["Merkmal drehen"].op == "rotate_feature"

    # Und die Operation selbst sagt mit demselben Satz ab.
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=found)
    with pytest.raises(ValidationError) as caught:
        _run_op("slot_hole", entry, profile, at_feature=bore.id, slot_length=12.0)
    assert str(caught.value.detail) == str(NEEDS_A_PLAIN_BORE)

    # Eine Bohrung für sich bleibt, wie sie war.
    plain = bored
    plain_found = detect(plain)
    alone_bore = next(f for f in plain_found.values() if f.kind == "hole")
    alone = {str(a.title): a for a in actions_for(alone_bore, plain_found, mesh=plain)}
    assert alone["Zum Langloch ziehen"].op == "slot_hole"
    assert alone["Merkmal drehen"].op == "rotate_feature"


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

    def chain_at(selected: Feature, available: object, mesh: MeshData) -> relations.CavityState:
        asked.append((selected, available, mesh))
        return relations.CavityState((bore, transition, counterbore), False, None)

    # Seit dem 14.09.2026 fragt das Fenster die Kette **und** die Berührung
    # eines fremden Rands in einem Zug (``cavity_chain_state_at``): Beides
    # braucht ``actions_for``, um zu sagen, was an einem geteilten Hohlraum
    # scheitern würde.
    monkeypatch.setattr(relations, "cavity_chain_state_at", chain_at)
    panel = FeaturePanel()

    selected = counterbore if pick_widening else bore
    panel.show_feature(selected.id, selected, features=linked, mesh=body)

    assert asked == [(selected, linked, body)], (
        "das Panel reicht Netz und Merkmale genau einmal durch"
    )
    heading = next(widget for widget in panel._built if isinstance(widget, QLabel))
    if pick_widening:
        assert "mit Stufen" not in heading.text()
    else:
        assert "Bohrung 1 mit Stufen und Senkung" in heading.text()
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
    assert "3 Abschnitte dieser Öffnung" in text
    assert "gemeinsam verschoben" in text


def test_a_handling_that_does_not_apply_stands_with_its_reason(qt_app: QApplication) -> None:
    """Was nicht geht, steht als eine Zeile mit seinem Grund (RM-535).

    Seit dem 15.09.2026 fielen Absagen weg; am Kundenmodell hatten danach 174
    von 190 Merkmalen keine Zeile zum Versetzen und keinen Satz, warum (Robert
    06.10.2026: „alles einheitlich, Bohrung Vorbild für alle Funktionen“).
    Gleich begründete Absagen liegen in **einer** Zeile, angeklickt wird nichts.
    """
    loop = Feature(
        id="edge_loop_1",
        kind="edge_loop",
        provenance="detected",
        params={"centre": (0.0, 0.0, 0.0), "open_edges": 4},
    )
    ungültig = [action for action in actions_for(loop) if action.op is None]
    assert len(ungültig) > 1, "ohne mehrere Absagen prüft dieser Test das Zusammenlegen nicht"
    assert all(str(action.reason).strip() for action in ungültig), "jede nennt ihren Grund"

    panel = FeaturePanel()
    panel.show_feature("edge_loop_1", loop)

    assert not buttons(panel), "keine Handlung ist anklickbar"
    zeilen = [
        label.text()
        for row in panel._built
        for label in row.findChildren(QLabel)
        if "—" in label.text()
    ]
    for grund in dict.fromkeys(str(action.reason) for action in ungültig):
        mit_grund = [zeile for zeile in zeilen if zeile.endswith(grund)]
        assert len(mit_grund) == 1, (grund, zeilen)
    assert str(ungültig[0].title) in " ".join(zeilen)


def test_an_opening_where_nothing_applies_says_why_once(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Bohrung, an der der Kern jede Handlung ablehnt, nennt den Grund (Durchsicht 0.5.1).

    Am Laptop-Ständer lehnte der Kern an 13 von 28 Bohrungen alles mit „In
    dieser Bohrung steht Material …“ ab; das Fenster zeigte nur Name, Maß und
    den Katalog, und der Kunde wartete auf Maße im Bild. Der Satz steht jetzt
    einmal da, nicht je Handlung; eine anklickbare Handlung gibt es weiter
    nicht.
    """
    from app.core.geom.prepare_ops import HOLE_IS_NOT_EMPTY
    from app.core.perceive.actions import FeatureAction

    identifier, feature = a_hole()
    refused = tuple(
        FeatureAction(title=action.title, op=None, reason=HOLE_IS_NOT_EMPTY)
        for action in actions_for(feature)
    )
    assert len(refused) > 1, "ohne mehrere Absagen prüft der Test das Zusammenlegen nicht"
    monkeypatch.setattr(actions, "actions_for", lambda *args, **kwargs: refused)

    panel = FeaturePanel()
    panel.show_feature(identifier, feature)

    assert not buttons(panel), "keine Handlung ist anklickbar"
    said = [
        label.text()
        for label in panel.findChildren(QLabel)
        if str(HOLE_IS_NOT_EMPTY) in label.text()
    ]
    # Eine Zeile, alle Titel davor (RM-535: Absagen stehen als Zeile).
    assert len(said) == 1 and said[0].endswith(str(HOLE_IS_NOT_EMPTY)), said


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
    Untermenü. **Seit RM-510 trägt ihn an der Fläche der Hauptknopf *Bausteine*
    der Karte darunter** (``test_ui.py``,
    ``test_a_face_offers_the_catalogue_from_the_panel``): Zwei Knöpfe mit einem
    Ziel wären eine Frage ohne Antwort. Das Merkmalfenster selbst bietet, was
    nur es hat: an dieser Fläche zeichnen, und ein Loch oder eine Aussparung.
    """
    from app.i18n import tr

    identifier, feature = a_face()
    # Seit RM-535 gilt an der Fläche genau eine Zeile: *Fläche versetzen*.
    offered = {action.op for action in actions_for(feature)} - {None}
    assert offered == {"push_face"}, "sonst prüft das nichts"

    panel = FeaturePanel()
    panel.show_feature(identifier, feature)
    gerufen: list[tuple[str, bool]] = []
    panel.sketchRequested.connect(lambda feature_id, cut: gerufen.append((feature_id, cut)))

    knoepfe = {widget.text(): widget for widget in panel._built if isinstance(widget, QPushButton)}
    assert tr("Baustein einsetzen …") not in knoepfe, "ein Ziel, ein Knopf (RM-510)"
    for text, cut in ((tr("Hier zeichnen"), False), (tr("Loch oder Aussparung zeichnen …"), True)):
        knopf = knoepfe[text]
        assert knopf.isEnabled() and not knopf.isHidden()
        knopf.click()
        assert gerufen[-1] == (identifier, cut), text


def test_a_face_moves_by_a_distance_from_its_own_row(qt_app: QApplication) -> None:
    """*Fläche versetzen* steht als Zeile mit dem Weg, wie *Merkmal verschieben*
    an der Bohrung (RM-535, Robert 06.10.2026: „alles einheitlich“).

    Der Weg beginnt bei 0 und nicht bei der Vorgabe des Dialogs (2 mm): Ein
    *Übernehmen* ohne Hinsehen versetzte sonst still. Übernommen wird mit der
    Fläche unter ``face`` — dem Namen, unter dem die Operation sie führt.
    """
    from app.i18n import tr

    identifier, feature = a_face()
    panel = FeaturePanel()
    angefordert: list[tuple[str, dict[str, object]]] = []
    panel.operationRequested.connect(lambda op, werte: angefordert.append((op, werte)))
    panel.show_feature(identifier, feature)

    titel = str(tr("Fläche versetzen"))
    assert titel in buttons(panel)
    zeile = next(row for row in panel._shown_rows.values() if row.op == "push_face")
    weg = zeile.widgets["distance"]
    assert weg.value_mm() == pytest.approx(0.0)
    assert panel.take_values("push_face", {"distance": -1.5})
    assert weg.value_mm() == pytest.approx(-1.5)
    press(panel, titel)
    assert angefordert == [("push_face", {"face": identifier, "distance": pytest.approx(-1.5)})]


def test_a_face_offers_the_seam_protection_toggle(qt_app: QApplication) -> None:
    """T8, §22.3: „Diese Fläche soll schön bleiben" — als Haken unter den Handlungen.

    Der Haken ist keine Operation und geht darum nicht über
    ``operationRequested``: Er meldet Merkmal und Stand, und was das Dokument
    daraus macht, entscheidet die Sitzung. Der heutige Stand kommt von außen
    — aus dem Dokument, nicht aus dem Bild.
    """
    identifier, feature = a_face()
    panel = FeaturePanel()
    gemeldet: list[tuple[str, bool]] = []
    panel.protectionToggled.connect(lambda key, on: gemeldet.append((key, on)))

    panel.show_feature(identifier, feature)
    haken = panel.protection_toggle()
    assert haken is not None and haken.isEnabled() and not haken.isChecked()
    assert haken.accessibleName() == "Vor Trennnähten schützen"
    assert haken.toolTip(), "der Haken sagt, was er tut"

    haken.setChecked(True)
    assert gemeldet == [(identifier, True)]

    panel.show_feature(identifier, feature, protected=True)
    wieder = panel.protection_toggle()
    assert wieder is not None and wieder.isChecked(), "der Stand kommt aus dem Dokument"
    assert gemeldet == [(identifier, True)], "der Aufbau meldet keine Geste"


def test_a_feature_without_triangles_hides_unavailable_protection(
    qt_app: QApplication,
) -> None:
    """Ein Merkmal ohne Fläche zeigt keinen wirkungslosen Schutzschalter."""
    feature = Feature(id="edge_1", kind="edge_loop", provenance="detected", params={})
    panel = FeaturePanel()
    panel.show_feature("edge_1", feature)

    haken = panel.protection_toggle()
    assert haken is None
    saetze = [
        widget.text()
        for widget in panel._built
        if isinstance(widget, QLabel) and "Dreiecke" in widget.text()
    ]
    assert not saetze


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
        assert "Strg+Z" in panel._every.accessibleDescription(), (
            f"{schluessel} ohne Rücknahmezusage"
        )


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
    previews: list[Any] = []

    def preview(op: str, params: dict[str, Any]) -> None:
        previews.append((op, params, panel.preview_targets(op)))
        panel.block_apply("Die Vorschau wird berechnet. Bitte das Ergebnis abwarten.")

    panel.valuesChanged.connect(preview)
    assert panel.preview_targets("move_feature") == ()
    panel._every.setChecked(True)
    assert len(previews) == 1 and not panel.can_accept()
    panel._apply.click()
    assert not fuer_alle and not einzeln
    panel.block_apply(None)
    panel._apply.click()

    assert not einzeln, "gesetzt heißt: nicht nur dieses eine"
    assert fuer_alle, "die Sammelhandlung wurde nicht gemeldet"
    op, params, ids = fuer_alle[-1]
    assert previews[-1] == (op, params, tuple(ids))
    from app.core.perceive.relations import alike_for_action

    group = alike_for_action(op, identifier, available, mesh)
    assert ids[0] == identifier
    assert set(ids) == {member.target for member in group.members}
    panel._every.setChecked(False)
    assert len(previews) == 2 and previews[-1][2] == ()
    assert not panel.can_accept()


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


def _panel_state(panel: FeaturePanel) -> list[Any]:
    """Alles, was ein Kunde oder ein Vorleser am Fenster ablesen kann — je Zeile.

    Werte, Grenzen, Einheit, Texte, Kurzhilfen, zugängliche Namen und
    Beschreibungen, Sichtbarkeit und Sperre; dazu die Handlungen hinter dem
    Knopf unten. Zwei Fenster mit gleichem Stand sind für den Kunden dasselbe
    Fenster, gleich wie sie entstanden sind.
    """
    from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox, QToolButton

    rows: list[Any] = []
    for row in panel._built:
        widgets: list[Any] = []
        for widget in (row, *row.findChildren(QWidget)):
            entry: list[Any] = [
                type(widget).__name__,
                widget.toolTip(),
                widget.statusTip(),
                widget.accessibleName(),
                widget.accessibleDescription(),
                widget.isVisibleTo(panel),
                widget.isEnabled(),
            ]
            if isinstance(widget, (QLabel, QPushButton, QToolButton, QCheckBox)):
                entry.append(widget.text())
            if isinstance(widget, QCheckBox):
                entry.append(widget.isChecked())
            if isinstance(widget, LengthSpin):
                entry.append(round(widget.value_mm(), 9))
            if isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                entry.extend((widget.value(), widget.minimum(), widget.maximum(), widget.suffix()))
            if isinstance(widget, QComboBox):
                entry.extend((widget.currentData(), widget.count()))
            widgets.append(entry)
        rows.append(widgets)
    runs = [(entry.title, entry.reason, entry.op, entry.members) for entry in panel._runs.values()]
    return [rows, runs, sorted(panel._explanations.values()), panel._armed_title.text()]


def test_the_next_hole_keeps_the_rows_and_reads_exactly_like_a_fresh_panel(
    qt_app: QApplication,
) -> None:
    """RM-204: Ein Merkmalklick baut nicht mehr alle Handlungen neu.

    Gemessen am 21.09.2026: ``show_feature`` leerte das Fenster und baute je
    Auswahl alle Zeilen neu — an einer Bohrung sechs Handlungen mit achtzehn
    Feldern. Am Halter mit Wabenmuster kostete das Aufbauen 14 ms je Klick,
    von 53 ms für das ganze Fenster (22.09.2026). Jetzt behält die nächste
    Bohrung die Zeilen der vorigen und schreibt nur ihre Werte hinein.

    **Und sieht dabei genau so aus wie frisch gebaut**: Werte, Grenzen,
    Kurzhilfe mit dem Ausgangswert (nicht doppelt), Namen, Erklärung —
    verglichen mit einem zweiten Fenster, das nur die zweite Bohrung kennt.
    """
    load_operations()
    mesh = plate()
    found = features.detect(mesh)
    (first_id, first), (second_id, second) = two_holes()
    panel = FeaturePanel()
    panel.show_feature(first_id, first, features=found, mesh=mesh)
    before = {id(row) for row in panel._built}
    boxes_before = [row for row in panel._built if row in panel._shown_rows]
    gemeldet: list[tuple[str, dict[str, object]]] = []
    panel.valuesChanged.connect(lambda op, params: gemeldet.append((op, params)))

    panel.show_feature(second_id, second, features=found, mesh=mesh)
    qt_app.processEvents()

    reused = [row for row in panel._built if id(row) in before]
    assert len(reused) == len(boxes_before) >= 5, "jede Handlungszeile bleibt dieselbe"
    assert not gemeldet, "das Füllen ist keine Eingabe — nichts wird gemeldet"

    fresh = FeaturePanel()
    fresh.show_feature(second_id, second, features=found, mesh=mesh)
    assert _panel_state(panel) == _panel_state(fresh)
    tips = [
        widget.toolTip()
        for row in panel._built
        for widget in row.findChildren(LengthSpin)
        if "Ausgangswert" in widget.toolTip()
    ]
    assert tips and all(tip.count("Ausgangswert") == 1 for tip in tips), tips

    # Die Wege der Zeile meinen das neue Merkmal: melden, ausführen.
    getan: list[tuple[str, dict[str, object]]] = []
    panel.operationRequested.connect(lambda op, params: getan.append((op, params)))
    move = row_of(panel, "Merkmal verschieben")
    spin = next(widget for widget in fields(move) if isinstance(widget, LengthSpin))
    spin.set_value_mm(spin.value_mm() + 1.5)
    assert gemeldet and gemeldet[-1][0] == "move_feature"
    assert gemeldet[-1][1]["at_feature"] == second_id
    press(panel, "Merkmal verschieben")
    assert getan and getan[-1][0] == "move_feature" and getan[-1][1]["at_feature"] == second_id


def test_the_core_answers_a_feature_once_per_evaluation(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hin- und herklicken fragt den Kern nicht jedes Mal neu (RM-181, Anteil Oberfläche).

    Hohlraumkette, Handlungen und Geschwister sind reine Funktionen von Körper
    und Merkmalsliste; am Halter mit Wabenmuster kostete ``actions_for`` je
    Bohrungsklick 22 ms (22.09.2026), und wer drei Bohrungen vergleicht,
    zahlte sie bei jedem Zurückklicken wieder. Eine neue Auswertung bringt
    eine neue Merkmalsliste — dann wird wieder gefragt.
    """
    from app.core.perceive import actions as actions_module

    load_operations()
    mesh = plate()
    found = features.detect(mesh)
    (first_id, first), (second_id, second) = two_holes()
    asked: list[str] = []
    original = actions_module.actions_for

    def counted(feature: Feature, *args: Any, **kwargs: Any) -> Any:
        asked.append(feature.id)
        return original(feature, *args, **kwargs)

    monkeypatch.setattr(actions_module, "actions_for", counted)
    panel = FeaturePanel()
    for identifier, feature in ((first_id, first), (second_id, second)) * 3:
        panel.show_feature(identifier, feature, features=found, mesh=mesh)
    assert asked == [first_id, second_id], asked
    assert [entry.op for entry in panel._runs.values()][:2] == ["move_feature", "resize_hole"]

    again = dict(found)
    panel.show_feature(first_id, again[first_id], features=again, mesh=mesh)
    assert asked[-1] == first_id and len(asked) == 3, "eine neue Merkmalsliste fragt neu"


def test_an_answer_from_the_worker_builds_the_panel_without_asking_the_core(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Was der Arbeiter geantwortet hat, baut dasselbe Fenster wie die eigene Frage (RM-232).

    An einem großen Körper rechnet ``feature_answers`` im Arbeiter, und das
    Fenster bekommt die Antwort über ``remember_answers``, bevor es aufbaut.
    Der Aufbau fragt den Kern dann nicht noch einmal — sonst wäre der Weg in
    den Arbeiter umsonst —, und er zeigt Zeile für Zeile, was ein Fenster
    zeigt, das selbst gefragt hat. Eine andere Merkmalsliste erbt nichts.
    """
    from app.core.perceive import actions as actions_module
    from app.ui.panels import feature_answers

    load_operations()
    mesh = plate()
    found = features.detect(mesh)
    hole_id = next(key for key, value in found.items() if value.kind == "hole")
    hole = found[hole_id]
    asked = FeaturePanel()
    asked.show_feature(hole_id, hole, features=found, mesh=mesh)
    answers = feature_answers(hole_id, hole, found, mesh)
    panel = FeaturePanel()
    assert panel.known_answers(hole_id, hole, found, mesh) is None

    panel.remember_answers(hole_id, hole, found, mesh, answers)
    monkeypatch.setattr(
        actions_module, "actions_for", lambda *_a, **_k: pytest.fail("der Kern wurde gefragt")
    )
    panel.show_feature(hole_id, hole, features=found, mesh=mesh)

    assert panel.known_answers(hole_id, hole, found, mesh) is answers
    assert panel.known_answers(hole_id, hole, dict(found), mesh) is None
    assert _panel_state(panel) == _panel_state(asked)


def test_the_waiting_panel_names_the_feature_and_offers_nothing(qt_app: QApplication) -> None:
    """Bis die Handlungen da sind, stehen Name, Maß und ein Satz — und keine Zeile (RM-232)."""
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QLabel

    from app.i18n import tr
    from app.ui.panels import cavity_name, feature_measure

    load_operations()
    mesh = plate()
    found = features.detect(mesh)
    hole_id = next(key for key, value in found.items() if value.kind == "hole")
    panel = FeaturePanel()
    try:
        panel.show_feature(hole_id, found[hole_id], features=found, mesh=mesh)
        assert panel._runs, "vorher bot das Fenster etwas an"

        panel.show_pending(hole_id, found[hole_id])

        texts = [label.text() for label in panel.findChildren(QLabel) if label.isVisibleTo(panel)]
        # Die Herkunft nur, wenn sie warnt (RM-510): knappe Maßzeile.
        measure = feature_measure(found[hole_id], compact=True)
        heading = f"{cavity_name(hole_id, found[hole_id], ())}  ·  {measure}"
        assert heading in texts
        assert tr("Die Handlungen werden ermittelt …") in texts
        assert not panel._runs, "keine Zeile, die etwas anbietet"
    finally:
        # **Gelöscht, solange die Hülle hier lebt.** Die Zeilen, die
        # ``show_pending`` per ``deleteLater`` wegräumt, halten über ihre
        # Signale Verweise auf das Fenster. Ohne Elternteil hing seine Hülle
        # danach nur noch an ihnen: Im Abbau der Suite fiel der letzte
        # Verweis mitten in der Zustellung ihrer Löschung, Python löschte das
        # Fenster samt noch wartender Geschwister, und der Prozess endete mit
        # „Fatal Python error: Aborted“ — seit dem Entstehen des Tests, drei
        # von drei gebunden. Im Programm hat das Fenster einen Elternteil.
        panel.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_a_hole_heading_leaves_its_measure_to_the_sentence_below(qt_app: QApplication) -> None:
    """Der Kopf nennt die Bohrung, der Satz darunter ihr Maß — einmal (RM-516).

    „Bohrung 1 · Ø5,20 mm · eingepasst“ stand über „Bohrungsmaß: 5,20 mm
    (eingepasst). Passt vermutlich zu M5“: derselbe Durchmesser samt Herkunft
    zweimal untereinander.
    """
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QLabel

    from app.ui.labels import length
    from app.ui.panels import cavity_name

    load_operations()
    mesh = plate()
    found = features.detect(mesh)
    hole_id = next(key for key, value in found.items() if value.kind == "hole")
    hole = found[hole_id]
    panel = FeaturePanel()
    try:
        panel.show_feature(hole_id, hole, features=found, mesh=mesh)
        built = [widget.text() for widget in panel._built if isinstance(widget, QLabel)]
        assert built[0] == cavity_name(hole_id, hole, ()), "der Kopf nennt nur die Bohrung"
        diameter = length(float(hole.params["diameter"]), with_unit=False)
        assert any(diameter in text for text in built[1:]), "das Maß steht im Satz darunter"
    finally:
        panel.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_a_partly_reused_panel_matches_a_fresh_one_and_tabs_like_the_eye(
    qt_app: QApplication,
) -> None:
    """Vom Stift zum Ring: vier Handlungen bleiben, *Maße ändern* hat andere Felder.

    Die neue Zeile entsteht nach den wiederverwendeten, steht im Fenster aber
    an zweiter Stelle. Qt führte die Fokuskette in der Reihenfolge der
    Entstehung; ohne neu gezogene Kette sprang die Tabulatortaste von der
    letzten alten Zeile zurück nach oben (RM-204). Und eine Zeile, die beim
    Messen im Bild weggenommen war (RM-199), kommt sichtbar zurück.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLineEdit

    from tests.helpers import ridged_shaft

    load_operations()
    # Der Schaft mit freistehendem Wulst: Der Wulst an ``post_with_fillet``
    # lässt sich nicht vom Körper trennen, dort sagt seit RM-535 jede Zeile ab.
    shaft = ridged_shaft("mesh", recess=False)
    mesh = as_mesh_data(shaft.mesh)
    found = shaft.features
    pin_id = next(key for key, value in found.items() if value.kind == "pin")
    torus_id = next(key for key, value in found.items() if value.kind == "torus")
    panel = FeaturePanel()
    panel.show_feature(pin_id, found[pin_id], features=found, mesh=mesh)
    panel.set_measuring(True, op="move_feature")
    panel.set_measuring(False)
    panel.set_measuring(True, op="move_feature")
    kept = {id(row) for row in panel._built}

    panel.show_feature(torus_id, found[torus_id], features=found, mesh=mesh)
    panel.set_measuring(False)
    qt_app.processEvents()

    assert sum(id(row) in kept for row in panel._built) == 4, "vier von fünf Zeilen bleiben"
    fresh = FeaturePanel()
    fresh.show_feature(torus_id, found[torus_id], features=found, mesh=mesh)
    assert _panel_state(panel) == _panel_state(fresh)

    def a_stop(widget: QWidget) -> bool:
        # Das Textfeld im Drehfeld und die Liste im Aufklappfenster einer
        # Auswahl sind Innenleben, keine Halte.
        return (
            widget.focusPolicy() != Qt.FocusPolicy.NoFocus
            and not isinstance(widget, QLineEdit)
            and widget.window() is panel.window()
        )

    stops = [
        child
        for row in panel._built
        for child in (row, *row.findChildren(QWidget))
        if a_stop(child)
    ]
    assert len(stops) > 6
    for first, second in pairwise(stops):
        node = first.nextInFocusChain()
        while not a_stop(node):
            node = node.nextInFocusChain()
        assert node is second, (
            f"nach {first.accessibleName() or type(first).__name__} kommt "
            f"{node.accessibleName() or type(node).__name__} statt "
            f"{second.accessibleName() or type(second).__name__}"
        )


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
    halbe Auskunft. Das Maß trägt seine Einheit (RM-516): Ohne sie las sich der
    Satz in Zoll als Millimeter.
    """
    from app.core.scene.placement import bore_advice

    identifier, feature = a_hole()
    from app.ui.labels import length, localised

    diameter = float(feature.params["diameter"])
    erwartet, _choices = bore_advice(
        diameter, feature=feature, ask=False, measured=length(diameter)
    )

    panel = FeaturePanel()
    panel.show_feature(identifier, feature)

    texte = " ".join(row.text() for row in panel._built if isinstance(row, QLabel))
    assert erwartet in texte, texte
    # Zwei Nachkommastellen in Millimetern (``units._UNIT_DECIMALS``), dahinter die Einheit.
    assert f"{localised(f'{diameter:.2f}')} mm" in texte, texte


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
    Bedeutung noch von unten nach, beim zweiten nicht mehr (Bildschirmfoto
    eines Kunden, gemessen von 3d-druck-4d am 04.09.2026).

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
        # Vorn der Pfeil, der die Handlung aufklappt (RM-510), gleich dahinter
        # ihr Titel — beide vor den Feldern, und der Pfeil heißt für den
        # Bildschirmleser wie die Handlung.
        from PySide6.QtWidgets import QToolButton

        pfeil, titel = kopf.itemAt(0).widget(), kopf.itemAt(1).widget()
        assert isinstance(pfeil, QToolButton) and pfeil.objectName() == "actionHeading"
        assert pfeil.accessibleName() == "Merkmal verschieben"
        assert isinstance(titel, QLabel) and titel.text() == "Merkmal verschieben", (
            f"nach dem Pfeil steht {titel!r} statt der Überschrift"
        )
    finally:
        panel.deleteLater()


def test_a_nearly_nominal_bore_explains_why_it_is_not_assigned(qt_app: QApplication) -> None:
    """Gleich gerundete 2-mm-Maße dürfen keine unerklärlich verschiedenen Normaussagen tragen."""
    from dataclasses import replace

    identifier, feature = a_hole()
    panel = FeaturePanel()
    # Die Nennmaß-Auskunft gilt einem **belegten** Maß: Eine eingepasste Bohrung
    # (``fit``) nennt eine Größe nur als Einschätzung („passt vermutlich") —
    # hier steht die Frage nach der Rundung, also ein nativ gelesenes Maß.
    nearly = replace(
        feature,
        params={**feature.params, "diameter": 1.9999},
        measure_sources={**feature.measure_sources, "diameter": "native"},
    )
    panel.show_feature(identifier, nearly)
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


@pytest.mark.parametrize("op", ["create_lid", "screw_lid"])
def test_a_lid_step_opens_in_the_feature_panel(qt_app: QApplication, op: str) -> None:
    """Ein Klick auf Kragen oder Öffnung eines Deckels zeigt seinen Schritt (Review RM-526, B1).

    Mit der leeren Höhe der Öffnung warf ``show_part`` ``TypeError``: *Baustein
    verschieben* bot ``z`` mit dem Wert ``None`` an. Ein Deckel hat keine Lage in
    der Ebene, also keine Verschiebung; Maße ändern und Entfernen bleiben.
    """
    from types import SimpleNamespace

    from app.core.bootstrap import load_operations
    from app.ui.panels import FeaturePanel

    load_operations()
    spec = REGISTRY.get(op)
    panel = FeaturePanel()
    try:
        for params in ({}, {"z": None}):
            panel.show_part(SimpleNamespace(id=4, op=op, params=params), spec)
            titles = buttons(panel)
            assert "Baustein verschieben" not in titles, titles
            assert "Baustein entfernen" in titles, titles
    finally:
        panel.deleteLater()


def test_a_count_is_a_whole_number_without_a_unit(qt_app: QApplication) -> None:
    """Die Haken eines Einhängers sind eine Anzahl — kein Maß in Millimetern.

    ``count`` und ``steps`` des Lochwand-Einhängers sind ganze Zahlen ohne
    Einheit. Als ``length`` bekamen sie im Merkmalfenster ein Längenfeld:
    „Anzahl: 2,00 mm", in Zoll „0,08 in" — und gingen als ``4.0`` in den
    Schritt zurück (Sonde über alle Bausteine, 14.09.2026). Der Kern nennt die
    Art jetzt ``count``, das Fenster baut dafür ein Ganzzahlfeld, und was
    zurückgeht, ist eine ganze Zahl.
    """
    from types import SimpleNamespace

    from app.core.perceive.actions import part_actions

    load_operations()
    spec = REGISTRY.get("insert_pegboard_hook")
    step = SimpleNamespace(
        id=5, op="insert_pegboard_hook", params={"count": 2, "steps": 1, "x": 4.0}
    )
    fields = {field.name: field for action in part_actions(step, spec) for field in action.fields}
    assert fields["count"].kind == "count", fields["count"]
    assert fields["steps"].kind == "count", fields["steps"]

    panel = FeaturePanel()
    changed: list[tuple[int, dict]] = []
    panel.stepChangeRequested.connect(lambda op_id, params: changed.append((op_id, params)))
    try:
        panel.show_part(step, spec)
        counts = [
            editor
            for editor in panel.findChildren(BoundedSpin)
            if editor.accessibleName().startswith("Maße ändern — ")
        ]
        assert len(counts) == 2, [editor.accessibleName() for editor in counts]
        for editor in counts:
            assert editor.suffix() == "", "eine Anzahl trägt keine Einheit"
            assert editor.decimals() == 0, "eine Anzahl bleibt ganzzahlig"
        counts[0].setValue(4)
        press(panel, "Maße ändern")
        assert len(changed) == 1
        _op_id, params = changed[0]
        assert params["count"] == 4 and isinstance(params["count"], int), params
        assert isinstance(params["steps"], int), params
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

    # Seit dem 20.09.2026 geht auch dieser Weg durch die Vorschaufreigabe
    # (``_preview_can_apply``) und räumt die Merkmalsvorschau ab; hier gilt
    # beides als erledigt, geprüft wird das Zusammensetzen der Werte.
    fenster = SimpleNamespace(
        session=SimpleNamespace(
            project=SimpleNamespace(document=SimpleNamespace(ops=[schritt])),
            change_params=lambda op_id, params: geschrieben.append((op_id, params)),
        ),
        feature_panel=object(),
        _quiet_host=None,
        _preview_can_apply=lambda owner, order: True,
        _drop_feature_preview=lambda: None,
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

    gerufen: list[Any] = []
    schritt = SimpleNamespace(id=5, op="insert_keyhole", params={"size": "M5", "drop": 9.0})
    panel = SimpleNamespace(
        step_for_action=lambda op: 5, preview_targets=lambda op: (), shown_part_step=lambda: 5
    )
    # Seit dem 20.09.2026 baut die Vorschau einen Auftrag (``_PreviewOrder``)
    # und reicht ihn an die Freigabe; geprüft wird die Weiche davor — der
    # Auftrag nennt den Schritt, nicht einen zweiten Baustein daneben.
    fenster = SimpleNamespace(
        _feature_pending=("insert_keyhole", {"size": "M5"}),
        feature_panel=panel,
        _quiet_host=None,
        _quiet_order=None,
        object_tree=SimpleNamespace(selected=lambda: "obj_1"),
        session=SimpleNamespace(history=SimpleNamespace(operation=lambda op_id: schritt)),
        _set_preview_order=lambda owner, order: gerufen.append(order) or order,
        _request_order_preview=lambda approval: None,
    )
    fenster._prepare_feature_order = lambda op, params: MainWindow._prepare_feature_order(
        fenster, op, params
    )

    MainWindow._preview_feature_change(fenster)
    assert len(gerufen) == 1, gerufen
    assert gerufen[0].change_op == 5 and gerufen[0].drafts == ()
    assert gerufen[0].change_values == {"size": "M5", "drop": 9.0}

    # Und ohne Baustein bleibt es beim Entwurf neben der Szene.
    gerufen.clear()
    panel.step_for_action = lambda op: None
    fenster._feature_pending = ("resize_hole", {"diameter": 6.0})
    MainWindow._preview_feature_change(fenster)
    assert len(gerufen) == 1 and gerufen[0].drafts, gerufen
    assert gerufen[0].change_op is None


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
    from tests.helpers import exact_kernel

    # Ohne geladenes Register ist die Grundmenge leer, und der Test wäre grün,
    # ohne eine Handlung gesehen zu haben.
    exact_kernel()
    load_operations()
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
    erwartet = {str(REGISTRY.get(name).title) for name, _feld in EDGE_OPERATIONS}
    erwartet |= {str(titel) for _name, titel, _felder, _fest in EDGE_VARIANTS}
    assert set(knoepfe) == erwartet, (
        "an einer Kante steht genau, was EDGE_OPERATIONS und EDGE_VARIANTS nennen"
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


def test_the_chamfer_edge_row_carries_the_kind_and_its_fields_from_the_register() -> None:
    """Die Fase an einer Kante führt Art, zweiten Abstand, Winkel und Seitentausch (P6.2).

    Aus dem Register und nicht aus einer Liste hier: Vorgaben, Grenzen,
    Einheiten und die Bedingung ``depends_on`` reisen unverändert mit. Die
    Breite bleibt vorn, damit eine Fase mit gleicher Breite so aussieht wie
    bisher; *Verrunden* und *Wulst* behalten ihr eines Maß.
    """
    from tests.helpers import exact_kernel

    exact_kernel()
    load_operations()
    key = "e:-20.00,0.00,20.00:0.000,1.000,0.000"
    rows: dict[str, Any] = {}
    for action in actions.edge_actions(key):
        # Die Grundzeile je Operation; Varianten (EDGE_VARIANTS) folgen danach.
        rows.setdefault(str(action.op), action)

    chamfer = rows["chamfer_edges"]
    names = [field.name for field in chamfer.fields]
    assert names == ["distance", "mode", "second_distance", "angle", "flip_sides"]
    schema = {entry.name: entry for entry in REGISTRY.get("chamfer_edges").params.spec()}
    for field in chamfer.fields:
        entry = schema[field.name]
        assert field.value == entry.default, field.name
        assert field.depends_on == entry.depends_on, field.name
        assert field.minimum == entry.minimum and field.maximum == entry.maximum, field.name
    by_name = {field.name: field for field in chamfer.fields}
    assert by_name["mode"].kind == "choice"
    assert [value for value, _text in by_name["mode"].choices] == list(schema["mode"].choices)
    assert by_name["angle"].kind == "angle"
    assert by_name["flip_sides"].kind == "bool"
    assert by_name["mode"].value == "equal_distances", "eine neue Fase ist gleich breit wie bisher"
    assert dict(chamfer.fixed) == {"edges": "named", "edge_keys": key}

    for name, measure in EDGE_OPERATIONS:
        if name != "chamfer_edges" and name in rows:
            assert [field.name for field in rows[name].fields] == [measure], name


def _chamfer_editor(panel: FeaturePanel, label: str) -> QWidget:
    """Das Feld der Fasenzeile mit dieser Beschriftung — über seinen zugänglichen Namen."""
    title = str(REGISTRY.get("chamfer_edges").title)
    wanted = f"{title} — {label}"
    found = [widget for widget in panel.findChildren(QWidget) if widget.accessibleName() == wanted]
    assert len(found) == 1, f"{wanted!r}: {len(found)} Felder"
    return found[0]


def test_the_chamfer_row_at_an_edge_shows_only_the_fields_of_its_kind(
    qt_app: QApplication,
) -> None:
    """Art wählen, und die Zeile zeigt, was dazugehört — wie der Operationsdialog (P6.2).

    Gleiche Breite: nur Breite und Art. Zwei Abstände: dazu der zweite Abstand
    und *Seiten tauschen*. Abstand und Winkel: der Winkel statt des zweiten
    Abstands. Die Zahlenfelder sind die des Dialogs (``ValueField``) und
    nehmen einen Ausdruck an; jedes trägt einen Namen mit der Handlung.
    Übernommen wird ein Schritt mit allen Werten und der angeklickten Kante;
    *Seiten tauschen* von außen (die Marke im Bild) geht über denselben Haken.
    """
    from app.ui.op_dialog import ValueField
    from tests.helpers import exact_kernel

    exact_kernel()
    load_operations()
    schema = {entry.name: entry for entry in REGISTRY.get("chamfer_edges").params.spec()}
    key = "e:-20.00,0.00,20.00:0.000,1.000,0.000"
    panel = FeaturePanel()
    gemeldet: list[tuple[str, dict[str, Any]]] = []
    gerufen: list[tuple[str, dict[str, Any]]] = []
    panel.valuesChanged.connect(lambda op, werte: gemeldet.append((op, dict(werte))))
    panel.operationRequested.connect(lambda op, werte: gerufen.append((op, dict(werte))))

    panel.show_edge(key, "Waagerecht · 30,00 mm", parameter_values={"b": 1.5})

    breite = _chamfer_editor(panel, str(schema["distance"].title))
    art = _chamfer_editor(panel, str(schema["mode"].title))
    zweiter = _chamfer_editor(panel, str(schema["second_distance"].title))
    winkel = _chamfer_editor(panel, str(schema["angle"].title))
    tauschen = _chamfer_editor(panel, str(schema["flip_sides"].title))
    assert isinstance(breite, ValueField) and isinstance(zweiter, ValueField)
    assert isinstance(winkel, ValueField), "Winkel mit derselben Einheit wie im Dialog"
    assert isinstance(art, QComboBox) and isinstance(tauschen, QCheckBox)

    def gezeigt() -> set[str]:
        return {
            name
            for name, editor in (("second", zweiter), ("angle", winkel), ("flip", tauschen))
            if not editor.isHidden()
        }

    assert gezeigt() == set(), "gleiche Breite: nur Breite und Art"
    assert not panel.toggle_field("chamfer_edges", "flip_sides"), (
        "bei gleicher Breite gibt es nichts zu tauschen"
    )

    art.setCurrentIndex(art.findData("two_distances"))
    assert gezeigt() == {"second", "flip"}
    assert gemeldet[-1][0] == "chamfer_edges" and gemeldet[-1][1]["mode"] == "two_distances"
    beschriftung = {label.buddy(): label for label in panel.findChildren(QLabel) if label.buddy()}
    assert not beschriftung[zweiter].isHidden(), "die Beschriftung kommt mit dem Feld"
    assert beschriftung[winkel].isHidden(), "und geht mit ihm"

    art.setCurrentIndex(art.findData("distance_angle"))
    assert gezeigt() == {"angle", "flip"}
    art.setCurrentIndex(art.findData("two_distances"))

    # Die Namen: keiner leer, keiner doppelt, jeder mit der Handlung.
    namen = [editor.accessibleName() for editor in (breite, art, zweiter, winkel, tauschen)]
    assert len(set(namen)) == len(namen)
    assert all(name.startswith(str(REGISTRY.get("chamfer_edges").title)) for name in namen)

    # Die Fokuskette geht die Zeile hinunter wie das Auge: Breite, Art,
    # zweiter Abstand, Seitentausch.
    reihenfolge: list[QWidget] = []
    halt = breite.focusProxy() or breite
    for _ in range(40):
        halt = halt.nextInFocusChain()
        for editor in (art, zweiter, tauschen):
            if (halt is editor or editor.isAncestorOf(halt)) and editor not in reihenfolge:
                reihenfolge.append(editor)
    assert reihenfolge == [art, zweiter, tauschen]

    zweiter.set_value(0.5)
    breite.set_value("=@b * 2")
    assert panel.toggle_field("chamfer_edges", "flip_sides")
    assert tauschen.isChecked()
    assert gemeldet[-1][1]["flip_sides"] is True, "der Tausch meldet sich wie ein Klick"

    press(panel, str(REGISTRY.get("chamfer_edges").title))

    assert len(gerufen) == 1
    op, werte = gerufen[0]
    assert op == "chamfer_edges"
    assert werte["edges"] == "named" and werte["edge_keys"] == key
    assert werte["mode"] == "two_distances"
    assert werte["second_distance"] == pytest.approx(0.5)
    assert werte["distance"] == "=@b * 2", "der Ausdruck geht als Ausdruck in den Schritt"
    assert werte["flip_sides"] is True
    # Jeder Wert ist ein Parameter der Operation — keiner, den sie nicht kennt.
    validate(REGISTRY.get("chamfer_edges").params, {**werte, "distance": 3.0})


def test_the_edge_panel_offers_a_variable_fillet_with_start_and_end(
    qt_app: QApplication,
) -> None:
    """P6.1: „Verrunden mit Verlauf" an der angeklickten Kante — zwei Felder, ein Schritt.

    Die Zeile führt dieselbe Operation wie *Verrunden*, mit Radius am Anfang
    und am Ende und dem Verlauf fest eingestellt. Gedrückt wird der echte
    Knopf; was hinausgeht, ist der Auftrag, den die Auswertung rechnet.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    schluessel = "e:-20.00,0.00,20.00:0.000,1.000,0.000"
    panel = FeaturePanel()
    gerufen: list[tuple[str, dict[str, Any]]] = []
    panel.operationRequested.connect(lambda op, werte: gerufen.append((op, dict(werte))))

    panel.show_edge(schluessel, "Waagerecht · 30,00 mm · x -20,00, y 0,00")
    press(panel, str(EDGE_VARIANTS[0][1]))

    assert len(gerufen) == 1
    op, werte = gerufen[0]
    assert op == "fillet_edges"
    assert werte["mode"] == "variable_radius"
    assert werte["edges"] == "named" and werte["edge_keys"] == schluessel
    schema = {e.name: e for e in REGISTRY.get("fillet_edges").params.spec()}
    assert werte["radius"] == pytest.approx(float(schema["radius"].default))
    assert werte["end_radius"] == pytest.approx(float(schema["end_radius"].default))


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

    **Die fünf sitzen seit dem 13.09.2026 in einem eigenen Widget**
    (``footer``), damit ein Träger sie aus dem Rollinhalt heben kann; ihre
    Reihenfolge zueinander gilt dort weiter, und die Zeile als Ganzes steht
    unter den Handlungen.
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
    assert plaetze[panel.footer()] > max(zeilen), "die Knopfzeile steht über den Handlungen"

    unten = panel.footer().layout()
    assert unten is not None
    ordnung = {unten.itemAt(index).widget(): index for index in range(unten.count())}
    assert ordnung[panel._every] == ordnung[panel._apply] - 1, (
        "der Haken gehört unmittelbar über den Knopf"
    )
    # **Und der Weg ins Bild steht davor, nicht dazwischen** (11.09.2026): Der
    # Haken ändert den Umfang des Übernehmens, also gehört er an dessen Seite;
    # ein Knopf zwischen beiden machte aus „für alle" eine Frage, auf die zwei
    # Knöpfe antworten.
    assert ordnung[panel._in_view] < ordnung[panel._every], "der Weg ins Bild steht davor"


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


def test_the_wheel_over_an_unfocused_field_rolls_the_panel_and_not_the_value(
    qt_app: QApplication,
) -> None:
    """Rollen im Merkmalfenster drehte Werte, sobald der Zeiger über einem Feld lag.

    Robert, 16.09.2026: „hier sollten wir erst reinklicken müssen". Ohne Fokus
    geht die Radraste an den Rollbereich, mit Fokus an das Feld — wie es die
    Regel in ``oberflaeche.md`` beschreibt.

    **Gerollt wird hier nicht gemessen, und das ist kein Versäumnis:** Qt
    reicht nur *spontane* Radereignisse — die vom Fenstersystem — an das
    Elternteil weiter; ein gesendetes bleibt beim Empfänger, damit ein
    Rollbereich seine eigenen Weiterleitungen nicht zurückbekommt. Geprüft
    wird deshalb, woran Qt die Weiterleitung knüpft: Das Feld lässt das
    Ereignis **unangenommen**, und seine Fokusregel gibt dem Rad keinen Fokus.
    """
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent

    key, feature = a_hole()
    mesh = plate()
    panel = FeaturePanel()
    scroller = QScrollArea()
    scroller.setWidget(panel)
    scroller.setWidgetResizable(True)
    scroller.resize(320, 160)
    scroller.show()
    panel.show_feature(key, feature, features=features.detect(mesh), mesh=mesh)
    layout = panel.layout()
    assert layout is not None
    layout.activate()
    # Zweimal: Der Rollbereich legt seine Balken erst im nächsten Umlauf nach.
    QApplication.processEvents()
    QApplication.processEvents()
    bar = scroller.verticalScrollBar()
    assert bar.maximum() > 0, "Voraussetzung: das Fenster rollt überhaupt"
    spin = next(field for field in panel.findChildren(LengthSpin) if field.isVisibleTo(panel))
    before = spin.value_mm()

    def a_notch_down() -> QWheelEvent:
        centre = spin.rect().center()
        return QWheelEvent(
            QPointF(centre),
            QPointF(spin.mapToGlobal(centre)),
            QPoint(),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )

    assert not spin.hasFocus(), "Voraussetzung: niemand hat ins Feld geklickt"
    assert spin.focusPolicy() == Qt.FocusPolicy.StrongFocus, "das Rad nimmt keinen Fokus"
    unfocused = a_notch_down()
    QApplication.sendEvent(spin, unfocused)
    assert spin.value_mm() == before, "ohne Fokus bleibt der Wert stehen"
    assert not unfocused.isAccepted(), "und die Raste bleibt frei für den Rollbereich"

    scroller.activateWindow()
    spin.setFocus(Qt.FocusReason.MouseFocusReason)
    QApplication.processEvents()
    assert spin.hasFocus(), "Voraussetzung: der Klick ins Feld gibt den Fokus"
    focused = a_notch_down()
    QApplication.sendEvent(spin, focused)
    assert spin.value_mm() != before, "mit Fokus dreht das Rad den Wert"
    assert focused.isAccepted(), "und das Feld hat die Raste genommen"
    scroller.close()


def test_a_bound_part_still_offers_moving_and_removing(qt_app: QApplication) -> None:
    """Ein Baustein, dessen Lage an einem Parameter hängt, zeigt alle drei Handlungen.

    Das Beispielprojekt bindet die Höhe jedes Bausteins an ``@staerke``, und
    ``float("=@staerke")`` beendete den Aufbau mitten in der Liste: Rechts
    stand nur noch *Maße ändern*, ohne Verschieben und ohne Entfernen (Robert,
    16.09.2026: „bei manchen bausteinen keine möglichkeit zum verschieben").
    Das gebundene Feld bekommt jetzt dasselbe Ausdrucksfeld wie der
    Operationsdialog, und ein Übernehmen gibt den Ausdruck unverändert zurück
    — die Bindung überlebt die Bedienung (§13).
    """
    from types import SimpleNamespace

    from app.core.bootstrap import load_operations
    from app.ui.op_dialog import ValueField
    from app.ui.panels import FeaturePanel

    load_operations()
    spec = REGISTRY.get("insert_screw_hole")
    step = SimpleNamespace(
        id=2, op="insert_screw_hole", params={"size": "M4", "x": -20.0, "z": "=@staerke"}
    )

    panel = FeaturePanel()
    changed: list[tuple[int, dict]] = []
    panel.stepChangeRequested.connect(lambda op_id, params: changed.append((op_id, params)))
    try:
        panel.show_part(step, spec, parameter_values={"staerke": 6.0})

        titles = buttons(panel)
        assert titles == ["Maße ändern", "Baustein verschieben", "Baustein entfernen"], titles

        bound = [
            widget for widget in panel.findChildren(ValueField) if widget.value() == "=@staerke"
        ]
        assert len(bound) == 1, "die gebundene Achse trägt das Ausdrucksfeld"

        press(panel, "Baustein verschieben")
        assert len(changed) == 1, changed
        op_id, params = changed[0]
        assert op_id == 2
        assert params["z"] == "=@staerke", "der Ausdruck kommt unverändert zurück"
        assert params["x"] == pytest.approx(-20.0)
    finally:
        panel.deleteLater()


def test_a_divider_leads_to_the_organizer_not_to_its_face(qt_app: QApplication) -> None:
    """Wer eine Trennwand anklickt, hat den Organizer gemeint.

    **Befund Robert, 18.09.2026:** „Baustein verschieben bei Trennwand
    organizer keine Wirkung" und „organiser über Baustein komplett samt
    Trennwände erstellen über organiser editor, falls es einen gibt keine
    Ahnung wie man hinkommt". Ein Organizer bringt je Fach und je Trennwand
    Merkmale mit; an einer Trennwandfläche standen die Handlungen einer
    Fläche — Bohren, Tasche, Fläche versetzen. Keine davon meint die
    Trennwand, und ihre Lage steht in keinem Parameter: Sie folgt aus den
    Fachmaßen, und die ändert der Fächereditor.

    Dieselbe Regel wie beim Baustein, nur über :data:`SPEAKS_FOR_ITS_FEATURES`
    statt über die Kategorie — der Organizer steht unter ``primitive``, weil
    er aus eigenen Maßen entsteht.
    """
    from app.core.bootstrap import load_operations
    from app.core.knowledge import profiles
    from app.core.perceive.actions import part_actions
    from app.core.scene import History, OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import new_project
    from app.i18n import _
    from app.ui.panels import part_step_of

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    History(document).apply(_("Organizer"), [OperationDraft(op="create_organizer", params={})])
    scene = evaluate(document, profiles.make_profile("centauri-carbon-2", "petg")).scene
    body = next(iter(scene.objects.values()))

    divider = next(
        name
        for name, feature in body.features.items()
        if feature.params.get("organizer_role") == "divider"
    )
    # **Das Merkmal gehört zur Frage**, nicht nur sein Schritt: Beim Baustein
    # spricht der ganze Schritt für jedes seiner Merkmale, beim Organizer nur
    # für die Rollen in :data:`SPEAKS_FOR_ITS_FEATURES` — ``organizer_base``
    # und die Böden behalten ihre eigenen Flächenhandlungen.
    step = part_step_of(body.features[divider].created_by, document, body.features[divider])
    assert step is not None, "eine Trennwand führt zu ihrem Schritt"

    floor = next(
        (
            feature
            for feature in body.features.values()
            if feature.params.get("organizer_role") == "floor"
        ),
        None,
    )
    assert floor is not None, "die Voraussetzung: der Organizer hat auch Böden"
    assert part_step_of(floor.created_by, document, floor) is None, (
        "ein Boden ist eine Fläche und führt nicht zum Fächereditor"
    )

    actions = part_actions(*step)
    measures = next(action for action in actions if action.fields)
    assert {field.name for field in measures.fields} == {"width", "depth", "height"}
    assert not any(field.name == "layout" for field in measures.fields), (
        "eine Fachaufteilung ist kein Zahlenfeld"
    )
    assert measures.elsewhere, "und der Weg zu ihr steht daneben"


def test_measure_fields_keep_the_bound_feature_after_the_panel_changes(
    qt_app: QApplication,
) -> None:
    """Der Feldleser hält die ausgewählte Bohrung, auch wenn die Karte neu aufgebaut wird."""
    from app.ui.panels import feature_field_values

    identifier, feature = a_hole()
    panel = FeaturePanel()
    owner = QWidget()
    try:
        panel.show_feature(identifier, feature)
        built = panel.measure_fields("resize_hole", owner, feature=feature)
        assert built is not None
        action, group, editors = built
        editors["diameter"].set_value_mm(9.0)
        panel.show_feature("other-hole", replace(feature, id="other-hole"))
        values = feature_field_values(action.fields, editors, action.fixed, feature_id=identifier)
        assert values["at_feature"] == identifier
        assert values["diameter"] == pytest.approx(9.0)
        assert all(editor.accessibleName() for editor in editors.values())
        # Die Tiefe ist seit dem 23.09.2026 ein Feld mit dem gemessenen Wert —
        # und steht nicht mehr zusätzlich als gesperrte Auskunft daneben.
        if "depth" in feature.params:
            assert values["depth"] == pytest.approx(float(feature.params["depth"]))
        assert not any(
            label.accessibleName() == "Gemessene Tiefe" for label in group.findChildren(QLabel)
        )
    finally:
        owner.close()
        owner.deleteLater()
        panel.close()
        panel.deleteLater()


@pytest.mark.parametrize("provenance", ["generated", "detected"])
def test_measure_source_is_shared_by_tree_caption_fields_and_accessibility(
    qt_app: QApplication, provenance: str
) -> None:
    """Der Zielwert ist editierbar, die Aussage zum vorhandenen Fit bleibt dieselbe."""
    from app.ui.panels import _feature_tip

    identifier, original = a_hole()
    feature = replace(
        original,
        provenance=provenance,  # type: ignore[arg-type]
        params={**original.params, "diameter": 8.012345},
        measure_sources={**original.measure_sources, "diameter": "fit"},
    )
    panel = FeaturePanel()
    owner = QWidget()
    try:
        panel.show_feature(identifier, feature)
        built = panel.measure_fields("resize_hole", owner, feature=feature)
        assert built is not None
        _action, group, editors = built
        caption = group.findChild(QLabel, "feature-measure-source")
        assert caption is not None and "eingepasst" in caption.text()
        editor = editors["diameter"]
        hint = editor.toolTip()
        assert "Ausgangswert:" in hint and "eingepasst" in hint
        assert "Konstruktionsmaß ist nicht bekannt" in hint
        assert editor.accessibleDescription() == hint and not editor.statusTip()
        assert "eingepasst" in _feature_tip(identifier, feature, None)
        editor.set_value_mm(10.0)
        assert editor.toolTip() == hint
        assert "10" not in caption.text()
        assert feature.params["diameter"] == pytest.approx(8.012345)
    finally:
        owner.close()
        owner.deleteLater()
        panel.close()
        panel.deleteLater()


def _measure_group_state(group: QWidget) -> list[list[tuple[Any, ...]]]:
    """Was eine Maßgruppe zeigt, Zeile für Zeile: Texte, Werte, Grenzen, Hilfen."""
    from PySide6.QtWidgets import QFormLayout

    layout = group.layout()
    assert isinstance(layout, QFormLayout)
    rows: list[list[tuple[Any, ...]]] = []
    for row in range(layout.rowCount()):
        entry: list[tuple[Any, ...]] = []
        for role in (
            QFormLayout.ItemRole.LabelRole,
            QFormLayout.ItemRole.FieldRole,
            QFormLayout.ItemRole.SpanningRole,
        ):
            item = layout.itemAt(row, role)
            widget = item.widget() if item is not None else None
            if widget is None:
                continue
            state: tuple[Any, ...] = (
                type(widget).__name__,
                widget.toolTip(),
                widget.statusTip(),
                widget.accessibleName(),
                widget.accessibleDescription(),
                widget.isHidden(),
            )
            if isinstance(widget, LengthSpin):
                state += (
                    widget.text(),
                    round(widget.value_mm(), 6),
                    widget.minimum(),
                    widget.maximum(),
                    widget.suffix(),
                    widget.lineEdit().isModified(),
                )
            elif isinstance(widget, QLabel):
                state += (widget.text(), widget.minimumHeight(), widget.objectName())
            entry.append(state)
        rows.append(entry)
    return rows


def test_measure_conditions_follow_bool_choice_chains_refresh_and_reuse(
    qt_app: QApplication,
) -> None:
    """Die Maßgruppe folgt den Bedingungen, ohne verborgene Eingaben zu verlieren."""
    from types import SimpleNamespace

    from app.core.perceive.actions import ActionField, FeatureAction
    from app.ui.panels import refresh_feature_fields, refused_feature_field

    fields = (
        ActionField("enabled", "Einschalten", "", False, "bool"),
        ActionField(
            "mode",
            "Art",
            "",
            "extended",
            "choice",
            choices=(("simple", "Einfach"), ("extended", "Erweitert")),
            depends_on=("enabled", (True,)),
        ),
        ActionField(
            "length",
            "Länge",
            "mm",
            5.0,
            "length",
            minimum=1.0,
            maximum=20.0,
            depends_on=("mode", ("extended",)),
        ),
    )
    action = FeatureAction("Maße ändern", "slot_hole", fields=fields)
    panel = FeaturePanel()
    panel._runs["test"] = SimpleNamespace(op="slot_hole", action=action)
    group = None
    try:
        built = panel.measure_fields("slot_hole", None)
        assert built is not None
        _, group, editors = built
        assert editors["mode"].isHidden()
        assert editors["length"].isHidden(), "auch die indirekte Bedingung gilt"
        editors["enabled"].setChecked(True)
        assert not editors["mode"].isHidden()
        assert not editors["length"].isHidden()
        editors["length"].set_value_mm(7.0)
        editors["mode"].setCurrentIndex(0)
        assert editors["length"].isHidden()
        editors["enabled"].setChecked(False)
        assert editors["mode"].isHidden()
        refresh_feature_fields(fields, editors, {"mode": "extended", "enabled": True})
        assert not editors["length"].isHidden(), "Kernwerte aktualisieren trotz blockierter Signale"
        assert editors["length"].value_mm() == pytest.approx(7.0)
        assert panel.keep_measure_group(group)
        rebuilt = panel.measure_fields("slot_hole", None)
        assert rebuilt is not None and rebuilt[1] is group
        assert editors["mode"].isHidden() and editors["length"].isHidden()
        editors["enabled"].setChecked(True)
        assert not editors["length"].isHidden()
        assert editors["length"].value_mm() == pytest.approx(5.0)
        group.show()
        QApplication.processEvents()
        editor = editors["length"]
        editor.lineEdit().setText(editor.textFromValue(50.0))
        assert refused_feature_field(editors) is not None
        editors["enabled"].setChecked(False)
        assert refused_feature_field(editors) is None, "ein unwirksames Feld sperrt nicht"
        editors["enabled"].setChecked(True)
        assert refused_feature_field(editors) is not None, "die Eingabe bleibt korrigierbar"
    finally:
        if group is not None:
            group.deleteLater()
        panel.deleteLater()


@pytest.mark.parametrize("op", ["drill_hole", "drill_brep_hole"])
def test_original_bore_measures_hide_slot_fields_until_enabled(
    qt_app: QApplication, op: str
) -> None:
    """Der native Fund: runde Bohrung zeigt keine Langlochlänge oder -richtung."""
    from types import SimpleNamespace

    load_operations()
    identifier, feature = a_hole()
    panel = FeaturePanel()
    owner = QWidget()
    try:
        panel.show_feature(identifier, feature)
        step = SimpleNamespace(id=17, op=op, params={"diameter": 6.0, "slotted": False})
        panel.offer_bore_step(step, REGISTRY.get(op), {})
        built = panel.measure_fields(op, owner, feature=feature)
        assert built is not None
        _, _group, editors = built
        # Die Richtung steht seit RM-513 hinten im Dialog des Schritts, nicht in
        # der Maßgruppe; gezogen wird sie im Bild (``slot_handle``).
        assert "slot_angle" not in editors
        assert editors["slot_length"].isHidden()
        editors["slotted"].setChecked(True)
        assert not editors["slot_length"].isHidden()
        editors["slotted"].setChecked(False)
        assert editors["slot_length"].isHidden()
    finally:
        owner.deleteLater()
        panel.deleteLater()


def test_a_returned_measure_group_shows_what_a_fresh_one_would(qt_app: QApplication) -> None:
    """Eine zurückgegebene Maßgruppe kommt für die nächste Bohrung wieder — wie neu gebaut (RM-232).

    Vergleich mit einem zweiten Fenster, das dieselbe Bohrung zum ersten Mal
    zeigt: dieselben Zeilen, Texte, Werte, Grenzen und Hilfen, kein getippter
    Rest, und nichts, was der vorige Fluss hineingehängt hatte. Was der
    Empfänger gebunden hatte, löst die Rückgabe; mit Elternteil wird nicht
    zurückgenommen.
    """
    from PySide6.QtCore import QEvent
    from shiboken6 import isValid

    found = [
        (key, value) for key, value in features.detect(plate()).items() if value.kind == "hole"
    ]
    assert len(found) >= 2, "die Voraussetzung: zwei Bohrungen"
    (first_id, first), (second_id, second) = found[:2]
    second = replace(second, params={**second.params, "diameter": 7.25})
    panel, reference = FeaturePanel(), FeaturePanel()
    owner = QWidget()
    try:
        panel.show_feature(first_id, first)
        built = panel.measure_fields("resize_hole", None, feature=first)
        assert built is not None
        _action, group, editors = built
        # Getippt im vorigen Fluss — auch in einem Feld, dessen Wert gleich
        # bleibt: Qt schreibt dessen Text dann nicht neu und ließe den Merker.
        for editor in editors.values():
            if isinstance(editor, LengthSpin):
                editor.lineEdit().setModified(True)
        stray = QCheckBox(group)
        released: list[int] = []
        panel.bind_measure_group(group, lambda: released.append(1))
        assert panel.keep_measure_group(group)
        assert released == [1] and group.isHidden()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert stray not in group.findChildren(QCheckBox), "der Haken des vorigen Flusses ist weg"

        panel.show_feature(second_id, second)
        again = panel.measure_fields("resize_hole", None, feature=second)
        reference.show_feature(second_id, second)
        fresh = reference.measure_fields("resize_hole", None, feature=second)
        assert again is not None and fresh is not None
        assert again[1] is group, "dieselbe Gruppe kommt zurück"
        assert [again[2][name] for name in editors] == list(editors.values())
        assert _measure_group_state(again[1]) == _measure_group_state(fresh[1])
        assert again[2]["diameter"].value_mm() == pytest.approx(7.25)

        group.setParent(owner)
        assert not panel.keep_measure_group(group), "mit Elternteil geht sie wie bisher"

        # Eine wartende Gruppe hat keinen Elternteil — sie geht mit dem Fenster.
        leaving = FeaturePanel()
        leaving.show_feature(first_id, first)
        waiting = leaving.measure_fields("resize_hole", None, feature=first)
        assert waiting is not None and leaving.keep_measure_group(waiting[1])
        leaving.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(waiting[1]), "keine Waise nach dem Fenster"
    finally:
        for widget in (owner, panel, reference):
            widget.close()
            widget.deleteLater()


def test_measure_group_owns_the_editable_fields_and_the_only_completion(
    qt_app: QApplication,
) -> None:
    """Panelgegenstücke sind gesperrt, während die Maßgruppe ihren Entwurf hält."""
    identifier, feature = a_hole()
    panel = FeaturePanel()
    try:
        panel.show_feature(identifier, feature)
        panel.set_measuring(True, op="resize_hole", begun=True)
        assert not panel._apply.isVisibleTo(panel)
        assert not panel._cancel.isVisibleTo(panel)
        assert not panel._every.isVisibleTo(panel)
        for row in panel._built:
            for editor in row.findChildren(QWidget):
                if isinstance(editor.property("handlingKey"), str):
                    assert not editor.isEnabled()
        panel.set_measuring(False)
        assert panel._apply.isVisibleTo(panel)
        assert any(editor.isEnabled() for editor in panel.findChildren(LengthSpin))
    finally:
        panel.close()
        panel.deleteLater()


@pytest.mark.parametrize("op", ["drill_hole", "drill_brep_hole"])
def test_the_original_bore_block_leaves_the_panel_while_its_measures_stand_in_the_view(
    qt_app: QApplication,
    op: str,
) -> None:
    """RM-199 ganz: Auch der Block des Bohrschritts steht nicht rechts, solange er im Bild steht.

    ``set_measuring`` verbirgt die Zeile der gemessenen Handlung (``_blocks``);
    der nachgereichte Block „Bohrung im ursprünglichen Schritt ändern" trug
    sich dort nicht ein und blieb mit vier gesperrten Feldern neben der
    Maßgruppe stehen (Review Fenster #5).
    """
    from types import SimpleNamespace

    load_operations()
    identifier, feature = a_hole()
    step = SimpleNamespace(id=17, op=op, params={"diameter": 6.0, "depth": 0.0})
    panel = FeaturePanel()
    try:
        panel.show_feature(identifier, feature)
        panel.offer_bore_step(step, REGISTRY.get(op), {})
        key = next(key for key, entry in panel._runs.items() if entry.op == op)
        assert key in panel._blocks, "der Bohrschritt-Block kennt seine Zeile"
        line, row = panel._blocks[key]
        panel.set_measuring(True, op=op)
        assert not row.isVisibleTo(panel), "seine Maße stehen im Bild, nicht rechts"
        assert line is None or not line.isVisibleTo(panel)
        other = next(
            row for key, (_l, row) in panel._blocks.items() if panel._runs[key].op == "move_feature"
        )
        assert other.isVisibleTo(panel), "die übrigen Handlungen bleiben"
        alternatives = [
            widget
            for key, (_line, widget) in panel._blocks.items()
            if panel._runs[key].op in {"resize_hole", "slot_hole"}
        ]
        assert len(alternatives) == 2
        assert all(not widget.isVisibleTo(panel) for widget in alternatives), (
            "gemessene Folgemaße konkurrieren nicht mit den ursprünglichen Schrittmaßen"
        )
        panel.set_measuring(False)
        assert row.isVisibleTo(panel)
        assert all(widget.isVisibleTo(panel) for widget in alternatives)
    finally:
        panel.close()
        panel.deleteLater()


def test_the_twin_beside_the_measures_drops_the_fields_the_view_already_carries(
    qt_app: QApplication,
) -> None:
    """Was die Maßgruppe im Bild trägt, steht auch im Zwilling rechts nicht noch einmal.

    RM-199 nahm nur den Block der gemessenen Handlung weg. An einer Bohrung
    stand darunter *Zum Langloch ziehen* mit Breite, X, Y, Z und
    Materialtoleranz — dieselben Zahlen wie im Bild —, und am Langloch
    *Bohrung ändern* mit dem Durchmesser, den die Maßgruppe als Breite führt
    (Robert, 24.09.2026: „vor allem mit dem merkmalpanel nebenan"). Was der
    Zwilling allein hat, bleibt stehen, und *Merkmal verschieben* bleibt, wie
    RM-199 es entschieden hat.
    """
    identifier, feature = a_hole()
    mesh = plate()
    panel = FeaturePanel()
    try:
        panel.show_feature(identifier, feature, features=features.detect(mesh), mesh=mesh)
        rows = {row.op: row for row in panel._shown_rows.values()}
        pull, resize, move = rows["slot_hole"], rows["resize_hole"], rows["move_feature"]
        shared = set(pull.widgets) & set(resize.widgets)
        assert shared == {"diameter", "x", "y", "z", "compensate"}, shared

        def shown(row: Any) -> set[str]:
            return {name for name, editor in row.widgets.items() if not editor.isHidden()}

        before = {op: shown(row) for op, row in rows.items()}
        panel.set_measuring(True, op="resize_hole")
        assert shown(pull) == before["slot_hole"] - shared
        assert {"slot_length", "slot_angle"} <= shown(pull), "Länge und Richtung bleiben"
        assert all(pull.labels[name].isHidden() for name in shared), "samt Beschriftung"
        assert shown(move) == before["move_feature"]

        panel.set_measuring(True, op="slot_hole")
        assert shown(pull) == before["slot_hole"], "die Handlung im Bild behält ihre Felder"
        assert shown(resize) == before["resize_hole"] - shared
        assert {"depth", "entrance_mode"} <= shown(resize), "Tiefe und Umfang bleiben"

        panel.set_measuring(False)
        assert {op: shown(row) for op, row in rows.items()} == before
    finally:
        panel.close()
        panel.deleteLater()


@pytest.mark.parametrize("op", ["drill_hole", "drill_brep_hole"])
def test_original_bore_fields_keep_expressions_through_depth_and_hidden_position(
    qt_app: QApplication,
    op: str,
) -> None:
    """Ein skalierter Bohrungsschritt bekommt Originalwerte statt gemessener Weltmaße."""
    from types import SimpleNamespace

    from app.ui.op_dialog import ValueField
    from app.ui.panels import feature_field_values, refresh_feature_fields, refused_feature_field

    load_operations()
    identifier, feature = a_hole()
    step = SimpleNamespace(
        id=17,
        op=op,
        params={"diameter": "=@bore", "depth": 0.0, "x": 7.0, "y": -3.0, "z": 5.0},
    )
    panel = FeaturePanel()
    owner = QWidget()
    try:
        panel.show_feature(identifier, feature)
        panel.offer_bore_step(step, REGISTRY.get(op), {"bore": 6.0})
        built = panel.measure_fields(op, owner)
        assert built is not None
        action, group, editors = built
        assert isinstance(editors["diameter"], ValueField)
        assert "aus dem Schritt" in editors["diameter"].toolTip()
        assert "erzeugenden Schritt" in editors["diameter"].accessibleDescription()
        values = feature_field_values(action.fields, editors, action.fixed)
        assert values["diameter"] == "=@bore"
        assert values["depth"] == pytest.approx(0.0)
        assert values["x"] == pytest.approx(7.0)
        assert values["y"] == pytest.approx(-3.0)
        assert values["z"] == pytest.approx(5.0)
        assert "at_feature" not in values
        assert panel.step_for_action(op) == 17
        assert panel.step_for_action("resize_hole") is None
        assert "ursprünglichen Schrittwerte" in spoken(group)
        refresh_feature_fields(action.fields, editors, {"diameter": "=@bore", "depth": 4.0})
        changed = feature_field_values(action.fields, editors, action.fixed)
        assert changed["diameter"] == "=@bore"
        assert changed["depth"] == pytest.approx(4.0)
        diameter = editors["diameter"]
        diameter.toggle.setChecked(True)
        diameter.text.setText("=@bore*100")
        refusal = diameter.refusal()
        assert refusal and "Obergrenze" in refusal
        assert refused_feature_field(editors) == (refusal, diameter.text)
    finally:
        owner.close()
        owner.deleteLater()
        panel.close()
        panel.deleteLater()


@pytest.mark.parametrize("modified", [False, True])
@pytest.mark.parametrize("focused", [False, True])
def test_measure_refresh_only_protects_a_focused_draft(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, modified: bool, focused: bool
) -> None:
    """Neu fokussierte Karten erhalten Werte; eine wirklich getippte Eingabe bleibt stehen."""
    from app.ui.panels import refresh_feature_fields

    identifier, feature = a_hole()
    panel = FeaturePanel()
    owner = QWidget()
    try:
        panel.show_feature(identifier, feature)
        built = panel.measure_fields("slot_hole", owner)
        assert built is not None
        action, _group, editors = built
        angle = editors["slot_angle"]
        angle.setValue(12)
        angle.lineEdit().setModified(modified)
        monkeypatch.setattr(
            QApplication, "focusWidget", lambda: angle.lineEdit() if focused else None
        )
        refresh_feature_fields(action.fields, editors, {"slot_angle": 45})
        assert angle.value() == pytest.approx(12 if modified and focused else 45)
    finally:
        owner.close()
        owner.deleteLater()
        panel.close()
        panel.deleteLater()


def test_the_waiting_panel_already_shows_its_feature(qt_app: QApplication) -> None:
    """Das wartende Fenster zeigt sein Merkmal — und nicht zugleich „Kein Merkmal gewählt“.

    Bis zur Antwort des Arbeiters stehen Name und Maß (RM-232). Das Fenster
    galt dabei als leer (``feature_id`` war ``None``): Ein Aufbau der
    Menüeinträge in dieser Zeit stellte über ``say_nothing_is_chosen`` den
    Leersatz unter den Namen, und die Prüfung nach einer neuen Auswertung
    übersah ein verschwundenes Merkmal.
    """
    load_operations()
    mesh = plate()
    found = features.detect(mesh)
    hole_id = next(key for key, value in found.items() if value.kind == "hole")
    panel = FeaturePanel()

    panel.show_pending(hole_id, found[hole_id])
    panel.say_nothing_is_chosen(True)

    assert panel.feature_id == hole_id
    assert panel._empty.isHidden(), "der Leersatz stand unter dem gewählten Merkmal"


def test_a_chosen_edge_or_pair_is_not_called_nothing_chosen(qt_app: QApplication) -> None:
    """RM-269 (2): Neben einer gewählten Kante stand „Kein Merkmal gewählt …“.

    ``show_edge`` blendet den Leersatz aus; der Aufbau der Karte danach
    (``MainWindow._update_actions``) ruft ``say_nothing_is_chosen(True)`` — ein
    Körper ist ja gewählt —, und das Fenster galt als leer, weil eine Kante kein
    Merkmal ist (MASSBILD-09). Dasselbe bei zwei gewählten Merkmalen und ihrem
    Abstand. Was dasteht, entscheidet, nicht die Art der Auswahl.
    """
    load_operations()
    mesh = plate()
    found = features.detect(mesh)
    holes = [key for key, value in found.items() if value.kind == "hole"][:2]
    panel = FeaturePanel()
    try:
        panel.show_edge("e:-20.00,0.00,20.00:0.000,1.000,0.000", "Waagerecht · 30,00 mm")
        panel.say_nothing_is_chosen(True)
        assert panel._empty.isHidden(), "der Leersatz stand neben der gewählten Kante"

        panel.show_pair(holes[0], found[holes[0]], holes[1], found[holes[1]])
        panel.say_nothing_is_chosen(True)
        assert panel._empty.isHidden(), "der Leersatz stand über dem Abstand"

        panel.clear()
        panel.say_nothing_is_chosen(True)
        assert not panel._empty.isHidden(), "ohne Inhalt bleibt der Satz"
    finally:
        panel.close()
        panel.deleteLater()


def test_a_fresh_row_that_is_hidden_stays_hidden_after_qt_lays_it_out(
    qt_app: QApplication,
) -> None:
    """Verborgen heißt ausdrücklich verborgen — auch an einer frisch eingesetzten Zeile.

    Ein Widget, das eben erst in ein sichtbares Layout kam, meldet
    ``isHidden()``, bis Qt es mit einem eingereihten Aufruf zeigt. Verbarg
    ``_set_shown`` es nur, wenn es nicht schon „verborgen“ war, zeigte Qt es
    danach trotzdem: Der Block von *Bohrung ändern* stand rechts neben der
    Maßgruppe im Bild, mit denselben Feldern (Durchsicht 0.5.1, RM-199).
    """
    from PySide6.QtWidgets import QVBoxLayout

    from app.ui.panels import _set_shown

    host = QWidget()
    layout = QVBoxLayout(host)
    host.show()
    qt_app.processEvents()
    row = QWidget()
    layout.addWidget(row)
    assert row.isHidden(), "Voraussetzung: frisch im Layout, noch nicht gezeigt"

    _set_shown(row, False)
    for _round in range(5):
        qt_app.processEvents()

    assert row.isHidden(), "Qt zeigte die verborgene Zeile nachträglich"
    _set_shown(row, True)
    assert not row.isHidden()
    host.close()
    host.deleteLater()


def test_a_chamber_stands_in_the_tree_as_one_row_with_its_walls_beneath(
    qt_app: QApplication,
) -> None:
    """Die funktionale Gruppe im Baum (RM-184, Dateiaudit §7).

    Ein Kasten 40 × 30 × 20 mit 2 mm Wand hat innen 36 × 26 × 18: Die Zeile
    des Bodens heißt „Kammer“ und trägt dieses Innenmaß, die vier Wände
    hängen darunter, und wer die Zeile wählt, hat die ganze Kammer gewählt —
    derselbe Weg wie die Senkung unter ihrer Bohrung.
    """
    from app.core.perceive.groups import functional_groups
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.labels import length
    from app.ui.panels import ObjectTree, _feature_item
    from tests.helpers import walled_bin

    mesh = walled_bin()
    found = features.detect(mesh)
    chamber = next(group for group in functional_groups(found, mesh) if group.kind == "chamber")
    entry = SceneObject(id="obj_1", name="Kasten", mesh=mesh, features=found)
    tree = ObjectTree()
    tree.show_scene(EvaluationResult(Scene(objects={entry.id: entry})))
    body = tree.tree.topLevelItem(0)
    assert body is not None
    anchor = _feature_item(body, chamber.anchor)
    assert anchor is not None and anchor.parent() is body
    assert anchor.text(0) == "Kammer"
    across, along, deep = (
        length(36.0, with_unit=False),
        length(26.0, with_unit=False),
        length(18.0),
    )
    assert anchor.text(1) in {f"{across} × {along} × {deep}", f"{along} × {across} × {deep}"}
    walls = [member for member, role in chamber.roles if role == "wall"]
    assert len(walls) == 4
    for wall in walls:
        row = _feature_item(body, wall)
        assert row is not None and row.parent() is anchor, wall
    assert "Boden und Wände umschließen eine Öffnung." in anchor.toolTip(0)
    tree.select_feature(entry.id, chamber.anchor)
    assert set(tree.selected_features()) == {(entry.id, member) for member in chamber.members}
    tree.close()


def test_a_wall_says_which_chamber_it_belongs_to_and_offers_to_change_it(
    qt_app: QApplication,
) -> None:
    """Das Merkmalfenster an einer Wand: Gruppe, Nachweis, Innenmaß — und *Kammer ändern*.

    Die Felder der Handlung tragen die Maße der Kammer, nicht die der Wand:
    Wer an einer Wand klickt, ändert das Innenmaß (RM-184).
    """
    from app.core.perceive.groups import functional_groups
    from app.ui.labels import length
    from tests.helpers import walled_bin

    load_operations()
    mesh = walled_bin()
    found = features.detect(mesh)
    chamber = next(group for group in functional_groups(found, mesh) if group.kind == "chamber")
    wall = next(member for member, role in chamber.roles if role == "wall")
    panel = FeaturePanel()
    panel.show_feature(wall, found[wall], features=found, mesh=mesh)
    labels = [label for row in panel._built for label in row.findChildren(QLabel)]
    labels += [row for row in panel._built if isinstance(row, QLabel)]
    texts = [label.text() for label in labels]
    assert "Teil von Kammer" in texts
    assert "Boden und Wände umschließen eine Öffnung." in texts
    values = {label.accessibleName(): label.text() for label in labels if label.accessibleName()}
    assert values["Tiefe"] == length(18.0)
    assert sorted((values["Breite innen"], values["Länge innen"])) == sorted(
        (length(36.0), length(26.0))
    )
    assert "Kammer ändern" in buttons(panel)
    action = next(entry for entry in panel._runs.values() if entry.title == "Kammer ändern")
    offered = action.values()
    assert offered["depth"] == pytest.approx(18.0, abs=1e-6)
    assert sorted((offered["width"], offered["length"])) == pytest.approx([26.0, 36.0], abs=1e-6)
    panel.close()


def test_a_lug_offers_to_change_the_closure_by_its_play(qt_app: QApplication) -> None:
    """Das Merkmalfenster an einer Nocke: *Verschluss ändern* mit dem Spiel, vorbelegt mit null.

    Den Drehweg trägt das Gegenstück — sein Feld fehlt, und die Notiz sagt
    warum (RM-184). Ein Verschluss trägt kein Spiel, das sich an ihm allein
    messen ließe; deshalb steht dort null und nicht ein Maß.
    """
    import numpy as np
    import trimesh

    from app.core.perceive.groups import functional_groups

    load_operations()
    path = Path(__file__).parent / "data" / "meshes" / "recognition_bayonet_lid.npz"
    with np.load(path, allow_pickle=False) as data:
        mesh = MeshData(raw=trimesh.Trimesh(data["vertices"], data["faces"], process=False))
    found = features.detect(mesh)
    closure = next(group for group in functional_groups(found, mesh) if group.kind == "closure")
    lug = next(member for member in closure.members if member != closure.anchor)
    panel = FeaturePanel()
    panel.show_feature(lug, found[lug], features=found, mesh=mesh)
    assert "Verschluss ändern" in buttons(panel)
    action = next(entry for entry in panel._runs.values() if entry.title == "Verschluss ändern")
    offered = action.values()
    assert offered["play"] == pytest.approx(0.0)
    assert "turn" not in offered
    built = panel.measure_fields("resize_closure", None)
    assert built is not None
    _action, group, editors = built
    try:
        assert set(editors) == {"play"}
        notes = [label.text() for label in group.findChildren(QLabel)]
        assert any("Anschlag" in text for text in notes), notes
    finally:
        group.deleteLater()
        panel.deleteLater()
