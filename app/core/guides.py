"""Die Bildanleitungen des Handbuchs (Bauplan §2.7, §37.2).

Eine Bildanleitung führt durch eine Aufgabe, Schritt für Schritt, und jeder
Schritt zeigt ein Bildschirmfoto der echten Oberfläche: eine Nummer und ein
Rahmen auf dem Bedienelement, um das es geht, dazu ein kurzer Satz. Wer so
liest, muss nicht suchen, wo „rechts im Bericht" liegt. Er sieht es.

Drei Stellen beantworten drei Fragen (``konzepte/konzept-handbuch-2026-09.md``
§5), und keine davon eine zweite:

* **Hier** steht, was der Kunde tut und wohin er sieht: Titel, Kurzfassung,
  Schritte und die Namen der Ziele. Ohne Qt, übersetzbar, dieselbe Quelle für
  Handbuchfenster, Website, PDF und Kommandozeile.
* **``app/ui/guide_targets.py``** weiß, welches Widget ein Name meint.
* **``tools/make_guides.py``** weiß, wie der Zustand für das Bild entsteht. Es
  geht den Weg jeder Anleitung beim Release in der echten Oberfläche; kann es
  einen Schritt nicht gehen, hält der Release an. Zwischen zwei Versionen
  läuft es nicht.

Die Ziele sind Namen aus einem festen Wortschatz (:data:`TARGETS` und die
Arten in :data:`TARGET_KINDS`), nicht Widgetnamen. Ein Name sagt, was der
Kunde sieht: ``report`` ist der Prüfbericht, gleich in welchem Reiter er
gerade steckt und wie seine Klasse heißt.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Final, Literal

from app.i18n import TranslatableText, _

#: In welchem Teil des Handbuchs eine Anleitung steht. Die übrigen Teile
#: (Funktionen, Hilfe bei Problemen, Nachschlagen) tragen keine Anleitungen.
GuidePart = Literal["start", "tasks"]

#: Die festen Ziele, die eine Anleitung nennen darf.
#:
#: Die ersten sieben sind die Bereiche, auf die schon die Tour zeigt
#: (``tour.TourTarget``); beide fragen dieselbe Auflösung in der Oberfläche.
TARGETS: Final[frozenset[str]] = frozenset(
    {
        # Hauptfenster
        "tree",
        "parameters",
        "history",
        "report",
        "viewport",
        "toolbar",
        "tools",
        "header",
        "selection",
        "statusbar",
        # Der letzte Schritt im Verlauf und die erste Handlung im Prüfbericht:
        # Wer ein Loch verschieben will, soll die Zeile sehen, nicht die Liste.
        "history.last",
        "report.action",
        # „An den Slicer übergeben …" im Prüfbericht — der letzte Meter, wenn
        # nichts mehr zu beanstanden ist
        "report.slicer",
        # „Bausteine" unten im Auswahlfenster: der Katalog, von der gewählten
        # Fläche aus, ohne Umweg über das Menü
        "selection.parts",
        # Der Druckdialog: Drucker oben, „Slicen" und „Druckdatei speichern …"
        "print.printer",
        "print.slice",
        "print.save",
        # Startbildschirm: die Ablagefläche und die Knöpfe „Neues Projekt",
        # „Modell öffnen …", „Projekt öffnen …" und „Handbuch"
        "start.drop",
        "start.new",
        "start.model",
        "start.project",
        "start.manual",
        # Der offene Dialog als Ganzes und sein Hauptknopf. Der heißt nicht
        # „Übernehmen", sondern wie die Operation („Bohrung setzen"), bei
        # Bausteinen „Einsetzen"; der Satz des Schritts nennt ihn so.
        "dialog",
        "dialog.accept",
    }
)

#: Ziele mit einem Namen dahinter, geschrieben als ``art:name``:
#:
#: * ``command:file.open`` — ein Befehl über seine Kennung aus
#:   ``MainWindow.window_commands``, im Bild sein Knopf oder Menüeintrag;
#: * ``operation:drill_hole`` — eine Operation über ihren Registernamen, im
#:   Bild ihr Eintrag im Auswahlfenster oder im Menü;
#: * ``field:diameter`` — ein Feld im offenen Operationsdialog über den Namen
#:   seines Parameters;
#: * ``part:screw_hole`` — ein Baustein über seinen Registernamen, im Bild
#:   seine Kachel im offenen Bausteinkatalog.
TARGET_KINDS: Final[tuple[str, ...]] = ("command", "operation", "field", "part")

_NAME: Final = re.compile(r"[a-z0-9_.]+")

#: Wie viele Wörter ein Schritt höchstens hat, gezählt an der deutschen
#: Quelle. Ein Schritt ist ein Satz unter einem Bild; wer mehr sagen muss,
#: hat zwei Schritte oder eine Erklärung, die auf eine eigene Seite gehört.
MAX_STEP_WORDS: Final = 20

#: Wie viele Wörter eine Beschriftung in einer Legende höchstens hat.
MAX_LABEL_WORDS: Final = 12


def is_target(name: str) -> bool:
    """Ob ``name`` ein Ziel aus dem Wortschatz ist."""
    if name in TARGETS:
        return True
    kind, separator, rest = name.partition(":")
    return bool(separator) and kind in TARGET_KINDS and bool(_NAME.fullmatch(rest))


@dataclass(frozen=True, slots=True)
class Mark:
    """Ein Ziel im Bild, und wie es beschriftet wird.

    ``label`` bleibt bei einem gewöhnlichen Schritt leer: Das erste Ziel trägt
    dann die Nummer des Schritts, jedes weitere nur einen Rahmen. Tragen die
    Ziele Beschriftungen, ist der Schritt eine **Legende** — jedes Ziel bekommt
    seine eigene Nummer, und unter dem Bild steht, wofür sie steht.
    """

    target: str
    label: TranslatableText | str = ""


@dataclass(frozen=True, slots=True)
class GuideStep:
    """Ein Satz und das Bild dazu."""

    text: TranslatableText | str
    marks: tuple[Mark, ...] = ()
    whole_window: bool = False
    """Das Bild zeigt das ganze Fenster statt des Umkreises seiner Ziele."""

    @property
    def is_legend(self) -> bool:
        """Ob die Ziele einzeln nummeriert und beschriftet werden."""
        return any(str(mark.label) for mark in self.marks)


@dataclass(frozen=True, slots=True)
class Guide:
    """Eine Bildanleitung: eine Aufgabe, von vorn bis zum Ergebnis."""

    key: str
    title: TranslatableText | str
    summary: TranslatableText | str
    part: GuidePart
    steps: tuple[GuideStep, ...]

    def figure_key(self, number: int) -> str:
        """Der Schlüssel der Abbildung zu Schritt ``number`` (gezählt ab 1)."""
        return f"guide-{self.key}-{number}"

    def figure_keys(self) -> tuple[str, ...]:
        """Die Abbildungsschlüssel aller Schritte, in ihrer Reihenfolge."""
        return tuple(self.figure_key(number) for number in range(1, len(self.steps) + 1))


def step(text: TranslatableText | str, *targets: str, whole_window: bool = False) -> GuideStep:
    """Ein gewöhnlicher Schritt: der Satz und die Ziele, auf die das Bild zeigt."""
    return GuideStep(text, tuple(Mark(target) for target in targets), whole_window)


def legend(
    text: TranslatableText | str,
    *entries: tuple[str, TranslatableText | str],
    whole_window: bool = True,
) -> GuideStep:
    """Ein Legendenschritt: jedes Ziel mit Nummer und Beschriftung."""
    return GuideStep(text, tuple(Mark(target, label) for target, label in entries), whole_window)


GUIDES: Final[tuple[Guide, ...]] = (
    Guide(
        key="window-overview",
        title=_("Das Fenster auf einen Blick"),
        summary=_("Wo was steht, in einem Bild."),
        part="start",
        steps=(
            legend(
                _("Jede Nummer im Bild steht für einen Bereich des Fensters."),
                (
                    "toolbar",
                    _("Werkzeugleiste: neu, öffnen, speichern, Modell einfügen, zeichnen."),
                ),
                ("tree", _("Objekte: alle Teile und was Solidon darin erkennt.")),
                ("parameters", _("Parameter: benannte Maße wie Wandstärke oder Lochabstand.")),
                ("history", _("Verlauf: jeder Schritt bis hierher. Doppelklick ändert ihn.")),
                ("viewport", _("Ansicht: Ihr Modell. Klicken wählt aus, rechts ziehen dreht.")),
                ("tools", _("Werkzeuge unter dem Modell: Schnitt, Messen, Bewegen und mehr.")),
                ("report", _("Prüfbericht: was nicht stimmt, meist mit Knopf zum Beheben.")),
                ("selection", _("Auswahl: Maße und passende Handlungen zum gewählten Teil.")),
                ("statusbar", _("Statusleiste: Maße, Fortschritt und offene Warnungen.")),
            ),
        ),
    ),
    Guide(
        key="print-a-model",
        title=_("Ein Modell prüfen und drucken"),
        summary=_("Von der heruntergeladenen Datei bis zur Druckdatei."),
        part="start",
        steps=(
            step(
                _("Ziehen Sie die Datei auf das Fenster oder klicken Sie auf *Modell öffnen …*."),
                "start.drop",
                "start.model",
            ),
            # Offene Stellen und verkehrte Flächen repariert Solidon beim
            # Einlesen selbst; der Bericht sagt, was es war, und die Knöpfe unter
            # einem Befund zeigen die Stelle oder nehmen die Reparatur zurück.
            # Ein „Knopf, der ihn behebt" stand im ersten Entwurf und war am
            # Fenster falsch (Probelauf 27.09.2026 an broken_open.stl).
            step(_("Rechts im *Prüfbericht* steht, was Solidon am Modell gefunden hat."), "report"),
            step(
                _("Ein Klick auf einen Befund zeigt darunter, was Sie tun können."),
                "report.action",
            ),
            step(
                _("Passt alles, klicken Sie auf *An den Slicer übergeben …*."),
                "report.slicer",
            ),
            step(_("Prüfen Sie oben Drucker und Filament."), "print.printer"),
            step(
                _("*Slicen* rechnet die Druckdatei, *Druckdatei speichern …* legt sie ab."),
                "print.slice",
                "print.save",
            ),
        ),
    ),
    Guide(
        key="drill-a-hole",
        title=_("Ein Loch bohren"),
        summary=_("Eine Bohrung in ein vorhandenes Modell setzen und später verschieben."),
        part="start",
        steps=(
            step(_("Klicken Sie auf das Teil. Es ist jetzt gewählt."), "viewport"),
            # Nur der Punkt: Mit dem Auswahlfenster am rechten Rand im selben
            # Bild wurde der Ausschnitt das ganze Fenster, und der Punkt auf
            # der Fläche war nicht mehr zu erkennen (Probelauf 27.09.2026).
            step(_("Klicken Sie noch einmal, genau auf die Fläche für das Loch."), "viewport"),
            step(
                _("Rechts unter *Auswahl*: Klicken Sie auf *Bohrung setzen*."),
                "operation:drill_hole",
            ),
            # Die Vorschau hat ihr eigenes Bild nach dem Übernehmen: Im selben
            # Bild wie das Feld lag das Werkzeugkreuz über dem Loch, und der
            # Ausschnitt wurde das ganze Fenster (Probelauf 27.09.2026).
            step(_("Tragen Sie den Durchmesser ein, zum Beispiel 5 mm."), "field:diameter"),
            step(_("Klicken Sie auf *Bohrung setzen*."), "dialog.accept"),
            step(_("Das Loch sitzt jetzt in der Fläche."), "viewport"),
            step(
                _(
                    "Sitzt es falsch? Ein Doppelklick auf den Schritt im *Verlauf* "
                    "öffnet ihn wieder."
                ),
                "history.last",
            ),
        ),
    ),
    Guide(
        key="first-part",
        title=_("Das erste eigene Teil"),
        summary=_("Eine Platte mit gesenktem Schraubenloch, vom leeren Projekt bis zum Druck."),
        part="start",
        steps=(
            step(_("Klicken Sie auf dem Startbildschirm auf *Neues Projekt*."), "start.new"),
            step(
                _("Öffnen Sie oben *Erzeugen → Grundformen → Quader anlegen*."),
                "operation:create_brep_box",
            ),
            step(
                _("Tragen Sie die Maße ein, zum Beispiel 60, 30 und 5 mm."),
                "field:width",
                "field:depth",
                "field:height",
            ),
            step(_("Klicken Sie auf *Quader anlegen*."), "dialog.accept"),
            step(
                _(
                    "Klicken Sie zweimal auf die Oberseite: erst ist das Teil gewählt, "
                    "dann die Fläche."
                ),
                "viewport",
            ),
            step(_("Rechts unter *Auswahl*: Klicken Sie auf *Bausteine*."), "selection.parts"),
            # Ein Doppelklick fügt ein. Mit „Einfügen" im selben Bild wurde der
            # Ausschnitt der ganze Katalog, und die Kachel war nicht mehr zu
            # lesen (Probelauf 27.09.2026).
            step(_("Doppelklicken Sie auf *Schraubenloch mit Senkung*."), "part:screw_hole"),
            step(
                _(
                    "Wählen Sie die Schraubengröße, zum Beispiel M4, "
                    "und klicken Sie auf *Einsetzen*."
                ),
                "field:size",
                "dialog.accept",
            ),
            step(
                _("Die Platte ist fertig. Gedruckt wird wie in *Ein Modell prüfen und drucken*."),
                "viewport",
                "report.slicer",
            ),
        ),
    ),
)


def find(key: str) -> Guide | None:
    """Eine Anleitung beim Namen."""
    for guide in GUIDES:
        if guide.key == key:
            return guide
    return None


def fingerprint(guide: Guide) -> str:
    """Ein Abdruck dessen, was die Bilder einer Anleitung zeigen sollen.

    Die Aufnahme schreibt ihn neben die Bilder (``guides.json``); ein Test
    vergleicht ihn beim Release mit dem heutigen Stand. Ein neuer Schritt, ein
    anderes Ziel oder ein anderer Satz verlangt neue Bilder: Die Zahl der
    Bilder hängt an den Schritten, die Markierung an den Zielen, und der Satz
    steht als Alt-Text am Bild. Gezählt wird die deutsche Quelle, nicht eine
    Übersetzung — eine bessere Übersetzung ändert kein Bild.
    """
    parts = [guide.key, str(len(guide.steps))]
    for one in guide.steps:
        parts.append(_source(one.text))
        parts.append("1" if one.whole_window else "0")
        for mark in one.marks:
            parts.extend((mark.target, _source(mark.label)))
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def _source(text: TranslatableText | str) -> str:
    return text.msgid if isinstance(text, TranslatableText) else text
