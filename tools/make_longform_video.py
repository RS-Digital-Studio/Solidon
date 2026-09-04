"""Lange YouTube-Tutorials aus der sichtbaren Solidon-Anwendung erzeugen.

    .venv\\Scripts\\python.exe tools/make_longform_video.py
    .venv\\Scripts\\python.exe tools/make_longform_video.py montagehalter

Die Filme beginnen in einem leeren Projekt und bauen ein wirklich
ausgewertetes, druckbares Modell auf. Sie verwenden dieselben Dialoge,
Operationen und Katalogeinträge wie die Anwendung. Gesprochen wird nicht:
ruhige deutsche Einblendungen und ein vollständig selbst erzeugtes Musikbett
tragen den Ablauf.

Anders als :mod:`tools.make_video` hält dieses Werkzeug nicht jede
Bildschirmsekunde als PNG fest. Ein Tutorial von mehr als drei Minuten würde
bei dreißig Vollbildern pro Sekunde mehrere Gigabyte Zwischenstand erzeugen.
Hier wird jeder fachliche Zustand einmal aus dem sichtbaren Fenster gegriffen
und über seine Lesedauer gehalten. Die Geometrie dazwischen ist trotzdem echt;
jeder Schritt wird abgewartet und auf vollständige Auswertung geprüft.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
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
    QWidget,
)

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.registry import REGISTRY  # noqa: E402
from app.core.scene import OperationDraft  # noqa: E402
from app.core.sketch import shapes  # noqa: E402
from app.core.sketch.serialize import sketch_to_text  # noqa: E402
from app.core.types import Parameter  # noqa: E402
from app.i18n import install_catalog, set_language  # noqa: E402
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
    ) -> None:
        """Fenster, höchstens einen Dialog, Text und Systemzeiger aufnehmen."""
        if seconds <= 0.0:
            raise ValueError("Eine Folie braucht eine positive Dauer.")
        if dialog is not None:
            _place_dialog(self.window, dialog)
            dialog.raise_()
            dialog.activateWindow()
        else:
            self.window.raise_()
            self.window.activateWindow()
        video_base.settle(self.app, 12)

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
        self._paint_caption(frame, title, detail, title_card=title_card)
        point = self._point_for(target)
        if point is not None:
            video_base._paint_pointer(frame, (float(point.x()), float(point.y()), click))

        path = self.folder / f"{len(self.slides):03d}.png"
        if not frame.save(str(path), "PNG"):
            raise SystemExit(f"Bild ließ sich nicht schreiben: {path}")
        self.slides.append(Slide(path, seconds))

    def click(
        self,
        title: str,
        detail: str,
        *,
        dialog: QDialog,
        target: QWidget,
    ) -> None:
        """Einen kurzen, sichtbaren Klickring vor der Handlung ergänzen."""
        self.add(title, detail, 0.35, dialog=dialog, target=target, click=True)

    def ensure_minimum(self, title: str, detail: str) -> None:
        """Die Dreiminuten-Grenze mit einer sinnvollen Schlusskarte sichern."""
        rest = MINIMUM_SECONDS - self.seconds
        if rest > 0.0:
            self.add(title, detail, rest + 1.0, title_card=True)

    def _paint_dialog(self, frame: QImage, dialog: QDialog) -> None:
        """Den einen offenen Dialog über den OpenGL-Fenstergriff legen."""
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
    ) -> None:
        """Eine ruhige, telefonlesbare Einblendung über die Anwendung setzen."""
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
            box = QRectF(34, 24, 1230, 132)
            painter.setBrush(QColor(18, 22, 29, 228))
            painter.drawRoundedRect(box, 20, 20)
            painter.setBrush(QColor("#e08b4e"))
            painter.drawRoundedRect(QRectF(34, 24, 12, 132), 6, 6)
            painter.setPen(QColor("#aeb8c8"))
            painter.setFont(QFont("Segoe UI", 15, QFont.Weight.DemiBold))
            painter.drawText(QRectF(70, 37, 1170, 24), self.chapter.upper())
            painter.setPen(QColor("#f7f9fb"))
            painter.setFont(QFont("Segoe UI", 27, QFont.Weight.DemiBold))
            painter.drawText(QRectF(70, 61, 1170, 42), title)
            painter.setPen(QColor("#d4d9e1"))
            painter.setFont(QFont("Segoe UI", 17))
            painter.drawText(
                QRectF(70, 104, 1170, 40),
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
    session.apply(title, list(drafts), raise_on_error=True, bundle=bundle)
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
    dialog = ParameterDialog(session.project.document.parameters, recorder.window)
    dialog.name_field.setText(name)
    dialog.value_field.setValue(value)
    dialog.minimum_field.setText(f"{minimum:g}")
    dialog.maximum_field.setText(f"{maximum:g}")
    action = _button(dialog)
    recorder.add(
        f"Projektmaß: {title}",
        f"{value:g} mm - mit sinnvollen Grenzen für spätere Varianten.",
        5.8,
        dialog=dialog,
        target=dialog.value_field,
    )
    recorder.click(
        f"{title} anlegen",
        "Der Name kann in allen folgenden Operationen mit @ verwendet werden.",
        dialog=dialog,
        target=action,
    )
    dialog.close()
    dialog.deleteLater()
    parameter = Parameter(
        name=name,
        value=value,
        unit="mm",
        title=title,
        minimum=minimum,
        maximum=maximum,
    )
    if not session.add_parameter(parameter):
        raise SystemExit(f"Parameter ließ sich nicht anlegen: {name}")
    _verify(session, f"Parameter {name}")
    recorder.add(
        f"{title} steht im Projekt",
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
    """Einen vorhandenen Parameter sichtbar ändern und neu auswerten."""
    existing = session.project.document.parameters[name]
    dialog = ParameterDialog(
        session.project.document.parameters,
        recorder.window,
        existing=existing,
    )
    dialog.value_field.setValue(value)
    action = _button(dialog)
    recorder.add(
        f"Variante testen: {title}",
        f"Nur dieses Projektmaß wird auf {value:g} mm geändert.",
        6.5,
        dialog=dialog,
        target=dialog.value_field,
    )
    recorder.click(
        "Neu aufbauen",
        "Alle abhängigen Schritte bleiben erhalten und werden erneut gerechnet.",
        dialog=dialog,
        target=action,
    )
    dialog.close()
    dialog.deleteLater()
    if not session.change_parameter(name, value):
        raise SystemExit(f"Parameter ließ sich nicht ändern: {name}")
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
    catalog = recorder.window._make_catalog()
    catalog.resize(1120, 760)
    if search:
        catalog.search.setText(search)
    catalog.show_file_result("", part_name=part_name)
    catalog.set_can_insert(True)
    catalog.set_feature_chosen(False)
    video_base.settle(recorder.app, 30)
    item = catalog._item_named(part_name)
    point: QPoint | None = None
    if item is not None:
        rectangle = catalog.list.visualItemRect(item)
        point = catalog.list.mapToGlobal(rectangle.center())
    recorder.add(title, detail, 7.0, dialog=catalog, target=point)
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
    spec = REGISTRY.get(op_name)
    if not spec.params.spec():
        # Eine Operation ohne Werte hat absichtlich keinen Dialog. Vorher und
        # nachher zeigen ist hier die ehrliche Bedienfolge; einen erfundenen
        # Bestätigungsknopf darf der Film nicht ergänzen.
        recorder.add(title, detail, 6.0, target=recorder.window.viewport)
        recorder.window.run_operation(spec, given=dict(values))
        _verify(session, title)
        _fit(recorder.window, recorder.app)
        recorder.add(
            result_title,
            result_detail,
            result_seconds,
            target=recorder.window.viewport,
        )
        return
    recorder.window.run_operation(spec, given=dict(values))
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


def _begin_video(
    app: QApplication,
    chapter: str,
    folder: Path,
) -> tuple[Session, MainWindow, Recorder]:
    """Ein leeres sichtbares Projekt für genau einen Film öffnen."""
    session = Session()
    window = MainWindow(session, UiSettings())
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

    sketch = sketch_to_text(shapes.rectangle(70.0, 45.0))
    window.start_sketch("sketch_extrude", sketch)
    video_base.settle(app, 30)
    panel = window._sketch_panel
    if panel is None:
        raise SystemExit("Skizzenmodus ging nicht auf.")
    recorder.add(
        "Rechteck auf der XY-Ebene zeichnen",
        "70 x 45 mm - Raster, Fang und Maße bleiben direkt am Umriss sichtbar.",
        8.0,
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
        given={"height": "=@plattenstaerke", "name": "Montagehalter"},
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
        given={
            "size": "M4",
            "depth": "=@plattenstaerke",
            "countersink": True,
            "x": "=-@lochabstand/2",
            "y": 0.0,
            "z": 0.0,
        },
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
                    "z": 0.0,
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
                    "z": 0.0,
                },
            ),
        ],
    )
    _fit(window, app)
    recorder.add(
        "Beide Bohrungen in einem Verlaufsschritt",
        "Abstand und Senkung bleiben reproduzierbar; ein Rückgängig nimmt beide zusammen zurück.",
        7.5,
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

    _edit_parameter(recorder, session, "lochabstand", 60.0, "Lochabstand")
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
    _fit(window, app)
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

    _show_catalog(
        recorder,
        "heatset_m4",
        "Katalog: Heat-Set-Einpressbuchse",
        "M3 aus der Normteiltabelle - mit Einführfase und zusätzlicher Tiefe.",
        search="Heat-Set",
    )
    heat_title, heat_drafts = steps[3]
    _select(window, "obj_1")
    window.run_operation(REGISTRY.get("insert_heatset_m4"), given=heat_drafts[0].params)
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
    _apply(session, rib_title, rib_drafts)
    _fit(window, app)
    recorder.add(
        "Steifigkeit nur dort, wo sie gebraucht wird",
        "Zwei verrundete Rippen verstärken den Boden, ohne das ganze Gehäuse dicker zu machen.",
        8.0,
        target=window.viewport,
    )

    _show_catalog(
        recorder,
        "foot",
        "Katalog: vier Standfüße",
        "Durchmesser und Höhe sind anpassbar; die Positionen folgen wieder den Außenmaßen.",
        search="Standfuß",
    )
    foot_title, foot_drafts = steps[6]
    _apply(session, foot_title, foot_drafts)
    _fit(window, app)
    recorder.add(
        "Das Gehäuse bekommt Abstand zur Unterlage",
        "Alle vier Füße gehören weiterhin zu derselben druckbaren Komponente.",
        7.0,
        target=window.viewport,
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
    _apply(session, latch_title, latch_drafts)
    _fit(window, app)
    recorder.add(
        "Zwei Rastnasen schließen den Deckel",
        "Breite, Höhe und Spiel bleiben als Bausteinwerte im Verlauf erhalten.",
        7.0,
        target=window.viewport,
    )

    for title, drafts in steps[9:12]:
        _apply(session, title, drafts)
    _fit(window, app)
    recorder.add(
        "Deckel daneben - Innenaufbau sichtbar",
        "Materialfarben und Schriftzug machen Boden und Deckel eindeutig unterscheidbar.",
        9.0,
        target=window.viewport,
    )
    final_title, final_drafts = steps[12]
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

    sketch = sketch_to_text(shapes.rectangle(100.0, 70.0))
    window.start_sketch("sketch_extrude", sketch)
    video_base.settle(app, 30)
    panel = window._sketch_panel
    if panel is None:
        raise SystemExit("Skizzenmodus ging nicht auf.")
    recorder.add(
        "Grundplatte direkt auf dem Druckbett zeichnen",
        "100 x 70 mm bieten Platz für zwei SKÅDIS-Haken und den großen Halteclip.",
        8.0,
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
        given={"height": "=@platte", "name": "SKÅDIS-Besenhalter"},
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
        "Flach auf dem Bett konstruiert - eine stützfreundliche Ausgangslage.",
        7.0,
        target=window.viewport,
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
            "plate": 3.0,
            "x": 0.0,
            "y": 18.0,
            "z": "=@platte",
            "axis": "z",
        },
        "Zwei passende SKÅDIS-Haken einsetzen",
        (
            "Die Systemmaße kommen aus dem Katalog; nur Position und gewünschte "
            "Variante werden gesetzt."
        ),
        object_id="obj_1",
        focus="count",
        result_title="Die Befestigung ist Teil des Körpers",
        result_detail="Zwei Haken und Verriegelung entstehen als eine druckbare Komponente.",
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
            "y": -15.0,
            "z": "=@platte",
            "axis": "z",
        },
        "Clip auf den echten Stieldurchmesser einstellen",
        "@rohr steuert die Öffnung; Wand, Breite und Griff bleiben unabhängig.",
        object_id="obj_1",
        focus="diameter",
        result_title="Der Besenhalter ist geometrisch vollständig",
        result_detail="Grundplatte, SKÅDIS-Haken und 35-mm-Clip sind zu einem Körper verbunden.",
        result_seconds=9.0,
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
        "place_on_bed",
        {},
        "Drucklage festlegen",
        "Die flache Rückseite liegt auf dem Bett; Haken und Clip wachsen nach oben.",
        object_id="obj_1",
        result_title="Ein sinnvoll orientiertes Einteiler-Modell",
        result_detail="Die Konstruktion ist für den praktischen FDM-Druck vorbereitet.",
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
    video_base.write_feature_music(music, recorder.seconds + 0.4)
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
    os.environ.pop("QT_QPA_PLATFORM", None)
    wanted = sys.argv[1:] or list(STORIES)
    unknown = [name for name in wanted if name not in STORIES]
    if unknown:
        raise SystemExit(f"Unbekannt: {', '.join(unknown)}. Möglich: {', '.join(STORIES)}")

    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    video_base.require_screen(app)
    install_catalog("de", read_catalog("de"))
    set_language("de")
    install_qt_translations(app, "de")
    apply_theme(app, "dark")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="solidon-longform-") as temporary:
        root = Path(temporary)
        for name in wanted:
            filename, label, story = STORIES[name]
            print(f"\n=== {label} ===")
            recorder = story(app, root / name)
            target = OUTPUT_DIR / filename
            print(f"Kodiere {recorder.seconds:.1f} Sekunden nach {target}")
            _encode(recorder, target)
            print(f"Geprüft: {target}")

    print(f"\nFertig: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
