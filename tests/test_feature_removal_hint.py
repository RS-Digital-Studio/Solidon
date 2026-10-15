"""FD-36: Der Entfernen-Hinweis nennt den erreichbaren Weg aus der Maßgruppe."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel

from app.core.bootstrap import load_operations
from app.core.geom.mesh import read_mesh
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.i18n import set_language, tr
from app.i18n.catalog import available_languages, install_language
from app.ui.labels import BoundedLengthSpin
from app.ui.op_dialog import ValueField
from app.ui.panels import FeaturePanel


@pytest.mark.parametrize("language", available_languages())
@pytest.mark.parametrize("measuring,begun", [(False, False), (True, False), (True, True)])
def test_removal_hint_names_cancel_only_when_the_measure_draft_blocks_removal(
    qt_app, language: str, measuring: bool, begun: bool
) -> None:
    """Nur der begonnene Maßentwurf sperrt Entfernen; die offene Maßgruppe allein nicht."""
    install_language(language)
    set_language(language)
    load_operations()
    path = Path(__file__).parent / "data" / "meshes" / "plate_holes.stl"
    mesh = read_mesh(path.read_bytes(), ".stl")
    feature = next(feature for feature in detect(mesh).values() if feature.kind == "hole")
    panel = FeaturePanel()
    group = None
    try:
        panel.show_feature(feature.id, feature)
        built = panel.measure_fields("resize_hole", None, feature=feature)
        assert built is not None
        _action, group, editors = built
        panel.set_measuring(measuring, op="resize_hole", begun=begun)
        removal = next(row for row in panel._shown_rows.values() if row.op == "remove_feature")
        assert removal.button is not None
        assert removal.button.isEnabled() is not begun
        editor = editors["diameter"]
        assert isinstance(editor, BoundedLengthSpin)
        editor.lineEdit().selectAll()
        QTest.keyClicks(editor.lineEdit(), editor.textFromValue(0.1))
        hints = [label.text() for label in group.findChildren(QLabel)]
        action = str(removal.action.title)
        hint = next(text for text in hints if action in text)
        assert (str(tr("Abbrechen")) in hint) is begun, hint
        assert editor.refusal() in hint
        if begun:
            assert hint.index(str(tr("Abbrechen"))) < hint.index(action)
        panel.set_measuring(False)
        assert removal.button.isEnabled()
    finally:
        if group is not None:
            group.close()
            group.deleteLater()
        panel.close()
        panel.deleteLater()


@pytest.mark.parametrize("language", available_languages())
def test_part_removal_hint_keeps_the_part_title_and_direct_path(qt_app, language: str) -> None:
    """Der gleiche Hinweis am Baustein behält den Namen seines tatsächlich angebotenen Knopfs."""
    install_language(language)
    set_language(language)
    load_operations()
    panel = FeaturePanel()
    try:
        panel.show_part(
            SimpleNamespace(id=5, op="insert_dowel", params={}), REGISTRY.get("insert_dowel")
        )
        row = next(row for row in panel._shown_rows.values() if "diameter" in row.widgets)
        editor = row.widgets["diameter"]
        assert isinstance(editor, ValueField)
        editor.spin.lineEdit().selectAll()
        QTest.keyClicks(editor.spin.lineEdit(), editor.spin.textFromValue(0.1))
        assert str(tr("Baustein entfernen")) in editor.hint.text()
        assert str(tr("Abbrechen")) not in editor.hint.text()
    finally:
        panel.close()
        panel.deleteLater()
