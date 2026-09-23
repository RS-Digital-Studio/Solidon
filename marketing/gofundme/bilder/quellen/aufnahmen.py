"""Nimmt das ganze Solidon3D-Fenster maximiert auf, für die GoFundMe-Bilder.

    .venv\\Scripts\\python.exe marketing/gofundme/bilder/quellen/aufnahmen.py \\
        --quelle <Ordner mit app/, tools/ und website/teile/ aus v0.4.4> --sprache de

Robert, 23.09.2026: „Du nimmst die Bilder aber schon so auf, dass der ganze
Bildschirm verwendet wird und wir nicht nur so eine kleine Szene haben.“ Also:
das Hauptfenster maximiert auf dem 2560x1440-Schirm, in nativen Pixeln, die
Kamera eng am Modell, und die Bedienung, um die es geht, im selben Bild.

**Aufgenommen wird die veröffentlichte Demo 0.4.4, nicht der Arbeitsbaum.**
Die Galerie soll zeigen, was man heute lädt; 0.5.0 zeigt zum Beispiel Maße im
Bild, die 0.4.4 nicht kennt. ``--quelle`` zeigt deshalb auf einen Ordner mit
den Dateien des Tags:

    git archive v0.4.4 app tools website/teile | tar -x -C <ordner>

Das Skript setzt diesen Ordner an die erste Stelle von ``sys.path`` und prüft,
dass ``app`` wirklich von dort kommt (``skript-im-worktree-laedt-app-aus-dem-
hauptbaum``).

**Mit eigenen Nutzerverzeichnissen.** Wie ``tools/make_web_images.py`` beim
Filamentlager: Die Aufnahme liest und schreibt Einstellungen, und Roberts
echtes Profil gehört einer neueren Version. Die Verzeichnisse liegen in einem
Temp-Ordner und verschwinden danach.

**Nur eigene Modelle.** Der Rollenhalter aus ``website/teile/weg1-halter-
anpassen.p3d`` (eingelesene STL mit echten Bohrungen) und das Beispiel
``passung-nach-materialwechsel.p3d``; beide stehen mit geklärter Rechtekette in
``ASSET-RIGHTS.toml``. Die Modelle in ``F:\\3D Dateien`` sind fremde Downloads
ohne festgehaltene Lizenz und kommen deshalb in kein öffentliches Bild.

Geschrieben werden je Szene die Vollbildaufnahme nach ``aufnahmen/`` und eine
``aufnahmen/<sprache>.json`` mit den Fensterkoordinaten der Stellen, auf die
``make_gofundme_images.py`` Ausschnitt und Maßmarken legt.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TARGET = HERE / "aufnahmen"

#: Die Nutzerverzeichnisse, die umgebogen werden — dieselben wie in
#: ``tests/conftest.py`` (§38).
ISOLATED = ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME")

#: Der neue Durchmesser für die große Bohrung des Rollenhalters, in mm.
NEW_DIAMETER = 38.0


def prepare(source: Path) -> None:
    """Umgebung und Suchpfad setzen, bevor irgendetwas Qt oder ``app`` lädt."""
    room = Path(tempfile.mkdtemp(prefix="gofundme-profil-"))
    for name in ISOLATED:
        folder = room / name
        folder.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(folder)
    os.environ.pop("QT_QPA_PLATFORM", None)
    sys.path.insert(0, str(source / "tools"))
    sys.path.insert(0, str(source))


class Capture:
    """Ein maximiertes Hauptfenster und die Aufnahmen daraus."""

    def __init__(self, source: Path, language: str) -> None:
        import make_figures as figures
        from PySide6.QtWidgets import QApplication

        import app as app_package
        from app.core.bootstrap import load_operations
        from app.i18n import install_catalog, set_language
        from app.i18n.catalog import read_catalog
        from app.ui.app import install_qt_translations
        from app.ui.main_window import MainWindow
        from app.ui.session import Session
        from app.ui.settings import UiSettings
        from app.ui.theme import apply_theme

        loaded_from = Path(app_package.__file__).resolve().parent.parent
        if loaded_from != source.resolve():
            raise SystemExit(f"app kommt aus {loaded_from}, nicht aus {source} — Abbruch.")
        self.figures = figures
        self.source = source
        self.language = language
        load_operations()
        self.app = QApplication.instance() or QApplication([])
        apply_theme(self.app, "dark")
        install_catalog(language, read_catalog(language))
        set_language(language)
        install_qt_translations(self.app, language)
        self.session = Session()
        self.window = figures.prepared(MainWindow(self.session, UiSettings()), hidden=False)
        self.window._show_start_screen(False)
        self.points: dict[str, Any] = {}

    # --- Ablauf ---------------------------------------------------------------

    def settle(self, rounds: int = 20) -> None:
        self.figures.settle(self.app, rounds)

    def open(self, path: Path) -> None:
        self.session.open_project(path)
        if not self.figures.await_result(self.app, self.session, 90.0):
            raise SystemExit(f"{path.name}: die Auswertung wurde nicht fertig.")
        self.window.raise_()
        self.window.activateWindow()
        self.settle(30)

    def body(self) -> tuple[str, Any]:
        result = self.session.last_result
        object_id, body = next(iter(result.scene.objects.items()))
        return object_id, body

    def camera(
        self, focal: tuple[float, ...], direction: tuple[float, ...], distance: float
    ) -> None:
        """Blickpunkt, Richtung vom Blickpunkt zur Kamera, Abstand in mm."""
        length = sum(value * value for value in direction) ** 0.5
        unit = [value / length for value in direction]
        position = tuple(focal[axis] + unit[axis] * distance for axis in range(3))
        self.window.viewport.set_camera_pose(position, tuple(focal), (0.0, 0.0, 1.0))
        self.window.viewport.settle_camera()
        self.window.viewport.renderer.render()
        self.settle(30)

    def window_point(self, point: tuple[float, ...]) -> tuple[float, float]:
        """Wo ein Weltpunkt im Fenster liegt, in Fensterpixeln."""
        from PySide6.QtCore import QPoint

        viewport = self.window.viewport
        x, y, _depth = viewport.renderer.world_to_display(tuple(point))
        origin = viewport.mapTo(self.window, QPoint(0, 0))
        return x + origin.x(), y + origin.y()

    def where(self, name: str, point: tuple[float, ...]) -> None:
        """Merkt sich, wo ein Weltpunkt im Fenster liegt (Fensterpixel)."""
        x, y = self.window_point(point)
        self.points.setdefault(self.current, {})[name] = [round(x), round(y)]

    def aim(
        self,
        point: tuple[float, ...],
        direction: tuple[float, ...],
        distance: float,
        target: tuple[float, float],
    ) -> None:
        """Kamera wie :meth:`camera`, aber so verschoben, dass ``point`` bei ``target``
        im Fenster liegt.

        Der Ausschnitt für GoFundMe schneidet aus der Vollbildaufnahme; damit die
        Handlung in dessen Mitte liegt, muss sie im Fenster an einer bestimmten
        Stelle stehen und nicht in der Mitte der Ansicht. Verschoben wird die
        Kamera parallel, der Blickwinkel bleibt.
        """
        length = sum(value * value for value in direction) ** 0.5
        back = [value / length for value in direction]
        forward = [-value for value in back]
        right = [forward[1] * 1.0 - forward[2] * 0.0, forward[2] * 0.0 - forward[0] * 1.0, 0.0]
        norm = sum(value * value for value in right) ** 0.5
        right = [value / norm for value in right]
        up = [
            right[1] * forward[2] - right[2] * forward[1],
            right[2] * forward[0] - right[0] * forward[2],
            right[0] * forward[1] - right[1] * forward[0],
        ]
        focal = [float(value) for value in point]
        self.camera(tuple(focal), direction, distance)
        for _ in range(4):
            x, y = self.window_point(point)
            dx, dy = target[0] - x, target[1] - y
            if abs(dx) < 2.0 and abs(dy) < 2.0:
                break
            shifted_right = tuple(point[axis] + right[axis] for axis in range(3))
            shifted_up = tuple(point[axis] + up[axis] for axis in range(3))
            per_mm_x = self.window_point(shifted_right)[0] - x
            per_mm_y = y - self.window_point(shifted_up)[1]
            focal = [
                focal[axis] - right[axis] * dx / per_mm_x + up[axis] * dy / per_mm_y
                for axis in range(3)
            ]
            self.camera(tuple(focal), direction, distance)

    def shoot(self, name: str) -> None:
        """Das Fenster ohne Titelleiste, so wie der Bildschirm es zeigt."""
        self.current = name
        screen = self.window.screen()
        shot = screen.grabWindow(self.window.winId())
        target = TARGET / f"{name}-{self.language}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not shot.save(str(target)):
            raise SystemExit(f"{target} ließ sich nicht schreiben.")
        print(f"  {target.name}: {shot.width()}x{shot.height()}", flush=True)

    def shoot_with_dialog(self, name: str, dialog: Any) -> None:
        """Fenster samt Dialog darüber: der Bildschirmausschnitt des Fensters."""
        from PySide6.QtCore import QPoint

        self.current = name
        screen = self.window.screen()
        origin = self.window.mapToGlobal(QPoint(0, 0)) - screen.geometry().topLeft()
        shot = screen.grabWindow(
            0, origin.x(), origin.y(), self.window.width(), self.window.height()
        )
        target = TARGET / f"{name}-{self.language}.png"
        if not shot.save(str(target)):
            raise SystemExit(f"{target} ließ sich nicht schreiben.")
        corner = dialog.mapTo(dialog, QPoint(0, 0))
        top_left = dialog.mapToGlobal(corner) - self.window.mapToGlobal(QPoint(0, 0))
        self.points.setdefault(name, {})["dialog"] = [
            top_left.x(),
            top_left.y(),
            dialog.width(),
            dialog.height(),
        ]
        print(f"  {target.name}: {shot.width()}x{shot.height()} (mit Dialog)", flush=True)

    # --- Szenen ---------------------------------------------------------------

    def holder(self) -> None:
        """Rollenhalter: vorher, Bohrung angeklickt und neues Maß getippt, nachher."""
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QDoubleSpinBox, QWidget

        self.open(self.source / "website" / "teile" / "weg1-halter-anpassen.p3d")
        object_id, body = self.body()
        holes = sorted(
            ((key, f) for key, f in body.features.items() if f.kind == "hole"),
            key=lambda pair: -float(pair[1].params.get("diameter", 0.0)),
        )
        (_left_key, left), (right_key, right) = sorted(
            holes[:2], key=lambda p: p[1].params["centre"][0]
        )
        # Die Übersicht liegt mit der Mitte des Teils bei 1180/720 im Fenster:
        # Der Ausschnitt für vorher und nachher beginnt links am Fensterrand,
        # damit der Verlauf mit im Bild steht, und hat seine Mitte bei 960.
        overview = ((0.0, 0.0, 26.0), (0.95, -1.25, 0.95), 245.0, (1180.0, 720.0))

        # Vorher: das ganze Teil, eng eingepasst, der Objektbaum zugeklappt,
        # damit der Verlauf ganz zu sehen ist.
        self.window.object_tree.tree.clearSelection()
        self.window.object_tree.tree.collapseAll()
        self.aim(*overview)
        self.shoot("halter-vorher")
        self.where("loch_links", left.params["centre"])
        self.where("loch_rechts", right.params["centre"])
        self.where("teil", (0.0, 0.0, 26.0))

        # Angeklickt: die rechte große Bohrung, nah von vorn rechts.
        self.window.object_tree.select_feature(object_id, right_key)
        self.settle(20)
        centre = tuple(float(value) for value in right.params["centre"])
        # Die Bohrung bei 1500/660: in der Mitte des rechtsbündigen Ausschnitts
        # (640 bis 2560), und links neben dem Prüfbericht, den sie so nicht
        # verdeckt.
        self.aim(centre, (1.0, -0.9, 0.45), 150.0, (1500.0, 660.0))
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.settle(10)
        panel = self.window.feature_panel
        key = next((entry for entry, run in panel._runs.items() if run.op == "resize_hole"), None)
        if key is None:
            raise SystemExit(f"„Bohrung ändern“ fehlt an der Bohrung: {panel._runs}")
        from app.core.registry.registry import REGISTRY

        declared = {entry.name: entry for entry in REGISTRY.get("resize_hole").params.spec()}
        label = str(declared["diameter"].title)
        editors = [
            widget
            for widget in panel.findChildren(QWidget)
            if widget.property("handlingKey") == key
            and isinstance(widget, QDoubleSpinBox)
            and widget.isVisibleTo(panel)
            and widget.accessibleName().endswith(f" — {label}")
        ]
        if len(editors) != 1:
            raise SystemExit(
                f"Durchmesserfeld nicht eindeutig: {[e.accessibleName() for e in editors]}"
            )
        field = editors[0]
        line = field.lineEdit()
        line.setFocus()
        line.selectAll()
        QTest.keyClicks(line, f"{NEW_DIAMETER:g}".replace(".", ","))
        self.settle(60)
        self.shoot("halter-bohrung")
        self.where("loch", centre)

        # Übernehmen, dann dieselbe Übersicht wie vorher.
        before = len(self.session.project.document.ops)
        panel._apply.click()
        if not self.figures.await_result(self.app, self.session, 90.0):
            raise SystemExit("„Bohrung ändern“ wurde nicht fertig.")
        self.settle(20)
        if len(self.session.project.document.ops) <= before:
            raise SystemExit("Übernehmen hat keinen Schritt angelegt.")
        self.window.object_tree.tree.clearSelection()
        self.window.object_tree.tree.collapseAll()
        self.settle(10)
        self.aim(*overview)
        self.shoot("halter-nachher")
        self.where("loch_links", left.params["centre"])
        self.where("loch_rechts", right.params["centre"])
        self.where("teil", (0.0, 0.0, 26.0))
        measured = self._diameter(right_key)
        self.points["halter-nachher"]["durchmesser_neu"] = measured
        self.points["halter-vorher"]["durchmesser_alt"] = float(right.params["diameter"])

        self.session.forget_changes()

    def _diameter(self, key: str) -> float:
        _object_id, body = self.body()
        feature = body.features.get(key)
        return float(feature.params.get("diameter", 0.0)) if feature is not None else 0.0

    def print_dialog(self) -> None:
        """„Drucken vorbereiten …“ über dem maximierten Fenster.

        „Das Wichtigste“ wird zugeklappt, wie es jeder Kunde mit einem Klick
        tut: Offen ist der Dialog 906 Punkte hoch, und der Teil, um den es im
        Bild geht (Vorschläge mit Grund, Übergabe an den Slicer), stünde auf
        dem Telefon unter GoFundMes Titel. Der Dialog steht mittig und so tief,
        dass über ihm Platz für die Überschrift bleibt.
        """
        from app.core import discover
        from app.core import tools as external_tools
        from app.ui.print_settings_dialog import PrintSettingsDialog

        found = discover.find_programs("slicer", external_tools.SLICERS)
        wanted = next((one for one in found if "prusa" in one.name.lower()), None)
        kept_remembered, kept_remember = discover.remembered_path, discover.remember_path
        if wanted is not None:
            discover.remembered_path = lambda tool_id: str(wanted)
        discover.remember_path = lambda tool_id, value: None
        try:
            dialog = PrintSettingsDialog(self.session, self.window.settings, self.window)
            dialog.show()
            dialog.raise_()
            if not dialog.wait_for_slicers():
                raise SystemExit("Die Slicersuche des Druckdialogs kam nicht zurück.")
            for _ in range(200):
                if not dialog._profiles_pending:
                    break
                self.settle(2)
            from PySide6.QtWidgets import QToolButton

            from app.i18n import tr

            for heading in dialog.findChildren(QToolButton, "sectionHeading"):
                if heading.text() == tr("Das Wichtigste") and heading.isChecked():
                    heading.setChecked(False)
            self.settle(10)
            dialog.adjustSize()
            dialog.resize(dialog.width(), dialog.minimumSizeHint().height())
            self.settle(10)
            frame = self.window.geometry()
            dialog.move(frame.x() + (frame.width() - dialog.width()) // 2, frame.y() + 420)
            self.settle(40)
            self.shoot_with_dialog("drucken", dialog)
            dialog.release()
            dialog.close()
        finally:
            discover.remembered_path, discover.remember_path = kept_remembered, kept_remember
        self.settle(10)

    def report(self) -> None:
        """Das Beispiel mit der Warnung im Prüfbericht."""
        self.open(self.source / "app" / "examples" / "passung-nach-materialwechsel.p3d")
        self.window.object_tree.tree.clearSelection()
        self.window.viewport.view_from("iso")
        self.window.viewport.reset_camera()
        self.settle(20)
        position, focal, _up, _scale = self.window.viewport.camera_pose()
        direction = tuple(position[axis] - focal[axis] for axis in range(3))
        distance = sum(value * value for value in direction) ** 0.5
        # Dose und Deckel bei 1450/720: in der Mitte des rechtsbündigen
        # Ausschnitts, mit dem Prüfbericht rechts daneben im selben Bild.
        self.aim(tuple(focal), direction, distance * 0.62, (1450.0, 720.0))
        self.settle(20)
        self.shoot("pruefbericht")
        self.where("modell", tuple(focal))

        # Drucken: der Dialog über demselben Fenster — an Dose und TPU-Deckel,
        # weil das weiche Material die meisten begründeten Vorschläge bringt.
        self.print_dialog()
        self.session.forget_changes()

    def close(self) -> None:
        self.session.forget_changes()
        self.window.close()
        self.session.release(120_000)
        self.figures.release_viewport(self.window)
        target = TARGET / f"{self.language}.json"
        target.write_text(json.dumps(self.points, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  {target.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quelle", type=Path, required=True, help="Ordner mit dem Stand v0.4.4")
    parser.add_argument("--sprache", choices=("de", "en"), default="de")
    arguments = parser.parse_args()
    source = arguments.quelle.resolve()
    if not (source / "app" / "branding.py").is_file():
        raise SystemExit(f"{source} enthält kein app/ — erst den Stand v0.4.4 auspacken.")
    prepare(source)
    capture = Capture(source, arguments.sprache)
    try:
        capture.holder()
        capture.report()
    finally:
        capture.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
