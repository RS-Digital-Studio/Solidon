"""Vollbildaufnahmen der echten Anwendung (Stand 0.4.4) für die Beitragsbilder.

Ein Prozess je Motiv und Sprache, wie bei ``tools/make_figures.py``::

    .venv\\Scripts\\python.exe marketing\\reichweite\\posts\\bilder\\capture_app.py \\
        --app <Baum von v0.4.4> --motif gegenstuecke --language de

``--app`` zeigt auf einen Export des Tags ``v0.4.4`` (``git archive v0.4.4 app
tools``, dazu der gebaute Kern ``app/core/slice/_chain*.pyd`` aus dem
Hauptbaum, dessen Quelle seit 0.4.4 unverändert ist), damit die Bilder die
Oberfläche der veröffentlichten Demo zeigen und nicht den Entwicklungsstand.
Das Werkzeug lädt Anwendung und Hilfsmodule aus diesem Baum, nie aus dem
Hauptbaum.

Bildstandard (Robert, 23.09.2026): das ganze Solidon-Fenster maximiert auf dem
2560x1440-Schirm, native Pixel, das Modell füllt die 3D-Ansicht, und das
Bedienelement der Handlung steht im selben Bild. Aufgenommen wird über
``PrintWindow`` der Inhalt des Fensters selbst, ein offener Dialog an seiner
Stelle darüber; der Bildschirmausschnitt dient nur zur Kontrolle.

Nutzerverzeichnisse werden vor dem ersten Import der Anwendung auf einen
eigenen Ordner gebogen; Roberts Einstellungen, Lager und Zuletzt-Liste bleiben
unberührt. Aufgenommene Dateien landen unter ``aufnahmen/`` neben diesem Skript.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "aufnahmen"
MOTIFS = (
    "probe",
    "bohrung",
    "gegenstuecke",
    "frage",
    "pruefbericht",
    "langloch",
    "demo",
    "schraubdose",
    "rueckmeldung",
    "unterstuetzen",
)
Vec = tuple[float, float, float]


def isolate_profile() -> Path:
    """Eigene Nutzerverzeichnisse setzen, bevor irgendetwas die Anwendung importiert."""
    profile = Path(tempfile.mkdtemp(prefix="solidon-post-capture-"))
    for name in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
        target = profile / name
        target.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(target)
    os.environ.pop("QT_QPA_PLATFORM", None)
    return profile


def unit(vector: Sequence[float]) -> Vec:
    """Vektor auf Länge eins bringen."""
    length = math.sqrt(sum(value * value for value in vector)) or 1.0
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def cross(a: Vec, b: Vec) -> Vec:
    """Kreuzprodukt."""
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def print_window(hwnd: int, *, client_only: bool) -> Any:
    """Den Inhalt eines Fensters über ``PrintWindow`` als PIL-Bild holen (nur Windows)."""
    import ctypes
    from ctypes import wintypes

    from PIL import Image

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC,
        wintypes.HBITMAP,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.UINT,
    ]
    rect = wintypes.RECT()
    if client_only:
        user32.GetClientRect(wintypes.HWND(hwnd), ctypes.byref(rect))
    else:
        user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    screen_dc = user32.GetDC(None)
    memory_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    gdi32.SelectObject(memory_dc, bitmap)
    flags = 0x2 | (0x1 if client_only else 0x0)  # PW_RENDERFULLCONTENT, PW_CLIENTONLY
    if not user32.PrintWindow(wintypes.HWND(hwnd), memory_dc, flags):
        raise SystemExit("PrintWindow ist fehlgeschlagen")

    class Header(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    header = Header()
    header.biSize = ctypes.sizeof(Header)
    header.biWidth = width
    header.biHeight = -height  # von oben nach unten
    header.biPlanes = 1
    header.biBitCount = 32
    buffer = ctypes.create_string_buffer(width * height * 4)
    lines = gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer, ctypes.byref(header), 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memory_dc)
    user32.ReleaseDC(None, screen_dc)
    if lines != height:
        raise SystemExit("GetDIBits lieferte nicht alle Zeilen")
    return Image.frombuffer("RGBA", (width, height), buffer.raw, "raw", "BGRA", 0, 1).convert("RGB")


def visible_window(hwnd: int) -> tuple[Any, int, int]:
    """Ein Fenster samt Titelleiste, ohne die unsichtbaren Randflächen von Windows.

    ``PrintWindow`` zeichnet das ganze Fensterrechteck, und darin liegen links,
    rechts und unten einige unsichtbare Pixel zum Ziehen der Größe; im Bild
    wären sie ein schwarzer Rahmen. ``DWMWA_EXTENDED_FRAME_BOUNDS`` nennt den
    sichtbaren Teil. Zurück kommen Bild und linke obere Ecke in
    Bildschirmkoordinaten.
    """
    import ctypes
    from ctypes import wintypes

    whole = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(whole))
    visible = wintypes.RECT()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd), 9, ctypes.byref(visible), ctypes.sizeof(visible)
    )
    image = print_window(hwnd, client_only=False)
    box = (
        visible.left - whole.left,
        visible.top - whole.top,
        visible.right - whole.left,
        visible.bottom - whole.top,
    )
    return image.crop(box), visible.left, visible.top


def client_origin(hwnd: int) -> tuple[int, int]:
    """Linke obere Ecke der Client-Fläche in Bildschirmkoordinaten."""
    import ctypes
    from ctypes import wintypes

    point = wintypes.POINT(0, 0)
    ctypes.windll.user32.ClientToScreen(wintypes.HWND(hwnd), ctypes.byref(point))
    return point.x, point.y


class Capture:
    """Ein sichtbares, maximiertes Hauptfenster und die Werkzeuge, es aufzunehmen."""

    def __init__(self, app_root: Path, language: str) -> None:
        sys.path.insert(0, str(app_root))
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication

        QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
        self.app = QApplication.instance() or QApplication([])

        from app.branding import APP_VERSION
        from app.core.bootstrap import load_operations
        from app.i18n import install_catalog, set_language
        from app.i18n.catalog import read_catalog
        from app.ui.app import install_qt_translations
        from app.ui.main_window import MainWindow
        from app.ui.session import Session
        from app.ui.settings import UiSettings
        from app.ui.theme import apply_theme
        from tools import make_figures as figures

        if APP_VERSION != "0.4.4":
            raise SystemExit(f"Erwartet wird der Baum von 0.4.4, gefunden: {APP_VERSION}")
        self.version = APP_VERSION
        self.figures = figures
        self.language = language
        load_operations()
        install_catalog(language, read_catalog(language))
        set_language(language)
        install_qt_translations(self.app, language)
        apply_theme(self.app, "dark")
        self.session = Session()
        self.window = MainWindow(self.session, UiSettings(language=language))
        figures.prepared(self.window, hidden=False)
        self.session.start_new()
        self.window._show_start_screen(False)
        self.wait("Leeres Projekt")
        self.window.raise_()
        self.window.activateWindow()
        self.settle(40)

    # --- Warten ---------------------------------------------------------------

    def settle(self, rounds: int = 12) -> None:
        """Einen echten Event-Loop laufen lassen (siehe ``make_figures.settle``)."""
        self.figures.settle(self.app, rounds)

    def wait(self, context: str) -> None:
        """Auf die Auswertung warten und abbrechen, wenn sie nicht vollständig ist."""
        self.session.wait_for_idle(120_000)
        self.settle(6)
        result = self.session.last_result
        if result is None or not result.complete:
            raise SystemExit(f"{context}: Auswertung unvollständig")

    # --- Kamera ---------------------------------------------------------------

    def frame(
        self,
        target: Vec,
        direction: Vec,
        extent: float,
        *,
        fill: float = 0.8,
        shift: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        """Kamera auf ``target`` richten, so dass ``extent`` Millimeter ``fill`` der
        Viewporthöhe einnehmen; ``shift`` verschiebt das Ziel im Bild (Anteil der
        halben Viewportbreite bzw. -höhe, rechts und oben positiv)."""
        viewport = self.window.viewport
        renderer = viewport.renderer
        height = max(viewport.height(), 1)
        width = max(viewport.width(), 1)
        projection = float(renderer._camera.projection_matrix[1, 1])
        distance = extent * projection / (2.0 * fill)
        view = unit(direction)
        right = unit(cross((-view[0], -view[1], -view[2]), (0.0, 0.0, 1.0)))
        up = unit(cross(right, (-view[0], -view[1], -view[2])))
        per_pixel = 2.0 * distance / (projection * height)
        dx = -shift[0] * (width / 2.0) * per_pixel
        dy = -shift[1] * (height / 2.0) * per_pixel
        focal = tuple(target[i] + right[i] * dx + up[i] * dy for i in range(3))
        position = tuple(focal[i] + view[i] * distance for i in range(3))
        # Zweimal, mit Prüfung dazwischen: Eine gerade fertig gewordene Auswertung
        # kann die Ansicht noch einmal einpassen und die gesetzte Stellung
        # überschreiben. Dann stimmt das Bild nicht mit dem Zuschnitt überein.
        for _attempt in range(3):
            viewport.set_camera_pose(position, focal, (0.0, 0.0, 1.0))
            viewport.settle_camera()
            renderer.render()
            self.settle(20)
            current = renderer.camera_pose().position
            if math.dist(current, position) <= 1e-3 * max(distance, 1.0):
                return
        raise SystemExit("Die Kamerastellung wurde von der Anwendung überschrieben")

    # --- Aufnahme -------------------------------------------------------------

    def layout(self) -> dict[str, list[int]]:
        """Wo die wichtigen Bereiche im Fenster liegen, in Fensterpixeln."""
        from PySide6.QtCore import QPoint

        found: dict[str, list[int]] = {}
        for name in ("viewport", "feature_panel", "report", "object_tree", "parameters"):
            widget = getattr(self.window, name, None)
            if widget is None or not widget.isVisible():
                continue
            origin = widget.mapTo(self.window, QPoint(0, 0))
            found[name] = [origin.x(), origin.y(), widget.width(), widget.height()]
        return found

    def shoot(self, name: str, extra: dict[str, Any] | None = None, dialog: Any = None) -> Path:
        """Das Hauptfenster aufnehmen, einen offenen Dialog an seiner Stelle eingeschlossen.

        **Über ``PrintWindow`` und nicht vom Bildschirm.** Auf demselben Schirm
        öffnen andere Sitzungen eigene Solidon-Fenster (Handbuch- und
        Website-Bilder); eine Bildschirmaufnahme nahm am 23.09.2026 zweimal deren
        Startbildschirm statt des eigenen Fensters auf. ``PrintWindow`` mit
        ``PW_RENDERFULLCONTENT`` zeichnet den Inhalt des Fensters selbst, auch die
        3D-Ansicht, gleich was darüber liegt. Zur Kontrolle wird der
        Bildschirmausschnitt daneben gelegt: Weicht er stark ab, war das Fenster
        verdeckt, und das steht im Beleg.
        """
        from PIL import Image, ImageChops, ImageStat
        from PySide6.QtCore import QPoint

        self.window.raise_()
        self.window.activateWindow()
        if dialog is not None:
            dialog.raise_()
            dialog.activateWindow()
        self.settle(10)
        image = print_window(int(self.window.winId()), client_only=True)
        if dialog is not None:
            panel, left, top = visible_window(int(dialog.winId()))
            client_x, client_y = client_origin(int(self.window.winId()))
            image.paste(panel, (left - client_x, top - client_y))
        screen = self.window.screen()
        top_left = self.window.mapToGlobal(QPoint(0, 0))
        screen_origin = screen.geometry().topLeft()
        grabbed = screen.grabWindow(
            0,
            top_left.x() - screen_origin.x(),
            top_left.y() - screen_origin.y(),
            self.window.width(),
            self.window.height(),
        )
        check = Image.fromqimage(grabbed.toImage()).convert("RGB")
        difference = 0.0
        if check.size == image.size:
            difference = sum(ImageStat.Stat(ImageChops.difference(check, image)).mean) / 3.0
        OUTPUT.mkdir(parents=True, exist_ok=True)
        target = OUTPUT / f"{name}-{self.language}.png"
        image.save(target)
        info = {
            "version": self.version,
            "language": self.language,
            "screen": screen.name(),
            "device_pixel_ratio": screen.devicePixelRatio(),
            "size": list(image.size),
            "method": "PrintWindow(PW_CLIENTONLY | PW_RENDERFULLCONTENT)",
            "screen_difference": round(difference, 2),
            "layout": self.layout(),
            **(extra or {}),
        }
        target.with_suffix(".json").write_text(
            json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        note = "  (Bildschirm wich ab: verdeckt?)" if difference > 6.0 else ""
        print(f"{target.name}: {image.size[0]}x{image.size[1]}, Abweichung {difference:.2f}{note}")
        return target

    def modal(self, action: Callable[[], None], inside: Callable[[Any], None]) -> None:
        """Einen echten modalen Dialog öffnen und in seiner Ereignisschleife arbeiten."""
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QDialog

        failures: list[BaseException] = []

        def visit() -> None:
            dialog = QApplication.activeModalWidget()
            try:
                if dialog is None:
                    raise RuntimeError("Die Aktion hat keinen modalen Dialog geöffnet.")
                inside(dialog)
            except BaseException as error:
                failures.append(error)
            finally:
                if isinstance(dialog, QDialog):
                    dialog.reject()

        QTimer.singleShot(400, visit)
        action()
        if failures:
            raise failures[0]

    def close(self) -> None:
        """Ohne Speichernachfrage schließen und den Renderer freigeben."""
        self.session.forget_changes()
        self.window.close()
        self.session.release(120_000)
        self.figures.release_viewport(self.window)


def motif_probe(capture: Capture) -> None:
    """Ein Beispielprojekt öffnen und das Fenster ausmessen."""
    from app.core import examples

    capture.session.open_project(examples.directory() / "passung-nach-materialwechsel.p3d")
    capture.wait("Beispiel")
    capture.window.viewport.reset_camera()
    capture.settle(30)
    capture.shoot("probe")


def build_source(folder: Path, name: str, drafts: Sequence[tuple[str, dict[str, Any]]]) -> Path:
    """Eine eigene Ausgangs-STL über registrierte Operationen bauen (keine fremden Rechte)."""
    from app.core.geom.mesh import as_mesh_data
    from app.core.knowledge import profiles
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import new_project

    project = new_project()
    history = History(project.document)
    for op, params in drafts:
        inputs = ("obj_1",) if op != "create_box" else ()
        history.apply(name, [OperationDraft(op=op, inputs=inputs, params=params)])
    result = evaluate(project.document, profiles.make_profile())
    if not result.complete or len(result.scene.objects) != 1:
        raise SystemExit(f"Ausgangsmodell {name} ist nicht eindeutig")
    body = next(iter(result.scene.objects.values()))
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.stl"
    as_mesh_data(body.mesh).raw.export(path)
    return path


def import_stl(capture: Capture, path: Path) -> str:
    """Eine STL wie über „Modell einfügen“ einlesen und die neue Körperkennung liefern."""
    before = set(capture.session.last_result.scene.objects)
    if not capture.session.import_model(path, raise_on_error=True):
        raise SystemExit(f"{path.name} ließ sich nicht einlesen")
    capture.wait(f"Import {path.name}")
    added = set(capture.session.last_result.scene.objects) - before
    if len(added) != 1:
        raise SystemExit(f"Import sollte genau einen Körper liefern: {added}")
    return str(added.pop())


def holes(capture: Capture, body: str) -> list[tuple[str, Any]]:
    """Erkannte Bohrungen eines Körpers, von links nach rechts."""
    features = capture.session.last_result.scene.objects[body].features
    found = [(key, feature) for key, feature in features.items() if feature.kind == "hole"]
    return sorted(found, key=lambda pair: pair[1].params["centre"][0])


def typed(value: float) -> str:
    """Eine Zahl so, wie sie ein Kunde in ein Feld tippt (Dezimalzeichen des Systems)."""
    from PySide6.QtCore import QLocale

    return f"{value:g}".replace(".", QLocale().decimalPoint())


def move_body(capture: Capture, body: str, dx: float) -> None:
    """Ein Teil über die Bewegen-Leiste unten verschieben, wie ein Kunde es tut."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window = capture.window
    window.object_tree.select_object(body)
    capture.settle(10)
    button = window.tools._buttons["transform"]
    button.click()
    capture.settle(12)
    bar = window.transform_bar
    if not bar.isVisible() or bar.role() != "move":
        raise SystemExit("Die Bewegen-Leiste ist nach dem Klick nicht offen")
    line = bar.dx.lineEdit()
    line.setFocus()
    line.selectAll()
    QTest.keyClicks(line, typed(dx))
    capture.settle(6)
    before = len(capture.session.project.document.ops)
    QTest.keyClick(line, Qt.Key.Key_Return)
    capture.wait("Verschieben")
    if len(capture.session.project.document.ops) <= before:
        raise SystemExit("Enter in der Bewegen-Leiste hat keinen Schritt angelegt")
    button.click()
    capture.settle(8)
    window.object_tree.tree.clearSelection()
    capture.settle(6)


def type_into_card(capture: Capture, op: str, values: dict[str, float]) -> Any:
    """Im Merkmalfenster rechts Zahlen in die Handlung ``op`` tippen (Vorschau, kein Übernehmen)."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDoubleSpinBox, QScrollArea, QWidget

    from app.core.registry import REGISTRY

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    capture.settle(6)
    panel = capture.window.feature_panel
    key = next((entry for entry, run in panel._runs.items() if run.op == op), None)
    if key is None:
        raise SystemExit(f"Das Merkmalfenster bietet {op} nicht an: {panel._runs}")
    declared = {entry.name: entry for entry in REGISTRY.get(op).params.spec()}
    editors = [
        widget
        for widget in panel.findChildren(QWidget)
        if widget.property("handlingKey") == key
        and isinstance(widget, QDoubleSpinBox)
        and widget.isVisibleTo(panel)
    ]
    last = None
    for name, value in values.items():
        label = str(declared[name].title)
        found = [w for w in editors if w.accessibleName().endswith(f" — {label}")]
        if len(found) != 1:
            raise SystemExit(f"{op}: Feld {name} nicht eindeutig im Merkmalfenster")
        editor = found[0]
        parent = editor.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                parent.ensureWidgetVisible(editor, 40, 60)
                break
            parent = parent.parentWidget()
        line = editor.lineEdit()
        line.setFocus()
        line.selectAll()
        QTest.keyClicks(line, typed(value))
        capture.settle(10)
        actual = editor.value_mm() if hasattr(editor, "value_mm") else editor.value()
        if abs(float(actual) - float(value)) > 1e-6:
            raise SystemExit(f"{op}: Feld {name} zeigt {actual} statt {value}")
        last = editor
    # Die Vorschau rechnet im Arbeiter; warten, bis sie im Bild steht.
    capture.session.wait_for_idle(60_000)
    capture.settle(40)
    return last


def motif_bohrung(capture: Capture) -> None:
    """Senkbohrung an einer eingelesenen STL: neuer Durchmesser im Merkmalfenster, Vorschau."""
    folder = Path(tempfile.mkdtemp(prefix="solidon-post-source-"))
    name = "Halterung" if capture.language == "de" else "Bracket"
    path = build_source(
        folder,
        name,
        [
            ("create_box", {"width": 80.0, "depth": 44.0, "height": 6.0}),
            *[
                (
                    "drill_hole",
                    {
                        "diameter": 4.5,
                        "widening_diameter": 9.0,
                        "widening_depth": 0.0,
                        "transition_angle": 90.0,
                        "depth": 0.0,
                        "x": x,
                        "y": 0.0,
                        "z": 6.0,
                        "axis": "z",
                        "compensate": False,
                    },
                )
                for x in (-26.0, 26.0)
            ],
        ],
    )
    body = import_stl(capture, path)
    found = holes(capture, body)
    if len(found) != 2:
        raise SystemExit(f"Erwartet zwei erkannte Bohrungen, gefunden {len(found)}")
    key, _feature = found[1]
    capture.window.object_tree.select_feature(body, key)
    capture.settle(20)
    type_into_card(capture, "resize_hole", {"diameter": 6.6})
    # Beide Bohrungen im Bild: links die unveränderte, rechts die Vorschau mit
    # dem neuen Durchmesser. Die Lage im Fenster richtet sich nach dem
    # Zuschnitt (rechts das Merkmalfenster, darüber der Prüfbericht).
    capture.frame(
        (0.0, 0.0, 6.0), (0.0, -1.0, 1.25), 52.0, fill=0.5, shift=shift_for(capture, 1890, 910)
    )
    capture.shoot("bohrung", {"hole": key, "diameter_before": 4.5, "diameter_after": 6.6})


def face_facing(capture: Capture, body: str, direction: float) -> str:
    """Die eine ebene Seitenfläche eines Körpers, die in ±X zeigt."""
    features = capture.session.last_result.scene.objects[body].features
    found = [
        key
        for key, feature in features.items()
        if feature.kind == "face" and feature.params.get("normal", (0, 0, 0))[0] * direction > 0.99
    ]
    if len(found) != 1:
        raise SystemExit(f"Seitenfläche an {body} nicht eindeutig: {found}")
    return str(found[0])


def motif_gegenstuecke(capture: Capture) -> None:
    """Zwei eingelesene Teile, Dialog „Gegenstücke setzen“ offen, Stift und Loch in der Vorschau."""
    from PySide6.QtCore import QPoint

    from tools.make_longform_video import _button
    from tools.make_workshop_videos import set_field

    folder = Path(tempfile.mkdtemp(prefix="solidon-post-source-"))
    names = (
        ("Teil-links", "Teil-rechts") if capture.language == "de" else ("part-left", "part-right")
    )
    first = import_stl(
        capture,
        build_source(
            folder,
            names[0],
            [("create_box", {"width": 20.0, "depth": 36.0, "height": 24.0, "x": -40.0})],
        ),
    )
    second = import_stl(
        capture,
        build_source(
            folder,
            names[1],
            [("create_box", {"width": 20.0, "depth": 36.0, "height": 24.0, "x": 20.0})],
        ),
    )
    move_body(capture, first, -30.0)
    first_face = face_facing(capture, first, 1.0)
    second_face = face_facing(capture, second, -1.0)
    capture.window.object_tree.select_features([(first, first_face), (second, second_face)])
    capture.settle(20)
    action = capture.window.counterpart_action
    if not action.isEnabled():
        raise SystemExit("„Gegenstücke setzen“ ist trotz zweier Flächen gesperrt")
    left = capture.session.last_result.scene.objects[first].mesh.bounds
    right = capture.session.last_result.scene.objects[second].mesh.bounds
    gap_centre = (
        (float(left.maximum[0]) + float(right.minimum[0])) / 2.0,
        0.0,
        float(left.maximum[2]) / 2.0,
    )
    placement = {"de": (1240, 560, 800), "en": (1240, 470, 660)}[capture.language]

    def inside(dialog: Any) -> None:
        dialog.pairs.setCurrentIndex(dialog.pairs.findData("dowel"))
        for name, value in {"diameter": 8.0, "length": 12.0, "play": 0.2, "chamfer": 0.5}.items():
            set_field(dialog._fields[name], value)
        dialog.valuesChanged.emit()
        capture.settle(30)
        capture.session.wait_for_idle(60_000)
        capture.settle(40)
        capture.frame(
            gap_centre,
            (-0.42, -1.0, 0.42),
            58.0,
            fill=0.6,
            shift=shift_for(capture, placement[0], placement[1]),
        )
        dialog.adjustSize()
        origin = capture.window.mapToGlobal(QPoint(0, 0))
        dialog.move(origin.x() + 1240 - dialog.width() // 2, origin.y() + placement[2])
        capture.settle(30)
        capture.shoot(
            "gegenstuecke",
            {
                "pair": "dowel",
                "values": {"diameter": 8.0, "length": 12.0, "play": 0.2, "chamfer": 0.5},
                "dialog": [
                    dialog.x() - origin.x(),
                    dialog.y() - origin.y(),
                    dialog.width(),
                    dialog.height(),
                ],
                "ok_button": _button(dialog).text(),
            },
            dialog=dialog,
        )

    capture.modal(action.trigger, inside)


def open_project(capture: Capture, path: Path) -> None:
    """Ein Projekt öffnen, wie über Datei → Öffnen, ohne die Zuletzt-Liste zu berühren.

    Gewartet wird, bis das Projekt wirklich steht: Die Auswertung des leeren
    Projekts davor ist auch „vollständig“, und am 23.09.2026 wurde so einmal der
    Ladebildschirm aufgenommen statt des Modells.
    """
    import time

    capture.session.open_project(path)
    capture.window._show_start_screen(False)
    deadline = time.monotonic() + 180.0
    while time.monotonic() < deadline:
        capture.session.wait_for_idle(2_000)
        capture.settle(5)
        result = capture.session.last_result
        if (
            result is not None
            and result.complete
            and result.scene.objects
            and capture.session.project.document.ops
        ):
            break
    else:
        raise SystemExit(f"{path.name} wurde nicht fertig geladen")
    tour = getattr(capture.window, "tour", None)
    if tour is not None and getattr(tour, "active", False):
        capture.window._remove_tour()
    capture.settle(60)


REPOSITORY = Path(__file__).resolve().parents[4]


def scene_box(capture: Capture) -> tuple[Vec, float]:
    """Mitte und größte Ausdehnung aller Körper der Szene."""
    bounds = [body.mesh.bounds for body in capture.session.last_result.scene.objects.values()]
    low = [min(float(b.minimum[i]) for b in bounds) for i in range(3)]
    high = [max(float(b.maximum[i]) for b in bounds) for i in range(3)]
    centre = ((low[0] + high[0]) / 2.0, (low[1] + high[1]) / 2.0, (low[2] + high[2]) / 2.0)
    return centre, max(high[i] - low[i] for i in range(3))


def shift_for(capture: Capture, x: float, y: float) -> tuple[float, float]:
    """Bildschirmstelle in Fensterpixeln als Verschiebung für :meth:`Capture.frame`."""
    from PySide6.QtCore import QPoint

    viewport = capture.window.viewport
    origin = viewport.mapTo(capture.window, QPoint(0, 0))
    centre_x = origin.x() + viewport.width() / 2.0
    centre_y = origin.y() + viewport.height() / 2.0
    return (x - centre_x) / (viewport.width() / 2.0), (centre_y - y) / (viewport.height() / 2.0)


def dialog_box(capture: Capture, dialog: Any) -> list[int]:
    """Lage eines offenen Dialogs in Fensterpixeln."""
    from PySide6.QtCore import QPoint

    origin = capture.window.mapToGlobal(QPoint(0, 0))
    frame = dialog.frameGeometry()
    return [frame.x() - origin.x(), frame.y() - origin.y(), frame.width(), frame.height()]


def motif_frage(capture: Capture) -> None:
    """Der eingelesene und angepasste Rollenhalter mit seinem Verlauf links."""
    open_project(capture, REPOSITORY / "website/teile/weg1-halter-anpassen.p3d")
    centre, size = scene_box(capture)
    capture.frame(centre, (1.0, -1.1, 0.95), size, fill=0.44, shift=shift_for(capture, 690, 440))
    capture.shoot("frage", {"project": "website/teile/weg1-halter-anpassen.p3d"})


def motif_pruefbericht(capture: Capture) -> None:
    """Das Beispiel mit der zu engen Passung: Modell groß, Prüfbericht rechts daneben."""
    # Eine Kopie außerhalb des Beispielordners: Ein geöffnetes Beispiel startet
    # seine Tour, und die richtet die Kamera nach dem Einpassen noch einmal aus.
    import shutil

    from app.core import examples

    copy = (
        Path(tempfile.mkdtemp(prefix="solidon-post-source-")) / "passung-nach-materialwechsel.p3d"
    )
    shutil.copyfile(examples.directory() / "passung-nach-materialwechsel.p3d", copy)
    open_project(capture, copy)
    centre, size = scene_box(capture)
    capture.frame(centre, (-0.9, -1.3, 1.0), size, fill=0.62, shift=shift_for(capture, 1600, 860))
    capture.shoot("pruefbericht", {"project": "app/examples/passung-nach-materialwechsel.p3d"})


def motif_langloch(capture: Capture) -> None:
    """Rundes Loch an einer eingelesenen STL, im Merkmalfenster zum Langloch gezogen (Vorschau)."""
    folder = Path(tempfile.mkdtemp(prefix="solidon-post-source-"))
    name = "Wandhalter" if capture.language == "de" else "wall-mount"
    path = build_source(
        folder,
        name,
        [
            ("create_box", {"width": 100.0, "depth": 55.0, "height": 8.0}),
            *[
                (
                    "drill_hole",
                    {
                        "diameter": 6.0,
                        "depth": 0.0,
                        "x": x,
                        "y": 0.0,
                        "z": 8.0,
                        "axis": "z",
                        "compensate": False,
                    },
                )
                for x in (-28.0, 28.0)
            ],
        ],
    )
    body = import_stl(capture, path)
    found = holes(capture, body)
    if len(found) != 2:
        raise SystemExit(f"Erwartet zwei erkannte Bohrungen, gefunden {len(found)}")
    key = found[0][0]
    capture.window.object_tree.select_feature(body, key)
    capture.settle(20)
    type_into_card(capture, "slot_hole", {"slot_length": 20.0, "slot_angle": 0.0})
    capture.frame(
        (-5.0, 0.0, 8.0), (0.0, -1.0, 1.25), 56.0, fill=0.47, shift=shift_for(capture, 1890, 910)
    )
    capture.shoot("langloch", {"hole": key, "slot_length": 20.0, "slot_angle": 0.0})


def motif_demo(capture: Capture) -> None:
    """Das Elektronikgehäuse mit Parametern und Verlauf, groß im Fenster."""
    open_project(capture, REPOSITORY / "website/teile/gehaeuse.p3d")
    centre, size = scene_box(capture)
    target, fill = {"de": ((690, 560), 0.52), "en": ((700, 430), 0.46)}[capture.language]
    capture.frame(centre, (1.0, -1.2, 0.95), size, fill=fill, shift=shift_for(capture, *target))
    steps = len(capture.session.project.document.ops)
    capture.shoot("demo", {"project": "website/teile/gehaeuse.p3d", "steps": steps})


def motif_schraubdose(capture: Capture) -> None:
    """Die Vorratsdose mit Schraubdeckel und ihrem Verlauf."""
    open_project(capture, REPOSITORY / "website/teile/schraubdose.p3d")
    centre, size = scene_box(capture)
    capture.frame(centre, (1.0, -1.25, 0.8), size, fill=0.56, shift=shift_for(capture, 700, 560))
    steps = [str(op.op) for op in capture.session.project.document.ops]
    capture.shoot("schraubdose", {"project": "website/teile/schraubdose.p3d", "steps": steps})


def motif_dialog(capture: Capture, name: str, project: Path, action: Callable[[], None]) -> None:
    """Ein Projekt öffnen und einen modalen Dialog der Anwendung mit aufnehmen."""
    open_project(capture, project)
    centre, size = scene_box(capture)
    capture.frame(centre, (1.0, -1.2, 0.95), size, fill=0.62, shift=shift_for(capture, 1155, 700))

    def inside(dialog: Any) -> None:
        capture.settle(30)
        capture.shoot(
            name,
            {
                "project": project.relative_to(REPOSITORY).as_posix(),
                "dialog": dialog_box(capture, dialog),
            },
            dialog=dialog,
        )

    capture.modal(action, inside)


def motif_rueckmeldung(capture: Capture) -> None:
    """Hilfe, Rückmeldung senden, über dem Rollenhalter."""
    motif_dialog(
        capture,
        "rueckmeldung",
        REPOSITORY / "website/teile/rollenhalter.p3d",
        capture.window.action_feedback,
    )


def motif_unterstuetzen(capture: Capture) -> None:
    """Hilfe, Solidon3D unterstützen, über dem Rollenhalter."""
    motif_dialog(
        capture,
        "unterstuetzen",
        REPOSITORY / "website/teile/rollenhalter.p3d",
        capture.window.action_donate,
    )


MOTIF_FUNCTIONS: dict[str, Callable[[Capture], None]] = {
    "probe": motif_probe,
    "bohrung": motif_bohrung,
    "gegenstuecke": motif_gegenstuecke,
    "frage": motif_frage,
    "pruefbericht": motif_pruefbericht,
    "langloch": motif_langloch,
    "demo": motif_demo,
    "schraubdose": motif_schraubdose,
    "rueckmeldung": motif_rueckmeldung,
    "unterstuetzen": motif_unterstuetzen,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True, help="Baum von v0.4.4")
    parser.add_argument("--motif", choices=MOTIFS, required=True)
    parser.add_argument("--language", choices=("de", "en"), default="de")
    args = parser.parse_args()
    isolate_profile()
    capture = Capture(args.app.resolve(), args.language)
    try:
        MOTIF_FUNCTIONS[args.motif](capture)
    finally:
        capture.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
