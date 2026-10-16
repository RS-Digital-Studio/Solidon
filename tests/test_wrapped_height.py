"""Ein umbrochener Satz ist so hoch wie sein Text in seiner Breite (FD-133).

Die Karten pinnen die Höhe umbrochener Sätze als Mindesthöhe
(``panels.fit_wrapped``). Gemessen wurde einmal, an der Grundbreite der linken
Spalte. In der rechten Karte, die 400 bis 540 Punkte breit ist, passt die
Erklärung unter einem Flächenpaar oft in eine Zeile; die gepinnte zweite Zeile
blieb als Leerraum stehen, der Text mittig darin. Am Lauf des
Funktionsdurchgangs stand das im Portugiesischen als zwei Leerzeilen im
Maßblock von *Gegenstücke setzen …*.
"""

from __future__ import annotations

import pytest
import trimesh
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from app.core.geom.mesh import MeshData
from app.core.perceive import features
from app.core.types import Feature

LANGUAGES = ("de", "en", "es", "fr", "it", "pt")


def _needed(label: QLabel) -> int:
    """Was der Text in der Breite des Satzes braucht, ohne die gepinnte Höhe.

    ``QLabel.heightForWidth`` meldet nie weniger als die eigene Mindesthöhe.
    """
    pinned = label.minimumHeight()
    label.setMinimumHeight(0)
    try:
        return max(label.heightForWidth(label.width()), 0)
    finally:
        label.setMinimumHeight(pinned)


def _settle(qt_app: QApplication) -> None:
    for _round in range(10):
        qt_app.processEvents()


def _two_faces() -> tuple[tuple[str, Feature], tuple[str, Feature]]:
    found = features.detect(MeshData.of(trimesh.creation.box(extents=(40.0, 30.0, 20.0))))
    faces = [(key, value) for key, value in found.items() if value.kind == "face"]
    assert len(faces) >= 2, "ein Quader hat Flächen"
    return faces[0], faces[1]


def _set_language(language: str) -> None:
    from app.i18n import set_language
    from app.i18n.catalog import install_language

    install_language(language)
    set_language(language)


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("width", (416, 540))
def test_the_pair_card_has_no_empty_lines(qt_app: QApplication, language: str, width: int) -> None:
    """Der Maßblock eines Flächenpaars, wie ihn das Fenster füllt.

    Abstand, die zwei Herkunftszeilen, der Satz zur Prüfung und die Passungsart
    (``MainWindow._on_features_selected``) — kein Satz ist höher als sein Text.
    """
    _set_language(language)
    from app.i18n import tr
    from app.ui.labels import feature_label
    from app.ui.panels import FeaturePanel

    (first_id, first), (second_id, second) = _two_faces()
    panel = FeaturePanel()
    try:
        panel.show_pair(first_id, first, second_id, second)
        panel.show_note(
            f"{tr('Quader')} · {feature_label(first_id, first)}\n"
            f"{tr('Quader')} · {feature_label(second_id, second)}"
        )
        panel.show_note(
            tr(
                "Prüft die Maße und folgt den Teilmaterialien. "
                "Die Teile werden dabei nicht verschoben."
            )
        )
        panel.show_fit_choices({"flush": tr("Sollmaß: {value}").format(value="0,00 mm")}, None)
        panel.resize(width, 900)
        panel.show()
        _settle(qt_app)

        labels = [
            label
            for row in panel._built
            for label in (row, *row.findChildren(QLabel))
            if isinstance(label, QLabel) and label.isVisible() and label.wordWrap()
        ]
        assert len(labels) >= 4, [label.text() for label in labels]
        for label in labels:
            needed = _needed(label)
            assert label.height() <= needed, (
                f"{label.text()!r}: {label.height()} Punkte hoch bei {label.width()} breit, "
                f"der Text braucht {needed}"
            )
            assert label.height() >= needed, f"{label.text()!r} ist abgeschnitten"
    finally:
        panel.hide()
        panel.deleteLater()


@pytest.mark.parametrize("width", (300, 420))
def test_the_empty_tree_sentence_follows_the_card_width(qt_app: QApplication, width: int) -> None:
    """Der Zwilling in der linken Karte: seit FD-20 wird sie bis ``LEFT_MAX`` breit."""
    from app.ui.panels import ObjectTree

    tree = ObjectTree()
    try:
        tree.resize(width, 600)
        tree.show()
        _settle(qt_app)
        note = tree._empty
        assert note.isVisible()
        assert note.height() == _needed(note), (
            f"bei {width} Punkten {note.height()} hoch, der Text braucht {_needed(note)}"
        )
    finally:
        tree.hide()
        tree.deleteLater()


def test_a_shorter_sentence_gives_its_line_back(qt_app: QApplication) -> None:
    """Ein Satz, der später kürzer wird, behält nicht die Höhe des längeren.

    So wechselt der Sperrgrund unter dem Übernehmen-Knopf und die Sollauskunft
    der Passungsart: der Text ändert sich, die Breite nicht.
    """
    from app.ui.panels import fit_wrapped

    host = QWidget()
    try:
        column = QVBoxLayout(host)
        label = QLabel(" ".join(["Ein langer Satz, der umbricht."] * 8), host)
        label.setWordWrap(True)
        fit_wrapped(label)
        column.addWidget(label)
        column.addStretch(1)
        host.resize(300, 600)
        host.show()
        _settle(qt_app)
        assert label.height() == _needed(label) > 3 * label.fontMetrics().height()

        label.setText("Kurz.")
        _settle(qt_app)
        assert label.height() == _needed(label) == label.fontMetrics().height(), (
            f"{label.height()} Punkte für eine Zeile von {label.fontMetrics().height()}"
        )

        host.resize(200, 600)
        label.setText(" ".join(["Ein langer Satz, der umbricht."] * 8))
        _settle(qt_app)
        assert label.height() == _needed(label), "wächst auch wieder, an der neuen Breite"
    finally:
        host.hide()
        host.deleteLater()
