# Welches Element des Auswahlfensters meldet über heightForWidth mehr Höhe, als es braucht?
# Läuft über slot_probe.py (echtes Fenster). Wählt Bohrung 1, wartet, und schreibt je
# sichtbarem Kind des Rollinhalts Lage, Höhe und heightForWidth ins Protokoll.
from PySide6.QtWidgets import QScrollArea as _QScrollArea
from PySide6.QtWidgets import QWidget as _QWidget

_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
window.object_tree.select_object(_object_id)
idle(0.8)
window.object_tree.select_feature(_object_id, _holes[0])
idle(1.0)
window.object_tree.select_feature(_object_id, _holes[1])
idle(1.0)

_scroller = window.feature_dock.widget().findChild(_QScrollArea)
_inside = _scroller.widget()
log(
    "Sicht", _scroller.viewport().size().toTuple(),
    "Inhalt", _inside.size().toTuple(),
    "hfw(Sicht)", _inside.heightForWidth(_scroller.viewport().width()),
    "hfw(Inhalt)", _inside.heightForWidth(_inside.width()),
    "min", _inside.minimumSizeHint().toTuple(), "hint", _inside.sizeHint().toTuple(),
)


def _dump(widget, depth: int, limit: int = 4) -> None:
    layout = widget.layout()
    if layout is None or depth > limit:
        return
    for index in range(layout.count()):
        item = layout.itemAt(index)
        child = item.widget()
        if child is None:
            spacer = item.spacerItem()
            if spacer is not None:
                log("  " * depth + f"[Abstand] hint={spacer.sizeHint().toTuple()} geo={spacer.geometry().getRect()}")
            elif item.layout() is not None:
                inner = item.layout()
                log("  " * depth + f"[Layout {type(inner).__name__}] geo={inner.geometry().getRect()} hfw={inner.heightForWidth(inner.geometry().width()) if inner.hasHeightForWidth() else '-'}")
            continue
        if not child.isVisible():
            continue
        text = ""
        for attribute in ("text", "title", "accessibleName"):
            value = getattr(child, attribute, None)
            if callable(value):
                text = (value() or "")[:30]
                if text:
                    break
        hfw = child.heightForWidth(child.width()) if child.hasHeightForWidth() else "-"
        log(
            "  " * depth
            + f"{type(child).__name__} '{text}' geo={child.geometry().getRect()}"
            f" hint={child.sizeHint().height()} min={child.minimumSizeHint().height()} hfw={hfw}"
        )
        _dump(child, depth + 1, limit)


_dump(_inside, 0)

_ops = window.selection_operations
_content = _ops.scroller.widget()
log(
    "Liste: Rollbereich hint", _ops.scroller.sizeHint().toTuple(),
    "Inhalt hint", _content.sizeHint().toTuple(), "Inhalt min", _content.minimumSizeHint().toTuple(),
    "Inhalt geo", _content.geometry().getRect(),
    "Schrifthöhe", _ops.scroller.fontMetrics().height(),
)
_dump(_content, 0, 2)
