"""Die Schnellauswahl zeigt den Wirkungsbereich und meldet ausschließlich bewusste Spulenwahl."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.knowledge import filaments
from app.core.types import MaterialSlot, SceneObject
from app.ui.filament_assignment import QuickFilamentPicker


def _body(
    identifier: str, name: str, material_slots: list[MaterialSlot] | None = None
) -> SceneObject:
    """Ein kleiner gültiger Körper stellt den echten Auswahlvertrag her."""
    import trimesh

    from app.core.geom.mesh import MeshData

    return SceneObject(
        id=identifier,
        name=name,
        mesh=MeshData.of(
            trimesh.creation.box(),
            slots=((material_slots[0].index,) * 12) if material_slots else (),
        ),
        material_slots=material_slots or [],
    )


@pytest.fixture
def picker(qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ein eigenes Lager, ohne Hauptfenster und ohne Renderer."""
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    widget = QuickFilamentPicker()
    yield widget
    widget.close()


def test_no_selection_keeps_inventory_reachable(picker: QuickFilamentPicker) -> None:
    seen: list[bool] = []
    picker.inventoryRequested.connect(lambda: seen.append(True))
    assert not picker.picker.isEnabled()
    picker.inventory_button.click()
    assert seen == [True]
    assert not picker.clear_button.isEnabled()
    assert picker.clear_button.isHidden()


def test_a_chosen_spool_is_reported_at_once_without_a_confirmation(
    picker: QuickFilamentPicker,
) -> None:
    """Die Wahl ist die Zuweisung — kein *Übernehmen*, kein *Abbrechen* (RM-557).

    Ein Filament ändert keine Geometrie; was es tut, nimmt Strg+Z zurück
    (Regel 19). Am exakten Körper stand bis RM-557 ein Übernehmen dazwischen,
    und bis dahin zeigte die Ansicht die alte Farbe.
    """
    from PySide6.QtWidgets import QPushButton

    spool = filaments.save(filaments.CatalogueFilament("PLA Rot", "#ff0000", "PLA"))
    picker.set_context([_body("part", "Teil")])
    chosen: list[object] = []
    picker.spoolChosen.connect(chosen.append)
    row = picker.picker.findData(spool.identifier)
    picker.picker.setCurrentIndex(row)
    picker.picker.activated.emit(row)
    assert [entry.identifier for entry in chosen] == [spool.identifier]
    texts = {button.text() for button in picker.findChildren(QPushButton)}
    assert not texts & {"Übernehmen", "Abbrechen"}, texts


def test_inventory_error_is_visible_and_repaired_file_refreshes_choices(
    picker: QuickFilamentPicker,
) -> None:
    """Kein leeres Lager als Fehlerersatz und kein veralteter Snapshot nach Reparatur."""
    from dataclasses import replace

    first = filaments.save(filaments.CatalogueFilament("Alt", "#112233"))
    picker.set_context([_body("part", "Teil")])
    before = filaments.catalogue_path().read_bytes()
    filaments.catalogue_path().write_text("{kaputt", encoding="utf-8")
    picker.refresh()
    assert not picker.notice.isHidden()
    assert "Sicherung" in picker.notice.text()
    assert picker.inventory_button.isEnabled()
    filaments.catalogue_path().write_bytes(before)
    filaments.save(replace(first, name="Neu"))
    picker.refresh()
    assert picker.notice.isHidden()
    assert "Neu" in picker.picker.itemText(1)


def test_removal_is_reachable_without_a_catalogue_spool(picker: QuickFilamentPicker) -> None:
    """Auch ein fremdes Projektfilament lässt sich ohne Besitzangabe wieder entfernen."""
    seen = []
    picker.clearRequested.connect(lambda: seen.append(True))
    picker.set_context([_body("part", "Teil")])
    assert not picker.clear_button.isEnabled()
    picker.set_context([_body("part", "Teil", [MaterialSlot(0, "Fremde Spule")])])
    assert filaments.catalogue() == ()
    assert picker.clear_button.isEnabled()
    assert not picker.clear_button.isHidden()
    picker.clear_button.click()
    assert seen == [True]


def test_removal_only_uses_the_selected_faces(picker: QuickFilamentPicker) -> None:
    """Eine neutrale Fläche bietet kein Entfernen der anderen noch bemalten Flächen an."""
    from dataclasses import replace

    from app.core.types import Feature

    obj = _body("part", "Teil", [MaterialSlot(1, "Spule")])
    obj = replace(
        obj,
        mesh=replace(obj.mesh, slots=(0, 1) * 6),
        features={
            "neutral": Feature("neutral", "face", "generated", {}, face_indices=(0,)),
            "assigned": Feature("assigned", "face", "generated", {}, face_indices=(1,)),
        },
    )
    picker.set_context([obj], selected_features=(("part", "neutral"),))
    assert not picker.clear_button.isEnabled()
    picker.set_context([obj], selected_features=(("part", "assigned"),))
    assert picker.clear_button.isEnabled()


def test_legacy_object_material_is_named_and_removable_without_a_spool(
    picker: QuickFilamentPicker,
) -> None:
    """Ein altes ABS-Körpermaterial bleibt echte Information und benötigt keine Lager-Spule."""
    from dataclasses import replace

    from app.ui.filament_picker import FilamentPanel

    obj = replace(_body("legacy", "Alt"), material="abs")
    picker.set_context([obj])
    assert "ABS" in picker.picker.currentText()
    assert picker.clear_button.isEnabled()
    assert filaments.catalogue() == ()
    panel = FilamentPanel()
    panel.show_scene([obj])
    assert panel._used[0][0].material_type == "ABS"


def test_project_filament_without_inventory_is_still_named(picker: QuickFilamentPicker) -> None:
    obj = _body(
        identifier="part", name="Teil", material_slots=[MaterialSlot(index=1, name="Fremd")]
    )
    picker.set_context([obj])
    assert "Fremd" in picker.picker.currentText()
    assert picker.picker.currentData() == ""
    assert filaments.catalogue() == ()


def test_mixed_assignment_is_not_a_guessed_spool(picker: QuickFilamentPicker) -> None:
    first = _body(identifier="first", name="A", material_slots=[MaterialSlot(index=1, name="Rot")])
    second = _body(
        identifier="second", name="B", material_slots=[MaterialSlot(index=1, name="Blau")]
    )
    picker.set_context([first, second])
    assert "Mehrere Filamente" in picker.picker.currentText()
    assert picker.picker.currentData() == ""


def test_unused_slot_does_not_announce_multimaterial(picker: QuickFilamentPicker) -> None:
    """Nach dem Färben des ganzen Körpers bestimmen seine Flächen die aktuelle Anzeige."""
    active = MaterialSlot(index=0, name="Aktiv", colour=(1, 0, 0))
    stale = MaterialSlot(index=1, name="Früher", colour=(0, 0, 1))
    picker.set_context([_body("part", "Teil", [active, stale])])
    assert picker.picker.currentText() == "Im Projekt: Aktiv"


def test_partial_assignment_does_not_claim_the_whole_body_is_assigned(
    picker: QuickFilamentPicker,
) -> None:
    """Die noch unbemalten Flächen bleiben bei einem teilweise gefärbten Körper sichtbar."""
    from dataclasses import replace

    active = MaterialSlot(index=1, name="Aktiv", colour=(1, 0, 0))
    body = _body("part", "Teil", [active])
    body = replace(body, mesh=replace(body.mesh, slots=(0, 1) * 6))
    picker.set_context([body])
    assert "Mehrere Filamente" in picker.picker.currentText()


@pytest.mark.parametrize("bodies", [1, 2])
@pytest.mark.parametrize("faces", [1, 2])
def test_mixed_body_and_face_selection_names_the_actual_scope(
    picker: QuickFilamentPicker, bodies: int, faces: int
) -> None:
    """Eine Flächenwahl an B darf die vollständige Zuweisung an Körper A nicht verschweigen."""
    picker.set_context(
        [
            *[_body(f"whole-{index}", "Ganz") for index in range(bodies)],
            _body("partial", "Teilweise"),
        ],
        selected_features=tuple(("partial", face) for face in ("top", "side")[:faces]),
    )
    body_text = "Ganzer Körper: 1." if bodies == 1 else "Ganze Körper: 2."
    face_text = "Gewählte Fläche: 1." if faces == 1 else "Gewählte Flächen: 2."
    assert picker.scope.text() == f"{body_text} {face_text}"
    assert picker.picker.currentText() == "Filament für die Auswahl"


@pytest.mark.parametrize("count", [1, 2])
def test_body_selection_uses_the_right_number(picker: QuickFilamentPicker, count: int) -> None:
    """Der Wirkungsbereich nennt einen Körper in der Einzahl."""
    picker.set_context([_body(f"body-{index}", "Körper") for index in range(count)])
    assert picker.scope.text() == (
        "Die Zuweisung betrifft den gewählten Körper."
        if count == 1
        else "Die Zuweisung betrifft 2 gewählte Körper."
    )


@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("part", [False, True])
def test_face_and_part_selection_use_the_right_number(
    picker: QuickFilamentPicker, count: int, part: bool
) -> None:
    """Ein Baustein bleibt als Ganzes benannt, einzelne Flächen bleiben eine Teilauswahl."""
    picker.set_context(
        [_body("partial", "Teilweise")],
        selected_features=tuple(("partial", face) for face in ("top", "side")[:count]),
        part=part,
    )
    if part:
        assert picker.picker.currentText() == "Filament für den Baustein wählen"
        assert picker.scope.text() == (
            "Die Zuweisung gilt dem ganzen Baustein: eine Fläche."
            if count == 1
            else "Die Zuweisung gilt dem ganzen Baustein: 2 Flächen."
        )
    else:
        assert picker.picker.currentText() == (
            "Filament für die gewählte Fläche wählen"
            if count == 1
            else "Filament für die gewählten Flächen wählen"
        )
        assert picker.scope.text() == (
            "Die Zuweisung betrifft nur die gewählte Fläche."
            if count == 1
            else "Die Zuweisung betrifft 2 gewählte Flächen."
        )
    assert picker.picker.toolTip() == picker.picker.currentText()


def test_refresh_and_context_do_not_emit_assignment(picker: QuickFilamentPicker) -> None:
    seen: list[filaments.CatalogueFilament] = []
    picker.spoolChosen.connect(seen.append)
    obj = _body(identifier="part", name="Teil")
    before = list(obj.material_slots)
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#123456", remaining_grams=123))
    picker.set_context([obj])
    picker.refresh()
    assert not seen
    assert obj.material_slots == before
    row = picker.picker.findData(entry.identifier)
    assert "123" in picker.picker.itemText(row)
    picker._chosen(row)
    assert seen == [entry]
    assert obj.material_slots == before


def test_same_label_is_a_different_choice(picker: QuickFilamentPicker) -> None:
    first = filaments.save(filaments.CatalogueFilament("Spule", "#123456", location="A"))
    second = filaments.save(filaments.CatalogueFilament("Spule", "#123456", location="B"))
    picker.set_context(
        [_body(identifier="part", name="Teil")], selected_features=(("part", "face"),)
    )
    assert "nur die gewählte Fläche" in picker.scope.text()
    assert picker.picker.findData(first.identifier) != picker.picker.findData(second.identifier)


def test_archive_between_display_and_click_does_not_assign(picker: QuickFilamentPicker) -> None:
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#123456"))
    picker.set_context([_body(identifier="part", name="Teil")])
    row = picker.picker.findData(entry.identifier)
    filaments.archive(entry.identifier)
    seen: list[object] = []
    picker.spoolChosen.connect(seen.append)
    picker._chosen(row)
    assert not seen
    assert picker.picker.findData(entry.identifier) < 0


@pytest.mark.parametrize("change", ["name", "colour", "material_type", "slicer_profile", "stock"])
def test_quick_choice_checks_the_identity_that_was_displayed(
    picker: QuickFilamentPicker, change: str
) -> None:
    """Nur Bestandsänderungen lassen sich ohne neue Druckentscheidung übernehmen."""
    from dataclasses import replace

    entry = filaments.save(filaments.CatalogueFilament("Alt", "#123456", "PLA"))
    picker.set_context([_body("part", "Teil")])
    row = picker.picker.findData(entry.identifier)
    updates = {
        "name": {"name": "Neu"},
        "colour": {"colour": "#987654"},
        "material_type": {"material_type": "PETG"},
        "slicer_profile": {"slicer_profile": "Neu"},
        "stock": {"remaining_grams": 200},
    }
    fresh = filaments.save(replace(entry, **updates[change]))
    seen = []
    picker.spoolChosen.connect(seen.append)
    picker._chosen(row)
    if change == "stock":
        assert seen == [fresh]
    else:
        assert not seen
        assert "erneut" in picker.notice.text()
        assert not picker.notice.isHidden()
        picker._chosen(picker.picker.findData(entry.identifier))
        assert seen == [fresh]
        assert picker.notice.isHidden()


def test_operation_dialog_forwards_spool_outside_parameters(
    qt_app: QApplication, picker: QuickFilamentPicker
) -> None:
    """Die lokale Kennung landet im Bindungsweg, niemals in reproduzierbaren Op-Werten."""
    from app.core import bootstrap
    from app.core.registry import REGISTRY
    from app.ui.filament_picker import FilamentField
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#123456"))
    dialog = OperationDialog(REGISTRY.get("paint_slot"), {"part": "Teil"})
    field = dialog.findChild(FilamentField)
    assert field is not None
    seen: list[object] = []
    dialog.spoolChosen.connect(seen.append)
    # Die Zeile trägt keine Kennung, solange nur eine Spule so heißt (T3);
    # die Kurzhilfe trägt sie weiter.
    row = next(
        index
        for index in range(field.count())
        if entry.identifier[:8] in str(field.itemData(index, Qt.ItemDataRole.ToolTipRole) or "")
        or field.itemText(index).startswith("Spule ·")
    )
    assert entry.identifier[:8] not in field.itemText(row)
    field.setCurrentIndex(row)
    field._chosen(row)
    assert seen == [entry]
    assert entry.identifier not in repr(dialog.values())
    assert dialog.values()["replace_filament"] is True


def test_dialog_project_or_neutral_choice_clears_previous_physical_spool(
    qt_app: QApplication, picker: QuickFilamentPicker
) -> None:
    """Die letzte Wahl bestimmt Werte und Bindung; eine frühere Spule bleibt nicht aktiv."""
    from app.core import bootstrap
    from app.core.registry import REGISTRY
    from app.ui.filament_picker import _ID_ROLE, FilamentField
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    entry = filaments.save(filaments.CatalogueFilament("Regal", "#123456", "PLA"))
    slot = MaterialSlot(index=2, name="Projekt", colour=(1, 0, 0), material_type="ABS")
    dialog = OperationDialog(REGISTRY.get("paint_slot"), {"part": "Teil"}, slots=[slot])
    field = dialog.findChild(FilamentField)
    seen = []
    dialog.spoolChosen.connect(seen.append)
    for row in (field.findData(entry.identifier, _ID_ROLE), field.findData(2), field.findData(0)):
        field.setCurrentIndex(row)
        field._chosen(row)
    assert seen == [entry, None, None]
    assert dialog.values()["slot"] == 0
    assert all(
        dialog.values()[key] == "" for key in ("name", "colour", "material_type", "slicer_profile")
    )
    assert not dialog.values()["replace_filament"]


def test_changed_spool_explains_reselection_in_the_open_dialog(
    qt_app: QApplication, picker: QuickFilamentPicker
) -> None:
    """Der Konflikt bleibt als lesbarer Hinweis direkt neben der erneuten Auswahl erreichbar."""
    from app.core import bootstrap
    from app.core.registry import REGISTRY
    from app.ui.filament_picker import _ID_ROLE, FilamentField
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#123456"))
    dialog = OperationDialog(REGISTRY.get("paint_slot"), {"part": "Teil"})
    field = dialog.findChild(FilamentField)
    row = field.findData(entry.identifier, _ID_ROLE)
    filaments.archive(entry.identifier)
    field.setCurrentIndex(row)
    field._chosen(row)
    assert not dialog._filament_notice.isHidden()
    assert "aktualisierten Liste" in dialog._filament_notice.text()
    assert field.findData(entry.identifier, _ID_ROLE) < 0


def test_multi_feature_editor_preserves_legacy_scope_and_named_choices(
    qt_app: QApplication,
) -> None:
    """Eine alte Einzelwahl öffnet als markierte Fläche und lässt sich gezielt erweitern."""
    from app.core import bootstrap
    from app.core.registry import REGISTRY
    from app.ui.op_dialog import FeatureSetField, OperationDialog

    bootstrap.load_operations()
    dialog = OperationDialog(
        REGISTRY.get("clear_filament"),
        {"part": "Teil"},
        values={"at_feature": "top"},
        features={"top": "Oberseite", "side": "Seite"},
        source_objects=("part",),
    )
    field = dialog.findChild(FeatureSetField)
    assert field is not None
    assert dialog.values()["at_feature"] == ""
    assert dialog.values()["at_features"] == ["top"]
    assert not dialog._rows["at_feature"].isRowVisible(dialog._editors["at_feature"])
    assert dialog.take_feature("side", "Seite", "part")
    assert dialog.values()["at_features"] == ["top", "side"]
    assert not dialog.take_feature("foreign", "Fremd", "other")
    assert field.list.item(0).text() == "Oberseite"


def test_empty_feature_selection_never_expands_to_the_whole_body(qt_app: QApplication) -> None:
    """Beim Umwählen bleibt die Vorschau stehen, bis eine neue begrenzte Wahl vorliegt."""
    from PySide6.QtCore import Qt

    from app.core import bootstrap
    from app.core.registry import REGISTRY
    from app.ui.op_dialog import FeatureSetField, OperationDialog

    bootstrap.load_operations()
    dialog = OperationDialog(
        REGISTRY.get("clear_filament"),
        {"part": "Teil"},
        values={"at_features": ["top"]},
        features={"top": "Oberseite"},
    )
    field = dialog.findChild(FeatureSetField)
    changes = []
    dialog.valuesChanged.connect(lambda: changes.append(dialog.values()))
    field.list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert not dialog._accept_button.isEnabled()
    assert dialog.values()["at_features"] == ["top"]
    assert not changes
    dialog.accept()
    assert dialog.result() == 0
    field.whole.setChecked(True)
    assert dialog._accept_button.isEnabled()
    assert dialog.values()["at_features"] == []
    assert changes[-1]["at_features"] == []


def test_missing_saved_feature_is_preserved_in_the_multi_editor(qt_app: QApplication) -> None:
    """Ein nicht mehr gefundenes Merkmal wird nicht still auf eine andere Fläche umgebogen."""
    from PySide6.QtCore import Qt

    from app.ui.op_dialog import FeatureSetField

    field = FeatureSetField({"side": "Seite"}, ["missing"])
    assert field.value() == ["missing"]
    assert field.list.item(1).data(Qt.ItemDataRole.UserRole) == "missing"


def test_embedded_picker_fits_the_narrow_selection_tab(qt_app: QApplication) -> None:
    """Ein schmaler Rollbereich hält Pfeil und Lagerknopf vollständig erreichbar."""
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QScrollArea

    from app.core.scene import OperationDraft
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from app.ui.style import NORMAL, apply_style
    from app.ui.theme import apply_theme

    apply_theme(qt_app, "dark")
    apply_style(qt_app, "dark")
    session = Session()
    window = MainWindow(session, UiSettings())
    window.resize(1280, 800)
    window.show()
    assert session.apply("Prüfkörper", [OperationDraft("create_box")])
    assert session.wait_for_idle()
    result = session.evaluate_now()
    window.object_tree.select_object(next(iter(result.scene.objects)))
    # Offscreen hat synthetische Schriftmetriken. Geprüft wird mindestens
    # 244 Pixel Breite, bei größeren Knopfmaßen entsprechend mehr. Das ist
    # keine Messung einer festen nativen Fensterbreite.
    width = max(
        244, window.quick_filament.inventory_button.minimumSizeHint().width() + 2 * NORMAL + 20
    )
    # Die rechte Karte ist so schmal, wie ein schmales Fenster sie macht
    # (``overlay.card_width``): Die Enge-Grenze gibt ihr 42 % der Breite.
    from app.ui.overlay import CARD_PADDING, NARROW_CARD_SHARE

    window.resize(int((width + 2 * CARD_PADDING + 4) / NARROW_CARD_SHARE) + 1, 800)
    QTest.qWait(100)
    # Der Rollbereich liegt seit dem 13.09.2026 in einer Spalte, unter der die
    # Knopfzeile des Merkmalfensters fest steht (`_build_feature_dock`); der
    # Reiter *Auswahl* ist diese Spalte, der Rollbereich ihr erstes Kind.
    column = window.feature_dock
    scroller = column.findChild(QScrollArea)
    assert isinstance(scroller, QScrollArea)
    assert scroller.horizontalScrollBar().maximum() == 0
    quick = window.quick_filament
    # Der Wähler wartet zugeklappt unter der Liste (RM-510); erreichbar heißt:
    # ein Klick auf „Filament und Druck“, dann stehen Pfeil und Lagerknopf da.
    from PySide6.QtWidgets import QToolButton

    heading = window.selection_operations.print_section.findChild(QToolButton, "sectionHeading")
    assert heading is not None and not heading.isChecked()
    heading.click()
    QApplication.processEvents()
    assert scroller.horizontalScrollBar().maximum() == 0, "auch aufgeklappt rollt nichts quer"
    for control in (quick.picker, quick.inventory_button):
        right = control.mapTo(scroller.viewport(), QPoint(control.width(), 0)).x()
        assert right <= scroller.viewport().width()
        assert control.isVisible()
    quick.set_context(
        list(result.scene.objects.values()),
        selected_features=((next(iter(result.scene.objects)), "face"),),
    )
    QApplication.processEvents()
    assert quick.scope.height() >= quick.scope.heightForWidth(quick.scope.width())


def test_refresh_only_visits_each_whole_body_slot_array_once(
    picker: QuickFilamentPicker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Text und Entfernen-Knopf teilen denselben vollständigen Flächendurchlauf."""
    from app.ui import filament_assignment

    calls = []
    original = filament_assignment.used_slots

    def counted(mesh):
        calls.append(mesh)
        return original(mesh)

    monkeypatch.setattr(filament_assignment, "used_slots", counted)
    first = _body("one", "Teil", [MaterialSlot(1, "Rot")])
    second = _body("two", "Anderes Teil")
    picker.set_context([first, second])
    assert len(calls) == 2
    assert picker.clear_button.isEnabled()


def test_a_wheel_notch_without_focus_assigns_nothing(picker: QuickFilamentPicker) -> None:
    """Eine Radraste über dem Schnellwähler weist nie zu, auch nicht mit Fokus.

    Seit RM-557 ist jede Wahl am Wähler sofort eine Zuweisung mit eigenem
    Verlaufsschritt. Wer die Karte *Auswahl* mit dem Rad rollte, färbte den
    gewählten Körper je Raste um (Review U2, Fund 2) — nach der ersten Wahl
    hat der Wähler den Fokus, und es ging wieder los (Nachprüfung, G1).
    Entscheidung des Koordinators: Das Rad rollt die Karte, gewählt wird in
    der Liste oder mit Enter.
    """
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QLineEdit, QStyleFactory, QVBoxLayout, QWidget

    filaments.save(filaments.CatalogueFilament("PLA Rot", "#ff0000", "PLA"))
    filaments.save(filaments.CatalogueFilament("PLA Blau", "#0000ff", "PLA"))
    picker.set_context([_body("part", "Teil")])
    # Fusion wie in der Anwendung (``theme.py``): Dort dreht das Rad ein
    # Auswahlfeld überhaupt.
    fusion = QStyleFactory.create("Fusion")
    picker.picker.setStyle(fusion)
    host = QWidget()
    layout = QVBoxLayout(host)
    other = QLineEdit(host)
    layout.addWidget(other)
    picker.setParent(host)
    layout.addWidget(picker)
    host.show()
    host.activateWindow()
    other.setFocus()
    QApplication.processEvents()
    chosen: list[object] = []
    picker.spoolChosen.connect(chosen.append)

    def notch() -> QWheelEvent:
        field = picker.picker
        local = QPointF(field.width() / 2, field.height() / 2)
        return QWheelEvent(
            local,
            field.mapToGlobal(local.toPoint()).toPointF(),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )

    try:
        assert not picker.picker.hasFocus()
        QApplication.sendEvent(picker.picker, notch())
        QApplication.processEvents()
        assert chosen == [], "ohne Fokus weist eine Raste nichts zu"
        assert picker.picker.currentIndex() == 0

        picker.picker.setFocus()
        QApplication.processEvents()
        assert picker.picker.hasFocus()
        QApplication.sendEvent(picker.picker, notch())
        QApplication.processEvents()
        event = notch()
        QApplication.sendEvent(picker.picker, event)
        QApplication.processEvents()
        assert chosen == [], "auch mit Fokus weist das Rad nichts zu"
        assert not event.isAccepted(), "die Raste geht weiter — an die Karte, die rollt"
        assert picker.picker.currentIndex() == 0
    finally:
        picker.setParent(None)
        host.close()
        host.deleteLater()


def test_arrows_browse_the_closed_picker_and_enter_assigns(picker: QuickFilamentPicker) -> None:
    """Am geschlossenen Wähler weist nur Enter zu — Pfeile, Tippen, Umschalt und Alt blättern.

    Jede Wahl ist seit RM-557 sofort ein Verlaufsschritt, und Qt meldet am
    geschlossenen Feld jeden Pfeilschritt und jeden getippten Buchstaben als
    Wahl (Entscheidung Koordinator, Review U2; Nachprüfung M1: „p“, „pl“,
    Umschalt+Pfeil und Alt+Pfeil hoch wiesen weiter zu). Escape kehrt zur
    Standzeile zurück. Ohne Maus bleibt alles erreichbar: Alt+Pfeil runter
    öffnet die Liste, Enter wählt dort.
    """
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QComboBox

    for name, colour in (("PETG Grün", "#00ff00"), ("PLA Blau", "#0000ff"), ("PLA Rot", "#ff0000")):
        filaments.save(filaments.CatalogueFilament(name, colour, "PLA"))
    picker.set_context([_body("part", "Teil")])
    picker.show()
    picker.activateWindow()
    combo: QComboBox = picker.picker
    combo.setFocus()
    QApplication.processEvents()
    chosen: list[object] = []
    picker.spoolChosen.connect(chosen.append)

    def press(key: Qt.Key, modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
        QTest.keyClick(combo, key, modifier)
        QApplication.processEvents()

    press(Qt.Key.Key_Down)
    press(Qt.Key.Key_Down)
    assert chosen == [], "Pfeile ohne Enter weisen nichts zu"
    assert combo.currentIndex() == 2, "die Pfeile blättern"
    expected = combo.itemData(2)
    press(Qt.Key.Key_Return)
    assert [entry.identifier for entry in chosen] == [expected], "Enter weist genau einmal zu"

    for keys in (
        [(Qt.Key.Key_P, Qt.KeyboardModifier.NoModifier)],
        [
            (Qt.Key.Key_P, Qt.KeyboardModifier.NoModifier),
            (Qt.Key.Key_L, Qt.KeyboardModifier.NoModifier),
        ],
        [(Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)],
        [
            (Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier),
            (Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier),
        ],
    ):
        chosen.clear()
        picker.set_context([_body("part", "Teil")])
        combo.setFocus()
        for key, modifier in keys:
            press(key, modifier)
        assert chosen == [], f"{keys}: geschlossen weist nur Enter zu"
        assert not combo.view().isVisible(), f"{keys}: die Liste bleibt zu"
        press(Qt.Key.Key_Escape)
        assert combo.currentIndex() == 0, f"{keys}: Escape kehrt zur Standzeile zurück"
        assert chosen == []

    chosen.clear()
    picker.set_context([_body("part", "Teil")])
    combo.setFocus()
    press(Qt.Key.Key_Down)
    picker.inventory_button.setFocus()
    QApplication.processEvents()
    assert chosen == [] and combo.currentIndex() == 0, "geblättert und gegangen: nichts gewählt"

    chosen.clear()
    picker.set_context([_body("part", "Teil")])
    combo.setFocus()
    QTest.keyClick(combo, Qt.Key.Key_Down, Qt.KeyboardModifier.AltModifier)
    QApplication.processEvents()
    view = combo.view()
    assert view.isVisible(), "Alt+Pfeil runter öffnet die Liste ohne Maus"
    QTest.keyClick(view, Qt.Key.Key_Down)
    QTest.keyClick(view, Qt.Key.Key_Return)
    QApplication.processEvents()
    assert len(chosen) == 1, "Enter in der offenen Liste weist genau einmal zu"
