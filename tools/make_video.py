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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PySide6.QtWidgets import QApplication, QWidget

from app.core.activation import store as activation_store
from app.i18n import install_catalog, set_language
from app.i18n.catalog import read_catalog

#: Den OpenGL-Kontext freigeben, bevor das nächste Fenster kommt.
#:
#: Stand hier bis zum 24.08.2026 als wortgleiche zweite Fassung — vier
#: Anweisungen, Zeile für Zeile dieselben wie in ``make_figures``. Der
#: Unterschied lag allein im Docstring: Dort steht, **woran** man es merkt (der
#: Orientierungswürfel lag im zweiten Durchgang als handtellergroßes
#: Achsenkreuz quer über dem Modell, und das englische Handbuchbild zeigte
#: statt des Gehäuses ein X, ein Y und ein Z). Hier stand die Kurzfassung, und
#: wer nur sie las, kannte den Fallstrick nicht.
#:
#: Der Weg zwischen zwei Werkzeugen ist nicht neu: ``build_licence_module``
#: holt sich ``public_key`` und ``sign`` aus ``make_licence_keys``. Und teuer
#: ist er hier nicht — ``make_video`` lädt das Operationsregister selbst
#: (``load_operations`` weiter unten), zieht also nichts mit, was es nicht
#: ohnehin braucht.
from tools.make_figures import release_viewport

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


def offer_copy(language: str) -> tuple[str, str]:
    """Leitet Sprecherabschluss und Schlusskarte aus genau diesem Bau ab.

    Demo, späterer Testlauf und Verkauf ohne Test sind drei Angebote. Der
    Videogenerator darf keines davon als eigenen, von der Anwendung getrennten
    Text pflegen — sonst verspricht die nächste Aufnahme wieder den vorigen
    Stand.
    """
    if activation_store.DEMO_UNTIL is not None:
        deadline = activation_store.DEMO_UNTIL
        if language == "en":
            months = (
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            )
            return (
                "Solidon. Try the complete demo now.",
                f"Full demo until {deadline.day} {months[deadline.month - 1]} {deadline.year}",
            )
        return (
            "Solidon. Jetzt die vollständige Demo ausprobieren.",
            f"Vollständige Demo bis {deadline:%d.%m.%Y}",
        )
    if activation_store.TRIAL_FROM is not None:
        if language == "en":
            return (
                "Solidon. Try it free.",
                f"Try free for {activation_store.TRIAL_DAYS} days",
            )
        return (
            "Solidon. Jetzt kostenlos ausprobieren.",
            f"{activation_store.TRIAL_DAYS} Tage kostenlos testen",
        )
    if language == "en":
        return "Solidon. Simple to design. Safe to print.", "Discover Solidon"
    return "Solidon. Einfach konstruieren. Sicher drucken.", "Solidon kennenlernen"


#: Das Einstiegsvideo — kurz, und es beginnt beim Problem, nicht beim Programm.
#:
#: Für jemanden, der Solidon nicht kennt. Es nennt zuerst den Ärger, den die
#: Zielgruppe kennt (das Teil passt nicht, und in den meisten Programmen heißt
#: das: von vorne), zeigt dann die Antwort und endet mit einem Schritt, den man
#: sofort gehen kann.
#:
#: **Kürzer als das Parametrik-Video und in anderer Reihenfolge.** Dort dreht
#: sich zehn Sekunden lang ein Gehäuse, bevor irgendetwas passiert — für ein
#: erstes Video ist das zu lang: auf beiden Plattformen entscheidet sich in den
#: ersten Sekunden, ob jemand bleibt.
OPENING: dict[str, tuple[tuple[str, str], ...]] = {
    "de": (
        ("hook", "Zwei Millimeter zu schmal. Und du fängst wieder von vorne an."),
        (
            "morph",
            "In Solidon nicht. Du änderst eine Zahl — "
            "und Bohrungen, Buchsen und Deckel wandern mit.",
        ),
        ("closing", offer_copy("de")[0]),
    ),
    "en": (
        ("hook", "Two millimetres too narrow. And you start over."),
        (
            "morph",
            "Not in Solidon. You change one number — "
            "and the holes, the inserts and the lid all follow.",
        ),
        ("closing", offer_copy("en")[0]),
    ),
}

#: Das Parametrik-Video: je Szene ein Satz, und der Satz bestimmt die Länge.
#:
#: Erzählt wird das, was diese Anwendung von einem Netzbetrachter
#: unterscheidet — ein Maß ändern, und Bohrungen, Bausteine und Deckel wandern
#: mit. **Nicht der Chat.** Der lokale Agent brauchte im Versuch 75 Sekunden
#: für eine Antwort, lief zweimal in die Zeitgrenze und erzeugte dabei keine
#: einzige Operation; ein Video, das „Satz eintippen, Bauteil herausbekommen"
#: verspricht, wäre ein Versprechen auf etwas, das die Installation hier nicht
#: einlöst.
#:
#: Es setzt voraus, dass der Zuschauer weiß, was Solidon ist — deshalb ist
#: :data:`OPENING` das erste Video und dieses das zweite.
#:
#: **Die Zahlen im Intro sind gemessen, nicht geschätzt.** Zweiundfünfzig
#: Minuten und achtzehn Gramm stehen dort, weil dieses Projekt einmal ganz
#: durch die Übergabe gelaufen ist: Elegoo Centauri Carbon 2, Elegoo PETG,
#: Profil „0.20mm Standard", zurückgelesen aus dem G-Code des ElegooSlicer
#: (siehe ``ROADMAP.md``). Bei ``breite`` auf 96 mm werden 64 Minuten und
#: 22,6 Gramm daraus — der Zuschauer sieht den kleinen Stand, also steht der
#: kleine Wert. Wer am Projekt oder am Profil dreht, misst neu, statt die
#: Zahl anzupassen: eine gerundete Behauptung wäre schlechter als keine.
STORYBOARD: dict[str, tuple[tuple[str, str], ...]] = {
    "de": (
        (
            "intro",
            "Das ist ein Gehäuse aus Solidon. Siebzig Millimeter breit, "
            "mit Mutternfallen, Einpressbuchsen und einer Kabeldurchführung — "
            "zweiundfünfzig Minuten Druckzeit, achtzehn Gramm.",
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
            "with nut traps, heat-set inserts and a cable gland — "
            "fifty-two minutes of printing, eighteen grams.",
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

#: Das Modul-Video: ein Teil, das zu groß gedruckt wäre, wird zu sechs, die
#: zusammenhalten.
#:
#: Es erzählt Weg 1 aus Bauplan §2.2 — ein fertiges Modell anpassen — und
#: braucht dafür kein einziges Maß: Man sieht, dass es auseinandergeht, und man
#: sieht, dass es wieder zusammengeht. Das ist die Sorte Aussage, die ein Video
#: besser kann als ein Text.
#:
#: **Der Schluss ist der Punkt.** Nicht „Solidon kann teilen" — teilen kann
#: jeder Slicer. Sondern: Was einmal geteilt ist, lässt sich erweitern, und die
#: Verbindung dafür hat niemand von Hand konstruiert.
#: **Ohne Druckzeiten, und das mit Absicht.** Der naheliegende Satz wäre „am
#: Stück einundzwanzig Stunden, je Modul drei" — die einundzwanzig stehen in der
#: Spezifikation des Besteckkorbs und gelten dem Stand mit 3-mm-Wänden, nicht
#: diesem. Die drei waren geschätzt. Eine Zahl, die niemand an *diesem* Teil
#: gemessen hat, gehört in kein Video; wer sie messen will, sliced beide Stände
#: und setzt sie hier ein.
MODULAR: dict[str, tuple[tuple[str, str], ...]] = {
    "de": (
        (
            "intro",
            "Ein Abtropfkorb für Besteck. Sechs Fächer, ein Teil — und ein Druck, "
            "der über einen Tag läuft.",
        ),
        (
            "explode",
            "Zwei Klicks legen die Trennebene — Solidon setzt die Schwalbenschwänze "
            "selbst, dorthin, wo die Wand sie trägt.",
        ),
        (
            "join",
            "Sechs Module, die zusammenstecken. Jedes für sich auf die Platte, "
            "jedes für sich gedruckt.",
        ),
        (
            "outro",
            "Und wer mehr Besteck hat, druckt ein Fach dazu. Solidon.",
        ),
    ),
    "en": (
        (
            "intro",
            "A draining basket for cutlery. Six compartments, one part — and a print "
            "that runs for more than a day.",
        ),
        (
            "explode",
            "Two clicks set the parting plane — Solidon places the dovetails itself, "
            "where the wall can carry them.",
        ),
        (
            "join",
            "Six modules that plug together. Each on the plate on its own, each "
            "printed on its own.",
        ),
        (
            "outro",
            "And if you own more cutlery, you print another compartment. Solidon.",
        ),
    ),
}

#: Die Drehbücher unter ihren Namen. Vorgabe ist das Einstiegsvideo.
SCRIPTS = {
    "einstieg": OPENING,
    "parametrik": STORYBOARD,
    "modular": MODULAR,
}

#: Wie weit die Teile im Modul-Video auseinandergehen, als Faktor auf den
#: Abstand zur Mitte. Eins ist der doppelte Abstand — genug, dass man die
#: Schwalbenschwänze sieht, wenig genug, dass die sechs im Bild bleiben.
EXPLOSION = 1.0

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

#: Das Anwendungszeichen für die Schlusskarte.
#:
#: Dieselbe Datei, die auch die Anwendung und die Website tragen — ein zweites,
#: nur fürs Video gepflegtes Zeichen wäre in einem halben Jahr ein anderes.
ICON_FILE = Path(__file__).resolve().parent.parent / "app" / "images" / "icon" / "solidon3d.svg"

#: Was auf der Schlusskarte steht.
#:
#: Aus demselben Freischaltstand wie die Anwendung abgeleitet. Ein Video, das
#: etwas anderes verspricht als die Seite, auf die es schickt, verliert genau
#: dort seinen Zuschauer.
OUTRO_CALL = {
    "de": offer_copy("de")[1],
    "en": offer_copy("en")[1],
}

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
    #: Ab welchem Bild die Schlusskarte steht — ``count``, wenn es keine gibt.
    #:
    #: Die feste Beschriftung des Hochformats endet dort. Ohne das lag sie über
    #: der Karte: Überschrift und Adresse standen doppelt im Bild, einmal von
    #: der Karte und einmal darüber.
    card_from: int = -1


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


def speak_storyboard(
    language: str, out: Path, script: dict[str, tuple[tuple[str, str], ...]]
) -> list[tuple[str, Path, float]]:
    """Jede Szene einmal sprechen und sagen, wie lange sie dauert.

    Vor jeder Aufnahme, aus demselben Grund wie beim einzelnen Satz: die
    Sprache bestimmt die Länge der Szene, nicht eine geratene Sekundenzahl.
    """
    spoken: list[tuple[str, Path, float]] = []
    for key, text in script[language]:
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


def outro_card(size: tuple[int, int], inner: tuple[int, int, int, int], language: str) -> Any:
    """Die Schlusskarte zeichnen: Zeichen, Marke, Aufruf.

    Kein Bildschirmfoto, sondern gezeichnet — sie zeigt ja nichts aus der
    Anwendung. Gerendert wird in **Aufnahmegröße**, und alles Wesentliche
    liegt innerhalb von ``inner``: das ist der Ausschnitt, den das Hochformat
    später herausschneidet. Wer die Karte mittig auf das ganze Bild setzt,
    findet sie dort angeschnitten wieder.

    Ein Vorspann mit demselben Inhalt wäre der naheliegende Gegenpart und
    wäre falsch. Vorne kostet ein Zeichen genau die Sekunden, in denen der
    Zuschauer entscheidet, ob er bleibt — Markenerinnerung baut man am Ende
    auf, wenn er schon zugesehen hat.
    """
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    width, height = size
    left, top, inner_width, inner_height = inner
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#14161a"))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    # Bezugsgröße ist die kürzere Seite des Ausschnitts: dieselbe Karte trägt
    # damit quer wie hoch, ohne zwei Sätze von Zahlen.
    unit = min(inner_width, inner_height)
    centre_x = left + inner_width / 2
    centre_y = top + inner_height / 2

    logo = ICON_FILE
    if logo.is_file():
        renderer = QSvgRenderer(str(logo))
        side = unit * 0.26
        renderer.render(
            painter,
            QRectF(centre_x - side / 2, centre_y - side * 1.05, side, side),
        )

    painter.setPen(QColor("#e6edf3"))
    brand = QFont()
    brand.setPixelSize(int(unit * 0.115))
    brand.setWeight(QFont.Weight.DemiBold)
    painter.setFont(brand)
    painter.drawText(
        QRectF(left, centre_y + unit * 0.10, inner_width, unit * 0.18),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        "Solidon",
    )

    painter.setPen(QColor("#9aa4b2"))
    call = QFont()
    call.setPixelSize(int(unit * 0.055))
    painter.setFont(call)
    painter.drawText(
        QRectF(left, centre_y + unit * 0.27, inner_width, unit * 0.12),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        OUTRO_CALL[language],
    )

    painter.setPen(QColor("#e08b4e"))
    address = QFont()
    address.setPixelSize(int(unit * 0.062))
    address.setWeight(QFont.Weight.DemiBold)
    painter.setFont(address)
    painter.drawText(
        QRectF(left, centre_y + unit * 0.40, inner_width, unit * 0.12),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        "solidon3d.de",
    )
    painter.end()
    return image


def write_outro(
    frames: Path,
    start: int,
    count: int,
    size: tuple[int, int],
    inner: tuple[int, int, int, int],
    language: str,
) -> int:
    """Die Schlusskarte als Bildfolge in denselben Ordner schreiben.

    Sie läuft damit durch dieselbe Kodierung wie alles andere — ein zweites
    Video anzuhängen hieße, Auflösung, Bildrate und Farbraum ein zweites Mal
    zusammenpassen zu lassen.
    """
    frames.mkdir(parents=True, exist_ok=True)
    card = outro_card(size, inner, language)
    for index in range(count):
        card.save(str(frames / f"{start + index:05d}.png"))
    return start + count


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


def explode_step(
    window: QWidget,
    app: QApplication,
    span: tuple[float, float],
    zoom: float = 1.0,
    turns: float = 0.12,
) -> StepFn:
    """Die Teile auseinanderziehen — oder wieder zusammenschieben.

    Die Bewegung, die eine Teilung überhaupt erst erklärt. Sechs Module, die
    aneinanderstehen, sehen aus wie ein Korb mit Fugen; erst wenn sie
    auseinandergehen, sieht man, dass es sechs Teile sind. Und erst wenn sie
    wieder zusammengehen, sieht man, dass sie zusammengehören.

    Der Versatz kommt aus der Ansicht (``Viewport.set_explosion``) und erreicht
    das Netz nie — was hier auseinanderfährt, steht im Stapel und im Export
    weiterhin dort, wo es hingehört. Ein Video, das dafür die Geometrie
    verschöbe, zeigte etwas, das die Anwendung nicht tut.

    Die Kamera dreht dabei ein Stück mit: Auseinander **und** um sich selbst
    ist eine Bewegung, die man ansieht; auseinander allein sieht aus wie ein
    stehendes Bild, in dem etwas ruckt.
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
    low, high = span

    def step(index: int, total: int) -> None:
        # Sinus statt linear, wie beim Parameterlauf: die Bewegung beginnt und
        # endet ruhig, statt anzuspringen und abrupt zu stehen.
        share = 0.5 - 0.5 * math.cos(math.pi * index / max(1, total - 1))
        # Erst der Versatz, dann die Kamera: ``set_explosion`` baut die Szene
        # neu auf, und was vorher an der Kamera stand, wäre danach vielleicht
        # nicht mehr das, was gilt.
        viewport.set_explosion(low + (high - low) * share)
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
    language: str = "de",
    morph_name: str = MORPH_PARAMETER,
    morph_span: tuple[float, float] = MORPH,
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
    # Und den Versatz auch: ``shoot_storyboard`` läuft zweimal am selben
    # Fenster, quer und hoch. Bliebe die Explosion stehen, begänne das
    # Hochformat mit einem Korb, der schon auseinander ist.
    window.viewport.set_explosion(0.0)  # type: ignore[attr-defined]
    total = 0
    card_from = -1
    readout: list[str] = []
    for key, _path, seconds in spoken:
        count = max(1, round(seconds * FPS))
        if key == "closing":
            # Die Schlusskarte kommt aus dem Zeichenprogramm, nicht aus dem
            # Fenster — sie zeigt nichts aus der Anwendung.
            readout.extend([""] * (total - len(readout)))
            card_from = total
            size = (window.width(), window.height())
            total = write_outro(frames, total, count, size, viewport_rect(window), language)
            readout.extend([""] * (total - len(readout)))
            print(f"  {key:12s} {count:4d} Bilder (Schlusskarte)")
            continue
        if key == "morph":
            # Die Bilder vor dieser Szene tragen keinen Wert — aufgefüllt wird
            # bis hierher, damit der Index im Bandwurm der Wert des Bildes
            # bleibt und nicht der Wert des Bildes minus einer Szene.
            readout.extend([""] * (total - len(readout)))
            step = morph_step(window, app, session, morph_name, morph_span, readout, label)
        elif key == "explode":
            step = explode_step(window, app, (0.0, EXPLOSION), zoom)
        elif key == "join":
            step = explode_step(window, app, (EXPLOSION, 0.0), zoom)
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
    window.viewport.set_explosion(0.0)  # type: ignore[attr-defined]
    settle(app, 20)
    readout.extend([""] * (total - len(readout)))
    return Shot(
        frames=frames,
        count=total,
        viewport=viewport_rect(window),
        readout=tuple(readout),
        card_from=card_from if card_from >= 0 else total,
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


#: Die Grenzen eines Website-Loops (WD1).
#:
#: **Ein Loop ist keine kleine Fassung des Videos.** Er läuft stumm, endlos und
#: neben Text, den jemand gerade liest — er soll zeigen, dass sich etwas
#: bewegt, und nicht erzählen. Daraus folgt jede Zahl hier:
#:
#: * **720p statt 1080p.** Auf der Seite steht er in einer Spalte, nie im
#:   Vollbild. Die Hälfte der Datenmenge für einen Unterschied, den man an
#:   dieser Größe nicht sieht.
#: * **Kein Ton.** Ein Video, das ungefragt spricht, ist der schnellste Weg
#:   zum Zurück-Knopf. Ohne Tonspur spielt es außerdem in jedem Browser von
#:   selbst — ``autoplay`` gilt nur für stumme Videos.
#: * **Zwei Formate.** ``webm`` (VP9) ist kleiner, ``mp4`` (H.264) versteht
#:   jeder. Der Browser nimmt das erste, das er kann; wer nur eines liefert,
#:   liefert manchem gar nichts.
#: * **Ein Standbild.** Es steht, bis das Video geladen ist — und bei
#:   ``prefers-reduced-motion`` ist es das einzige, was der Besucher je sieht.
#:   Ohne poster zeigt der Browser dort ein schwarzes Rechteck.
LOOP_HEIGHT = 720

#: Wie lang ein Loop läuft, in Sekunden.
#:
#: Zwölf ist die Mitte der Spanne, die das Konzept nennt (5 bis 15): lang
#: genug für vier Szenen, kurz genug, dass ein Besucher den Anfang noch kennt,
#: wenn er wieder anfängt. Wer das ändert, prüft die Dateigröße mit — sie
#: wächst linear mit.
LOOP_SECONDS = 12.0

#: Wie stark der Loop gerechnet wird, je Format.
#:
#: Gemessen wird am Ziel: 2 bis 5 MB je Loop. Der Upload schafft 1,8 MB/s, und
#: fünf Loops sind damit eine halbe Minute — der Besucher lädt einen davon,
#: aber die Seite muss auch hochgehen.
LOOP_CRF_H264 = 26
LOOP_CRF_VP9 = 34


def encode_loop(shot: Shot, stem: Path) -> tuple[Path, Path, Path]:
    """Einen Website-Loop schreiben: ``webm``, ``mp4`` und sein Standbild.

    ``stem`` ist der Pfad **ohne** Endung; zurück kommen die drei Dateien in
    der Reihenfolge, in der sie im HTML stehen sollten — erst ``webm``, dann
    ``mp4``, dann das Standbild.

    **Das Standbild ist das erste Bild und nicht irgendeines.** Es steht, bis
    das Video geladen ist, und muss deshalb genau das zeigen, womit der Loop
    anfängt; ein Standbild aus der Mitte lässt das Bild springen, sobald die
    Wiedergabe einsetzt.

    **Kein Ton, und das ist mehr als eine Auslassung:** ``-an`` macht aus dem
    Loop ein Video, das der Browser von selbst abspielen darf. Mit Tonspur —
    auch mit stiller — verlangt jeder Browser eine Nutzergeste.
    """
    scaled = f"scale=-2:{LOOP_HEIGHT}:flags=lanczos"
    webm = stem.with_suffix(".webm")
    mp4 = stem.with_suffix(".mp4")
    poster = stem.with_suffix(".png")

    run_ffmpeg(
        [
            "-framerate",
            str(FPS),
            "-i",
            str(shot.frames / "%05d.png"),
            "-an",
            "-vf",
            scaled,
            "-c:v",
            "libvpx-vp9",
            "-crf",
            str(LOOP_CRF_VP9),
            "-b:v",
            "0",
            "-row-mt",
            "1",
            str(webm),
        ]
    )
    run_ffmpeg(
        [
            "-framerate",
            str(FPS),
            "-i",
            str(shot.frames / "%05d.png"),
            "-an",
            "-vf",
            scaled,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            str(LOOP_CRF_H264),
            "-preset",
            "slow",
            # Damit der Browser mit dem Abspielen beginnen kann, bevor die
            # Datei ganz da ist: der Index gehört an den Anfang.
            "-movflags",
            "+faststart",
            str(mp4),
        ]
    )
    run_ffmpeg(
        [
            "-i",
            str(shot.frames / "00000.png"),
            "-vf",
            scaled,
            "-frames:v",
            "1",
            str(poster),
        ]
    )
    for written in (webm, mp4, poster):
        megabytes = written.stat().st_size / 1024 / 1024
        print(f"  Loop  → {written.name}  {megabytes:.1f} MB")
    return webm, mp4, poster


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
    # Die feste Beschriftung endet, wo die Schlusskarte beginnt. Ohne diese
    # Bedingung lag sie über der Karte: Überschrift und Adresse standen doppelt
    # im Bild, einmal aus der Karte und einmal darüber.
    until = f":enable='lt(n,{shot.card_from})'"
    chain = (
        f"crop={width}:{height}:{left}:{top},"
        f"scale=1080:{scaled_height}:flags=lanczos,"
        f"pad=1080:1920:0:{pad_top}:color=0x14161a,"
        f"drawtext=fontfile='{font}':text='{headline}':fontcolor=white:fontsize=72:"
        f"x=(w-text_w)/2:y=150{until},"
        f"drawtext=fontfile='{font}':text='{sub}':fontcolor=0x9aa4b2:fontsize=40:"
        f"x=(w-text_w)/2:y=258{until},"
        f"drawtext=fontfile='{font}':text='solidon3d.de':fontcolor=0x6ea8fe:fontsize=46:"
        f"x=(w-text_w)/2:y=1750{until}"
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
    # Beim Start zurückgesetzt, nicht beim Import — die Begründung steht in
    # `tools/make_manual.py`: ein Modul, das die Plattform schon beim Importieren
    # umstellt, reißt jeden Testlauf mit, der es nur lesen will.
    os.environ.pop("QT_QPA_PLATFORM", None)

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

    # Erstes Argument nach dem Ziel ist das Drehbuch, alles Weitere sind
    # Sprachen: ``make_video.py ziel einstieg de``.
    arguments = sys.argv[2:]
    name = arguments[0] if arguments and arguments[0] in SCRIPTS else "einstieg"
    script = SCRIPTS[name]
    # Ein Argument, das auf ``.p3d`` endet, ist das Projekt. Gebraucht für
    # Drehbücher, die kein Beispielprojekt zeigen, sondern ein echtes — das
    # Modul-Video tut das, und ein Druckprojekt wohnt nicht im Repository.
    chosen = [entry for entry in arguments if entry.endswith(".p3d")]
    project = Path(chosen[0]) if chosen else None
    # ``loop`` schaltet auf die Website-Fassung um: stumm, 720p, kurz, in
    # zwei Formaten samt Standbild. Kein eigenes Werkzeug daneben — es ist
    # dieselbe Aufnahme aus demselben Drehbuch, nur anders ausgegeben, und
    # zwei Programme, die dasselbe Fenster filmen, laufen unweigerlich
    # auseinander.
    as_loop = "loop" in arguments
    # ``--morph <name>[:<von>:<bis>]`` — welcher Parameter im Loop läuft.
    #
    # **Das Werkzeug folgt dem Motiv, nicht umgekehrt.** ``MORPH_PARAMETER``
    # heißt ``breite``; das Beispielprojekt und das Gehäuse-Schaustück haben
    # ihn, der Rollenhalter nennt ihn ``rollenbreite`` und läuft von 55 bis 90.
    # Ein Teil umzubenennen, damit ein Aufnahmewerkzeug es findet, hätte den
    # Zweck verkehrt: Parameternamen gehören dem Nutzer.
    #
    # Name und Spanne stehen in **einem** Schalter, weil beides zusammengehört
    # — ein anderer Parameter hat fast immer auch einen anderen Bereich, und
    # zwei Schalter wären zwei Gelegenheiten, nur einen zu setzen.
    morph_name, morph_span = MORPH_PARAMETER, MORPH
    for entry in arguments:
        if not entry.startswith("--morph"):
            continue
        value = entry.split("=", 1)[1] if "=" in entry else ""
        if not value:
            index = arguments.index(entry)
            value = arguments[index + 1] if index + 1 < len(arguments) else ""
        parts = value.split(":")
        if parts and parts[0]:
            morph_name = parts[0]
        if len(parts) == 3:
            morph_span = (float(parts[1]), float(parts[2]))
        break
    skip = {morph_name, f"{morph_name}:{morph_span[0]:g}:{morph_span[1]:g}"}
    wanted = [
        entry
        for entry in arguments
        if entry not in SCRIPTS
        and entry != "loop"
        and not entry.endswith(".p3d")
        and not entry.startswith("--")
        and entry not in skip
    ] or list(script)
    print(f"Drehbuch: {name}{' (Website-Loop)' if as_loop else ''}")
    if project is not None:
        print(f"Projekt:  {project}")

    qt_translator = None
    for language in wanted:
        if language not in script:
            raise SystemExit(f"Kein Drehbuch für {language!r} — vorhanden: {', '.join(script)}")
        print(f"\n=== {language} ===")
        install_catalog(language, read_catalog(language))
        set_language(language)
        # Auch Qt selbst spricht die Sprache der Aufnahme, sonst steht
        # „Cancel" auf einem Dialog, der in der Anwendung „Abbrechen" sagt.
        if qt_translator is not None:
            app.removeTranslator(qt_translator)
        qt_translator = install_qt_translations(app, language)
        if as_loop:
            shoot_loop(
                app,
                language,
                out,
                frames / f"{name}-{language}",
                script[language],
                f"{name}-{language}",
                chosen=project,
                morph_name=morph_name,
                morph_span=morph_span,
            )
            continue
        shoot_language(app, language, out, frames / f"{name}-{language}", script, project)

    print(f"\nFertig: {out}")
    return 0


#: Wie viele Bilder eine Umdrehung hat.
#:
#: Sechsunddreißig sind zehn Grad je Bild — fein genug, dass eine Ziehgeste
#: rund wirkt, und grob genug, dass die Reihe klein bleibt. Bei
#: vierundsiebzig (fünf Grad) sieht man den Unterschied nicht mehr und lädt
#: die doppelte Datenmenge.
TURNTABLE_STEPS = 36

#: Wie breit ein Bild der Reihe ist.
#:
#: Der Loop ist 1280 breit, weil er die ganze Anwendung zeigt. Hier steht nur
#: das **Teil** im Bild, und das steht auf der Seite in einer Spalte — 800
#: reichen, und sie sind bei sechsunddreißig Bildern der Unterschied zwischen
#: anderthalb und vier Megabyte.
TURNTABLE_WIDTH = 1000
#: Achthundert waren es bis zum 31.08.2026, aus einer Zeit, in der die Bühne
#: schmaler stand. Nach der Straffung misst sie 745 Punkte — 800 Bildpunkte
#: darauf sind Faktor 1,07, und die Latte für Schärfe liegt bei 1,2. Tausend
#: ergeben 1,34 und liegen sicher darüber; zwölfhundert kosteten 144 kB mehr
#: für einen Unterschied, den niemand sieht.

#: Wie stark die Bilder gerechnet werden (WebP, 0 bis 100).
#:
#: Achtzig ist die Schwelle, unter der bei Flächen mit weichem Verlauf — und
#: ein schattierter Körper ist genau das — Streifen sichtbar werden.
TURNTABLE_QUALITY = 80

#: Wie nah die Kamera am Teil steht (Faktor auf den Abstand).
#:
#: Gemessen: Bei 1,0 fuellt das Schaustueck knapp ein Drittel des Bildes, und
#: die Kabeldurchfuehrung ist ein Fleck von vier Bildpunkten.
TURNTABLE_ZOOM = 0.62


def hide_axis_marker(window: Any) -> None:
    """Das Achsenkreuz in der Ecke abschalten.

    Der Nachbar von :func:`hide_orientation_widget`, und er wird getrennt
    gerufen: Im **Loop** ist die Anwendung die Aussage, dort gehören ihre
    Bedienelemente ins Bild. In der Drehreihe ist es das **Teil**, und ein
    Achsenkreuz, das sich mitdreht, ist Werkzeug im Schaufenster.

    **Es hängt am Renderer, nicht am Plotter.** ``plotter.axes_widget`` gibt es
    in pyvista 0.48 nicht; ein ``getattr`` darauf liefert still ``None``, und
    das Kreuz bliebe stehen, ohne dass irgendein Aufruf sich beschwert. Der
    Weg dorthin steht in ``app.ui.viewport.axes_widget_of`` — hier
    nachgebildet, weil ``tools`` die Oberfläche nicht importiert.
    """
    plotter = getattr(getattr(window, "viewport", None), "plotter", None)
    renderer = getattr(plotter, "renderer", None) if plotter is not None else None
    marker = getattr(renderer, "axes_widget", None)
    if marker is None:
        return
    try:
        marker.EnabledOff()
    except Exception as problem:  # pragma: no cover - hängt am Treiber
        print(f"  (Achsenkreuz blieb an: {problem})")


def shoot_turntable(
    app: QApplication,
    out: Path,
    frames: Path,
    stem: str,
    steps: int = TURNTABLE_STEPS,
    chosen: Path | None = None,
    zoom: float = TURNTABLE_ZOOM,
    ratio: float | None = None,
) -> list[Path]:
    """Eine Umdrehung des Teils als Bildreihe — zum Ziehen auf der Website.

    **Warum eine Reihe und kein Video:** Ein Video läuft, eine Reihe gehorcht.
    Der Besucher zieht mit der Maus und entscheidet selbst, wo er hinsieht —
    an der Bohrung von der Seite, an der Senkung von oben, an der Wandstärke
    an der Kante. Das ist mehr, als eine Kamerafahrt zeigen kann, und es
    braucht auf der Seite **keine fremde Bibliothek**: Bilder tauschen ist
    fünfzehn Zeilen.

    **Die Bedienzonen sind aus**, anders als beim Loop. Dort ist die
    Anwendung die Aussage; hier ist es das Teil, und ein Objektbaum, der sich
    mitdreht, gibt es nicht — er stünde still, während das Teil sich dreht,
    und das sieht aus wie ein Fehler.

    **Der Abstand hängt am Motiv, nicht am Werkzeug.** ``TURNTABLE_ZOOM`` ist
    am Elektronikgehäuse gemessen, und das ist ein hohes, schmales Teil. Ein
    breites — der Rollenhalter ist 128 mm breit — ragt bei demselben Wert oben
    und rechts aus dem Bild. Wer ein anderes Teil aufnimmt, gibt seinen Wert
    mit, statt die Konstante zu verstellen: Sie gehört dem Schaustück.

    Zurück kommen die Bilddateien in der Reihenfolge der Umdrehung.
    """
    from app.core import examples
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    session = Session()
    window = MainWindow(session, UiSettings())
    window.resize(*WINDOW)
    window.show()
    settle(app, 60)

    project = chosen if chosen is not None else examples.directory() / EXAMPLE
    if not project.is_file():
        raise SystemExit(f"Projekt fehlt: {project}")
    session.open_project(project)
    if not await_result(app, session):
        raise SystemExit(f"Das Projekt rechnete nicht fertig: {project}")

    # Dieselbe Wache wie beim Loop: Ohne Körper dreht sich ein leerer Raum.
    result = getattr(session, "last_result", None)
    bodies = len(result.scene.objects) if result is not None else 0
    if not bodies:
        raise SystemExit(f"Kein Körper in der Szene ({project.name}).")

    show_panels(window, False)
    hide_orientation_widget(window)
    hide_axis_marker(window)
    settle(app, 30)

    frames.mkdir(parents=True, exist_ok=True)
    for old in frames.glob("*.png"):
        old.unlink()
    print(f"  Projekt: {project.name}, {bodies} Körper, {steps} Bilder")
    # **Naeher heran als beim Video.** Dort steht das Teil in einem Fenster
    # mit Baum und Verlauf; hier hat es das Bild fuer sich, und bei Faktor 1
    # fuellte es knapp ein Drittel davon. Ein Teil, das man drehen soll, muss
    # gross genug sein, dass man beim Drehen etwas erkennt.
    record(window, app, frames, 0, steps, orbit_step(window, app, zoom, 1.0))

    left, top, width, height = viewport_rect(window)
    # **Der Zuschnitt folgt der Bühne, nicht dem Fenster.** Zeigt die Seite
    # 16/7 und die Aufnahme 1000/510, bezahlt jedes Bild Pixel für einen Rand,
    # den der Browser wegschneidet. Geschnitten wird um die Mitte, weil das
    # Teil dort steht.
    cut_x, cut_y, cut_w, cut_h = left, top, width, height
    if ratio:
        wanted = int(width / ratio)
        if wanted < height:
            cut_h = wanted - (wanted % 2)
            cut_y = top + (height - cut_h) // 2
        else:
            cut_w = int(height * ratio)
            cut_w -= cut_w % 2
            cut_x = left + (width - cut_w) // 2
    written: list[Path] = []
    out.mkdir(parents=True, exist_ok=True)
    for index in range(steps):
        target = out / f"{stem}-{index:02d}.webp"
        run_ffmpeg(
            [
                "-i",
                str(frames / f"{index:05d}.png"),
                # Erst den Viewport ausschneiden, dann auf die Zielbreite:
                # Zuschneiden nach dem Skalieren träfe andere Bildpunkte.
                "-vf",
                f"crop={cut_w}:{cut_h}:{cut_x}:{cut_y},scale={TURNTABLE_WIDTH}:-2:flags=lanczos",
                "-quality",
                str(TURNTABLE_QUALITY),
                str(target),
            ]
        )
        written.append(target)
    total = sum(entry.stat().st_size for entry in written) / 1024 / 1024
    print(f"  Reihe → {stem}-00…{steps - 1:02d}.webp  {total:.1f} MB zusammen")
    release_viewport(window)
    return written


def loop_timing(
    scenes: tuple[tuple[str, str], ...], seconds: float
) -> list[tuple[str, Path, float]]:
    """Die Szenen eines Drehbuchs auf eine feste Gesamtdauer verteilen.

    **Ein Loop hat keine Stimme, also braucht er eine andere Uhr.** Im Video
    dauert eine Szene so lang wie der Satz, der sie begleitet
    (:func:`speak_storyboard`); ohne Ton gibt es diesen Satz nicht, und die
    Dauer muss von außen kommen.

    Verteilt wird gleichmäßig. Das ist grob und für den Zweck richtig: Ein
    Loop zeigt, **dass** sich etwas bewegt — wer eine Szene betonen will,
    schneidet ein eigenes Drehbuch, statt hier Gewichte einzuführen.

    Der Pfad im Ergebnis ist ein Platzhalter. ``shoot_storyboard`` liest von
    jedem Eintrag nur Namen und Dauer; die Tonspur ignoriert es (``_path``).
    """
    if not scenes:
        return []
    per_scene = seconds / len(scenes)
    return [(key, Path(), per_scene) for key, _text in scenes]


def shoot_loop(
    app: QApplication,
    language: str,
    out: Path,
    frames: Path,
    scenes: tuple[tuple[str, str], ...],
    stem: str,
    seconds: float = LOOP_SECONDS,
    chosen: Path | None = None,
    morph_name: str = MORPH_PARAMETER,
    morph_span: tuple[float, float] = MORPH,
) -> tuple[Path, Path, Path]:
    """Ein Drehbuch als Website-Loop aufnehmen und ausgeben.

    Dieselbe Aufnahme wie beim Video — sichtbares Fenster, Bild für Bild,
    ``grabWindow`` — nur ohne Ton, ohne Hochformat und mit fester Dauer. Was
    dabei herauskommt, sind die drei Dateien aus :func:`encode_loop`.

    **Die Bedienzonen bleiben im Bild**, anders als beim Hochformat. Ein Loop
    auf der Website soll das *Produkt* zeigen und nicht einen Körper im
    Nichts: Objektbaum, Verlauf und Prüfbericht sind das, was Solidon von
    einem Betrachter unterscheidet.
    """
    from app.core import examples
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    session = Session()
    window = MainWindow(session, UiSettings())
    window.resize(*WINDOW)
    window.show()
    settle(app, 60)

    # **Ohne Projekt filmt man den Startbildschirm.** Beim ersten Lauf war
    # genau das das Ergebnis: 360 Bilder, 0,29 MB, beide Kontrollfälle grün —
    # und das Standbild zeigte eine leere Ablagefläche mit vier Kacheln. Für
    # eine Website ist das die schlechteste denkbare erste Sekunde. Dieselbe
    # Vorgabe wie beim Video (:func:`shoot_language`).
    project = chosen if chosen is not None else examples.directory() / EXAMPLE
    if not project.is_file():
        raise SystemExit(f"Projekt fehlt: {project}")
    session.open_project(project)
    if not await_result(app, session):
        raise SystemExit(f"Das Projekt rechnete nicht fertig: {project}")
    settle(app, 30)

    # **Die Wache, die den ersten Lauf gefangen hätte.** Sie fragt nicht nach
    # der Bildzahl und nicht nach der Dateigröße — beide waren grün —, sondern
    # danach, ob überhaupt ein Körper im Bild steht.
    result = getattr(session, "last_result", None)
    bodies = len(result.scene.objects) if result is not None else 0
    if not bodies:
        raise SystemExit(
            f"Kein Körper in der Szene ({project.name}) — der Loop zeigte den Startbildschirm."
        )
    print(f"  Projekt: {project.name}, {bodies} Körper")

    print(f"Aufnahme Loop {stem} ({seconds:.0f} s):")
    shot = shoot_storyboard(
        window,
        app,
        session,
        frames,
        loop_timing(scenes, seconds),
        language=language,
        morph_name=morph_name,
        morph_span=morph_span,
    )
    files = encode_loop(shot, out / stem)
    # Ein Fenster je Aufnahme, und der Viewport wird ausdrücklich
    # losgelassen: Ohne das behält das ``QtInteractor`` des ersten seinen
    # OpenGL-Kontext, und im zweiten Loop liegt der Orientierungswürfel
    # als handtellergroßes Achsenkreuz quer über dem Modell.
    release_viewport(window)
    return files


def shoot_language(
    app: QApplication,
    language: str,
    out: Path,
    frames: Path,
    script: dict[str, tuple[tuple[str, str], ...]],
    chosen: Path | None = None,
) -> None:
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
    spoken = speak_storyboard(language, out, script)
    audio = out / f"stimme-{language}.wav"
    join_audio(spoken, audio)
    print(f"  zusammen {sum(entry[2] for entry in spoken):.1f} s")

    session = Session()
    window = MainWindow(session, UiSettings())
    window.resize(*WINDOW)
    window.show()

    project = chosen if chosen is not None else examples.directory() / EXAMPLE
    if not project.is_file():
        raise SystemExit(f"Projekt fehlt: {project}")
    session.open_project(project)
    window._show_start_screen(False)
    if not await_result(app, session):
        raise SystemExit("Die Auswertung wurde nicht fertig — kein Video")
    window.raise_()
    window.activateWindow()
    settle(app, 60)

    # Zwei Formate an **einem** Fenster, aus demselben Grund wie oben.
    print("Aufnahme quer:")
    landscape = shoot_storyboard(
        window, app, session, frames / "landscape", spoken, language=language
    )

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
