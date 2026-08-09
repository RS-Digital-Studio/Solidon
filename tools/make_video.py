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
from collections.abc import Callable
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

#: Was eine Szene je Bild tut: Nummer und Gesamtzahl herein, Welt eingestellt.
StepFn = Callable[[int, int], None]

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

#: Die eigene Umgebung für die Sprachausgabe.
#:
#: **Nicht die Projektumgebung.** Chatterbox bringt PyTorch mit; das in der
#: venv zu haben, aus der PyInstaller das Paket baut, wäre eine
#: Abhängigkeitskette, die mit Solidon nichts zu tun hat. Aufgerufen wird es
#: deshalb wie ffmpeg — als fremdes Programm, siehe
#: ``tools/speak_chatterbox.py``.
VOICE_PYTHON = Path(__file__).resolve().parent.parent / ".venv-tts" / "Scripts" / "python.exe"
VOICE_SCRIPT = Path(__file__).resolve().parent / "speak_chatterbox.py"

#: Das Drehbuch: je Szene ein Satz, und der Satz bestimmt die Länge.
#:
#: Erzählt wird das, was diese Anwendung von einem Netzbetrachter
#: unterscheidet — ein Maß ändern, und Bohrungen, Bausteine und Deckel wandern
#: mit. **Nicht der Chat.** Der lokale Agent brauchte im Versuch 75 Sekunden
#: für eine Antwort, lief zweimal in die Zeitgrenze und erzeugte dabei keine
#: einzige Operation; ein Video, das „Satz eintippen, Bauteil herausbekommen"
#: verspricht, wäre ein Versprechen auf etwas, das die Installation hier nicht
#: einlöst.
STORYBOARD: dict[str, tuple[tuple[str, str], ...]] = {
    "de": (
        (
            "intro",
            "Das ist ein Gehäuse aus Solidon. Siebzig Millimeter breit, "
            "mit Mutternfallen, Einpressbuchsen und einer Kabeldurchführung.",
        ),
        (
            "parameters",
            "Seine Maße stehen nicht im Modell. Sie sind benannte Parameter.",
        ),
        (
            "morph",
            "Wird die Breite größer, wandern Bohrungen, Bausteine und Deckel mit. "
            "Jedes Bild ist neu gerechnet, nicht gedehnt.",
        ),
        (
            "outro",
            "Solidon. Parametrisch konstruieren, offline, ohne CAD-Studium.",
        ),
    ),
    "en": (
        (
            "intro",
            "This is an enclosure built in Solidon. Seventy millimetres wide, "
            "with nut traps, heat-set inserts and a cable gland.",
        ),
        (
            "parameters",
            "Its dimensions are not baked into the model. They are named parameters.",
        ),
        (
            "morph",
            "Widen it, and the holes, the inserts and the lid all follow. "
            "Every frame is recomputed, not stretched.",
        ),
        (
            "outro",
            "Solidon. Parametric design, offline, no CAD degree required.",
        ),
    ),
}

#: Von wo nach wo die Breite läuft, und über wie viele Bilder.
#:
#: Der Wert wird bei jedem Schritt wirklich gesetzt und die Szene wirklich neu
#: gerechnet — gemessene 0,08 Sekunden je Durchgang, deshalb ist das als
#: Bewegung überhaupt zeigbar. Gedehnt würde man sofort sehen: die Bohrungen
#: würden oval.
MORPH = (70.0, 96.0)

#: Welcher Parameter dabei läuft. Er heißt im Beispielprojekt deutsch, weil
#: Parameternamen dem Nutzer gehören und nicht dem Code.
MORPH_PARAMETER = "breite"

#: Wie er in der Einblendung heißt.
#:
#: Übersetzt, obwohl der Parameter selbst deutsch heißt: im englischen
#: Hochformat stand sonst „breite = 83 mm" unter einer Überschrift, die
#: „Change one dimension" sagt. Die Zahl ist echt, nur ihre Beschriftung ist
#: für den Zuschauer geschrieben — und der liest im englischen Video Englisch.
#:
#: Die Parameterleiste im **Querformat** bleibt davon unberührt; dort steht
#: weiter, was im Beispielprojekt steht. Das ist kein Fehler dieses Werkzeugs,
#: sondern der Umstand, dass es nur ein deutsches Beispielprojekt gibt.
READOUT_LABEL = {"de": "breite", "en": "width"}

#: Wörter, die das Modell anders geschrieben bekommt, als sie geschrieben
#: werden — **leer, und das mit Absicht.**
#:
#: Chatterbox ist mehrsprachig mit englischem Schwerpunkt, und ein leichter
#: englischer Einschlag bleibt hörbar. Der naheliegende Gegenzug war, dem
#: Modell die schwierigen Wörter zu buchstabieren („Solidonn", „Einpress-
#: Buchsen"). Im Gegenhören war kein Unterschied festzustellen; der Eintrag
#: ist deshalb wieder heraus, statt als gelöst zu gelten, was nicht gelöst
#: ist.
#:
#: Der Haken bleibt: kommt einmal ein Wort erkennbar falsch, steht hier die
#: Stelle, an der man es richtigstellt — nur für das Modell, nie für den
#: Zuschauer.
PRONUNCIATION: dict[str, str] = {}

#: Die feste Beschriftung des Hochformats, je Sprache.
#:
#: **Nicht über** ``tr()``: der Textsammler liest ``app/``, und was hier steht,
#: käme nie in den Katalog — ``translate()`` fiele auf die Message-ID zurück,
#: also auf Deutsch. Im englischen Video stünde dann eine deutsche Überschrift.
PORTRAIT_TEXT = {
    "de": ("Ein Maß ändern", "Alles andere wandert mit."),
    "en": ("Change one dimension", "Everything else follows."),
}

#: Pause hinter jedem Satz, in Sekunden.
#:
#: Sie steht im Ton **und** im Bild, sonst wechselt die Szene, während noch
#: gesprochen wird. Ein Satz, der auf dem letzten Wort abgeschnitten wird,
#: klingt nach Fehler, auch wenn nichts fehlt.
SCENE_TAIL = 0.7

#: Was gesprochen wird, wenn das Werkzeug ohne Drehbuch läuft (``--kurz``).
SCRIPT = {
    "de": (
        "Solidon baut druckbare Bauteile aus einem Satz. Parametrisch, offline, ohne CAD-Studium."
    ),
    "en": (
        "Solidon turns a sentence into a printable part. "
        "Parametric, offline, no CAD degree required."
    ),
}

#: Ziellautheit in LUFS.
#:
#: **Nicht -14.** Das ist die Schwelle, ab der beide Plattformen absenken —
#: kein Sollwert, den man treffen müsste. Gemessen erreicht diese Stimme sie
#: nicht, ohne dass die Dynamik dabei draufgeht: bei einer Spitzengrenze von
#: -1,5 dBTP landete jede Kompressionsstufe zwischen -15,6 und -16,8 LUFS,
#: und die Spitze lag jedes Mal exakt auf der Grenze. Nicht die Kompression
#: war zu schwach, die Grenze war bindend.
#:
#: Ziellautheit in LUFS — das **Ziel**, nicht das Ergebnis.
#:
#: Erreicht wird es nicht, und das ist Absicht. Bei einer Spitzengrenze von
#: -1,5 dBTP landet diese Stimme bei rund -16 LUFS, egal wie fest man
#: komprimiert; die Spitze liegt jedes Mal exakt auf der Grenze, nicht die
#: Kompression ist zu schwach. Für ein Sprachvideo ist -16 ohnehin der
#: übliche Ort, und -14 ist die Schwelle, ab der die Plattformen absenken —
#: kein Sollwert.
#:
#: Stehen bleibt die -14 trotzdem, weil der Abstand dorthin das dynamische
#: Nachregeln von ``loudnorm`` auslöst (siehe :func:`polish`). Wer hier -16
#: einträgt, bekommt eine Stimme, die die Zahl trifft und dumpfer klingt.
LOUDNESS = -14.0

#: Die Kette, die aus der Sprachausgabe einen Sendeton macht.
#:
#: Gemessen an der Verteilung der Klangenergie bringt sie die Präsenz (2 bis
#: 6 kHz) von 1,4 auf 5,1 Prozent und die Brillanz (6 bis 11 kHz) von 0,6 auf
#: 4,7 — die beiden Bänder, an denen Verständlichkeit hängt. Roh klingt piper
#: dumpf, weil dort fast nichts liegt.
#:
#: **Oberhalb von 11 kHz ändert das nichts**, und keine Einstellung tut das:
#: piper liefert 22,05 kHz, damit ist bei der halben Abtastrate Schluss. Der
#: ``aexciter`` erfindet Obertöne unterhalb dieser Grenze, nicht darüber.
#:
#: Die Reihenfolge ist nicht beliebig: ``aresample`` steht **vor** dem
#: Exciter, damit der Platz für Obertöne oberhalb der Quellrate hat.
#:
#: Die Werte gelten für Chatterbox und **nicht mehr für piper**. Die alte
#: Kette musste ein dumpfes 22-kHz-Signal von 0,6 Prozent Präsenz hochziehen;
#: Chatterbox liefert 4,5 Prozent bei 24 kHz. Dieselbe Anhebung darübergelegt
#: ergab 8,7 Prozent — anderthalbmal so viel wie das, was bei piper gut klang,
#: und in dem Bereich wird eine Stimme scharf und zischend.
#:
#: Deshalb: keine Präsenzanhebung mehr bei 2,8 kHz, die Absenkung bei 200 Hz
#: nur noch halb so tief (Chatterbox hat 39 statt 64 Prozent Fundament), und
#: der Exciter trägt die Brillanz allein. Er ist der einzige Regler, der sie
#: bewegt, und bei 3,0 liegen Präsenz und Brillanz auf rund 6 und 3 Prozent.
#:
#: Die Lautheit ist absichtlich **nicht** dabei — sie hängt hinten an
#: (:func:`polish`).
POLISH_FILTERS = (
    "aresample=48000,"
    "highpass=f=75,"
    "equalizer=f=200:t=q:w=1.2:g=-1.5,"
    "deesser=i=0.45,"
    "aexciter=amount=3.0:drive=6:freq=6500:ceil=16000:blend=0,"
    "acompressor=threshold=-18dB:ratio=3:attack=8:release=120:makeup=1.5"
)


@dataclass(frozen=True, slots=True)
class Shot:
    """Eine aufgenommene Einstellung: die Bilder und wo der Viewport lag."""

    frames: Path
    count: int
    viewport: tuple[int, int, int, int]
    #: Je Bild der Wert, der darin stand — leer, wo nichts läuft.
    #:
    #: Gebraucht fürs Hochformat: dort sind die Bedienzonen ausgeblendet, also
    #: ist die Parameterleiste nicht im Bild. Eine Szene, die von benannten
    #: Maßen spricht und dabei nur einen Körper zeigt, behauptet etwas, das der
    #: Zuschauer nicht sehen kann.
    readout: tuple[str, ...] = ()


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


def speak(text: str, language: str, target: Path) -> float:
    """Den Satz sprechen lassen und sagen, wie lange er dauert.

    Der Rückgabewert ist der Grund, warum das **vor** der Aufnahme läuft: die
    Länge des Videos richtet sich nach der Stimme, nicht die Stimme nach einer
    geratenen Länge. Wer es andersherum macht, hat am Ende einen Satz, der
    mitten im Wort abgeschnitten wird, oder vier Sekunden, in denen sich ein
    Modell schweigend weiterdreht.
    """
    if not VOICE_PYTHON.is_file():
        raise SystemExit(
            f"Die Umgebung für die Sprachausgabe fehlt: {VOICE_PYTHON}\n"
            f"Anlegen mit: python -m venv .venv-tts && "
            f'.venv-tts\\Scripts\\python.exe -m pip install chatterbox-tts "setuptools<81"\n'
            f"Das setuptools ist kein Beiwerk: das Wasserzeichen-Modul von "
            f"Chatterbox importiert pkg_resources, und das ist ab 81 nicht mehr dabei."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    finished = subprocess.run(
        [str(VOICE_PYTHON), str(VOICE_SCRIPT), str(target), language, spoken_form(text)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if finished.returncode != 0:
        raise SystemExit(f"Die Sprachausgabe brach ab:\n{finished.stderr.strip()}")
    return audio_duration(target)


def spoken_form(text: str) -> str:
    """Was das Modell liest — nicht, was der Zuschauer liest.

    Chatterbox ist mehrsprachig mit englischem Schwerpunkt, und das hört man
    an einzelnen Wörtern. „Solidon" liest es englisch; die Doppelkonsonante
    hält den Vokal kurz und rückt es zurück ins Deutsche. Der Zuschauer
    bekommt diese Schreibweise nie zu sehen — sie steht ausschließlich in der
    Eingabe an das Modell.
    """
    for written, spoken in PRONUNCIATION.items():
        text = text.replace(written, spoken)
    return text


def polish(source: Path, target: Path) -> None:
    """Aus der rohen Sprachausgabe die fertige Tonspur machen.

    **Einmal für beide Videos**, nicht je Video einmal. ``loudnorm`` ist keine
    reine Funktion des Eingangs — es misst und regelt —, und zweimal gerechnet
    ergibt zweimal leicht anderes. Quer und hoch sollen denselben Ton haben,
    nicht zwei ähnliche.

    ``loudnorm`` läuft hier **im Einzeldurchlauf und bewusst nicht in zwei
    Durchgängen.** Das sieht nach der schlechteren Wahl aus und ist die
    richtige: ohne vorher gemessene Werte regelt der Filter dynamisch, und
    dieses Nachregeln ist Teil des Klangs, der ausgewählt wurde. Der
    Zwei-Durchlauf mit ``linear=true`` skaliert bloß — er trifft die
    Ziellautheit genauer und drückt dabei die Brillanz von 4,7 auf 2,5
    Prozent. Die genauere Zahl war das dumpfere Ergebnis.

    Das Ziel bleibt aus demselben Grund bei :data:`LOUDNESS`, obwohl es nicht
    erreicht wird: der Abstand dorthin ist es, der das Nachregeln auslöst.
    Herauskommen rund -16 LUFS, und das ist für ein Sprachvideo genau richtig.
    """
    run_ffmpeg(
        [
            "-i",
            str(source),
            "-af",
            f"{POLISH_FILTERS},loudnorm=I={LOUDNESS}:TP=-1.5:LRA=11,aresample=48000",
            str(target),
        ]
    )


def speak_storyboard(language: str, out: Path) -> list[tuple[str, Path, float]]:
    """Jede Szene einmal sprechen und sagen, wie lange sie dauert.

    Vor jeder Aufnahme, aus demselben Grund wie beim einzelnen Satz: die
    Sprache bestimmt die Länge der Szene, nicht eine geratene Sekundenzahl.
    """
    spoken: list[tuple[str, Path, float]] = []
    for key, text in STORYBOARD[language]:
        raw = out / "audio" / f"{key}-{language}-roh.wav"
        ready = out / "audio" / f"{key}-{language}.wav"
        stamp = ready.with_suffix(".txt")
        # Was schon gesprochen ist, wird nicht neu gesprochen.
        #
        # Das spart nicht nur Zeit — es macht die Tonspur überhaupt erst
        # wiederholbar. piper hat keinen Startwert und würfelt bei jedem Lauf
        # neu; zwei Aufnahmen desselben Satzes klingen messbar verschieden.
        # Wer nach einer Bildkorrektur neu rendert, bekäme sonst nebenbei eine
        # andere Stimme.
        cached = stamp.is_file() and stamp.read_text(encoding="utf-8") == text
        if cached and ready.is_file():
            print(f"  {key:12s} {audio_duration(ready) + SCENE_TAIL:5.1f} s (unverändert)")
        else:
            speak(text, language, raw)
            polish(raw, ready)
            stamp.write_text(text, encoding="utf-8")
            print(f"  {key:12s} {audio_duration(ready) + SCENE_TAIL:5.1f} s")
        spoken.append((key, ready, audio_duration(ready) + SCENE_TAIL))
    return spoken


def join_audio(pieces: list[tuple[str, Path, float]], target: Path) -> None:
    """Die Tonspuren der Szenen hintereinanderlegen.

    Jede bekommt hinten :data:`SCENE_TAIL` Sekunden Stille — dieselbe Pause,
    die auch im Bild steht. Ohne sie stößt der nächste Satz an den letzten, und
    die Szene wechselt genau dann, wenn noch gesprochen wird.
    """
    listing = target.parent / "tonfolge.txt"
    lines = []
    for index, (key, path, seconds) in enumerate(pieces):
        padded = path.parent / f"{index:02d}-{key}-mit-pause.wav"
        run_ffmpeg(
            [
                "-i",
                str(path),
                "-af",
                f"apad=pad_dur={SCENE_TAIL}",
                "-t",
                f"{seconds:.3f}",
                str(padded),
            ]
        )
        lines.append(f"file '{padded.as_posix()}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(target)])


def audio_duration(path: Path) -> float:
    """Wie lang eine Tondatei ist, in Sekunden."""
    binary = shutil.which("ffprobe")
    if binary is None:
        raise SystemExit("ffprobe fehlt — es kommt zusammen mit ffmpeg.")
    finished = subprocess.run(
        [
            binary,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if finished.returncode != 0:
        raise SystemExit(f"ffprobe brach ab:\n{finished.stderr.strip()}")
    return float(finished.stdout.strip())


def audio_arguments(audio: Path | None) -> list[str]:
    """Die Tonspur anhängen, auf Sendelautheit gebracht.

    ``loudnorm`` bringt sie auf :data:`LOUDNESS`, das Umtasten auf 48 kHz
    stereo ist das, was beide Plattformen erwarten. piper liefert 22 kHz mono
    mit Spitzen bis an die Aussteuerungsgrenze — brauchbar, aber roh. Wer es
    so hochlädt, bekommt es normalisiert zurück, und zwar ohne Rücksicht auf
    die Dynamik, die die Stimme trägt.
    """
    if audio is None:
        return []
    return [
        "-i",
        str(audio),
        # ``apad`` hängt Stille an, bis das Bild fertig ist, und ``-shortest``
        # schneidet dann dort — nicht am Ton.
        #
        # **Ohne das Auffüllen macht ``-shortest`` das Gegenteil von dem, was
        # hier gebraucht wird:** es kürzt auf die kürzeste Spur, und das ist
        # der Ton. Der Nachlauf, der verhindern soll, dass das Bild auf der
        # letzten Silbe endet, war damit exakt wieder abgeschnitten — aus 6,6
        # Sekunden wurden 5,4.
        "-af",
        "apad",
        "-c:a",
        "aac",
        "-b:a",
        "256k",
        # Der Encoder wirft oberhalb seiner Trennfrequenz alles weg, und seine
        # Vorgabe liegt unter dem, was der Exciter erzeugt hat. Bei 192 kbit/s
        # und Vorgabe kam die Brillanz mit 2,8 statt 4,7 Prozent im Video an —
        # ein Teil der Politur wurde also erst aufgetragen und dann wieder
        # abgeschliffen.
        "-cutoff",
        "18000",
        "-ac",
        "2",
        "-shortest",
    ]


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


def record(
    window: QWidget,
    app: QApplication,
    frames: Path,
    start: int,
    count: int,
    step: Callable[[int, int], None],
) -> int:
    """``count`` Bilder aufnehmen und dabei je Bild ``step`` aufrufen.

    Der gemeinsame Kern aller Szenen. ``step`` bekommt Nummer und Gesamtzahl
    und stellt die Welt für dieses eine Bild ein — Kamera, Parameter, was auch
    immer die Szene bewegt. Zurück kommt die nächste freie Bildnummer, damit
    die Szenen fortlaufend in **einen** Ordner schreiben und ffmpeg am Ende
    einen einzigen Aufruf braucht.
    """
    frames.mkdir(parents=True, exist_ok=True)
    screen = window.screen() or QApplication.primaryScreen()
    for index in range(count):
        step(index, count)
        app.processEvents()
        window.screen()
        screen.grabWindow(window.winId()).save(str(frames / f"{start + index:05d}.png"))
    return start + count


def orbit_step(window: QWidget, app: QApplication, zoom: float, turns: float) -> StepFn:
    """Eine Kreisbahn um den Blickpunkt, als Schrittfunktion für :func:`record`.

    Dieselbe Rechnung wie in :func:`orbit`, nur portionsweise: die Kamera wird
    gesetzt statt gedreht, damit sich über hundert Bilder nichts aufsummiert.
    """
    viewport = window.viewport  # type: ignore[attr-defined]
    plotter = viewport.plotter
    viewport.reset_camera()
    settle(app, 20)
    camera = plotter.camera
    focal = tuple(float(value) for value in camera.focal_point)
    position = tuple(float(value) for value in camera.position)
    offset_x, offset_y = position[0] - focal[0], position[1] - focal[1]
    radius = math.hypot(offset_x, offset_y) * zoom
    height = focal[2] + (position[2] - focal[2]) * zoom
    start_angle = math.atan2(offset_y, offset_x)

    def step(index: int, total: int) -> None:
        angle = start_angle + 2.0 * math.pi * turns * index / max(1, total)
        camera.position = (
            focal[0] + radius * math.cos(angle),
            focal[1] + radius * math.sin(angle),
            height,
        )
        redraw = getattr(viewport, "_redraw_shadows", None)
        if callable(redraw):
            redraw()
        plotter.render()

    return step


def morph_step(
    window: QWidget,
    app: QApplication,
    session: Any,
    name: str,
    span: tuple[float, float],
    readout: list[str] | None = None,
    label: str = "",
) -> StepFn:
    """Einen Parameter über die Szene laufen lassen — und wirklich rechnen.

    Der Wert wird gesetzt, das Dokument neu ausgewertet und erst dann das Bild
    genommen. **Kein Dehnen**: eine skalierte Aufnahme würde man an den
    Bohrungen sofort erkennen, die dabei oval werden. Gemessene 0,08 Sekunden
    je Durchgang machen das als Bewegung überhaupt erst möglich.

    Ausgewertet wird synchron über ``evaluate_now`` und nicht über den
    Arbeitsfaden: bei dreißig Bildern in der Sekunde wäre sonst jedes zweite
    aufgenommen, bevor die Szene fertig gerechnet ist. Der Parameter wandert
    dabei direkt ins Dokument statt über ``change_parameter``, weil jeder
    Zwischenwert sonst eine eigene Transaktion wäre — der Verlauf stünde am
    Ende der Szene mit hundert Einträgen da, die niemand je zurücknehmen will.
    Gezeigt wird dasselbe, was beim Drehen am Wertfeld zu sehen ist.
    """
    import dataclasses

    document = session.project.document
    low, high = span
    viewport = window.viewport  # type: ignore[attr-defined]
    plotter = viewport.plotter
    camera = plotter.camera
    focal = tuple(float(value) for value in camera.focal_point)
    start = tuple(float(value) for value in camera.position)

    def step(index: int, total: int) -> None:
        # Sinus statt linear: die Bewegung beginnt und endet ruhig, statt
        # anzuspringen und abrupt zu stehen.
        share = 0.5 - 0.5 * math.cos(math.pi * index / max(1, total - 1))
        value = low + (high - low) * share
        parameters = document.parameters
        existing = parameters.get(name)
        if existing is None:
            return
        parameters[name] = dataclasses.replace(existing, value=value)
        session.projectChanged.emit()
        session.evaluate_now()
        if readout is not None:
            # Auf ganze Millimeter: eine Zahl mit zwei Nachkommastellen, die
            # dreißigmal in der Sekunde springt, ist im Video nicht zu lesen.
            readout.append(f"{label or name} = {value:.0f} mm")
        # Die Kamera weicht mit, sonst wächst das Teil aus dem Bild.
        #
        # **Nicht über ``reset_camera``**: das passt bei jedem Bild neu ein und
        # springt dabei, weil der Hüllquader sich sprunghaft ändert, sobald ein
        # Baustein umzieht. Ein glatter Faktor auf den Abstand hält das Teil im
        # Bild und die Bewegung ruhig. Im Hochformat ist es der Unterschied
        # zwischen einem Gehäuse und einem angeschnittenen Gehäuse.
        away = 1.0 + (value / low - 1.0) * 0.8
        camera.position = (
            focal[0] + (start[0] - focal[0]) * away,
            focal[1] + (start[1] - focal[1]) * away,
            focal[2] + (start[2] - focal[2]) * away,
        )
        redraw = getattr(viewport, "_redraw_shadows", None)
        if callable(redraw):
            redraw()
        plotter.render()

    return step


def hold_step(window: QWidget, app: QApplication) -> StepFn:
    """Stehen bleiben — für Szenen, in denen der Text die Arbeit macht."""
    plotter = getattr(getattr(window, "viewport", None), "plotter", None)

    def step(index: int, total: int) -> None:
        if plotter is not None:
            plotter.render()

    return step


def shoot_storyboard(
    window: QWidget,
    app: QApplication,
    session: Any,
    frames: Path,
    spoken: list[tuple[str, Path, float]],
    zoom: float = 1.0,
    label: str = "",
) -> Shot:
    """Alle Szenen des Drehbuchs hintereinander aufnehmen.

    Die Bilder landen fortlaufend nummeriert in **einem** Ordner — ffmpeg
    bekommt am Ende eine einzige Folge und muss nichts zusammensetzen.

    Am Schluss steht der Parameter wieder auf seinem Anfangswert. Ohne das
    beginnt der zweite Durchgang dort, wo der erste aufgehört hat, und das
    Hochformat zeigte ein Gehäuse, das schon breit ist und dann noch breiter
    wird.
    """
    reset_morph(session)
    total = 0
    readout: list[str] = []
    for key, _path, seconds in spoken:
        count = max(1, round(seconds * FPS))
        if key == "morph":
            # Die Bilder vor dieser Szene tragen keinen Wert — aufgefüllt wird
            # bis hierher, damit der Index im Bandwurm der Wert des Bildes
            # bleibt und nicht der Wert des Bildes minus einer Szene.
            readout.extend([""] * (total - len(readout)))
            step = morph_step(window, app, session, MORPH_PARAMETER, MORPH, readout, label)
        elif key == "parameters":
            step = hold_step(window, app)
        else:
            # Aufmacher und Abspann drehen, aber nur ein Stück weit: eine volle
            # Umdrehung in vier Sekunden sieht aus wie ein Ausstellungsstück im
            # Schaufenster.
            step = orbit_step(window, app, zoom, turns=0.35)
        total = record(window, app, frames, total, count, step)
        print(f"  {key:12s} {count:4d} Bilder")
    reset_morph(session)
    settle(app, 20)
    readout.extend([""] * (total - len(readout)))
    return Shot(
        frames=frames,
        count=total,
        viewport=viewport_rect(window),
        readout=tuple(readout),
    )


def reset_morph(session: Any) -> None:
    """Den bewegten Parameter auf seinen Anfangswert zurückstellen."""
    import dataclasses

    parameters = session.project.document.parameters
    existing = parameters.get(MORPH_PARAMETER)
    if existing is None:
        return
    parameters[MORPH_PARAMETER] = dataclasses.replace(existing, value=MORPH[0])
    session.projectChanged.emit()
    session.evaluate_now()


def encode_landscape(shot: Shot, target: Path, audio: Path | None = None) -> None:
    """Das Querformat: die Bilder, wie sie sind."""
    run_ffmpeg(
        [
            "-framerate",
            str(FPS),
            "-i",
            str(shot.frames / "%05d.png"),
            *audio_arguments(audio),
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


def encode_portrait(
    shot: Shot,
    target: Path,
    headline: str,
    sub: str,
    audio: Path | None = None,
) -> None:
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
    chain += readout_filters(shot, font, pad_top)
    run_ffmpeg(
        [
            "-framerate",
            str(FPS),
            "-i",
            str(shot.frames / "%05d.png"),
            *audio_arguments(audio),
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


def readout_filters(shot: Shot, font: str, pad_top: int) -> str:
    """Den laufenden Parameterwert einblenden, solange er sich ändert.

    Ein ``drawtext`` je Bild wären hier 268 Filter. Gleiche aufeinanderfolgende
    Werte werden deshalb zu einem Abschnitt zusammengefasst — auf ganze
    Millimeter gerundet bleiben von 70 bis 96 knapp dreißig übrig, und jeder
    steht so lange, wie er gilt.
    """
    if not any(shot.readout):
        return ""
    spans: list[tuple[int, int, str]] = []
    for index, text in enumerate(shot.readout):
        if not text:
            continue
        if spans and spans[-1][2] == text and spans[-1][1] == index - 1:
            spans[-1] = (spans[-1][0], index, text)
        else:
            spans.append((index, index, text))
    parts = []
    for first, last, text in spans:
        safe = text.replace(":", r"\:")
        parts.append(
            f",drawtext=fontfile='{font}':text='{safe}':fontcolor=0xe6edf3:fontsize=52:"
            f"box=1:boxcolor=0x14161a@0.85:boxborderw=18:"
            f"x=(w-text_w)/2:y={pad_top + 46}:enable='between(n,{first},{last})'"
        )
    return "".join(parts)


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
    from app.core.bootstrap import load_operations
    from app.ui.app import install_qt_translations
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

    wanted = sys.argv[2:] or list(STORYBOARD)
    qt_translator = None
    for language in wanted:
        if language not in STORYBOARD:
            raise SystemExit(f"Kein Drehbuch für {language!r} — vorhanden: {', '.join(STORYBOARD)}")
        print(f"\n=== {language} ===")
        install_catalog(language, read_catalog(language))
        set_language(language)
        # Auch Qt selbst spricht die Sprache der Aufnahme, sonst steht
        # „Cancel" auf einem Dialog, der in der Anwendung „Abbrechen" sagt.
        if qt_translator is not None:
            app.removeTranslator(qt_translator)
        qt_translator = install_qt_translations(app, language)
        shoot_language(app, language, out, frames / language)

    print(f"\nFertig: {out}")
    return 0


def shoot_language(app: QApplication, language: str, out: Path, frames: Path) -> None:
    """Ein vollständiger Durchgang für eine Sprache: sprechen, filmen, kodieren.

    Je Sprache ein eigenes Hauptfenster — und deshalb am Ende
    :func:`release_viewport`. Ohne das behält das ``QtInteractor`` des ersten
    Fensters seinen OpenGL-Kontext, und im zweiten Durchgang liegt der
    Orientierungswürfel als handtellergroßes Achsenkreuz quer über dem Modell.
    Die Anwendung merkt das nie, sie baut ein Hauptfenster und dann keins mehr;
    dieses Werkzeug baut zwei.
    """
    from app.core import examples
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    # **Zuerst die Stimme.** Sie bestimmt, wie lang jede Szene wird — und wenn
    # etwas an ihr fehlt, soll das auffallen, bevor zweimal achthundert Bilder
    # gerechnet sind.
    print("Sprachausgabe:")
    spoken = speak_storyboard(language, out)
    audio = out / f"stimme-{language}.wav"
    join_audio(spoken, audio)
    print(f"  zusammen {sum(entry[2] for entry in spoken):.1f} s")

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

    # Zwei Formate an **einem** Fenster, aus demselben Grund wie oben.
    print("Aufnahme quer:")
    landscape = shoot_storyboard(window, app, session, frames / "landscape", spoken)

    print("Aufnahme hoch:")
    show_panels(window, False)
    hide_orientation_widget(window)
    window.resize(*PORTRAIT)
    settle_resize(window, app)
    portrait = shoot_storyboard(
        window,
        app,
        session,
        frames / "portrait",
        spoken,
        zoom=PORTRAIT_ZOOM,
        label=READOUT_LABEL.get(language, MORPH_PARAMETER),
    )
    show_panels(window, True)

    headline, sub = PORTRAIT_TEXT[language]
    print("Kodierung:")
    encode_landscape(landscape, out / f"solidon3d-{language}-quer-1080p.mp4", audio)
    encode_portrait(
        portrait,
        out / f"solidon3d-{language}-hoch-1080x1920.mp4",
        headline=headline,
        sub=sub,
        audio=audio,
    )

    window.close()
    release_viewport(window)


if __name__ == "__main__":
    raise SystemExit(main())
