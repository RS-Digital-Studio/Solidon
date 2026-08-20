"""Den Druckdialog offscreen aufbauen und ausmessen."""

from __future__ import annotations

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import (  # noqa: E402
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QGroupBox,
    QLabel,
    QTabWidget,
)

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.ui.print_settings_dialog import FIELDS, PrintSettingsDialog  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402

app = QApplication([])
dialog = PrintSettingsDialog(Session(), UiSettings())
dialog.resize(dialog.sizeHint())
dialog.show()
app.processEvents()

print("Fenster:", dialog.width(), "x", dialog.height(), " Mindestmaß:", dialog.minimumSize())
print("Anfangsfokus:", type(dialog.focusWidget()).__name__ if dialog.focusWidget() else "keiner")

print("\n--- Gruppen ---")
for box in dialog.findChildren(QGroupBox):
    print(
        f"  {box.title()!r:34s} sichtbar={box.isVisible()} "
        f"ankreuzbar={box.isCheckable()} an={box.isChecked()} aktiv={box.isEnabled()}"
    )

print("\n--- Reiter ---")
for tabs in dialog.findChildren(QTabWidget):
    print("  ", [tabs.tabText(i) for i in range(tabs.count())])

print("\n--- Felder vorn: Beschriftung, Editorbreite ---")
for path, editor in dialog._editors.items():
    field = dialog._fields[path]
    if not field.front:
        continue
    print(
        f"  {dialog._label(field)!r:26s} {type(editor).__name__:16s} "
        f"breite={editor.width():4d} hoehe={editor.height():3d} aktiv={editor.isEnabled()}"
    )

widths = sorted({e.width() for e in dialog._editors.values()})
print("\nEditorbreiten insgesamt:", widths)
spin = [e for e in dialog._editors.values() if isinstance(e, QAbstractSpinBox)]
print("Zahlenfelder:", len(spin), "breiteste:", max(e.width() for e in spin) if spin else 0)

print("\n--- Nicht bedienbare Elemente mit Grund? ---")
for widget in dialog.findChildren(QComboBox):
    if not widget.isEnabled():
        print(f"  gesperrt: QComboBox mit {widget.count()} Einträgen, Tooltip={widget.toolTip()!r}")

print("\n--- Labels, die wie Auskunft aussehen ---")
for label in dialog.findChildren(QLabel):
    text = label.text().strip()
    if len(text) > 30:
        print(f"  {text[:110]!r} sichtbar={label.isVisible()}")

print("\n--- Vorschlagsliste ---")
advice = getattr(dialog, "advice_list", None) or getattr(dialog, "advice", None)
print("  Attribut:", type(advice).__name__ if advice is not None else "nicht gefunden")
for name in dir(dialog):
    if "advice" in name or "state" in name:
        print("   ", name)
