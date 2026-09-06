"""Galeriebilder für die Website: ein Teil, groß, mit Licht und Schatten.

    .venv\\Scripts\\python.exe tools/make_gallery.py [name …]

Die Startseite zeigt im Beweis-Teil (WD3, M6), was mit Solidon entsteht. Für
diese Bilder gilt etwas anderes als für die Belegbilder daneben: Dort geht es
um die Oberfläche, hier um das Teil. Aufgenommen wird deshalb der Viewport,
und die Karten werden weggeschnitten.

**Warum nicht die flache Projektion.** ``drawing.project`` zeichnet ohne Licht
— gut genug für ein Vorschaubild im Katalog und für das Vorher/Nachher, wo es
auf sichtbare Löcher ankommt. Für ein Bild, das Qualität zeigen soll, fehlt
ihm alles, was Qualität ausmacht: Schatten, Materialwirkung, weiche Kanten.
Vier Versuche mit Textur und Gitter sind daran gescheitert — sauber gerechnet,
und trotzdem nichtssagend. Robert am 30.08.2026: „ja den besten weg, wir
wollen qualität zeigen."

**Drei Fallen, alle beim Bauen zugeschnappt.**

1. *Die Karten ausblenden nimmt den Viewport mit.* Der Träger, den man über
   ``parentWidget()`` sucht, hält beide — das Bild wurde schwarz. Geschnitten
   wird deshalb, statt zu verstecken.
2. *``mapTo`` über zwei Hierarchien lügt.* Die gemessenen Kanten lagen bei
   5973 und 7845 Punkten in einem 2560 breiten Fenster. Gemessen wird über
   ``mapToGlobal`` beider Seiten und die Differenz.
3. *``reset_camera`` lässt Luft.* Das ist beim Arbeiten richtig und für ein
   Galeriebild verschenkte Fläche; ein Zoom danach holt das Teil heran.

**Nicht offscreen.** Wie ``make_figures`` und ``make_web_images``: Dort hat Qt
keine Schriften, und die Ansicht baut keinen Renderer — ``grab`` bekäme ein
leeres Bild. Aufgenommen wird über ``screen.grabWindow``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QWidget

from app.core.bootstrap import load_operations

TARGET = Path(__file__).resolve().parent.parent / "website" / "bilder"

#: Wie nah die Kamera an das Teil geht, nachdem sie eingepasst hat.
#:
#: 1,7 schnitt den Deckel des Schaustücks am rechten Rand an; 1,4 lässt einen
#: Rand, der das Teil nicht klein aussehen lässt. Gemessen am breitesten Motiv,
#: weil der Zuschnitt für alle gilt.
ZOOM = 1.4

#: Wo die Vorgabe zu nah ist — je Teil, mit Grund.
#:
#: ``reset_camera`` rahmt nach einem Schwenk enger als aus der Vorgabe heraus:
#: Ein Teil, das von hinten flach gesehen wird, füllt mehr Breite als dasselbe
#: Teil von schräg oben. 1,4 schnitt den Lochwandhalter an.
ZOOMS: dict[str, float] = {
    # Am fertigen Seitenausschnitt gemessen: In einer 288 Punkte breiten
    # Kachel waren die Einhänger bei 1,0 nicht mehr zu erkennen — und sie
    # sind der Grund, warum das Teil dasteht.
    "lochwandhalter": 1.45,
    "klappbox": 1.15,
    # Zwei Körper nebeneinander, und ``reset_camera`` rahmt beide mit Luft:
    # Bei 0,95 stand das halbe Druckbett samt Maßzahlen im Bild. **Der Wert
    # hing am Gizmo**: Solange es in der Szene stand, rahmte ``reset_camera``
    # weiter, und 1,35 traf. Ohne Gizmo rahmt sie enger, und derselbe Wert
    # schnitt die Dose zu einem Ausschnitt ihrer Wand zusammen — sichtbar nur
    # daran, dass man plötzlich die roten Innenflächen des Gewindes sah.
    "schraubdose": 1.05,
}

#: Abstand des Zuschnitts zu den Karten, in Bildpunkten.
MARGIN = 24

#: Breite des abgelegten Bildes.
#:
#: Aufgenommen wird in Fenstergröße — 1825 Punkte beim Schaustück, und als PNG
#: sind das 1,1 MB. Eine Galerie mit acht davon wäre neun Megabyte für eine
#: Seite, die jemand auf dem Telefon öffnet. 900 reicht für die doppelte
#: Auflösung einer 450 Punkte breiten Kachel, und WebP macht daraus ein
#: Zehntel.
WIDTH = 900

#: Von wo aus ein Teil gezeigt wird, wenn die Vorgabe sein Merkmal verdeckt.
#:
#: **Roberts Einwand vom 30.08.2026: „so bringen die haken aber nichts".** Der
#: Lochwandhalter stand in der Standardansicht von vorn, und seine SKADIS-Haken
#: sitzen hinten — ein Bild, das genau das nicht zeigt, wofür das Teil da ist.
#:
#: Die Vorgabe ``iso`` blickt von (1, -1, 0.8), also von vorn-rechts-oben. Was
#: hier steht, ist die Ausnahme davon, und jede Zeile nennt ihren Grund: Ein
#: Blickwinkel ohne Begründung ist beim nächsten Teil geraten.
VIEWS: dict[str, tuple[float, float, float]] = {
    # Von hinten, und **flach**: Die Einhänger sitzen auf der Rückwand und sind
    # der ganze Zweck des Teils — Robert am 30.08.2026: „so bringen die haken
    # aber nichts". Der erste Versuch stand bei 0,7 in der Höhe und sah dabei
    # in den offenen Kasten; dessen Innenwände zeigt die Anwendung rot
    # (``BACKFACE_COLOUR``, damit man beim Arbeiten merkt, dass man von innen
    # sieht), und ein halbrotes Bild erklärt in einer Galerie niemandem etwas.
    "lochwandhalter": (-0.9, -1.0, 0.3),
    # Flacher als die Vorgabe: Das Gewinde am Hals liest sich von der Seite,
    # von oben verschwindet es hinter dem Rand.
    "schraubdose": (1.0, -1.0, 0.35),
    # Ebenfalls flach, aus demselben Grund: Das Filmscharnier ist eine dünne
    # Stelle in der Wand und von oben ein Strich.
    "klappbox": (1.0, -0.8, 0.4),
}

#: Wie stark WebP verdichtet (0 bis 100).
#:
#: 82 ist der Punkt, an dem an einem Verlaufsschatten nichts mehr auffällt und
#: die Datei ein Zehntel des PNG wiegt. Höher kostet Bytes ohne sichtbaren
#: Gewinn, niedriger zeigt Ringe um die Kanten — und Kanten sind hier das Teil.
QUALITY = 82


def edge(widget: QWidget | None, origin: QPoint, side: str) -> int | None:
    """Wo ein Widget im Viewport-Bild liegt — in dessen eigenen Punkten.

    ``mapToGlobal`` und Differenz, nicht ``mapTo``: Der Weg von der Kartenspalte
    zum Viewport führt über zwei Hierarchien, und Qt rechnet ihn nicht so, wie
    es beim Lesen aussieht.
    """
    if widget is None or not widget.isVisible():
        return None
    corner = widget.mapToGlobal(QPoint(0, 0))
    if side == "right":
        return corner.x() - origin.x()
    if side == "left":
        return corner.x() - origin.x() + widget.width()
    return corner.y() - origin.y()


def crop_box(window: Any, view: Any) -> tuple[int, int, int]:
    """Der freie Bereich des Viewports: links, rechts, unten.

    Die Karten liegen als Overlay darüber. Sie zu verstecken nähme den Viewport
    mit — der gesuchte Träger hält beide.
    """
    origin = view.mapToGlobal(QPoint(0, 0))
    cards = window.object_tree.parentWidget()
    while cards is not None and cards.parentWidget() is not None and cards.width() < 150:
        cards = cards.parentWidget()
    left = edge(cards, origin, "left") or 0
    right = edge(window.right, origin, "right") or view.width()
    bottom = edge(window.tools, origin, "top") or view.height()
    return left, right, bottom


def shoot_part(window: Any, app: QApplication, stem: str) -> Path:
    """Ein geladenes Teil aufnehmen und unter ``galerie-<stem>.webp`` ablegen."""
    from make_figures import settle

    view = window.viewport
    # **Das Achsenkreuz gehört nicht ins Galeriebild.** In der Anwendung sagt
    # es, wo oben ist, und dafür ist es da. Auf einem Bild, das ein Teil zeigen
    # soll, steht es davor — bei der Schraubdose mitten im Gewinde.
    if view.renderer is not None:
        view.renderer.set_axes_marker(None)
    # **Und das Verschiebe-Gizmo, aus demselben Grund** — gefunden erst am
    # fertigen Seitenausschnitt: Auf dem Bild der Klappbox stand der blaue
    # Pfeil mitten im Teil, dazu der rote und der grüne Ring. Es erscheint,
    # sobald ein Objekt ausgewählt ist, und nach dem Öffnen einer Projektdatei
    # ist manchmal eines ausgewählt. In der Anwendung ist es die Handhabe zum
    # Ziehen; auf einem Galeriebild ist es Werkzeug im Schaufenster.
    view.set_gizmo(False)

    view.reset_camera()
    settle(app, 20)
    # **Erst die Richtung, dann einpassen.** Andersherum stünde das Teil nach
    # dem Schwenk wieder halb außerhalb: ``reset_camera`` rahmt für die Lage,
    # in der es gerufen wird.
    direction = VIEWS.get(stem)
    if direction is not None and view.renderer is not None:
        from app.ui.render.api import CameraPose

        view.renderer.set_camera_pose(CameraPose(direction, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)))
        settle(app, 10)
        view.reset_camera()
        settle(app, 20)
    view.zoom(ZOOMS.get(stem, ZOOM))
    settle(app, 30)

    screen = view.screen() or QApplication.primaryScreen()
    shot = screen.grabWindow(view.winId())
    left, right, bottom = crop_box(window, view)

    x0 = max(0, min(left + MARGIN, shot.width() - 100))
    x1 = max(x0 + 100, min(shot.width(), right - MARGIN))
    y1 = max(200, min(shot.height(), bottom - MARGIN))
    cut = shot.copy(x0, MARGIN, x1 - x0, y1 - MARGIN)
    # Glatt skaliert, nicht schnell: Ein Teil mit feinen Kanten — Gewinde,
    # Rändel, Rippen — verliert sie beim schnellen Verfahren.
    small = cut.toImage().scaledToWidth(WIDTH, Qt.TransformationMode.SmoothTransformation)

    TARGET.mkdir(parents=True, exist_ok=True)
    target = TARGET / f"galerie-{stem}.webp"
    if not small.save(str(target), "WEBP", QUALITY):
        raise SystemExit(f"{target} ließ sich nicht schreiben — kein leises Fertig")
    print(f"  {stem:22s} {small.width()}x{small.height()}  {target.stat().st_size // 1024} KB")
    return target


def main() -> int:
    """Jedes genannte Projekt aufnehmen; ohne Namen alle aus ``parts``."""
    from make_figures import await_result, prepared

    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    load_operations()
    app = QApplication.instance() or QApplication(sys.argv[:1])

    source = Path(__file__).resolve().parent.parent / "website" / "teile"
    wanted = sys.argv[1:] or [p.stem for p in sorted(source.glob("*.p3d"))]
    if not wanted:
        raise SystemExit(
            f"Keine Projekte in {source}. Lege sie dort ab oder nenne Namen auf der Kommandozeile."
        )

    print(f"{len(wanted)} Teile:")
    for stem in wanted:
        project = source / f"{stem}.p3d"
        if not project.is_file():
            raise SystemExit(f"Fehlt: {project}")
        # **Ein eigenes Fenster je Teil.** Ein zweites Projekt in dasselbe zu
        # laden geht, hinterlässt aber die Kamera des ersten und dessen
        # Auswahl; beides säße dann im Bild. Der Aufbau kostet Sekunden, ein
        # falsch stehendes Bild kostet den Durchgang.
        session = Session()
        window = prepared(MainWindow(session, UiSettings()), hidden=False)
        session.open_project(project)
        window._show_start_screen(False)
        if not await_result(app, session):
            raise SystemExit(f"{stem}: die Auswertung wurde nicht fertig")
        window.raise_()
        window.activateWindow()
        shoot_part(window, app, stem)
        window.close()
    print("\nFertig. Die Maße gehören in die <img>-Angaben der Seiten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
