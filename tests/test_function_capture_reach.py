"""Was der Prüfstand an einer Fläche aufnimmt, ist, was der Kunde dort hat (Paket F8, RM-737).

Offscreen an echten Widgets, ohne den ganzen Fall: Felder, die der Besitzer
selbst versteckt, zählen nicht (FD-102); eine Zeile in Liste oder Baum, die
die Ansicht mit „…“ kürzt, ist abgeschnitten (FD-110); der Grund eines grauen
Knopfs steht als eigenes Bild da (FD-149); ein Glied der Tab-Kette ohne
eigenen Namen heißt nicht nach seiner Klasse (FD-141).
"""

from __future__ import annotations

from typing import Any

from tools import function_capture as capture

# --- FD-102: ein selbst verstecktes Feld ist keines der Fläche --------------------------


def test_a_field_its_owner_hides_is_not_counted_but_one_behind_a_flap_is(qt_app: Any) -> None:
    """Der Haken „Auf alle … anwenden“ steht leer und versteckt im Merkmalfenster.

    Er erscheint erst bei mehreren gleichartigen Merkmalen, dann mit Text und
    Kurzhilfe (``feature_editing.configure_scope``). Versteckt zählte ihn V3 als
    Feld ohne Titel und Satz (FD-102, Lauf 037–042). Ein Feld hinter einer
    zugeklappten Klappe bleibt dagegen ein Feld der Fläche, nur nicht vorn.
    """
    from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QVBoxLayout, QWidget

    root = QWidget()
    layout = QVBoxLayout(root)
    front = QWidget(root)
    form = QFormLayout(front)
    width = QDoubleSpinBox(front)
    width.setAccessibleName("Breite")
    width.setToolTip("Wie breit das Teil wird.")
    form.addRow("Breite", width)
    layout.addWidget(front)
    flap = QWidget(root)
    behind = QFormLayout(flap)
    depth = QDoubleSpinBox(flap)
    depth.setAccessibleName("Tiefe")
    depth.setToolTip("Wie tief es reicht.")
    behind.addRow("Tiefe", depth)
    layout.addWidget(flap)
    flap.setVisible(False)
    every = QCheckBox("", root)
    every.setVisible(False)
    layout.addWidget(every)
    root.show()
    try:
        entries = capture.field_entries(root)
        assert [(entry["label"], entry["front"]) for entry in entries] == [
            ("Breite", True),
            ("Tiefe", False),
        ]
    finally:
        root.close()


def test_the_feature_window_names_every_field_it_counts(qt_app: Any) -> None:
    """Am echten Merkmalfenster einer Bohrung: kein gezähltes Feld ohne Namen (FD-102)."""
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    from app.core.bootstrap import load_operations
    from app.core.types import Feature
    from app.ui.panels import FeaturePanel

    load_operations()
    host = QWidget()
    body = QVBoxLayout(host)
    panel = FeaturePanel()
    body.addWidget(panel)
    body.addWidget(panel.footer())
    hole = Feature(
        id="hole",
        kind="hole",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 5.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 5.2,
            "depth": 10.0,
            "through": True,
        },
    )
    panel.show_feature(hole.id, hole)
    host.resize(420, 1400)
    host.show()
    try:
        for op in ("move_feature", "duplicate_feature"):
            row = next(row for row in panel._shown_rows.values() if row.op == op)
            row.toggle.click()
            qt_app.processEvents()
            surface = row.toggle.parentWidget()
            entries = [*capture.field_entries(surface), *capture.field_entries(panel.footer())]
            assert entries, op
            unnamed = [e for e in entries if not e["label"] and not e["accessible_name"]]
            assert unnamed == [], (op, unnamed)
            row.toggle.click()
            qt_app.processEvents()
    finally:
        host.close()
