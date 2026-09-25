# Welches Kind des Merkmalfensters ist von Anfang an nativ, und welche Vorfahren?
from PySide6.QtCore import Qt as _Qt
from PySide6.QtWidgets import QWidget as _QWidget

_NATIVE = _Qt.WidgetAttribute.WA_NativeWindow
_panel = window.feature_panel
for _child in _panel.children():
    if isinstance(_child, _QWidget) and _child.testAttribute(_NATIVE):
        log("natives Kind:", type(_child).__name__, repr(_child.objectName()), "sichtbar", _child.isVisible(),
            "Kinder:", [type(c).__name__ for c in _child.children()][:12])
_current = _panel
while _current is not None:
    log("Vorfahr:", type(_current).__name__, repr(_current.objectName()), "nativ", _current.testAttribute(_NATIVE),
        "PaintOnScreen", _current.testAttribute(_Qt.WidgetAttribute.WA_PaintOnScreen))
    _current = _current.parentWidget()
# Die Geschwister der Andockleiste: welche sind nativ?
_dock = _panel
while _dock is not None and type(_dock).__name__ != "_FeatureDock":
    _dock = _dock.parentWidget()
if _dock is not None:
    for _sibling in _dock.parentWidget().children():
        if isinstance(_sibling, _QWidget):
            log("  Geschwister der Leiste:", type(_sibling).__name__, repr(_sibling.objectName()), "nativ", _sibling.testAttribute(_NATIVE))
