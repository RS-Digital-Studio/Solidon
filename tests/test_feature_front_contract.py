"""FD7/16/63/64: Maßgruppe, Feldhilfen und Hauptaktion teilen denselben Vertrag."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.bootstrap import load_operations
from app.core.geom.mesh import read_mesh
from app.core.perceive.actions import actions_for, bore_action
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.i18n import set_language, tr
from app.i18n.catalog import available_languages, install_language
from app.ui.labels import set_display_unit
from app.ui.panels import FIELD_PROPERTY, FeaturePanel, feature_field_values
from tests.ui_helpers import session as session
from tests.ui_helpers import wait_until
from tests.ui_helpers import window as window


@pytest.fixture(autouse=True)
def customer_theme(qt_app):
    """Die wirkliche Gestaltung gilt im Fall als konsistente Betriebslage.

    Nur das Stylesheet zu setzen ließe Palette und Themenmerker in einem
    anderen Zustand. Danach kehrt genau die Lage davor zurück — Stil,
    Palette, Schrift, Stylesheet und Themenmerker —, nicht ein nacktes
    Nichts (conftest, „Was hier absichtlich NICHT zurückgesetzt wird“): Das
    stehen gebliebene dunkle Thema machte Fälle späterer Dateien im selben
    Prozess rot, die allein grün sind (FD-84).
    """
    from PySide6.QtGui import QFont, QPalette

    from app.ui import theme
    from app.ui.style import apply_style

    style = qt_app.style().name()
    palette = QPalette(qt_app.palette())
    font = QFont(qt_app.font())
    sheet = qt_app.styleSheet()
    marker = qt_app.property("solidonTheme")
    active = theme.current_theme()
    theme.apply_theme(qt_app, "dark")
    apply_style(qt_app, "dark")
    yield
    qt_app.setStyle(style)
    qt_app.setStyleSheet(sheet)
    qt_app.setPalette(palette)
    qt_app.setFont(font)
    qt_app.setProperty("solidonTheme", marker)
    theme._ACTIVE = active


def test_customer_theme_remains_consistent_after_a_light_predecessor(qt_app):
    """MG-M1: Light → diese Fixture → Dark darf keine halbe Themenlage hinterlassen."""
    from PySide6.QtGui import QPalette

    from app.ui.theme import apply_theme, current_theme

    apply_theme(qt_app, "light")
    light_sheet = qt_app.styleSheet()
    lifecycle = customer_theme.__wrapped__(qt_app)
    next(lifecycle)
    dark_sheet = qt_app.styleSheet()
    dark_palette = QPalette(qt_app.palette())
    assert dark_sheet != light_sheet
    with pytest.raises(StopIteration):
        next(lifecycle)
    apply_theme(qt_app, "dark")
    assert current_theme() == "dark"
    assert qt_app.property("solidonTheme") == "dark"
    assert qt_app.palette() == dark_palette
    assert qt_app.styleSheet() == dark_sheet


@pytest.fixture
def hole():
    """Ein tatsächlich erkanntes Loch aus dem gemeinsamen Korpus."""
    load_operations()
    path = Path(__file__).parent / "data" / "meshes" / "plate_holes.stl"
    mesh = read_mesh(path.read_bytes(), ".stl")
    found = detect(mesh)
    return next(feature for feature in found.values() if feature.kind == "hole")


def _action(feature, features=None, mesh=None):
    return next(
        action for action in actions_for(feature, features, mesh=mesh) if action.op == "resize_hole"
    )


def _front(editors, owner):
    return {name for name, editor in editors.items() if editor.isVisibleTo(owner)}


@pytest.mark.parametrize("language", available_languages())
@pytest.mark.parametrize("unit", ["mm", "in"])
@pytest.mark.parametrize("larger", [False, True])
def test_hole_front_and_help_survive_units_languages_and_content_font(
    qt_app, hole, language, unit, larger
):
    """Zwei Maße bleiben vorn; Feinheiten haben eigene Hilfen hinter der Klappe."""
    install_language(language)
    set_language(language)
    set_display_unit(unit)
    panel = FeaturePanel()
    frame = QWidget()
    frame.resize(1920, 1080)
    layout = QVBoxLayout(frame)
    try:
        panel.show_feature(hole.id, hole)
        built = panel.measure_fields("resize_hole", frame, feature=hole)
        assert built is not None
        action, group, editors = built
        layout.addWidget(group)
        old_heights = {name: editor.fontMetrics().height() for name, editor in editors.items()}
        if larger:
            for target in group.findChildren(QWidget):
                font = QFont(target.font())
                font.setPointSizeF(18.0)
                target.setFont(font)
        frame.show()
        qt_app.processEvents()
        if larger:
            for name, editor in editors.items():
                assert editor.font().pointSizeF() == pytest.approx(18.0)
                assert editor.fontMetrics().height() > old_heights[name]
                for inner in editor.findChildren(QLineEdit):
                    assert inner.font().pointSizeF() == pytest.approx(18.0)
        assert _front(editors, frame) == {"diameter", "depth"}
        flap = group.findChild(QWidget, "feature-measure-more")
        assert flap is not None
        heading = flap.findChild(QToolButton, "sectionHeading")
        assert heading is not None
        heading.click()
        qt_app.processEvents()
        assert {"entrance_mode", "compensate"} <= _front(editors, frame)
        schema = {entry.name: entry for entry in REGISTRY.get("resize_hole").params.spec()}
        for field in action.fields:
            editor = editors[field.name]
            meaning = str(schema[field.name].doc)
            assert meaning and editor.toolTip().startswith(meaning)
            assert editor.accessibleDescription() == editor.toolTip()
            label = next(label for label in group.findChildren(QLabel) if label.buddy() is editor)
            assert label.accessibleDescription() == editor.toolTip()
            assert label.toolTip() == editor.toolTip()
            for inner in editor.findChildren(QLineEdit):
                # RowCheckBox hält ein verborgenes Drehfeld allein für seine
                # Höhenmessung. Nur ein erreichbares Innenfeld liest der Kunde.
                if inner.isVisibleTo(editor):
                    assert meaning in inner.accessibleDescription()
            assert not editor.statusTip()
        choice = editors["entrance_mode"]
        assert isinstance(choice, QComboBox)
        assert choice.itemData(0, Qt.ItemDataRole.ToolTipRole)
        assert choice.itemData(1, Qt.ItemDataRole.AccessibleDescriptionRole)
        editors["compensate"].setChecked(True)
        editors["depth"].set_value_mm(7.0)
        heading.click()
        values = feature_field_values(action.fields, editors)
        assert values["compensate"] is True
        assert values["depth"] == pytest.approx(7.0)
        assert _front(editors, frame) == {"diameter", "depth"}
    finally:
        frame.close()
        frame.deleteLater()
        panel.deleteLater()
        set_display_unit("mm")
        set_language("de")


def test_follow_preselection_is_visible_and_does_not_reuse_a_hidden_row(qt_app, hole):
    """Ein bewusster vierter Wert einschließlich Sammelhaken; keine alte Klappenzuordnung."""
    from tests.helpers import sloping_bore

    panel = FeaturePanel()
    normal = _action(hole)
    mesh, features, sunk = sloping_bore()
    follow = _action(sunk, features, mesh)
    assert next(field.value for field in follow.fields if field.name == "entrance_mode") == "follow"
    boxes = []
    try:
        for action, feature, expected in (
            (normal, hole, {"diameter", "depth"}),
            (follow, sunk, {"diameter", "depth", "entrance_mode"}),
            (normal, hole, {"diameter", "depth"}),
        ):
            panel._runs["test"] = SimpleNamespace(op="resize_hole", action=action)
            built = panel.measure_fields("resize_hole", None, feature=feature)
            assert built is not None
            _, box, editors = built
            boxes.append(box)
            box.resize(1920, 1080)
            box.show()
            qt_app.processEvents()
            assert _front(editors, box) == expected
            assert len(expected) + 1 <= 4, "der separate Sammelhaken zählt mit"
            assert panel.keep_measure_group(box)
        assert boxes[0] is boxes[2]
        assert boxes[0] is not boxes[1]
    finally:
        panel.deleteLater()


@pytest.mark.parametrize("op", ["drill_hole", "drill_brep_hole"])
def test_original_bore_keeps_its_schema_help_values_and_conditions(qt_app, hole, op):
    """Der ursprüngliche Auftrag liest weiterhin sein Schema und seine gespeicherten Werte."""
    spec = REGISTRY.get(op)
    step = SimpleNamespace(id=17, op=op, params={"diameter": 6.0, "slotted": False})
    action = bore_action(step, spec)
    schema = {entry.name: entry for entry in spec.params.spec()}
    panel = FeaturePanel()
    owner = QWidget()
    try:
        panel.show_feature(hole.id, hole)
        panel.offer_bore_step(step, spec, {})
        built = panel.measure_fields(op, owner, feature=hole)
        assert built is not None
        _, _, editors = built
        for field in action.fields:
            assert str(schema[field.name].doc) in editors[field.name].toolTip()
        assert editors["slot_length"].isHidden()
        editors["slotted"].setChecked(True)
        assert not editors["slot_length"].isHidden()
        assert editors["diameter"].value() == pytest.approx(6.0)
        assert str(schema["diameter"].doc) in editors["diameter"].toolTip()
    finally:
        owner.deleteLater()
        panel.deleteLater()


def _selected_hole(window, qt_app):
    """Der echte Auswahlanschluss einschließlich des separaten Sammelhakens."""
    from tests.render_fakes import RecordingRenderer

    window.viewport.renderer = RecordingRenderer(size=(1920, 1080))
    window.resize(1920, 1080)
    window.show()
    window.open_path(Path(__file__).parent / "data" / "meshes" / "plate_holes.stl")
    assert window.session.wait_for_idle(60_000)
    result = window.session.evaluate_now()
    object_id, body = next(iter(result.scene.objects.items()))
    hole_id = next(name for name, feature in body.features.items() if feature.kind == "hole")
    window.object_tree.select_feature(object_id, hole_id)
    assert window.session.wait_for_idle(30_000)
    wait_until(
        qt_app,
        lambda: (
            window._quiet_placement is not None
            and window._quiet_placement.active
            and window._quiet_placement._measure_group is not None
        ),
    )
    return object_id, hole_id


def test_real_measure_group_counts_scope_and_explains_both_scope_controls(window, qt_app):
    """FD63/64 werden an innerem Formular und tatsächlich angebauter Fußzeile geprüft."""
    _selected_hole(window, qt_app)
    flow = window._quiet_placement
    assert flow is not None and flow.active
    group = flow._measure_group
    assert group is not None
    controls = [
        widget
        for widget in group.findChildren(QWidget)
        if widget.property(FIELD_PROPERTY) and widget.isVisibleTo(group)
    ]
    scope = flow._measure_scope
    assert isinstance(scope, QCheckBox) and scope.isVisibleTo(flow._measure_box)
    assert {widget.property(FIELD_PROPERTY) for widget in controls} == {"diameter", "depth"}
    assert len(controls) + 1 == 3
    assert scope.toolTip() and scope.toolTip() == scope.accessibleDescription()
    assert scope.accessibleName() == scope.text()
    scope_hint = scope.toolTip()
    window.end_quiet_placement()
    row = next(row for row in window.feature_panel._shown_rows.values() if row.op == "resize_hole")
    row.toggle.setChecked(True)
    right = window.feature_panel._every
    assert right.isVisibleTo(window.feature_dock)
    assert right.toolTip() == scope_hint
    assert right.accessibleDescription() == right.toolTip()
    assert _front(row.widgets, window.feature_dock) == {"diameter", "depth"}


@pytest.mark.parametrize("op", ["move_feature", "duplicate_feature", "rotate_feature"])
def test_entire_selection_card_has_one_primary_and_returns_it_to_catalog(window, qt_app, op):
    """FD16 umfasst den Katalog, den Fußknopf und den Rückweg zur Körperauswahl."""
    object_id, _ = _selected_hole(window, qt_app)
    catalog = window.selection_operations.catalog_button
    assert not catalog.isDefault(), "auch die Maßgruppe besitzt ihren eigenen Abschluss"
    window.end_quiet_placement()
    panel = window.feature_panel
    row = next(row for row in panel._shown_rows.values() if row.op == op)
    row.toggle.setChecked(True)
    qt_app.processEvents()
    assert catalog.isVisibleTo(window.feature_dock)
    assert panel._apply.isVisibleTo(window.feature_dock)
    assert panel._apply.isDefault()
    assert not catalog.isDefault()
    assert catalog.font().weight() == QFont.Weight.Normal
    editor = next(widget for widget in row.widgets.values() if widget.isVisibleTo(panel))
    editor.setFocus(Qt.FocusReason.OtherFocusReason)
    qt_app.processEvents()
    focus = qt_app.focusWidget()
    assert focus is not None and (focus is editor or editor.isAncestorOf(focus))
    panel.block_apply(tr("Bitte warten …"))
    assert not catalog.isDefault(), "ein gesperrter Entwurf bleibt derselbe Auftrag"
    assert qt_app.focusWidget() is focus
    panel.block_apply(None)
    window.object_tree.select_object(object_id)
    qt_app.processEvents()
    assert catalog.isDefault()
    assert catalog.font().weight() >= QFont.Weight.DemiBold


def test_cancel_clears_the_selection_and_returns_the_primary_to_the_catalog(window, qt_app):
    """Abbrechen hebt die Merkmalauswahl auf; ohne Auftrag führt wieder der Katalog."""
    _selected_hole(window, qt_app)
    document = window.session.project.document
    before = tuple(document.ops)
    flow = window._quiet_placement
    assert flow is not None and flow.active
    flow._measure_cancel.click()
    wait_until(qt_app, lambda: window._quiet_placement is None)
    panel = window.feature_panel
    assert tuple(document.ops) == before
    assert window.object_tree.selected_feature() is None
    qt_app.processEvents()
    assert window.selection_operations.catalog_button.isDefault()
    assert not panel._apply.isVisibleTo(window.feature_dock)


def test_material_correction_has_a_plain_name_and_describes_the_entered_target(hole):
    """FD7: Der sichtbare Name sagt Druckabweichung; aus lässt das Zielmaß gelten."""
    set_language("de")
    field = next(field for field in _action(hole).fields if field.name == "compensate")
    assert str(field.label) == "Druckabweichung ausgleichen"
    assert "eingegebene Maß" in str(field.doc)
    assert "Materialprofil" in str(field.doc)


def test_radius_help_matches_the_presented_quantity(qt_app, hole):
    """Der vorhandene Durchmesser-zu-Radius-Adapter übersetzt auch den Wirkungssatz."""
    from app.core.perceive.actions import _action_field
    from app.ui.panels import feature_field

    entry = next(
        entry for entry in REGISTRY.get("resize_feature").params.spec() if entry.name == "diameter"
    )
    rounding = replace(hole, kind="fillet", params={"radius": 3.0})
    field = _action_field(entry, rounding, "resize_feature")
    owner = QWidget()
    try:
        editor = feature_field(
            field, owner, expression_fields={}, part_fields={}, parameter_values={}
        )
        assert str(field.label) == tr("Radius")
        assert tr("Radius") in editor.toolTip()
        assert tr("Durchmesser") not in editor.toolTip()
        assert editor.value_mm() == pytest.approx(3.0)
        values = feature_field_values((field,), {field.name: editor})
        assert values["diameter"] == pytest.approx(editor.value_mm() * 2.0)
    finally:
        owner.deleteLater()


def test_reused_right_row_closes_its_back_and_explicit_focus_opens_it(qt_app, hole):
    """Neue Auswahl beginnt vorn; die Übergabe an ein hinteres Feld macht dieses erreichbar."""
    panel = FeaturePanel()
    panel.resize(1920, 1080)
    try:
        panel.show_feature(hole.id, hole)
        row = next(row for row in panel._shown_rows.values() if row.op == "resize_hole")
        row.toggle.setChecked(True)
        panel.show()
        qt_app.processEvents()
        more = row.box.findChild(QWidget, "feature-row-more")
        assert more is not None
        heading = more.findChild(QToolButton, "sectionHeading")
        assert heading is not None
        heading.click()
        row.widgets["compensate"].setChecked(True)
        heading.click()
        assert panel.focus_field("resize_hole", "compensate")
        assert heading.isChecked()
        assert row.widgets["compensate"].isChecked()
        other = replace(hole, id="next_hole", params={**hole.params, "diameter": 7.0})
        panel.show_feature(other.id, other)
        again = next(row for row in panel._shown_rows.values() if row.op == "resize_hole")
        assert again is row
        again.toggle.setChecked(True)
        qt_app.processEvents()
        assert not heading.isChecked()
        assert _front(again.widgets, panel) == {"diameter", "depth"}
        assert not again.widgets["compensate"].isChecked()
        assert again.widgets["diameter"].toolTip().count(tr("Ausgangswert:")) <= 1
        assert panel.focus_field("resize_hole", "diameter")
        QTest.keyClick(again.widgets["diameter"], Qt.Key.Key_Tab)
        assert again.widgets["depth"].hasFocus()
        QTest.keyClick(again.widgets["depth"], Qt.Key.Key_Tab)
        assert heading.hasFocus()
        QTest.keyClick(heading, Qt.Key.Key_Space)
        QTest.keyClick(heading, Qt.Key.Key_Tab)
        assert again.widgets["entrance_mode"].hasFocus()
    finally:
        panel.close()
        panel.deleteLater()


def test_original_expression_keeps_meaning_grammar_and_written_value(qt_app, hole):
    """Die Schemahilfe ergänzt die Grammatik; Bearbeiten schreibt keinen Ausdruck um."""
    from app.ui.op_dialog import ValueField

    panel = FeaturePanel()
    owner = QWidget()
    try:
        panel.show_feature(hole.id, hole)
        step = SimpleNamespace(
            id=17, op="drill_hole", params={"diameter": "=@size", "slotted": False}
        )
        panel.offer_bore_step(step, REGISTRY.get("drill_hole"), {"size": 6.0})
        built = panel.measure_fields("drill_hole", owner, feature=hole)
        assert built is not None
        action, _, editors = built
        editor = editors["diameter"]
        assert isinstance(editor, ValueField)
        doc = str(
            next(
                entry
                for entry in REGISTRY.get("drill_hole").params.spec()
                if entry.name == "diameter"
            ).doc
        )
        grammar = editor._grammar_help()
        assert doc in editor.text.accessibleDescription()
        assert grammar in editor.text.accessibleDescription()
        editor.text.setText("=@size+1")
        assert doc in editor.text.toolTip() and grammar in editor.text.toolTip()
        assert "=@size+1" in editor.text.toolTip()
        values = feature_field_values(action.fields, editors, action.fixed)
        assert values["diameter"] == "=@size+1"
        assert editor.text.toolTip().count(doc) == 1
        editor.toggle.setChecked(False)
        editor.spin.lineEdit().selectAll()
        QTest.keyClicks(editor.spin.lineEdit(), "0")
        assert editor.refusal()
        assert doc in editor.spin.accessibleDescription()
        assert editor.refusal() in editor.spin.accessibleDescription()
        assert doc in editor.spin.lineEdit().accessibleDescription()
        assert editor.refusal() in editor.spin.lineEdit().toolTip()
        editor.spin.lineEdit().selectAll()
        QTest.keyClicks(editor.spin.lineEdit(), "8")
        assert not editor.refusal()
        assert editor.spin.accessibleDescription() == editor.toolTip()
        assert editor.spin.lineEdit().toolTip() == editor.toolTip()
    finally:
        owner.deleteLater()
        panel.deleteLater()


@pytest.mark.parametrize("scope", [False, True])
@pytest.mark.parametrize("compensate", [False, True])
def test_measure_acceptance_keeps_hidden_values_scope_and_one_undo(
    window, qt_app, monkeypatch, scope, compensate
):
    """Echte Panelwerte rechnen an einem oder allen Löchern; ein Undo stellt die Szene her."""
    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.prepare import bore_diameter
    from app.ui.labels import LengthSpin

    # Der Auftragsweg wird echt gerechnet, der Aufnahmetest ersetzt nur den
    # Renderer. Die native Sichtbarkeit ist ein getrennter Nachweis.
    monkeypatch.setattr(window.viewport, "is_difference_applied", lambda _difference: True)
    monkeypatch.setattr(window.viewport, "is_scene_applied", lambda _result: True)
    object_id, hole_id = _selected_hole(window, qt_app)
    document = window.session.project.document
    before_ops = tuple(document.ops)
    before_transactions = len(document.transactions)
    before_body = window.session.last_result.scene.objects[object_id]
    before_vertices = as_mesh_data(before_body.mesh).raw.vertices.copy()
    group = window.feature_panel.measure_group("resize_hole")
    assert group is not None and len(group.members) > 1
    targets = {member.target for member in group.members} if scope else {hole_id}
    flow = window._quiet_placement
    assert flow is not None and flow.active and flow._measure_group is not None
    box = flow._measure_group
    editors = {
        str(widget.property(FIELD_PROPERTY)): widget
        for widget in box.findChildren(QWidget)
        if widget.property(FIELD_PROPERTY)
    }
    diameter = editors["diameter"]
    assert isinstance(diameter, LengthSpin)
    wanted = diameter.value_mm() + 0.5
    assert isinstance(flow._measure_scope, QCheckBox)
    if scope:
        flow._measure_scope.click()
    heading = box.findChild(QWidget, "feature-measure-more").findChild(
        QToolButton, "sectionHeading"
    )
    heading.click()
    assert isinstance(editors["compensate"], QCheckBox)
    if compensate:
        editors["compensate"].click()
    heading.click()
    QTest.keyClick(diameter, Qt.Key.Key_End)
    diameter.set_value_mm(wanted)
    wait_until(qt_app, flow._measure_accept.isEnabled)
    assert window._quiet_host is not None
    assert window._quiet_host.values()["compensate"] is compensate
    flow._measure_accept.click()
    wait_until(qt_app, lambda: len(document.transactions) == before_transactions + 1)
    assert window.session.wait_for_idle(60_000)
    appended = document.ops[len(before_ops) :]
    assert len(appended) == len(targets)
    assert {step.params["at_feature"] for step in appended} == targets
    assert all(step.params["compensate"] is compensate for step in appended)
    assert len(document.transactions) == before_transactions + 1
    result = window.session.evaluate_now()
    changed = result.scene.objects[object_id]
    expected = bore_diameter(wanted, window.session.evaluation_profile, compensate)
    assert all(
        float(changed.features[target].params["diameter"]) == pytest.approx(expected)
        for target in targets
    )
    assert window.session.undo() is not None
    assert window.session.wait_for_idle(60_000)
    assert tuple(document.ops) == before_ops
    restored = window.session.evaluate_now().scene.objects[object_id]
    assert as_mesh_data(restored.mesh).raw.vertices == pytest.approx(before_vertices)


@pytest.mark.parametrize("entry", ["command", "search"])
def test_registered_command_and_search_keep_the_shared_hole_schema(window, qt_app, entry):
    """Registrierter Befehl und Suche öffnen dieselben Feldhilfen und Korrekturbedeutung.

    Die auswahlgebundene Operation hat keine eigene Zeile im Hauptmenü.
    Die QAction trägt ihren registrierten Befehl und das zugehörige Kürzel.
    """
    _selected_hole(window, qt_app)
    window.end_quiet_placement()
    if entry == "command":
        action = window._op_actions["resize_hole"]
        assert action.isEnabled()
        action.trigger()
    else:
        panel = window.selection_operations
        panel.search.setText(str(REGISTRY.get("resize_hole").title))
        qt_app.processEvents()
        item = next(
            panel.hits.item(index)
            for index in range(panel.hits.count())
            if panel.hits.item(index).data(Qt.ItemDataRole.UserRole) == "resize_hole"
        )
        assert item.flags() & Qt.ItemFlag.ItemIsEnabled
        panel.hits.itemActivated.emit(item)
    qt_app.processEvents()
    dialog = window._op_dialog
    assert dialog is not None and dialog.spec.name == "resize_hole"
    try:
        schema = {field.name: field for field in REGISTRY.get("resize_hole").params.spec()}
        for name in ("diameter", "depth", "compensate", "entrance_mode"):
            assert str(schema[name].doc) == dialog._editors[name].toolTip()
            assert str(schema[name].doc) == dialog._editors[name].accessibleDescription()
        assert str(schema["compensate"].title) == tr("Druckabweichung ausgleichen")
    finally:
        dialog.reject()


def test_local_recognition_keeps_the_shared_hole_help(qt_app, profile, monkeypatch):
    """Die lokal erkannte Bohrung benutzt dieselbe Schemaquelle wie Menü und Maßgruppe."""
    from tests.test_local_recognition_ui import choose_action, dispose, make_dialog

    dialog, _project, _before = make_dialog(profile, monkeypatch)
    try:
        wait_until(qt_app, dialog.save_button.isEnabled)
        choose_action(dialog, "resize_hole")
        editor = dialog.editor
        assert editor is not None
        schema = {field.name: field for field in REGISTRY.get("resize_hole").params.spec()}
        for name in ("diameter", "depth", "compensate", "entrance_mode"):
            assert editor._editors[name].toolTip() == str(schema[name].doc)
        assert str(schema["compensate"].title) == tr("Druckabweichung ausgleichen")
    finally:
        dispose(dialog, qt_app)
