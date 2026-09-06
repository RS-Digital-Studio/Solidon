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

import hashlib
import math
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
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

#: Wo der sichtbare Mauszeiger in diesem Bild steht — Fensterkoordinaten
#: und ob der Klickring sichtbar sein soll. Bildschirmaufnahmen enthalten den
#: Systemzeiger nicht zuverlässig; der Film ergänzt deshalb das im
#: Betriebssystem eingestellte Zeigerbild an genau der Stelle, an der dieselbe
#: Aufnahme die Qt-Eingabe auslöst.
PointerFn = Callable[[int, int], tuple[float, float, bool] | None]

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

#: Das eingelesene MIT-Korpusnetz für den Merkmalsfilm. Im Projekt stehen
#: bereits Reparatur und Bettlage; die fünf Bohrungen stammen weiterhin aus
#: der eingebetteten STL und nicht aus einer Solidon-Konstruktion.
FEATURE_EXAMPLE = "weg1-halterung-anpassen.p3d"

#: Eingaben, die das Aufnahmewerkzeug wie die sichtbare Anwendung unmittelbar
#: einlesen darf. Damit kann ein Belegfilm ein wirkliches Nutzermodell zeigen,
#: ohne es erst in ein nur für die Aufnahme gebautes Projekt umzupacken.
MODEL_SUFFIXES = frozenset(
    {".3mf", ".glb", ".gltf", ".obj", ".off", ".ply", ".step", ".stl", ".stp"}
)

#: Die eigene Umgebung für die Sprachausgabe.
#:
#: **Nicht die Projektumgebung.** Chatterbox bringt PyTorch mit; das in der
#: venv zu haben, aus der PyInstaller das Paket baut, wäre eine
#: Abhängigkeitskette, die mit Solidon nichts zu tun hat. Aufgerufen wird es
#: deshalb wie ffmpeg — als fremdes Programm, siehe
#: ``tools/speak_chatterbox.py``.
VOICE_PYTHON = Path(__file__).resolve().parent.parent / ".venv-tts" / "Scripts" / "python.exe"
VOICE_SCRIPT = Path(__file__).resolve().parent / "speak_chatterbox.py"
VOICE_REFERENCE = Path(__file__).resolve().parent / "voice-reference.wav"


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
            "closing",
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
            "closing",
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
            "closing",
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
            "closing",
            "And if you own more cutlery, you print another compartment. Solidon.",
        ),
    ),
}

#: Die Drehbücher unter ihren Namen. Vorgabe ist das Einstiegsvideo.
#: Weg 1 — ein fremdes Modell anpassen.
#:
#: **Ohne Morph-Szene**, und das ist keine Sparsamkeit: Ein eingelesenes
#: Modell hat keine benannten Parameter, und `morph_step` steigt bei einem
#: unbekannten Namen still aus. Das Video zeigte an dieser Stelle
#: hundertzwanzig Bilder Stillstand. `record` fällt bei jedem Szenennamen,
#: den es nicht kennt, auf eine Kreisbahn zurück — das ist die richtige
#: Bewegung für ein Teil, dessen Änderung man von einer Seite sieht.
ANPASSEN: dict[str, tuple[tuple[str, str], ...]] = {
    "de": (
        (
            "hook",
            "Eine heruntergeladene Datei. Sie passt fast — nur das eine Loch fehlt.",
        ),
        (
            "turn",
            "Solidon liest sie ein, repariert das Netz und setzt sie aufs "
            "Bett. Dann klicken Sie auf die Stelle, die stört.",
        ),
        (
            "closing",
            "Aus fremd wird deins.",
        ),
    ),
    "en": (
        (
            "hook",
            "A downloaded file. It almost fits — one hole is missing.",
        ),
        (
            "turn",
            "Solidon reads it, repairs the mesh and places it on the bed. "
            "Then you click the spot that bothers you.",
        ),
        (
            "closing",
            "Someone else's file becomes yours.",
        ),
    ),
}

#: Weg 3 — aus Text oder Bild ein druckbares Teil.
#:
#: Ohne Morph, aus demselben Grund wie bei :data:`ANPASSEN`: Ein generiertes
#: Modell kommt ohne benannte Parameter herein. Es kommt auch ohne Maßstab —
#: die Eule maß 1,9 Einheiten, und was Solidon zuerst mit ihr tut, ist ihr
#: eine Größe zu geben.
GENERIEREN: dict[str, tuple[tuple[str, str], ...]] = {
    "de": (
        (
            "hook",
            "Ein Satz Text, ein Modell. Was ein Generator liefert, ist noch "
            "kein Druckteil: keine Größe, zu fein vernetzt, beliebig gedreht.",
        ),
        (
            "turn",
            "Solidon setzt den Maßstab, bringt die Auflösung auf ein Maß, mit "
            "dem sich arbeiten lässt, und sucht die Lage mit den wenigsten "
            "Stützen.",
        ),
        (
            "closing",
            "Vom Einfall zum Bauteil.",
        ),
    ),
    "en": (
        (
            "hook",
            "One line of text, one model. What a generator hands you is not "
            "yet a printable part: no scale, too dense, arbitrarily rotated.",
        ),
        (
            "turn",
            "Solidon sets the scale, brings the mesh down to a size you can "
            "work with, and finds the orientation that needs the fewest "
            "supports.",
        ),
        (
            "closing",
            "From idea to part.",
        ),
    ),
}

#: Weg 4 — Formen, die kein Maß haben.
#:
#: Wieder ohne Morph, und hier ist es die Aussage selbst: Ein geformter Körper
#: hat keine benannten Parameter, weil das der Punkt dieses Weges ist. Der
#: Schlusssatz nennt, was kein Sculpting-Programm mitliefert — der ganze
#: Vorgang bleibt ein Schritt im Verlauf und damit rücknehmbar.
FORMEN: dict[str, tuple[tuple[str, str], ...]] = {
    "de": (
        (
            "hook",
            "Manche Formen haben kein Maß. Eine Fingermulde ist keine Zahl — sie ist eine Hand.",
        ),
        (
            "turn",
            "Grundkörper zusammensetzen, weich verschmelzen, gleichmäßig "
            "vernetzen, dann mit dem Pinsel ausformen. Die Wandstärke läuft "
            "dabei mit.",
        ),
        (
            "closing",
            "Von Hand geformt, und trotzdem rücknehmbar.",
        ),
    ),
    "en": (
        (
            "hook",
            "Some shapes have no dimension. A finger groove is not a number — it is a hand.",
        ),
        (
            "turn",
            "Combine primitives, blend them smoothly, remesh evenly, then "
            "sculpt. Wall thickness updates as you go.",
        ),
        (
            "closing",
            "Shaped by hand, and still undoable.",
        ),
    ),
}

#: Das kurze Beweisvideo zur Merkmalsbearbeitung auf einem eingelesenen Netz.
#:
#: Die Frage des All3DP-Redakteurs vom 04.09.2026 trifft genau den Punkt, den
#: ein gewöhnlicher Bildschirmfilm nicht beantwortet: Wird erst ein CAD-Körper
#: rekonstruiert, oder arbeitet Solidon wirklich am Netz? Deshalb nennt der
#: erste Satz ausdrücklich STL, Dreiecke und den fehlenden CAD-Verlauf. Danach
#: zeigt die Aufnahme nicht bloß zwei gleich aussehende Löcher, sondern dieselbe
#: Kennung vor und nach der Operation. Das ist der Beleg für den Unterschied
#: zwischen „schließen und neu bohren“ und ``move_feature``.
FEATURE_EDITING: dict[str, tuple[tuple[str, str], ...]] = {
    "de": (
        (
            "mesh",
            "Hier liegt wirklich nur eine STL. Dreiecke, sonst nichts. Kein CAD-Verlauf.",
        ),
        (
            "recognise",
            "Ich klicke auf diese Bohrung. Solidon erkennt fünf Komma eins neun "
            "Millimeter: ein Durchgangsloch für M fünf.",
        ),
        (
            "preview_feature",
            "Rechts ändere ich die X-Position, von minus fünfundzwanzig auf minus zehn "
            "Millimeter. Schon in der Vorschau wandert die Bohrung.",
        ),
        (
            "apply_feature",
            "Jetzt übernehme ich die Änderung. Es bleibt dieselbe Bohrung, mit derselben "
            "Kennung. Deshalb verlieren Passungen und spätere Schritte nicht ihren Bezug.",
        ),
        (
            "closing",
            "Eine STL ändern, ohne sie in CAD nachzubauen. Das ist Solidon.",
        ),
    ),
    "en": (
        (
            "mesh",
            "This really is just an STL. Triangles, nothing else. No CAD history.",
        ),
        (
            "recognise",
            "I click this hole. Solidon recognises 5.19 millimetres: an M5 clearance hole.",
        ),
        (
            "preview_feature",
            "On the right, I change X from minus 25 to minus 10 millimetres. "
            "The hole moves in the preview.",
        ),
        (
            "apply_feature",
            "Now I apply the change. It is still the same hole, with the same identity. "
            "That is why fits and later steps keep their reference.",
        ),
        (
            "closing",
            "Change an STL without rebuilding it in CAD. That is Solidon.",
        ),
    ),
}

#: Fünf kurze Belege für Redaktionen. Jeder beantwortet genau eine Aussage
#: aus der Pressemitteilung vom 04.09.2026 und bleibt deshalb auch eingebettet
#: in einem Artikel verständlich. Englisch steht zuerst, weil die konkrete
#: Rückfrage von All3DP kam. Die deutschen Fassungen laufen zeitversetzt im
#: selben Zweitagesrhythmus, damit jede Sprache eine eigene Zielgruppe erreicht,
#: ohne dass zwei nahezu gleiche Shorts am selben Tag gegeneinander antreten.
PRESS_RESIZE: dict[str, tuple[tuple[str, str], ...]] = {
    "de": (
        ("recognise", "Solidon erkennt eine Montagebohrung direkt in einer echten STL."),
        ("resize_preview", "Durchmesser ändern und das Ergebnis vorab sehen."),
        ("resize_apply", "Dieselbe erkannte Bohrung behält ihre Kennung in neuer Größe."),
        ("closing", "Ein Merkmal ändern, ohne das Teil neu aufzubauen."),
    ),
    "en": (
        ("recognise", "Solidon recognises a mounting hole directly in a real STL."),
        ("resize_preview", "Change its diameter and see the result before applying it."),
        ("resize_apply", "The same recognised hole keeps its identity at the new size."),
        ("closing", "Resize a feature without rebuilding the part."),
    ),
}

PRESS_APPLY_ALL: dict[str, tuple[tuple[str, str], ...]] = {
    "de": (
        ("recognise", "Eine von fünf gleichen Bohrungen in der importierten STL wählen."),
        ("all_prepare", "Einen Durchmesser für alle gleichen Merkmale festlegen."),
        ("all_apply", "Alle fünf Bohrungen ändern sich in einer Transaktion."),
        ("closing", "Eine Änderung für das gesamte Bohrungsmuster."),
    ),
    "en": (
        ("recognise", "Select one of five matching holes in the imported STL."),
        ("all_prepare", "Set one diameter and apply it to every matching feature."),
        ("all_apply", "All five holes change in one transaction and one undo."),
        ("closing", "One edit for the whole hole pattern."),
    ),
}

PRESS_DISTANCE: dict[str, tuple[tuple[str, str], ...]] = {
    "de": (
        ("recognise", "Die erste erkannte Bohrung in der importierten STL wählen."),
        ("pair_select", "Eine zweite Bohrung zur Auswahl hinzufügen."),
        ("distance_result", "Solidon zeigt Mittenabstand und Achsversatz sofort an."),
        ("closing", "Vor dem Druck prüfen, ob das Teil wirklich passt."),
    ),
    "en": (
        ("recognise", "Select the first recognised hole in the imported STL."),
        ("pair_select", "Add a second hole to the selection."),
        ("distance_result", "Solidon reports the centre distance and every axis offset."),
        ("closing", "Check whether a downloaded part will fit before printing."),
    ),
}

PRESS_DUPLICATE: dict[str, tuple[tuple[str, str], ...]] = {
    "de": (
        ("recognise", "Eine erkannte Bohrung in der importierten STL wählen."),
        ("duplicate_preview", "Die neue Position des Duplikats in der Vorschau festlegen."),
        ("duplicate_apply", "Die neue Bohrung entsteht, ohne das Teil neu aufzubauen."),
        ("closing", "Ein STL-Merkmal so direkt duplizieren wie in CAD."),
    ),
    "en": (
        ("recognise", "Select a recognised hole in the imported STL."),
        ("duplicate_preview", "Choose the position of its duplicate with a live preview."),
        ("duplicate_apply", "The new hole appears without rebuilding the surrounding part."),
        ("closing", "Duplicate an STL feature as directly as a CAD feature."),
    ),
}

PRESS_REMOVE: dict[str, tuple[tuple[str, str], ...]] = {
    "de": (
        ("recognise", "Eine erkannte Bohrung in der importierten STL wählen."),
        ("remove_apply", "Das Merkmal entfernen, während der STL-Körper bleibt."),
        ("remove_undo", "Ein Strg+Z stellt die vollständige Änderung wieder her."),
        ("closing", "Merkmalsbearbeitung, die vollständig rücknehmbar bleibt."),
    ),
    "en": (
        ("recognise", "Select a recognised hole in the imported STL."),
        ("remove_apply", "Remove the feature while the surrounding STL body stays."),
        ("remove_undo", "One Ctrl+Z restores the complete edit."),
        ("closing", "Feature editing that remains non-destructive."),
    ),
}

SCRIPTS = {
    "einstieg": OPENING,
    "parametrik": STORYBOARD,
    "modular": MODULAR,
    "anpassen": ANPASSEN,
    "generieren": GENERIEREN,
    "formen": FORMEN,
    "merkmal": FEATURE_EDITING,
    "presse-groesse": PRESS_RESIZE,
    "presse-alle": PRESS_APPLY_ALL,
    "presse-abstand": PRESS_DISTANCE,
    "presse-duplizieren": PRESS_DUPLICATE,
    "presse-entfernen": PRESS_REMOVE,
}

#: Drehbücher, die den echten Merkmalsweg mit Zeiger, Text im Bild und eigener
#: Musik aufnehmen. Der Name entscheidet zugleich den eindeutigen Dateistamm.
FEATURE_SHORT_STEMS = {
    "merkmal": "solidon3d-stl-feature",
    "presse-groesse": "solidon3d-press-resize-hole",
    "presse-alle": "solidon3d-press-change-five-holes",
    "presse-abstand": "solidon3d-press-measure-hole-spacing",
    "presse-duplizieren": "solidon3d-press-duplicate-hole",
    "presse-entfernen": "solidon3d-press-remove-hole",
}
FEATURE_SHORT_SCRIPTS = frozenset(FEATURE_SHORT_STEMS)

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

#: Ziel der sichtbaren Probe. Fünfzehn Millimeter sind im Bild deutlich; die
#: Operation selbst arbeitet selbstverständlich auch mit kleineren Wegen.
FEATURE_DEMO_TARGET_X = -10.0

#: Szenen, die den Merkmalsbeweis aufbauen. Der Name ist Teil des Vertrags mit
#: :func:`prepare_feature_demo_scene`; ein Tippfehler soll dort auffallen und
#: nicht still auf eine Kreisfahrt zurückfallen.
FEATURE_DEMO_SCENES = frozenset(
    {
        "mesh",
        "recognise",
        "preview_feature",
        "apply_feature",
        "resize_preview",
        "resize_apply",
        "all_prepare",
        "all_apply",
        "pair_select",
        "distance_result",
        "duplicate_preview",
        "duplicate_apply",
        "remove_apply",
        "remove_undo",
    }
)

#: Der stumme Merkmalsfilm bekommt eine feste, bewusst knappe Uhr. Die
#: Einblendungen brauchen weniger Zeit als ein Sprecher; sieben Sekunden für
#: Eingabe und Übernehmen lassen den tatsächlichen Mausweg dennoch lesbar.
FEATURE_SCENE_SECONDS = {
    "mesh": 4.0,
    "recognise": 5.0,
    "preview_feature": 7.0,
    "apply_feature": 7.0,
    "resize_preview": 6.0,
    "resize_apply": 5.0,
    "all_prepare": 6.0,
    "all_apply": 5.0,
    "pair_select": 5.0,
    "distance_result": 5.0,
    "duplicate_preview": 6.0,
    "duplicate_apply": 5.0,
    "remove_apply": 6.0,
    "remove_undo": 5.0,
    "closing": 4.0,
}

#: Was statt einer künstlichen Stimme im Bild steht. Titel nennen die
#: Handlung, die zweite Zeile den Beleg. Der Text liegt tief im Viewport, aber
#: oberhalb der Werkzeugleiste; Objektbaum und Merkmalfenster bleiben frei.
FEATURE_CAPTIONS = {
    "de": {
        "mesh": ("NUR EINE STL", "Dreiecke · kein CAD-Verlauf"),
        "recognise": ("BOHRUNG AUSWÄHLEN", "Erkannt: ⌀ 5,19 mm · M5-Durchgang"),
        "preview_feature": (
            "POSITION DIREKT ÄNDERN",
            "X: -25 mm → -10 mm · Live-Vorschau",
        ),
        "apply_feature": (
            "DIESELBE BOHRUNG BLEIBT ERHALTEN",
            "Kennung hole_1 · Passungen bleiben verbunden",
        ),
        "resize_preview": (
            "DURCHMESSER DIREKT ÄNDERN",
            "Ø 5,44 → 6,50 mm · Live-Vorschau",
        ),
        "resize_apply": (
            "DIESELBE BOHRUNG · NEUE GRÖSSE",
            "Kennung bleibt · Passungen bleiben verbunden",
        ),
        "all_prepare": (
            "EINE ÄNDERUNG FÜR FÜNF BOHRUNGEN",
            "Auf alle gleichen Merkmale anwenden",
        ),
        "all_apply": (
            "FÜNF BOHRUNGEN · EIN UNDO",
            "Eine Transaktion ändert das ganze Muster",
        ),
        "pair_select": (
            "ZWEI BOHRUNGEN AUSWÄHLEN",
            "Kein eigenes Messwerkzeug nötig",
        ),
        "distance_result": (
            "MITTENABSTAND",
            "Gesamt und X / Y / Z erscheinen sofort",
        ),
        "duplicate_preview": (
            "ERKANNTE BOHRUNG DUPLIZIEREN",
            "Neue Position wählen · Live-Vorschau",
        ),
        "duplicate_apply": (
            "NEUE BOHRUNG · KEIN NEUBAU",
            "Das ursprüngliche Merkmal bleibt erhalten",
        ),
        "remove_apply": (
            "BOHRUNG ENTFERNEN · NICHT DAS TEIL",
            "Der umgebende STL-Körper bleibt erhalten",
        ),
        "remove_undo": (
            "EIN STRG+Z HOLT SIE ZURÜCK",
            "Die vollständige Änderung bleibt rücknehmbar",
        ),
    },
    "en": {
        "mesh": ("JUST AN STL", "Triangles · no CAD history"),
        "recognise": ("SELECT THE HOLE", "Recognised: ⌀ 5.19 mm · M5 clearance"),
        "preview_feature": (
            "CHANGE ITS POSITION DIRECTLY",
            "X: -25 mm → -10 mm · live preview",
        ),
        "apply_feature": (
            "THE SAME HOLE IS PRESERVED",
            "Identity hole_1 · fits stay connected",
        ),
        "resize_preview": (
            "CHANGE THE DIAMETER DIRECTLY",
            "Ø 5.44 → 6.50 mm · live preview",
        ),
        "resize_apply": (
            "SAME HOLE · NEW SIZE",
            "Identity preserved · later fits stay attached",
        ),
        "all_prepare": (
            "ONE CHANGE FOR FIVE HOLES",
            "Apply to all matching features",
        ),
        "all_apply": (
            "FIVE HOLES · ONE UNDO",
            "A single transaction changes the pattern",
        ),
        "pair_select": (
            "SELECT TWO HOLES",
            "No separate measuring tool",
        ),
        "distance_result": (
            "CENTRE-TO-CENTRE DISTANCE",
            "Total and X / Y / Z appear immediately",
        ),
        "duplicate_preview": (
            "DUPLICATE THE RECOGNISED HOLE",
            "Choose its new position · live preview",
        ),
        "duplicate_apply": (
            "A NEW HOLE · NO REBUILD",
            "The original feature stays intact",
        ),
        "remove_apply": (
            "REMOVE THE HOLE · NOT THE PART",
            "The surrounding STL body remains",
        ),
        "remove_undo": (
            "ONE CTRL+Z BRINGS IT BACK",
            "The complete edit stays reversible",
        ),
    },
}

#: Nach dem tatsächlichen Klick trennt ein kurzer Ergebnisstreifen die
#: bestätigte Operation von ihrer unmittelbar davor gezeigten Vorschau. Ohne
#: diese zweite Kodierung sieht ein korrektes Übernehmen im Film wie ein
#: wirkungsloser Klick aus, weil Vorschau und Ergebnis dieselbe Geometrie
#: zeigen. Der Streifen ist eine Filmeinblendung und kein nachgebautes
#: Bedienelement der Anwendung.
FEATURE_COMMIT_BADGES = {
    "de": {
        "apply_feature": "ANGEWENDET · 1 UNDO-SCHRITT",
        "resize_apply": "ANGEWENDET · 1 UNDO-SCHRITT",
        "all_apply": "5 BOHRUNGEN ANGEWENDET · 1 UNDO",
        "duplicate_apply": "DUPLIZIERT · 1 UNDO-SCHRITT",
        "remove_apply": "ENTFERNT · 1 UNDO-SCHRITT",
    },
    "en": {
        "apply_feature": "APPLIED · 1 UNDO STEP",
        "resize_apply": "APPLIED · 1 UNDO STEP",
        "all_apply": "5 HOLES APPLIED · 1 UNDO",
        "duplicate_apply": "DUPLICATED · 1 UNDO STEP",
        "remove_apply": "REMOVED · 1 UNDO STEP",
    },
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

#: Die Kette, die aus einer Sprachausgabe einen Sendeton macht. Sie bleibt für
#: die übrigen Filme erhalten; der Merkmalsfilm benutzt bewusst Originalmusik
#: und eingeblendeten Text. Die Lautheit hängt weiterhin getrennt hinten an
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


def await_result(app: QApplication, session: object, seconds: float = 900.0) -> bool:
    """Warten, bis die Auswertung durch ist.

    Sie läuft in einem Arbeitsfaden (§15.6), also genügt kein Stapel
    ``processEvents``: ohne das Warten filmt das Werkzeug den Startbildschirm.

    **Fünfzehn Minuten und nicht eine**, seit dem 31.08.2026 — und die
    Begründung ist enger, als sie zuerst hier stand.

    Belegt ist: Ein dichtes importiertes Modell kann beim Öffnen rund eine
    Minute kosten, wenn ``orient_for_print`` auf hunderttausend Dreiecken
    rechnet. Sechzig Sekunden sind dafür genau an der Grenze, und was dann
    kommt, ist der Satz „Das Projekt rechnete nicht fertig" — er klingt nach
    Fehler und meint Langsamkeit.

    **Nicht belegt und deshalb hier nicht mehr behauptet:** Frühere Fassungen
    dieses Docstrings nannten 574 und 909 CPU-Sekunden für zwei andere
    Projekte. Diese Zahlen waren echt, aber falsch zugeordnet — es war die
    CPU-Zeit **ganzer Läufe**, nicht die einer Phase, und zugeschrieben wurde
    sie dem Öffnen, weil die Ausgabe an dieser Stelle stehenblieb. Sie blieb
    stehen, weil Python puffert. Gemessen hat eine Nachbarsitzung dieselbe
    Datei danach mit **0,96 s**.

    Die lange Marke bleibt trotzdem: Sie kostet nichts, solange nichts hängt,
    und ein Hänger ist an der stillstehenden CPU-Zeit des Prozesses zu
    erkennen — nicht an dieser Marke.
    """
    deadline = time.monotonic() + seconds
    started = time.monotonic()
    reported = 0.0
    while time.monotonic() < deadline:
        app.processEvents()
        if getattr(session, "last_result", None) is not None:
            settle(app)
            return True
        # Alle dreißig Sekunden eine Zeile: Ein Werkzeug, das eine
        # Viertelstunde schweigt, sieht aus, als hinge es.
        waited = time.monotonic() - started
        if waited - reported >= 30.0:
            reported = waited
            print(f"  … rechnet seit {waited:.0f} s")
        time.sleep(0.05)
    return False


def _open_video_input(session: Any, source: Path) -> None:
    """Ein Projekt öffnen oder ein Modell über den sichtbaren Importweg einlesen."""
    if source.suffix.lower() == ".p3d":
        session.open_project(source)
        return
    session.start_new()
    session.import_model(source, raise_on_error=True)


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
    target = getattr(getattr(viewport, "renderer", None), "widget", None) or viewport
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
    renderer = getattr(getattr(window, "viewport", None), "renderer", None)
    if renderer is not None:
        renderer.render()
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
    voice_stamp = hashlib.sha256()
    for source in (VOICE_SCRIPT, VOICE_REFERENCE):
        if not source.is_file():
            raise SystemExit(f"Die Sprachquelle fehlt: {source}")
        voice_stamp.update(source.read_bytes())
    voice_version = voice_stamp.hexdigest()
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
        expected_stamp = f"{voice_version}\n{text}"
        cached = stamp.is_file() and stamp.read_text(encoding="utf-8") == expected_stamp
        if cached and ready.is_file():
            print(f"  {key:12s} {audio_duration(ready) + SCENE_TAIL:5.1f} s (unverändert)")
        else:
            speak(text, language, raw)
            polish(raw, ready)
            stamp.write_text(expected_stamp, encoding="utf-8")
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
        # Die Konkatenationsliste wird relativ zu ihrem eigenen Ordner
        # gelesen. Stand hier der ebenfalls relative Zielpfad, setzte ffmpeg
        # beides zusammen (``ziel/ziel/audio/...``) und fand keinen Ton.
        # Ein absoluter Schrägstrichpfad gilt unter Windows und Unix gleich.
        lines.append(f"file '{padded.resolve().as_posix()}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(target)])


def _subtitle_stamp(seconds: float) -> str:
    """Eine Zeitangabe im SRT-Format, ohne Rundungsüberlauf."""
    milliseconds = max(0, round(seconds * 1000.0))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def write_subtitles(
    spoken: list[tuple[str, Path, float]],
    scenes: tuple[tuple[str, str], ...],
    target: Path,
) -> Path:
    """Die gesprochenen Sätze als hochladbare YouTube-Untertitel schreiben.

    Jeder Tonbaustein trägt hinten :data:`SCENE_TAIL` Sekunden Pause. Die
    Untertitel enden vor dieser Pause, während die nächste Szene erst danach
    beginnt. Dadurch bleibt zwischen zwei Sätzen derselbe Atemraum wie im Ton.
    """
    if len(spoken) != len(scenes):
        raise ValueError("Ton und Drehbuch haben verschieden viele Szenen")
    elapsed = 0.0
    blocks: list[str] = []
    for number, ((spoken_key, _path, duration), (scene_key, sentence)) in enumerate(
        zip(spoken, scenes, strict=True), start=1
    ):
        if spoken_key != scene_key:
            raise ValueError(f"Ton {spoken_key!r} gehört nicht zu Szene {scene_key!r}")
        audible_end = elapsed + max(0.0, duration - SCENE_TAIL)
        blocks.append(
            f"{number}\n{_subtitle_stamp(elapsed)} --> {_subtitle_stamp(audible_end)}\n{sentence}"
        )
        elapsed += duration
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n\n".join(blocks) + "\n", encoding="utf-8-sig")
    print(f"  Text  → {target.name}")
    return target


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


def feature_timing(scenes: tuple[tuple[str, str], ...]) -> list[tuple[str, Path, float]]:
    """Die feste Bildzeit des Merkmalsfilms in Drehbuchreihenfolge liefern."""
    missing = [key for key, _text in scenes if key not in FEATURE_SCENE_SECONDS]
    if missing:
        raise ValueError(f"Keine Bildzeit für Merkmalsfilmszene: {', '.join(missing)}")
    return [(key, Path(), FEATURE_SCENE_SECONDS[key]) for key, _text in scenes]


def write_feature_music(target: Path, seconds: float) -> Path:
    """Ein eigenes, deterministisches Musikbett für den Merkmalsfilm bauen.

    Alle Töne entstehen hier aus Sinusschwingungen; weder Komposition noch
    Aufnahme stammen von Dritten. Damit reist kein GEMA- oder Plattformrecht
    mit dem Film. Die drei kurzen Akzente liegen exakt auf den sichtbaren
    Klicks, ohne wie nachträglich angeklebte Mausklick-Geräusche zu wirken.
    """
    import wave

    import numpy as np

    rate = 48_000
    count = max(1, round(seconds * rate))
    time_axis = np.arange(count, dtype=np.float64) / rate
    stereo = np.zeros((count, 2), dtype=np.float64)
    chords = (
        (146.83, 220.00, 293.66, 349.23),
        (116.54, 174.61, 233.08, 293.66),
        (130.81, 196.00, 261.63, 349.23),
        (130.81, 196.00, 261.63, 329.63),
    )
    span = seconds / len(chords)
    overlap = min(1.2, span / 3.0)
    for chord_index, frequencies in enumerate(chords):
        start = chord_index * span - (overlap if chord_index else 0.0)
        end = (chord_index + 1) * span + (overlap if chord_index < len(chords) - 1 else 0.0)
        local = time_axis - start
        envelope = np.clip(local / overlap, 0.0, 1.0)
        envelope *= np.clip((end - time_axis) / overlap, 0.0, 1.0)
        envelope = np.sin(envelope * math.pi / 2.0) ** 2
        for note_index, frequency in enumerate(frequencies):
            weight = 0.055 / (1.0 + note_index * 0.22)
            phase = chord_index * 0.73 + note_index * 0.41
            left = np.sin(2.0 * math.pi * frequency * time_axis + phase)
            right = np.sin(2.0 * math.pi * frequency * 1.0015 * time_axis + phase + 0.18)
            # Eine leise Oktave gibt Kontur, ohne aus dem Pad eine Melodie zu
            # machen. Unter Sprache läge sie im Weg; hier trägt sie den Film.
            left += 0.15 * np.sin(4.0 * math.pi * frequency * time_axis + phase)
            right += 0.15 * np.sin(4.0 * math.pi * frequency * 0.9985 * time_axis + phase + 0.18)
            stereo[:, 0] += weight * envelope * left
            stereo[:, 1] += weight * envelope * right

    # Ruhiger Puls, nicht Schlagzeug: Er gibt dem sonst völlig geraden
    # Bildschirmfilm Bewegung, bleibt aber unter der Bedienung.
    for beat in np.arange(0.8, seconds, 1.5):
        local = time_axis - beat
        active = (local >= 0.0) & (local < 0.32)
        pulse = np.zeros(count, dtype=np.float64)
        pulse[active] = (
            np.sin(2.0 * math.pi * (68.0 * local[active] - 18.0 * local[active] ** 2))
            * np.exp(-local[active] * 13.0)
            * 0.09
        )
        stereo[:, 0] += pulse
        stereo[:, 1] += pulse

    scene_starts: dict[str, float] = {}
    elapsed = 0.0
    for key, duration in FEATURE_SCENE_SECONDS.items():
        scene_starts[key] = elapsed
        elapsed += duration
    click_times = (
        scene_starts["recognise"] + FEATURE_SCENE_SECONDS["recognise"] * 0.48,
        scene_starts["preview_feature"] + FEATURE_SCENE_SECONDS["preview_feature"] * 0.32,
        scene_starts["apply_feature"] + FEATURE_SCENE_SECONDS["apply_feature"] * 0.38,
    )
    for click in click_times:
        local = time_axis - click
        active = (local >= 0.0) & (local < 0.09)
        accent = np.zeros(count, dtype=np.float64)
        accent[active] = (
            np.sin(2.0 * math.pi * 1250.0 * local[active]) * np.exp(-local[active] * 48.0) * 0.13
        )
        stereo[:, 0] += accent
        stereo[:, 1] += accent

    master = np.ones(count, dtype=np.float64)
    fade = min(count // 2, round(rate * 0.9))
    master[:fade] = np.sin(np.linspace(0.0, math.pi / 2.0, fade)) ** 2
    master[-fade:] = np.sin(np.linspace(math.pi / 2.0, 0.0, fade)) ** 2
    stereo *= master[:, None]
    rms = float(np.sqrt(np.mean(stereo * stereo)))
    if rms > 0.0:
        stereo *= min(0.12 / rms, 0.78 / float(np.max(np.abs(stereo))))
    pcm = np.round(np.clip(stereo, -1.0, 1.0) * 32767.0).astype("<i2")
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(pcm.tobytes())
    print(f"  Musik → {target.name}  {seconds:.1f} s · eigene Komposition")
    return target


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
    renderer = viewport.renderer
    screen = window.screen() or QApplication.primaryScreen()

    viewport.reset_camera()
    settle(app, 20)

    pose = renderer.camera_pose()
    focal = pose.focal_point
    position = pose.position
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
        _aim_camera(
            renderer,
            (focal[0] + radius * math.cos(angle), focal[1] + radius * math.sin(angle), height),
            focal,
            pose.view_up,
        )
        # Die Schatten hängen an der Blickrichtung (§18.6). Ohne diese Zeile
        # steht das Licht still, während sich das Teil dreht — es sieht aus,
        # als klebte der Schatten am Boden fest.
        redraw = getattr(viewport, "_redraw_shadows", None)
        if callable(redraw):
            redraw()
        renderer.render()
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


@lru_cache(maxsize=1)
def _system_pointer_image() -> Any | None:
    """Den vom Nutzer eingestellten Windows-Pfeil in seiner echten Größe laden.

    ``grabWindow`` lässt den Systemzeiger weg. Unter Windows steht der aktive
    Pfeilpfad jedoch im Cursor-Schema des Nutzers; dadurch kann der Film genau
    dieses Bild ergänzen, statt eine ähnliche Form nachzuzeichnen. Auf anderen
    Plattformen bleibt der bisherige kontrastreiche Ersatz.
    """
    if os.name != "nt":
        return None

    import ctypes
    import winreg

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors") as key:
            path = str(winreg.QueryValueEx(key, "Arrow")[0])
        path = os.path.expandvars(path)
        image = QImage(path)
        if image.isNull():
            return None
        width = max(1, int(ctypes.windll.user32.GetSystemMetrics(13)))
        height = max(1, int(ctypes.windll.user32.GetSystemMetrics(14)))
        return image.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    except (OSError, ValueError):
        return None


def _paint_pointer(frame: Any, mark: tuple[float, float, bool]) -> None:
    """Den echten Systemzeiger und beim tatsächlichen Klick einen Ring zeichnen."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

    x, y, pressed = mark
    painter = QPainter(frame)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    if pressed:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#e08b4e"), 3.0))
        painter.drawEllipse(QPointF(x, y), 16.0, 16.0)
    pointer = _system_pointer_image()
    if pointer is not None:
        painter.drawImage(QPointF(x, y), pointer)
    else:
        path = QPainterPath(QPointF(x, y))
        path.lineTo(x + 1.0, y + 26.0)
        path.lineTo(x + 7.5, y + 20.0)
        path.lineTo(x + 14.0, y + 32.0)
        path.lineTo(x + 19.0, y + 29.0)
        path.lineTo(x + 13.0, y + 17.0)
        path.lineTo(x + 22.0, y + 17.0)
        path.closeSubpath()
        painter.setPen(QPen(QColor("#14161a"), 3.0))
        painter.setBrush(QColor("#f7f9fb"))
        painter.drawPath(path)
    painter.end()


def _paint_feature_caption(
    frame: Any,
    caption: tuple[str, str],
    index: int,
    total: int,
) -> None:
    """Eine ruhige Zweizeilen-Einblendung in den freien unteren Viewport setzen."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPainter

    edge = max(1, round(FPS * 0.22))
    alpha = min(1.0, (index + 1) / edge, (total - index) / edge)
    width = min(1080.0, frame.width() - 520.0)
    box = QRectF((frame.width() - width) / 2.0, frame.height() - 218.0, width, 112.0)
    painter = QPainter(frame)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setOpacity(alpha)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(16, 19, 24, 224))
    painter.drawRoundedRect(box, 12.0, 12.0)
    painter.setBrush(QColor("#e08b4e"))
    painter.drawRoundedRect(QRectF(box.left(), box.top(), 6.0, box.height()), 3.0, 3.0)

    title_font = QFont("Segoe UI", 24)
    title_font.setWeight(QFont.Weight.DemiBold)
    painter.setFont(title_font)
    painter.setPen(QColor("#f5f7fa"))
    painter.drawText(
        QRectF(box.left() + 34.0, box.top() + 14.0, box.width() - 58.0, 37.0),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        caption[0],
    )
    detail_font = QFont("Segoe UI", 18)
    painter.setFont(detail_font)
    painter.setPen(QColor("#b7c0cb"))
    painter.drawText(
        QRectF(box.left() + 34.0, box.top() + 55.0, box.width() - 58.0, 38.0),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        caption[1],
    )
    painter.end()


def record(
    window: QWidget,
    app: QApplication,
    frames: Path,
    start: int,
    count: int,
    step: Callable[[int, int], None],
    pointer: PointerFn | None = None,
    caption: tuple[str, str] | None = None,
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
        shot = screen.grabWindow(window.winId())
        if caption is not None:
            _paint_feature_caption(shot, caption, index, count)
        mark = pointer(index, count) if pointer is not None else None
        if mark is not None:
            _paint_pointer(shot, mark)
        shot.save(str(frames / f"{start + index:05d}.png"))
    return start + count


def orbit_step(
    window: QWidget,
    app: QApplication,
    zoom: float,
    turns: float,
    start_degrees: float = 0.0,
) -> StepFn:
    """Eine Kreisbahn um den Blickpunkt, als Schrittfunktion für :func:`record`.

    Dieselbe Rechnung wie in :func:`orbit`, nur portionsweise: die Kamera wird
    gesetzt statt gedreht, damit sich über hundert Bilder nichts aufsummiert.

    **``start_degrees`` entscheidet, was im Standbild steht.** ``reset_camera``
    liefert immer denselben Blick, und der ist für ein konstruiertes Teil
    richtig — es steht so, wie es gezeichnet wurde. Ein generiertes oder für
    den Druck gedrehtes Teil steht dagegen, wie die Schichtanalyse es hingelegt
    hat, und das ist keine Ansicht, sondern ein Ergebnis. Beim ersten
    Eulen-Loop war Bild 0 der schlechteste Winkel der ganzen Aufnahme — und
    genau dieses Bild wird zum ``poster``, das bei ``preload="none"`` und bei
    reduzierter Bewegung das einzige ist, was der Besucher je sieht.
    """
    viewport = window.viewport  # type: ignore[attr-defined]
    renderer = viewport.renderer
    viewport.reset_camera()
    settle(app, 20)
    pose = renderer.camera_pose()
    focal = pose.focal_point
    position = pose.position
    offset_x, offset_y = position[0] - focal[0], position[1] - focal[1]
    radius = math.hypot(offset_x, offset_y) * zoom
    height = focal[2] + (position[2] - focal[2]) * zoom
    start_angle = math.atan2(offset_y, offset_x) + math.radians(start_degrees)

    def step(index: int, total: int) -> None:
        angle = start_angle + 2.0 * math.pi * turns * index / max(1, total)
        _aim_camera(
            renderer,
            (focal[0] + radius * math.cos(angle), focal[1] + radius * math.sin(angle), height),
            focal,
            pose.view_up,
        )
        redraw = getattr(viewport, "_redraw_shadows", None)
        if callable(redraw):
            redraw()
        renderer.render()

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
    renderer = viewport.renderer
    pose = renderer.camera_pose()
    focal = pose.focal_point
    start = pose.position

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
        _aim_camera(
            renderer,
            (
                focal[0] + (start[0] - focal[0]) * away,
                focal[1] + (start[1] - focal[1]) * away,
                focal[2] + (start[2] - focal[2]) * away,
            ),
            focal,
            pose.view_up,
        )
        redraw = getattr(viewport, "_redraw_shadows", None)
        if callable(redraw):
            redraw()
        renderer.render()

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
    renderer = viewport.renderer
    viewport.reset_camera()
    settle(app, 20)
    pose = renderer.camera_pose()
    focal = pose.focal_point
    position = pose.position
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
        _aim_camera(
            renderer,
            (focal[0] + radius * math.cos(angle), focal[1] + radius * math.sin(angle), height),
            focal,
            pose.view_up,
        )
        redraw = getattr(viewport, "_redraw_shadows", None)
        if callable(redraw):
            redraw()
        renderer.render()

    return step


def hold_step(window: QWidget, app: QApplication) -> StepFn:
    """Stehen bleiben — für Szenen, in denen der Text die Arbeit macht."""
    renderer = getattr(getattr(window, "viewport", None), "renderer", None)

    def step(index: int, total: int) -> None:
        if renderer is not None:
            renderer.render()

    return step


def _feature_target_id(session: Any) -> str:
    """Die für den Film gewählte, über alle Szenen feste Merkmalskennung."""
    return str(getattr(session, "_video_feature_id", "hole_1"))


def _feature_demo_target(session: Any) -> tuple[str, str, Any]:
    """Den einen belegten Zielpunkt des Merkmalsfilms finden.

    Die Kennung wird absichtlich verlangt statt durch „die erste Bohrung“
    ersetzt: Genau ihre Beständigkeit ist die Aussage des Films. Würde die
    Erkennung sie anders benennen, soll der Lauf anhalten, bevor ein falscher
    Beleg entsteht.
    """
    result = session.last_result
    if result is None:
        raise SystemExit("Keine ausgewertete Szene für den Merkmalsfilm")
    target_id = _feature_target_id(session)
    for object_id, entry in result.scene.objects.items():
        feature = entry.features.get(target_id)
        if feature is not None and feature.kind == "hole":
            return object_id, target_id, feature
    raise SystemExit(f"Der Merkmalsfilm braucht die erkannte Bohrung {target_id}")


def _feature_action_row(window: Any, op: str) -> tuple[list[Any], Any, Any | None]:
    """Felder, Knopf und Sammelhaken einer sichtbaren Merkmalshandlung.

    Gesucht wird über den Registertitel und nicht über die Reihenfolge aller
    Eingabefelder. Im Panel stehen X/Y/Z zweimal — einmal fürs Verschieben und
    einmal fürs Duplizieren. „Das erste X-Feld“ wäre damit ein stiller Vertrag
    mit der heutigen Reihenfolge statt mit der gezeigten Handlung.
    """
    from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton

    from app.core.registry import REGISTRY
    from app.ui.labels import LengthSpin

    title = str(REGISTRY.get(op).title)
    for row in window.feature_panel._built:
        fields = row.findChildren(LengthSpin)
        buttons = [button for button in row.findChildren(QPushButton) if button.text() == title]
        labels = [label for label in row.findChildren(QLabel) if label.text() == title]
        if not buttons or (fields and not labels):
            continue
        every = next((box for box in row.findChildren(QCheckBox) if box.text()), None)
        return list(fields), buttons[0], every
    raise SystemExit(f"Im Merkmalfenster fehlt die Handlung {title!r}")


def _feature_move_row(window: Any) -> tuple[Any, Any]:
    """X-Feld und Knopf der sichtbaren Handlung „Merkmal verschieben“."""
    fields, button, _every = _feature_action_row(window, "move_feature")
    if not fields:
        raise SystemExit("Im Merkmalfenster fehlt das X-Feld von „Merkmal verschieben“")
    return fields[0], button


def _feature_holes(session: Any) -> tuple[str, list[tuple[str, Any]]]:
    """Die belegten Bohrungen der Presseplatte in stabiler Reihenfolge."""
    result = session.last_result
    if result is None:
        raise SystemExit("Keine ausgewertete Szene für den Merkmalsfilm")
    target_id = _feature_target_id(session)
    for object_id, entry in result.scene.objects.items():
        holes = sorted(
            (
                (feature_id, feature)
                for feature_id, feature in entry.features.items()
                if feature.kind == "hole"
            ),
            key=lambda pair: pair[0],
        )
        if any(feature_id == target_id for feature_id, _feature in holes):
            return object_id, holes
    raise SystemExit(f"Das Pressemodell mit {target_id} wurde nicht gefunden")


def feature_caption(session: Any, language: str, scene: str) -> tuple[str, str]:
    """Messwert und Anzahl aus dem gezeigten Modell statt aus Werbetext lesen."""
    title, detail = FEATURE_CAPTIONS[language][scene]
    if scene in {"recognise", "resize_preview"}:
        from app.core.scene.placement import screw_for_bore

        _object_id, _feature_id, feature = _feature_demo_target(session)
        diameter = float(feature.params["diameter"])
        size = screw_for_bore(diameter)
        if scene == "resize_preview":
            if language == "de":
                value = f"{diameter:.2f}".replace(".", ",")
                return title, f"Ø {value} → 6,50 mm · Live-Vorschau"
            return title, f"Ø {diameter:.2f} → 6.50 mm · live preview"
        if language == "de":
            value = f"{diameter:.2f}".replace(".", ",")
            suffix = f" · {size}-Durchgang" if size else ""
            return title, f"Erkannt: ⌀ {value} mm{suffix}"
        suffix = f" · {size} clearance" if size else ""
        return title, f"Recognised: Ø {diameter:.2f} mm{suffix}"
    if scene in {"all_prepare", "all_apply"}:
        _object_id, holes = _feature_holes(session)
        count = len(holes)
        words = (
            {2: "ZWEI", 3: "DREI", 4: "VIER", 5: "FÜNF", 6: "SECHS"}
            if language == "de"
            else {2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE", 6: "SIX"}
        )
        word = words.get(count, str(count))
        if scene == "all_prepare":
            title = (
                f"EINE ÄNDERUNG FÜR {word} BOHRUNGEN"
                if language == "de"
                else f"ONE CHANGE FOR {word} HOLES"
            )
            return title, detail
        title = f"{word} BOHRUNGEN · EIN UNDO" if language == "de" else f"{word} HOLES · ONE UNDO"
        return title, detail
    return title, detail


def _wait_for_feature_preview(window: Any, app: QApplication, seconds: float = 120.0) -> None:
    """Auf den entprellten, im Arbeiter gerechneten Merkmalsvergleich warten."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if getattr(window, "_preview_shown", False):
            settle(app, 20)
            return
        time.sleep(0.02)
    raise SystemExit("Die Merkmalsvorschau wurde nicht sichtbar")


def _widget_centre(window: Any, widget: Any) -> tuple[float, float]:
    """Die Mitte eines Bedienelements in Koordinaten des Hauptfensters."""
    from PySide6.QtCore import QPoint

    point = widget.mapTo(window, QPoint(widget.width() // 2, widget.height() // 2))
    return float(point.x()), float(point.y())


def _feature_click(window: Any) -> tuple[Any, tuple[float, float, float], tuple[float, float]]:
    """Eingabeziel und sichtbare Stelle auf der Innenwand der Zielbohrung.

    Die Mitte eines Durchgangslochs ist leer und deshalb kein Klickziel. Der
    Punkt liegt auf seiner zylindrischen Wand, ein Viertel der Tiefe unter der
    Oberseite — dort trifft der Zell-Picker wirklich ein Dreieck des Merkmals.
    """
    from PySide6.QtCore import QPoint

    _object_id, _feature_id, feature = _feature_demo_target(window.session)
    centre = tuple(float(value) for value in feature.params["centre"])
    diameter = float(feature.params["diameter"])
    depth = float(feature.params["depth"])
    world = (centre[0] + diameter / 2.0, centre[1], centre[2] + depth / 4.0)
    viewport = window.viewport
    display = viewport._display_of(world)
    interactor = viewport.renderer.widget
    if display is None:
        raise SystemExit("Die Bohrung ließ sich nicht ins Videobild projizieren")
    ratio = float(interactor.devicePixelRatioF()) or 1.0
    local = QPoint(round(display[0] / ratio), round(display[1] / ratio))
    visible = interactor.mapTo(window, local)
    return interactor, world, (float(visible.x()), float(visible.y()))


def _ease(
    start: tuple[float, float], end: tuple[float, float], share: float
) -> tuple[float, float]:
    """Eine ruhige Mausbewegung zwischen zwei Punkten."""
    clamped = max(0.0, min(1.0, share))
    eased = 0.5 - 0.5 * math.cos(math.pi * clamped)
    return (
        start[0] + (end[0] - start[0]) * eased,
        start[1] + (end[1] - start[1]) * eased,
    )


def feature_demo_step(
    window: Any,
    app: QApplication,
    session: Any,
    scene: str,
) -> tuple[StepFn, PointerFn | None]:
    """Den sichtbaren Bedienweg einer Szene samt gezeichnetem Zeiger bauen.

    Die Maus bewegt sich nicht nur über eine nachträgliche Grafik. Am Klickbild
    schickt ``QTest`` dieselbe Eingabe an Viewport, Zahlenfeld oder Knopf, die
    ein Mensch dort auslösen würde; der gezeichnete Zeiger macht genau diesen
    sonst unsichtbaren Systemzustand im Bildschirmabgriff sichtbar.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    if scene == "mesh":
        return orbit_step(window, app, 1.0, turns=0.18), None

    if scene == "recognise":
        target_id = _feature_target_id(session)
        _interactor, world, feature_point = _feature_click(window)
        viewport = window.viewport.renderer.widget
        start = _widget_centre(window, viewport)
        clicked = False

        def select_step(index: int, total: int) -> None:
            nonlocal clicked
            if not clicked and index >= round(total * 0.48):
                # QTest-Ereignisse endeten am eingebetteten Renderfenster,
                # bevor der Pick sie sah (gemessen unter VTK). ``_select_at``
                # ist genau der UI-Weg nach dem Pick; der projizierte
                # Punkt liegt auf derselben Bohrungswand wie der Zeiger.
                window.viewport._select_at(world)
                app.processEvents()
                if window.object_tree.selected_feature() != target_id:
                    raise SystemExit(f"Der sichtbare Klick hat {target_id} nicht ausgewählt")
                clicked = True
            window.viewport.renderer.render()

        def select_pointer(index: int, total: int) -> tuple[float, float, bool]:
            point = _ease(start, feature_point, index / max(1.0, total * 0.45))
            pressed = abs(index - round(total * 0.48)) <= 2
            return (*point, pressed)

        return select_step, select_pointer

    if scene == "distance_result":
        return hold_step(window, app), None

    if scene == "remove_undo":
        target_id = _feature_target_id(session)
        restored = False

        def undo_step(index: int, total: int) -> None:
            nonlocal restored
            if not restored and index >= round(total * 0.36):
                QTest.keyClick(
                    window,
                    Qt.Key.Key_Z,
                    Qt.KeyboardModifier.ControlModifier,
                )
                session.wait_for_idle(120_000)
                settle(app, 30)
                _object_id, feature_id, _feature = _feature_demo_target(session)
                if feature_id != target_id:
                    raise SystemExit("Strg+Z hat die entfernte Bohrung nicht wiederhergestellt")
                restored = True
            window.viewport.renderer.render()

        return undo_step, None

    if scene == "resize_preview":
        # 5,14 auf 6,50 mm ist eine sinnvolle reale Änderung, aber in der
        # Gesamtansicht nur wenige Pixel breit. Für die Vorschau fährt die
        # Kamera deshalb näher an das ganze Teil. Der Blickpunkt bleibt in der
        # Modellmitte: Ein Flug direkt an die Bohrung zeigte zwar ihr Maß, aber
        # nur noch eine graue Ebene und verlor den Zusammenhang zum Halter.
        # Die Folgeszene behält denselben Zoom für das bestätigte Ergebnis.
        window.viewport.zoom(1.45)
        settle(app, 20)

    _interactor, _world, feature_point = _feature_click(window)

    if scene == "pair_select":
        from app.ui.panels import _feature_item

        object_id, holes = _feature_holes(session)
        target_id = _feature_target_id(session)
        first = next(feature for feature_id, feature in holes if feature_id == target_id)
        first_diameter = float(first.params.get("diameter", 0.0))
        second_id, _second = min(
            ((feature_id, feature) for feature_id, feature in holes if feature_id != target_id),
            key=lambda pair: abs(float(pair[1].params.get("diameter", 0.0)) - first_diameter),
        )
        tree = window.object_tree.tree
        tree.expandAll()
        root = next(
            (
                tree.topLevelItem(index)
                for index in range(tree.topLevelItemCount())
                if tree.topLevelItem(index) is not None
                and tree.topLevelItem(index).data(0, Qt.ItemDataRole.UserRole) == object_id
            ),
            None,
        )
        item = _feature_item(root, second_id)
        if item is None:
            raise SystemExit(f"Die zweite Bohrung {second_id} fehlt im Objektbaum")
        tree.scrollToItem(item)
        settle(app, 20)
        local = tree.visualItemRect(item).center()
        visible = tree.viewport().mapTo(window, local)
        target = (float(visible.x()), float(visible.y()))
        selected = False

        def pair_step(index: int, total: int) -> None:
            nonlocal selected
            if not selected and index >= round(total * 0.44):
                QTest.mouseClick(
                    tree.viewport(),
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.ControlModifier,
                    local,
                )
                app.processEvents()
                if len(window.object_tree.selected_features()) != 2:
                    raise SystemExit("Die sichtbare Mehrfachauswahl enthält nicht zwei Bohrungen")
                if set(window.viewport.highlighted_features()) != {target_id, second_id}:
                    raise SystemExit("Die erste Bohrung verlor ihre sichtbare Mehrfachauswahl")
                if window.viewport.highlighted_object() is not None:
                    raise SystemExit("Die Mehrfachauswahl färbt den ganzen Körper")
                selected = True
            window.viewport.renderer.render()

        def pair_pointer(index: int, total: int) -> tuple[float, float, bool]:
            point = _ease(feature_point, target, index / max(1.0, total * 0.40))
            pressed = abs(index - round(total * 0.44)) <= 2
            return (*point, pressed)

        return pair_step, pair_pointer

    edit_actions = {
        "preview_feature": ("move_feature", "-10"),
        "resize_preview": ("resize_hole", "6.5"),
        "all_prepare": ("resize_hole", "6.5"),
        "duplicate_preview": ("duplicate_feature", "-10"),
    }
    if scene in edit_actions:
        op, typed_value = edit_actions[scene]
        fields, _button, every = _feature_action_row(window, op)
        if not fields:
            raise SystemExit(f"Die Presseaufnahme braucht ein Längenfeld für {op}")
        field = fields[0]
        field_point = _widget_centre(window, field)
        every_point = _widget_centre(window, every) if every is not None else field_point
        typed = False
        previewed = False
        selected_all = False

        def edit_step(index: int, total: int) -> None:
            nonlocal typed, previewed, selected_all
            if not typed and index >= round(total * 0.28):
                QTest.mouseClick(field, Qt.MouseButton.LeftButton)
                field.setFocus()
                field.selectAll()
                QTest.keyClicks(field, typed_value)
                QTest.keyClick(field, Qt.Key.Key_Return)
                typed = True
            if typed and not previewed and index >= round(total * 0.54):
                _wait_for_feature_preview(window, app)
                previewed = True
            if scene == "all_prepare" and not selected_all and index >= round(total * 0.70):
                if every is None:
                    raise SystemExit("Der Sammelhaken für gleichartige Bohrungen fehlt")
                QTest.mouseClick(every, Qt.MouseButton.LeftButton)
                if not every.isChecked():
                    raise SystemExit("Der sichtbare Sammelhaken blieb aus")
                selected_all = True
            window.viewport.renderer.render()

        def edit_pointer(index: int, total: int) -> tuple[float, float, bool]:
            if scene == "all_prepare" and index >= round(total * 0.48):
                share = (index - total * 0.48) / max(1.0, total * 0.18)
                point = _ease(field_point, every_point, share)
                pressed = abs(index - round(total * 0.70)) <= 2
                return (*point, pressed)
            point = _ease(feature_point, field_point, index / max(1.0, total * 0.24))
            pressed = abs(index - round(total * 0.28)) <= 2
            return (*point, pressed)

        return edit_step, edit_pointer

    apply_actions = {
        "apply_feature": "move_feature",
        "resize_apply": "resize_hole",
        "all_apply": "resize_hole",
        "duplicate_apply": "duplicate_feature",
        "remove_apply": "remove_feature",
    }
    op = apply_actions.get(scene)
    if op is None:
        raise SystemExit(f"Unbekannte Merkmalsfilmszene: {scene}")
    fields, button, every = _feature_action_row(window, op)
    if scene == "all_apply" and (every is None or not every.isChecked()):
        raise SystemExit("Die Sammelhandlung begann ohne gesetzten Haken")
    origin = every if scene == "all_apply" else (fields[0] if fields else None)
    origin_point = _widget_centre(window, origin) if origin is not None else feature_point
    button_point = _widget_centre(window, button)
    applied = False
    before_transactions = len(session.project.document.transactions)
    _object_id, holes_before = _feature_holes(session)
    target_id = _feature_target_id(session)

    def apply_step(index: int, total: int) -> None:
        nonlocal applied
        if not applied and index >= round(total * 0.38):
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            session.wait_for_idle(120_000)
            settle(app, 30)
            if scene == "remove_apply":
                result = session.last_result
                if result is None or _object_id not in result.scene.objects:
                    raise SystemExit("Das Entfernen der Bohrung nahm den ganzen Körper mit")
                if target_id in result.scene.objects[_object_id].features:
                    raise SystemExit("Die gewählte Bohrung blieb nach Entfernen bestehen")
            else:
                _after_object, feature_id, feature = _feature_demo_target(session)
                if feature_id != target_id:
                    raise SystemExit(f"Die Bohrungskennung wechselte zu {feature_id}")
                if scene == "apply_feature":
                    centre = feature.params.get("centre")
                    if centre is None or not math.isclose(
                        float(centre[0]), FEATURE_DEMO_TARGET_X, abs_tol=0.5
                    ):
                        raise SystemExit(
                            f"Die Bohrung wurde nicht an die belegte Zielstelle versetzt: {centre}"
                        )
                elif scene == "resize_apply" and not math.isclose(
                    float(feature.params.get("diameter", 0.0)), 6.5, abs_tol=0.2
                ):
                    raise SystemExit("Die Bohrung wurde nicht auf 6,5 mm geändert")
                elif scene == "all_apply":
                    _after_object, holes_after = _feature_holes(session)
                    measured = [
                        float(hole.params.get("diameter", 0.0)) for _feature_id, hole in holes_after
                    ]
                    if len(measured) != len(holes_before) or not all(
                        math.isclose(value, 6.5, abs_tol=0.2) for value in measured
                    ):
                        raise SystemExit(
                            f"Nicht alle Bohrungen wurden gemeinsam geändert: {measured}"
                        )
                    if len(session.project.document.transactions) != before_transactions + 1:
                        raise SystemExit(
                            "Die Sammelhandlung wurde nicht als eine Transaktion gespeichert"
                        )
                elif scene == "duplicate_apply":
                    _after_object, holes_after = _feature_holes(session)
                    if len(holes_after) != len(holes_before) + 1:
                        raise SystemExit(
                            "Die Duplizierung erzeugte nicht genau eine weitere Bohrung"
                        )
            applied = True
        window.viewport.renderer.render()

    def apply_pointer(index: int, total: int) -> tuple[float, float, bool]:
        point = _ease(origin_point, button_point, index / max(1.0, total * 0.34))
        pressed = abs(index - round(total * 0.38)) <= 2
        return (*point, pressed)

    return apply_step, apply_pointer


def reset_feature_demo(window: Any, app: QApplication, session: Any) -> None:
    """Den Merkmalsfilm auf die eingelesene Ausgangsdatei zurückstellen."""
    window._drop_feature_preview()
    edited = {
        "move_feature",
        "resize_hole",
        "duplicate_feature",
        "remove_feature",
    }
    while session.project.document.ops and session.project.document.ops[-1].op in edited:
        session.undo()
        session.wait_for_idle(120_000)
    object_id, _feature_id, _feature = _feature_demo_target(session)
    window.object_tree.select_object(object_id)
    window.feature_dock.hide()
    # Das Verbergen gehört dem Aufnahmewerkzeug, nicht dem Nutzer. Der Dock
    # merkt ein gewöhnliches ``hide`` sonst als „selbst geschlossen“ und
    # verweigert beim sichtbaren Bohrungsklick sein automatisches Öffnen.
    window.feature_dock.dismissed = False
    settle(app, 20)


def prepare_feature_demo_scene(
    window: Any,
    app: QApplication,
    session: Any,
    scene: str,
    panel_visible: bool,
) -> None:
    """Den Anfangszustand einer sichtbaren Bediensequenz herstellen."""
    if scene == "mesh":
        object_id, _feature_id, _feature = _feature_demo_target(session)
        window.object_tree.select_object(object_id)
        window.feature_dock.hide()
        window.feature_dock.dismissed = False
        settle(app, 20)
        return
    if scene == "recognise":
        object_id, _feature_id, _feature = _feature_demo_target(session)
        window.object_tree.select_object(object_id)
        window.feature_dock.hide()
        window.feature_dock.dismissed = False
        settle(app, 20)
        return
    if not panel_visible:
        window.feature_dock.hide()
        window.feature_dock.dismissed = False


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
    start_degrees: float = 0.0,
    feature_panel_visible: bool = True,
) -> Shot:
    """Alle Szenen des Drehbuchs hintereinander aufnehmen.

    Die Bilder landen fortlaufend nummeriert in **einem** Ordner — ffmpeg
    bekommt am Ende eine einzige Folge und muss nichts zusammensetzen.

    Am Schluss steht der Parameter wieder auf seinem Anfangswert. Ohne das
    beginnt der zweite Durchgang dort, wo der erste aufgehört hat, und das
    Hochformat zeigte ein Gehäuse, das schon breit ist und dann noch breiter
    wird.
    """
    feature_demo = any(key in FEATURE_DEMO_SCENES for key, _path, _seconds in spoken)
    reset_morph(session)
    if feature_demo:
        reset_feature_demo(window, app, session)
    # Und den Versatz auch: ``shoot_storyboard`` läuft zweimal am selben
    # Fenster, quer und hoch. Bliebe die Explosion stehen, begänne das
    # Hochformat mit einem Korb, der schon auseinander ist.
    window.viewport.set_explosion(0.0)  # type: ignore[attr-defined]
    total = 0
    card_from = -1
    readout: list[str] = []
    for key, _path, seconds in spoken:
        count = max(1, round(seconds * FPS))
        pointer: PointerFn | None = None
        caption: tuple[str, str] | None = None
        if key in FEATURE_DEMO_SCENES:
            prepare_feature_demo_scene(window, app, session, key, feature_panel_visible)
            step, pointer = feature_demo_step(window, app, session, key)
            caption = feature_caption(session, language, key)
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
        if key in FEATURE_DEMO_SCENES:
            pass
        elif key == "morph":
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
            step = orbit_step(window, app, zoom, turns=0.35, start_degrees=start_degrees)
        total = record(window, app, frames, total, count, step, pointer, caption)
        print(f"  {key:12s} {count:4d} Bilder")
    reset_morph(session)
    if feature_demo:
        reset_feature_demo(window, app, session)
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


def compose_feature_short(
    landscape: Shot,
    target_frames: Path,
    timing: list[tuple[str, Path, float]],
    language: str,
    captions: dict[str, tuple[str, str]] | None = None,
) -> Shot:
    """Aus der breiten Bedienaufnahme eine lesbare Short-Komposition bauen.

    Ein einfacher 9:16-Zuschnitt würde entweder das ausgewählte Loch oder das
    Merkmalfenster verlieren. Deshalb zeigt jedes Bild das Modell groß und
    darunter nur den gerade bedienten Bereich. Ein dauerhaftes Miniaturbild
    des ganzen Fensters verschwendet auf dem Telefon Fläche und macht genau
    die Felder unlesbar, die den Beleg tragen.
    """
    from PySide6.QtCore import QRect, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen

    if target_frames.exists():
        shutil.rmtree(target_frames)
    target_frames.mkdir(parents=True)
    width, height = 1080, 1920
    model_rect = QRect(310, 0, 1358, 920)
    detail_rects = {
        "mesh": QRect(310, 0, 1358, 920),
        "recognise": QRect(1660, 70, 260, 220),
        "preview_feature": QRect(1660, 135, 260, 210),
        "apply_feature": QRect(1660, 135, 260, 210),
        "resize_preview": QRect(1660, 315, 260, 190),
        "resize_apply": QRect(1660, 315, 260, 190),
        "all_prepare": QRect(1660, 315, 260, 190),
        "all_apply": QRect(0, 690, 310, 245),
        "pair_select": QRect(0, 80, 310, 220),
        "distance_result": QRect(1660, 65, 260, 220),
        "duplicate_preview": QRect(1660, 590, 260, 230),
        "duplicate_apply": QRect(1660, 590, 260, 230),
        "remove_apply": QRect(500, 250, 850, 575),
        "remove_undo": QRect(10, 715, 200, 135),
    }

    def cover(source: QImage, target_width: int, target_height: int) -> QImage:
        """Einen Ausschnitt füllen, ohne Schrift oder Modell zu verzerren."""
        scaled = source.scaled(
            target_width,
            target_height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        left = max(0, (scaled.width() - target_width) // 2)
        top = max(0, (scaled.height() - target_height) // 2)
        return scaled.copy(left, top, target_width, target_height)

    caption_map = captions or FEATURE_CAPTIONS[language]
    commit_badges = FEATURE_COMMIT_BADGES[language]
    source_index = 0
    card_from = landscape.count
    for scene_number, (key, _path, seconds) in enumerate(timing):
        scene_count = max(1, round(seconds * FPS))
        if key == "closing":
            card_from = source_index
            card = outro_card((width, height), (0, 0, width, height), language)
            for _local_index in range(scene_count):
                card.save(str(target_frames / f"{source_index:05d}.png"))
                source_index += 1
            continue

        caption = caption_map[key]
        for _local_index in range(scene_count):
            source = QImage(str(landscape.frames / f"{source_index:05d}.png"))
            if source.isNull():
                raise SystemExit(f"Short-Quellbild fehlt: {source_index:05d}.png")
            canvas = QImage(width, height, QImage.Format.Format_RGB32)
            canvas.fill(QColor("#14161a"))
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

            kicker = QFont("Segoe UI")
            kicker.setPixelSize(25)
            kicker.setWeight(QFont.Weight.DemiBold)
            painter.setFont(kicker)
            painter.setPen(QColor("#e08b4e"))
            painter.drawText(
                QRectF(60.0, 48.0, 960.0, 36.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                "SOLIDON3D · STL",
            )
            title = QFont("Segoe UI")
            title.setPixelSize(54)
            title.setWeight(QFont.Weight.Bold)
            while QFontMetrics(title).horizontalAdvance(caption[0]) > 960:
                title.setPixelSize(title.pixelSize() - 1)
            painter.setFont(title)
            painter.setPen(QColor("#f5f7fa"))
            painter.drawText(
                QRectF(60.0, 98.0, 960.0, 72.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                caption[0],
            )
            detail_font = QFont("Segoe UI")
            detail_font.setPixelSize(35)
            painter.setFont(detail_font)
            painter.setPen(QColor("#b7c0cb"))
            painter.drawText(
                QRectF(60.0, 174.0, 960.0, 54.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                caption[1],
            )

            model = cover(source.copy(model_rect), 960, 650)
            painter.setPen(QPen(QColor("#39424d"), 2.0))
            painter.setBrush(QColor("#0f1216"))
            painter.drawRoundedRect(QRectF(59.0, 264.0, 962.0, 652.0), 10.0, 10.0)
            painter.drawImage(QRectF(60.0, 265.0, 960.0, 650.0), model)

            label_font = QFont("Segoe UI")
            label_font.setPixelSize(24)
            label_font.setWeight(QFont.Weight.DemiBold)
            painter.setFont(label_font)
            painter.setPen(QColor("#7f8b99"))
            label = "DETAILANSICHT" if language == "de" else "DETAIL VIEW"
            painter.drawText(
                QRectF(60.0, 945.0, 960.0, 38.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
            detailed = cover(source.copy(detail_rects[key]), 960, 650)
            painter.setPen(QPen(QColor("#e08b4e"), 2.0))
            painter.setBrush(QColor("#0f1216"))
            painter.drawRoundedRect(QRectF(59.0, 993.0, 962.0, 652.0), 10.0, 10.0)
            painter.drawImage(QRectF(60.0, 994.0, 960.0, 650.0), detailed)

            badge = commit_badges.get(key)
            if badge is not None and _local_index >= round(scene_count * 0.50):
                badge_rect = QRectF(352.0, 835.0, 676.0, 64.0)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(20, 23, 28, 232))
                painter.drawRoundedRect(badge_rect, 10.0, 10.0)
                painter.setBrush(QColor("#e08b4e"))
                painter.drawRoundedRect(QRectF(352.0, 835.0, 8.0, 64.0), 4.0, 4.0)
                badge_font = QFont("Segoe UI")
                badge_font.setPixelSize(27)
                badge_font.setWeight(QFont.Weight.Bold)
                painter.setFont(badge_font)
                painter.setPen(QColor("#f5f7fa"))
                painter.drawText(
                    QRectF(380.0, 835.0, 626.0, 64.0),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    badge,
                )

            painter.setPen(QColor("#7f8b99"))
            footer = QFont("Segoe UI")
            footer.setPixelSize(30)
            painter.setFont(footer)
            painter.drawText(
                QRectF(60.0, 1745.0, 960.0, 48.0),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                "solidon3d.de",
            )
            dot_y = 1835.0
            for dot in range(len(timing)):
                painter.setBrush(QColor("#e08b4e") if dot == scene_number else QColor("#46505c"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(475.0 + dot * 42.0, dot_y, 14.0, 14.0))
            painter.end()
            canvas.save(str(target_frames / f"{source_index:05d}.png"))
            source_index += 1

    if source_index != landscape.count:
        raise SystemExit(f"Short hat {source_index} Bilder, die Quelle aber {landscape.count}")
    return Shot(
        frames=target_frames,
        count=source_index,
        viewport=(0, 0, width, height),
        card_from=card_from,
    )


def encode_feature_short(shot: Shot, target: Path, audio: Path) -> None:
    """Die fertige 9:16-Komposition als YouTube Short kodieren."""
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
            "medium",
            "-movflags",
            "+faststart",
            str(target),
        ]
    )
    print(f"  Short → {target.name}")


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
    # Ein Projekt oder Modell kann ausdrücklich das jeweilige Schaustück
    # ersetzen. Ein STL läuft dabei durch denselben sichtbaren Importweg wie
    # beim Nutzer; gerade für Pressebelege wäre ein vorher umgebautes P3D die
    # falsche Aussage über das gezeigte Ausgangsmaterial.
    chosen = [
        entry for entry in arguments if Path(entry).suffix.lower() in MODEL_SUFFIXES | {".p3d"}
    ]
    project = Path(chosen[0]) if chosen else None
    # ``loop`` schaltet auf die Website-Fassung um: stumm, 720p, kurz, in
    # zwei Formaten samt Standbild. Kein eigenes Werkzeug daneben — es ist
    # dieselbe Aufnahme aus demselben Drehbuch, nur anders ausgegeben, und
    # zwei Programme, die dasselbe Fenster filmen, laufen unweigerlich
    # auseinander.
    as_loop = "loop" in arguments
    short_only = "short" in arguments
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
    # ``--start <grad>`` — von welchem Winkel aus die Kreisbahn beginnt.
    #
    # In Grad und nicht in Umdrehungen: „52" liest sich, „0,146" nicht.
    start_degrees = 0.0
    for entry in arguments:
        if not entry.startswith("--start"):
            continue
        value = entry.split("=", 1)[1] if "=" in entry else ""
        if not value:
            index = arguments.index(entry)
            value = arguments[index + 1] if index + 1 < len(arguments) else ""
        if value:
            start_degrees = float(value)
        break

    feature_id = option(arguments, "--feature") or "hole_1"
    skip = {
        morph_name,
        f"{morph_name}:{morph_span[0]:g}:{morph_span[1]:g}",
        feature_id,
    }
    if start_degrees:
        skip.add(f"{start_degrees:g}")
    wanted = [
        entry
        for entry in arguments
        if entry not in SCRIPTS
        and entry != "loop"
        and entry != "short"
        and Path(entry).suffix.lower() not in MODEL_SUFFIXES | {".p3d"}
        and not entry.startswith("--")
        and entry not in skip
    ] or list(script)
    print(f"Drehbuch: {name}{' (Website-Loop)' if as_loop else ''}")
    if project is not None:
        print(f"Projekt:  {project}")

    # ``turntable`` nimmt die Bildreihe zum Ziehen auf und stapelt sie zum
    # Sprite. **Vor** der Sprachschleife, weil an einem Teil, das sich dreht,
    # kein Wort steht — eine Aufnahme dient allen sechs Fassungen.
    #
    # Bis zum 31.08.2026 gab es diesen Einstieg nicht: ``shoot_turntable``
    # stand da und wurde von niemandem gerufen. Wer den Sprite neu brauchte,
    # schrieb sich ein Skript daneben — und das Seitenverhältnis der Bühne
    # war damit nicht nachzuvollziehen.
    if "turntable" in arguments:
        # ``--ratio 16/7`` schneidet auf das Verhältnis der Bühne zu. Als
        # Bruch und nicht als Kommazahl, weil im Stylesheet auch ein Bruch
        # steht und man beide nebeneinanderlegen können soll.
        given_ratio = option(arguments, "--ratio")
        ratio: float | None = None
        if given_ratio:
            left, _, right = given_ratio.partition("/")
            ratio = float(left) / float(right) if right else float(left)
        stem = option(arguments, "--name") or "sprite"
        # **Der Abstand gehört dem Motiv.** ``TURNTABLE_ZOOM`` ist am
        # Elektronikgehäuse gemessen; der Rollenhalter ist 128 mm breit und
        # ragte damit oben und rechts aus dem Bild — im eingesetzten Sprite
        # war die Oberkante der Seitenwand abgeschnitten. Der Docstring von
        # ``shoot_turntable`` verlangt seit jeher, den eigenen Wert
        # mitzugeben; bis zum 31.08.2026 gab es dafür keinen Schalter.
        given_zoom = option(arguments, "--zoom")
        zoom = float(given_zoom) if given_zoom else TURNTABLE_ZOOM
        print(f"Drehscheibe: {stem}, Verhältnis {ratio or 'wie das Fenster'}, Abstand {zoom}")
        files = shoot_turntable(
            app, out, frames / "turntable", stem, chosen=project, zoom=zoom, ratio=ratio
        )
        stack_sprite(files, out / f"{stem}.webp")
        print()
        print(f"Fertig: {out}")
        return 0

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
                start_degrees=start_degrees,
            )
            continue
        shoot_language(
            app,
            language,
            out,
            frames / f"{name}-{language}",
            script,
            project,
            script_name=name,
            short_only=short_only,
            feature_id=feature_id,
        )

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


def _aim_camera(
    renderer: Any,
    position: tuple[float, float, float],
    focal: tuple[float, float, float],
    up: tuple[float, float, float],
) -> None:
    """Die Kamera des Renderers stellen — gezeichnet wird danach vom Aufrufer."""
    from app.ui.render.api import CameraPose

    renderer.set_camera_pose(CameraPose(position, focal, up))


def hide_axis_marker(window: Any) -> None:
    """Das Achsenkreuz in der Ecke abschalten.

    Der Nachbar von :func:`hide_orientation_widget`, und er wird getrennt
    gerufen: Im **Loop** ist die Anwendung die Aussage, dort gehören ihre
    Bedienelemente ins Bild. In der Drehreihe ist es das **Teil**, und ein
    Achsenkreuz, das sich mitdreht, ist Werkzeug im Schaufenster.

    Über den Vertrag des Renderers (``set_axes_marker(None)``) und nicht über
    dessen Innereien: Ein ``getattr`` auf ein Widget, das es nicht gibt, liefert
    still ``None``, und das Kreuz bliebe stehen, ohne dass sich ein Aufruf
    beschwert.
    """
    renderer = getattr(getattr(window, "viewport", None), "renderer", None)
    if renderer is None:
        return
    try:
        renderer.set_axes_marker(None)
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
    _open_video_input(session, project)
    if not await_result(app, session):
        raise SystemExit(f"Das Projekt rechnete nicht fertig: {project}")

    # Dieselbe Wache wie beim Loop: Ohne Körper dreht sich ein leerer Raum.
    result = getattr(session, "last_result", None)
    bodies = len(result.scene.objects) if result is not None else 0
    if not bodies:
        raise SystemExit(f"Kein Körper in der Szene ({project.name}).")

    show_panels(window, False)
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


def option(arguments: list[str], name: str) -> str:
    """Den Wert eines Schalters lesen, als ``--name wert`` wie als ``--name=wert``.

    Drei Schalter mit demselben zwölfzeiligen Block davor waren der Grund, aus
    dem der vierte fehlte: Wer ihn ergänzen will, schreibt den Block ein
    viertes Mal ab. Eine leere Zeichenkette heißt: nicht angegeben.
    """
    for index, entry in enumerate(arguments):
        if not entry.startswith(name):
            continue
        if "=" in entry:
            return entry.split("=", 1)[1]
        return arguments[index + 1] if index + 1 < len(arguments) else ""
    return ""


def stack_sprite(files: list[Path], target: Path) -> Path:
    """Die Einzelbilder einer Umdrehung zu **einem** Bild stapeln.

    **Warum überhaupt ein Sprite.** Sechsunddreißig Dateien sind
    sechsunddreißig Anfragen, und beim Ziehen darf nichts nachgeladen werden
    — sonst stockt genau die Bewegung, die der Geste folgen soll. Das
    Stylesheet verschiebt stattdessen ``background-position-y`` in einem Bild
    mit ``background-size: 100% 3600%``.

    **Warum das hier steht und nicht in einem Skript daneben.** Bis zum
    31.08.2026 gab es diesen Schritt nur als Handarbeit: ``shoot_turntable``
    schrieb die Reihe, und irgendjemand setzte sie zusammen. Das Ergebnis lag
    als ``bock-sprite.webp`` auf der Website, und der Weg dorthin war
    verloren — wer das Seitenverhältnis ändern wollte, musste ihn neu
    erfinden.

    Gestapelt wird mit ffmpeg und nicht mit Pillow: ``run_ffmpeg`` steht
    ohnehin bereit, und ``tools/`` kommt bisher ohne Bildbibliothek aus.
    """
    pattern = str(files[0].parent / f"{files[0].stem[:-3]}-%02d.webp")
    run_ffmpeg(
        [
            "-i",
            pattern,
            "-filter_complex",
            f"tile=1x{len(files)}",
            "-quality",
            str(TURNTABLE_QUALITY),
            str(target),
        ]
    )
    size = target.stat().st_size / 1024
    print(f"  Sprite → {target.name}  {size:.0f} kB, {len(files)} Aufnahmen übereinander")
    return target


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
    start_degrees: float = 0.0,
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
    _open_video_input(session, project)
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
        start_degrees=start_degrees,
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
    script_name: str = "einstieg",
    short_only: bool = False,
    feature_id: str = "hole_1",
) -> None:
    """Ein vollständiger Durchgang für eine Sprache: vertonen, filmen, kodieren.

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

    feature_short = script_name in FEATURE_SHORT_SCRIPTS
    stem = FEATURE_SHORT_STEMS.get(script_name, "solidon3d")
    if feature_short:
        # Der konkrete Höreindruck entscheidet: Eine künstliche Stimme, die
        # als solche auffällt, schwächt ausgerechnet einen Beweisfilm. Kurze
        # Einblendungen und ein eigenes Musikbett brauchen keine Behauptung,
        # die der Film nicht selbst zeigt.
        spoken = feature_timing(script[language])
        seconds = sum(entry[2] for entry in spoken)
        audio = write_feature_music(out / f"{stem}-music.wav", seconds)
        for obsolete in (out / f"stimme-{language}.wav", out / f"{stem}-{language}.srt"):
            if obsolete.is_file():
                obsolete.unlink()
        old_audio = out / "audio"
        if old_audio.is_dir():
            shutil.rmtree(old_audio)
        old_listing = out / "tonfolge.txt"
        if old_listing.is_file():
            old_listing.unlink()
        print(f"  zusammen {seconds:.1f} s · Text im Bild, keine künstliche Stimme")
    else:
        # **Zuerst die Stimme.** Sie bestimmt, wie lang jede Szene wird — und
        # wenn etwas an ihr fehlt, soll das auffallen, bevor zweimal
        # achthundert Bilder gerechnet sind.
        print("Sprachausgabe:")
        spoken = speak_storyboard(language, out, script)
        audio = out / f"stimme-{language}.wav"
        join_audio(spoken, audio)
        write_subtitles(spoken, script[language], out / f"{stem}-{language}.srt")
        print(f"  zusammen {sum(entry[2] for entry in spoken):.1f} s")

    session = Session()
    session._video_feature_id = feature_id
    window = MainWindow(session, UiSettings())
    window.resize(*WINDOW)
    window.show()

    default_example = FEATURE_EXAMPLE if feature_short else EXAMPLE
    project = chosen if chosen is not None else examples.directory() / default_example
    if not project.is_file():
        raise SystemExit(f"Projekt fehlt: {project}")
    _open_video_input(session, project)
    window._show_start_screen(False)
    if not await_result(app, session):
        raise SystemExit("Die Auswertung wurde nicht fertig — kein Video")
    if feature_short:
        # Prüfbericht und Merkmalfenster liegen beide rechts. Im normalen
        # Arbeitsfenster darf der Nutzer beides zugleich sehen; im schmalen
        # Belegfilm würden sie jedoch übereinander um dieselbe Modellfläche
        # kämpfen. Für diese Aufnahme bleibt nur das bediente Merkmalfenster.
        window.right.hide()
        window.overlay.reflow()
    window.raise_()
    window.activateWindow()
    settle(app, 60)

    # Zwei Formate an **einem** Fenster, aus demselben Grund wie oben.
    print("Aufnahme quer:")
    landscape = shoot_storyboard(
        window, app, session, frames / "landscape", spoken, language=language
    )

    portrait: Shot | None = None
    if feature_short:
        print("Komposition Short:")
        short_captions = {
            key: feature_caption(session, language, key)
            for key, _path, _seconds in spoken
            if key != "closing"
        }
        portrait = compose_feature_short(
            landscape,
            frames / "portrait",
            spoken,
            language,
            short_captions,
        )
    else:
        print("Aufnahme hoch:")
        show_panels(window, False)
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
            language=language,
            feature_panel_visible=False,
        )
        show_panels(window, True)
    print("Kodierung:")
    if not short_only:
        encode_landscape(landscape, out / f"{stem}-{language}-quer-1080p.mp4", audio)
    else:
        obsolete_landscape = out / f"{stem}-{language}-quer-1080p.mp4"
        if obsolete_landscape.is_file():
            obsolete_landscape.unlink()
    if portrait is not None:
        if feature_short:
            encode_feature_short(
                portrait,
                out / f"{stem}-{language}-short-1080x1920.mp4",
                audio,
            )
        else:
            headline, sub = PORTRAIT_TEXT[language]
            encode_portrait(
                portrait,
                out / f"{stem}-{language}-hoch-1080x1920.mp4",
                headline=headline,
                sub=sub,
                audio=audio,
            )

    # Ein unmittelbar eingelesenes Modell ist „ungespeichert“, und auch ein
    # geöffnetes P3D gilt nach den für den Film ausgeführten und rückgängig
    # gemachten Schritten als geändert. Beim Schließen des Aufnahmewerkzeugs
    # darf deshalb kein Speichern-Dialog auf Bedienung warten: Quelle und
    # fertiger Film liegen bereits an ihren Zielorten, das geöffnete Dokument
    # sollte nie geschrieben werden.
    session._dirty = False
    window.close()
    release_viewport(window)


if __name__ == "__main__":
    raise SystemExit(main())
