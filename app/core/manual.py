"""Das Handbuch (Bauplan §2.7, §37.2).

Zwei Sorten Seiten, aus zwei guten Gründen getrennt.

**Die Referenz ist erzeugt.** Jede Operation, jeder Parameter, jeder Bereich
kommt aus dem Register (§10) — dieselbe Quelle, aus der die Menüs, die Dialoge,
die Kommandozeile und die Werkzeugliste des Agenten entstehen. Ein Handbuch,
das eine zweite Liste führt, ist ein Handbuch, das irgendwann etwas anderes
sagt als das Programm.

**Die Einführung ist geschrieben.** Was ein Operationsstack ist, warum das
Spiel aus dem Materialprofil kommt und was passiert, wenn man dieselbe Zahl
später ändert, steht in keinem Parameterschema. Diese Seiten sind der
Unterschied zwischen „ich sehe eine lange Liste" und „ich weiß, was ich damit
mache" — und sie sind kurz gehalten, weil ein Handbuch, das gelesen werden
soll, keine hundert Seiten haben darf.

Der Text lebt hier und nicht in der Oberfläche: er ist ohne Qt prüfbar, und
die Kommandozeile kann ihn genauso ausgeben wie das Fenster.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Final, Literal

from app.core import guides
from app.core.registry import documentation
from app.core.registry.registry import CATEGORIES, REGISTRY, Registry
from app.i18n import Figure, TranslatableText, _

#: Die fünf Teile des Handbuchs (Konzept Handbuch §4). Gegliedert wird nach
#: dem, was der Kunde vorhat, nicht nach den Bereichen des Programms: Wer
#: anfängt, findet die ersten Schritte; wer eine Aufgabe hat, eine Anleitung;
#: wer nachschlagen will, das Nachschlagewerk — und keiner muss durch die
#: anderen hindurch.
Part = Literal["start", "tasks", "topics", "help", "reference"]

PART_TITLES: Final[dict[Part, TranslatableText]] = {
    "start": _("Erste Schritte"),
    "tasks": _("Anleitungen"),
    "topics": _("Funktionen"),
    "help": _("Hilfe bei Problemen"),
    "reference": _("Nachschlagen"),
}


@dataclass(frozen=True, slots=True)
class Page:
    """Eine Seite des Handbuchs. ``body`` ist Markdown.

    Abbildungen stehen als ``![](figure:schlüssel)`` im Text — ohne Alt-Text,
    denn der gehört in den Abbildungskatalog und nicht in jede Stelle, die ein
    Bild einsetzt. So gibt es ihn genau einmal, und ein Übersetzer bekommt eine
    Zeile zu sehen, an der es nichts zu übersetzen gibt.
    """

    key: str
    title: TranslatableText | str
    body: TranslatableText | str
    generated: bool = False
    """Erzeugte Seiten kommen aus dem Register und stehen hinter den anderen."""
    summary: TranslatableText | str = ""
    """Ein Satz vorweg: was auf dieser Seite steht, für den, der sie überfliegt.

    Ein eigenes Feld und kein erster Absatz im Fließtext, damit ein Test ihn
    einfordern kann — eine Kurzfassung, die man vergessen darf, schreibt beim
    zwanzigsten Kapitel niemand mehr. Die erzeugten Seiten haben keine: Was
    dort steht, sagt ihre Überschrift.
    """
    part: Part = "reference"
    """Der Teil des Handbuchs, in dem die Seite steht. Gesetzt wird er von
    :func:`pages` aus der Gliederung (:data:`OUTLINE`), nicht an jeder Seite:
    Welche Seite wohin gehört, ist eine Entscheidung über das Ganze und steht
    deshalb an einer Stelle."""

    def figures(self) -> tuple[str, ...]:
        """Die Schlüssel der Abbildungen, in der Reihenfolge ihres Auftretens."""
        return tuple(FIGURE_PATTERN.findall(str(self.body)))

    def text(self) -> str:
        """Kurzfassung und Text, so wie die Seite gelesen wird.

        Eine Stelle für beide Ausgaben. Setzten Fenster und Markdown sie je
        selbst zusammen, stünde die Kurzfassung irgendwann nur noch in einer
        von beiden — und niemandem fiele auf, in welcher.
        """
        opening = f"*{self.summary}*\n\n" if self.summary else ""
        return f"{opening}{self.body}"


#: Ein Bildverweis im Fließtext einer Seite.
FIGURE_PATTERN: Final = re.compile(r"!\[\]\(figure:([a-z0-9-]+)\)")

#: Die erste Seite, „Wo fange ich an?": Auf sie zeigen der Handbuchknopf des
#: Startbildschirms und F1 im Hauptfenster (Konzept Handbuch §4, §7).
#:
#: Der Schlüssel steht hier und nicht in der Oberfläche: Welche Seite gemeint
#: ist, weiß das Handbuch. ``tests/test_manual.py`` hält Knopfhinweis und
#: Seitentitel zusammen. Er heißt ``start`` wie die frühere erste Seite, die sie
#: ersetzt, damit ein Verweis auf ``handbuch.html#start`` weiter an den Anfang
#: führt.
WHERE_TO_START: Final = "start"
SPACEMOUSE_ACCESS: Final = "spacemouse-access"

#: Der Vorsatz der erzeugten Referenzkapitel. Ohne ihn hießen „Die Bausteine“
#: und das Kapitel „Bausteine“ beide ``parts``, „Zeichnen“ und „Skizze“ beide
#: ``sketch``, und wer eine Seite beim Schlüssel suchte, bekam die erste:
#: F1 in *Mutternfalle* landete oben auf der Erklärseite statt am Eintrag.
#: Derselbe Wert ist der Anker der Website (``#ref-holes``).
REFERENCE_PAGE_PREFIX: Final = "ref-"


def reference_key(category: str) -> str:
    """Der Seitenschlüssel des Referenzkapitels einer Kategorie."""
    return f"{REFERENCE_PAGE_PREFIX}{category}"


def operation_anchor(operation: str) -> str:
    """Die unsichtbare, sprachunabhängige Sprungmarke eines Referenzeintrags."""
    return f"operation-{operation}"


def reference_anchors(key: str, registry: Registry | None = None) -> tuple[tuple[str, str], ...]:
    """Sprungmarke und Kundentitel in derselben Reihenfolge wie die Referenz.

    Gleiche Titel bleiben verschiedene Ziele. Die Oberfläche setzt die
    Anker nach ihrem sicheren Markdownimport, die Website als HTML-Kennung;
    im Lesetext erscheint keiner davon.
    """
    if not key.startswith(REFERENCE_PAGE_PREFIX):
        return ()
    category = key.removeprefix(REFERENCE_PAGE_PREFIX)
    return tuple(
        (operation_anchor(spec.name), str(spec.title))
        for spec in (registry or REGISTRY).by_category().get(category, ())
    )


_SPACEMOUSE_LINUX = _(
    "**Linux (USB oder USB-Empfänger, mit systemd-logind)**\n\n"
    "Ein gefundenes Gerät kann noch für Ihren Benutzer gesperrt sein. Mit "
    "*Anleitung kopieren* in der *3D-Maus-Hilfe* erhalten Sie die Befehle für genau "
    "die erkannte Hersteller- und Produktkennung. Prüfen Sie diese vor dem "
    "Ausführen im Terminal. Das Anlegen der udev-Regel benötigt einmalig "
    "Administratorrechte; Solidon selbst läuft als normaler Benutzer. "
    "Die Regel gibt den Zugriff nur dem aktiven, lokal angemeldeten Benutzer. "
    "Stecken Sie das Gerät danach ab und wieder ein; Solidon sucht automatisch weiter.\n\n"
    "Die Regel gilt für USB, auch mit USB-Empfänger. Bei Bluetooth zuerst per USB "
    "verbinden und die Anleitung für dieses Gerät kopieren. Ohne systemd-logind "
    "lassen Sie die benutzerbezogene Gerätefreigabe durch Ihre Systemverwaltung "
    "einrichten. Andere Programme, die das Gerät exklusiv geöffnet haben, zuerst schließen."
)
_SPACEMOUSE_MAC = _(
    "**macOS**\n\n"
    "Installieren oder aktualisieren Sie 3DxWare von 3Dconnexion und aktivieren "
    "Sie dessen Treibererweiterung. Ab macOS 15: „Systemeinstellungen › Allgemein "
    "› Anmeldeobjekte & Erweiterungen › Treibererweiterungen“ öffnen und "
    "„3DconnexionHelper“ einschalten. Bis macOS 14: unter „Datenschutz & Sicherheit“ "
    "die blockierte Systemsoftware von „3DconnexionHelper“ erlauben. Folgen Sie "
    "den weiteren Hinweisen des Treiberinstallationsprogramms und starten Sie "
    "Solidon danach neu. Die Anleitung des Herstellers steht unter "
    "3dconnexion.com im Support unter „Enabling 3Dconnexion Extension After Installing the Driver“."
)
_SPACEMOUSE_WINDOWS = _(
    "**Windows und andere Systeme**\n\n"
    "Stecken Sie das Gerät ab und wieder ein. Schließen Sie andere Programme, "
    "die es exklusiv verwenden könnten, und prüfen Sie den Anschluss sowie "
    "die Geräte- und Treiberhinweise von 3Dconnexion. Solidon sucht automatisch weiter."
)


def spacemouse_access_help(platform: str, device: tuple[int, int] | None = None) -> str:
    """Die Betriebssystemhilfe, optional mit einer gerätebezogenen USB-Freigabe.

    Die Regel läuft vor systemds 73-seat-late.rules. Dessen uaccess-Builtin
    vergibt die ACL an den aktiven Benutzer des Sitzplatzes, keine Freigabe
    für alle Benutzer. Die Befehle werden nur angezeigt beziehungsweise kopiert.
    """
    if platform == "darwin":
        return str(_SPACEMOUSE_MAC)
    if not platform.startswith("linux"):
        return str(_SPACEMOUSE_WINDOWS)
    text = str(_SPACEMOUSE_LINUX)
    if device is not None:
        vendor, product = device
        path = f"/etc/udev/rules.d/70-solidon-spacemouse-{vendor:04x}-{product:04x}.rules"
        rule = (
            f'SUBSYSTEM=="hidraw", ATTRS{{idVendor}}=="{vendor:04x}", '
            f'ATTRS{{idProduct}}=="{product:04x}", TAG+="uaccess"'
        )
        text += (
            f"\n\n```sh\nsudo tee {path} <<'EOF'\n{rule}\nEOF\n"
            "sudo udevadm control --reload-rules\n```"
        )
    return text


def _where_to_start_page() -> Page:
    """Die erste Seite: welche Anleitung zu welchem Vorhaben führt.

    Die zwei Listen entstehen aus :data:`OUTLINE`; ihre Einträge werden in
    :data:`guides.GUIDES` aufgelöst. Eine neue Anleitung steht ohne Nachtrag
    hier, wenn sie in der Gliederung steht, und jeder Verweis heißt in jeder
    Sprache wie die Seite, auf die er führt. Was die frühere erste Seite als
    einzige wusste, steht kurz darunter, mit ihren vier Bildschirmfotos: die
    Fragen beim ersten Start, welche Dateien Solidon liest, das Auswählen in
    zwei Stufen, der Dialog einer Handlung und der Prüfbericht.
    ``main-window`` ist zugleich das Vorschaubild der Website
    (``og:image`` in ``tools/make_manual.py``).
    """

    def listed(part: Part) -> str:
        # Der Doppelpunkt gehört zum übersetzten Satz: Französisch setzt davor
        # ein Leerzeichen.
        guide_by_key = {guide.key: guide for guide in guides.GUIDES}
        return "\n".join(
            "* "
            + str(
                _(
                    "{guide}: {summary}",
                    guide=f"[{guide.title}](manual:{guide.key})",
                    summary=guide.summary,
                )
            )
            for key in dict(OUTLINE)[part]
            if (guide := guide_by_key.get(key)) is not None
        )

    blocks = [
        str(
            _(
                "Jede Anleitung zeigt ihre Schritte an Bildern der echten Oberfläche. "
                "Eine Nummer und ein Rahmen markieren, wohin Sie klicken. Nehmen Sie "
                "die, die zu Ihrem Vorhaben passt."
            )
        ),
        f"**{_('Vom Start bis zum Druck')}**\n\n{listed('start')}",
    ]
    tasks = listed("tasks")
    if tasks:
        blocks.append(f"**{_('Einzelne Aufgaben')}**\n\n{tasks}")
    blocks += [
        str(
            _(
                "**Beim ersten Start** fragt Solidon nach Sprache, Slicer und Drucker. Die "
                "Drucker kommen aus dem gewählten Slicer, jeder einmal, und das Suchfeld über der "
                "Liste findet Ihren schnell; die Düse wählen Sie später in den "
                "Druckeinstellungen. Fehlt Ihr Drucker, legen Sie einen eigenen mit seinen "
                "tatsächlichen Bauraummaßen an. *Später einstellen* geht auch. Alles ändern Sie "
                "jederzeit in den Einstellungen. Filamente aus Ihrem Slicer übernehmen Sie im "
                "Filamentlager als eigene Spulen. Auf dem Startbildschirm führen vier Touren "
                "durch Modellanpassung, Konstruktion, erzeugte Modelle und freies Formen. "
                "Solange die Szene leer ist, zeigt der Arbeitsbereich die Einstiege: Quader, "
                "Zylinder, *Zeichnen*, *Bausteine* und mit KI-Zugang *Im Chat beschreiben*; "
                "eine Datei ziehen Sie einfach hinein."
            )
        ),
        "![](figure:start-screen)",
        str(
            _(
                "**Welche Dateien Solidon öffnet:** STL, 3MF, OBJ, PLY, OFF, GLB, GLTF, STEP "
                "und STP als Modell, SVG und DXF als Zeichnung zum Hochziehen. Steht in der "
                "Datei keine Einheit, wie bei STL, fragt Solidon nach; fast alles im Netz ist "
                "in Millimetern. Große Dateien liest Solidon im Hintergrund, das Fenster bleibt "
                "bedienbar. Eine direkte Adresse einer Modelldatei ziehen Sie aus dem Browser "
                "auf das Fenster oder öffnen sie über *Datei → Modell aus dem Netz …*. Bei "
                "einer Modellseite bietet Solidon die gefundenen Dateien zur Auswahl an; "
                "geschützte Downloads laden Sie im Browser herunter und öffnen die lokale "
                "Datei."
            )
        ),
        "![](figure:main-window)",
        str(
            _(
                "**Der Prüfbericht** rechts sagt, was am Modell nicht stimmt. Ein Klick "
                "auf einen Befund zeigt darunter, was Sie dagegen tun können."
            )
        ),
        "![](figure:report)",
        str(
            _(
                "**Auswählen geht in zwei Stufen.** Der erste Klick wählt das ganze Teil, "
                "der zweite die Fläche darin; `Esc` geht eine Stufe zurück. Ein gerade "
                "angelegtes Teil ist schon gewählt, dort wählt der erste Klick die Fläche. "
                "Ein weiteres Teil nehmen Sie mit gedrückter Umschalt- oder `Strg`-Taste "
                "dazu, am Mac mit `⌘`. Rechts unter *Auswahl* stehen dann die Handlungen, "
                "die dazu passen. Der Rechtsklick zeigt den Schritt, aus dem die Stelle "
                "stammt, das Zeichnen auf der Fläche, das Ausblenden, *Objekt entfernen* "
                "und bei mehreren Teilen *Vereinigen*."
            )
        ),
        str(
            _(
                "**Im Operationsdialog stehen die Maße.** Vorn stehen die Werte, die "
                "man meistens ändert. Der Rest liegt hinter *Weitere Einstellungen* "
                "und passt in aller Regel schon."
            )
        ),
        "![](figure:op-dialog)",
        str(
            _(
                "**Der Rest des Handbuchs:** *{topics}* erklärt die Bereiche des Programms "
                "im Einzelnen, *{help}* hilft, wenn etwas nicht geht, und *{reference}* "
                "führt jedes Fachwort und jede Operation mit ihren Werten. Die Suche im "
                "Handbuchfenster versteht auch eigene Wörter wie „abrunden“."
            )
        ).format(
            topics=PART_TITLES["topics"],
            help=PART_TITLES["help"],
            reference=PART_TITLES["reference"],
        ),
    ]
    return Page(
        key=WHERE_TO_START,
        title=_("Wo fange ich an?"),
        summary=_("Welche Anleitung zu Ihrem Vorhaben passt, und was Sie vorher wissen sollten."),
        body="\n\n".join(blocks),
    )


def _spacemouse_page() -> Page:
    """Dieselbe Hilfe im Handbuch und im kopierbaren Gerätehinweis."""
    return Page(
        key=SPACEMOUSE_ACCESS,
        title=_("Wenn die 3D-Maus nicht reagiert"),
        summary=_(
            "Ein erkanntes Gerät braucht Zugriff durch Solidon; hier steht der Weg zur Freigabe."
        ),
        body="\n\n".join(
            spacemouse_access_help(platform) for platform in ("linux", "darwin", "win32")
        ),
    )


#: Die geschriebenen Seiten, in der Reihenfolge, in der sie jemand liest.
INTRODUCTION: Final[tuple[Page, ...]] = (
    Page(
        key="what",
        summary=_("Wofür das Programm gedacht ist und wofür nicht."),
        title=_("Was Solidon ist"),
        body=_(
            "Solidon baut und ändert Modelle für den 3D-Drucker und macht sie "
            "druckfertig.\n\n"
            "* **Jeder Schritt bleibt eine Zahl.** Eine Bohrung, die zwei Millimeter "
            "danebensitzt, wird verschoben, nicht neu gebohrt.\n"
            "* **Das Spiel einer Passung kommt aus dem Material.** Wer es einmal misst, "
            "verbessert damit auch Teile, die er früher gebaut hat.\n"
            "* **Bausteine statt Handarbeit:** Mutternfalle, Heat-Set-Einpressbuchse, "
            "Rastnase, Filmscharnier, Magnettasche, je ein Klick statt einer halben "
            "Stunde.\n\n"
            "**Skizzen gehören dazu.** Grundformen und eigene Zeichnungen mit Bedingungen "
            "werden hochgezogen, eingeschnitten, gedreht oder entlang eines Bogens "
            "geführt, und jedes Maß darf ein Projektparameter sein.\n\n"
            "**Was es nicht ist:** kein Slicer, die Druckdatei rechnet weiter Ihr Slicer. "
            "Keine Cloud, kein Konto, keine Telemetrie. Von sich aus meldet sich Solidon "
            "nur beim Start, um nach einer neuen Version zu fragen, und nennt dabei nur "
            "die eigene Versionsnummer; das lässt sich in den Einstellungen abschalten. "
            "Ohne Netz, Konto und Sprachmodell bleibt alles außer dem Chat benutzbar."
        ),
    ),
    Page(
        key="window",
        summary=_("Was die Bereiche des Fensters können, über das hinaus, was man sieht."),
        title=_("Das Fenster"),
        body=_(
            "Wo was steht, zeigt [Das Fenster auf einen Blick](manual:window-overview). "
            "Hier steht, was die Bereiche können.\n\n"
            "![](figure:window)\n\n"
            "**Die Projektkopfzeile** nennt Projekt, Drucker und die verwendeten "
            "Filamente. Ein Klick auf den Drucker wählt für dieses Projekt einen anderen. "
            "Hat das Projekt mehrere Platten, stellt der Plattenwähler daneben die "
            "Ansicht auf eine davon.\n\n"
            "**Oben die Werkzeugleiste.** *Zeichnen* schwenkt die Ansicht senkrecht auf "
            "die Zeichenebene, das Modell tritt durchscheinend zurück. *Formen* und "
            "*Skelett* brauchen einen gewählten Körper und sagen das schon vor dem Klick. "
            "Escape kommt aus jedem Werkzeug zurück.\n\n"
            "**Unter dem Modell die Werkzeugzeile:** *Schnitt*, *Messen*, *Bewegen*, "
            "*Analyse*, *Schichten*, *Explosion* und *Teilen*, der Reihe nach auf Alt+1 "
            "bis Alt+7. Nur *Bewegen* und *Teilen* ändern das Modell, jeweils als "
            "Schritt im Verlauf; die anderen sehen nur hin.\n\n"
            "**Links** stehen Objekte, Parameter, Verlauf und Filamente, jeder Abschnitt "
            "einklappbar. Unter jedem Körper im Objektbaum steht, was die Erkennung darin "
            "gefunden hat.\n\n"
            "**Die Maus in der Ansicht.** Links klicken wählt aus, links ziehen "
            "verschiebt die Ansicht. Drücken Sie links auf einen gewählten Körper, "
            "bewegen Sie den Körper. Rechts ziehen dreht, das gedrückte Mausrad kippt "
            "nach oben und unten, Scrollen zoomt zum Zeiger. Pos1 (*Einpassen*) rahmt den "
            "gewählten Körper, ohne Auswahl die ganze Szene.\n\n"
            "**Mit der Tastatur fliegen.** W und S fahren vor und zurück, A und D "
            "seitwärts, Q und E kippen. Solange die Taste liegt, fliegt die Ansicht "
            "gleichmäßig, und anders als der Zoom fliegt sie durch das Teil hindurch. Die "
            "Tasten wirken, sobald die Ansicht den Fokus hat, also nach einem Klick "
            "hinein.\n\n"
            "**Wer es anders gewohnt ist, stellt um.** Die Einstellungen bieten vier "
            "weitere Belegungen nach Cura, Bambu Studio, Orca und PrusaSlicer, CAD und "
            "Blender; dort wählt die linke Taste wieder aus, und die Tastatur fliegt "
            "nicht. Eine 3D-Maus (SpaceMouse) fährt dieselbe Kamera: Schieben verschiebt "
            "das Teil, Drehen dreht es, Ziehen holt es näher, eine Gerätetaste passt "
            "alles ein. Geschwindigkeit und Richtung stehen in den Einstellungen, sobald "
            "ein Gerät gesehen wurde. Reagiert es nicht, hilft [Wenn die 3D-Maus nicht "
            "reagiert](manual:spacemouse-access).\n\n"
            "**Rechts daneben drei Reiter:** *Auswahl*, *Prüfbericht* und *Chat*. Beim "
            "Zeichnen kommt einer für die Bedingungen dazu, in der Tour einer für ihre "
            "Schritte. F9 blendet den ganzen Bereich aus; dann hat das Modell den Platz, "
            "und die Statusleiste zählt die offenen Befunde. Beide Karten lassen sich "
            "am Griff oben rechts verschieben, mit der Maus oder den Pfeiltasten. Ein "
            "Doppelklick auf den Griff oder *Ansicht → Karten an ihren Platz* legt sie "
            "zurück.\n\n"
            "**Die Auswahl** kommt nach vorn, sobald Sie im Bild oder im Objektbaum etwas "
            "anklicken. Oben stehen die Maße dessen, was Sie "
            "angeklickt haben, darunter die passenden Handlungen, vorn die häufigsten: "
            "bei zwei Körpern *Vereinigen*, *Abziehen* und *Schnittmenge*, bei einem "
            "*Bohrung setzen*, *Aushöhlen*, *An Ebene teilen* und *Modell nachbauen*. "
            "Alle weiteren stehen in Gruppen "
            "darunter, und ein Suchfeld findet jede. Ohne Auswahl stehen dort die "
            "Handlungen für alle Körper, etwa *Druckoptimal ausrichten*. Der Knopf "
            "*Bausteine* öffnet den Katalog. Was der Reiter an einem Merkmal zeigt, "
            "steht in [Was Solidon im Modell erkennt](manual:features).\n\n"
            "**Der Prüfbericht** springt bei einer neuen Meldung nicht nach vorn. Sein "
            "Reiter zählt Fehler (X) und Warnungen (!) und blinkt einige Sekunden, rot "
            "bei einem Fehler, gelb bei einer Warnung. Getönt bleibt er, bis Sie den "
            "Bericht angesehen haben. Gleiche Meldungen stehen in einer Zeile, ihre Zahl "
            "in Klammern davor; ein Klick wählt alle betroffenen Teile, und eine Handlung "
            "fragt, für welche davon sie gelten soll.\n\n"
            "**Ein Menü für die Auswahl gibt es nicht.** Die Menüleiste behält, was ohne "
            "Auswahl geht. Tastenkürzel gelten weiter, und die Befehlspalette findet jede "
            "Handlung über ihren Namen, mit dem Kürzel daneben.\n\n"
            "**Es gibt keine Betriebsarten** und keine Werkbänke, zwischen denen man "
            "umschalten müsste. Es gibt die Szene."
        ),
    ),
    Page(
        key="looking",
        summary=_(
            "Was Messen, Schnitt, Analysekarten und Schichtvorschau zeigen, bevor gedruckt wird."
        ),
        title=_("Hinsehen, bevor gedruckt wird"),
        body=_(
            "Ob ein Modell druckbar ist, sieht man ihm selten an: an der dünnsten Wand, "
            "am Überhang, an der Insel, die in der Luft beginnt. Fünf Werkzeuge unter der "
            "Ansicht zeigen es, und keines ändert das Modell. Kaputt machen kann man "
            "damit nichts.\n\n"
            "**Messen** zeigt den Abstand zweier Punkte; der Zeiger fängt Ecken und "
            "Kanten. Solange gemessen wird, zeigt die Ansicht ohne Perspektive, damit man "
            "nicht danebenzielt. Ein Klick auf eine Fläche misst die **Wandstärke** "
            "dahinter. Jede Strecke bleibt als Bemaßung stehen, bis Sie sie wegnehmen, so "
            "lassen sich mehrere vergleichen.\n\n"
            "**Schnitt** legt eine Ebene durch das Modell, und der Regler zieht sie "
            "hindurch. Die Schnittfläche wird geschlossen gezeichnet, ein Hohlraum ist "
            "also als Hohlraum zu erkennen.\n\n"
            "**Analyse** färbt das Modell nach einer von sieben Karten. **Wandstärke**, "
            "**Überhang**, **Stützbedarf** und **Krümmung** sagen, ob es sich drucken "
            "lässt. **Netzfehler** zeigt offene Kanten, Stellen mit mehr als zwei Flächen "
            "und Flächen, die einander durchdringen; dort liegt meist der Grund, wenn "
            "Vereinigen oder Abziehen scheitert. **Merkmale** zeigt, was die Erkennung "
            "gefunden hat, **Passungen**, welche Flächen an einer Passung hängen und "
            "welche davon verletzt ist. Die Legende nennt immer Zahlenbereich und "
            "Herkunft der Werte. Ein Klick auf eine Warnung im Prüfbericht fährt die "
            "Kamera an die Stelle.\n\n"
            "**Schichten** zeigt das Modell so, wie es in Schichten zerfällt; bei "
            "mehreren Körpern wählen Sie zuerst einen. Der Regler fährt hindurch, daneben "
            "stehen Schichtnummer und Gesamtzahl, Z-Höhe, Querschnittsfläche, Zahl der "
            "Inseln und Überhangfläche. Kontur, Insel und Überhang unterscheidet die "
            "Legende nicht nur durch die Farbe. Das ist Solidons eigene Schichtanalyse "
            "und nicht die Rechnung des Slicers; beide Zahlen stehen getrennt da.\n\n"
            "![](figure:layers)\n\n"
            "**Explosion** zieht mehrere Körper zum Ansehen auseinander. Export und "
            "Verlauf bleiben unberührt.\n\n"
            "**Auch der Schatten sagt etwas.** Er fällt für jedes Stück einzeln, und ein "
            "Teil, das in mehrere Stücke zerfallen ist, wirft mehrere Schatten."
        ),
    ),
    Page(
        key="features",
        summary=_(
            "Was Solidon in einem geladenen Modell wiedererkennt und was ein Klick darauf "
            "möglich macht."
        ),
        title=_("Was Solidon im Modell erkennt"),
        body=_(
            "Eine STL-Datei enthält nur Dreiecke, keine Bohrung und kein Maß. "
            "Solidon liest die Formen zurück: Nach dem Laden passt eine Erkennung "
            "Zylinder, Kegel, Kugeln, Ringe und Rundungen in die Flächen. Was "
            "passt, wird ein **Merkmal** mit Mitte, Achse, Maß und einer Kennung, "
            "die bleibt. Die Bohrung ist dann wieder eine Bohrung.\n\n**Dreizehn "
            "Arten, und der Name sagt die Lage:**\n\n* **Bohrung**: ein Zylinder, "
            "der hineingeht, durchnummeriert als „Bohrung 1“, „Bohrung 2“.\n* "
            "**Langloch**: zwei runde Enden und zwei gerade Flanken, mit Breite "
            "und Länge.\n* **Muster**: viele gleiche Zellen auf einer Fläche, wie "
            "*Textur aufbringen* sie zeichnet. Ein Wabenhalter mit 196 Zellen ist "
            "ein Merkmal mit Teilung, Zellbreite und Tiefe; *Merkmal ändern* setzt "
            "sie neu, *Merkmal entfernen* füllt die Zellen. Ein kleines Feld, das nur "
            "als einzelne Merkmale dasteht, markieren Sie im Objektbaum und fassen "
            "es mit *Als Muster zusammenfassen* zusammen.\n* **Zapfen**: ein "
            "Zylinder, der heraussteht.\n* **Senkung** oder **Verjüngung**: ein "
            "Kegel, hinein oder heraus.\n* **Pfanne** oder **Kuppel**: eine "
            "Kugelfläche.\n* **Kehle** oder **Wulst**: ein umlaufender Ring.\n* "
            "**Hohlkehle** oder **Verrundung**: eine gerundete Kante.\n* "
            "**Innengewinde** oder **Außengewinde**.\n* **Lufteinschluss**: ein "
            "Hohlraum ohne Weg nach außen. Ob er gewollt ist, etwa als Tasche für "
            "einen Magneten, weiß nur, wer das Teil gezeichnet hat.\n* **Offene "
            "Kante**: ein Loch im Netz, das repariert werden will.\n* **Fläche**, "
            "benannt nach ihrer Richtung: „Oberseite“, „Vorderseite“, „Rechte "
            "Seite“. Eine Wand, die nach innen zeigt, heißt „Oberseite innen“.\n* "
            "**Gerundete Seite**: ein gebogenes Stück Oberfläche ohne eigene "
            "Ebene, etwa der Bogen eines D. Darauf können Sie bohren, Grundkörper "
            "und Bausteine platzieren und ein eigenes Filament zuweisen. Zum "
            "Zeichnen wählen Sie eine ebene Fläche oder eine Skizzenebene.\n\nWo "
            "zwei Namen stehen, entscheidet die Richtung: innen Hohlkehle, außen "
            "Verrundung. Im Objektbaum stehen die Merkmale unter ihrem Körper, "
            "gleichartige zusammen.\n\n**Nicht jede Form wird ein Merkmal.** Die "
            "Erkennung braucht ausreichend genaue und eindeutige Geometrie. Ihre "
            "Mindestgrößen sind keine allgemeinen Druckgrenzen. An Freiformen "
            "lässt sie ungesicherte Kugeln, Ringe, Kegel und Verrundungen aus; "
            "Bohrungen, Zapfen, Flächen und Gewinde bleiben. Der Prüfbericht nennt "
            "ausgelassene Rundformen. Eine vollständige Kugel oder ein Ring kann "
            "weiterhin erkannt werden.\n\n**Dieselbe Form in anderer Lage.** Ein Teil, "
            "das Sie in Solidon verschieben oder drehen, behält seine Merkmale und "
            "deren Kennungen. Wird dasselbe Teil in anderer Lage neu eingelesen, kann "
            "eine Form knapp an der Grenze der Erkennung, etwa ein sehr flacher Bogen "
            "oder ein kurzes Kegelstück, einmal als Merkmal erscheinen und einmal "
            "nicht. Dasselbe kann zwischen Rechnern mit verschiedenen Prozessoren "
            "vorkommen.\n\n## Der Reiter Auswahl\n\nWer etwas anklickt, "
            "im Bild oder im Objektbaum, findet es rechts unter *Auswahl*; der Klick "
            "holt den Reiter nach vorn. "
            "Oben steht, was gewählt ist, etwa „Bohrung 1“, darunter bei einer "
            "Bohrung ihr Maß und die Normgröße dazu: 5,19 mm ist das Durchgangsloch für "
            "M5. Darunter stehen die Handlungen, je eine Gruppe aus "
            "Feldern.\n\n**Die Felder stehen auf den gemessenen Werten**, denn eine "
            "geänderte Zahl ist die Operation. Wer die Bohrung zwei Millimeter "
            "weiter rechts haben will, ändert genau diese Zahl. Sobald das Tippen "
            "kurz ruht, zeigt das Bild die Vorschau. *Übernehmen* unten führt die "
            "Handlung aus, deren Felder Sie zuletzt angefasst haben, und welche "
            "das ist, steht darüber. Erst dann entsteht ein Schritt im "
            "Verlauf.\n\n**Lieber zeigen als tippen?** *Im Bild einstellen* über "
            "*Übernehmen* gibt dem Loch im Bild einen Griff zum Versetzen und "
            "Drehen, Knöpfe zum Ziehen und Maßlinien zu zwei Kanten der Fläche; "
            "jedes Maß lässt sich dort auch eintippen. Ein gezogenes "
            "Langloch behält dabei seine Form. *Übernehmen* macht daraus einen "
            "Schritt, *Abbrechen* oder Escape verwirft ihn.\n\n**Ein leeres "
            "Koordinatenfeld heißt: Das Loch bleibt, wo es ist.** Bei *Bohrung "
            "ändern* und *Zum Langloch ziehen* stehen X, Y und Z auf „wie "
            "gemessen“. Eine eingetragene Zahl ist eine neue Stelle, auch die "
            "Null; so kommt ein Loch genau in die Mitte des Teils.\n\n**Sechs "
            "Handlungen gibt es**, je nach Art:\n\n* *Merkmal verschieben*: die neue "
            "Mitte als X, Y, Z.\n* *Bohrung ändern* oder *Merkmal ändern*: der neue "
            "Durchmesser, bei einer Bohrung samt Materialtoleranz; bei einem "
            "Langloch die Breite, die Enden wachsen mit.\n* *Zum Langloch ziehen*: "
            "Länge und Richtung. An einer runden Bohrung steht in der Länge ihr "
            "doppelter Durchmesser, die Schraube hat dann einen Durchmesser Weg. "
            "Ein Langloch lässt sich verlängern oder verkürzen und behält seine "
            "Richtung, bis Sie sie ändern. Die Materialtoleranz weitet das "
            "Langloch, der Weg der Schraube bleibt der eingegebene.\n* *Merkmal "
            "drehen*: Achse und Winkel.\n* *Merkmal verdoppeln*: dieselbe Bohrung "
            "ein zweites Mal an anderer Stelle.\n* *Merkmal entfernen*: ohne Feld, "
            "*Übernehmen* genügt.\n\nBohrung und Langloch können alle sechs, ein "
            "Zapfen alles außer dem Ziehen. Eine Kugelfläche lässt sich weder "
            "drehen noch ziehen. Ein Kegel kann alles außer dem Ziehen, solange er "
            "für sich steht; über einer Bohrung lässt er sich nicht allein "
            "versetzen. Eine Verrundung ändert ihren Radius oder verschwindet "
            "ganz, auch im eingelesenen Modell. Ein Lufteinschluss lässt sich "
            "verschieben und entfernen; entfernt wird er mit Material gefüllt. "
            "Ein Gewinde ändert Durchmesser und Steigung oder wird ganz entfernt; "
            "verschieben, drehen und verdoppeln lässt es sich nicht. Fläche, gerundete "
            "Seite, offene Kante und Ring haben keine dieser Handlungen.\n\n**Was nicht "
            "geht, steht als Satz da**, nicht als "
            "graues Feld, an einem Ring etwa der Weg über den ganzen Körper oder "
            "einen Ring als Werkzeug.\n\n**Mehrere gleichartige Merkmale am selben "
            "Körper** bekommen an jeder Handlung einen Haken wie „Auf alle 4 "
            "gleichartigen anwenden“. Vier Bohrungen einer Lochreihe werden so in "
            "einem Schritt aufgebohrt, und ein Strg+Z nimmt alle vier "
            "zurück.\n\n**An einer Fläche** gilt keine der sechs Handlungen. Dort "
            "setzen die Bausteine an, und der Knopf *Bausteine* öffnet den "
            "Katalog.\n\n**Eine Kante ist das Dritte, was ein Klick treffen kann.** "
            "Der erste Klick wählt den Körper, der zweite die Kante. Rechts stehen "
            "dann *Verrunden*, *Fase anbringen* und *Wulst anlegen* mit je einem "
            "Maß. Das geht auch an einem eingelesenen Modell; die Rundung besteht "
            "dort aus geraden Stücken, die feiner sind, als eine Düse auflöst. Für "
            "alle senkrechten Kanten wählen Sie im Dialog die Gruppe statt jeder "
            "Kante einzeln. Auch *Fläche versetzen* und *Formschräge anstellen* "
            "arbeiten am eingelesenen Netz.\n\n**Zwei markierte Merkmale zeigen "
            "ihren Abstand**, von Mitte zu Mitte und je Achse in X, Y und Z. Das "
            "ist eine Auskunft ohne Knopf und ohne Schritt im Verlauf. Bei drei "
            "markierten bleibt der Reiter, wie er war.\n\n## Was mit einem Merkmal "
            "sonst noch geht\n\n**Entf trifft das Merkmal, nicht den Körper.** Ist "
            "eine Bohrung gewählt, nimmt die Taste die Bohrung weg; ohne gewähltes "
            "Merkmal löscht sie alle markierten Objekte.\n\n**Der Griff sitzt am gewählten "
            "Merkmal.** Wer eine Bohrung wählt und *Bewegen* holt, findet ihn an "
            "ihrer Öffnung. Ein Zug daran wird *Merkmal verschieben* oder *Merkmal "
            "drehen*, das Teil bleibt stehen. Einen Skalierwürfel gibt es dort "
            "nicht; eine Bohrung wächst über ihren Durchmesser. Beim Ziehen zeigt "
            "ein Zylinder, wohin es geht; der Körper ändert sich erst beim "
            "Loslassen.\n\n**Beim Verschieben reist die Kennung mit.** Eine Passung, "
            "die auf diese Bohrung zeigt, behält ihren Bezug. Eine Kopie aus "
            "*Merkmal verdoppeln* bekommt eine eigene Kennung.\n\n**Drei Warnungen "
            "können dabei kommen:** eine durchgehende Bohrung, die nach dem "
            "Versetzen nicht mehr durchgeht; ein Langloch, das an einem Ende über "
            "die Kante ragt, auch wenn seine Mitte im Material sitzt; und eine "
            "Senkung über einer Bohrung, die sich nicht allein versetzen lässt, "
            "weil sie in die Bohrung übergeht. Die Meldung nennt den Weg: das "
            "Merkmal in der Mitte wählen oder die Bohrung verschließen und beides "
            "neu anlegen, *Senken* ist eine eigene Operation.\n\n**Was die Erkennung "
            "gefunden hat**, zeigt die Karte *Merkmale* unter *Analyse*, noch "
            "bevor Sie klicken.\n\n**Bohrung und Einlauf gemeinsam ändern.** In "
            "*Bohrung ändern* ändert *Senkung, Stufen und Verengung mitnehmen* "
            "alle Durchmesser zusammen, auch die Öffnung einer Verengung; "
            "Einführbreite, Senkungswinkel und Stufentiefen bleiben. *Nur "
            "Bohrungsdurchmesser* lässt Senkung und Stufen, wie sie sind. Ein "
            "Strg+Z nimmt die Änderung zurück.\n\n**Eine Stelle gezielt erkennen.** "
            "Fehlt an einem großen Netz ein Merkmal, wählen Sie mit der rechten "
            "Maustaste auf der Oberfläche *Merkmale an dieser Stelle erkennen*, "
            "vergrößern den Radius, bis es ganz erfasst ist, und öffnen es in der "
            "Liste über *Merkmal bearbeiten …*. Nach der Vorschau übernimmt "
            "Solidon Erkennung und Änderung zusammen, ein Strg+Z nimmt beides "
            "zurück. *Nur Merkmale übernehmen* speichert allein die Erkennung."
        ),
    ),
    Page(
        key="moving",
        summary=_(
            "Objekte verschieben, drehen und skalieren, Flächen versetzen und Filamente zuweisen."
        ),
        title=_("Bewegen und Färben"),
        body=_(
            "Zwei Wege ändern das Modell selbst: *Bewegen* in der Werkzeugzeile unter der "
            "Ansicht und das Zuweisen von Filament rechts unter *Auswahl*. Jeder Zug "
            "und jede Zuweisung ist ein eigener Schritt im Verlauf, mit Zahlen, die sich "
            "dort später ändern lassen, und Strg+Z nimmt ihn einzeln zurück.\n\n"
            "**Bewegen zeigt einen Griff im Bild:** drei Pfeile zum Verschieben, drei "
            "Ringe zum Drehen und einen Würfel zum gleichmäßigen Skalieren, beschriftet "
            "mit X, Y, Z und S. Bewegt wird, was gewählt ist, das Teil oder eine Bohrung "
            "darin; dann bleibt das Teil stehen ([Was Solidon im Modell "
            "erkennt](manual:features)). Die Statuszeile sagt bei jedem Griff, was er "
            "bewegt.\n\n"
            "**Tippen statt ziehen.** Drei Knöpfe in der Leiste wählen *Verschieben*, "
            "*Drehen* oder *Skalieren*, daneben stehen die Zahlen: X, Y, Z in "
            "Millimetern, ein Winkel in Grad, ein Faktor in Prozent oder gleich das "
            "Zielmaß. Die Eingabetaste wendet an. Während eines Zugs steht die Zahl über "
            "dem Bild; wer eine Ziffer tippt, übernimmt den Zug, die Eingabetaste setzt "
            "genau diesen Wert ohne Einrasten, Esc verwirft den Zug.\n\n"
            "**Der Schatten zieht mit.** Hebt man ein Teil an, läuft er seitlich davon; "
            "ohne Perspektive ist das die einzige Auskunft über die Höhe.\n\n"
            "**Beim Verschieben am Griff kommt nichts über den Rand des Betts:** Solidon "
            "holt den Körper auf eine freie Stelle derselben Platte zurück. Ein getippter "
            "Wert gilt dagegen, wie er dasteht; ob das Teil danach noch auf dem Bett "
            "liegt, sagt der Prüfbericht. Lassen Sie ihn auf einem anderen Bett los, "
            "liegt er danach auf dessen Platte.\n\n"
            "**Rasterfang und Winkelfang** stehen hinter dem Knopf mit dem Raster und ab "
            "Werk auf null, sonst verschluckten sie jeden kleinen Zug. Beim Drehen rastet "
            "der Winkel trotzdem kurz bei Vielfachen von 45 Grad ein, und ein Bogen im "
            "Bild zeigt es.\n\n"
            "**Ist eine Fläche gewählt, sitzt der Griff auf ihr.** Ein Zug versetzt die "
            "Fläche in ihrer Richtung, und die Nachbarwände wachsen mit (*Fläche "
            "versetzen*): Aus dem 20-mm-Klotz wird ein 25-mm-Klotz. Das geht auch am "
            "eingelesenen Modell und bewegt nur die angeklickte Fläche. *Drehen* und "
            "*Skalieren* stehen dann grau und sagen im Tooltip, warum.\n\n"
            "**Für genaue Maße** setzt *Auf Maß bringen* ein Zielmaß, der Dialog von "
            "*Skalieren* verzerrt je Achse. Zwei Teile setzt *An Merkmal ausrichten* "
            "aneinander, Fläche auf Fläche oder Bohrung auf Bohrung. Sein Ziel ist "
            "anfangs leer, und *Übernehmen* wartet, bis Sie es gewählt haben. Der erste "
            "Klick ins Bild wählt es; die Liste im Feld *Ziel* bietet es ebenso an.\n\n"
            "**Farbe kommt über das Filament.** *Filament zuweisen* nimmt den ganzen "
            "Körper, *Filament auf eine Fläche* die angeklickte Fläche, auch eine "
            "gerundete Seite wie den Bogen eines Buchstabens. Gewählt wird ein Filament "
            "mit Namen und Farbe, aus dem eigenen Lager oder neu angelegt; ganz oben "
            "steht, was der Körper schon trägt. Im 3MF-Export wird daraus der "
            "Filamentwechsel, ein Teil ohne eigenes Filament behält die Farbe des "
            "Körpers. *Filament entfernen* nimmt die Zuweisung für die gewählten Körper "
            "oder Flächen zurück.\n\n"
            "**Das Filamentlager** öffnen Sie auf der Startseite oder über *Bearbeiten*. "
            "Jede Spule führt ihren eigenen Restbestand, auch wenn zwei gleich heißen; "
            "ohne bekannte Menge steht dort *Unbekannt*. Die Schnellauswahl weist eine "
            "Spule direkt zu, an gewählten Flächen nur diesen. Änderungen im Lager "
            "überschreiben keine gespeicherten Projektfarben oder Druckwerte. Eine Spule "
            "trägt bis zu vier Farben: Die erste zeigt das Bild, alle kommen bei Bambu "
            "Studio, OrcaSlicer und ElegooSlicer an."
        ),
    ),
    Page(
        key="sketch",
        summary=_("Zeichnen mit Bedingungen: Linien, Bögen, Maße, und was danach daraus wird."),
        title=_("Zeichnen"),
        body=_(
            "Für den Umriss, den kein Grundkörper hergibt, etwa eine Grundplatte "
            "mit einer Aussparung für ein Netzteil.\n\n**Angefangen wird oben in der "
            "Werkzeugleiste.** *Zeichnen* schwenkt die Ansicht senkrecht auf die "
            "Zeichenebene, gezeichnet wird im Modell. Was daraus wird, entscheiden "
            "Sie am Ende. Escape kommt wieder "
            "heraus.\n\n![](figure:sketch-mode)\n\n**Zuerst die Ebene.** *Draufsicht "
            "(XY)* liegt flach wie das Druckbett, *Vorderansicht (XZ)* und "
            "*Seitenansicht (YZ)* stehen, und die ebenen Flächen "
            "vorhandener Körper stehen mit in der Liste. Der Satz daneben sagt, "
            "wie die Druckschichten zur Zeichnung liegen: auf der Draufsicht parallel, auf "
            "den stehenden Ebenen quer, und eine waagerechte Linie wird dort "
            "später eine Fuge. Schneller geht es mit einem Rechtsklick auf eine "
            "Fläche, im Bild oder im Objektbaum: *Auf dieser Fläche zeichnen*. "
            "Unter *Neue Ebene …* entsteht eine Ebene, parallel versetzt, um eine "
            "Achse gekippt oder durch drei Punkte; der Abstand darf ein "
            "Projektparameter sein, und die Ebene wandert mit ihrer "
            "Fläche.\n\n**Werkzeuge und Tasten:** Linie `L`, Rechteck `R`, Kreis "
            "`C`, Bogen `A`, Punkt `P`, Kurve `S`, Vieleck `V`, Langloch `G`, "
            "Trimmen `T`. Vieleck, Langloch, Lochkreis und Lochraster entstehen "
            "aus zwei Klicks: Mitte und Ecke, die Mitten der beiden runden Enden, "
            "Mitte und erstes Loch, zwei gegenüberliegende Löcher. Eckenzahl, "
            "Breite, Anzahl oder Lochdurchmesser stehen daneben in der Leiste. Die "
            "Linie läuft als Zug weiter, eine Kurve endet mit Doppelklick, "
            "Eingabetaste oder einem Klick auf ihren letzten Punkt. `1`, `2` und "
            "`3` wechseln zwischen XY, XZ und YZ; `Esc` bricht ein angefangenes "
            "Element ab und schaltet aufs Auswählen. Alles entsteht als Zeichnung "
            "mit Bedingungen und bleibt bemaßbar.\n\n**Ansehen und ziehen.** Die "
            "Ansicht bedienen Sie wie im Hauptfenster, und *Einpassen* (`Pos1`) "
            "holt alles ins Bild. Mit *Auswählen* verschiebt ein Zug einen Punkt, "
            "und was an ihm hängt, zieht nach. **Strg beim Klicken sammelt**: "
            "*Parallel* und *Rechtwinklig* brauchen zwei Linien, *Symmetrisch* "
            "zwei Punkte und eine Achse, und die Reihenfolge der Klicks zählt. "
            "`Entf` löscht die Auswahl samt ihren Bedingungen, in der "
            "Bedingungsliste nur den Eintrag. `Strg+Z` nimmt hier den letzten Zug "
            "auf dem Blatt zurück, nicht den letzten Schritt im "
            "Verlauf.\n\n**Fangen.** Ein Klick nahe einem vorhandenen Punkt fängt "
            "ihn, und beide bekommen die Bedingung *Verbunden*: Sie bleiben zusammen, auch "
            "wenn später etwas wandert. Wo kein Punkt in der Nähe ist, fängt mit "
            "*Am Raster fangen* das Raster, auf die nächste Linie. Seine Weite "
            "folgt dem Zoom in der Folge 1, 2, 5; eine eingetippte Weite bleibt "
            "stehen, und *Automatisch* lässt sie wieder dem Zoom "
            "folgen.\n\n**Bemaßen beim Zeichnen.** Bei Linie und Kreis erscheint "
            "nach dem ersten Klick ein Maßfeld am Zeiger: Länge oder Durchmesser "
            "tippen, Eingabetaste. Die Richtung kommt vom Zeiger, die Zahl bleibt "
            "als Bedingung stehen. Ø oder R neben dem Feld tauscht Durchmesser "
            "gegen Radius, und zwar in jedem Kreisfeld der Anwendung. Nachträglich "
            "bemaßt `D` zwei gewählte Punkte, auch mit einem Ausdruck: `@breite/2` "
            "bindet das Maß an einen Projektparameter.\n\n**Bedingungen halten die "
            "Zeichnung zusammen.** Etwas auswählen, dann den Knopf drücken oder "
            "die rechte Maustaste am Ort. Dazu gehören: Abstand, Radius, "
            "Durchmesser, Winkel, Verbunden, Waagerecht, Senkrecht, Parallel, "
            "Rechtwinklig, Tangential, Auf Kurve, Krümmungsstetig, Gleich groß, "
            "Mittelpunkt, Konzentrisch, Symmetrisch, Fest und Referenzmaß, das nur "
            "mitmisst. Angeboten wird nur, was zur Auswahl passt, und ein "
            "zweiter Klick auf den gedrückten Knopf nimmt die Bedingung zurück. "
            "Rechts stehen die Bedingungen der gewählten Linie oder des gewählten "
            "Punkts, darüber ihre Gesamtzahl. Zwei, die sich widersprechen, stehen "
            "immer da. Wer einen Eintrag überfährt, sieht die Punkte aufleuchten, "
            "die er hält. Ein Rechtsklick auf einen Punkt "
            "zeigt, was an ihm hängt, und nimmt es einzeln "
            "weg.\n\n![](figure:sketch-editor)\n\n**Unten steht, wie fest die "
            "Zeichnung ist.** *Bestimmt* heißt, nichts wandert mehr. „Noch 4 Maße "
            "fehlen, dann wackelt nichts mehr“ heißt, dass die Skizze noch "
            "verschiebbar ist; sie funktioniert trotzdem. Widersprechen sich zwei "
            "Maße, nennt Solidon sie, und die letzte gültige Lage bleibt "
            "stehen.\n\n**Ändern ohne neu zu zeichnen:** *Trimmen* schneidet die "
            "angeklickte Hälfte weg, *Verlängern* lässt sie wachsen, *Versetzen* "
            "(`O`) legt eine Kontur im Abstand daneben, negativ nach innen, "
            "*Spiegeln* spiegelt die Auswahl an der X- oder Y-Achse. *Hilfslinie* "
            "(`X`) trägt Bedingungen, bildet aber kein Profil, etwa als "
            "Mittellinie. *Projizieren* holt die Kanten vorhandener Körper, die "
            "diese Ebene schneidet, in die Zeichnung, *Flächenkontur* den Rand der "
            "Fläche samt ihren Löchern. Beides kommt fest und als Hilfslinie: So "
            "richten Sie etwas an einem eingelesenen Teil aus, statt abzumessen. "
            "Es ist eine Kopie; ändert sich der Körper, zieht sie nicht "
            "mit.\n\n**Der Rand des Bauraums ist gestrichelt eingezeichnet.** Wer "
            "darüber hinauszeichnet, liest an der Linie: *die Skizze ragt darüber "
            "hinaus*. Bei kleinen Teilen liegt er außerhalb des "
            "Bildes.\n\n![](figure:sketch-uses)\n\n**Zum Schluss sagen Sie, was daraus "
            "wird.** *Hochziehen* und *Abtragen* stehen an der fertigen Kontur. "
            "*Fertig* klappt alle Arten auf, jede mit einem Satz: hochziehen, als "
            "Tasche einschneiden, ein Lochfeld schneiden, um die senkrechte Achse "
            "drehen, entlang eines Bogens führen oder zwischen zwei Umrissen "
            "aufspannen. Was nicht geht, sagt warum. *Verwerfen* verlässt den "
            "Modus, und die Statuszeile nennt den Weg "
            "zurück.\n\n![](figure:sketch-result)\n\n**Die Zeichnung bleibt ein Wert "
            "im Verlauf.** Ein Doppelklick auf den Schritt öffnet die Zeichnung "
            "direkt wieder. Eine verschobene Linie rechnet die Operation neu, der "
            "Rest des Projekts bleibt. Ein gezeichneter Kreis wird ein runder "
            "Zylinder, kein Vieleck.\n\n**Eine vorhandene Zeichnung verwenden.** "
            "Ziehen Sie eine SVG- oder DXF-Datei ins Fenster. Unter *Zeichnung "
            "hochziehen* wählen Sie die Konturen in der Liste oder im "
            "Vorschaubild, *Alle gültigen* markiert alle verwendbaren; Innenringe "
            "bleiben Löcher. Höhe und Breite einstellen, die Vorschau prüfen. "
            "Nicht verwendbare Konturen bleiben mit einer Begründung sichtbar. "
            "Später öffnet der Schritt im Verlauf *Konturen wählen …* erneut, Höhe "
            "und Breite stehen dann im Operationsdialog."
        ),
    ),
    Page(
        key="ways",
        summary=_("Anpassen, konstruieren, erzeugen, formen: vier Wege in dieselbe Szene."),
        title=_("Die vier Wege"),
        body=_(
            "Fast jede Aufgabe geht einen von vier Wegen. Zu jedem liegt auf dem "
            "Startbildschirm ein Beispielprojekt bereit, mit einer Tour, die Schritt für "
            "Schritt zeigt, was Sie ausprobieren können, und selbst merkt, wenn ein "
            "Schritt getan ist.\n\n"
            "![](figure:ways)\n\n"
            "**Weg 1: ein fremdes Modell anpassen.** Heruntergeladen, passt fast: "
            "einlesen, reparieren, bohren, exportieren. Der häufigste Weg; wie er geht, "
            "zeigen [Ein Modell prüfen und drucken](manual:print-a-model) und [Ein Loch "
            "bohren](manual:drill-a-hole).\n\n"
            "**Weg 2: selbst konstruieren.** Aus Grundkörpern, Bausteinen und "
            "Zeichnungen, mit benannten Maßen wie Breite und Stärke; ändert sich eine "
            "Zahl, ändert sich das Teil. Der Anfang steht in [Das erste eigene "
            "Teil](manual:first-part), das Zeichnen in [Zeichnen](manual:sketch).\n\n"
            "**Weg 3: ein Modell aus Text oder Bild erzeugen.** Was zurückkommt, ist eine "
            "Oberfläche und keine Konstruktion. Sie läuft durch die Reparatur, Bohrungen "
            "entstehen danach als eigene Schritte ([Ein Modell erzeugen "
            "lassen](manual:generating)).\n\n"
            "**Weg 4: eine Figur formen.** Für Formen ohne Maß: aus Grundkörpern grob "
            "zusammengesetzt, weich verschmolzen und von Hand geformt. Hier zählt eine "
            "Geste statt einer Zahl ([Formen](manual:sculpting))."
        ),
    ),
    Page(
        key="sculpting",
        summary=_("Formen von Hand, und warum eine ganze Sitzung ein Schritt bleibt."),
        title=_("Formen"),
        body=_(
            "Manche Formen lassen sich nicht bemaßen. Ein Griff, der in der Hand liegen "
            "soll, eine Figur, ein gewachsener Übergang: Dafür gibt es den Pinsel.\n\n"
            "**Drei Stufen, und die zweite wird gern übersprungen.** Erst eine grobe Form "
            "aus Grundkörpern, weich verschmolzen (*Weich verschmelzen* rechts, sobald "
            "die Körper gewählt sind). Dann *Dreiecke angleichen*, damit überall gleich "
            "viele Eckpunkte sitzen. Dann *Formen*. Ohne die zweite Stufe folgt das Netz "
            "dem Pinsel nicht, und die Leiste sagt es.\n\n"
            "**Die ganze Sitzung ist ein Schritt im Verlauf**, nicht jeder Zug, denn eine "
            "Figur hat Tausende. Während der Sitzung nimmt Strg+Z einen Zug zurück, "
            "danach die ganze Sitzung.\n\n"
            "**Sechs Werkzeuge.** *Auftragen* und *Abtragen* sind dasselbe mit "
            "umgekehrtem Vorzeichen. *Glätten*, *Aufblasen* und *Flachziehen* brauchen je "
            "einen Durchgang mehr, die Leiste zeigt wie viele. *Kneifen* zieht zur "
            "Strichmitte und macht Kanten.\n\n"
            "**Innerhalb einer Etappe ist die Reihenfolge egal:** Zwei Züge über dieselbe "
            "Stelle addieren sich auf die Ausgangsfläche. Mit *Neu ansetzen* sitzt der "
            "nächste Zug auf dem, was schon da ist. Greift ein Zug in eine Mulde, die ein "
            "Zug davor gegraben hat, setzt er dort von selbst neu an und gräbt tiefer.\n\n"
            "**Symmetrie lässt sich nachträglich ändern**, auch an einer fertigen "
            "Sitzung. Gespiegelt wird an der Mitte des Körpers, wie er vor den Zügen "
            "dasteht; beim Formen bleibt sie stehen. Ein Zug auf der Spiegelebene wirkt "
            "einmal, nicht doppelt.\n\n"
            "**Der Pinsel greift nur die Seite, die ihm zugewandt ist.** Die Unterseite "
            "einer dünnen Platte oder die Innenwand eines Hohlkörpers bleibt, wo sie "
            "ist.\n\n"
            "**Wann nicht:** an einem Teil, das noch bemaßt wird, denn ein Zug sitzt an "
            "einer Stelle im Raum und verliert seine Fläche, wenn sich die Form darunter "
            "ändert. Für einen Übergang zwischen zwei Körpern ist *Weich verschmelzen* "
            "besser, drei Zahlen statt hundert Züge.\n\n"
            "**Dafür läuft die Wandstärke mit:** Zu dünne Stellen stehen als Zahl in der "
            "Leiste, bevor der Slicer sie findet. Sticht ein Zug durch die Wand oder lässt "
            "er weniger als die Mindestwand stehen, sagt es danach der Prüfbericht und "
            "zeigt die Stelle."
        ),
    ),
    Page(
        key="history",
        summary=_("Warum jeder Schritt änderbar bleibt und was eine Transaktion zusammenhält."),
        title=_("Der Verlauf"),
        body=_(
            "Jede Operation steht im Verlauf und bleibt dort änderbar. Ein Modell ist "
            "hier die Liste der Schritte, aus denen es entstanden ist, nicht bloß ein "
            "Netz aus Dreiecken.\n\n"
            "![](figure:stack)\n\n"
            "**Ein Doppelklick auf einen Schritt** öffnet ihn mit den Werten, die in der "
            "Datei stehen. Wer eine Bohrung versetzen will, ändert die Zahl, und neu "
            "gerechnet wird nur, was darunter hängt. Auch diese Änderung nimmt Strg+Z "
            "zurück. An einem Beispiel zeigt es [Ein Loch bohren](manual:drill-a-hole).\n\n"
            "**„Diesen Schritt ändern“** steht auch am Merkmal, im Kontextmenü der "
            "Ansicht und im Objektbaum: der Weg vom Ergebnis zum Schritt, ohne die Zeile "
            "im Verlauf zu suchen. Was ein Baustein erzeugt hat, fasst der Objektbaum "
            "unter dessen Namen zusammen.\n\n"
            "**Mehrere Schritte wählen** Sie mit Strg oder Umschalt. Genau diese gehen in "
            "einen eigenen Baustein ([Eigene Bausteine](manual:own-parts)); sonst nimmt er "
            "den gewählten Körper mit seinen Schritten, ohne jede Auswahl den ganzen "
            "Verlauf.\n\n"
            "**Löschen** steht im Kontextmenü der Liste und in der Leiste darunter und "
            "lässt sich zurücknehmen. Weil ein gelöschter Schritt die Schritte trifft, "
            "die auf ihm aufbauen, fragt Solidon hier als einzige Stelle im Verlauf nach "
            "und nennt die betroffenen Schritte und den Rückweg über Strg+Z.\n\n"
            "**Rückgängig nimmt eine ganze Transaktion zurück**, nie einen halben "
            "Schritt. Ein Vorschlag des Chats ist genau eine Transaktion.\n\n"
            "**Zwei Grenzen sind Absicht.** Zurückgenommene Schritte fallen weg, sobald "
            "ein neuer kommt; Zweige gibt es nicht. Und eine Änderung, die die Zahl der "
            "Objekte ändert, während spätere Schritte mit ihnen arbeiten, wird abgelehnt, "
            "denn die neuen Körper sind nicht die alten.\n\n"
            "**Anklicken setzt an.** Wer eine Fläche wählt und dann eine Operation "
            "aufruft, findet Ort und Achse eingetragen, die Größe nicht: Eine Senkung "
            "nimmt den Kopf der Schraube, nicht den Durchmesser der Bohrung darunter. An "
            "einer angeklickten Bohrung nennt der Dialog die passende Normgröße und "
            "fragt, wo keine passt, statt eine zu erfinden."
        ),
    ),
    Page(
        key="parameters",
        summary=_("Benannte Maße statt Zahlen im Modell, mit Ausdrücken zwischen ihnen."),
        title=_("Parameter und Ausdrücke"),
        body=_(
            "Ein Projekt hat benannte Parameter wie `breite`, `tiefe` oder `wandstaerke`, "
            "und Operationen rechnen mit ihnen statt mit festen Zahlen.\n\n"
            "**Wozu:** Eine Zahl, die an sieben Stellen steht, ändert man an sechs und "
            "übersieht die siebte. Ein Parameter steht an einer Stelle. Drehen Sie an "
            "`breite`, folgt alles, was davon abhängt: Die Bohrung in der Mitte bleibt in "
            "der Mitte, weil dort `=@breite/2` steht und nicht „35“.\n\n"
            "**Anlegen:** links unter *Parameter* auf *Parameter anlegen*, Name und Wert "
            "eintragen.\n\n"
            "**In ein Maß bringen:** Hat das Projekt Parameter, steht neben jedem "
            "Zahlenfeld der Knopf **fx** und schaltet es auf einen Ausdruck um. Dann "
            "nimmt das Feld `=@breite/2` an: `=` beginnt "
            "einen Ausdruck, `@` verweist auf einen Parameter. Nach `@` schlägt das Feld "
            "die Namen vor, darunter steht, was erlaubt ist.\n\n"
            "![](figure:parameter-field)\n\n"
            "**Name und Beschriftung können verschieden sein.** In der Liste steht "
            "vielleicht *Breite*, im Ausdruck `@breite`. Die Vorschlagsliste setzt den "
            "richtigen ein.\n\n"
            "**Grenzen, Einheit und Ausdruck** ändern Sie mit einem Rechtsklick auf den "
            "Parameter, *Ändern …*, rücknehmbar wie jede Änderung. Liegt eine getippte "
            "Zahl außerhalb der Grenzen, übernimmt Solidon sie nicht und nennt darunter "
            "die Grenze; *Parameter ändern …* führt dorthin.\n\n"
            "**Erlaubt sind** die vier Grundrechenarten, Klammern, `min`, `max`, `abs`, "
            "`round` und Verweise auf andere Parameter, etwa `=@breite/2 - @wand` oder "
            "`=max(@breite, 40)`. Sonst nichts: Solidon rechnet Ausdrücke selbst und "
            "führt nichts aus. Eine Projektdatei wandert zwischen Leuten und darf kein "
            "Programm sein, auch wenn ein Sprachmodell den Ausdruck geschrieben hat.\n\n"
            "**Ringschlüsse** wie `a` auf `b` und `b` auf `a` erkennt Solidon und nennt "
            "sie, statt endlos zu rechnen.\n\n"
            "Gerechnet wird in Millimetern und doppelter Genauigkeit, gerundet nur in der "
            "Anzeige: Was als „40,00 mm“ dasteht, ist intern eine Zahl mit allen Stellen."
        ),
    ),
    Page(
        key="tolerances",
        summary=_(
            "Woher das Spiel kommt, das ein Deckel braucht, und warum es nicht geschätzt wird."
        ),
        title=_("Material, Toleranzen, Passungen"),
        body=_(
            "Das Stück, das Solidon von einem Slicer unterscheidet. Ein gedrucktes "
            "Teil ist nie so groß wie gezeichnet: Kunststoff schwindet, ein Loch "
            "von 5 mm kommt enger heraus, die unterste Schicht wird breiter "
            "gedrückt. Wer zwei Teile ineinanderstecken will, muss das einrechnen, "
            "und das nimmt Solidon ab.\n\n**Das Spiel steht im Materialprofil, nicht "
            "im Modell.** Wer einen Stift in ein Loch stecken will, trägt keine "
            "0,2 ein, sondern wählt eine *Passung*; die Zahl kommt aus dem Profil "
            "des Materials, mit dem gedruckt wird.\n\n![](figure:fit)\n\n**Deshalb "
            "wirkt eine Kalibrierung rückwärts.** Ein Wert unter *Bearbeiten → "
            "Material kalibrieren* gilt für jede Passung, auch in Projekten, die "
            "vorher entstanden sind. Gemessen wird am gedruckten Prüfkörper, wie "
            "in [Ausprobieren statt raten: Varianten und "
            "Kalibrieren](manual:variants) beschrieben.\n\n**Die erste Schicht ist "
            "ein Sonderfall.** Sie wird gegen das Bett gedrückt und läuft nach "
            "außen aus, der Elefantenfuß. Bei einer Passung unten am Teil "
            "entscheidet das, ob es hineingeht.\n\n![](figure:elephant-foot)\n\n**Das "
            "Prüfstück** schneidet einen Würfel um eine Stelle aus dem Teil, statt "
            "sie nachzubauen: die echte Form mit derselben Toleranz, als kleiner "
            "Ausschnitt zum Probedrucken.\n\n**Eine Szene darf mehrere Materialien "
            "haben.** Eine TPU-Dichtung in einem PETG-Gehäuse schwindet anders und "
            "will mehr Spiel. *Material festlegen* gibt einem Körper sein eigenes "
            "Profil, und Toleranzen, Elefantenfuß und Passungsprüfung rechnen "
            "damit."
        ),
    ),
    Page(
        key="parts",
        summary=_("Geprüfte Verbindungen aus der Bibliothek statt selbst konstruierter Geometrie."),
        title=_("Die Bausteine"),
        body=_(
            "Einen Sechskant so tief in eine Wand zu legen, dass eine M4-Mutter passt und "
            "die Schraube trotzdem greift, ist beim ersten Mal eine halbe Stunde Arbeit. "
            "Ein Baustein erledigt es: Fläche oder Bohrung anklicken, Baustein wählen, "
            "Größe wählen. Den Weg im Bild zeigt [Das erste eigene Teil](manual:first-part)."
            "\n\n"
            "**Nach dem Einsetzen steht der Baustein im Bild**, auf der gewählten Fläche, "
            "in der gewählten Bohrung oder oben auf dem Körper, mit Maßlinien zu den Kanten "
            "und einem Griff. "
            "Ziehen oder ein Klick auf eine andere Stelle setzt ihn um, die Maße lassen "
            "sich auch tippen. Erst *Übernehmen* fügt ihn ein, Escape geht zurück zu den "
            "Werten. Ohne gewählten Körper bleibt *Einsetzen* gesperrt und sagt am Knopf, "
            "warum; durchsehen lässt sich der Katalog trotzdem.\n\n"
            "**Was für sich ein Teil ist, entsteht auch ohne Körper.** Kabelclip, "
            "Eckwinkel, Rippe, Standfuß, Wandhalter, Passstift, die beiden Scharniere, "
            "Schraube und Mutter legt *Einsetzen* ohne gewählte Fläche als eigenen Körper "
            "auf die Druckplatte, die Schraube mit dem Kopf nach unten. Mit einer gewählten "
            "Fläche oder Bohrung setzen sie sich dort an. Als eigener Körper gibt es nur die "
            "aufgesetzte Form. Für die Tasche eines Fußes wählen Sie eine Fläche.\n\n"
            "**Die Maße kommen aus einer Tabelle.** Schlüsselweite der M4-Mutter, Sitz "
            "der Einpressbuchse, Breite des Filmscharniers sind nachgeschlagen, nicht "
            "geschätzt.\n\n"
            "**Mutternfalle**: die Tasche für eine Sechskantmutter, die beim Drucken "
            "eingelegt wird. Der häufigste Weg zu einem belastbaren Gewinde.\n\n"
            "![](figure:part-nut-trap)\n\n"
            "**Heat-Set-Einpressbuchse**: die gestufte Bohrung für eine Messingbuchse, "
            "die mit dem Lötkolben eingeschmolzen wird. Aufwendiger, dafür beliebig oft "
            "lösbar.\n\n"
            "![](figure:part-heatset)\n\n"
            "**Rastnase**: ein federnder Arm, der beim Fügen ausweicht und dann "
            "einrastet. Ein Deckel, der ohne Schraube hält.\n\n"
            "![](figure:part-snap-fit)\n\n"
            "**Filmscharnier**: eine Stelle, so dünn, dass sie sich biegt, statt zu "
            "brechen. Das Gelenk wird mitgedruckt.\n\n"
            "![](figure:part-hinge)\n\n"
            "**Lochwand-Einhänger**: ein bis sechs Haken im Raster einer SKÅDIS-Lochwand, "
            "eine Rückplatte auf Wunsch. Von oben in die Schlitze, dann herunterziehen; "
            "eine federnde Rastzunge hält das Teil auch, wenn jemand daran zieht. Wer es "
            "oft abnimmt, schaltet die Zunge ab. Gedruckt wird liegend, damit die Zunge "
            "über ihre Schichten federt.\n\n"
            "![](figure:part-pegboard-hook)\n\n"
            "**Scharnierauge**: eine Lasche mit Bohrung. Zwei davon und ein Passstift "
            "ergeben ein Gelenk, das sich dreht.\n\n"
            "![](figure:part-hinge-eye)\n\n"
            "**Bolzenscharnier**: zwei Laschen um einen mitgedruckten Bolzen, fertig "
            "beweglich von der Platte. Der Spalt dazwischen ist die Passung, *Spiel* "
            "stellt ihn ein.\n\n"
            "**Eckwinkel**: das Dreieck in einer Innenecke, das zwei Wände im rechten "
            "Winkel hält. Für eine einzelne weiche Wand ist die Versteifungsrippe da.\n\n"
            "![](figure:part-gusset)\n\n"
            "**Standfuß**: ein gedruckter Fuß oder die Tasche für einen Gummifuß. Die "
            "Fase zeigt nach unten, damit der Elefantenfuß der ersten Schicht ins Leere "
            "quetscht.\n\n"
            "![](figure:part-foot)\n\n"
            "**Kabelclip**: ein Bügel, dessen Öffnung enger ist als das Kabel. Er führt, "
            "hält aber nicht gegen Zug; dafür gibt es die Durchführung.\n\n"
            "![](figure:part-cable-clip)\n\n"
            "**Druckbares Gewinde**: ein Innengewinde oder ein Gewindebolzen für ein "
            "gedrucktes Gegenstück, nicht für eine Metallschraube. Mit dem Haken bei "
            "Innengewinde schneidet es auf einer Fläche sein Loch selbst. Neben den "
            "M-Größen nimmt es unter *Eigenes Maß* jeden Durchmesser, etwa für ein Rohr. "
            "In eine vorhandene Bohrung setzt es das Gewinde, das passt, siehe [Ein "
            "Gewinde in eine Bohrung](manual:thread-a-hole).\n\n"
            "Dazu kommen Schraubenloch, Magnettasche, Kabeldurchführung, Rippe, "
            "Schlüsselloch, Kugellager einsetzen, Schraube, Gedruckte Mutter, "
            "Nutfeder, Wandhalter, Schnappverbindung, Passstift und Passbohrung, "
            "Schnappverbinder für eine Naht, Lasche mit Loch, Rohrschelle, die Halter in "
            "U-Form, rund, als Gabel und als Ablage und die Prüfkörper aus [Ausprobieren statt "
            "raten: Varianten und Kalibrieren](manual:variants). Der Katalog ordnet sie "
            "in Gruppen, jeden mit Bild.\n\n"
            "![](figure:catalog)\n\n"
            "**Ein Baustein bleibt änderbar** wie jede Operation: Er steht im Verlauf, "
            "und die Stellen, an denen er ansetzt, behalten ihren Namen.\n\n"
            "**Zwei Teile, die zusammengehören, entstehen zusammen.** *Gegenstücke setzen "
            "…* unter *Erzeugen → Bausteine*: an jedem der beiden Teile die Stelle "
            "markieren, das Paar wählen, die Maße einmal eingeben. Solidon setzt beide "
            "Hälften, trägt die Passung ein und legt alles in einen Schritt. Drei Paare "
            "gibt es: Passstift und Passbohrung, gedruckte Schraube und Mutter, "
            "Einpressbuchse und Durchgangsloch. Ist eine der beiden Stellen ein Gewinde, "
            "gibt es nichts zu wählen: Am anderen Teil entsteht das passende Gegengewinde.\n\n"
            "**Einen Organizer aufteilen.** *Erzeugen → Grundformen → Organizer anlegen* "
            "öffnen, Maße eingeben, *Fächer aufteilen …* wählen. *Außenmaße festhalten* "
            "oder *Lichte Fachmaße festhalten* entscheidet, ob die Schublade passen soll "
            "oder der Inhalt. Ein Fach oder eine Trennwand in der Draufsicht oder im Baum "
            "wählen, Fachmaße und Wandhöhen ändern, die Vorschau rechnet mit. *Aufteilung "
            "übernehmen* führt zum Dialog zurück, *Übernehmen* legt das Teil an, und im "
            "Verlauf lässt sich die Aufteilung später wieder öffnen. Wanne, Trennwand, "
            "Rand und Steckfuß gibt es auch einzeln als Bausteine."
        ),
    ),
    Page(
        key="own-parts",
        summary=_("Ein selbst gebautes Teil so ablegen, dass es beim nächsten Mal fertig dasteht."),
        title=_("Eigene Bausteine"),
        body=_(
            "Der Halter für die Werkbank hat einen Abend gekostet. Beim nächsten Mal soll "
            "er ein Eintrag im Katalog sein, mit einstellbarer Breite, weil das nächste "
            "Brett dicker ist.\n\n"
            "**Zuerst Projektparameter.** Einstellbar wird genau, was im Projekt einen "
            "Namen hat. Wer die Breite als feste Zahl in den Quader geschrieben hat, "
            "bekommt einen Baustein mit genau einer Breite. Legen Sie die Werte vorher "
            "als Parameter an und binden Sie die Maße daran ([Parameter und "
            "Ausdrücke](manual:parameters)).\n\n"
            "**Dann den Körper wählen** und im Bausteinkatalog (*Datei → Bausteinkatalog "
            "…*, Strg+K) *Auswahl als Baustein speichern …* drücken. Mit ihm gehen die "
            "Schritte, aus denen er entstanden ist, auch ein Werkzeug, das in ihm aufging. "
            "Andere Körper bleiben im Projekt. Wer genauer schneiden will, wählt die "
            "Schritte im Verlauf mit Strg oder Umschalt, sie gehen dann vor. Ohne jede "
            "Auswahl gilt der ganze Verlauf. Der Knopf bleibt gesperrt, solange Parameter "
            "fehlen, und sagt, was fehlt. Der Dialog nennt oben, was er bekommen hat.\n\n"
            "![](figure:own-part)\n\n"
            "**Der Dialog fragt fünf Dinge:** den Namen im Katalog, die Gruppe, eine "
            "Beschreibung, zu jedem Parameter, ob und wie er einstellbar ist "
            "(Beschriftung, Einheit, Grenzen, Vorgabe und ein Satz, was er bewirkt), und "
            "zu jedem erkannten Merkmal, ob man es später anklicken kann, etwa eine "
            "Bohrung zum Ausrichten. Ohne mindestens ein freigegebenes Maß und eine "
            "freigegebene Stelle bleibt *Baustein anlegen* gesperrt.\n\n"
            "**Beim Anlegen wird gerechnet:** Der Baustein entsteht einmal an jeder Ecke "
            "des angegebenen Bereichs, kleinste Breite mit größter Höhe und so fort. "
            "Kommt auch nur an einer Ecke kein brauchbarer Körper heraus, steht es am "
            "Eintrag im Katalog, bevor Sie ihn einsetzen.\n\n"
            "**Er bleibt auf diesem Rechner** und steht markiert neben den "
            "mitgelieferten; nichts wird hochgeladen. Geben Sie ein Projekt weiter, das "
            "ihn benutzt, reist er als Rezept mit, als Liste von Schritten und Werten, "
            "nicht als Programm. Hat der Empfänger schon einen Baustein dieses Namens, "
            "gewinnt seiner, und der mitgereiste bekommt einen eigenen.\n\n"
            "**Ändern heißt neu speichern** unter demselben Namen; der Knopf heißt dann "
            "*Baustein ersetzen*. Ist das Projekt weg oder kam der Baustein als Datei, "
            "holt *Zum Bearbeiten öffnen …* seine Schritte samt Ihren Angaben zurück in "
            "den Verlauf. Ein eingelesener Baustein bleibt als eingelesen gekennzeichnet.\n\n"
            "**Jedes Rezept hat eine Version**, die sich aus seinem Inhalt ergibt. Nutzt "
            "ein Projekt eine ältere, sagt Solidon es beim Öffnen; die alte Version reist "
            "im Projekt mit, steht als eigener Eintrag im Katalog, und Sie entscheiden, "
            "welche gilt."
        ),
    ),
    Page(
        key="exchange",
        summary=_(
            "Einen eigenen Baustein weitergeben und einen fremden übernehmen, über eine "
            "Datei statt über ein Konto."
        ),
        title=_("Bausteindateien austauschen"),
        body=_(
            "Bausteine wechseln nur als Datei den Besitzer, und auf welchem Weg, "
            "entscheiden Sie. Solidon hat keine öffentliche Bibliothek, lädt nichts hoch "
            "und braucht weder Konto noch Netz. Die Datei endet auf `.solidon-part` und "
            "trägt das Solidon-Symbol.\n\n"
            "**Weitergeben:** Im Bausteinkatalog (*Datei → Bausteinkatalog …*, Strg+K) "
            "einen eigenen Baustein wählen und *Baustein als Datei weitergeben …* "
            "drücken. Die Datei trägt Autor und Lizenz. Mitgelieferte und eingelesene "
            "Bausteine behalten ihre Herkunft; neu speichern macht fremde Arbeit nicht zu "
            "Ihrer.\n\n"
            "**Die Lizenz steht im Klartext:** *Gemeinfrei — jeder darf alles, ohne "
            "Bedingung*, *Namensnennung — mein Name muss dabeistehen* oder "
            "*Namensnennung, und Abwandlungen unter derselben Lizenz*. Die dritte "
            "verlangt, dass andere ihre Verbesserung ebenso weitergeben. Der Name daneben "
            "ist frei gewählt, ein Kürzel genügt.\n\n"
            "**Die Datei trägt Daten, nie ausführbaren Quelltext:** das Rezept aus "
            "Schritten und Werten und, wo nötig, eingebettete Modelldaten. Größe, Aufbau "
            "und Unversehrtheit prüft Solidon beim Weitergeben und beim Übernehmen "
            "gleich.\n\n"
            "**Übernehmen:** Im Katalog *Baustein aus Datei hinzufügen …* wählen. Geht "
            "die Datei durch, steht der Baustein im Katalog, und Sie benutzen ihn wie "
            "jeden anderen. Findet die Prüfung etwas, nennt sie das fehlende Feld, den "
            "unzulässigen Wert oder die unbekannte Operation. Heißt er wie einer Ihrer "
            "eigenen, bleibt Ihrer, und der neue bekommt einen abgeleiteten Namen.\n\n"
            "**Ein eingelesener Baustein bleibt im Katalog**, seine Herkunft sichtbar. "
            "Bei CC BY nennt jede Weitergabe den ursprünglichen Autor, bei CC BY-SA kommt "
            "eine abgeleitete Version außerdem unter dieselbe Lizenz.\n\n"
            "Alles bleibt offline. Weder die Datei noch Autor, Lizenz oder Herkunft "
            "werden an RS Digital übertragen."
        ),
    ),
    Page(
        key="print",
        summary=_("Vom fertigen Modell zur Druckdatei, ohne Solidon zu verlassen."),
        title=_("Drucken"),
        body=_(
            "*Datei → An den Slicer übergeben* (Strg+P) führt vom Modell zur Druckdatei. Rechnen "
            "tut sie der Slicer, bedient wird er von hier, meist ohne dass man ihn sieht. "
            "Schritt für Schritt zeigt es [Ein Modell prüfen und "
            "drucken](manual:print-a-model).\n"
            "\n"
            "**Oben fragt der Dialog in der Folge, in der eins vom anderen abhängt:** Slicer, "
            "Drucker, Düse, Platte, Filamente und Qualität. Den Drucker ändern Sie auch in der "
            "Projektkopfzeile, nur für dieses Projekt; Filamente, Farben und ihre Druckwerte "
            "bleiben. Die Düse wählen Sie aus den Größen, die Ihr Drucker kennt; ihr "
            "Durchmesser entscheidet, welche Maschine der Slicer bei der Übergabe wählt.\n"
            "\n"
            "![](figure:print-settings)\n"
            "\n"
            "**Vorn stehen die Werte, die man an jedem Teil ändert:** Fülldichte und Stützen; "
            "Schichthöhe, Wände, Temperaturen und die Suche liegen unter *Weitere "
            "Einstellungen*. Jedes Feld sagt in einem Satz, was es bewirkt. Was die Geometrie "
            "verlangt, schlägt die Analyse mit Begründung vor, etwa Stützen unter dem "
            "gemessenen Überhang oder eine Mindestzeit je Schicht bei einem spitz zulaufenden "
            "Teil. Wählen Sie unter *Haftung* Brim, Skirt oder Raft, stehen dort nur die Maße "
            "dieser Bettart. Eine Zahl außerhalb ihrer Grenze bleibt im Feld, die Grenze steht "
            "daneben, und *Slicen* wartet, bis sie stimmt.\n"
            "\n"
            "**Woher die Werte kommen:** Bei PrusaSlicer und der Orca-Familie (OrcaSlicer, "
            "Bambu Studio, ElegooSlicer, Creality Print, Anycubic Slicer Next) kommen Drucker, "
            "Prozess und Filament "
            "aus dem Slicer, und Solidon legt nur Ihre Änderungen und übernommene Vorschläge "
            "darauf; fehlt der Orca-Familie ein Profil, sagt die Statuszeile welches. Die "
            "Qualität wählt den Prozess des Herstellers, eine eigene Wahl bleibt. Bei Cura "
            "übernimmt Solidon auf Wunsch den Drucker, den Cura gerade nutzt, mit Düse sowie "
            "Start- und Endcode. Die übrigen Druckgrundlagen kommen bei diesem Weg aus Solidons "
            "Tabellen; Ihre Änderungen und übernommenen Vorschläge ergänzen sie.\n"
            "\n"
            "**Slicen** lässt den Slicer rechnen und liest die Druckdatei zurück: Druckzeit, "
            "Material und Schichten stehen danach im Dialog und im Prüfbericht, mit der "
            "Herkunft G-Code und getrennt von Solidons Schätzung und einer gewogenen Restmenge. "
            "*Druckdatei speichern* legt den G-Code ab, bei mehreren Platten eine Datei je "
            "Platte.\n"
            "\n"
            "**Im Slicer öffnen** gibt die Platte als Datei an das Fenster des Slicers, für den "
            "letzten Handgriff dort oder wenn ein Slicer von außen nicht annimmt, was sein "
            "Fenster kann. Profile braucht dieser Weg nicht. Die Orca-Familie bekommt mehrere "
            "Platten in einer Datei, geordnet wie ihre eigenen, PrusaSlicer und Cura eine Datei "
            "je Platte. Den zuletzt benutzten Weg trägt beim nächsten Öffnen der Hauptknopf.\n"
            "\n"
            "**Scheitert ein Lauf**, nennt die Absage den Grund und bietet an, was hilft: einen "
            "anderen Slicer, die Ausgabe des Slicers ansehen, das Maschinenprofil prüfen oder "
            "nur exportieren. Die Druckdatei wird nachgemessen: Fährt sie über den Bauraum "
            "hinaus oder ist sie niedriger als das Modell, steht das als Fehler im Prüfbericht.\n"
            "\n"
            "**Nach dem Druck** bucht *Filament abziehen …* den Verbrauch von den Spulen ab. "
            "Solidon-Schätzungen und G-Code-Mengen sind gekennzeichnet, fehlende bleiben "
            "unbekannt, bis Sie sie eintragen oder slicen, und eine spätere G-Code-Angabe "
            "berichtigt die Buchung. *Noch einmal gedruckt* bucht einen weiteren Druck. Im "
            "Filamentlager zeigt der *Buchungsverlauf* jeder Spule jede Buchung; *Gewählten "
            "Vorgang zurücknehmen* nimmt einen Druck zurück und auch wieder vor. Unter "
            "*Lager-Einstellungen* steht, was nach der Übergabe an den Slicer geschieht: "
            "*Nachfragen* (die Vorgabe), *Nie buchen* oder *Ohne Rückfrage buchen*."
        ),
    ),
    Page(
        key="resin",
        summary=_("Was an einem Resin-Drucker anders ist, und was Solidon dort weglässt."),
        title=_("Harz statt Filament: Resin-Drucker"),
        body=_(
            "Ein Resin-Drucker belichtet Schichten in einem Harzbad; Düse, Bahn und "
            "Elefantenfuß gibt es dort nicht. Beim ersten Start stehen zwei Resin-Drucker "
            "in derselben Liste wie die Filamentdrucker, ein kleiner wie Mars oder Photon "
            "Mono und ein großer wie Saturn oder Photon M. Ein eigener lässt sich mit "
            "Bauraum, Pixelgröße und Mindestwand anlegen.\n\n"
            "**Was dann anders gilt:** Die Mindestwand kommt aus dem Druckerprofil, das "
            "kleinste Detail ist der Bildpunkt. Der Prüfbericht schweigt über Brücken, "
            "Brim, Filamentwechsel und Düsentemperaturen, und der Druckdialog zeigt nur "
            "Drucker, Material, Platten und das Programm.\n\n"
            "**Der Weg zum Drucker ist die Datei**, denn viele Resin-Drucker arbeiten nur "
            "mit dem Slicer ihres Herstellers. *Im Slicer öffnen* gibt die Datei an jedes "
            "Programm, *Exportieren* legt sie ab. Wo Solidon die Form genau kennt, löst "
            "es sie so fein auf, wie die Bildpunkte verlangen, und der Prüfbericht nennt "
            "das Maß."
        ),
    ),
    Page(
        key="export",
        summary=_("Anordnen, prüfen, exportieren, und was jedes Format mitnimmt."),
        title=_("Auf das Bett und hinaus"),
        body=_(
            "**Auf dem Bett anordnen** legt die Objekte nebeneinander, jedes auf "
            "die erste Platte, auf der es Platz hat; erst wenn keine reicht, "
            "beginnt eine neue. Was nicht passt, wird gemeldet, nicht weggelassen. "
            "Besteht ein Körper aus losen Teilen, etwa ein Schriftzug, bietet der "
            "Prüfbericht an, ihn in Einzelteile aufzuteilen und auszurichten: "
            "ein Klick, und die "
            "Buchstaben liegen auf den Platten.\n\n**Zu groß für das Bett?** Dann "
            "wird geteilt, siehe [Wenn das Teil nicht auf das Bett "
            "passt](manual:splitting).\n\n**Was schräg nach außen wächst, braucht "
            "irgendwann Stützen.** Ab welchem Winkel Stützen nötig sind, hängt am "
            "Drucker; der Überhangfächer misst es "
            "aus.\n\n![](figure:overhang)\n\n**Dünne Wände brauchen eine Prüfung.** "
            "Beim Filamentdruck verwendet Solidon zwei Bahnen als Richtwert. Ob "
            "eine dünnere Wand gelingt und hält, hängt von Drucker, Material und "
            "Belastung ab. Auch um eine Bohrung: Bleibt dort weniger Material, als "
            "das Filament trägt, steht es im Prüfbericht, gemessen am fertigen "
            "Teil.\n\n![](figure:wall)\n\n**Exportiert wird nach STL, 3MF oder STEP**, "
            "dazu OBJ und PLY. 3MF bevorzugen die Slicer, und es trägt die "
            "Filamente als Farbgruppen; STL kennt keine Farbe. STEP bewahrt "
            "Flächen und Kanten für andere Konstruktionsprogramme.\n\n**Vor dem "
            "Schreiben zeigt der Export, was der Prüfbericht gefunden hat**, etwa "
            "eine dünne Wand. *Trotzdem exportieren* ist die Vorgabe, denn ein "
            "Bericht ist keine Sperre.\n\n**Ordner, Format und Namensschema merkt "
            "sich Solidon je Projekt.** Entstehen mehrere Dateien, steht im "
            "Namensfeld des Dateidialogs ein Muster mit Platzhaltern in "
            "geschweiften Klammern; ein Name ohne Klammern bleibt ein Name.\n\n**Zum "
            "Herzeigen gibt es GLB**, nicht zum Drucken: Farben und Name reisen "
            "mit, das Teil kommt maßstabsgetreu an, und der Empfänger dreht es im "
            "Browser.\n\n**Die Druckdatei schreibt der Slicer**, bedient wird er von "
            "hier ([Drucken](manual:print)). Solidons Schichtanalyse sucht Inseln, "
            "Spannweiten, dünne Stellen und die beste Lage; wo beide Zahlen "
            "nennen, steht dabei, welche woher kommt."
        ),
    ),
    Page(
        key="splitting",
        summary=_("Teilen, verstiften und anordnen, wenn der Bauraum nicht reicht."),
        title=_("Wenn das Teil nicht auf das Bett passt"),
        body=_(
            "Ist das Teil zu groß für den Bauraum, wird geteilt, und die Hälften müssen "
            "wieder zusammenkommen.\n\n"
            "**Der kürzeste Weg** ist das Werkzeug *Teilen* in der Werkzeugzeile "
            "(Alt+7). Zwei Klicks auf das Teil ziehen eine Linie, geteilt wird dort, "
            "gerade in den Bildschirm hinein. *Zum Zusammenstecken vorbereiten* ist von "
            "Anfang an angehakt: Stifte in die eine Hälfte, passende Löcher in die "
            "andere. Daneben wählen Sie, womit sie halten:\n\n"
            "* **Rund** druckt am saubersten, braucht aber zwei Stück, sonst verdrehen "
            "sich die Hälften.\n"
            "* **Sechskant** hält schon einzeln gegen Verdrehen.\n"
            "* **Schwalbenschwanz** hält auch gegen Auseinanderziehen quer zur Naht, weil "
            "er hinten schmaler ist als vorn.\n"
            "* **Schnapper** rastet ein, mit einem Federarm in der einen Hälfte und einer "
            "Tasche mit Rastkante in der anderen. Er hält ohne Kleber und lässt sich "
            "wieder lösen, braucht aber eine Naht von mindestens 5,4 mm; ist sie "
            "schmaler, werden es runde Stifte, und der Prüfbericht sagt warum.\n\n"
            "**Automatisch teilen …** rechts am gewählten Körper sucht auch die Stelle, "
            "über dieselbe Schichtanalyse wie die Suche nach der besten Lage. Am schwersten "
            "wiegt, dass die Naht aus einer Kontur besteht statt aus mehreren dünnen Stegen. "
            "Danach zählen ein gleichbleibender Querschnitt, der sich sauberer klebt als eine "
            "Schräge, eine freie dünnste Stelle, ähnlich große Hälften und zuletzt, "
            "welche Stücke weniger Stützen brauchen.\n\n"
            "**Braucht ein Teil mehrere Schnitte, plant die Suche die ganze Folge**, nach "
            "der Zahl der Stücke und Klebestellen am Ende. Ein spiegelgleiches Teil wird "
            "in der Symmetrieebene geteilt, beide Seiten drucken dann mit denselben "
            "Einstellungen. Lose Stücke werden an der Lücke getrennt, ohne Naht und "
            "Stift.\n\n"
            "![](figure:split)\n\n"
            "**In jede Schnittfläche kommen zwei Passstifte**, damit sich nichts "
            "verdreht. Der Durchmesser kommt aus der Fläche, das Spiel aus dem "
            "kalibrierten Materialprofil, und jeder Stift ist eine Passung, die bei jeder "
            "Auswertung geprüft wird.\n\n"
            "**Jeder Schnitt ist eine eigene Operation**: Die Ebene bleibt eine Zahl, die "
            "sich verschieben lässt, und Strg+Z nimmt einen Schnitt zurück, nicht die "
            "ganze Teilung. Wer die Ebene eintippen will, nimmt *An Ebene teilen* rechts am "
            "gewählten Körper, mit Achse und Position; null Stifte heißt dort nur "
            "schneiden.\n\n"
            "**Die Stücke heißen, was sie sind:** „… A · Stifte“ und „… B · Löcher“. "
            "Macht *Automatisch teilen* drei oder mehr Stücke, zählt es sie: „… 1 von "
            "3 · Stifte“, „… 2 von 3 · Stifte und Löcher“, „… 3 von 3 · Löcher“. Beim "
            "Export sagt der Dateiname, welches Teil man in der Hand hat."
        ),
    ),
    Page(
        key="variants",
        summary=_(
            "Spiel und Grenzen des eigenen Druckers messen, und mehrere Maße nebeneinander drucken."
        ),
        title=_("Ausprobieren statt raten: Varianten und Kalibrieren"),
        body=_(
            "Die Zahl, die über eine Passung entscheidet, ist das Spiel, und sie hängt an "
            "Drucker, Material und Düse. Geraten wird sie einmal, danach gemessen.\n\n"
            "**Gemessen wird am gedruckten Prüfkörper.** Im Bausteinkatalog (*Datei → "
            "Bausteinkatalog …*, `Strg+K`) steht unter *Kalibrierung* der "
            "*Toleranz-Testkörper*: Zapfen und Bohrungen mit gestuftem Spiel, vorgegeben "
            "vier Stufen von 0,10 bis 0,25 mm, im Dialog änderbar. Einmal drucken, "
            "durchprobieren und den Wert nehmen, der saugend passt.\n\n"
            "![](figure:part-fit-ladder)\n\n"
            "**Der Wert gehört ins Materialprofil:** *Bearbeiten → Material kalibrieren*. "
            "Jede Toleranz ist ein Verweis dorthin, also passt danach auch der Deckel von "
            "letzter Woche besser, ohne dass ihn jemand anfasst.\n\n"
            "**Dasselbe für Wände und Überhänge:** *Wandstärkenleiter* und "
            "*Überhangfächer* messen die dünnste Wand, die hält, und den Winkel, ab dem "
            "dieser Drucker Stützen braucht. Bis dahin gilt der Winkel aus dem Profil "
            "seines Herstellers, bei einem allgemeinen Drucker 45 Grad.\n\n"
            "**Hängt eine Zahl am Teil statt am Material**, hilft *Bearbeiten → Varianten "
            "erzeugen*. Es dreht einen Projektparameter durch einen Bereich und legt die "
            "Ausführungen nebeneinander, etwa fünf Griffdurchmesser auf einer Platte. Das "
            "Projekt bleibt unverändert, die Varianten sind nur eine Ausgabe."
        ),
    ),
    Page(
        key="chat",
        summary=_("Wie man mit dem Chat spricht, was er sieht und was aus einem Vorschlag wird."),
        title=_("Der Chat"),
        body=_(
            "Der Chat ruft dieselben Operationen auf wie das Fenster. Er wählt "
            "Operationen und Werte, rechnen tut das Programm.\n\n"
            "**Der Ablauf:** Sie schreiben, was Sie wollen, und bekommen einen Vorschlag, "
            "eine Liste von Operationen, noch nicht ausgeführt. Die Ansicht zeigt in "
            "Blau, was dazukäme, und in Orange, was verschwände. *Übernehmen* trägt ihn "
            "als eine Transaktion in den Verlauf ein, ein Strg+Z nimmt ihn ganz zurück, "
            "*Verwerfen* lässt nichts zurück.\n\n"
            "**Er sieht einen Steckbrief:** Maße, erkannte Merkmale, Projektparameter, "
            "Auswahl und Prüfbericht. Nach einem Strg+Z gilt sein Beitrag als verworfen.\n\n"
            "**Er braucht ein Sprachmodell**, einen eigenen Schlüssel (*Bearbeiten → Chat "
            "einrichten*, abgelegt im Schlüsselbund des Systems, nie in der Projektdatei) "
            "oder ein lokales Ollama ([Zusätzliche Programme einrichten](manual:extras)). "
            "Ohne Modell ist nur der Chat ausgegraut und sagt warum."
        ),
    ),
    Page(
        key="generating",
        summary=_("Aus Text oder Bild ein Netz, und was danach nötig ist, damit es druckbar wird."),
        title=_("Ein Modell erzeugen lassen"),
        body=_(
            "Sie beschreiben ein Teil oder geben ein Bild, und ein Generator macht "
            "daraus ein Netz: **Datei → Modell erzeugen.**\n\nGerechnet wird in "
            "einem lokalen **ComfyUI** auf Port 8188; läuft keines, bleibt der "
            "Eintrag ausgegraut und sagt warum. Die Einrichtung steht in "
            "[Zusätzliche Programme einrichten](manual:extras).\n\n**Was "
            "zurückkommt, ist eine Oberfläche, keine Konstruktion**, ohne "
            "Bohrungen und Passungen und oft nicht geschlossen. Bohrungen und "
            "Passungen entstehen danach als eigene Schritte.\n\n**Die Modelle und "
            "ihre Lizenzen.** Den Körper macht TRELLIS.2 von Microsoft (MIT-Lizenz). "
            "Es liest das Bild mit DINOv3 von Meta, das unter Metas DINOv3-Lizenz "
            "steht: weltweit und gewerblich nutzbar, mit Nutzungsbedingungen, unter "
            "anderem nicht für Waffen. Freigestellt wird mit BiRefNet (MIT). Für den "
            "Weg aus Text malt FLUX.2 [klein] 4B von Black Forest Labs vorher ein Bild "
            "(Apache-2.0). Solidon liefert keines davon mit, die Einrichtung lädt sie "
            "in Ihr ComfyUI.\n\n**Das "
            "Erzeugte liegt im Projekt wie eine hineingezogene Datei**, denn "
            "dieselbe Anfrage liefert nach einem Modellwechsel etwas anderes. "
            "Darüber stehen gewöhnliche Schritte wie *Reparieren*. Anfrage und "
            "Startwert bleiben dabei; derselbe Startwert liefert dasselbe "
            "Ergebnis, soweit das Modell es zulässt.\n\n**Die Reparaturkette läuft "
            "ohne Nachfrage**: Löcher schließen, doppelte Punkte zusammenführen, "
            "Außenseiten angleichen, Hüllen im Inneren entfernen, damit der Körper "
            "innen voll ist. Laden, Größe, Reparatur und Aufsetzen bilden "
            "einen Schritt: Ein Strg+Z nimmt das ganze erzeugte Modell zurück, im "
            "Verlauf bleibt jeder Teil einzeln änderbar."
        ),
    ),
    Page(
        key="extras",
        summary=_(
            "Die drei Programme, die Solidon nutzen kann: was jedes bringt und was nach "
            "dem Installieren noch zu tun ist."
        ),
        title=_("Zusätzliche Programme einrichten"),
        body=_(
            "**Keines davon ist Pflicht.** Einlesen, ändern, prüfen und exportieren gehen ohne "
            "alle drei.\n"
            "\n"
            "Die Liste steht unter **Hilfe → Zusätzliche Programme**, je Zeile Zweck, Zustand "
            "und Ort. Wo Solidon selbst installieren kann, steht ein Knopf, und erst sein Klick "
            "installiert: unter Windows über winget, unter macOS über Homebrew, unter Linux "
            "über Flatpak im Benutzerkonto. Ob zusätzliche Rechte nötig sind, hängt vom Paket "
            "und Installationsweg ab. Sonst stehen der Befehl zum Kopieren und die Seite des "
            "Herstellers daneben. Für ein Programm an ungewöhnlicher Stelle, etwa portabel auf "
            "einem zweiten Laufwerk, gibt es *Ort angeben …*, und diese Angabe gilt danach "
            "immer.\n"
            "\n"
            "## Der Slicer\n"
            "\n"
            "Für die Druckdatei und die Gegenprobe aus dem G-Code. Erkannt werden PrusaSlicer, "
            "SuperSlicer, OrcaSlicer, ElegooSlicer, Bambu Studio, Creality Print, Anycubic "
            "Slicer Next und Cura. Beim ersten Start schlägt Solidon den Drucker vor, den der "
            "Slicer zuletzt hatte.\n"
            "\n"
            "## Ollama für den Chat ohne eigenen Schlüssel\n"
            "\n"
            "Ollama bringt kein Modell mit und läuft nicht unbedingt. Beides erledigt "
            "*Bearbeiten → Chat einrichten*:\n"
            "\n"
            "1. **Läuft es?** Der Dialog sagt es, und ein Knopf startet es. Läuft es auf einem "
            "anderen Rechner, gehört seine Adresse in die Liste der zusätzlichen Programme.\n"
            "2. **Ein Modell holen.** Die Auswahl nennt die installierten und die bewährten. "
            "*Modell holen* lädt {least} bis {most} GB; ein abgebrochener Download setzt "
            "später fort.\n"
            "3. **Werkzeuge prüfen.** Ob ein Modell Werkzeuge wirklich aufruft, zeigt nur eine "
            "Probe mit einem echten Zug. Antwortet der Chat, führt aber nichts aus, hilft ein "
            "anderes Modell.\n"
            "\n"
            "**Die Probe misst auch die Geschwindigkeit** und sagt, wie lange es bis zum Beginn "
            "einer Antwort dauert. Ohne Grafikkarte rechnet Ollama auf dem Prozessor, um "
            "Größenordnungen langsamer; steht dort eine Wartezeit von Minuten, lohnt der lokale "
            "Weg auf diesem Rechner nicht. Nach zehn Minuten bricht Solidon eine lokale Anfrage "
            "ab.\n"
            "\n"
            "**Passt das Modell ganz in den Grafikspeicher, antwortet es meist schneller.** Die "
            "Parameterzahl allein belegt keine zuverlässigen Werkzeugaufrufe; prüfen Sie das "
            "Modell mit der Werkzeugprobe. Welche Modelle sich bewährt haben, steht in [Welche "
            "Modelle Solidon benutzt](manual:models). Für lange Züge lohnt ein Schlüssel für "
            "ein gehostetes Modell. AMD-Karten unterstützt Ollama selbst über **ROCm**; "
            "**IPEX-LLM** und **OpenVINO** sind eigene Installationen, die Solidon nicht "
            "einrichtet; ob ein solcher Weg trägt, zeigt die Werkzeugprobe.\n"
            "\n"
            "## ComfyUI für das Erzeugen aus Text oder Bild\n"
            "\n"
            "Die Knoten für diesen Weg bringt ComfyUI ab Version 0.35 selbst mit, die Modelle "
            "lädt Solidon dazu: über *Modelle einrichten …* in der Zeile von ComfyUI oder "
            "direkt aus *Datei → Modell erzeugen*, wenn dort ein Modell fehlt. Die "
            "**Desktop-Version** von comfy.org findet Solidon selbst, für die tragbare geben "
            "Sie notfalls den Ordner mit `custom_nodes` und `main.py` an.\n"
            "\n"
            "Die Einrichtung **prüft zuerst die Version von ComfyUI**; ist sie zu alt, sagt "
            "sie es, bevor etwas geladen wird. Auf Wunsch folgen das Modell für den Weg aus "
            "Bild mit rund {shape} GB und für den Weg aus Text das Bildmodell mit rund "
            "{image} GB, jede Datei in einem festen Stand und mit Prüfsumme. Ein abgebrochener "
            "Lauf setzt fort, wo er stand. **Danach ComfyUI einmal neu starten.** Während "
            "einer Erzeugung zeigt Solidon die verstrichene Zeit; bricht etwas ab, steht der "
            "Satz von ComfyUI im Dialog."
        ),
    ),
    Page(
        key="surfaces",
        summary=_("Muster als echte Geometrie, Gitterfüllungen und ausgehöhlte Körper."),
        title=_("Oberflächen und Füllungen"),
        body=_(
            "Ein Rändel für den Griff, eine Wabe fürs Aussehen, ein Gitter statt vollen "
            "Materials: Das ist echte Geometrie, keine Textur im Bild. Der Slicer "
            "bekommt, was Sie sehen.\n\n"
            "**Acht Muster:** Rippe, Welle, Rändel gerade und gekreuzt, Wabe, Noppen, "
            "Voronoi und Rauschen. Rändel gibt Griff, Wabe und Rippe sind Zierde, Voronoi "
            "und Rauschen verstecken die Schichtlinien. Die Vorschau im Dialog ist aus "
            "denselben Umrissen gezeichnet, die gedruckt werden.\n\n"
            "![](figure:textures)\n\n"
            "**Textur aufbringen** prägt ein Muster erhaben oder vertieft auf eine "
            "Fläche, auf einem runden Teil umlaufend. Die Teilung muss breiter sein als "
            "zwei Bahnen der Düse, die Tiefe höher als eine Schicht; beides prüft Solidon "
            "vorher, denn eine zu feine Prägung verschwindet im Druck.\n\n"
            "![](figure:texture)\n\n"
            "**Ein Muster ändern:** auf die texturierte Stelle klicken, rechts *Textur "
            "ändern*. Muster, Teilung, Tiefe und Drehung stehen dort, je nach Aufbringung "
            "auch Breite und Höhe. *Übernehmen* ändert den vorhandenen Schritt; passen "
            "mehrere, wählen Sie zuerst den gemeinten. Strg+Z stellt die alten Werte her.\n\n"
            "**Gitter füllen** ersetzt das Innere eines Körpers durch Gyroid, Wabe oder "
            "Würfelgitter. Anders als die Füllung des Slicers gehört es zum Modell, reist "
            "mit der Datei und lässt sich messen; seine Wandstärke wird gegen die Düse "
            "geprüft.\n\n"
            "Dafür muss der Innenraum bekannt sein. Bei einem selbst ausgehöhlten Körper "
            "ist er es. Bei einem eingelesenen hohlen Teil schließt Solidon die "
            "durchgehenden Bohrungen der Entlüftung probeweise, und was dann "
            "eingeschlossen ist, gilt als Innenraum; die Meldung sagt es. Sonst hilft "
            "nur, den Körper vorher auszuhöhlen."
        ),
    ),
    Page(
        key="labels",
        summary=_(
            "Text auf ein Teil oder als eigener Schriftzug: welche Schrift trägt, und was "
            "die Düse daraus macht."
        ),
        title=_("Beschriften"),
        body=_(
            "Ein Name auf dem Deckel, eine Größe auf der Schublade, ein Schild für die "
            "Werkbank. Beide Wege stehen im Menü *Erzeugen*: *Text aufbringen* setzt die "
            "Schrift erhaben oder vertieft auf eine Fläche des gewählten Körpers, "
            "*Schriftzug als Körper* legt sie als eigenes Objekt an, zum Aufkleben oder "
            "für den Zweifarbendruck. Eine angeklickte Fläche trägt Ort und Richtung "
            "selbst ein. Mit *Auf beiden Seiten* steht dieselbe Schrift auch gegenüber, "
            "wo die Richtung den Körper wieder verlässt, von außen lesbar, etwa auf einer "
            "Fahne.\n\n"
            "**Acht Schriften reisen mit dem Programm**, damit ein Projekt überall gleich "
            "aussieht: je eine serifenlose, eine mit Serifen und eine mit festen "
            "Zeichenbreiten in zwei Familien, dazu eine runde und eine geschriebene. Die "
            "sechs geraden gibt es normal, fett, kursiv und fett kursiv, unter *Weitere "
            "Einstellungen*; die runde und die geschriebene nur normal. Fett bleibt "
            "lesbar, wo der normale Schnitt schon verschmiert.\n\n"
            "**Ob eine Schrift trägt, entscheidet die Düse.** Solidon misst die "
            "Strichbreite des Textes gegen die schmalste Bahn Ihres Druckers und sagt, ab "
            "welcher Höhe sie trägt. Gesperrt wird nichts; ein Schild zum Ansehen darf "
            "klein sein.\n\n"
            "**Die Buchstaben stehen im Objektbaum wie andere Merkmale**, gerade Seiten "
            "als Flächen, gerundete als *Gerundete Seite*. Beide nehmen ein eigenes "
            "Filament an: anklicken, rechts *Filament auf eine Fläche*. Ein Schriftzug "
            "behält sein Filament auch, wenn er für das Bett in Buchstaben aufgeteilt wird.\n\n"
            "**Die Schrift bleibt änderbar.** Ein Doppelklick auf den Schritt im Verlauf "
            "öffnet Text, Größe, Schrift und Tiefe wieder; ein Tippfehler wird "
            "berichtigt, nicht neu gesetzt."
        ),
    ),
    Page(
        key="remote",
        summary=_("Ein anderes Programm bedient Solidon, lokal, abschaltbar und rücknehmbar."),
        title=_("Fernsteuerung"),
        body=_(
            "Ein anderes Programm auf demselben Rechner darf Solidon bedienen, etwa ein "
            "KI-Assistent wie Claude Code; die Verbindung heißt MCP.\n\n"
            "**Sie ist aus, bis Sie sie einschalten**, in den Einstellungen, zusammen mit "
            "dem Port. Solidon hört dann nur auf `127.0.0.1` und ist von keinem anderen "
            "Rechner erreichbar. In der Gegenstelle wird `http://127.0.0.1:8787/mcp` als "
            "Server eingetragen.\n\n"
            "**Was hereinkommt, ist eine Transaktion wie jede andere:** Der Verlauf zeigt "
            "sie mit dem Vermerk, dass sie von außen kam, und Strg+Z nimmt sie zurück. "
            "Nichts, was wie ein Dateipfad aussieht, geht durch die Leitung, denn ein "
            "fremdes Programm soll nicht bestimmen, was hier gelesen wird."
        ),
    ),
    Page(
        key="activation",
        summary=_("Lizenzschlüssel, Geräteaktivierung und der Weg ohne Internet."),
        title=_("Freischaltung"),
        body=_(
            "**Diese Version ist eine vollständige, befristete Demo.** Bis einschließlich "
            "30. Oktober 2026 ist Solidon ohne Lizenzschlüssel vollständig "
            "freigeschaltet, und die Statuszeile zählt die Tage. Danach startet diese "
            "Demo nicht mehr; Ihre Projekte bleiben erhalten.\n\n"
            "**Die spätere Verkaufsversion hat zunächst keine Testphase.** Ohne "
            "Freischaltung bleibt dort alles Lesende offen, Modelle öffnen, ansehen, "
            "vermessen. Freischaltung brauchen Änderungen am Modell, der Export, die "
            "Übergabe an den Slicer und der Chat.\n\n"
            "**Ein Schlüssel wird eingetragen, kein Konto angelegt:** *Hilfe → Solidon "
            "freischalten …*. Danach wird dieser Rechner einmal aktiviert, mit *Online "
            "aktivieren* oder über ein zweites Gerät, und bleibt ohne regelmäßige Abfrage "
            "nutzbar. Geräteschlüssel, Kaufcode und Zertifikat liegen im System und im "
            "Einstellungsordner, nie in einer Projektdatei.\n\n"
            "**Ohne Internet in drei Schritten:** *Offline aktivieren …* öffnen und die "
            "Anfrage speichern, die Datei auf einem Gerät mit Internet unter "
            "`solidon3d.de/offline-aktivierung.html` einlösen, die Antwort in Solidon "
            "einlesen. Sie gilt nur für den Rechner, der die Anfrage erzeugt hat.\n\n"
            "**Wie viele Rechner?** Mit einer privaten Lizenz einer, mit einer "
            "gewerblichen zwei. Die Art steht unter *Hilfe → Über Solidon*.\n\n"
            "**Beim Rechnerwechsel zuerst: Diesen Rechner deaktivieren.** Das gibt den "
            "Platz frei und entfernt Freischaltung und Kaufcode. Ist der alte Rechner "
            "verloren oder defekt, setzt der Support den Platz anhand der Bestellnummer "
            "zurück."
        ),
    ),
    Page(
        key="trouble",
        summary=_("Die häufigsten Fälle am Anfang, mit dem, was dahintersteckt."),
        title=_("Wenn etwas nicht geht"),
        body=_(
            "**Die Datei lässt sich nicht öffnen.**\n"
            "Solidon sagt, was mit ihr nicht stimmt: leer, abgeschnitten, trotz der "
            "Endung keine STL und kein 3MF, null Dreiecke oder keine Ausdehnung. Meist "
            "war der Download abgebrochen, oder es kam die Fehlerseite eines Servers "
            "statt des Modells; bei null Dreiecken war beim Exportieren nichts "
            "ausgewählt. *Andere Datei wählen* führt gleich in die Dateiauswahl.\n\n"
            "**Das Modell ist offen.**\n"
            "Was sicher geht, repariert Solidon schon beim Einlesen, und der Prüfbericht "
            "nennt es, etwa „Ein Loch wurde geschlossen.“ Eine große Öffnung bekommt eine "
            "neue Fläche, darunter stehen *Stelle zeigen* und *Offen lassen*. Bleibt "
            "etwas offen, steht dort zum Beispiel „Eine offene Stelle ließ sich nicht "
            "sicher schließen.“, und *Stellen zeigen* führt hin. Fehlt eine ganze Wand, "
            "ist eine andere Quelle der kürzere Weg.\n\n"
            "**Vereinigen oder Abziehen scheitert oder nimmt zu viel weg.**\n"
            "Beides braucht saubere Körper. Solidon versucht mehrere Verfahren und sagt, "
            "welches getragen hat; wurde auf einem Raster gerechnet, ging Genauigkeit "
            "verloren. Dann erst reparieren und noch einmal. Meldet der Prüfbericht "
            "„Teile des Modells überschneiden sich.“, hilft der Knopf *Überschneidungen "
            "auflösen*. Liegen zwei Flächen genau aufeinander, lassen Sie den "
            "abzuziehenden Körper einen Hundertstelmillimeter überstehen; Bausteine tun "
            "das von sich aus.\n\n"
            "**Das Teil passt nicht auf das Bett.**\n"
            "*Automatisch teilen* schneidet es in passende Stücke ([Wenn das Teil nicht "
            "auf das Bett passt](manual:splitting)). Prüfen Sie auch den Bauraum im "
            "Druckerprofil.\n\n"
            "**Die Passung sitzt zu stramm oder zu locker.**\n"
            "Nicht am Modell ändern, sondern messen und unter *Material kalibrieren* "
            "eintragen ([Ausprobieren statt raten: Varianten und "
            "Kalibrieren](manual:variants)).\n\n"
            "**Ein Schritt lässt sich nicht mehr ändern.**\n"
            "Würde die Änderung die Zahl der Objekte ändern, mit denen spätere Schritte "
            "arbeiten, hält die Auswertung an. Nehmen Sie die späteren Schritte zurück, "
            "ändern Sie, und bauen Sie neu auf.\n\n"
            "**STEP ist ausgegraut.**\n"
            "STEP braucht einzeln bearbeitbare Flächen und Kanten. Wählen Sie für ein "
            "Dreiecksnetz *In Flächen und Kanten umwandeln*. Prüfen Sie danach die "
            "Form und den Prüfbericht: Die Umwandlung stellt nicht automatisch die "
            "ursprüngliche CAD-Konstruktion wieder her. Einen vorhandenen "
            "Grundkörperschritt können Sie auch über sein Kontextmenü im Verlauf "
            "auf *Mit echten Flächen und Kanten rechnen* stellen. Verrunden und "
            "Fase gehen auch am Netz.\n\n"
            "**Die Handlungen rechts sind gesperrt.**\n"
            "Hält die Kette an einem Schritt an, etwa weil ein Teil auf kein Bett passt, "
            "nimmt Solidon keinen neuen dahinter an, denn er würde nie gerechnet. Der "
            "Grund steht an jedem Knopf, der Ausweg im Prüfbericht.\n\n"
            "**Der Chat antwortet nicht.**\n"
            "Er braucht einen eigenen Schlüssel oder ein lokales Ollama ([Der "
            "Chat](manual:chat)).\n\n"
            "**Alles ist zäh.**\n"
            "Beim Arbeiten rechnet Solidon in Entwurfsqualität, fein erst beim Export. "
            "Bei sehr detailreichen Modellen hilft frühes Vereinfachen; die Dreieckszahl "
            "steht im Objektbaum. Beim Öffnen zeigt eine Ladeanzeige, dass das Projekt "
            "noch lädt.\n\n"
            "**Ein grauer Knopf sagt, warum er grau ist**, als Kurzhilfe, in der "
            "Statuszeile und für den Bildschirmleser. Ohne Grund ist er ein Fehler in "
            "Solidon.\n\n"
            "**Keine Meldung endet bei der Feststellung.** Steht keine Handlung dabei, "
            "ist das ein Fehler in Solidon und einen Bericht wert: *Hilfe → Rückmeldung "
            "senden*. Bildschirmfoto, Protokoll und auf Wunsch die Sitzung gehen mit, die "
            "Vorschau zeigt vorher alles. Wer nichts aus der Hand geben möchte, legt "
            "einen Ordner auf dem eigenen Rechner ab.\n\n"
            "**Während der Demo fragt Solidon von selbst.** Nach 15 Minuten Arbeit mit "
            "einer neuen Version, gezählt nur, solange Sie etwas tun, legt sich eine "
            "Karte über die Ansicht und fragt, wie es läuft. *Rückmeldung geben* öffnet "
            "denselben Dialog wie *Hilfe → Rückmeldung senden*, mit drei freiwilligen "
            "Feldern: wie gut Sie zurechtkommen, was gut lief, was fehlte. Ohne Ihren "
            "Klick geht nichts hinaus. Die Karte kommt je Version einmal; *Nein danke* "
            "und eine gesendete Antwort gelten bis zur nächsten Version."
        ),
    ),
    Page(
        key="glossary",
        summary=_("Die Begriffe, die in Menüs und Meldungen vorkommen, kurz erklärt."),
        title=_("Wörterbuch"),
        body=_(
            "Die Wörter, die in Solidon, in Slicern und in Druckforen vorkommen — "
            "kurz erklärt.\n\n**Netz (Mesh)** — ein Körper als Hülle aus Dreiecken. "
            "STL und OBJ enthalten nichts anderes: keine Kreise, keine Maße, nur "
            "Dreiecke.\n\n**Geschlossen (wasserdicht)** — die Hülle hat kein Loch, "
            "innen und außen sind eindeutig. Nur ein geschlossener Körper lässt "
            "sich zuverlässig verknüpfen und drucken.\n\n**Merkmal** — eine Stelle "
            "im Netz, in der Solidon eine bekannte Form wiedererkannt hat: eine "
            "Bohrung, ein Zapfen, eine Rundung, eine Fläche. Aus zehntausend "
            "Dreiecken wird damit wieder etwas, das man anklicken und ändern "
            "kann.\n\n**Operation** — ein Arbeitsschritt: bohren, verrunden, teilen, "
            "einen Baustein setzen. In Solidon entsteht Geometrie nur "
            "so.\n\n**Transaktion** — alles, was ein Rückgängig auf einmal "
            "zurücknimmt. Ein Vorschlag des Chats ist genau eine, auch wenn er aus "
            "fünf Operationen besteht.\n\n**Parameter** — ein benanntes Maß des "
            "Projekts, etwa `breite`. Operationen dürfen damit rechnen; ändert "
            "sich der Wert, ändert sich alles, was daran hängt.\n\n**Baustein** — "
            "ein fertiges Konstruktionselement aus der Bibliothek, mit Maßen aus "
            "einer Tabelle statt aus dem Gedächtnis.\n\n**Skizze (Zeichnung)** — ein "
            "ebener Umriss aus Linien, Kreisen und Bögen. Aus ihr wird ein Körper, "
            "und sie bleibt danach änderbar: eine Linie verschieben heißt, das "
            "Teil ändern.\n\n**Bedingung** — eine Regel, die die Zeichnung "
            "zusammenhält: zwei Linien parallel, ein Abstand fest, ein Punkt auf "
            "einem anderen. Wird etwas gezogen, gelten sie "
            "weiter.\n\n**Freiheitsgrad** — was an einer Zeichnung noch wandern "
            "kann. „Noch 4 Maße fehlen, dann wackelt nichts mehr“ heißt: vier "
            "Dinge sind noch nicht festgelegt. Bei null ist die Zeichnung "
            "bestimmt.\n\n**Bestimmt** — jede Zahl der Zeichnung ist vergeben, "
            "nichts verrutscht mehr. Unbestimmt heißt nicht falsch: Die Zeichnung "
            "funktioniert, sie ist nur noch verschiebbar.\n\n**Hochziehen "
            "(extrudieren)** — einen Umriss senkrecht zu seiner Ebene hochziehen, "
            "bis ein Körper daraus wird. Der übliche Weg von der Zeichnung zum "
            "Teil; unter *Erzeugen → Zeichnen* heißt diese Art "
            "*Grundform hochziehen*, und andere Programme nennen ihn "
            "Extrudieren.\n\n**Tasche** — dasselbe nach innen: Der Umriss wird aus "
            "einem vorhandenen Körper herausgeschnitten, statt einen neuen "
            "aufzusetzen.\n\n**Profil** — der geschlossene Umriss, aus dem ein "
            "Körper entsteht. Nicht dasselbe wie das Material- oder Druckerprofil, "
            "das Werte liefert.\n\n**Kurve** — eine weiche Linie durch mehrere "
            "gesetzte Punkte, für Formen, die weder gerade noch kreisrund sind. In "
            "anderen Konstruktionsprogrammen heißt sie Spline.\n\n**Hilfslinie** — "
            "eine Linie, die Bedingungen trägt, aber selbst keinen Körper bildet. "
            "Die Mittellinie, an der etwas symmetrisch hängt, soll nicht "
            "mitgedruckt werden.\n\n**Passung** — wie stramm zwei Teile "
            "ineinandersitzen. Das nötige Spiel kommt aus dem "
            "Materialprofil.\n\n**Spiel** — der Abstand zwischen Zapfen und Loch, "
            "damit sich beides fügen lässt. Zu wenig klemmt, zu viel "
            "wackelt.\n\n**Presspassung** — Übermaß statt Spiel: das Teil wird "
            "eingepresst und hält von selbst.\n\n**Toleranz** — der Betrag, um den "
            "ein Maß absichtlich vom Nennmaß abweicht, damit das gedruckte "
            "Ergebnis stimmt.\n\n**Schwund** — Kunststoff zieht sich beim Abkühlen "
            "zusammen. Deshalb ist ein gedrucktes Teil etwas kleiner als "
            "gezeichnet.\n\n**Elefantenfuß** — die unterste Schicht wird gegen das "
            "Bett gedrückt und läuft nach außen aus. Das Teil ist unten breiter "
            "als geplant.\n\n**Überhang** — eine Fläche, die schräg nach außen "
            "wächst. Ab einem gewissen Winkel hat die Schicht darunter nichts "
            "mehr, worauf sie sich legen kann.\n\n**Stützen** — mitgedrucktes "
            "Material unter einem Überhang, das hinterher abgebrochen "
            "wird.\n\n**Insel** — ein Bereich einer Schicht, unter dem nichts ist. "
            "Ohne Stütze druckt der Drucker dort in die Luft.\n\n**Brücke "
            "(Spannweite)** — ein waagerechter Steg zwischen zwei Stützpunkten. "
            "Kurze Brücken gelingen ohne Stütze, lange hängen durch.\n\n**Düse** — "
            "die Öffnung, durch die der Kunststoff austritt, üblicherweise 0,4 mm. "
            "Sie begrenzt, wie fein ein Detail sein kann.\n\n**Bahnbreite** — wie "
            "breit eine gelegte Bahn wird. Zwei Bahnen nebeneinander dienen "
            "Solidon beim Filamentdruck als Richtwert für die "
            "Mindestwand.\n\n**Schichthöhe** — wie dick eine Lage ist, meist 0,2 mm. "
            "Kleiner heißt feiner und langsamer.\n\n**Slicer** — das Programm, das "
            "aus dem Modell die Druckdatei macht. Solidon ist keiner und ersetzt "
            "keinen.\n\n**G-Code** — die fertige Anweisungsliste für den Drucker. "
            "Sie kommt aus dem Slicer.\n\n**STL** — das verbreitetste Format: nur "
            "Dreiecke, keine Einheit, keine Farbe.\n\n**3MF** — der moderne "
            "Nachfolger: mit Einheit, Farben und mehreren Objekten in einer Datei. "
            "Wo der Slicer es kann, ist es die bessere Wahl.\n\n**STEP** — ein "
            "Format mit echten Flächen und Kanten statt Dreiecken. Das, was "
            "klassische CAD-Programme austauschen.\n\n**GLB** — das Format der "
            "Betrachter: Dreiecke mit Farben, in einer einzigen Datei, die jeder "
            "Browser öffnet. Zum Zeigen gedacht, nicht zum "
            "Drucken.\n\n**Prüfbericht** — die Liste dessen, was an der Szene "
            "auffällt, jeweils mit einer Handlung, die es behebt.\n\n**Filament** — "
            "eine benannte Spule mit Farbe und eigenen Druckwerten. Beim "
            "Mehrfarbendruck wird sie einem ganzen Teil oder einer erkannten "
            "Fläche zugewiesen."
        ),
    ),
)


def rules_text() -> str:
    """Die Regelsammlung, wie der Agent sie liest — nur lesbar gesetzt.

    §39 nennt sie das eigentliche Produkt. Ein Produkt, das man nicht lesen
    kann, ist schwer zu verkaufen: Bis hierher wusste niemand außer dem Agenten,
    wonach er sich richtet.
    """
    from app.core.knowledge.rules import load as load_rules
    from app.i18n import get_language

    collection = load_rules()
    language = get_language()
    lines = [
        str(
            _(
                "Diese Regeln liegen dem Agenten bei jeder Anfrage vor. Sie sind der "
                "Grund, warum er ein Schraubenloch aus der Tabelle nimmt statt es zu "
                "schätzen — und warum er nachfragt, statt zu raten."
            )
        ),
        "",
        str(_("Version: {version}", version=collection.version)),
        "",
    ]
    for rule in collection.rules:
        title, text = rule.reading(language)
        lines.append(f"### {title}")
        lines.append("")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def profiles_text() -> str:
    """Material, Drucker und Normteile als Tabellen.

    Die Zahlen stehen ohnehin im Programm und bestimmen jede Passung, jede
    Bohrung, jede Warnung über eine zu dünne Wand. Sie hier zu zeigen kostet
    nichts und beantwortet die Frage, die ein Prüfbericht offenlässt: *woher
    kommt dieser Wert?*
    """
    from app.core.knowledge import standards
    from app.core.knowledge.profiles import material_profiles, printer_profiles
    from app.i18n import format_decimal as decimal

    lines: list[str] = []

    lines.append(f"### {_('Materialien')}")
    lines.append("")
    lines.append(
        str(
            _(
                "Alle Maße in Millimetern. „Spiel“ ist der Abstand, den eine bewegliche "
                "Passung bekommt, „Presssitz“ das Übermaß einer festen. Ein Profil, das "
                "kalibriert wurde, trägt gemessene Werte statt der Vorgaben."
            )
        )
    )
    lines.append("")
    lines.append(
        f"| {_('Material')} | {_('Spiel')} | {_('Presssitz')} | {_('Bohrungszugabe')} "
        f"| {_('Elefantenfuß')} | {_('Schwund')} | {_('kalibriert')} |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for profile in material_profiles().values():
        kalibriert = _("ja") if profile.calibrated else _("nein")
        lines.append(
            f"| {profile.title} | {decimal(profile.clearance, 2)} | {decimal(profile.press, 2)} "
            f"| {decimal(profile.hole_compensation, 2)} | {decimal(profile.elephant_foot, 2)} "
            f"| {decimal(profile.shrinkage * 100, 1)} % | {kalibriert} |"
        )
    lines.append("")

    lines.append(f"### {_('Drucker')}")
    lines.append("")
    lines.append(
        str(
            _(
                "Der eingestellte Drucker entscheidet, was auf das Bett passt und ab "
                "wann eine Wand zu dünn ist — beim Filamentdrucker zwei Bahnen der "
                "Düse, beim Resin-Drucker die Mindestwand seines Profils. Das kleinste "
                "Detail ist dort die Düse, hier der Bildpunkt."
            )
        )
    )
    lines.append("")
    lines.append(
        f"| {_('Drucker')} | {_('Verfahren')} | {_('Bauraum')} | {_('Schichthöhe')} "
        f"| {_('Kleinstes Detail')} | {_('Mindestwand')} | {_('geschlossen')} |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for printer in printer_profiles().values():
        x, y, z = printer.build_volume
        enclosed = _("ja") if printer.enclosed else _("nein")
        technology = _("Resin") if printer.is_resin else _("Filament")
        # Die Mindestwand des Profils ohne Material: zwei Bahnen bei FDM, die
        # eigene Grenze bei Resin — dieselbe Herleitung wie in der Prüfung.
        wall = printer.minimum_wall if printer.is_resin else 2.0 * printer.extrusion_width
        detail = printer.pixel_size if printer.is_resin else printer.nozzle_diameter
        lines.append(
            f"| {printer.title} | {technology} | {x:.0f} × {y:.0f} × {z:.0f} "
            f"| {decimal(printer.layer_height, 2)} | {decimal(detail, 2)} "
            f"| {decimal(wall, 2)} | {enclosed} |"
        )
    lines.append("")

    lines.append(f"### {_('Normteile')}")
    lines.append("")
    lines.append(
        str(
            _(
                "Woher die Maße kommen, wenn ein Baustein ein Schraubenloch, eine "
                "Mutternfalle oder ein Gewinde setzt: aus der metrischen Reihe von M1.6 bis "
                "M64. Ein druckbares Innengewinde einer Größe passt in eine Bohrung, die bis "
                "zu einem Zehntel der Steigung enger sein darf als ihr Kernloch und dem Gang "
                "noch die halbe Tiefe in der Wand lässt. Passt keine, nimmt das Gewinde ein "
                "eigenes Maß, dessen Gänge mit voller Tiefe in der Wand der Bohrung liegen. "
                "Liegt es knapp neben einer Normgröße, wird es diese und weitet die Bohrung um "
                "den Rest auf. Auch Schraubenloch, Mutternfalle, Schraube "
                "und Mutter nehmen unter *Eigenes Maß* jeden Durchmesser. Ihre Maße sind dann "
                "aus den Normgrößen daneben abgeleitet und nicht genormt, und der Prüfbericht "
                "sagt das. Eine Einpressbuchse, die hier fehlt, bekommt Bohrung und Länge aus "
                "ihrem Datenblatt."
            )
        )
    )
    lines.append("")
    lines.append(
        f"| {_('Größe')} | {_('Nennmaß')} | {_('Durchgangsloch')} | {_('Kernloch')} "
        f"| {_('Kopf')} | {_('Steigung')} |"
    )
    lines.append("|---|---|---|---|---|---|")
    for screw in standards.load().screws.values():
        lines.append(
            f"| {screw.size} | {decimal(screw.nominal, 1)} | {decimal(screw.clearance, 1)} "
            f"| {decimal(screw.tap, 2)} | {decimal(screw.head, 1)} | {decimal(screw.pitch, 2)} |"
        )
    lines.append("")
    lines.append(
        str(
            _(
                "Muttern, Scheiben, Einpressbuchsen, Magnete, Lager, Profile und Rohre "
                "stehen in derselben Tabelle; die Bausteine schlagen dort nach."
            )
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def remote_text(registry: Registry | None = None) -> str:
    """Was ein fremdes Programm über die Leitung aufrufen kann.

    Die geschriebene Seite *Fernsteuerung* sagt, wie man sie einschaltet und
    warum sie standardmäßig aus ist. Was fehlte, war die Liste — und die ist
    genau das, was jemand braucht, der eine Gegenstelle einrichtet.

    Aus ``remote_tools`` und nicht aus dem Register: Zwei Operationen gehen
    nicht durch die Leitung, und eine Seite, die sie mitzählte, verspräche
    etwas, das beim ersten Aufruf abgelehnt wird.
    """
    from app.core.agent.remote import DENIED, remote_tools

    source = registry or REGISTRY
    reachable = {entry["name"] for entry in remote_tools(source)}
    lines = [
        str(
            _(
                "Jeder Eintrag hier ist dieselbe Operation, die auch im Fenster steht — "
                "rechts in der Auswahl oder im Menü —, mit denselben Parametern. Was "
                "hereinkommt, wird eine Transaktion wie jede andere: Der Verlauf zeigt "
                "sie, ein Strg+Z nimmt sie zurück."
            )
        ),
        "",
    ]
    for name, entries in source.by_category().items():
        listed = [spec for spec in entries if spec.name in reachable]
        if not listed:
            continue
        lines.append(f"### {CATEGORIES[name]}")
        lines.append("")
        for spec in listed:
            # Zuerst der Titel aus dem Menü, dann der Leitungsname: Der eine
            # sagt dem Leser, was gemeint ist, der andere der Gegenstelle,
            # was zu senden ist.
            doc = " ".join(str(spec.doc).split())
            head = f"- **{spec.title}** (`{spec.name}`)"
            lines.append(f"{head} — {doc}" if doc else head)
        lines.append("")

    # Was nicht aus dem Register kommt: Werkzeuge der Agentenschicht. Sie
    # lesen den Zustand oder ändern das Dokument neben dem Stapel — Parameter,
    # Passungen, Druckziel, Rücknahme. Eine Liste, die nur Operationen zeigte,
    # ließe genau die Hälfte weg, die eine Gegenstelle zuerst braucht.
    operations = {spec.name for spec in source.all()}
    others = [entry for entry in remote_tools(source) if entry["name"] not in operations]
    if others:
        lines.append(f"### {_('Lesen, Parameter, Rücknahme')}")
        lines.append("")
        lines.append(
            str(
                _(
                    "Diese Werkzeuge stehen in keinem Menü — sie sind die Auskunft, die "
                    "eine Gegenstelle braucht, bevor sie etwas ändert."
                )
            )
        )
        lines.append("")
        # Menschentitel für Werkzeuge, die in keinem Menü stehen — nur fürs
        # Handbuch, die Leitung kennt weiter die Namen. Ein Werkzeug ohne
        # Eintrag hier erscheint mit seinem Namen, statt zu fehlen.
        remote_titles = {
            "undo_transaction": _("Transaktion zurücknehmen"),
            "add_parameter": _("Parameter anlegen"),
            "set_parameter": _("Parameter ändern"),
            "add_fit": _("Passung anlegen"),
            "read_report": _("Prüfbericht lesen"),
            "find_part": _("Baustein suchen"),
            "read_digest": _("Steckbrief lesen"),
            "read_standard": _("Normteilmaße nachschlagen"),
            "read_analysis": _("Analyse lesen"),
            "set_print_target": _("Drucker und Material wechseln"),
        }
        for entry in others:
            doc = " ".join(str(entry["description"]).split())
            title = remote_titles.get(entry["name"])
            head = f"- **{title}** (`{entry['name']}`)" if title else f"- `{entry['name']}`"
            lines.append(f"{head} — {doc}" if doc else head)
        lines.append("")

    lines.append(f"### {_('Was nicht durch die Leitung geht')}")
    lines.append("")
    lines.append(
        str(
            _(
                "Zwei Operationen sind gesperrt, und beide aus demselben Grund: Ein "
                "fremdes Programm soll nicht bestimmen, was auf diesem Rechner "
                "ausgeführt oder gelesen wird."
            )
        )
    )
    lines.append("")
    # ``ask_user`` steht in keinem Register — es ist ein Werkzeug der
    # Agentenschicht und keine Operation. Deshalb über die vorhandenen Namen
    # und nicht über einen Zugriff, der bei ihm mit einem Programmfehler endet.
    titles = {spec.name: str(spec.title) for spec in source.all()}
    for name in sorted(DENIED):
        lines.append(f"- **{titles.get(name, _('Rückfrage an den Nutzer'))}** (`{name}`)")
    lines.append("")
    lines.append(
        str(
            _(
                "Dazu wird jedes Argument abgewiesen, das wie ein Dateipfad aussieht. "
                "Beides bleibt im Fenster benutzbar; gesperrt ist nur der Weg von "
                "außen."
            )
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def messages_text() -> str:
    """Jede Meldung im Wortlaut, mit dem, was sie bedeutet, und dem Ausweg.

    Die geschriebene Seite *Wenn etwas nicht geht* erklärt die häufigsten
    Fälle in ganzen Sätzen. Was fehlte, war die andere Richtung: Man liest
    einen Satz im Fenster und sucht ihn im Handbuch. Genau dafür steht die
    Meldung hier links und wörtlich — abgetippt findet man sie sonst nicht.

    Erzeugt aus der Ausnahmehierarchie: Regel 17 verlangt, dass jede Ausnahme
    einen Handlungsvorschlag trägt, also gibt es zu jeder auch die Spalte
    „was hilft" — und eine neue Ausnahme kann gar nicht in die Anwendung
    kommen, ohne hier aufzutauchen.
    """
    import importlib
    import pkgutil

    import app.core
    from app.core import errors

    # Die Hierarchie ist die Wahrheit, aber sie kennt nur, was importiert ist.
    # Hier stand eine handgepflegte Liste von fünf Modulen, und sie log:
    # ``SendFailed`` — „Die Rückmeldung ließ sich nicht senden", der
    # wahrscheinlichste Fehler überhaupt — wohnt in ``app.core.support`` und
    # fehlte im ausgelieferten Handbuch; der Inhalt hing daran, was der
    # erzeugende Prozess zufällig schon importiert hatte (Gesamtreview L-3).
    # Jetzt läuft der Einsammler über alle Kernmodule; dass jedes davon ohne
    # Nebenwirkung importierbar ist, sichert ``tests/test_core_isolation.py``.
    for info in pkgutil.walk_packages(app.core.__path__, prefix="app.core."):
        importlib.import_module(info.name)

    def walk(kind: type[errors.AppError]) -> list[type[errors.AppError]]:
        found: list[type[errors.AppError]] = []
        for child in kind.__subclasses__():
            # Nur die Anwendung selbst: Eine Testdatei, die sich im selben
            # Prozess eine Wegwerf-Ausnahme baut, gehört nicht ins Handbuch.
            if child.__module__.startswith("app.core."):
                found.append(child)
            found.extend(walk(child))
        return found

    lines = [
        str(
            _(
                "Was die Anwendung sagt, wenn etwas nicht geht — im Wortlaut, damit es "
                "sich nachschlagen lässt. Ein Fehler endet hier nie mit „fehlgeschlagen“: "
                "Zu jeder Meldung gehört mindestens ein Weg weiter."
            )
        ),
        "",
        f"| {_('Meldung')} | {_('Was hilft')} |",
        "|---|---|",
    ]
    seen: set[str] = set()
    for kind in sorted(walk(errors.AppError), key=lambda entry: str(entry.default_title)):
        title = str(kind.default_title)
        if title in seen:
            continue
        seen.add(title)
        ways = ", ".join(str(action.label) for action in kind.default_suggestions)
        lines.append(f"| {title} | {ways} |")
    lines.append("")
    lines.append(
        str(
            _(
                "Die Zeile darunter im Fenster nennt den Grund für genau diesen Fall — "
                "welche Wand zu dünn ist, welcher Wert außerhalb liegt, welche Datei "
                "gemeint war."
            )
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def models_text() -> str:
    """Welche Modelle Solidon benutzt, woher sie kommen und was sie leisten.

    **Die Auskunft gab es, verteilt auf vier Stellen.** Die Modellauswahl im
    Chat-Dialog nannte Größe und Trefferquote, das Handbuch nannte eines davon
    im Fließtext, der Erzeugungsdialog nannte für den Textweg gar keines („ein
    Bildmodell“ — welches, stand nirgends), und was Solidon selbst einrichtet,
    stand in den Konstanten von ``comfy_setup``. Wer wissen wollte, was er
    braucht, bevor er anfängt, fand vier Teilantworten.

    Erzeugt und nicht geschrieben, aus demselben Grund wie die Regeln und die
    Profile: Eine zweite Liste veraltet. Kommt ein Modell dazu oder ändert sich
    eine Messung, ändert sich diese Seite mit — sonst stünde hier eine
    Empfehlung, die niemand mehr gibt.
    """
    from app.core.backends import comfy_setup
    from app.core.backends.llm import (
        DEFAULT_OLLAMA_MODEL,
        OLLAMA_MIN_PARAMETERS,
        OLLAMA_SUGGESTIONS,
        OLLAMA_UNSUITABLE,
    )
    from app.i18n import format_decimal as decimal

    lines = [
        str(
            _(
                "Solidon rechnet Geometrie selbst und braucht dafür nichts. Zwei "
                "Dinge kommen von außen, und jedes davon braucht ein Modell: der "
                "Chat und das Erzeugen aus Text oder Bild. Ohne beides läuft alles "
                "andere — Einlesen, Ändern, Prüfen, Exportieren."
            )
        ),
        "",
        f"## {_('Für den Chat: ein Sprachmodell')}",
        "",
        str(
            _(
                "Läuft auf diesem Rechner, über Ollama. Geholt wird es in "
                "*Bearbeiten → Chat einrichten*: ein Knopf startet den Dienst, "
                "einer lädt das Modell, einer prüft es. Statt eines lokalen "
                "Modells geht auch ein eigener Schlüssel für ein gehostetes."
            )
        ),
        "",
        f"| {_('Modell')} | {_('Größe')} | {_('Was gemessen wurde')} |",
        "|---|---|---|",
    ]
    for name, gigabytes, note in OLLAMA_SUGGESTIONS:
        label = f"**{name}**" if name == DEFAULT_OLLAMA_MODEL else name
        lines.append(f"| {label} | {decimal(gigabytes, 1)} GB | {note} |")
    lines.extend(
        [
            "",
            str(
                _(
                    "Fett steht die Vorgabe. Gemessen wurde an acht Anfragen, die je "
                    "einen Werkzeugaufruf verlangen — bei einer absichtlich unklaren "
                    "ist die Rückfrage der richtige. Ein Modell, das nur darüber "
                    "schreibt, statt ihn auszuführen, antwortet im Chat und tut "
                    "nichts. Deshalb der Knopf *Werkzeuge prüfen*: Weder Größe noch "
                    "Anbieter sagen es voraus."
                )
            ),
            "",
            f"### {_('Geprüft und nicht empfohlen')}",
            "",
            f"| {_('Modell')} | {_('Größe')} | {_('Was gemessen wurde')} |",
            "|---|---|---|",
            *(
                f"| {name} | {decimal(gigabytes, 1)} GB | {note} |"
                for name, gigabytes, note in OLLAMA_UNSUITABLE
            ),
            "",
            str(
                _(
                    "Unterhalb von {n} Milliarden Parametern scheitern die Aufrufe "
                    "reproduzierbar. Und die Grafikkarte entscheidet über die Zeit: "
                    "Wo Ollama sie nicht anspricht, rechnet es auf dem Prozessor, "
                    "und das ist keine andere Geschwindigkeit, sondern eine andere "
                    "Größenordnung."
                )
            ).format(n=decimal(OLLAMA_MIN_PARAMETERS, 0)),
            "",
            f"## {_('Für das Erzeugen: drei Modelle')}",
            "",
            str(
                _(
                    "Laufen in ComfyUI, nacheinander, und alle drei richtet Solidon "
                    "ein — in der Liste der zusätzlichen Programme steht in der Zeile "
                    "von ComfyUI *Modelle einrichten …*. Das dritte braucht nur der "
                    "Weg aus Text; es ist deshalb ein eigenes Häkchen."
                )
            ),
            "",
            f"| {_('Wofür')} | {_('Modell')} | {_('Lizenz')} | {_('Größe')} | {_('Woher')} |",
            "|---|---|---|---|---|",
            "| {wofuer} | TRELLIS.2-4B, DINOv3 | MIT, {dino} | {groesse} | {woher} |".format(
                wofuer=_("Aus einem Bild einen Körper"),
                dino=_("DINOv3-Lizenz von Meta"),
                groesse=f"{decimal(comfy_setup.SHAPE_GIGABYTES, 1)} GB",
                woher=_("richtet Solidon ein"),
            ),
            "| {wofuer} | BiRefNet | MIT | {groesse} | {woher} |".format(
                wofuer=_("Das Objekt freistellen"),
                groesse=f"{comfy_setup.BACKGROUND_MEGABYTES} MB",
                woher=_("richtet Solidon ein"),
            ),
            "| {wofuer} | FLUX.2 [klein] 4B, Qwen3-4B | Apache-2.0 | {groesse} | {woher} |".format(
                wofuer=_("Aus Text erst ein Bild"),
                groesse=f"{decimal(comfy_setup.IMAGE_MODEL_GIGABYTES, 1)} GB",
                woher=_("richtet Solidon ein, auf Wunsch"),
            ),
            "",
            str(
                _(
                    "TRELLIS.2 von Microsoft steht unter der MIT-Lizenz. Es liest das "
                    "Bild mit DINOv3 von Meta, und dafür gilt Metas DINOv3-Lizenz: "
                    "weltweit und gewerblich nutzbar, mit Nutzungsbedingungen, unter "
                    "anderem nicht für Waffen und nicht gegen Handelsbeschränkungen. "
                    "Wer TRELLIS.2 benutzt, nimmt diese Bedingungen an."
                )
            ),
            "",
            f"### {_('Das Bildmodell')}",
            "",
            str(
                _(
                    "Nur für den Weg aus Text. Wer ein Foto oder eine Zeichnung "
                    "mitbringt, braucht es nie — und rund {size} GB für einen Weg, "
                    "den ein vorhandenes Bild umgeht, lädt Solidon niemandem "
                    "ungefragt herunter. Deshalb ist es in der Einrichtung ein "
                    "eigenes Häkchen; fehlt es beim Erzeugen, führt der Knopf "
                    "*Bildmodell einrichten …* direkt dorthin.",
                    size=Figure(f"{comfy_setup.IMAGE_MODEL_GIGABYTES:g}"),
                )
            ),
            "",
            str(
                _(
                    "Geholt werden **{file}** aus dem Verzeichnis *{source}* auf "
                    "Hugging Face, dazu der Textkodierer und die VAE, jede Datei in "
                    "einem festen Stand und mit Prüfsumme, in die passenden Ordner "
                    "unter *models* im Ordner von ComfyUI. Wer sie lieber selbst "
                    "hinlegt, legt sie dorthin. FLUX.2 [klein] 4B und Qwen3-4B stehen "
                    "unter der Lizenz Apache-2.0."
                )
            ).format(
                file=comfy_setup.IMAGE_MODEL_FILES[0].name,
                source=comfy_setup.IMAGE_MODEL_FILES[0].repo,
            ),
            "",
            str(
                _(
                    "Der Ablauf ist auf die schnelle Fassung von FLUX.2 [klein] 4B "
                    "eingestellt. Die 9B-Fassung und das Basismodell nimmt Solidon "
                    "nicht, auch wenn sie im Ordner liegen: Die 9B-Fassung darf "
                    "nicht gewerblich genutzt werden, das Basismodell braucht andere "
                    "Einstellungen."
                )
            ),
            "",
            f"### {_('Wie lange es dauert')}",
            "",
            str(
                _(
                    "Das hängt vor allem an der Grafikkarte. Aus **Text** dauert es "
                    "länger als aus einem **Bild**: Vorher lädt das Bildmodell in den "
                    "Grafikspeicher und rechnet ein Bild, danach erst das Modell für "
                    "den Körper. Dann kommt in beiden Fällen dieselbe Kette: auf "
                    "Arbeitsgröße bringen, reparieren, und bei sehr feinen Netzen die "
                    "Dreiecke verringern."
                )
            ),
            "",
            str(
                _(
                    "Ohne passende Grafikkarte dauert beides ein Vielfaches. Was "
                    "abbricht, ist ein Fehler und keine Langsamkeit — dann steht der "
                    "Satz von ComfyUI im Dialog, samt dem Schritt, in dem es riss."
                )
            ),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def knowledge_pages() -> tuple[Page, ...]:
    """Bedienrelevantes Nachschlagen: Modelle wählen, Druckwerte und Meldungen verstehen.

    Regeln und Werkzeugverträge für den Agenten gehören nicht zur Bedienung.
    Ihre Textausgaben bleiben separat abrufbar, erscheinen aber nicht in den
    Seiten, der Suche oder den Kundenausgaben des Handbuchs.
    """

    def titled(title: object, body: str) -> str:
        # Die Überschrift gehört in den Text, wie bei den Kategorie-Seiten:
        # daran erkennt der Ankersetzer das Kapitel, und das Verzeichnis
        # springt hin, statt ins Leere zu zeigen.
        return f"## {title}\n\n{body}"

    profiles_title = _("Material, Drucker, Normteile")
    messages_title = _("Meldungen im Wortlaut")
    models_title = _("Welche Modelle Solidon benutzt")
    return (
        Page(
            key="models",
            title=models_title,
            body=titled(models_title, models_text()),
            generated=True,
        ),
        Page(
            key="profiles",
            title=profiles_title,
            body=titled(profiles_title, profiles_text()),
            generated=True,
        ),
        Page(
            key="messages",
            title=messages_title,
            body=titled(messages_title, messages_text()),
            generated=True,
        ),
    )


#: Die Gliederung: je Teil die geschriebenen Seiten und die Bildanleitungen in
#: der Reihenfolge, in der jemand sie liest. Die erzeugten Seiten stehen nicht
#: darin; sie folgen am Ende von „Nachschlagen", erst das Wissen, dann eine
#: Seite je Kategorie des Registers.
#:
#: Eine Seite, die hier fehlt, fehlt im Handbuch. ``tests/test_guides.py``
#: verlangt deshalb jede geschriebene Seite und jede Anleitung genau einmal.
OUTLINE: Final[tuple[tuple[Part, tuple[str, ...]], ...]] = (
    (
        "start",
        (
            WHERE_TO_START,
            "what",
            "window-overview",
            "print-a-model",
            "drill-a-hole",
            "first-part",
            "housing-with-lid",
            "split-a-large-part",
            "ways",
        ),
    ),
    (
        "tasks",
        (
            "move-and-turn",
            "change-a-dimension",
            "undo-a-step",
            "thread-a-hole",
            "round-edges",
            "label-a-part",
            "draw-and-pull",
            "two-colours",
            "repair-a-model",
        ),
    ),
    (
        "topics",
        (
            "window",
            "history",
            "moving",
            "tolerances",
            "parts",
            "sketch",
            "looking",
            "features",
            "parameters",
            "print",
            "export",
            "splitting",
            "labels",
            "surfaces",
            "variants",
            "resin",
            "sculpting",
            "own-parts",
            "exchange",
            "generating",
            "chat",
            "extras",
            "remote",
            "activation",
        ),
    ),
    ("help", ("trouble", SPACEMOUSE_ACCESS)),
    ("reference", ("glossary",)),
)


def _part_for_page(key: str) -> Part:
    """Liefert den Handbuchteil aus der einen Gliederung."""
    for part, keys in OUTLINE:
        if key in keys:
            return part
    raise KeyError(f"Die Handbuchgliederung kennt die Seite {key!r} nicht.")


def guide_page(guide: guides.Guide) -> Page:
    """Eine Bildanleitung als Handbuchseite: je Schritt ein Satz und sein Bild.

    Hat eine Anleitung mehr als einen Schritt, trägt jeder Satz seine Nummer
    vorn, wie im Bild. Ein Legendenschritt bekommt unter dem Bild die
    nummerierte Liste dessen, worauf die Nummern im Bild zeigen.

    Der Text entsteht beim Aufruf in der eingestellten Sprache, wie bei den
    erzeugten Seiten: Die Sätze sind einzeln übersetzt, die Nummern und
    Bildverweise gehören keiner Sprache.
    """
    numbered = len(guide.steps) > 1
    blocks: list[str] = []
    for number, (figure_key, one) in enumerate(
        zip(guide.figure_keys(), guide.steps, strict=True), start=1
    ):
        blocks.append(f"**{number}.** {one.text}" if numbered else str(one.text))
        blocks.append(f"![](figure:{figure_key})")
        if one.is_legend:
            blocks.append(
                "\n".join(f"{index}. {mark.label}" for index, mark in enumerate(one.marks, 1))
            )
    return Page(
        key=guide.key,
        title=guide.title,
        summary=guide.summary,
        body="\n\n".join(blocks),
        part=_part_for_page(guide.key),
    )


def pages(registry: Registry | None = None) -> tuple[Page, ...]:
    """Alle Seiten in der Gliederung des Handbuchs, die erzeugten am Ende."""
    source = registry or REGISTRY
    generated = tuple(
        Page(
            key=reference_key(category),
            title=CATEGORIES[category],
            body=documentation(source, category=category, technical=False),
            generated=True,
        )
        for category in source.by_category()
    )
    written = {
        page.key: page
        for page in (
            _where_to_start_page(),
            *(_with_its_guides(_with_download_sizes(page)) for page in INTRODUCTION),
            _spacemouse_page(),
            *(guide_page(guide) for guide in guides.GUIDES),
        )
    }
    arranged = tuple(replace(written[key], part=part) for part, keys in OUTLINE for key in keys)
    return (*arranged, *knowledge_pages(), *generated)


#: Seiten, deren Text Downloadgrößen nennt — als Platzhalter, gefüllt in
#: :func:`_with_download_sizes`.
SIZED_PAGES: Final = frozenset({"extras"})


def _with_download_sizes(page: Page) -> Page:
    """Die Größen der Downloads kommen aus den Konstanten, nicht aus dem Satz.

    ``comfy_setup`` rechnet sie aus den Dateien, ``llm.OLLAMA_SUGGESTIONS``
    nennt die bewährten Modelle samt Größe; getippt veralteten sie beim
    nächsten Stand (Review 1 P3, G-9). Gefüllt wird erst hier, weil beide
    Module zu laden eine Drittelsekunde kostet — beim Import des Handbuchs
    für jede Seite, die sie nicht braucht.
    """
    if page.key not in SIZED_PAGES or not isinstance(page.body, TranslatableText):
        return page
    import math

    from app.core.backends import comfy_setup
    from app.core.backends.llm import OLLAMA_SUGGESTIONS

    pulled = [gigabytes for _name, gigabytes, _note in OLLAMA_SUGGESTIONS]
    # Platzhalter des Seitentexts, keine Befundwerte: Kein Tooltip zeigt sie
    # einzeln (``labels.value_label`` gilt ihnen nicht).
    sizes = {
        "least": math.ceil(min(pulled)),
        "most": math.ceil(max(pulled)),
        "shape": Figure(f"{comfy_setup.WEIGHT_GIGABYTES:g}"),
        "image": Figure(f"{comfy_setup.IMAGE_MODEL_GIGABYTES:g}"),
    }
    return replace(page, body=replace(page.body, values=sizes))


def _with_its_guides(page: Page) -> Page:
    """Eine Erklärseite mit dem Verweis auf die Anleitungen, die ihr Thema in Bildern zeigen.

    Erzeugt aus :attr:`guides.Guide.topics` und nicht in den Seitentext
    geschrieben: Der Text jeder Seite ist ein Katalogschlüssel, und ein
    Verweis darin verlangte die ganze Seite in fünf Sprachen neu. So kommt eine
    neue Anleitung mit einer Zeile an ihrer Seite an, unter dem Titel, unter
    dem sie auch in der Seitenliste steht.
    """
    shown = [guide for guide in guides.GUIDES if page.key in guide.topics]
    if not shown:
        return page
    links = " · ".join(f"[{guide.title}](manual:{guide.key})" for guide in shown)
    return replace(page, body=f"{page.body}\n\n**{_('Schritt für Schritt:')}** {links}")


def find(key: str, registry: Registry | None = None) -> Page | None:
    """Eine Seite beim Namen — für den Weg von einer Operation in ihr Kapitel."""
    for page in pages(registry):
        if page.key == key:
            return page
    return None


def help_for(operation: str, registry: Registry | None = None) -> tuple[str, str]:
    """Wo das Handbuch eine Operation erklärt: Seite und Stelle (Konzept Handbuch §7).

    Lehrt eine Anleitung die Operation (``Guide.teaches``), ist es ihre Seite,
    von oben. Sonst ist es der Eintrag in der Referenz ihrer Kategorie, an
    seiner unsichtbaren Sprungmarke. Gleich benannte Operationen haben damit
    eigene Ziele, während das Handbuch nur den Kundentitel zeigt. F1 im
    Operationsdialog fragt hier und nicht in der Oberfläche, damit die
    Antwort ohne Fenster prüfbar ist.
    """
    for guide in guides.GUIDES:
        if operation in guide.teaches:
            return guide.key, ""
    spec = (registry or REGISTRY).get(operation)
    return reference_key(spec.category), f"#{operation_anchor(spec.name)}"


def titled(page: Page, text: str) -> str:
    """Der Text einer Seite mit ihrer Überschrift — genau einmal.

    Jede Seite bekommt eine, auch die erzeugten. Die Referenzkapitel bringen
    sie mit (``documentation`` schreibt ``## Kategorie``), die vier
    Wissensseiten nicht: sie fingen mitten im Satz an. Auf der Website standen
    sie damit als Kapitel 22 bis 25 im Verzeichnis, und wer eines anklickte,
    landete nirgends — der Anker hängt an der Überschrift, und die gab es
    nicht. Im Handbuchfenster stand über denselben vier Seiten kein Titel.

    Entschieden wird am Text und nicht am Feld ``generated``, sonst stünde über
    einem Referenzkapitel zweimal dasselbe. Und die Regel steht hier und nicht
    zweimal: Fenster und erzeugtes Handbuch hatten je ihre eigene, und nur eine
    davon war je nachgezogen worden.
    """
    return text if text.startswith(f"## {page.title}") else f"## {page.title}\n\n{text}"


def as_markdown(registry: Registry | None = None, *, with_figures: bool = False) -> str:
    """Das ganze Handbuch am Stück, für die Kommandozeile und zum Nachlesen.

    ``with_figures`` behält die Bildverweise und die Verweise zwischen den
    Seiten, wie sie im Text stehen — das braucht, wer daraus HTML oder ein PDF
    macht. Ohne das tritt an jede Stelle der Alt-Text der Abbildung: eine
    Textausgabe, in der plötzlich eine Aussage fehlt, weil sie im Bild stand,
    wäre eine unvollständige. Von einem Seitenverweis bleibt dann sein Text.
    """
    from app.core.markup import unlinked

    parts = []
    for page in pages(registry):
        # Über ``Page.text`` und nicht über ``page.body``: Die Kurzfassung
        # gehört zur Seite, und das Handbuchfenster liest dieselbe Methode.
        text = page.text() if with_figures else unlinked(without_figures(page.text()))
        parts.append(titled(page, text))
    return "\n\n".join(parts).rstrip() + "\n"


def as_html(
    registry: Registry | None = None,
    *,
    figure_source: Callable[[str], str] | None = None,
    dark_source: Callable[[str], str] | None = None,
    link_target: Callable[[str], str | None] | None = None,
) -> str:
    """Das ganze Handbuch als HTML-Rumpf — für die Website und für das PDF.

    ``figure_source`` sagt, unter welcher Adresse eine Abbildung zu finden ist;
    wer nichts liefert, bekommt an ihrer Stelle den Alt-Text. Wo die Datei
    liegt, entscheidet damit der Aufrufer und nicht der Kern — hier soll keine
    Ablagestruktur festgeschrieben werden.

    ``dark_source`` beantwortet dieselbe Frage für ein dunkles Farbschema. Wer
    für einen Schlüssel nichts liefert, bekommt dort ein gewöhnliches Bild —
    ein Bildschirmfoto hat keine zweite Version, eine Zeichnung schon.

    ``link_target`` sagt, wohin ein Verweis auf eine andere Seite führt
    (:data:`app.core.markup.MANUAL_LINK`), auf der Website etwa zum Anker des
    Kapitels. Ohne die Funktion bleibt der Text des Verweises stehen.
    """
    from app.core import figures
    from app.core.markup import FigureSource, to_html

    def resolve(key: str) -> FigureSource | None:
        figure = figures.find(key)
        if figure is None:
            return None
        source = figure_source(key) if figure_source else ""
        dark = dark_source(key) if dark_source else ""
        return FigureSource(source, str(figure.alt), str(figure.caption), dark)

    return to_html(as_markdown(registry, with_figures=True), resolve, link_target)


def without_figures(body: str) -> str:
    """Bildverweise durch ihren Alt-Text ersetzen."""
    from app.core import figures
    from app.core.markup import plain

    def describe(match: re.Match[str]) -> str:
        figure = figures.find(match.group(1))
        if figure is None or not figure.in_text:
            return ""
        described = _("Abbildung: {description}", description=plain(str(figure.alt)))
        return f"*{described}*"

    return FIGURE_PATTERN.sub(describe, body)
