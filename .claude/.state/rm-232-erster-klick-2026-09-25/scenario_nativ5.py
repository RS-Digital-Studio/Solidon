# Welches QLabel des Merkmalfensters ist nativ, unter welchem Attribut, mit welchem Text?
from PySide6.QtCore import Qt as _Qt
from PySide6.QtWidgets import QWidget as _QWidget

_NATIVE = _Qt.WidgetAttribute.WA_NativeWindow
_panel = window.feature_panel
for _child in _panel.children():
    if isinstance(_child, _QWidget) and _child.testAttribute(_NATIVE):
        _names = [name for name, value in vars(_panel).items() if value is _child]
        log("natives Kind:", type(_child).__name__, "Attribut", _names, "Text", repr(getattr(_child, "text", lambda: "")()),
            "PaintOnScreen", _child.testAttribute(_Qt.WidgetAttribute.WA_PaintOnScreen),
            "TranslucentBackground", _child.testAttribute(_Qt.WidgetAttribute.WA_TranslucentBackground),
            "winId", int(_child.internalWinId() or 0))
# Innerhalb der Andockleiste: welche Nachkommen sind nativ, deren Eltern nicht nativ erzwungen wären?
_dock = window.findChild(_QWidget, "featureDock")
for _w in _dock.findChildren(_QWidget):
    if _w.testAttribute(_NATIVE):
        _parent = _w.parentWidget()
        log("  nativ in der Leiste:", type(_w).__name__, repr(_w.objectName()), "Eltern:", type(_parent).__name__)
