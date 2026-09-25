# Jedes Bild, das nach einem Merkmalklick auf dem Schirm steht, einzeln aufnehmen.
# Läuft über slot_probe.py (echtes Fenster); schreibt probe-out/frames/<klick>-<nr>.png
# und je Bild eine Zeile mit Zeit und Zustand ins Protokoll. Gespeichert wird nur,
# was sich gegenüber dem vorigen Bild geändert hat.
import hashlib as _hashlib
import time as _time

from PySide6.QtCore import Qt as _Qt

_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
_faces = [name for name, f in _entry.features.items() if f.kind == "face"][:1]
log("Bohrungen:", _holes, "Flächen:", _faces)
window.object_tree.select_object(_object_id)
idle(0.8)


def _state() -> str:
    flow = window._quiet_placement
    card = window.feature_dock
    panel = window.feature_panel
    heading = ""
    for widget in panel._built[:1]:
        heading = getattr(widget, "text", lambda: "")()[:40]
    from PySide6.QtWidgets import QScrollArea as _QScrollArea

    scroller = window.feature_dock.widget().findChild(_QScrollArea)
    inside = scroller.widget()
    bar = scroller.verticalScrollBar()
    footer = window.feature_panel.footer()
    sizes = (
        f" Sicht={scroller.viewport().height()} Inhalt={inside.height()}"
        f" min={inside.minimumSizeHint().height()} hint={inside.sizeHint().height()}"
        f" panel_min={window.feature_panel.minimumSizeHint().height()}"
        f" ops_min={window.selection_operations.minimumSizeHint().height()}"
        f" fuß={footer.height()} Balken={'ja' if bar.isVisible() else 'nein'}({bar.maximum()})"
    )
    return (
        sizes
        + f" Baum={window.object_tree.selected_feature()}"
        f" Fluss={'ja' if flow is not None else 'nein'}"
        f" Fläche={'ja' if flow is not None and flow._surface is not None else 'nein'}"
        f" Karte={card.geometry().getRect() if card.isVisible() else '-'}"
        f" Kopf='{heading}'"
    )


def _film(label: str, action, seconds: float = 1.4) -> None:
    last = None
    count = 0
    start = _time.perf_counter()
    action()
    while _time.perf_counter() - start < seconds:
        application.processEvents()
        picture = screen.grabWindow(int(window.winId()))
        small = picture.scaledToWidth(1280, _Qt.TransformationMode.SmoothTransformation)
        image = small.toImage()
        digest = _hashlib.blake2b(bytes(image.constBits()), digest_size=8).hexdigest()
        if digest != last:
            last = digest
            count += 1
            took = (_time.perf_counter() - start) * 1000.0
            small.save(str(OUT / f"{label}-{count:02d}.png"))
            dock = window.feature_dock
            corner = dock.mapTo(window, dock.rect().topLeft())
            ratio = picture.devicePixelRatio()
            picture.copy(
                int(corner.x() * ratio), int(corner.y() * ratio),
                int(dock.width() * ratio), int(dock.height() * ratio),
            ).save(str(OUT / f"{label}-{count:02d}-rechts.png"))
            log(f"BILD {label}-{count:02d} nach {took:6.0f} ms  {_state()}")
    log(f"{label}: {count} verschiedene Bilder")


_film("a-bohrung1", lambda: window.object_tree.select_feature(_object_id, _holes[0]))
idle(0.6)
_film("b-bohrung2", lambda: window.object_tree.select_feature(_object_id, _holes[1]))
idle(0.6)
_film("c-bohrung1-wieder", lambda: window.object_tree.select_feature(_object_id, _holes[0]))
idle(0.6)
if _faces:
    _film("d-flaeche", lambda: window.object_tree.select_feature(_object_id, _faces[0]))
    idle(0.6)
_film("e-bohrung2-wieder", lambda: window.object_tree.select_feature(_object_id, _holes[1]))
idle(0.6)
