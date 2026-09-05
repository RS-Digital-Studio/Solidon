"""Lange YouTube-Tutorials aus der sichtbaren Solidon-Anwendung erzeugen.

    .venv\\Scripts\\python.exe tools/make_longform_video.py
    .venv\\Scripts\\python.exe tools/make_longform_video.py montagehalter
    .venv\\Scripts\\python.exe tools/make_longform_video.py --language en

Die Filme beginnen in einem leeren Projekt und bauen ein wirklich
ausgewertetes, druckbares Modell auf. Sie verwenden dieselben Dialoge,
Operationen und Katalogeinträge wie die Anwendung. Gesprochen wird nicht:
ruhige deutsche oder englische Einblendungen und ein selbst erzeugtes Musikbett
tragen den Ablauf.

Anders als :mod:`tools.make_video` hält dieses Werkzeug nicht jede
Bildschirmsekunde als PNG fest. Ein Tutorial von mehr als drei Minuten würde
bei dreißig Vollbildern pro Sekunde mehrere Gigabyte Zwischenstand erzeugen.
Hier wird jeder fachliche Zustand einmal aus dem sichtbaren Fenster gegriffen
und über seine Lesedauer gehalten. Die Geometrie dazwischen ist trotzdem echt;
jeder Schritt wird abgewartet und auf vollständige Auswertung geprüft.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PySide6.QtCore import QPoint, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QDialog,
    QDialogButtonBox,
    QMenu,
    QWidget,
)

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.registry import REGISTRY  # noqa: E402
from app.core.scene import OperationDraft  # noqa: E402
from app.core.types import Parameter  # noqa: E402
from app.i18n import get_language, install_catalog, set_language, tr  # noqa: E402
from app.i18n.catalog import read_catalog  # noqa: E402
from app.ui.app import install_qt_translations  # noqa: E402
from app.ui.dialogs import ParameterDialog  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402
from app.ui.theme import apply_theme  # noqa: E402
from tools import make_video as video_base  # noqa: E402
from tools.make_figures import release_viewport  # noqa: E402
from tools.make_showpiece import SIZES as HOUSING_SIZES  # noqa: E402
from tools.make_showpiece import steps as housing_steps  # noqa: E402

FRAME_SIZE: Final = (1920, 1080)
MINIMUM_SECONDS: Final = 185.0
OUTPUT_DIR: Final = ROOT / "marketing" / "video" / "longform"
ENGLISH_PARAMETERS: Final = {
    "plattenstaerke": "plate_thickness",
    "lochabstand": "hole_spacing",
    "breite": "width",
    "tiefe": "depth",
    "hoehe": "height",
    "wand": "wall",
    "rohr": "shaft_diameter",
    "platte": "plate_thickness",
}
_captions: dict[str, str] = {}


def _text(source: str, **values: object) -> str:
    """Filmtexte aus dem eigenen Katalog, App-Begriffe aus der Anwendung übersetzen."""
    translated = _captions.get(source, tr(source))
    return translated.format(**values) if values else translated


def _parameter_name(name: str) -> str:
    """Benutzermaße im englischen Film samt ihren Ausdrücken englisch benennen."""
    return ENGLISH_PARAMETERS.get(name, name) if get_language() == "en" else name


def _localized_values(values: Mapping[str, Any]) -> dict[str, Any]:
    """Nur Namen und Parameterverweise übersetzen; Geometriewerte bleiben erhalten."""
    result = dict(values)
    for key, value in result.items():
        if isinstance(value, str) and value.startswith("="):
            result[key] = re.sub(
                r"@([A-Za-z_][A-Za-z_0-9]*)",
                lambda match: "@" + _parameter_name(match.group(1)),
                value,
            )
        elif key == "name" and isinstance(value, str):
            result[key] = _text(value)
    return result


@dataclass(frozen=True, slots=True)
class Slide:
    """Ein sichtbarer Zustand mit seiner Lesedauer."""

    path: Path
    seconds: float


class Recorder:
    """Greift echte Fensterzustände und schreibt daraus einen Film."""

    def __init__(
        self,
        app: QApplication,
        window: MainWindow,
        folder: Path,
        chapter: str,
    ) -> None:
        self.app = app
        self.window = window
        self.folder = folder
        self.chapter = chapter
        self.slides: list[Slide] = []
        self.events: list[dict[str, Any]] = []
        self._pointer: QPoint | None = None
        self._image_index = 0
        folder.mkdir(parents=True, exist_ok=True)

    @property
    def seconds(self) -> float:
        return sum(slide.seconds for slide in self.slides)

    def add(
        self,
        title: str,
        detail: str,
        seconds: float = 6.0,
        *,
        dialog: QDialog | None = None,
        target: QWidget | QPoint | None = None,
        click: bool = False,
        title_card: bool = False,
        overlays: Sequence[QWidget] = (),
        caption_bottom: bool = False,
    ) -> None:
        """Fenster, höchstens einen Dialog, Text und einen bewegten Zeiger aufnehmen."""
        if seconds <= 0.0:
            raise ValueError("Eine Folie braucht eine positive Dauer.")
        self.events.append(
            {
                "start": self.seconds,
                "duration": seconds,
                "title": _text(title),
                "detail": _text(detail),
            }
        )
        frame = self._capture_frame(
            title,
            detail,
            dialog=dialog,
            title_card=title_card,
            overlays=overlays,
            caption_bottom=caption_bottom,
        )
        point = self._point_for(target)
        movement = 0.0
        if (
            point is not None
            and self._pointer is not None
            and not click
            and not title_card
            and (point - self._pointer).manhattanLength() >= 24
        ):
            movement = min(0.6, max(0.0, seconds - 0.25))
            count = max(2, round(movement * 30.0))
            movement = count / 30.0
            for index in range(1, count + 1):
                phase = index / count
                eased = phase * phase * (3.0 - 2.0 * phase)
                moving = frame.copy()
                x = self._pointer.x() + (point.x() - self._pointer.x()) * eased
                y = self._pointer.y() + (point.y() - self._pointer.y()) * eased
                video_base._paint_pointer(moving, (x, y, False))
                self._store(moving, 1.0 / 30.0)

        if point is not None:
            video_base._paint_pointer(frame, (float(point.x()), float(point.y()), click))
        self._store(frame, max(0.05, seconds - movement))
        self._pointer = None if title_card else point or self._pointer

    def _capture_frame(
        self,
        title: str,
        detail: str,
        *,
        dialog: QDialog | None = None,
        title_card: bool = False,
        overlays: Sequence[QWidget] = (),
        caption_bottom: bool = False,
        settle_frames: int = 12,
    ) -> QImage:
        """Den aktuellen sichtbaren Zustand ohne Zeiger als Videobild greifen."""
        if dialog is not None:
            _place_dialog(self.window, dialog)
            dialog.raise_()
            dialog.activateWindow()
        elif not overlays:
            self.window.raise_()
            self.window.activateWindow()
        if settle_frames:
            video_base.settle(self.app, settle_frames)

        screen = self.app.primaryScreen()
        if screen is None:
            raise SystemExit("Kein Bildschirm verfügbar — kein Video erzeugt.")
        captured = screen.grabWindow(self.window.winId()).toImage()
        if captured.isNull():
            raise SystemExit("Das sichtbare Solidon-Fenster ließ sich nicht aufnehmen.")
        captured.setDevicePixelRatio(1.0)
        frame = captured.scaled(
            *FRAME_SIZE,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        frame.setDevicePixelRatio(1.0)

        if dialog is not None:
            self._paint_dialog(frame, dialog)
        for overlay in overlays:
            self._paint_dialog(frame, overlay)
        self._paint_caption(
            frame,
            title,
            detail,
            title_card=title_card,
            bottom=caption_bottom,
        )
        return frame

    def _store(self, frame: QImage, seconds: float) -> None:
        """Ein Einzelbild unter einer eindeutigen Nummer in die Zeitleiste schreiben."""
        path = self.folder / f"{self._image_index:05d}.png"
        if not frame.save(str(path), "PNG"):
            raise SystemExit(f"Bild ließ sich nicht schreiben: {path}")
        self.slides.append(Slide(path, seconds))
        self._image_index += 1

    def orbit(
        self,
        title: str,
        detail: str,
        *,
        seconds: float = 2.0,
        degrees: float = 42.0,
        zoom: float = 1.0,
    ) -> None:
        """Das Modell in einer kurzen, ruhigen Kamerafahrt räumlich zeigen."""
        viewport = self.window.viewport
        plotter = viewport.plotter
        if plotter is None:
            self.add(title, detail, seconds, target=viewport)
            return
        self.window.raise_()
        self.window.activateWindow()
        self.events.append(
            {
                "start": self.seconds,
                "duration": seconds,
                "title": _text(title),
                "detail": _text(detail),
            }
        )
        viewport.reset_camera()
        if zoom != 1.0:
            viewport.zoom(zoom)
        video_base.settle(self.app, 16)

        camera = plotter.camera
        focal = tuple(float(value) for value in camera.focal_point)
        position = tuple(float(value) for value in camera.position)
        offset_x = position[0] - focal[0]
        offset_y = position[1] - focal[1]
        radius = math.hypot(offset_x, offset_y)
        start = math.atan2(offset_y, offset_x)
        height = position[2]
        count = max(2, round(seconds * 20.0))
        for index in range(1, count + 1):
            phase = index / count
            eased = phase * phase * (3.0 - 2.0 * phase)
            angle = start + math.radians(degrees) * eased
            camera.position = (
                focal[0] + radius * math.cos(angle),
                focal[1] + radius * math.sin(angle),
                height,
            )
            redraw = getattr(viewport, "_redraw_shadows", None)
            if callable(redraw):
                redraw()
            plotter.render()
            self.app.processEvents()
            frame = self._capture_frame(
                title,
                detail,
                settle_frames=0,
            )
            self._store(frame, seconds / count)
        self._pointer = None

    def click(
        self,
        title: str,
        detail: str,
        *,
        dialog: QDialog | None = None,
        target: QWidget,
    ) -> None:
        """Einen kurzen, sichtbaren Klickring vor der Handlung ergänzen."""
        self.add(title, detail, 0.35, dialog=dialog, target=target, click=True)

    def ensure_minimum(self, title: str, detail: str) -> None:
        """Die Dreiminuten-Grenze mit einer sinnvollen Schlusskarte sichern."""
        rest = MINIMUM_SECONDS - self.seconds
        if rest > 0.0:
            self.add(title, detail, rest + 1.0, title_card=True)

    def _paint_dialog(self, frame: QImage, dialog: QWidget) -> None:
        """Ein separates Dialog- oder Menüfenster über den Fenstergriff legen."""
        picture = dialog.grab().toImage()
        picture.setDevicePixelRatio(1.0)
        origin = self.window.mapToGlobal(QPoint(0, 0))
        placed = dialog.mapToGlobal(QPoint(0, 0)) - origin
        scale_x = frame.width() / max(1, self.window.width())
        scale_y = frame.height() / max(1, self.window.height())
        width = max(1, round(dialog.width() * scale_x))
        height = max(1, round(dialog.height() * scale_y))
        picture = picture.scaled(
            width,
            height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter = QPainter(frame)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(QColor(0, 0, 0, 100))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            QRectF(
                placed.x() * scale_x + 14,
                placed.y() * scale_y + 18,
                width,
                height,
            ),
            12,
            12,
        )
        painter.drawImage(
            round(placed.x() * scale_x),
            round(placed.y() * scale_y),
            picture,
        )
        painter.end()

    def _point_for(self, target: QWidget | QPoint | None) -> QPoint | None:
        """Ein Widget oder einen globalen Punkt in das Videobild übersetzen."""
        if target is None:
            return None
        global_point = (
            target if isinstance(target, QPoint) else target.mapToGlobal(target.rect().center())
        )
        local = global_point - self.window.mapToGlobal(QPoint(0, 0))
        return QPoint(
            round(local.x() * FRAME_SIZE[0] / max(1, self.window.width())),
            round(local.y() * FRAME_SIZE[1] / max(1, self.window.height())),
        )

    def _paint_caption(
        self,
        frame: QImage,
        title: str,
        detail: str,
        *,
        title_card: bool,
        bottom: bool = False,
    ) -> None:
        """Eine ruhige, telefonlesbare Einblendung über die Anwendung setzen."""
        title, detail = _text(title), _text(detail)
        painter = QPainter(frame)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        if title_card:
            box = QRectF(205, 255, 1510, 495)
            painter.setBrush(QColor(18, 22, 29, 236))
            painter.drawRoundedRect(box, 28, 28)
            painter.setBrush(QColor("#e08b4e"))
            painter.drawRoundedRect(QRectF(205, 255, 18, 495), 9, 9)
            painter.setPen(QColor("#f7f9fb"))
            painter.setFont(QFont("Segoe UI", 42, QFont.Weight.DemiBold))
            painter.drawText(
                QRectF(285, 330, 1350, 130),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                title,
            )
            painter.setPen(QColor("#d4d9e1"))
            painter.setFont(QFont("Segoe UI", 25))
            painter.drawText(
                QRectF(285, 485, 1280, 180),
                Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop,
                detail,
            )
        else:
            top = 924 if bottom else 24
            box = QRectF(34, top, 1230, 132)
            painter.setBrush(QColor(18, 22, 29, 228))
            painter.drawRoundedRect(box, 20, 20)
            painter.setBrush(QColor("#e08b4e"))
            painter.drawRoundedRect(QRectF(34, top, 12, 132), 6, 6)
            painter.setPen(QColor("#aeb8c8"))
            painter.setFont(QFont("Segoe UI", 15, QFont.Weight.DemiBold))
            painter.drawText(QRectF(70, top + 13, 1170, 24), _text(self.chapter).upper())
            painter.setPen(QColor("#f7f9fb"))
            painter.setFont(QFont("Segoe UI", 27, QFont.Weight.DemiBold))
            painter.drawText(QRectF(70, top + 37, 1170, 42), title)
            painter.setPen(QColor("#d4d9e1"))
            painter.setFont(QFont("Segoe UI", 17))
            painter.drawText(
                QRectF(70, top + 80, 1170, 40),
                Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop,
                detail,
            )

        painter.end()


def _place_dialog(window: MainWindow, dialog: QDialog) -> None:
    """Den einzigen Dialog unterhalb der Einblendung im Fenster halten."""
    dialog.setModal(False)
    dialog.adjustSize()
    dialog.show()
    video_base.settle(QApplication.instance(), 8)  # type: ignore[arg-type]
    origin = window.mapToGlobal(QPoint(0, 0))
    x = origin.x() + max(20, (window.width() - dialog.width()) // 2)
    y = origin.y() + 175
    maximum_y = origin.y() + window.height() - dialog.height() - 25
    dialog.move(x, max(origin.y() + 165, min(y, maximum_y)))


def _button(dialog: QDialog) -> QWidget:
    """Den primären Knopf eines echten Dialogs finden."""
    box = dialog.findChild(QDialogButtonBox)
    if box is None:
        raise SystemExit(f"{dialog.windowTitle()}: keine Knopfleiste gefunden.")
    button = box.button(QDialogButtonBox.StandardButton.Ok)
    if button is None:
        for role in (
            QDialogButtonBox.StandardButton.Save,
            QDialogButtonBox.StandardButton.Apply,
        ):
            button = box.button(role)
            if button is not None:
                break
    if button is None:
        raise SystemExit(f"{dialog.windowTitle()}: kein primärer Knopf gefunden.")
    return button


def _menu_path(window: MainWindow, action: Any) -> list[tuple[QMenu, Any]]:
    """Den sichtbaren Weg von der Menüleiste bis zu einer Aktion finden."""
    menus = [menu for menu in window._menus if action in menu.actions()]
    if not menus:
        return []
    menu = menus[0]
    path: list[tuple[QMenu, Any]] = [(menu, action)]
    top_actions = window.menuBar().actions()
    while menu.menuAction() not in top_actions:
        parent = next(
            (candidate for candidate in window._menus if menu.menuAction() in candidate.actions()),
            None,
        )
        if parent is None:
            return []
        path.append((parent, menu.menuAction()))
        menu = parent
    path.reverse()
    return path


def _show_action_path(
    recorder: Recorder,
    action: Any,
    detail: str,
    *,
    seconds: float = 4.2,
) -> bool:
    """Eine echte Menüfolge mit Mausweg und hervorgehobenem Ziel zeigen."""
    path = _menu_path(recorder.window, action)
    if not path:
        return False
    root = path[0][0]
    root_action = root.menuAction()
    menu_bar = recorder.window.menuBar()
    root_point = menu_bar.mapToGlobal(menu_bar.actionGeometry(root_action).center())
    recorder.add(
        _text("Menü {title} öffnen", title=root.title()),
        detail,
        2.5,
        target=root_point,
        caption_bottom=True,
    )
    recorder.add(
        _text("Menü {title} öffnen", title=root.title()),
        detail,
        0.45,
        target=root_point,
        click=True,
        caption_bottom=True,
    )

    visible: list[QMenu] = []
    for index, (menu, chosen) in enumerate(path):
        menu.ensurePolished()
        menu.adjustSize()
        if index == 0:
            origin = menu_bar.mapToGlobal(menu_bar.actionGeometry(root_action).bottomLeft())
        else:
            parent, parent_action = path[index - 1]
            origin = parent.mapToGlobal(parent.actionGeometry(parent_action).topRight())
        menu.popup(origin)
        menu.setActiveAction(chosen)
        visible.append(menu)
        video_base.settle(recorder.app, 8)

    leaf_menu, leaf_action = path[-1]
    point = leaf_menu.mapToGlobal(leaf_menu.actionGeometry(leaf_action).center())
    labels = [root.title(), *(entry.text().replace("&", "") for _menu, entry in path)]
    recorder.add(
        " → ".join(labels),
        "Dieser sichtbare Menüpunkt öffnet den nächsten gezeigten Dialog.",
        seconds,
        target=point,
        overlays=tuple(visible),
        caption_bottom=True,
    )
    recorder.add(
        " → ".join(labels),
        "Jetzt wird genau diese Funktion gewählt.",
        0.45,
        target=point,
        click=True,
        overlays=tuple(visible),
        caption_bottom=True,
    )
    for menu in reversed(visible):
        menu.close()
    video_base.settle(recorder.app, 6)
    return True


def _operation_action(window: MainWindow, op_name: str) -> Any | None:
    """Die Menüaktion einer Operation einschließlich Varianteneintrag liefern."""
    return window._op_actions.get(op_name) or window._variant_actions.get(op_name)


def _draw_rectangle(recorder: Recorder, panel: Any, length: float, width: float) -> None:
    """Ein Rechteck über das echte Werkzeug, zwei Mausziele und zwei Maße zeichnen."""
    recorder.add(
        "Skizzenwerkzeug → Rechteck",
        "Der Rechteckknopf ist der direkte Weg: eine Ecke setzen, dann die Gegenecke.",
        2.8,
        target=panel.shapes_button,
    )
    recorder.click(
        "Rechteckwerkzeug aktivieren",
        "Jetzt folgen die beiden Punkte direkt im Viewport.",
        target=panel.shapes_button,
    )
    panel.shapes_button.click()
    video_base.settle(recorder.app, 8)

    first = (-length / 2.0, -width / 2.0)
    opposite = (length / 2.0, width / 2.0)
    first_local = recorder.window.viewport.sketch_screen_at(first)
    opposite_local = recorder.window.viewport.sketch_screen_at(opposite)
    if first_local is None or opposite_local is None:
        raise SystemExit("Die beiden Rechteckpunkte sind im Skizzenviewport nicht sichtbar.")
    first_point = recorder.window.viewport.mapToGlobal(first_local)
    opposite_point = recorder.window.viewport.mapToGlobal(opposite_local)
    recorder.add(
        "Erste Rechteckecke setzen",
        "Der Mausweg endet links unten am sichtbaren Rasterpunkt.",
        2.4,
        target=first_point,
    )
    recorder.add(
        "Erste Rechteckecke setzen",
        "Ein echter Skizzenklick legt den Startpunkt fest.",
        0.3,
        target=first_point,
        click=True,
    )
    panel.canvas.place_on_plane(first)
    panel.canvas.note_pointer(panel.canvas._to_screen(*opposite))
    video_base.settle(recorder.app, 8)
    recorder.add(
        "Maus zur Gegenecke bewegen",
        "Die Live-Vorschau zeigt bereits das entstehende Rechteck.",
        2.8,
        target=opposite_point,
    )

    panel.canvas.measure_field.set_value_mm(length)
    recorder.add(
        _text("Breite exakt auf {value:g} mm setzen", value=length),
        "Das Maßfeld steht direkt am Mauszeiger und speichert eine Bedingung.",
        2.8,
        target=panel.canvas.measure_field,
    )
    recorder.click(
        _text("{value:g} mm übernehmen", value=length),
        "Tab wechselt danach zum zweiten Rechteckmaß.",
        target=panel.canvas.measure_field,
    )
    panel.canvas.place_measured(length)
    video_base.settle(recorder.app, 8)

    panel.canvas.second_measure_field.set_value_mm(width)
    recorder.add(
        _text("Höhe exakt auf {value:g} mm setzen", value=width),
        "Auch das zweite Maß bleibt als editierbare Skizzenbedingung erhalten.",
        2.8,
        target=panel.canvas.second_measure_field,
    )
    recorder.click(
        _text("{value:g} mm übernehmen", value=width),
        "Damit wird der geschlossene Umriss fertiggestellt.",
        target=panel.canvas.second_measure_field,
    )
    panel.canvas.place_second_measured(width)
    video_base.settle(recorder.app, 12)


def _select(window: MainWindow, object_id: str) -> None:
    """Einen Wirtskörper sichtbar wählen."""
    window.object_tree.select_object(object_id)
    video_base.settle(QApplication.instance(), 8)  # type: ignore[arg-type]


def _fit(window: MainWindow, app: QApplication) -> None:
    """Die Szene für einen lesbaren Ergebniszustand einpassen."""
    # Orange Auswahl ist im Bedienmoment hilfreich, verdeckt in einem
    # Ergebnisbild aber gerade kleine Senkungen und Innenkanten. Der nächste
    # Schritt wählt seinen Wirtskörper ohnehin wieder ausdrücklich.
    window.object_tree.tree.clearSelection()
    window.viewport.view_from("iso")
    window.viewport.reset_camera()
    video_base.settle(app, 18)


def _view(window: MainWindow, app: QApplication, direction: str, zoom: float = 1.0) -> None:
    """Eine gezielte Ansicht einstellen und kleine Details lesbar heranholen."""
    window.object_tree.tree.clearSelection()
    window.viewport.view_from(direction)
    window.viewport.reset_camera()
    if zoom != 1.0:
        window.viewport.zoom(zoom)
    video_base.settle(app, 18)


def _highlight_kind(window: MainWindow, session: Session, object_id: str, kind: str) -> int:
    """Alle Merkmale einer Art in der blauen Merkmalsauswahl zeigen."""
    result = session.last_result
    if result is None or object_id not in result.scene.objects:
        return 0
    feature_ids = [
        feature_id
        for feature_id, feature in result.scene.objects[object_id].features.items()
        if feature.kind == kind
    ]
    if not feature_ids:
        return 0
    _select(window, object_id)
    window.viewport.select_features(feature_ids)
    video_base.settle(QApplication.instance(), 12)  # type: ignore[arg-type]
    return len(feature_ids)


def _verify(session: Session, context: str) -> None:
    """Auf die echte Auswertung warten und unvollständige Schritte stoppen."""
    session.wait_for_idle(120_000)
    result = session.last_result
    if result is None:
        raise SystemExit(f"{context}: keine Auswertung erhalten.")
    if not result.complete:
        findings = "; ".join(
            f"{entry.code}: {entry.message}" for entry in result.scene.report.findings
        )
        raise SystemExit(f"{context}: Auswertung hält an. {findings}")


def _apply(
    session: Session,
    title: str,
    drafts: Sequence[OperationDraft],
    *,
    bundle: bool = False,
) -> None:
    """Eine echte Transaktion anwenden und vollständig prüfen."""
    localized = [replace(draft, params=_localized_values(draft.params)) for draft in drafts]
    session.apply(_text(title), localized, raise_on_error=True, bundle=bundle)
    _verify(session, title)


def _add_parameter(
    recorder: Recorder,
    session: Session,
    name: str,
    title: str,
    value: float,
    *,
    minimum: float,
    maximum: float,
) -> None:
    """Den Parameterdialog zeigen und dasselbe Maß in die Sitzung übernehmen."""
    recorder.add(
        "Parameterleiste → Parameter anlegen …",
        _text("Hier beginnt der echte Bedienweg für das Projektmaß {title}.", title=_text(title)),
        2.8,
        target=recorder.window.parameters.add_button,
    )
    recorder.click(
        "Parameter anlegen … öffnen",
        "Der Klick öffnet den gleich gezeigten Dialog.",
        target=recorder.window.parameters.add_button,
    )
    dialog = ParameterDialog(session.project.document.parameters, recorder.window)
    dialog.name_field.setText(_parameter_name(name))
    dialog.value_field.setValue(value)
    dialog.minimum_field.setText(f"{minimum:g}")
    dialog.maximum_field.setText(f"{maximum:g}")
    action = _button(dialog)
    recorder.add(
        _text("Projektmaß: {title}", title=_text(title)),
        _text("{value:g} mm - mit sinnvollen Grenzen für spätere Varianten.", value=value),
        5.8,
        dialog=dialog,
        target=dialog.value_field,
    )
    recorder.click(
        _text("{title} anlegen", title=_text(title)),
        "Der Name kann in allen folgenden Operationen mit @ verwendet werden.",
        dialog=dialog,
        target=action,
    )
    dialog.close()
    dialog.deleteLater()
    parameter = Parameter(
        name=_parameter_name(name),
        value=value,
        unit="mm",
        title=_text(title),
        minimum=minimum,
        maximum=maximum,
    )
    if not session.add_parameter(parameter):
        raise SystemExit(f"Parameter ließ sich nicht anlegen: {name}")
    _verify(session, f"Parameter {name}")
    recorder.add(
        _text("{title} steht im Projekt", title=_text(title)),
        "Die Parameterleiste wird zur zentralen Stelle für Varianten.",
        4.2,
        target=recorder.window.parameters,
    )


def _edit_parameter(
    recorder: Recorder,
    session: Session,
    name: str,
    value: float,
    title: str,
) -> None:
    """Einen vorhandenen Parameter direkt in seiner echten Seitenzeile ändern."""
    field = recorder.window.parameters._editors.get(_parameter_name(name))
    if field is None:
        raise SystemExit(f"Parameterfeld ist in der Seitenleiste nicht sichtbar: {name}")
    recorder.add(
        _text("Parameterleiste → {title}", title=_text(title)),
        _text("Das sichtbare Wertefeld wird von Hand auf {value:g} mm geändert.", value=value),
        4.2,
        target=field,
    )
    recorder.click(
        _text("{value:g} mm in das Feld eingeben", value=value),
        "Nach der Eingabe rechnet Solidon alle abhängigen Schritte neu.",
        target=field,
    )
    field.setValue(value)
    video_base.settle(recorder.app, 10)
    _verify(session, f"Parameter {name} ändern")
    _fit(recorder.window, recorder.app)


def _show_catalog(
    recorder: Recorder,
    part_name: str,
    title: str,
    detail: str,
    *,
    search: str = "",
) -> None:
    """Den echten Katalog mit genau einem gewählten Baustein zeigen."""
    _show_action_path(
        recorder,
        recorder.window._catalog_action,
        "Der Bausteinkatalog ist über die Menüleiste und Strg+K erreichbar.",
    )
    catalog = recorder.window._make_catalog()
    catalog.resize(1120, 760)
    if search:
        catalog.search.setText(_text(search))
    catalog.show_file_result("", part_name=part_name)
    catalog.set_can_insert(True)
    catalog.set_feature_chosen(False)
    video_base.settle(recorder.app, 30)
    item = catalog._item_named(part_name)
    point: QPoint | None = None
    if item is not None:
        rectangle = catalog.list.visualItemRect(item)
        point = catalog.list.mapToGlobal(rectangle.center())
    recorder.add(title, detail, 5.8, dialog=catalog, target=point)
    if catalog._insert is not None:
        recorder.click(
            "Gewählten Baustein einsetzen",
            "Dieser Klick führt in den anschließend gezeigten Parameterdialog.",
            dialog=catalog,
            target=catalog._insert,
        )
    catalog.release()
    catalog.close()
    catalog.deleteLater()
    video_base.settle(recorder.app, 8)


def _show_operation(
    recorder: Recorder,
    session: Session,
    op_name: str,
    values: Mapping[str, Any],
    title: str,
    detail: str,
    *,
    object_id: str = "",
    focus: str = "",
    result_title: str,
    result_detail: str,
    result_seconds: float = 7.0,
) -> None:
    """Eine Operation über ihren echten Dialog bestätigen und ihr Ergebnis zeigen."""
    if object_id:
        _select(recorder.window, object_id)
    action = _operation_action(recorder.window, op_name)
    if action is not None:
        _show_action_path(
            recorder,
            action,
            _text(
                "So wird „{title}“ in der echten Anwendung aufgerufen.",
                title=REGISTRY.get(op_name).title,
            ),
        )
    spec = REGISTRY.get(op_name)
    if not spec.params.spec():
        # Eine Operation ohne Werte hat absichtlich keinen Dialog. Vorher und
        # nachher zeigen ist hier die ehrliche Bedienfolge; einen erfundenen
        # Bestätigungsknopf darf der Film nicht ergänzen.
        recorder.add(title, detail, 6.0, target=recorder.window.viewport)
        recorder.window.run_operation(spec, given=_localized_values(values))
        _verify(session, title)
        _fit(recorder.window, recorder.app)
        recorder.add(
            result_title,
            result_detail,
            result_seconds,
            target=recorder.window.viewport,
        )
        return
    recorder.window.run_operation(spec, given=_localized_values(values))
    video_base.settle(recorder.app, 20)
    dialog = recorder.window._op_dialog
    if dialog is None:
        raise SystemExit(f"{op_name}: Operationsdialog ging nicht auf.")
    target = dialog._editors.get(focus) if focus else None
    recorder.add(title, detail, 7.0, dialog=dialog, target=target or _button(dialog))
    action = _button(dialog)
    recorder.click(
        title,
        "Die Live-Vorschau verwendet bereits diese Werte.",
        dialog=dialog,
        target=action,
    )
    dialog.accept()
    _verify(session, title)
    _fit(recorder.window, recorder.app)
    recorder.add(result_title, result_detail, result_seconds, target=recorder.window.viewport)


def _show_bundled_operation(
    recorder: Recorder,
    session: Session,
    title: str,
    drafts: Sequence[OperationDraft],
    dialog_title: str,
    dialog_detail: str,
    *,
    focus: str,
    result_title: str,
    result_detail: str,
    result_seconds: float = 7.0,
) -> None:
    """Eine Mehrfachtransaktion über den echten Dialog ihres ersten Teils zeigen."""
    if not drafts:
        raise ValueError("Eine Mehrfachtransaktion braucht mindestens eine Operation.")
    first = drafts[0]
    if first.inputs:
        _select(recorder.window, first.inputs[0])
    recorder.window.run_operation(REGISTRY.get(first.op), given=_localized_values(first.params))
    video_base.settle(recorder.app, 20)
    dialog = recorder.window._op_dialog
    if dialog is None:
        raise SystemExit(f"{first.op}: Operationsdialog ging nicht auf.")
    target = dialog._editors.get(focus) or _button(dialog)
    recorder.add(dialog_title, dialog_detail, 6.2, dialog=dialog, target=target)
    recorder.click(
        title,
        _text(
            "Alle {count} gleichartigen Einsätze werden gemeinsam übernommen.", count=len(drafts)
        ),
        dialog=dialog,
        target=_button(dialog),
    )
    dialog.reject()
    _apply(session, title, drafts)
    _fit(recorder.window, recorder.app)
    recorder.add(result_title, result_detail, result_seconds, target=recorder.window.viewport)


def _begin_video(
    app: QApplication,
    chapter: str,
    folder: Path,
) -> tuple[Session, MainWindow, Recorder]:
    """Ein leeres sichtbares Projekt für genau einen Film öffnen."""
    session = Session()
    window = MainWindow(session, UiSettings(language=get_language()))
    window.resize(*FRAME_SIZE)
    window.move(0, 0)
    window.show()
    session.start_new()
    window._show_start_screen(False)
    _verify(session, "Leeres Projekt")
    window.raise_()
    window.activateWindow()
    video_base.settle(app, 40)
    return session, window, Recorder(app, window, folder, chapter)


def _finish_video(session: Session, window: MainWindow) -> None:
    """Arbeiter und OpenGL-Kontext ohne Speichernachfrage freigeben."""
    session._dirty = False
    window.close()
    session.release(120_000)
    release_viewport(window)


def story_mounting_bracket(app: QApplication, folder: Path) -> Recorder:
    """Eine parametrisierbare Montagehalterung aus einer Skizze bauen."""
    session, window, recorder = _begin_video(app, "Montagehalter aus Skizze", folder)
    recorder.add(
        "Vom leeren Projekt zum druckbaren Montagehalter",
        "Skizze, Projektmaße, Senkbohrungen, Versteifungsrippe, Variante und Rückgängig.",
        8.0,
        title_card=True,
    )
    recorder.add(
        "Wir beginnen wirklich leer",
        "Kein vorbereitetes STL und keine versteckte Quelldatei: nur das Druckbett.",
        6.0,
        target=window.viewport,
    )
    _add_parameter(
        recorder,
        session,
        "plattenstaerke",
        "Plattenstärke",
        6.0,
        minimum=3.0,
        maximum=12.0,
    )
    _add_parameter(
        recorder,
        session,
        "lochabstand",
        "Lochabstand",
        50.0,
        minimum=30.0,
        maximum=64.0,
    )

    sketch_action = _operation_action(window, "sketch_extrude")
    if sketch_action is not None:
        _show_action_path(
            recorder,
            sketch_action,
            "Der Menüpunkt öffnet den Skizzenmodus für eine neue Grundform.",
        )
    window.start_sketch("sketch_extrude")
    video_base.settle(app, 30)
    panel = window._sketch_panel
    if panel is None:
        raise SystemExit("Skizzenmodus ging nicht auf.")
    _draw_rectangle(recorder, panel, 70.0, 45.0)
    recorder.add(
        "Das Rechteck misst 70 x 45 mm",
        "Raster, Fang und beide Maße bleiben direkt am fertigen Umriss sichtbar.",
        5.0,
        target=window.viewport,
    )
    recorder.add(
        "Die Skizze ist noch keine Geometrie",
        "Erst die nächste Operation entscheidet, wie aus dem geschlossenen Umriss ein Körper wird.",
        6.0,
        target=panel,
    )
    window.finish_sketch(
        keep=True,
        given=_localized_values({"height": "=@plattenstaerke", "name": "Montagehalter"}),
    )
    video_base.settle(app, 25)
    dialog = window._op_dialog
    if dialog is None:
        raise SystemExit("Extrusionsdialog ging nicht auf.")
    recorder.add(
        "Skizze aufziehen",
        "Die Höhe folgt @plattenstaerke - eine spätere Variante baut denselben Verlauf neu.",
        7.0,
        dialog=dialog,
        target=dialog._editors.get("height"),
    )
    action = _button(dialog)
    recorder.click(
        "Montageplatte erzeugen",
        "Ein Klick übernimmt den sichtbaren Vorschauzustand.",
        dialog=dialog,
        target=action,
    )
    dialog.accept()
    _verify(session, "Skizze aufziehen")
    _fit(window, app)
    recorder.add(
        "Der erste druckbare Körper steht",
        "Die Skizze bleibt als Parameter des ersten Verlaufsschritts editierbar.",
        7.0,
        target=window.viewport,
    )

    _select(window, "obj_1")
    _show_catalog(
        recorder,
        "screw_hole",
        "Katalog: Schraubenloch mit Senkung",
        "Normgröße statt geratenem Durchmesser - hier M4 mit bündigem Schraubenkopf.",
        search="Schraubenloch",
    )
    recorder.window.run_operation(
        REGISTRY.get("insert_screw_hole"),
        given=_localized_values(
            {
                "size": "M4",
                "depth": "=@plattenstaerke",
                "countersink": True,
                "x": "=-@lochabstand/2",
                "y": 0.0,
                "z": "=@plattenstaerke",
            }
        ),
    )
    video_base.settle(app, 20)
    dialog = window._op_dialog
    if dialog is None:
        raise SystemExit("Schraubenlochdialog ging nicht auf.")
    recorder.add(
        "Erste M4-Senkbohrung positionieren",
        "Die X-Position ist kein Festwert: -@lochabstand/2.",
        7.0,
        dialog=dialog,
        target=dialog._editors.get("x"),
    )
    recorder.click(
        "Bohrung setzen",
        "Die zweite Seite verwendet denselben Parameter mit positivem Vorzeichen.",
        dialog=dialog,
        target=_button(dialog),
    )
    dialog.reject()
    _apply(
        session,
        "Zwei M4-Senkbohrungen",
        [
            OperationDraft(
                op="insert_screw_hole",
                inputs=("obj_1",),
                params={
                    "size": "M4",
                    "depth": "=@plattenstaerke",
                    "countersink": True,
                    "x": "=-@lochabstand/2",
                    "y": 0.0,
                    "z": "=@plattenstaerke",
                },
            ),
            OperationDraft(
                op="insert_screw_hole",
                inputs=("obj_1",),
                params={
                    "size": "M4",
                    "depth": "=@plattenstaerke",
                    "countersink": True,
                    "x": "=@lochabstand/2",
                    "y": 0.0,
                    "z": "=@plattenstaerke",
                },
            ),
        ],
    )
    _view(window, app, "top", 1.8)
    if _highlight_kind(window, session, "obj_1", "hole") < 2:
        raise SystemExit("Die zwei Schraubenlöcher sind im Ergebnis nicht sichtbar benannt.")
    recorder.add(
        "Jetzt sind beide M4-Senkbohrungen wirklich zu sehen",
        "Die nahe Draufsicht und die blaue Merkmalsfläche zeigen Bohrung und Senkung eindeutig.",
        8.5,
        target=window.viewport,
    )

    _show_catalog(
        recorder,
        "rib",
        "Katalog: Versteifungsrippe",
        "Mehr Steifigkeit ohne unnötig massive Platte - Länge, Höhe und Wand bleiben einstellbar.",
        search="Versteifungsrippe",
    )
    _show_operation(
        recorder,
        session,
        "insert_rib",
        {
            "length": 30.0,
            "height": 14.0,
            "thickness": 3.0,
            "fillet": 2.0,
            "x": 0.0,
            "y": 0.0,
            "z": "=@plattenstaerke",
            "axis": "y",
        },
        "Rippe an die Platte setzen",
        "Die Verrundung reduziert eine harte Kerbe am Übergang.",
        object_id="obj_1",
        focus="height",
        result_title="Leicht und steif statt einfach nur dick",
        result_detail="Der Katalogbaustein ist mit dem Grundkörper zu einer Komponente verbunden.",
    )
    recorder.orbit(
        "Bohrungen und Rippe aus mehreren Blickwinkeln",
        "Die kurze Kamerafahrt zeigt Senkungen, Innenkanten und den Übergang der Rippe.",
        seconds=2.6,
        degrees=48.0,
        zoom=1.08,
    )

    _edit_parameter(recorder, session, "lochabstand", 60.0, "Lochabstand")
    _view(window, app, "top", 1.8)
    _highlight_kind(window, session, "obj_1", "hole")
    recorder.add(
        "Die Bohrungen wandern - die Rippe bleibt",
        (
            "Nur der benannte Abstand änderte sich; Skizze und alle späteren "
            "Schritte blieben erhalten."
        ),
        8.0,
        target=window.viewport,
    )
    session.undo()
    _verify(session, "Parameteränderung zurücknehmen")
    _view(window, app, "top", 1.8)
    _highlight_kind(window, session, "obj_1", "hole")
    recorder.add(
        "Rückgängig stellt die vorige Variante wieder her",
        "Auch Parameteränderungen sind normale Verlaufsschritte.",
        6.0,
        target=window.viewport,
    )
    _show_operation(
        recorder,
        session,
        "place_on_bed",
        {},
        "Für den Druck auf das Bett legen",
        "Solidon richtet die niedrigste Stelle auf Z = 0 aus.",
        object_id="obj_1",
        result_title="Fertig zum Slicen",
        result_detail="Ein Körper, zwei M4-Senkbohrungen und eine verrundete Versteifungsrippe.",
        result_seconds=8.0,
    )
    window.right.setCurrentWidget(window.report)
    video_base.settle(app, 15)
    recorder.add(
        "Der Prüfbericht gehört zum Modell",
        (
            "Hinweise bleiben direkt neben Konstruktion und Verlauf - nicht in "
            "einem getrennten Werkzeug."
        ),
        7.0,
        target=window.report,
    )
    recorder.add(
        "Was dieses Beispiel gezeigt hat",
        (
            "Leeres Projekt → Skizze → Parameter → Katalogbausteine → Variante "
            "→ Rückgängig → Drucklage."
        ),
        9.0,
        title_card=True,
    )
    recorder.add(
        "Solidon3D selbst ausprobieren",
        "Vollständige Demo und weitere Beispiele: solidon3d.de",
        8.0,
        title_card=True,
    )
    recorder.ensure_minimum(
        "Eine Skizze, ein nachvollziehbarer Verlauf",
        "Die Maße lassen sich später ändern, ohne die Halterung neu zu zeichnen.",
    )
    _finish_video(session, window)
    return recorder


def story_housing(app: QApplication, folder: Path) -> Recorder:
    """Ein alltagstaugliches Elektronikgehäuse mit Katalogteilen bauen."""
    session, window, recorder = _begin_video(app, "Elektronikgehäuse", folder)
    recorder.add(
        "Ein komplettes Elektronikgehäuse in Solidon3D",
        (
            "Grundkörper, Verrundung, Wandstärke, Einpressbuchsen, "
            "Kabeldurchführung, Rippen, Füße und Deckel."
        ),
        9.0,
        title_card=True,
    )
    recorder.add(
        "Ausgangspunkt: ein leeres Projekt",
        "Wir bauen das Gehäuse vollständig aus Operationen und Katalogbausteinen auf.",
        6.0,
        target=window.viewport,
    )
    for name, value, title in HOUSING_SIZES:
        limits = {
            "breite": (80.0, 180.0),
            "tiefe": (60.0, 130.0),
            "hoehe": (30.0, 80.0),
            "wand": (1.6, 4.0),
        }[name]
        _add_parameter(
            recorder,
            session,
            name,
            title,
            value,
            minimum=limits[0],
            maximum=limits[1],
        )

    _first_title, first_drafts = housing_steps()[0]
    _show_operation(
        recorder,
        session,
        first_drafts[0].op,
        first_drafts[0].params,
        "B-Rep-Quader als Ausgangskörper",
        "Breite, Tiefe und Höhe verweisen auf die drei Projektmaße.",
        focus="width",
        result_title="Die Außenmaße stehen",
        result_detail="Als B-Rep bleiben Flächen und Kanten für die nächsten Schritte bearbeitbar.",
    )

    steps = housing_steps()
    _fillet_title, fillet_drafts = steps[1]
    _show_operation(
        recorder,
        session,
        fillet_drafts[0].op,
        fillet_drafts[0].params,
        "Kanten mit 4 mm Radius verrunden",
        "Das verbessert Haptik und Optik, bevor die Wand erzeugt wird.",
        object_id="obj_1",
        focus="radius",
        result_title="Der Rohkörper wirkt bereits wie ein Produkt",
        result_detail="Die Verrundung bleibt als eigener Verlaufsschritt editierbar.",
    )

    _hollow_title, hollow_drafts = steps[2]
    _show_operation(
        recorder,
        session,
        hollow_drafts[0].op,
        hollow_drafts[0].params,
        "Gehäuse mit offener Oberseite aushöhlen",
        "Die Wandstärke kommt aus @wand; der Innenraum folgt automatisch den Außenmaßen.",
        object_id="obj_1",
        focus="wall",
        result_title="Aus dem Block wird ein Gehäuse",
        result_detail="Innenraum, Boden und Wände sind ein zusammenhängender Körper.",
        result_seconds=8.0,
    )
    recorder.orbit(
        "Innenraum, Boden und Wandstärke räumlich prüfen",
        "Die leichte Drehung macht die offene Oberseite und die gleichmäßige Schale sichtbar.",
        seconds=2.8,
        degrees=-44.0,
        zoom=1.12,
    )

    _show_catalog(
        recorder,
        "heatset_m4",
        "Katalog: Heat-Set-Einpressbuchse",
        "M3 aus der Normteiltabelle - mit Einführfase und zusätzlicher Tiefe.",
        search="Heat-Set",
    )
    heat_title, heat_drafts = steps[3]
    _select(window, "obj_1")
    window.run_operation(
        REGISTRY.get("insert_heatset_m4"), given=_localized_values(heat_drafts[0].params)
    )
    video_base.settle(app, 20)
    dialog = window._op_dialog
    if dialog is None:
        raise SystemExit("Einpressbuchsendialog ging nicht auf.")
    recorder.add(
        "Die Position kommt vom Gehäuserand",
        "Jede Buchse bleibt zehn Millimeter von Breite und Tiefe entfernt.",
        7.0,
        dialog=dialog,
        target=dialog._editors.get("x"),
    )
    recorder.click(
        "Vier Buchsen einsetzen",
        "Die vier symmetrischen Positionen werden gemeinsam als eine Transaktion gesetzt.",
        dialog=dialog,
        target=_button(dialog),
    )
    dialog.reject()
    _apply(session, heat_title, heat_drafts)
    _fit(window, app)
    recorder.add(
        "Vier M3-Buchsen für den Deckel",
        "Wenn sich die Gehäusebreite ändert, wandern alle vier Positionen mit.",
        8.0,
        target=window.viewport,
    )
    recorder.orbit(
        "Alle vier Einpressbuchsen aus der Nähe",
        "Beim Drehen bleiben Einführfasen, Innenraum und die symmetrischen Abstände lesbar.",
        seconds=2.6,
        degrees=46.0,
        zoom=1.14,
    )

    _show_catalog(
        recorder,
        "cable_gland",
        "Katalog: Kabeldurchführung mit Zugentlastung",
        "Eine häufige Gehäuseaufgabe als anpassbarer Baustein statt Handarbeit.",
        search="Kabeldurchführung",
    )
    _gland_title, gland_drafts = steps[4]
    _show_operation(
        recorder,
        session,
        gland_drafts[0].op,
        gland_drafts[0].params,
        "Sechs-Millimeter-Kabel einführen",
        "Durchlass und Zugentlastung entstehen in einem Katalogschritt.",
        object_id="obj_1",
        focus="diameter",
        result_title="Kabelweg und Entlastung sind integriert",
        result_detail="Der Baustein ist keine lose Dekoration, sondern Teil des Gehäusekörpers.",
    )

    _show_catalog(
        recorder,
        "rib",
        "Katalog: zwei Versteifungsrippen",
        "Die Rippen folgen der Tiefe und sitzen jeweils bei einem Viertel der Breite.",
        search="Versteifungsrippe",
    )
    rib_title, rib_drafts = steps[5]
    _show_bundled_operation(
        recorder,
        session,
        rib_title,
        rib_drafts,
        "Erste Rippe ausrichten",
        "Länge, Höhe und Wandstärke sind im echten Katalogdialog sichtbar.",
        focus="height",
        result_title="Steifigkeit nur dort, wo sie gebraucht wird",
        result_detail=(
            "Zwei verrundete Rippen verstärken den Boden, ohne das ganze Gehäuse dicker zu machen."
        ),
        result_seconds=8.0,
    )
    recorder.orbit(
        "Kabelweg und Rippen von der Seite",
        "Die Kamerafahrt zeigt, wie Zugentlastung und Versteifungen in den Körper übergehen.",
        seconds=2.8,
        degrees=-50.0,
        zoom=1.08,
    )

    _show_catalog(
        recorder,
        "foot",
        "Katalog: vier Standfüße",
        "Durchmesser und Höhe sind anpassbar; die Positionen folgen wieder den Außenmaßen.",
        search="Standfuß",
    )
    foot_title, foot_drafts = steps[6]
    _show_bundled_operation(
        recorder,
        session,
        foot_title,
        foot_drafts,
        "Ersten Standfuß einstellen",
        "Durchmesser, Höhe und die berechnete Position stehen im Katalogdialog.",
        focus="height",
        result_title="Das Gehäuse bekommt Abstand zur Unterlage",
        result_detail="Alle vier Füße gehören weiterhin zu derselben druckbaren Komponente.",
    )

    _lid_title, lid_drafts = steps[7]
    _show_operation(
        recorder,
        session,
        lid_drafts[0].op,
        lid_drafts[0].params,
        "Passenden Deckel aus dem Gehäuse ableiten",
        "Dicke, Kragen und Spiel bleiben später unabhängig einstellbar.",
        object_id="obj_1",
        focus="thickness",
        result_title="Gehäuse und Deckel sind zwei Körper",
        result_detail="Der Deckel passt aus demselben Verlauf heraus zum aktuellen Gehäuse.",
        result_seconds=8.0,
    )

    _show_catalog(
        recorder,
        "latch",
        "Katalog: Rastnasen für den Deckel",
        "Eine lösbare Verbindung ohne zusätzliche Schrauben.",
        search="Rastnase",
    )
    latch_title, latch_drafts = steps[8]
    _show_bundled_operation(
        recorder,
        session,
        latch_title,
        latch_drafts,
        "Erste Rastnase einstellen",
        "Breite, Höhe und Spiel bleiben als sichtbare Bausteinwerte erhalten.",
        focus="width",
        result_title="Zwei Rastnasen schließen den Deckel",
        result_detail="Beide Rastnasen werden gemeinsam in einer Transaktion eingesetzt.",
    )

    _colour_title, colour_drafts = steps[9]
    _show_operation(
        recorder,
        session,
        colour_drafts[0].op,
        colour_drafts[0].params,
        "Gehäusematerial und Farbe festlegen",
        "Slot 1 benennt das hellgraue PETG direkt im Projekt.",
        object_id="obj_1",
        focus="colour",
        result_title="Der Gehäusekörper ist eindeutig zugeordnet",
        result_detail="Materialslot und Farbe bleiben am Körper gespeichert.",
    )
    _show_operation(
        recorder,
        session,
        colour_drafts[1].op,
        colour_drafts[1].params,
        "Deckelmaterial und Farbe festlegen",
        "Slot 2 hebt den Deckel orange vom Gehäuse ab.",
        object_id="obj_2",
        focus="colour",
        result_title="Deckel und Gehäuse lassen sich sofort unterscheiden",
        result_detail="Die Zuordnung ist Teil des nachvollziehbaren Verlaufs.",
    )

    _move_title, move_drafts = steps[10]
    _show_operation(
        recorder,
        session,
        move_drafts[0].op,
        move_drafts[0].params,
        "Deckel neben das Gehäuse verschieben",
        "Der X-Versatz von 135 mm macht Innenraum und Deckel gleichzeitig sichtbar.",
        object_id="obj_2",
        focus="dx",
        result_title="Deckel daneben - Innenaufbau sichtbar",
        result_detail="Beide Körper bleiben getrennt und einzeln bearbeitbar.",
        result_seconds=8.0,
    )
    _show_operation(
        recorder,
        session,
        move_drafts[1].op,
        move_drafts[1].params,
        "Gehäuse auf das Druckbett setzen",
        "Die Operation verschiebt nur in Z und verändert keine Geometrie.",
        object_id="obj_1",
        result_title="Der Gehäuseboden liegt auf Z = 0",
        result_detail="Die Drucklage ist als eigener Verlaufsschritt sichtbar.",
        result_seconds=5.0,
    )
    _show_operation(
        recorder,
        session,
        move_drafts[2].op,
        move_drafts[2].params,
        "Auch den Deckel auf das Druckbett setzen",
        "Der zweite Körper folgt über denselben sichtbaren Menüweg.",
        object_id="obj_2",
        result_title="Beide Körper stehen auf dem Bett",
        result_detail="Gehäuse und Deckel bleiben dabei getrennt.",
        result_seconds=5.0,
    )

    _label_title, label_drafts = steps[11]
    _show_operation(
        recorder,
        session,
        label_drafts[0].op,
        label_drafts[0].params,
        "Schriftzug auf dem Deckel anlegen",
        "Text, Größe, Höhe und Materialslot stehen im echten Operationsdialog.",
        object_id="obj_2",
        focus="text",
        result_title="Der Schriftzug ist echte Geometrie",
        result_detail="Er bleibt ein eigener, editierbarer Schritt auf dem Deckel.",
    )
    recorder.add(
        "Deckel daneben - Innenaufbau sichtbar",
        "Materialfarben und Schriftzug machen Boden und Deckel eindeutig unterscheidbar.",
        6.0,
        target=window.viewport,
    )
    recorder.orbit(
        "Gehäuse und Deckel als vollständiges System",
        "Die Drehung zeigt Innenaufbau, Kragen, Rastnasen und beide getrennten Körper.",
        seconds=3.2,
        degrees=58.0,
        zoom=1.05,
    )
    final_title, final_drafts = steps[12]
    arrange_action = _operation_action(window, final_drafts[0].op)
    if arrange_action is not None:
        _show_action_path(
            recorder,
            arrange_action,
            "Nach der Mehrfachauswahl ordnet dieser Menüpunkt beide Körper auf dem Bett an.",
        )
    _apply(session, final_title, final_drafts)
    _fit(window, app)
    recorder.add(
        "Beide Teile automatisch auf dem Druckbett",
        "Solidon ordnet Gehäuse und Deckel mit Abstand an, ohne sie zu verschmelzen.",
        8.0,
        target=window.viewport,
    )

    _edit_parameter(recorder, session, "breite", 140.0, "Gehäusebreite")
    recorder.add(
        "120 wird 140 mm - der Aufbau bleibt konsistent",
        "Wände, Deckel, Buchsen, Rippen, Füße und Rastnasen folgen der neuen Breite.",
        9.0,
        target=window.viewport,
    )
    window.right.setCurrentWidget(window.report)
    video_base.settle(app, 15)
    recorder.add(
        "Zum Schluss: Druckbarkeit prüfen",
        "Der Bericht nennt konkrete Hinweise und bleibt mit dem Projekt gespeichert.",
        7.0,
        target=window.report,
    )
    recorder.add(
        "Ein Gehäuse, das sich weiterentwickeln lässt",
        "Nicht nur ein fertiges Netz: Maße und jeder Katalogbaustein bleiben editierbar.",
        9.0,
        title_card=True,
    )
    recorder.add(
        "Mehr über Solidon3D",
        "Vollständige Demo, Download und weitere Anwendungsfälle: solidon3d.de",
        8.0,
        title_card=True,
    )
    recorder.ensure_minimum(
        "Vom leeren Projekt zum produktreifen Gehäuse",
        "Ein nachvollziehbarer Verlauf statt eines starren STL-Endzustands.",
    )
    _finish_video(session, window)
    return recorder


def story_skadis_holder(app: QApplication, folder: Path) -> Recorder:
    """Einen anpassbaren SKÅDIS-Halter für Besenstiele bauen."""
    session, window, recorder = _begin_video(app, "SKÅDIS-Besenhalter", folder)
    recorder.add(
        "Praktischer SKÅDIS-Besenhalter für 35-mm-Stiele",
        "Vom leeren Projekt über die Grundplatte bis zu Haken und anpassbarem Clip.",
        9.0,
        title_card=True,
    )
    recorder.add(
        "Ein typisches Hobby-Problem",
        "Das Lochwandsystem ist vorgegeben, der Durchmesser des vorhandenen Stiels aber nicht.",
        7.0,
        target=window.viewport,
    )
    _add_parameter(recorder, session, "rohr", "Rohrdurchmesser", 35.0, minimum=20.0, maximum=45.0)
    _add_parameter(recorder, session, "platte", "Plattenstärke", 6.0, minimum=4.0, maximum=10.0)

    sketch_action = _operation_action(window, "sketch_extrude")
    if sketch_action is not None:
        _show_action_path(
            recorder,
            sketch_action,
            "Der Menüpunkt öffnet den Skizzenmodus für die Grundplatte.",
        )
    window.start_sketch("sketch_extrude")
    video_base.settle(app, 30)
    panel = window._sketch_panel
    if panel is None:
        raise SystemExit("Skizzenmodus ging nicht auf.")
    _draw_rectangle(recorder, panel, 100.0, 70.0)
    recorder.add(
        "Die Grundplatte misst 100 x 70 mm",
        "Sie bietet Platz für zwei SKÅDIS-Haken und den großen Halteclip.",
        5.0,
        target=window.viewport,
    )
    recorder.add(
        "Geschlossener Umriss, klare Maße",
        "Die Skizze bleibt später im ersten Verlaufsschritt erreichbar.",
        6.0,
        target=panel,
    )
    window.finish_sketch(
        keep=True,
        given=_localized_values({"height": "=@platte", "name": "SKÅDIS-Besenhalter"}),
    )
    video_base.settle(app, 25)
    dialog = window._op_dialog
    if dialog is None:
        raise SystemExit("Extrusionsdialog ging nicht auf.")
    recorder.add(
        "Plattenstärke aus dem Projektmaß",
        "Die Extrusion verwendet @platte statt einer verstreuten Zahl.",
        7.0,
        dialog=dialog,
        target=dialog._editors.get("height"),
    )
    action = _button(dialog)
    recorder.click(
        "Grundplatte aufziehen",
        "Der erste Körper bleibt für alle folgenden Bausteine ausgewählt.",
        dialog=dialog,
        target=action,
    )
    dialog.accept()
    _verify(session, "Grundplatte aufziehen")
    _fit(window, app)
    recorder.add(
        "Die stabile Basis ist fertig",
        "Die Skizze liefert die Grundplatte; für die Montage richten wir sie jetzt senkrecht aus.",
        7.0,
        target=window.viewport,
    )

    _show_operation(
        recorder,
        session,
        "rotate_object",
        {"axis": "x", "angle": 90.0, "about": "centre"},
        "Grundplatte in Montagelage drehen",
        "So lassen sich Vorder- und Rückseite im nächsten Schritt eindeutig belegen.",
        object_id="obj_1",
        focus="angle",
        result_title="Die Platte steht wie später an der Lochwand",
        result_detail="Rückseitige Haken und vorderer Besenclip landen nun auf getrennten Seiten.",
    )

    _select(window, "obj_1")
    _show_catalog(
        recorder,
        "pegboard_hook",
        "Katalog: Lochwand-Einhänger",
        "System SKÅDIS, zwei Haken, Verriegelung und optionales Spiel.",
        search="Lochwand",
    )
    _show_operation(
        recorder,
        session,
        "insert_pegboard_hook",
        {
            "system": "skadis",
            "count": 2,
            "steps": 1,
            "latch": True,
            "plate": 0.0,
            "at_feature": "face_6",
            "x": 0.0,
            "y": 0.0,
            "z": 18.0,
        },
        "Zwei passende SKÅDIS-Haken auf die Rückseite setzen",
        ("Die Rückfläche gibt Position und Richtung vor; die Systemmaße kommen aus dem Katalog."),
        object_id="obj_1",
        focus="count",
        result_title="Die Haken sitzen ausschließlich hinten",
        result_detail="Vorn bleibt die Fläche für die eigentliche Besenaufnahme frei.",
        result_seconds=8.0,
    )

    _show_catalog(
        recorder,
        "cable_clip",
        "Katalog: Kabelclip als großer Rohrhalter",
        "Der gleiche parametrisierte Baustein kann auch einen 35-mm-Besenstiel greifen.",
        search="Kabelclip",
    )
    _show_operation(
        recorder,
        session,
        "insert_cable_clip",
        {
            "diameter": "=@rohr",
            "width": 18.0,
            "wall": 3.0,
            "grip": 4.0,
            "x": 0.0,
            "y": 0.0,
            "z": -12.0,
            "axis": "y",
        },
        "Clip auf den echten Stieldurchmesser einstellen",
        "@rohr steuert die Öffnung; Wand, Breite und Griff bleiben unabhängig.",
        object_id="obj_1",
        focus="diameter",
        result_title="Der Clip sitzt vorn, die Haken sitzen hinten",
        result_detail=(
            "Damit kann der Halter wirklich an der Lochwand hängen und zugleich den Stiel greifen."
        ),
        result_seconds=9.0,
    )
    recorder.orbit(
        "Vorder- und Rückseite im direkten Vergleich",
        "Die Kamerafahrt zeigt den 35-mm-Clip vorn und beide SKÅDIS-Haken auf der Gegenseite.",
        seconds=3.0,
        degrees=62.0,
        zoom=1.08,
    )

    _edit_parameter(recorder, session, "rohr", 40.0, "Rohrdurchmesser")
    recorder.add(
        "Passt auch für einen 40-mm-Stiel",
        "Nur der Clip wächst; SKÅDIS-Haken und Grundplatte bleiben unverändert.",
        8.0,
        target=window.viewport,
    )
    session.undo()
    _verify(session, "Rohrdurchmesser zurücknehmen")
    _fit(window, app)
    recorder.add(
        "Zurück zur 35-mm-Ausführung",
        "Die Variante ist rücknehmbar, ohne einen Katalogbaustein neu einzusetzen.",
        7.0,
        target=window.viewport,
    )

    _show_operation(
        recorder,
        session,
        "rotate_object",
        {"axis": "y", "angle": 90.0, "about": "centre"},
        "Für belastbare Rastzungen auf die Seite drehen",
        (
            "Die Hakenfedern liegen dadurch in der Schichtebene statt zwischen "
            "den Schichten zu reißen."
        ),
        object_id="obj_1",
        focus="angle",
        result_title="Die konstruktive Seite wird zur Druckunterseite",
        result_detail="Diese Lage folgt der vorgesehenen Belastungsrichtung des SKÅDIS-Bausteins.",
    )
    _show_operation(
        recorder,
        session,
        "place_on_bed",
        {},
        "Drucklage festlegen",
        (
            "Der tiefste Punkt wird auf Z = 0 gesetzt; die Rastzungen bleiben "
            "schichtgerecht ausgerichtet."
        ),
        object_id="obj_1",
        result_title="Ein funktionaler Einteiler in sinnvoller Drucklage",
        result_detail="Für den hohen, schmalen Aufbau empfiehlt sich im Slicer ein breiter Rand.",
        result_seconds=8.0,
    )
    window.right.setCurrentWidget(window.report)
    video_base.settle(app, 15)
    recorder.add(
        "Druckhinweise vor dem Export lesen",
        "Der Bericht bleibt am Modell und nennt Handlungen statt bloßer Fehlercodes.",
        7.0,
        target=window.report,
    )
    recorder.add(
        "Warum dieses Modell für Hobby-Anwender zählt",
        "Ein reales Maß ändert sich häufig - das Lochwandsystem soll dabei exakt bleiben.",
        9.0,
        title_card=True,
    )
    recorder.add(
        "Weitere praktische Konstruktionen mit Solidon3D",
        "Vollständige Demo und Download: solidon3d.de",
        8.0,
        title_card=True,
    )
    recorder.ensure_minimum(
        "Standardteil und eigenes Maß in einem Modell",
        (
            "Der Katalog hält das Systemmaß, der Projektparameter passt den Halter "
            "an deinen Gegenstand an."
        ),
    )
    _finish_video(session, window)
    return recorder


STORIES: Final[dict[str, tuple[str, str, Callable[[QApplication, Path], Recorder]]]] = {
    "montagehalter": (
        "solidon3d-montagehalter-aus-skizze-de-1080p.mp4",
        "Montagehalter aus Skizze",
        story_mounting_bracket,
    ),
    "elektronikgehaeuse": (
        "solidon3d-elektronikgehaeuse-de-1080p.mp4",
        "Elektronikgehäuse",
        story_housing,
    ),
    "skadis-besenhalter": (
        "solidon3d-skadis-besenhalter-de-1080p.mp4",
        "SKÅDIS-Besenhalter",
        story_skadis_holder,
    ),
}


def _write_longform_music(target: Path, seconds: float, chapter: str) -> Path:
    """Für jedes Tutorial ein eigenes, vollständig erzeugtes Musikstück schreiben."""
    import wave

    import numpy as np

    styles: dict[
        str,
        tuple[float, tuple[tuple[int, ...], ...], tuple[int, ...], float, int],
    ] = {
        "Montagehalter aus Skizze": (
            92.0,
            (
                (48, 55, 60, 64),
                (45, 52, 57, 60),
                (41, 48, 53, 57),
                (43, 50, 55, 62),
                (48, 55, 60, 67),
                (40, 47, 52, 55),
                (41, 48, 53, 60),
                (43, 50, 59, 62),
            ),
            (0, 2, 1, 3, 2, 1, 3, 1),
            0.17,
            173,
        ),
        "Elektronikgehäuse": (
            104.0,
            (
                (38, 45, 50, 53),
                (46, 53, 58, 62),
                (41, 48, 53, 57),
                (48, 55, 60, 64),
                (38, 45, 50, 57),
                (45, 52, 57, 60),
                (43, 50, 55, 58),
                (45, 52, 57, 64),
            ),
            (0, 1, 2, 3, 1, 3, 2, 1),
            0.28,
            311,
        ),
        "SKÅDIS-Besenhalter": (
            98.0,
            (
                (43, 50, 55, 59),
                (50, 57, 62, 66),
                (40, 47, 52, 55),
                (48, 55, 60, 64),
                (43, 50, 55, 62),
                (47, 54, 59, 62),
                (45, 52, 57, 60),
                (50, 57, 62, 69),
            ),
            (0, 2, 3, 1, 2, 0, 3, 2),
            0.22,
            947,
        ),
    }
    bpm, chords, arpeggio, colour, seed = styles[chapter]
    rate = 48_000
    count = max(1, round(seconds * rate))
    stereo = np.zeros((count, 2), dtype=np.float64)
    rng = np.random.default_rng(seed)

    def frequency(note: int) -> float:
        return 440.0 * 2.0 ** ((note - 69) / 12.0)

    def add_tone(
        start: float,
        duration: float,
        note: int,
        amplitude: float,
        pan: float,
        *,
        attack: float,
        release: float,
    ) -> None:
        begin = max(0, round(start * rate))
        end = min(count, round((start + duration) * rate))
        if end <= begin:
            return
        local = np.arange(end - begin, dtype=np.float64) / rate
        envelope = np.minimum(1.0, local / max(attack, 1.0 / rate))
        envelope *= np.minimum(1.0, (duration - local) / max(release, 1.0 / rate))
        envelope = np.clip(envelope, 0.0, 1.0) ** 1.35
        hz = frequency(note)
        phase = float(rng.uniform(0.0, 2.0 * math.pi))
        tone = np.sin(2.0 * math.pi * hz * local + phase)
        tone += colour * np.sin(4.0 * math.pi * hz * local + phase * 0.7)
        tone += colour * 0.18 * np.sin(6.0 * math.pi * hz * local + phase * 1.3)
        left = math.sqrt((1.0 - pan) / 2.0)
        right = math.sqrt((1.0 + pan) / 2.0)
        stereo[begin:end, 0] += amplitude * left * envelope * tone
        stereo[begin:end, 1] += amplitude * right * envelope * tone

    beat = 60.0 / bpm
    chord_seconds = 8.0 * beat
    chord_count = math.ceil(seconds / chord_seconds)
    for index in range(chord_count):
        chord = chords[index % len(chords)]
        start = index * chord_seconds
        # Das Pad wechselt alle zwei Takte und erhält durch wechselnde
        # Umkehrungen einen eigenen Verlauf statt einer vierfachen Schleife.
        inversion = (index // len(chords)) % len(chord)
        voiced = tuple(
            note + (12 if position < inversion else 0) for position, note in enumerate(chord)
        )
        for position, note in enumerate(voiced):
            add_tone(
                start - 0.12,
                chord_seconds + 0.35,
                note,
                0.020 / (1.0 + position * 0.12),
                -0.55 + 1.1 * position / max(1, len(voiced) - 1),
                attack=0.55,
                release=0.85,
            )
        for offset in (0.0, 4.0 * beat):
            add_tone(
                start + offset,
                2.25 * beat,
                chord[0] - 12,
                0.050,
                -0.08,
                attack=0.025,
                release=0.65,
            )

    step = beat / 2.0
    position = 0
    while position * step < seconds:
        start = position * step
        chord_index = int(start / chord_seconds)
        chord = chords[chord_index % len(chords)]
        pattern_index = arpeggio[position % len(arpeggio)]
        note = chord[pattern_index]
        if position % 16 in {6, 14}:
            note += 12
        # Jeder vierte Zweitakter atmet kurz; die drei Stücke unterscheiden
        # sich dadurch auch im Arrangement, nicht nur in den Tonhöhen.
        if chord_index % 4 != 3 or position % 16 >= 4:
            add_tone(
                start,
                step * 0.72,
                note,
                0.024,
                -0.42 if position % 2 == 0 else 0.42,
                attack=0.008,
                release=step * 0.28,
            )
        position += 1

    # Leiser, je Tutorial anders gefärbter Rhythmus. Alle Geräusche entstehen
    # aus berechnetem Rauschen und Sinusschwingungen, nicht aus Samples.
    for beat_index, start in enumerate(np.arange(0.0, seconds, beat)):
        begin = round(start * rate)
        end = min(count, begin + round(0.24 * rate))
        if end > begin and beat_index % 4 in {0, 2}:
            local = np.arange(end - begin, dtype=np.float64) / rate
            kick = np.sin(2.0 * math.pi * (72.0 * local - 22.0 * local**2))
            kick *= np.exp(-local * 15.0) * (0.060 if beat_index % 4 == 0 else 0.040)
            stereo[begin:end, 0] += kick
            stereo[begin:end, 1] += kick
        if beat_index % 2 == 1:
            end = min(count, begin + round(0.055 * rate))
            if end > begin:
                local = np.arange(end - begin, dtype=np.float64) / rate
                noise = rng.normal(0.0, 1.0, end - begin)
                tick = noise * np.exp(-local * 62.0) * (0.010 + colour * 0.025)
                stereo[begin:end, 0] += tick * 0.75
                stereo[begin:end, 1] += tick

    fade = min(count // 2, round(rate * 1.2))
    master = np.ones(count, dtype=np.float64)
    master[:fade] = np.sin(np.linspace(0.0, math.pi / 2.0, fade)) ** 2
    master[-fade:] = np.sin(np.linspace(math.pi / 2.0, 0.0, fade)) ** 2
    stereo *= master[:, None]
    rms = float(np.sqrt(np.mean(stereo * stereo)))
    peak = float(np.max(np.abs(stereo)))
    if rms > 0.0 and peak > 0.0:
        stereo *= min(0.095 / rms, 0.82 / peak)
    pcm = np.round(np.clip(stereo, -1.0, 1.0) * 32767.0).astype("<i2")
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(pcm.tobytes())
    print(f"  Musik → {target.name}  {seconds:.1f} s · eigenes Arrangement: {chapter}")
    return target


def _encode(recorder: Recorder, target: Path) -> None:
    """Die Zustandsbilder ohne riesigen Rohbildordner als H.264/AAC kodieren."""
    if not recorder.slides:
        raise SystemExit(f"{target.name}: keine Bilder aufgenommen.")
    target.parent.mkdir(parents=True, exist_ok=True)
    timeline = recorder.folder / "timeline.ffconcat"
    lines = ["ffconcat version 1.0"]
    for slide in recorder.slides:
        escaped = slide.path.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
        lines.append(f"duration {slide.seconds:.3f}")
    escaped = recorder.slides[-1].path.resolve().as_posix().replace("'", "'\\''")
    lines.append(f"file '{escaped}'")
    timeline.write_text("\n".join(lines) + "\n", encoding="utf-8")

    music = recorder.folder / "music.wav"
    _write_longform_music(music, recorder.seconds + 0.4, recorder.chapter)
    video_base.run_ffmpeg(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(timeline),
            "-i",
            str(music),
            "-vf",
            "fps=30,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t",
            f"{recorder.seconds:.3f}",
            "-movflags",
            "+faststart",
            str(target),
        ]
    )
    _verify_video(target)
    target.with_suffix(".timeline.json").write_text(
        json.dumps(recorder.events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _verify_video(path: Path) -> None:
    """Dauer, Bildgröße, Bildrate und Tonspur des fertigen Films prüfen."""
    binary = shutil.which("ffprobe")
    if binary is None:
        raise SystemExit("ffprobe fehlt — das fertige Video kann nicht geprüft werden.")
    finished = subprocess.run(
        [
            binary,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
            "-of",
            "default=noprint_wrappers=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if finished.returncode != 0:
        raise SystemExit(f"ffprobe brach ab: {finished.stderr.strip()}")
    values = finished.stdout
    duration_line = next((line for line in values.splitlines() if line.startswith("duration=")), "")
    duration = float(duration_line.partition("=")[2]) if duration_line else 0.0
    required = (
        duration >= 180.0,
        "width=1920" in values,
        "height=1080" in values,
        "r_frame_rate=30/1" in values,
        "codec_type=audio" in values,
        "codec_name=h264" in values,
    )
    if not all(required):
        raise SystemExit(f"Video erfüllt die Auslieferungswerte nicht:\n{values}")


def main() -> int:
    """Gewählte oder alle drei Hobby-Tutorials erzeugen."""
    global _captions
    os.environ.pop("QT_QPA_PLATFORM", None)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=("de", "en"), default="de")
    parser.add_argument("stories", nargs="*", metavar="VIDEO")
    args = parser.parse_args()
    wanted = args.stories or list(STORIES)
    for name in wanted:
        if name not in STORIES:
            parser.error(f"Unbekannt: {name}. Möglich: {', '.join(STORIES)}")
    language = args.language
    if language == "en":
        _captions = json.loads(
            Path(__file__).with_name("longform_video_en.json").read_text("utf-8")
        )
    else:
        _captions = {}

    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    video_base.require_screen(app)
    install_catalog(language, read_catalog(language))
    set_language(language)
    install_qt_translations(app, language)
    apply_theme(app, "dark")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="solidon-longform-") as temporary:
        root = Path(temporary)
        for name in wanted:
            filename, label, story = STORIES[name]
            print(f"\n=== {_text(label)} ({language}) ===", flush=True)
            recorder = story(app, root / name)
            target = OUTPUT_DIR / filename.replace("-de-", f"-{language}-")
            print(f"Kodiere {recorder.seconds:.1f} Sekunden nach {target}", flush=True)
            _encode(recorder, target)
            print(f"Geprüft: {target}", flush=True)

    print(f"\nFertig: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
