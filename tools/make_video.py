"""Marketing-Videos aus der laufenden Anwendung aufnehmen.

    .venv\\Scripts\\python.exe tools/make_video.py

Dasselbe Verfahren wie ``make_figures.py``, nur greift es nicht ein Bild ab,
sondern dreißig je Sekunde. Der Unterschied zu einer Bildschirmaufnahme ist
wichtiger, als er klingt: hier wird **Bild für Bild** gerechnet und gegriffen,
nicht in Echtzeit mitgeschnitten. Eine Kamerafahrt läuft deshalb exakt so
schnell, wie sie soll — unabhängig davon, ob die Maschine gerade schwitzt.
Ein Mitschnitt bekommt bei einem schweren Modell Ruckler, die niemand mehr
herausschneidet.

Aus **einer** Aufnahme fallen beide Formate:

* quer, 1920x1080, das ganze Fenster — für YouTube
* hoch, 1080x1920, der Viewport freigestellt und beschriftet — für TikTok

Das Hochformat ist bewusst kein Zuschnitt des Querformats. Ein Fenster mit
Objektbaum links und Parameterleiste rechts ergibt hochkant einen Streifen
Bedienelemente um einen briefmarkengroßen Körper. Gezeigt wird deshalb der
Viewport allein, und der Platz darüber und darunter trägt die Aussage.

**Was hier schiefgeht, wenn man es anders macht** — dieselben drei Fallen wie
bei den Handbuchbildern, aus denselben Gründen (siehe ``make_figures.py``):

1. Nicht offscreen. ``QT_QPA_PLATFORM=offscreen`` hat auf dieser Maschine
   keine Schriften, und jede Beschriftung wird ein leeres Kästchen.
2. Das Fenster muss **sichtbar** sein. OpenGL zeichnet nicht in ein Fenster,
   das nie auf dem Bildschirm war — die Bildmitte bliebe schwarz, also
   ausgerechnet das Modell.
3. ``screen.grabWindow`` statt ``QWidget.grab``. Der Qt-Painter malt das
   Widget nach und weiß nichts von dem, was OpenGL in den Viewport gezeichnet
   hat.

ffmpeg wird extern aufgerufen und nicht mitgeliefert — dasselbe Muster wie bei
OpenSCAD und den Slicern, damit bleibt die Lizenzlage unberührt (Regel 15).
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Vor allem, was Qt anfasst: die echte Plattform, siehe Modulkopf.
os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PySide6.QtWidgets import QApplication, QWidget

from app.i18n import install_catalog, set_language
from app.i18n.catalog import read_catalog

#: Aufnahmegröße fürs Querformat. Nativ Full HD — der Bildschirm hier ist
#: breit genug, und alles, was skaliert werden muss, verliert an den
#: Beschriftungen zuerst.
WINDOW = (1920, 1080)

#: Aufnahmegröße fürs Hochformat.
#:
#: 1080 breit, damit die Zielbreite ohne Skalierung erreicht wird. Die Höhe
#: ist, was der Bildschirm hergibt — ein Fenster von 1920 Bildpunkten Höhe
#: passt auf keinen der beiden Schirme hier, und was nicht auf dem Schirm
#: steht, greift ``grabWindow`` auch nicht ab. Der Rest der Zielhöhe wird
#: nicht gestreckt, sondern beschriftet.
PORTRAIT = (1080, 1340)

#: Wie nah die Kamera im Hochformat steht, als Faktor auf den eingepassten
#: Abstand. Ohne das steht der Körper in der Bildmitte und lässt links und
#: rechts die Hälfte frei — auf einem Telefon ist er dann fingernagelgroß.
#:
#: Nicht tiefer als das: der eingepasste Abstand gilt für die **Diagonale** des
#: Körpers, und während der Umdrehung dreht sich seine breiteste Seite einmal
#: quer ins Bild. Bei 0,62 stand das Gehäuse in der Hälfte der Bilder über den
#: Rand hinaus.
PORTRAIT_ZOOM = 0.82

#: Bilder je Sekunde. Beide Plattformen nehmen 30 an, und jedes Bild mehr
#: kostet eine Rechnung.
FPS = 30

#: Welches Projekt gezeigt wird. Das Gehäuse trägt benannte Maße, vier
#: Bausteine und ein Prüfstück — es zeigt, was die Anwendung kann, und nicht,
#: dass sie ein Loch bohren kann.
EXAMPLE = "gehaeuse-mit-bausteinen.p3d"


@dataclass(frozen=True, slots=True)
class Shot:
    """Eine aufgenommene Einstellung: die Bilder und wo der Viewport lag."""

    frames: Path
    count: int
    viewport: tuple[int, int, int, int]


def settle(app: QApplication, rounds: int = 12) -> None:
    """Der Oberfläche Zeit geben, fertig zu werden, bevor abgedrückt wird."""
    for _round in range(rounds):
        app.processEvents()


def await_result(app: QApplication, session: object, seconds: float = 60.0) -> bool:
    """Warten, bis die Auswertung durch ist.

    Sie läuft in einem Arbeitsfaden (§15.6), also genügt kein Stapel
    ``processEvents``: ohne das Warten filmt das Werkzeug den Startbildschirm.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if getattr(session, "last_result", None) is not None:
            settle(app)
            return True
        time.sleep(0.05)
    return False


def release_viewport(window: Any) -> None:
    """Den OpenGL-Kontext freigeben, bevor das nächste Fenster kommt.

    ``close()`` allein tut das nicht — das ``QtInteractor`` bleibt am Fenster
    hängen, und mit ihm sein Renderfenster. Beim zweiten Durchgang kippt sonst
    der Orientierungswürfel quer über das Modell.
    """
    plotter = getattr(getattr(window, "viewport", None), "plotter", None)
    if plotter is None:
        return
    try:
        plotter.close()
    except Exception as problem:  # pragma: no cover - hängt am Treiber
        print(f"  (Viewport ließ sich nicht schließen: {problem})")
    window.viewport.plotter = None


def viewport_rect(window: QWidget) -> tuple[int, int, int, int]:
    """Wo die 3D-Zeichenfläche im Fenster liegt, in Bildpunkten der Aufnahme.

    Gebraucht fürs Hochformat: dort wird genau dieser Ausschnitt freigestellt.
    Die Werte von Hand auszumessen hielte genau so lange, bis jemand eine
    Leiste breiter macht.

    Gemessen wird der **Interactor**, nicht der Viewport um ihn herum. Der ist
    ein Container mit einem Layout, in dem außer der Zeichenfläche noch
    anderes liegen kann; sein Rechteck ist unten größer als das, was OpenGL
    bemalt. Genau diese Differenz stand im ersten Hochformat als schwarzer
    Streifen unter dem Modell — und sie sah aus wie ein Fehler beim Rendern,
    war aber einer beim Messen.
    """
    viewport = window.viewport  # type: ignore[attr-defined]
    target = getattr(getattr(viewport, "plotter", None), "interactor", None) or viewport
    corner = target.mapTo(window, target.rect().topLeft())
    size = target.size()
    return (corner.x(), corner.y(), size.width(), size.height())


def require_screen(app: QApplication) -> None:
    """Prüfen, ob beide Aufnahmegrößen auf den Bildschirm passen.

    ``grabWindow`` greift den Bildschirm ab. Was nicht darauf steht, kommt als
    schwarze Fläche zurück — lautlos, ohne Fehler, in jedem einzelnen Bild.
    Diese Prüfung steht hier, weil genau das drei Durchgänge lang wie ein
    Fehler beim Rendern aussah.
    """
    screen = app.primaryScreen()
    available = screen.availableGeometry()
    # Grob geschätzter Platz für Titelleiste und Rahmen. Genau geht erst, wenn
    # das Fenster steht, und dann ist es für eine Absage zu spät.
    decoration = 40
    for label, (width, height) in (("quer", WINDOW), ("hoch", PORTRAIT)):
        if width > available.width() or height + decoration > available.height():
            raise SystemExit(
                f"Die Aufnahme {label} braucht {width}x{height} Bildpunkte, der Bildschirm "
                f"bietet {available.width()}x{available.height() - decoration}.\n"
                f"Entweder auf dem größeren Schirm laufen lassen, die Anzeigeskalierung "
                f"herabsetzen, oder {'WINDOW' if label == 'quer' else 'PORTRAIT'} im Kopf "
                f"dieser Datei kleiner setzen — das Hochformat wird ohnehin nicht "
                f"gestreckt, sondern beschriftet."
            )


def show_panels(window: Any, visible: bool) -> None:
    """Die drei schwebenden Zonen ein- oder ausblenden.

    Fürs Hochformat müssen sie weg. Sie liegen **über** dem Viewport, nicht
    daneben (``OverlayHost``) — ein Ausschnitt der Bildmitte enthält sie
    deshalb mit, und das Modell schrumpft auf den Rest. Genau so sah der erste
    Versuch aus: eine Briefmarke zwischen zwei Leisten, auf einem Telefon
    unlesbar.
    """
    overlay = getattr(window, "overlay", None)
    if overlay is None:
        return
    for name in ("left", "right", "bottom"):
        zone = getattr(overlay, name, None)
        if zone is not None:
            zone.setVisible(visible)
    tools = getattr(window, "tools", None)
    if tools is not None:
        tools.setVisible(visible)


def hide_orientation_widget(window: Any) -> None:
    """Den Orientierungswürfel abschalten.

    In der Anwendung ist er richtig — er sagt, wo oben ist, und man kann ihn
    anfassen. In einem Werbevideo ist er ein Bedienelement, das niemand
    bedient, und er sitzt genau in der Ecke, in der auf beiden Plattformen die
    Oberfläche des Abspielers liegt.
    """
    plotter = getattr(getattr(window, "viewport", None), "plotter", None)
    # Seit pyvista 0.46 hängen die Widgets an ``plotter.widgets``; der alte
    # Weg lebt noch, meldet sich aber mit einer Verfallswarnung.
    holder = getattr(plotter, "widgets", plotter)
    for widget in getattr(holder, "camera_widgets", ()):
        try:
            widget.Off()
        except Exception as problem:  # pragma: no cover - hängt am Treiber
            print(f"  (Orientierungswürfel blieb an: {problem})")


def settle_resize(window: Any, app: QApplication, seconds: float = 1.5) -> None:
    """Nach einer Größenänderung warten — und das Fenster auf den Schirm holen.

    Die neue Fenstergröße kommt vom Fenstersystem asynchron zurück, und erst
    danach verteilt Qt sie im Layout. Wer sofort misst, bekommt die Maße von
    vorher.

    Wichtiger noch ist das Verschieben. ``grabWindow`` greift **den
    Bildschirm** ab, nicht das Fenster: was unten aus dem sichtbaren Bereich
    ragt, kommt als Schwarz zurück. Ein Fenster, das quer zentriert stand und
    dann auf Hochformat wuchs, hing genau so unten heraus — die letzten 186
    Bildpunkte jedes Bildes waren nie etwas anderes als der Rand des
    Schreibtischs. Es sah aus wie ein Fehler beim Rendern, war aber einer beim
    Hinstellen.
    """
    screen = window.screen() or QApplication.primaryScreen()
    available = screen.availableGeometry()
    frame_extra = window.frameGeometry().height() - window.height()
    top = available.y() + max(0, frame_extra)
    left = available.x() + max(0, (available.width() - window.width()) // 2)
    window.move(left, top)
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    plotter = getattr(getattr(window, "viewport", None), "plotter", None)
    if plotter is not None:
        plotter.render()
    settle(app, 30)


def orbit(
    window: QWidget,
    app: QApplication,
    frames: Path,
    seconds: float = 8.0,
    zoom: float = 1.0,
) -> Shot:
    """Eine volle Umdrehung um das Modell, Bild für Bild.

    Die Kamera wird nicht gedreht, sondern gesetzt: Position auf einer
    Kreisbahn um den Blickpunkt, Höhe unverändert. Das ist deterministisch —
    dieselbe Aufnahme ergibt dieselben Bilder, auch auf einer anderen
    Maschine — und kommt ohne die Eigenheiten von ``camera.azimuth`` aus, das
    relativ zur aktuellen Stellung arbeitet und sich über hundert Bilder
    aufsummiert.
    """
    frames.mkdir(parents=True, exist_ok=True)
    viewport = window.viewport  # type: ignore[attr-defined]
    plotter = viewport.plotter
    screen = window.screen() or QApplication.primaryScreen()

    viewport.reset_camera()
    settle(app, 20)

    camera = plotter.camera
    focal = tuple(float(value) for value in camera.focal_point)
    position = tuple(float(value) for value in camera.position)
    offset_x, offset_y = position[0] - focal[0], position[1] - focal[1]
    # Der ganze Vektor wird skaliert, nicht nur seine Länge in der Ebene:
    # sonst rückt die Kamera näher, bleibt aber auf ihrer Höhe stehen, und aus
    # dem Dreiviertelblick wird mit jedem Schritt eine Draufsicht.
    radius = math.hypot(offset_x, offset_y) * zoom
    height = focal[2] + (position[2] - focal[2]) * zoom
    start = math.atan2(offset_y, offset_x)

    total = int(seconds * FPS)
    for index in range(total):
        angle = start + 2.0 * math.pi * index / total
        camera.position = (
            focal[0] + radius * math.cos(angle),
            focal[1] + radius * math.sin(angle),
            height,
        )
        # Die Schatten hängen an der Blickrichtung (§18.6). Ohne diese Zeile
        # steht das Licht still, während sich das Teil dreht — es sieht aus,
        # als klebte der Schatten am Boden fest.
        redraw = getattr(viewport, "_redraw_shadows", None)
        if callable(redraw):
            redraw()
        plotter.render()
        app.processEvents()
        shot = screen.grabWindow(window.winId())
        shot.save(str(frames / f"{index:05d}.png"))

    print(f"  {total} Bilder aufgenommen")
    return Shot(frames=frames, count=total, viewport=viewport_rect(window))


def encode_landscape(shot: Shot, target: Path) -> None:
    """Das Querformat: die Bilder, wie sie sind."""
    run_ffmpeg(
        [
            "-framerate",
            str(FPS),
            "-i",
            str(shot.frames / "%05d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "18",
            "-preset",
            "slow",
            str(target),
        ]
    )
    print(f"  quer  → {target.name}")


def encode_portrait(shot: Shot, target: Path, headline: str, sub: str) -> None:
    """Das Hochformat: Viewport freigestellt, Text darüber und darunter.

    Der Ausschnitt kommt aus der Aufnahme, nicht aus einer Tabelle — wo der
    Viewport liegt, hat das Fenster selbst gesagt.
    """
    left, top, width, height = shot.viewport
    # Auf 1080 Breite bringen, dann in die 1920 Höhe setzen — etwas unterhalb
    # der Mitte, weil oben zwei Zeilen stehen und unten eine.
    scaled_height = int(round(height * 1080 / width / 2) * 2)
    pad_top = max(0, min(1920 - scaled_height, 380))
    font = font_file()
    # Die Schrift sitzt an festen Stellen des **Zielbildes**, nicht an
    # Bruchteilen des Randes: sonst wandern Titel und Marke bei jeder anderen
    # Aufnahmehöhe mit, und die Reihe der Videos steht nicht mehr bündig.
    chain = (
        f"crop={width}:{height}:{left}:{top},"
        f"scale=1080:{scaled_height}:flags=lanczos,"
        f"pad=1080:1920:0:{pad_top}:color=0x14161a,"
        f"drawtext=fontfile='{font}':text='{headline}':fontcolor=white:fontsize=72:"
        f"x=(w-text_w)/2:y=150,"
        f"drawtext=fontfile='{font}':text='{sub}':fontcolor=0x9aa4b2:fontsize=40:"
        f"x=(w-text_w)/2:y=258,"
        f"drawtext=fontfile='{font}':text='solidon3d.de':fontcolor=0x6ea8fe:fontsize=46:"
        f"x=(w-text_w)/2:y=1750"
    )
    run_ffmpeg(
        [
            "-framerate",
            str(FPS),
            "-i",
            str(shot.frames / "%05d.png"),
            "-vf",
            chain,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "18",
            "-preset",
            "slow",
            str(target),
        ]
    )
    print(f"  hoch  → {target.name}")


def font_file() -> str:
    """Eine Schrift, die ffmpeg laden kann — mit Umlauten.

    ``drawtext`` bringt keine mit. Ohne Pfad bricht der Aufruf ab, und mit der
    falschen fehlen genau die Zeichen, die in jedem zweiten deutschen Satz
    stehen.
    """
    for candidate in (
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeui.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf",
    ):
        if candidate.is_file():
            # ffmpeg liest den Filtergraphen selbst — Doppelpunkt und
            # Backslash im Pfad müssen ihm aus dem Weg.
            return str(candidate).replace("\\", "/").replace(":", "\\:")
    raise SystemExit("Keine Schrift für die Beschriftung gefunden")


def run_ffmpeg(arguments: list[str]) -> None:
    """ffmpeg aufrufen und bei einem Fehler sagen, woran es lag."""
    binary = shutil.which("ffmpeg")
    if binary is None:
        raise SystemExit(
            "ffmpeg fehlt. Installieren mit: winget install Gyan.FFmpeg — "
            "danach eine neue Eingabeaufforderung öffnen."
        )
    finished = subprocess.run(
        [binary, "-y", "-loglevel", "error", *arguments],
        capture_output=True,
        text=True,
    )
    if finished.returncode != 0:
        raise SystemExit(f"ffmpeg brach ab:\n{finished.stderr.strip()}")


def main() -> int:
    from app.core import examples
    from app.core.bootstrap import load_operations
    from app.ui.app import install_qt_translations
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from app.ui.theme import apply_theme

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd() / "video-test"
    out.mkdir(parents=True, exist_ok=True)
    frames = out / "frames"
    if frames.exists():
        shutil.rmtree(frames)

    load_operations()
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    require_screen(app)
    apply_theme(app, "dark")
    install_catalog("de", read_catalog("de"))
    set_language("de")
    install_qt_translations(app, "de")

    session = Session()
    window = MainWindow(session, UiSettings())
    window.resize(*WINDOW)
    window.show()

    project = examples.directory() / EXAMPLE
    if not project.is_file():
        raise SystemExit(f"Beispielprojekt fehlt: {project}")
    session.open_project(project)
    window._show_start_screen(False)
    if not await_result(app, session):
        raise SystemExit("Die Auswertung wurde nicht fertig — kein Video")
    window.raise_()
    window.activateWindow()
    settle(app, 60)

    # Zwei Durchgänge an **einem** Fenster. Ein zweites zu bauen wäre der
    # naheliegende Weg und der falsche: der OpenGL-Kontext des ersten bliebe
    # am ``QtInteractor`` hängen, und der Orientierungswürfel läge im zweiten
    # Durchgang quer über dem Modell (siehe ``release_viewport``).
    print("Aufnahme quer:")
    landscape = orbit(window, app, frames / "landscape")

    print("Aufnahme hoch:")
    show_panels(window, False)
    hide_orientation_widget(window)
    window.resize(*PORTRAIT)
    settle_resize(window, app)
    portrait = orbit(window, app, frames / "portrait", zoom=PORTRAIT_ZOOM)
    show_panels(window, True)

    print("Kodierung:")
    encode_landscape(landscape, out / "solidon3d-quer-1080p.mp4")
    encode_portrait(
        portrait,
        out / "solidon3d-hoch-1080x1920.mp4",
        headline="Vom Chat zum Bauteil",
        sub="Parametrisch. Offline. Ohne CAD-Studium.",
    )

    window.close()
    release_viewport(window)
    print(f"\nFertig: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
