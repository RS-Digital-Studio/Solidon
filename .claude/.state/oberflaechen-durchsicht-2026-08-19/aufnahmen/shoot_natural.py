"""Dialoge in ihrer natürlichen Größe aufnehmen — ohne erzwungene Maße.

Das Handbuchbild zwingt jedem Dialog eine feste Größe auf (``prepared``), und
Leerraum darauf sagt deshalb nichts über den Dialog. Hier wird nur
``adjustSize`` gerufen und die Größe mitgeschrieben.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\Users\rober\Documents\Solidon")
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def settle(app: QApplication, rounds: int = 12) -> None:
    for _ in range(rounds):
        app.processEvents()


def shoot(widget, key: str) -> None:
    shot = widget.grab()
    path = OUT / f"{key}.png"
    shot.save(str(path))
    hint = widget.sizeHint()
    print(f"{key}: gezeigt {widget.width()}x{widget.height()} sizeHint {hint.width()}x{hint.height()}")


def natural(widget):
    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    widget.adjustSize()
    widget.show()
    return widget


def main() -> int:
    from app.ui.theme import apply_theme, enable_hidpi

    enable_hidpi()
    app = QApplication(sys.argv)
    apply_theme(app, "dark")

    from app.core.bootstrap import load_operations

    load_operations()
    from app.core.registry import REGISTRY

    from app.ui.op_dialog import OperationDialog

    # Vier Operationen mit sehr verschiedener Feldzahl.
    for name in ("drill_hole", "hollow_object", "create_lid", "split_plane", "label_text", "insert_screw_hole", "create_box", "repair"):
        entry = REGISTRY.get(name)
        if entry is None:
            print(f"{name}: kein Registereintrag")
            continue
        dialog = natural(OperationDialog(entry, ["Halterung"]))
        settle(app)
        shoot(dialog, f"op-{name}")
        dialog.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
