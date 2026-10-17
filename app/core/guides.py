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
from typing import TYPE_CHECKING, Final

from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    from app.core.perceive.actions import FeatureAction

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
        # *Bausteinkatalog …* unten im Auswahlfenster: der Katalog, von der gewählten
        # Fläche aus, ohne Umweg über das Menü
        "selection.parts",
        # „Filament und Druck“ unter der Liste der Auswahl und der Filamentwähler
        # darin: Dort wird gefärbt, am Körper wie an der Fläche (RM-510)
        "filament.section",
        "filament.picker",
        # Der Druckdialog: Drucker oben, „Slicen" und „Druckdatei speichern …"
        "print.printer",
        "print.slice",
        "print.save",
        # Startbildschirm: die Ablagefläche und die Knöpfe „Neues Projekt",
        # „Modell einfügen …", „Öffnen …" und „Handbuch"
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
        # Der Haken „Maße als Parameter anlegen" in einem Dialog, der ihn anbietet
        "dialog.naming",
        # Die Klappe „Weitere Einstellungen" im offenen Operationsdialog
        "dialog.more",
        # Die Zahlenfelder der Bewegen-Leiste, gleich welche Rolle gewählt ist
        "transform.values",
        # Das Wertfeld der ersten Zeile unter „Parameter" — über die Reihenfolge,
        # weil ein benanntes Maß in jeder Sprache anders heißt
        "parameters.first",
        # Die Beschriftung derselben Zeile — ein Rechtsklick dort öffnet ihr Menü
        # (``menu:parameters.edit``) — und *Zahlen an Maße binden …* darunter
        "parameters.first.label",
        "parameters.bind",
        # *Auswahl als Baustein speichern …* im offenen Bausteinkatalog
        "parts.save",
        # *Spule von Hand anlegen* im Filamentlager, im Fenster der neuen Spule
        # *Wählen …* am Profil des Slicers und der erste Farbknopf
        "filament.add",
        "filament.profile",
        "filament.colour",
        # Die erste Spule aus dem Lager in einem Filamentfeld — ein Ort in seiner Liste
        "filament.spool",
        # „Zeichnen" in der Werkzeugleiste und „Fertig" im Zeichenmodus
        "toolbar.draw",
        "sketch.done",
        # Der gemeinsame Knopf unten im Merkmalfenster, *Im Bild einstellen*
        # und der Haken *Auf alle N gleichartigen anwenden* darüber
        "feature.apply",
        "feature.in_view",
        "feature.every",
        # *Bezug ändern* und *Übernehmen* an der Maßgruppe im Bild
        "measure.reference",
        "measure.apply",
        # Das Suchfeld der Auswahlkarte und *Funktion suchen …* oben
        "search",
        "toolbar.search",
        # *Abbrechen* in der Statusleiste, das Vorschauband in der Ansicht und
        # *Modell nachbauen* in der Auswahlkarte
        "progress.cancel",
        "preview.banner",
        "selection.rebuild",
        # Die Seiten *Chat* und *Tour* der rechten Karte
        "chat",
        "tour",
        # *PayPal im Browser öffnen* beim Unterstützen und *Download-Seite öffnen*
        # im Fenster der neuen Version — Wege zu den Meldungen, wenn kein Browser öffnet
        "donation.paypal",
        "update.page",
        # In *Zusätzliche Programme*: *Installieren* einer Zeile, *Details anzeigen*
        # nach einem Fehlschlag, *ComfyUI einrichten …* und *Ort angeben …* eines Dienstes
        "install.action",
        "install.details",
        "install.follow.comfyui",
        "install.locate",
        # *Aus dem Slicer übernehmen* im Filamentlager
        "filament.import",
        # Die erste Zeile mit Filament unter *Filamente* in der Kopfzeile — ein Ort
        # in der Liste; ein Doppelklick öffnet die Druckwerte dieser Spule
        "filaments.first",
        # *Filament abziehen …* in der Zeile über der Ansicht nach einem Export
        "usage.review",
        # Die Reiterleiste der rechten Karte (ihr Rechtsklick öffnet das Menü mit
        # *In eigenem Fenster öffnen*) und *Zurück in Solidon* im eigenen Fenster
        "tabs.bar",
        "tabs.return",
        # Im Chat das erste Beispiel und *Senden*; im KI-Hinweis *Solidon-Datenschutz
        # lokal öffnen*; *Offline aktivieren …* beim Freischalten
        "request.example",
        "request.send",
        "disclosure.privacy",
        "activation.offline",
        # Die Beschreibung und *Erzeugen* in *Modell erzeugen*, *KI-Anfrage
        # fortsetzen* im KI-Hinweis
        "generate.prompt",
        "generate.start",
        "disclosure.continue",
        # Im Skizzeneditor *Koordinaten …* am gewählten Punkt und *Neue Ebene …* im
        # Ebenenfeld — ein Eintrag seiner Liste, ein Ort
        "sketch.coordinates",
        "sketch.new_plane",
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
#:   seine Kachel im offenen Bausteinkatalog;
#: * ``tool:transform`` — ein Werkzeug unter der Ansicht über seinen Schlüssel
#:   in der Werkzeugzeile (``section``, ``measure``, ``transform`` …);
#: * ``transform:rotate`` — eine Rolle der Bewegen-Leiste (``move``,
#:   ``rotate``, ``scale``);
#: * ``section:shaping`` — ein Abschnitt im Auswahlfenster über eine Kategorie
#:   des Registers; im Bild seine Überschrift, die ihn auf- und zuklappt;
#: * ``sketch:rectangle`` — ein Werkzeug des Zeichenmodus;
#: * ``sketch.point:1`` — ein Punkt der Skizze, wo er gezeichnet steht, gezählt
#:   ab 1 über die Punkte aller Elemente;
#: * ``sketch.at:20_10`` — eine Stelle der Zeichenebene in Millimetern
#:   (waagerecht, senkrecht), dort klickt ein Zeichenwerkzeug;
#: * ``sketch.constraint:distance`` — die erste Zeile der Bedingungsliste mit
#:   einer Bedingung dieser Art; die Liste zeigt, was an der Auswahl hängt;
#: * ``sketch.constrain:distance`` — der Knopf einer Bedingung über ihre Art;
#: * ``history:edit`` — ein Eintrag im Kontextmenü des Verlaufs (``edit``,
#:   ``insert``, ``switch``, ``delete``), solange das Menü offen ist; derselbe
#:   Eintrag wie ``menu:history.edit``, als Name der Anleitungen geblieben;
#: * ``feature:resize_hole`` — der Kopf einer Handlung im Merkmalfenster über
#:   ihren Schlüssel (``FeatureAction.key``: die Operation oder ein Schlüssel
#:   wie ``part.move``), siehe :func:`action_target`;
#: * ``edge:fillet_edges`` — eine Zeile an einer angeklickten Kante, eine
#:   Variante als ``edge:fillet_edges.variable_radius``;
#: * ``feature.field:resize_hole.diameter`` — ein Feld einer Handlung, gebildet
#:   aus Schlüssel und Feldname (:func:`action_field_target`);
#: * ``measure.field:diameter`` — ein Feld der Maßgruppe im Bild;
#: * ``menu:menubar.speichern_unter`` — eine Zeile der Menüleiste über
#:   ihren ``objectName`` (:func:`menubar_name`) oder eine Zeile eines offenen
#:   Kontextmenüs (``history.edit``, ``tree.…``, Operationsname,
#:   ``report.<handlung>``, ``parameters.…``);
#: * ``finding:arrange.below_bed`` — eine Zeile im Prüfbericht über ihre
#:   Befundkennung; die darf Großbuchstaben tragen (``op.drill_hole.ValidationError``);
#: * ``finding.action:place_on_bed`` — ein Knopf zum gewählten Befund;
#: * ``print:layers.layer_height`` — ein Feld im Druckdialog;
#: * ``setting:language`` — eine Zeile in den Einstellungen;
#: * ``handle:move.x`` — ein Griff im Bild oder eine Leiste (``bar.section``);
#: * ``tree.row:obj_1`` und ``tree.row:obj_1.hole_2`` — eine Zeile im Baum;
#: * ``history.row:3`` — die Verlaufszeile mit der sichtbaren Nummer 3;
#: * ``view:obj_1.hole_2`` — eine Stelle im Bild auf diesem Merkmal;
#: * ``view.edge:obj_1`` — eine Stelle im Bild auf einer bearbeitbaren Kante
#:   dieses Körpers; am gewählten Körper wählt ein Klick dort die Kante;
#: * ``dialog:print_settings_dialog`` — ein offener Dialog dieser Klasse;
#: * ``start.recent:1`` — ein Eintrag unter „Zuletzt geöffnet“ auf dem
#:   Startbildschirm, gezählt ab 1 in der Folge der Liste. Eine Menüzeile
#:   dafür gibt es nicht;
#: * ``message:unsaved_changes`` — ein Meldungs-, Frage- oder Eingabefenster
#:   über ein Wort für seine Frage: eine Rückfrage (``QMessageBox``), eine
#:   Meldung, eine Eingabe, ein Farbwähler am Ort (``app/ui/message_dialog``);
#: * ``message.button:unsaved_changes.save`` — ein Knopf darin; bei einer
#:   Fehlermeldung ist der Knopf die Kennung der Handlung
#:   (``message.button:error.retry``), in einer Rückfrage über Qts
#:   Knopfleiste der Standardknopf (``ok``, ``cancel``);
#: * ``setting.section:weitere_einstellungen`` — die Kopfzeile eines Abschnitts
#:   der Einstellungen, gebildet aus seinem Titel (:func:`name_part`).
#:
#: **Ein Name nennt die Sache, nie Datei oder Modul:** Die Oberfläche wird
#: aufgeteilt, und ein Name mit Modul verlöre Tour, Anleitung und
#: Funktionsdurchgang (``tests/test_guide_targets.py`` hält es).
TARGET_KINDS: Final[tuple[str, ...]] = (
    "command",
    "operation",
    "field",
    "part",
    "tool",
    "transform",
    "section",
    "sketch",
    "history",
    "feature",
    "edge",
    "feature.field",
    "measure.field",
    "menu",
    "finding",
    "finding.action",
    "print",
    "setting",
    "handle",
    "tree.row",
    "history.row",
    "view",
    "view.edge",
    "dialog",
    "start.recent",
    "message",
    "message.button",
    "setting.section",
    "sketch.point",
    "sketch.at",
    "sketch.constraint",
    "sketch.constrain",
)

#: Das erste Glied jedes Namens einer Zeile der Menüleiste (:func:`menubar_name`).
MENUBAR: Final = "menubar"

#: Der Name einer Widget-Eigenschaft, die ein Bedienelement als Ziel ausweist.
#:
#: Widgets tragen ihr Ziel als dynamische Eigenschaft und nicht als
#: ``objectName``: Der gehört dem Stylesheet (``actionHeading``,
#: ``functionSearch``). Aktionen in Menüs tragen es dagegen als ``objectName``.
TARGET_PROPERTY: Final = "guideTarget"

_WORD: Final = r"[a-z0-9_]+"
_DOTTED: Final = rf"{_WORD}(?:\.{_WORD})*"

#: Wie der Name hinter jeder Art aussieht. Eine Befundkennung trägt den Namen
#: einer Ausnahmeklasse und damit Großbuchstaben; alles andere ist klein.
_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    **{kind: re.compile(_DOTTED) for kind in TARGET_KINDS},
    "operation": re.compile(_WORD),
    "part": re.compile(_WORD),
    "field": re.compile(_WORD),
    "edge": re.compile(rf"{_WORD}(?:\.{_WORD})?"),
    "view.edge": re.compile(_WORD),
    "feature.field": re.compile(rf"{_WORD}(?:\.{_WORD})+"),
    "measure.field": re.compile(_WORD),
    "finding": re.compile(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*"),
    "history.row": re.compile(r"[1-9][0-9]*"),
    "start.recent": re.compile(r"[1-9][0-9]*"),
    "dialog": re.compile(r"[a-z][a-z0-9_]*"),
    "message": re.compile(_WORD),
    "message.button": re.compile(rf"{_WORD}\.{_DOTTED}"),
    "sketch.point": re.compile(r"[1-9][0-9]*"),
    "sketch.at": re.compile(r"[0-9]+_[0-9]+"),
    "sketch.constraint": re.compile(_WORD),
    "sketch.constrain": re.compile(_WORD),
}

#: Die Umlaute in einem Namen aus der deutschen Quelle.
_UMLAUTS: Final = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"}
)

#: Wie viele Wörter ein Schritt höchstens hat, gezählt an der deutschen
#: Quelle. Ein Schritt ist ein Satz unter einem Bild; wer mehr sagen muss,
#: hat zwei Schritte oder eine Erklärung, die auf eine eigene Seite gehört.
MAX_STEP_WORDS: Final = 20

#: Wie viele Wörter eine Beschriftung in einer Legende höchstens hat.
MAX_LABEL_WORDS: Final = 12


def is_target(name: str) -> bool:
    """Ob ``name`` ein Ziel aus dem Wortschatz ist — fest oder Art mit passendem Namen."""
    if name in TARGETS:
        return True
    kind, separator, rest = name.partition(":")
    pattern = _PATTERNS.get(kind)
    return bool(separator) and pattern is not None and bool(pattern.fullmatch(rest))


def menubar_name(msgid: str, context: str | None = None) -> str:
    """Der ``objectName`` einer Zeile der Menüleiste, gebildet aus ihrer deutschen Quelle.

    Klein, Umlaute ausgeschrieben, alles andere als ``_``, ohne Auslassungspunkte
    und Kürzelzeichen: *Speichern unter …* heißt ``menubar.speichern_unter``. Ein
    Übersetzungskontext steht vorn (``menubar.kamera.rechts``). Der Name hängt
    an der Quelle und nicht an der Anzeige, also gilt er in jeder Sprache, und
    er hängt nicht an der Lage der Zeile — eine neue Zeile darüber ändert ihn
    nicht.
    """
    parts = [name_part(text) for text in (context, msgid) if text]
    if not parts or not all(parts):
        raise ValueError(f"menubar_name: aus {msgid!r} entsteht kein Name")
    return ".".join((MENUBAR, *parts))


def menubar_name_of(text: TranslatableText | str) -> str:
    """:func:`menubar_name` für einen Titel, wie Register und Menüaufbau ihn führen.

    Ein übersetzbarer Text gibt Quelle und Kontext; ein schlichter Text ist ein
    Titel, den niemand übersetzt (ein eigener Baustein), und steht für sich.
    """
    if isinstance(text, TranslatableText):
        return menubar_name(text.msgid, text.context)
    return menubar_name(text)


def dialog_name(class_name: str) -> str:
    """Der Name hinter ``dialog:`` für eine Fensterklasse: ``PrintSettingsDialog``
    heißt ``print_settings_dialog``, ``LLMKeyDialog`` ``llm_key_dialog``; ein
    führender Unterstrich fällt weg (``_PanelWindow`` → ``panel_window``).

    Eine Quelle für die Funktionsliste, die die Klassen im Quelltext findet,
    und die Auflösung, die das offene Fenster sucht.
    """
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", class_name.lstrip("_"))
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", spaced).lower()


def name_part(text: str) -> str:
    """Ein Glied eines Zielnamens aus einem Text: klein, Umlaute ausgeschrieben,
    alles andere ``_`` (``Speichern unter …`` → ``speichern_unter``)."""
    text = text.replace("…", "").replace("&", "").translate(_UMLAUTS).lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def action_key(action: FeatureAction) -> str:
    """Der Schlüssel einer Handlung im Merkmalfenster (``FeatureAction.key``).

    Leer heißt: der Name ihrer Operation. Eine Handlung ohne Operation und ohne
    Schlüssel hat keinen und damit kein Ziel.
    """
    return str(action.key or action.op or "")


def action_target(action: FeatureAction) -> str:
    """Das Ziel am Kopf einer Handlung: ``edge:<schlüssel>`` an einer angeklickten
    Kante, sonst ``feature:<schlüssel>``; leer ohne Schlüssel.

    Eine Kantenzeile erkennt sich an dem Wert, den nur sie mitbringt
    (``edges="named"``, ``perceive.actions.edge_actions``).
    """
    key = action_key(action)
    if not key:
        return ""
    edge = ("edges", "named") in action.fixed
    return f"{'edge' if edge else 'feature'}:{key}"


def action_field_target(action: FeatureAction, field_name: str) -> str:
    """Das Ziel an einem Feld einer Handlung: ``feature.field:<schlüssel>.<feld>``."""
    key = action_key(action)
    return f"feature.field:{key}.{field_name}" if key else ""


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
    steps: tuple[GuideStep, ...]
    teaches: tuple[str, ...] = ()
    """Die Operationen, die diese Anleitung lehrt, mit ihrem Registernamen.

    F1 in ihrem Dialog schlägt diese Anleitung auf (``manual.help_for``). Ein
    eigenes Feld und keine Ableitung aus den Markierungen: Der Zwilling im
    anderen Rechenkern (``drill_brep_hole`` neben ``drill_hole``) öffnet
    denselben Dialog, ohne dass ein Bild ihn markiert. Jede markierte Operation
    steht hier auch, das prüft ``tests/test_guides.py``. Umgekehrt nur, was die
    Schritte zeigen: Eine Operation, die die Anleitung bloß streift, schickte
    F1 in eine Anleitung, die die Frage nicht beantwortet — ihr Eintrag in der
    Referenz tut es."""
    topics: tuple[str, ...] = ()
    """Die Erklärseiten, an deren Ende ein Verweis auf diese Anleitung steht.

    Wer auf *Der Verlauf* liest, wie man einen Schritt ändert, findet dort den
    Weg in Bildern (``manual.pages``). Der Verweis wird erzeugt und steht nicht
    im Seitentext: Jede Seite ist ein Katalogschlüssel, und ein Verweis darin
    verlangte sie in fünf Sprachen neu. Dass jede Seite hier eine Erklärseite
    ist und jede Anleitung eine hat, prüft ``tests/test_guides.py``."""

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
        steps=(
            legend(
                _("Jede Nummer im Bild steht für einen Bereich des Fensters."),
                (
                    "toolbar",
                    _(
                        "Werkzeugleiste: neu, öffnen, speichern, Modell einfügen, "
                        "zeichnen, formen, Skelett."
                    ),
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
        topics=("window",),
    ),
    Guide(
        key="print-a-model",
        title=_("Ein Modell prüfen und drucken"),
        summary=_("Von der heruntergeladenen Datei bis zur Druckdatei."),
        steps=(
            step(
                _("Ziehen Sie die Datei auf das Fenster oder klicken Sie auf *Modell einfügen …*."),
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
            # Erst nach dem Slicen erscheint *Druckdatei speichern …* (RM-514);
            # gezeigt wird deshalb der Knopf, mit dem es weitergeht.
            step(
                _("*Slicen* rechnet die Druckdatei. Danach legt *Druckdatei speichern …* sie ab."),
                "print.slice",
            ),
        ),
        topics=("print",),
    ),
    Guide(
        key="drill-a-hole",
        title=_("Ein Loch bohren"),
        summary=_("Löcher in ein vorhandenes Modell bohren und später verschieben."),
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
            # Die Lage steht im wieder geöffneten Schritt hinter der Klappe:
            # Vorn bleibt, was man an einer Bohrung meist ändert.
            step(
                _(
                    "Klappen Sie *Weitere Einstellungen* auf, ändern Sie *Position X* "
                    "oder *Position Y* und klicken Sie auf *Bohrung setzen*."
                ),
                "dialog.more",
                "field:x",
                "field:y",
                "dialog.accept",
            ),
        ),
        teaches=("drill_hole", "drill_brep_hole"),
        topics=("features",),
    ),
    Guide(
        key="first-part",
        title=_("Das erste eigene Teil"),
        summary=_(
            "Vom leeren Projekt zur fertigen Platte, mit einem Baustein für das Schraubenloch."
        ),
        steps=(
            step(_("Klicken Sie auf dem Startbildschirm auf *Neues Projekt*."), "start.new"),
            # **Rechts in der Karte, nicht im Menü:** Ohne Auswahl stehen die
            # Erzeuger seit RM-735 unter *Auswahl*, und das Ziel zeigt zuerst
            # auf ihren Knopf (``guide_targets.area_for``). Mit dem Menüweg im
            # Satz rahmte das Bild den Knopf rechts, während links das Menü
            # offen stand, und kein Zuschnitt fasste beides (Probe 16.10.2026).
            step(
                _("Rechts unter *Auswahl*: Klicken Sie auf *Quader anlegen*."),
                "operation:create_brep_box",
            ),
            step(
                _("Tragen Sie die Maße ein, zum Beispiel 60, 30 und 5 mm."),
                "field:width",
                "field:depth",
                "field:height",
            ),
            step(_("Klicken Sie auf *Quader anlegen*."), "dialog.accept"),
            # **Ein neues Teil ist schon gewählt** (``_queue_created_choice``):
            # Der erste Klick nimmt deshalb die Fläche. „Zweimal: erst das Teil,
            # dann die Fläche“ stimmte nur, wenn vorher etwas anderes gewählt war
            # (Fragebogen zu 0.5.3).
            step(
                _(
                    "Klicken Sie auf die Oberseite. Der neue Quader ist schon gewählt, "
                    "also wählt der Klick die Fläche."
                ),
                "viewport",
            ),
            # **Unten der Knopf, nicht die Klappe**: An einer Fläche steht über
            # der Liste die Abschnittsklappe *Bausteine* (*Deckel erzeugen*,
            # *Drehdeckel erzeugen*); der
            # Knopf zum Katalog heißt deshalb wie im Menü *Bausteinkatalog …*.
            step(
                _("Rechts unter *Auswahl*: Klicken Sie unten auf *Bausteinkatalog …*."),
                "selection.parts",
            ),
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
                _(
                    "Die Platte ist fertig. Gedruckt wird wie in "
                    "[Ein Modell prüfen und drucken](manual:print-a-model)."
                ),
                "viewport",
                "report.slicer",
            ),
        ),
        teaches=("create_brep_box", "create_box", "insert_screw_hole"),
        topics=("parts",),
    ),
    Guide(
        key="housing-with-lid",
        title=_("Ein Gehäuse mit Deckel"),
        summary=_(
            "Eine Dose aushöhlen, den passenden Deckel erzeugen und beides auf dem Druckbett "
            "anordnen."
        ),
        steps=(
            # Klick und Knopf in je einem Bild: Zusammen wurde der Ausschnitt
            # das ganze Fenster, und *Aushöhlen* war nicht mehr zu lesen
            # (Probelauf 27.09.2026).
            # **Kein Klick auf den neuen Quader**: Er ist nach dem Anlegen schon
            # gewählt, und ein Klick darauf nahm die Oberseite — an einer Fläche
            # stand *Aushöhlen* dann nicht, wo das nächste Bild es zeigt
            # (Fragebogen zu 0.5.3).
            step(
                _(
                    "Legen Sie wie in [Das erste eigene Teil](manual:first-part) "
                    "einen Quader an. Danach ist er schon gewählt."
                ),
                "viewport",
            ),
            step(
                _("Rechts unter *Auswahl*: Klicken Sie auf *Aushöhlen*."),
                "operation:hollow_object",
            ),
            step(
                _("Tragen Sie die Wandstärke ein, etwa 2 mm, und haken Sie *Oben öffnen* an."),
                "field:wall",
                "field:open_top",
            ),
            step(_("Klicken Sie auf *Aushöhlen*."), "dialog.accept"),
            step(
                _("Öffnen Sie oben *Erzeugen → Bausteine → Deckel erzeugen*."),
                "operation:create_lid",
            ),
            # *Deckel erzeugen* ist eine Operation und kein Baustein aus dem
            # Katalog: Ihr Hauptknopf heißt wie sie, nicht *Einsetzen*.
            step(
                _("Das Spiel zur Dose kommt aus dem Material. Klicken Sie auf *Deckel erzeugen*."),
                "dialog.accept",
            ),
            # Ausrichten gilt allen Körpern und steht deshalb, wenn nichts
            # gewählt ist (Robert, 27.09.2026).
            step(
                _("Der Deckel sitzt auf der Dose. Klicken Sie daneben ins Leere."),
                "viewport",
            ),
            step(
                _("Rechts unter *Auswahl*: Klicken Sie auf *Druckoptimal ausrichten*."),
                "operation:orient_for_print",
            ),
            # Der Knopf öffnet einen Dialog mit Vorschau und richtet erst
            # damit aus; ohne diesen Schritt zeigte das letzte Bild die
            # Vorschau statt der fertigen Lage (Probelauf 27.09.2026).
            step(
                _("Klicken Sie im Dialog auf *Druckoptimal ausrichten*."),
                "dialog.accept",
            ),
            step(
                _(
                    "Dose und Deckel liegen nebeneinander. Prüfen und drucken Sie sie wie in "
                    "[Ein Modell prüfen und drucken](manual:print-a-model)."
                ),
                "viewport",
                "report.slicer",
            ),
        ),
        teaches=("hollow_object", "create_lid", "orient_for_print"),
        topics=("parts",),
    ),
    Guide(
        key="split-a-large-part",
        title=_("Ein zu großes Teil teilen"),
        summary=_(
            "Ein Teil, das nicht auf das Bett passt, in Stücke mit Stiften teilen und auf dem "
            "Druckbett anordnen."
        ),
        steps=(
            step(
                _(
                    "Rechts im *Prüfbericht* steht, dass das Teil über den Bauraum hinausragt. "
                    "Klicken Sie darauf."
                ),
                "report",
            ),
            step(_("Klicken Sie auf *Modell teilen*."), "report.action"),
            step(
                _("Solidon teilt das Teil und setzt Stifte, damit die Stücke zusammenpassen."),
                "viewport",
            ),
            # Der Knopf steht erst unter seinem Befund; ohne gewählten Befund
            # zeigt der Bericht andere Handlungen (Prüfung am Fenster, 11.10.2026).
            step(
                _(
                    "Klicken Sie im *Prüfbericht* auf den Befund, dass die Hälften "
                    "aneinanderliegen, dann auf *Auf dem Bett anordnen*."
                ),
                "report.action",
            ),
            step(
                _(
                    "Die Stücke liegen nebeneinander. Prüfen und drucken Sie sie wie in [Ein "
                    "Modell prüfen und drucken](manual:print-a-model)."
                ),
                "viewport",
                "report.slicer",
            ),
        ),
        teaches=("split_pinned",),
        topics=("splitting",),
    ),
    Guide(
        key="move-and-turn",
        title=_("Ein Teil verschieben und drehen"),
        summary=_("Am Griff im Bild ziehen oder genaue Werte eintippen."),
        steps=(
            step(_("Klicken Sie auf das Teil. Es ist jetzt gewählt."), "viewport"),
            step(_("Unten unter der Ansicht: Klicken Sie auf *Bewegen*."), "tool:transform"),
            step(
                _("Ziehen Sie an einem der Pfeile im Bild, um das Teil zu verschieben."), "viewport"
            ),
            step(
                _(
                    "Genau geht es mit Zahlen: Tippen Sie unten die Werte ein "
                    "und drücken Sie Enter."
                ),
                "transform.values",
            ),
            step(
                _(
                    "Zum Drehen: Klicken Sie auf *Drehen*, wählen Sie die *Achse* "
                    "und tragen Sie den *Winkel* ein."
                ),
                "transform:rotate",
                "transform.values",
            ),
            step(
                _("Jede Bewegung ist ein Schritt im *Verlauf* und lässt sich zurücknehmen."),
                "history.last",
            ),
        ),
        teaches=("translate_object", "rotate_object"),
        topics=("moving",),
    ),
    Guide(
        key="change-a-dimension",
        title=_("Ein Maß nachträglich ändern"),
        summary=_("Maße als Parameter anlegen und später an einer Stelle ändern."),
        steps=(
            step(
                _(
                    "Legen Sie wie in [Das erste eigene Teil](manual:first-part) einen Quader an"
                    ". *Maße als Parameter anlegen* muss angehakt sein."
                ),
                "dialog.naming",
            ),
            step(
                _(
                    "Klicken Sie auf *Quader anlegen*. Die Maße stehen jetzt links "
                    "unter *Parameter*."
                ),
                "parameters",
            ),
            step(
                _(
                    "Tragen Sie bei *Breite* einen neuen Wert ein, zum Beispiel 80 mm, "
                    "und drücken Sie Enter."
                ),
                "parameters.first",
            ),
            step(
                _("Das Teil ändert sich mit, ebenso jeder Schritt, der das Maß benutzt."),
                "viewport",
            ),
        ),
        topics=("parameters",),
    ),
    Guide(
        key="undo-a-step",
        title=_("Einen Schritt zurücknehmen oder ändern"),
        summary=_("Rückgängig machen, einen Schritt im Verlauf ändern, ausschalten oder löschen."),
        steps=(
            step(
                _(
                    "Oben im Menü *Bearbeiten*: *Rückgängig* nimmt den letzten Schritt zurück, "
                    "ebenso Strg+Z."
                ),
                "command:edit.undo",
            ),
            legend(
                _(
                    "Ein Rechtsklick auf einen Schritt im *Verlauf* zeigt, "
                    "was Sie mit ihm tun können."
                ),
                ("history:edit", _("Parameter ändern: den Schritt öffnen und Werte ändern.")),
                ("history:switch", _("Ausschalten: den Schritt weglassen, ohne ihn zu löschen.")),
                ("history:delete", _("Schritt löschen: fragt nach; abhängige Schritte gehen mit.")),
                whole_window=False,
            ),
            step(
                _(
                    "*Schritt löschen …* fragt vorher nach; abhängige Schritte gehen mit. "
                    "Strg+Z holt alles zurück."
                ),
                "dialog",
            ),
        ),
        topics=("history",),
    ),
    Guide(
        key="thread-a-hole",
        title=_("Ein Gewinde in eine Bohrung"),
        summary=_("Ein druckbares Innengewinde in eine vorhandene Bohrung setzen."),
        steps=(
            step(
                _(
                    "Klicken Sie zweimal auf die Bohrung: erst ist das Teil gewählt, "
                    "dann die Bohrung."
                ),
                "viewport",
            ),
            step(
                _("Öffnen Sie oben im Menü *Datei* den *Bausteinkatalog …*."),
                "command:file.catalog",
            ),
            step(_("Doppelklicken Sie auf *Druckbares Gewinde*."), "part:printed_thread"),
            step(
                _(
                    "Über den Feldern steht, welches Gewinde in diese Bohrung passt. "
                    "Wählen Sie die *Größe* und klicken Sie auf *Einsetzen*."
                ),
                "field:size",
                "dialog.accept",
            ),
            step(
                _(
                    "Das Gewinde sitzt in der Bohrung. Ist sie zu weit, etwa ein Schraubenloch "
                    "derselben Größe, sagt es der Prüfbericht."
                ),
                "viewport",
            ),
        ),
        teaches=("insert_printed_thread",),
        topics=("parts",),
    ),
    Guide(
        key="round-edges",
        title=_("Kanten abrunden oder anfasen"),
        summary=_(
            "Die Kanten eines Teils rund oder schräg machen, mit Vorschau vor dem Übernehmen."
        ),
        steps=(
            step(_("Klicken Sie auf das Teil. Es ist jetzt gewählt."), "viewport"),
            # Ob *Ändern* offen steht, hängt an der Zahl seiner Einträge
            # (``selection_operations.OPEN_UP_TO``); am Netz stand es offen, und
            # „klappen Sie auf“ hätte es zugeklappt (Prüfung am Fenster, 11.10.2026).
            step(
                _(
                    "Rechts unter *Auswahl* steht der Abschnitt *Ändern*. "
                    "Ist er zugeklappt, klappen Sie ihn auf."
                ),
                "section:shaping",
            ),
            step(_("Klicken Sie auf *Verrunden*."), "operation:fillet_edges"),
            step(
                _("Tragen Sie den *Radius* ein und wählen Sie unter *Kanten*, welche rund werden."),
                "field:radius",
                "field:edges",
            ),
            step(
                _("Die Vorschau zeigt die Rundung. Klicken Sie auf *Verrunden*."), "dialog.accept"
            ),
            step(
                _("Die Kanten sind rund. Schräg statt rund geht genauso mit *Fase anbringen*."),
                "viewport",
                "operation:chamfer_edges",
                whole_window=True,
            ),
        ),
        teaches=("fillet_edges", "chamfer_edges"),
        topics=("features",),
    ),
    Guide(
        key="label-a-part",
        title=_("Ein Teil beschriften"),
        summary=_("Text erhaben oder vertieft auf eine Fläche setzen."),
        steps=(
            step(
                _(
                    "Klicken Sie zweimal auf die Fläche für den Text: erst ist das Teil gewählt, "
                    "dann die Fläche."
                ),
                "viewport",
            ),
            step(
                _("Rechts unter *Auswahl*: Klicken Sie auf *Text aufbringen*."),
                "operation:label_text",
            ),
            step(
                _("Tippen Sie den *Text* ein und wählen Sie die *Schriftgröße*."),
                "field:text",
                "field:size",
            ),
            step(
                _(
                    "Unter *Art* wählen Sie erhaben oder vertieft. "
                    "Klicken Sie auf *Text aufbringen*."
                ),
                "field:mode",
                "dialog.accept",
            ),
            step(_("Der Text steht auf der Fläche."), "viewport"),
        ),
        teaches=("label_text",),
        topics=("labels",),
    ),
    Guide(
        key="draw-and-pull",
        title=_("Einen Körper aufziehen"),
        summary=_("Mit drei Klicks ein eigenes Teil auf das Bett stellen."),
        steps=(
            # Der Startbildschirm hat keine Werkzeugleiste; von dort geht es
            # erst über *Neues Projekt* (Prüfung am Fenster, 11.10.2026).
            step(
                _(
                    "Vom Startbildschirm aus klicken Sie zuerst auf *Neues Projekt*, "
                    "dann oben in der Werkzeugleiste auf *Zeichnen*."
                ),
                "toolbar.draw",
            ),
            step(_("Klicken Sie auf das Bett. Dort beginnt das Rechteck."), "viewport"),
            step(
                _(
                    "Klicken Sie die Gegenecke. Oder tippen Sie die Maße: "
                    "50, Tab, 30, Eingabetaste."
                ),
                "viewport",
            ),
            step(
                _("Ziehen Sie die Höhe nach oben und klicken Sie. Das Teil steht."),
                "viewport",
            ),
            step(
                _("Gedruckt wird wie in [Ein Modell prüfen und drucken](manual:print-a-model)."),
                "viewport",
                "report.slicer",
            ),
        ),
        teaches=("sketch_extrude", "sketch_join"),
        topics=("sketch",),
    ),
    Guide(
        key="two-colours",
        title=_("Zweifarbig drucken"),
        summary=_("Einer Fläche ein zweites Filament geben; der Slicer bekommt den Wechsel mit."),
        steps=(
            step(
                _(
                    "Klicken Sie zweimal auf die Fläche: erst ist das Teil gewählt, "
                    "dann die Fläche."
                ),
                "viewport",
            ),
            step(
                _("Rechts unter *Auswahl*: Klappen Sie *Filament und Druck* auf."),
                "filament.section",
            ),
            step(_("Wählen Sie dort das Filament für diese Fläche."), "filament.picker"),
            step(
                _(
                    "Die Fläche hat ihre Farbe. Gedruckt wird wie in "
                    "[Ein Modell prüfen und drucken](manual:print-a-model)."
                ),
                "viewport",
                "report.slicer",
            ),
        ),
        teaches=("paint_slot",),
        topics=("moving",),
    ),
    Guide(
        key="repair-a-model",
        title=_("Ein Modell reparieren"),
        summary=_("Was Solidon beim Einlesen selbst repariert, und wie Sie den Rest beheben."),
        steps=(
            step(
                _(
                    "Beim Einlesen repariert Solidon, was sicher geht. "
                    "Der *Prüfbericht* sagt, was es war."
                ),
                "report",
            ),
            step(_("Klicken Sie auf den Befund und dann auf *Stelle zeigen*."), "report.action"),
            step(_("Die Ansicht zeigt die reparierte Stelle."), "viewport"),
            step(
                _(
                    "Andere Befunde tragen ihre Reparatur als Knopf, "
                    "etwa *Überschneidungen auflösen*."
                ),
                "report.action",
            ),
            step(
                _(
                    "Die Reparatur ist abgeschlossen. Prüfen Sie die übrigen Befunde. Der "
                    "Schritt steht im *Verlauf*."
                ),
                "history.last",
            ),
        ),
        teaches=("repair",),
        topics=("trouble",),
    ),
)


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
