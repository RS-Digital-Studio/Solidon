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
Unterschied zwischen „ich sehe 62 Einträge" und „ich weiß, was ich damit
mache" — und sie sind kurz gehalten, weil ein Handbuch, das gelesen werden
soll, keine hundert Seiten haben darf.

Der Text lebt hier und nicht in der Oberfläche: er ist ohne Qt prüfbar, und
die Kommandozeile kann ihn genauso ausgeben wie das Fenster.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from app.core.registry import documentation
from app.core.registry.registry import CATEGORIES, REGISTRY, Registry
from app.i18n import TranslatableText, _


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

#: Das Kapitel, auf das der Startbildschirm zeigt.
#:
#: Sein Knopf heißt „Handbuch — die ersten fünfzehn Minuten" und öffnete „Was
#: Solidon ist", den ersten von über vierzig Einträgen: ``pages()`` liefert die
#: Einführung zuerst, und das Handbuchfenster stellte auf Zeile null. Wer den
#: einzigen Hilfe-Knopf des Startbildschirms drückt, musste das zugesagte
#: Kapitel danach selbst suchen.
#:
#: Der Schlüssel steht hier und nicht in der Oberfläche: Welche Seite gemeint
#: ist, weiß das Handbuch. ``tests/test_manual.py`` hält Knopftext und
#: Seitentitel zusammen.
FIRST_MINUTES: Final = "start"


#: Die geschriebenen Seiten, in der Reihenfolge, in der sie jemand liest.
INTRODUCTION: Final[tuple[Page, ...]] = (
    Page(
        key="what",
        summary=_("Wofür das Programm gedacht ist, und wofür nicht — in vier Absätzen."),
        title=_("Was Solidon ist"),
        body=_(
            "Solidon baut, ändert und druckreif macht — Modelle für den "
            "3D-Drucker.\n\n"
            "Drei Dinge unterscheiden es von dem, was sonst offen ist:\n\n"
            "* **Jeder Schritt bleibt eine Zahl.** Eine Bohrung, die zwei "
            "Millimeter danebensitzt, wird verschoben und nicht neu gebohrt.\n"
            "* **Passungen kommen aus dem Material, nicht aus dem Gefühl.** "
            "Wer sein Spiel einmal misst, verbessert damit auch Teile, die er "
            "vorher gebaut hat.\n"
            "* **Bausteine statt Handarbeit.** Mutternfalle, Heat-Set-Buchse, "
            "Rastnase, Filmscharnier, Magnettasche — je ein Klick statt je "
            "einer halben Stunde.\n\n"
            "**Skizzen gehören dazu:** Grundformen und selbst Gezeichnetes mit "
            "Zwangsbedingungen — extrudiert, getascht, rotiert oder entlang "
            "eines Bogens geführt, und jedes Maß darf ein Projektparameter "
            "sein.\n\n"
            "**Was es nicht ist:** kein Slicer — die Druckdatei kommt weiter "
            "aus dem Slicer, Solidon sucht und bewertet nur. Keine Cloud — kein "
            "Konto, keine Telemetrie, nichts, was den Rechner von allein verlässt.\n\n"
            "Ohne Netz, ohne Konto und ohne Sprachmodell bleibt alles außer dem "
            "Chat benutzbar."
        ),
    ),
    Page(
        key="start",
        summary=_("Der erste Durchlauf von der heruntergeladenen Datei bis zur Druckdatei."),
        title=_("Die ersten fünfzehn Minuten"),
        body=_(
            "Wer noch nie mit einem Konstruktionsprogramm gearbeitet hat, fängt "
            "hier an. Ein heruntergeladenes Modell bekommt ein Loch und geht "
            "danach in den Slicer — der häufigste aller Fälle, in acht "
            "Schritten.\n\n"
            "**1. Beim ersten Start drei Fragen beantworten.** Sprache, Drucker, "
            "Material. Steht der eigene Drucker nicht dabei, tut es ein ähnlicher "
            "— die Maße lassen sich später ändern. *Später einstellen* geht auch, "
            "dann gelten Vorgaben.\n\n"
            "![](figure:start-screen)\n\n"
            "**2. Eine Datei auf das Fenster ziehen.** STL, 3MF, OBJ, GLB, "
            "PLY, OFF und STEP; dazu SVG und DXF für Zeichnungen, die "
            "extrudiert werden sollen. Ist in der Datei keine Einheit "
            "vermerkt — bei STL nie —, fragt Solidon nach, statt zu raten. Im "
            "Zweifel Millimeter: fast alles im Netz ist in Millimetern.\n\n"
            "Liegt die Datei noch nicht auf der Platte, geht auch ihre Adresse: "
            "den Herunterladen-Verweis aus dem Browser auf das Fenster ziehen, "
            "oder *Datei → Modell aus dem Netz* — das Feld ist mit dem gefüllt, "
            "was in der Zwischenablage steht. Wer dabei die Adresse der "
            "Modellseite erwischt statt der Datei, bekommt es gesagt.\n\n"
            "**3. In den Prüfbericht schauen.** Rechts steht, was mit dem Modell "
            "nicht stimmt. Löcher, doppelte Flächen, verkehrt herum liegende "
            "Dreiecke — bei heruntergeladenen Modellen ist das die Regel, nicht "
            "die Ausnahme. Jeder Befund hat eine Schaltfläche, die ihn behebt.\n\n"
            "![](figure:report)\n\n"
            "**4. Reparieren.** Meist genügt die vorgeschlagene Handlung im "
            "Bericht. Das Modell bleibt dabei, was es war — die Reparatur ist ein "
            "Schritt im Verlauf und lässt sich zurücknehmen.\n\n"
            "![](figure:main-window)\n\n"
            "**5. Auf die Fläche zeigen, in die das Loch soll, und rechts "
            "klicken.** Das Menü nennt genau die Operationen, die auf diese "
            "Fläche passen — bei einer ebenen Fläche zum Beispiel *Bohrung "
            "setzen*. Der Rechtsklick trifft immer das Genaueste unter dem "
            "Zeiger, ohne Vorarbeit.\n\n"
            "Der Linksklick geht einen Schritt langsamer, und das mit Absicht: "
            "Der erste wählt das **ganze Teil**, der zweite die Stelle darin — "
            "eine Fläche, eine Bohrung. So kommt man auch an das Teil selbst "
            "heran, um es zu verschieben oder zu drehen. `Esc` geht wieder eine "
            "Stufe zurück.\n\n"
            "**6. Den Durchmesser eintragen und übernehmen.** Ort und Richtung "
            "stehen schon da, weil die Fläche ausgewählt war. Alles Weitere — "
            "Toleranz, Auflösung — liegt hinter *Weitere Einstellungen* und "
            "bleibt in aller Regel unberührt.\n\n"
            "![](figure:op-dialog)\n\n"
            "Das Ergebnis: derselbe Körper, ein Loch mehr.\n\n"
            "![](figure:drill)\n\n"
            "**7. Sitzt das Loch falsch, wird es verschoben, nicht neu gebohrt.** "
            "Ein Doppelklick auf den Schritt im Verlauf öffnet ihn wieder. Zahl "
            "ändern, übernehmen, fertig. Das gilt auch noch nächste Woche.\n\n"
            "**8. Exportieren.** *Datei → Exportieren*, dann 3MF, wenn der Slicer "
            "es kann — sonst STL. Diese Datei kommt in den Slicer, und der macht "
            "daraus den G-Code.\n\n"
            "Mehr braucht der erste Durchgang nicht. Alles Übrige in diesem "
            "Handbuch ist Ausbau davon."
        ),
    ),
    Page(
        key="window",
        summary=_("Welcher Bereich des Fensters welche Frage beantwortet."),
        title=_("Das Fenster"),
        body=_(
            "Drei Zonen, und keine davon versteckt sich.\n\n"
            "![](figure:window)\n\n"
            "**Oben die Werkzeugleiste:** Neu, Öffnen, Speichern, *Modell "
            "einfügen* — und *Zeichnen*, das die Ansicht senkrecht auf die "
            "Zeichenebene schwenkt — das Modell bleibt stehen und tritt "
            "durchscheinend zurück. Escape kommt daraus zurück wie "
            "aus jedem anderen Werkzeug. Die Knöpfe tragen nur ihr Zeichen; "
            "der Name erscheint, sobald der Zeiger darauf stehen bleibt.\n\n"
            "**Unter dem Modell die Werkzeugzeile:** *Schnitt*, *Messen*, "
            "*Bewegen*, *Analyse*, *Schichten*, *Explosion*, *Trennen*, "
            "*Bemalen* — von links nach rechts auf Alt+1 bis Alt+8. Die "
            "meisten davon sehen nur hin; *Bewegen*, *Trennen* und *Bemalen* "
            "ändern das Modell wirklich, und alle drei tun es als Schritt im "
            "Verlauf.\n\n"
            "**Links** liegen Objektbaum, Parameter und Verlauf untereinander, "
            "jeder Abschnitt einklappbar. Der Objektbaum zeigt, was in der Szene "
            "steht; die Parameterliste die benannten Maße des Projekts; der "
            "Verlauf jeden Schritt, der zum aktuellen Stand geführt hat.\n\n"
            "**In der Mitte** das Modell. Linke Maustaste wählt aus, rechte oder "
            "mittlere dreht, Umschalt und Ziehen schiebt, das Mausrad zoomt "
            "dorthin, wo der Zeiger steht. Wer es aus einem anderen Programm "
            "anders gewohnt ist, stellt in den Einstellungen auf CAD- oder "
            "Blender-Belegung um.\n\n"
            "**Rechts** entweder der Chat oder der Prüfbericht — nie beides, "
            "weil beides gleichzeitig niemand liest. Entsteht eine Warnung, "
            "springt die Ansicht von selbst auf den Bericht. Ein Tastendruck "
            "blendet die ganze Spalte aus, dann ist das Modell im Vollbild.\n\n"
            "**Unten** die Statusleiste: Maße des Ausgewählten, Fortschritt einer "
            "laufenden Rechnung, offene Warnungen.\n\n"
            "**Es gibt keine Betriebsarten.** Kein Umschalten zwischen "
            "„Bearbeiten“ und „Konstruieren“, keine Werkbänke — es gibt einen "
            "Zustand, und das ist die Szene.\n\n"
            "**Wenn Sie etwas suchen, drücken Sie die Befehlspalette auf.** Sie "
            "findet jede Operation über ihren Namen und zeigt das Tastenkürzel "
            "gleich daneben. So lernt man die Kürzel nebenbei, statt sie "
            "auswendig zu lernen."
        ),
    ),
    Page(
        key="looking",
        summary=_(
            "Was der Prüfbericht meldet, was die Analysekarten zeigen, und wann "
            "man hinsehen sollte."
        ),
        title=_("Hinsehen, bevor gedruckt wird"),
        body=_(
            "Ein Modell sieht auf dem Bildschirm fast immer gut aus. Ob es sich "
            "drucken lässt, steht woanders — in der Wandstärke an der dünnsten "
            "Stelle, im Überhang über der Grenze, in der Insel, die in der Luft "
            "anfängt. Fünf Werkzeuge in der Leiste unter der Ansicht "
            "beantworten das, und keines davon ändert etwas am Modell.\n\n"
            "**Messen** (Werkzeugleiste, *Messen*) legt zwei Punkte fest und "
            "zeigt den Abstand. Der Zeiger fängt dabei auf Ecken und Kanten, "
            "man muss also nicht treffen, sondern nur in die Nähe kommen. Für "
            "die **Wandstärke** genügt ein Klick auf eine Fläche: Solidon "
            "schickt einen Strahl nach innen und misst, wo er wieder "
            "herauskommt. Eine gemessene Strecke bleibt als **Bemaßung** "
            "stehen, bis Sie sie wegnehmen — so lassen sich drei Maße "
            "nebeneinander vergleichen, statt sie sich zu merken.\n\n"
            "**Der Schnitt** (*Schnitt*) legt eine Ebene durch das Modell und "
            "zeigt, was dahinter liegt. Die Schnittfläche wird dabei "
            "geschlossen dargestellt, nicht als offenes Loch — ein Hohlraum "
            "ist damit als Hohlraum zu erkennen und nicht als Fehler in der "
            "Anzeige. Die Ebene lässt sich mit dem Regler durchziehen.\n\n"
            "**Die Analysekarten** (*Analyse*) färben das Modell nach einer "
            "Zahl ein. Sieben gibt es: **Wandstärke**, **Überhang**, "
            "**Stützbedarf** und **Krümmung** beantworten die Frage nach der "
            "Druckbarkeit. **Netzfehler** zeigt offene Kanten und Stellen, an "
            "denen mehr als zwei Flächen zusammenstoßen — dort sitzt fast "
            "immer die Ursache, wenn eine Verknüpfung scheitert. "
            "**Feature-Zuordnung** färbt, was die Erkennung aus dem Körper "
            "gemacht hat: welche Fläche als Bohrung gilt, welche als Tasche. "
            "**Passungen** zeigt, welche Flächen an einer Passung beteiligt "
            "sind und welche davon verletzt ist. Die Legende nennt immer den "
            "Zahlenbereich **und** die Herkunft der Werte — eine Karte ohne "
            "Maßstab ist ein hübsches Bild. Ein Klick auf eine Warnung im "
            "Prüfbericht fährt die Kamera an die Stelle.\n\n"
            "**Die Schichtvorschau** (*Schichten*) zeigt das Modell so, wie es "
            "in Schichten zerfällt. Der Regler fährt hindurch; was Sie sehen, "
            "ist Solidons eigene Schichtanalyse und **nicht** das, was der "
            "Slicer später rechnet. Beide Zahlenwelten bleiben getrennt "
            "ausgewiesen, damit niemand eine Schätzung für eine Messung hält.\n\n"
            "![](figure:layers)\n\n"
            "**Die Explosionsansicht** (*Explosion*) zieht mehrere Körper "
            "auseinander, damit man sieht, was ineinandergreift. Sie "
            "verschiebt nur die Anzeige — der Stapel und der Export bleiben "
            "unberührt.\n\n"
            "Keines dieser Werkzeuge erzeugt eine Operation. Sie sind eine "
            "Brille, kein Werkzeug: Sie können nichts damit kaputt machen, und "
            "ein Undo hat hier nichts zurückzunehmen."
        ),
    ),
    Page(
        key="moving",
        summary=_("Objekte verschieben, drehen, anordnen — und Flächen einem Filament zuweisen."),
        title=_("Bewegen und Bemalen"),
        body=_(
            "Zwei Werkzeuge derselben Leiste ändern das Modell wirklich: "
            "*Bewegen* und *Bemalen*. Beide halten das Versprechen des "
            "Verlaufs — jeder Zug und jeder Strich ist ein eigener Schritt, "
            "den Strg+Z einzeln zurücknimmt.\n\n"
            "**Bewegen** schaltet den Griff im Bild ein, das *Gizmo*: drei "
            "Pfeile zum Verschieben, drei Ringe zum Drehen, ein Würfel zum "
            "gleichmäßigen Skalieren — beschriftet mit X, Y, Z und S. Beim "
            "Loslassen steht der Zug als *Verschieben*, *Drehen* oder "
            "*Skalieren* im Verlauf, mit Zahlen, die sich dort nachträglich "
            "ändern lassen wie jede andere. **Rasterfang** und "
            "**Winkelfang** runden jeden Zug auf den eingestellten Schritt "
            "— ein Millimeter und fünfzehn Grad sind die Vorgabe, null "
            "heißt: kein Einrasten.\n\n"
            "**Während des Zugs steht die Zahl über dem Bild.** Wer sie "
            "genau will, tippt sie: die erste Ziffer übernimmt den Zug, die "
            "Eingabetaste wendet genau den getippten Wert an — ohne "
            "Einrasten, denn wer tippt, meint es exakt —, und Esc verwirft "
            "den Zug ganz.\n\n"
            "**Ist eine Fläche gewählt, sitzt der Griff auf der Fläche.** "
            "Ein Zug an ihr versetzt die Fläche in ihrer Richtung, und die "
            "Nachbarwände wachsen mit (*Fläche versetzen*) — aus dem "
            "20-mm-Klotz wird ein 25-mm-Klotz, keine verschobene Kiste. Was "
            "quer zur Fläche gezogen wird, verfällt: eine Fläche kennt nur "
            "vor und zurück.\n\n"
            "Der Würfel skaliert gleichmäßig — für ein genaues Zielmaß gibt "
            "es *Auf Maß bringen*, für achsweises Verzerren den Dialog von "
            "*Skalieren*. Und wer zwei Teile aneinandersetzen will, zieht "
            "nicht pixelgenau, sondern nimmt *An Merkmal ausrichten*: "
            "Fläche auf Fläche, Bohrung auf Bohrung.\n\n"
            "**Bemalen** macht Klicks zu Pinselstrichen. *Pinsel scharf* "
            "schalten, Slot und Radius wählen, auf das Modell klicken — das "
            "ändert Materialslots und damit das Modell, nicht bloß das "
            "Bild. Beim 3MF-Export wird daraus der Filamentwechsel für den "
            "Drucker. Der **Kantenwinkel** hält den Pinsel an Kanten an, "
            "damit eine Farbe nicht um die Ecke läuft; 180 Grad heißt: über "
            "alles hinweg.\n\n"
            "Beides sieht der Verlauf genauso wie einen Menüeintrag: "
            "dieselben Operationen, dasselbe Undo, dieselbe Möglichkeit, es "
            "sich anders zu überlegen."
        ),
    ),
    Page(
        key="sketch",
        summary=_("Zeichnen mit Zwängen: Linien, Bögen, Bedingungen, und was danach daraus wird."),
        title=_("Zeichnen"),
        body=_(
            "Für den Umriss, den kein Grundkörper hergibt. Ein Klotz mit einer "
            "Bohrung braucht keine Zeichnung — eine Grundplatte mit einer "
            "Aussparung, in die ein Netzteil passt, schon.\n\n"
            "**Angefangen wird oben in der Werkzeugleiste.** Das fünfte Zeichen "
            "von links ist *Zeichnen* — die Knöpfe dort tragen keine Beschriftung, "
            "ihr Name steht am Zeiger. Es schwenkt die Ansicht senkrecht auf die "
            "Zeichenebene: Gezeichnet wird im Modell und nicht daneben. Was daraus "
            "entsteht, entscheiden Sie am Ende — nicht vorher. Escape kommt wieder "
            "heraus, wie aus jedem anderen "
            "Werkzeug.\n\n"
            "![](figure:sketch-mode)\n\n"
            "**Zuerst die Ebene, dann die Linie.** *XY* liegt flach wie das "
            "Druckbett, *XZ* und *YZ* stehen. Ist ein Körper in der Szene, "
            "stehen dessen ebene Flächen mit in der Liste — dann zeichnen Sie "
            "direkt auf der Oberseite eines Teils. Der Satz neben der Wahl "
            "sagt, wie die Druckschichten dazu liegen: auf *XY* parallel zur "
            "Zeichnung, auf den stehenden Ebenen quer dazu — und quer heißt, "
            "dass eine waagerechte Linie im Bild später eine Fuge ist. Bei "
            "einer angeklickten Fläche entscheidet ihre Neigung, und der Satz "
            "nennt sie: liegend, quer oder schräg zur Schichtung.\n\n"
            "**Die Werkzeuge und ihre Tasten:** Linie `L`, Kreis `C`, Bogen "
            "`A`, Punkt `P`, Spline `S`, Trimmen `T`. `Esc` schaltet zurück "
            "aufs Auswählen und bricht ein angefangenes Element ab. Die Linie "
            "läuft als Zug weiter — das Ende ist der Anfang der nächsten. Ein "
            "Spline sammelt, bis Sie sagen, dass er fertig ist: Doppelklick, "
            "Eingabetaste, oder noch einmal auf den letzten Punkt klicken.\n\n"
            "**Fertige Umrisse liegen bereit.** Unter *Grundform*: Rechteck "
            "(`R`), Langloch, Kreis, Sechseck — und die beiden, die sonst Handarbeit "
            "wären, Lochkreis und Lochraster. Sie kommen als Zeichnung mit "
            "Bedingungen herein, nicht als Punkthaufen, und sind danach "
            "bemaßbar wie selbst Gezeichnetes.\n\n"
            "**Sehen, wählen, ziehen.** Das Mausrad zoomt, die mittlere "
            "Maustaste schiebt die Fläche — gedreht wird hier nichts, eine "
            "Skizze ist flach. *Einpassen* (`Pos1`) holt alles zurück ins "
            "Bild, und beim Öffnen ist es schon passiert: eine vorhandene "
            "Zeichnung füllt die Fläche, ein leeres Blatt zeigt den ganzen "
            "Bauraum. Mit *Auswählen* greift ein Zug an einem Punkt "
            "diesen Punkt und verschiebt ihn; der Solver zieht nach, was "
            "daran hängt. **Strg beim Klicken sammelt**, und das ist keine "
            "Feinheit: *Parallel* und *Rechtwinklig* brauchen zwei Linien, "
            "*Symmetrisch* zwei Punkte und eine Achse. Die Reihenfolge der "
            "Klicks zählt — „A parallel B“ ist nicht „B parallel A“. `Entf` "
            "löscht die Auswahl samt den Bedingungen, die an ihr hingen; "
            "liegt der Blick dagegen auf der Bedingungsliste, löscht `Entf` "
            "den Eintrag dort. Und `Strg+Z` gilt auch hier, für den letzten "
            "Zug auf dem Blatt und nicht für den letzten Schritt im "
            "Verlauf.\n\n"
            "**Ein Klick nahe einem vorhandenen Punkt fängt ihn.** Das ist "
            "mehr als Bequemlichkeit: die beiden Punkte bekommen eine "
            "*Deckung* und bleiben zusammen, auch wenn später etwas anderes "
            "wandert. Zwei Punkte, die nur zufällig dieselben Koordinaten "
            "haben, tun das nicht.\n\n"
            "**Und wo kein Punkt ist, fängt das Raster.** Die Linien im "
            "Hintergrund folgen dem Zoom: Sie stehen in der Folge 1, 2, 5 und "
            "werden gröber, sobald sie dichter als zwanzig Bildpunkte lägen — "
            "ein Raster, dessen Linien ineinanderlaufen, hilft niemandem. "
            "Steht *Am Raster fangen*, fällt jeder Klick auf die Weite, die "
            "gerade im Bild steht, und zwar auf die **nächste**; abgeschnitten "
            "läge jeder Punkt in dieselbe Richtung versetzt. Vorhandene Punkte "
            "gehen vor — wo einer in der Nähe liegt, gewinnt er, denn er "
            "bringt eine Deckung mit und das Raster nur eine runde Zahl.\n\n"
            "**Die Weite lässt sich festhalten.** Tippen Sie eine ein, bleibt "
            "sie stehen, gleich wie weit Sie zoomen; für ein Teil, das in "
            "Zweimillimeterschritten gedacht ist, ist das die halbe "
            "Konstruktion. Ganz heruntergedreht steht *Automatisch* im Feld, "
            "und die Weite folgt wieder dem Zoom.\n\n"
            "**Bemaßen, während man zeichnet.** Bei Linie und Kreis wird "
            "nach dem ersten Klick das Maßfeld in der Leiste scharf: Länge "
            "oder Durchmesser "
            "eintippen, Eingabetaste — die Richtung kommt vom Zeiger, die "
            "Zahl aus dem Feld, und sie bleibt als Bedingung stehen. "
            "Nachträglich geht dasselbe mit `D` über zwei ausgewählte Punkte, "
            "und dort darf ein Ausdruck stehen: `@breite/2` bindet das Maß an "
            "einen Projektparameter, statt es zu wiederholen.\n\n"
            "**Bedingungen halten die Zeichnung, nicht die Koordinaten.** "
            "Etwas auswählen, dann der Knopf — oder die rechte Maustaste am "
            "Ort. Es gibt zehn: Abstand, Deckung, Waagerecht, Senkrecht, "
            "Parallel, Rechtwinklig, Tangential, Symmetrisch, Fest und "
            "Referenzmaß, das mitmisst ohne zu halten. Was zur Auswahl nicht "
            "passt, ist ausgegraut. Rechts stehen alle in einer Liste; wer "
            "einen Eintrag überfährt, sieht die Punkte aufleuchten, die er "
            "hält, und `Entf` nimmt ihn weg.\n\n"
            "![](figure:sketch-editor)\n\n"
            "**Unten steht, wie fest die Zeichnung ist.** *Bestimmt* heißt, "
            "dass jede Zahl vergeben ist und nichts mehr wandert. „Vier "
            "Freiheitsgrade sind noch frei“ heißt, dass vier Dinge noch nicht "
            "festgelegt sind — die Skizze funktioniert trotzdem, sie ist nur "
            "noch verschiebbar. Widersprechen sich zwei Maße, sagt Solidon "
            "welche, und die letzte gültige Lage bleibt stehen: eine "
            "unmögliche Bedingung zerstört nicht das Gezeichnete.\n\n"
            "**Ändern, ohne neu zu zeichnen:** *Trimmen* schneidet die "
            "angeklickte Hälfte weg, *Verlängern* lässt sie wachsen, "
            "*Versetzen* (`O`) legt eine Kontur im Abstand daneben — negativ "
            "nach innen —, *Spiegeln* wirft die Auswahl an die X- oder "
            "Y-Achse. *Hilfsgeometrie* (`X`) macht aus einer Linie eine, die "
            "Bedingungen trägt, aber kein Profil bildet: die Mittellinie, an "
            "der etwas symmetrisch hängt, soll nicht mit extrudiert werden. "
            "Und *Projizieren* holt die Kanten der vorhandenen Körper auf "
            "dieser Ebene in die Zeichnung — der Weg, etwas an einem "
            "importierten Teil auszurichten, statt es abzumessen und "
            "abzutippen.\n\n"
            "**Der Rand des Bauraums ist eingezeichnet** — gestrichelt, mit "
            "seinem Maß daran, und wer darüber hinauszeichnet, liest es an "
            "derselben Linie: *die Skizze ragt darüber hinaus*. Die "
            "Zeichenfläche ist damit die früheste Stelle, an der auffällt, "
            "dass ein Teil nicht auf das Bett passt — früher als jeder "
            "Prüfbericht. Bei einem kleinen Teil liegt der Rahmen außerhalb "
            "des Bildes, und das ist Absicht: hineinpassen tut es ohnehin. "
            "Wird die Zeichnung größer als die Platte, kommt er von selbst "
            "mit ins Bild.\n\n"
            "![](figure:sketch-uses)\n\n"
            "**Zum Schluss fragt Solidon, was daraus wird.** Der Knopf "
            "*Fertig* zeigt die fünf Arten mit einem Satz dazu: "
            "extrudieren, als Tasche einschneiden, um die senkrechte Achse "
            "drehen, entlang eines Bogens führen, oder zwischen zwei "
            "Umrissen aufspannen. *Zurück zum Zeichnen* geht dort auch — es "
            "wirft nichts weg, sondern öffnet dieselbe Zeichnung wieder.\n\n"
            "![](figure:sketch-result)\n\n"
            "**Die Zeichnung ist danach ein Wert wie jeder andere.** Sie "
            "steht als Parameter der Operation im Verlauf, und ein "
            "Doppelklick auf den Schritt öffnet sie über *Zeichnen …* erneut. "
            "Eine Linie, die zwei Millimeter danebensitzt, wird verschoben — "
            "die Operation darüber rechnet neu, und der Rest des Projekts "
            "bleibt, wie er war.\n\n"
            "Die Umrisse gehen als exakte Kurven in den zweiten Rechenkern: "
            "ein gezeichneter Kreis wird ein runder Zylinder und kein "
            "Vieleck mit vielen Ecken."
        ),
    ),
    Page(
        key="ways",
        summary=_("Anpassen, konstruieren, erzeugen, formen — vier Wege in dieselbe Szene."),
        title=_("Die vier Wege"),
        body=_(
            "Fast jede Aufgabe geht einen von vier Wegen. Zu jedem liegt ein "
            "Beispielprojekt bereit — auf dem Startbildschirm, und jedes "
            "öffnet sich mit einer Tour: rechts steht Schritt für Schritt, "
            "was Sie ausprobieren sollten, und die Tour merkt selbst, wenn "
            "ein Schritt getan ist.\n\n"
            "![](figure:ways)\n\n"
            "**Weg 1 — ein fremdes Modell anpassen.** Etwas heruntergeladen, es "
            "passt fast: einlesen, reparieren, bohren, exportieren. Der "
            "häufigste Weg, und der, bei dem die Reparatur zählt.\n\n"
            "**Weg 2 — selbst konstruieren.** Aus Grundkörpern, Bausteinen und "
            "Zeichnungen etwas Neues, mit benannten Parametern: Breite, Tiefe, "
            "Stärke. Ändert sich eine Zahl, ändert sich das Teil. Was kein "
            "Grundkörper hergibt, wird gezeichnet — das Zeichen *Zeichnen* oben "
            "in der Werkzeugleiste, beschrieben im Kapitel davor.\n\n"
            "**Weg 3 — ein erzeugtes Modell aufbereiten.** Was ein Bildmodell "
            "liefert, ist eine Oberfläche und keine Konstruktion. Sie kommt "
            "durch die Reparaturkette, und Bohrungen entstehen danach als "
            "eigene Schritte — nicht dadurch, dass man das Netz vermisst.\n\n"
            "**Weg 4 — eine Figur formen.** Eine Form, die sich nicht bemaßen "
            "lässt: aus Grundkörpern grob zusammengesetzt, weich verschmolzen "
            "und dann von Hand geformt. Das eigene Kapitel dazu steht weiter "
            "unten; was ihn von den anderen dreien unterscheidet, ist, dass "
            "hier eine Geste zählt und keine Zahl."
        ),
    ),
    Page(
        key="sculpting",
        summary=_("Formen von Hand — und warum ein ganzer Vorgang ein Schritt bleibt."),
        title=_("Formen"),
        body=_(
            "Manche Formen lassen sich nicht bemaßen. Ein Griff, der in der Hand "
            "liegen soll, eine Figur, ein gewachsener Übergang — dafür gibt es "
            "den Pinsel.\n\n"
            "**Der Weg dorthin hat drei Stufen, und die erste wird gern "
            "übersprungen.** Erst eine grobe Form aus Grundkörpern, weich "
            "verschmolzen (*Weich verschmelzen* im Menü *Ändern*); dann "
            "*Dreiecke angleichen*, damit überall gleich viele Eckpunkte "
            "sitzen; dann *Formen*. Wer die zweite Stufe auslässt, malt auf "
            "einem Netz, das seinem Pinsel nicht folgen kann — die Leiste sagt "
            "es, sobald die Sitzung offen ist.\n\n"
            "**Die ganze Sitzung ist ein Schritt im Verlauf.** Nicht ein "
            "Schritt je Zug: Eine Figur sind mehrere tausend Züge, und ein "
            "Verlauf mit viertausend Einträgen ist keiner mehr. Strg+Z nimmt "
            "während der Sitzung einen Zug zurück, danach die ganze Sitzung.\n\n"
            "**Sechs Werkzeuge.** *Auftragen* und *Abtragen* sind dasselbe mit "
            "umgekehrtem Vorzeichen. *Glätten*, *Aufblasen* und *Flachziehen* "
            "lesen, was vor ihnen liegt, und kosten deshalb je einen "
            "zusätzlichen Durchgang — die Leiste zeigt, wie viele es sind. "
            "*Kneifen* zieht zur Strichmitte und macht Kanten.\n\n"
            "**Die Reihenfolge ist innerhalb einer Etappe egal.** Zwei Züge "
            "über dieselbe Stelle addieren sich auf die Ausgangsfläche, statt "
            "dass der zweite auf dem Ergebnis des ersten sitzt. Wer das nicht "
            "will, setzt *Neu ansetzen* — dann beginnt der nächste Zug auf dem, "
            "was da ist. Der Schalter gilt für einen Zug.\n\n"
            "**Symmetrie ist nachträglich änderbar.** Sie steht an der "
            "Operation und nicht am einzelnen Zug: Eine fertige Sitzung lässt "
            "sich damit spiegeln. Gespiegelt wird am Ursprung des Objekts — "
            "nicht an seinem Schwerpunkt, denn der wandert beim Formen.\n\n"
            "**Wann dieses Werkzeug nicht das richtige ist.** An einem Teil, "
            "das noch bemaßt wird: Ein Zug sitzt an einer Stelle im Raum, und "
            "wer die Form darunter ändert, zieht ihm die Fläche weg. Für einen "
            "Übergang zwischen zwei Körpern ist *Weich verschmelzen* besser — "
            "drei Zahlen statt hundert Zügen, und jederzeit änderbar. Und wer "
            "eine Porträtbüste modelliert, ist mit einem Programm besser "
            "bedient, das dafür gebaut ist; sechs Pinsel sind sechs Pinsel.\n\n"
            "**Was dieses Programm dafür kann und die anderen nicht:** Während "
            "Sie formen, läuft die Wandstärke mit. Zu dünne Stellen stehen als "
            "Zahl in der Leiste, bevor der Slicer sie findet."
        ),
    ),
    Page(
        key="history",
        summary=_("Warum jeder Schritt änderbar bleibt und was eine Transaktion zusammenhält."),
        title=_("Der Verlauf"),
        body=_(
            "Jede Operation steht im Verlauf, und dort bleibt sie änderbar. Das "
            "ist der Unterschied, an dem alles Weitere hängt: ein Modell ist hier "
            "nicht ein Netz aus Dreiecken, sondern die Liste der Schritte, aus "
            "denen es entstanden ist.\n\n"
            "![](figure:stack)\n\n"
            "**Doppelklick auf einen Schritt** öffnet ihn wieder — mit den "
            "Werten, die in der Datei stehen. Wer eine Bohrung zwei Millimeter "
            "versetzen will, ändert die Zahl; neu gerechnet wird nur, was "
            "darunter hängt.\n\n"
            "**Rückgängig nimmt eine ganze Transaktion zurück**, nicht einen "
            "halben Schritt. Ein Vorschlag des Chats ist genau eine Transaktion "
            "— ein Undo nimmt ihn vollständig zurück.\n\n"
            "Zwei Grenzen sind Absicht. Zurückgenommene Schritte fallen weg, "
            "sobald ein neuer kommt: es gibt keine Zweige. Und eine Änderung, "
            "die die *Anzahl* der Objekte ändert, während spätere Schritte damit "
            "arbeiten, wird abgelehnt — die neuen Körper sind nicht die alten, "
            "und ein Fehler am Ende über eine Zahl am Anfang ist einer, den "
            "niemand mehr zuordnen kann.\n\n"
            "**Anklicken setzt an.** Wer eine Fläche im Fenster auswählt und "
            "dann eine Operation aufruft, findet Ort und Achse schon "
            "eingetragen. Die Größe nicht: eine Senkung nimmt den Kopf der "
            "Schraube und nicht den Durchmesser der Bohrung, auf der sie sitzt."
        ),
    ),
    Page(
        key="parameters",
        summary=_("Benannte Maße statt Zahlen im Modell, mit Ausdrücken zwischen ihnen."),
        title=_("Parameter und Ausdrücke"),
        body=_(
            "Ein Projekt hat benannte Parameter — `breite`, `tiefe`, "
            "`wandstaerke` —, und Operationen dürfen mit ihnen rechnen statt "
            "mit festen Zahlen.\n\n"
            "**Warum das mehr ist als Bequemlichkeit.** Eine Zahl, die an "
            "sieben Stellen steht, ist sieben Zahlen: ändert man sie, ändert "
            "man sechs davon und übersieht die siebte. Ein Parameter ist eine "
            "Zahl an einer Stelle. Drehen Sie an `breite`, und alles, was "
            "davon abhängt, folgt in einem Zug — die Bohrung in der Mitte "
            "bleibt in der Mitte, weil dort `=@breite/2` steht und nicht "
            "„35“.\n\n"
            "**So legt man einen an.** Links unter *Parameter* auf "
            "*Parameter anlegen*, Name und Wert eintragen. Im Feld einer "
            "Operation schreiben Sie dann `=@breite` statt einer Zahl — das "
            "Gleichheitszeichen macht aus dem Feld einen Ausdruck, das "
            "Klammeraffen-Zeichen verweist auf einen Parameter.\n\n"
            "**Was in einem Ausdruck stehen darf:** die vier "
            "Grundrechenarten, Klammern, `min`, `max`, `abs`, `round` und "
            "Verweise auf andere Parameter. `=@breite/2 - @wand` ist "
            "erlaubt, `=max(@breite, 40)` auch.\n\n"
            "Nicht erlaubt ist alles andere, und das ist Absicht: der "
            "Ausdruck wird von einem eigenen Auswerter gerechnet, nicht von "
            "Python. **Eine Projektdatei ist eine Datei und kein Programm** — "
            "sie wandert als Fehlerbericht zwischen Leuten, und was darin "
            "steht, darf nichts ausführen. Daran ändert auch ein "
            "Sprachmodell nichts, das den Ausdruck geschrieben hat.\n\n"
            "**Ringschlüsse werden erkannt und benannt.** Wenn `a` auf `b` "
            "zeigt und `b` auf `a`, sagt Solidon das, statt bis zum "
            "Anschlag zu rechnen.\n\n"
            "Gerechnet wird durchgehend in Millimetern und doppelter "
            "Genauigkeit. Gerundet wird nur, was angezeigt wird — was Sie "
            "als „40,00 mm“ lesen, ist im Kern eine Zahl mit allen Stellen."
        ),
    ),
    Page(
        key="tolerances",
        summary=_(
            "Woher das Spiel kommt, das ein Deckel braucht — und warum es nicht geschätzt wird."
        ),
        title=_("Material, Toleranzen, Passungen"),
        body=_(
            "Das Stück, das Solidon von einem Slicer unterscheidet.\n\n"
            "Ein gedrucktes Teil ist nie so groß wie gezeichnet. Kunststoff "
            "schwindet beim Abkühlen, ein Loch von 5 mm kommt enger heraus, und "
            "die unterste Schicht wird breiter gedrückt als alle darüber. Wer "
            "zwei Teile ineinanderstecken will, muss das einrechnen — und genau "
            "das nimmt Solidon ab.\n\n"
            "**Das Spiel steht im Materialprofil, nicht im Modell.** Wer einen "
            "Stift in ein Loch stecken will, trägt keine 0,2 ein — er sagt "
            "*Passung*, und die Zahl kommt aus dem Profil des Materials, mit "
            "dem gedruckt wird.\n\n"
            "![](figure:fit)\n\n"
            "**Deshalb wirkt eine Kalibrierung rückwärts.** Unter *Bearbeiten → "
            "Material kalibrieren* wird der gemessene Wert eingetragen. Er gilt "
            "ab dann für jede Passung — auch für die in Projekten, die vorher "
            "entstanden sind.\n\n"
            "**Gemessen wird gedruckt, nicht geschätzt.** Der "
            "*Toleranz-Testkörper* bringt Zapfen und Bohrungen mit gestaffeltem "
            "Spiel auf eine Platte: einmal drucken, ausprobieren, Wert steht. "
            "Die *Wandstärkenleiter* und der *Überhangfächer* machen dasselbe "
            "für die Mindestwandstärke und den Winkel, ab dem dieser Drucker "
            "wirklich Stützen braucht — statt der Faustregel 45 Grad.\n\n"
            "![](figure:part-fit-ladder)\n\n"
            "**Die erste Schicht ist ein Sonderfall.** Sie wird gegen das Bett "
            "gedrückt und läuft dabei nach außen aus. Bei einer Passung, die "
            "unten am Teil sitzt, ist das der Unterschied zwischen „geht rein“ "
            "und „geht nicht rein“.\n\n"
            "![](figure:elephant-foot)\n\n"
            "**Das Prüfstück** schneidet einen Würfel um eine Stelle heraus, "
            "statt sie nachzubauen. Was gedruckt wird, ist die echte Geometrie "
            "mit der echten Toleranz: zwei Minuten statt zwei Stunden, und das "
            "Ergebnis gilt für das Teil.\n\n"
            "**Eine Szene darf mehrere Materialien haben.** Eine TPU-Dichtung "
            "in einem PETG-Gehäuse schwindet anders und will mehr Spiel. Mit "
            "*Material festlegen* bekommt der einzelne Körper sein eigenes "
            "Profil, und Toleranzen, Elefantenfuß und Passungsprüfung rechnen "
            "damit."
        ),
    ),
    Page(
        key="parts",
        summary=_("Geprüfte Verbindungen aus der Bibliothek statt selbst konstruierter Geometrie."),
        title=_("Die Bausteine"),
        body=_(
            "Ein Sechskant so tief in eine Wand zu legen, dass eine M4-Mutter "
            "hineinpasst und die Schraube trotzdem greift, ist eine halbe Stunde "
            "Arbeit — beim ersten Mal. Die Bausteinbibliothek nimmt sie ab: "
            "Baustein wählen, Größe wählen, auf die Fläche setzen.\n\n"
            "**Die Maße kommen aus einer Tabelle, nicht aus dem Gedächtnis.** "
            "Was ein M4-Sechskant für Schlüsselweite hat, wie tief eine "
            "Einpressbuchse sitzt, wie breit ein Filmscharnier sein darf — das "
            "ist nachgeschlagen und nicht geschätzt.\n\n"
            "**Mutternfalle** — die Tasche für eine Sechskantmutter, die beim "
            "Drucken eingelegt wird. Die häufigste Art, an einem gedruckten Teil "
            "ein belastbares Gewinde zu bekommen.\n\n"
            "![](figure:part-nut-trap)\n\n"
            "**Einpressbuchse** — die abgestufte Bohrung für eine "
            "Messingbuchse, die mit dem Lötkolben eingeschmolzen wird. "
            "Aufwendiger als die Mutternfalle, dafür beliebig oft lösbar.\n\n"
            "![](figure:part-heatset)\n\n"
            "**Rastnase** — der federnde Arm, der beim Fügen ausweicht und "
            "danach einrastet. Ein Deckel, der ohne Schraube hält.\n\n"
            "![](figure:part-snap-fit)\n\n"
            "**Filmscharnier** — eine Stelle, die so dünn ist, dass sie sich "
            "biegt, statt zu brechen. Das Gelenk wird mitgedruckt, es gibt "
            "nichts zu montieren.\n\n"
            "![](figure:part-hinge)\n\n"
            "**Lochwand-Einhänger** — ein bis sechs Haken auf einer "
            "gemeinsamen Rückplatte, im Raster einer SKÅDIS-Lochwand. Von "
            "oben in die Schlitze, dann herunterziehen: Die Nase greift "
            "hinter die Platte.\n\n"
            "**Scharnierauge** — eine Lasche mit Bohrung. Zwei davon und ein "
            "Passstift ergeben ein Gelenk, das sich dreht; das Filmscharnier "
            "darüber biegt sich. Ausdrücklich ein halbes Scharnier.\n\n"
            "**Eckwinkel** — das Dreieck in einer Innenecke, das zwei Wände "
            "im rechten Winkel hält. Für eine einzelne weiche Wand ist die "
            "Versteifungsrippe zuständig.\n\n"
            "**Standfuß** — ein gedruckter Fuß oder die Tasche für einen "
            "gekauften Gummifuß, je nach Wahl. Die Fase zeigt nach unten, "
            "damit der Elefantenfuß der ersten Schicht ins Leere quetscht.\n\n"
            "**Kabelclip** — der Bügel auf einer Fläche, dessen Öffnung "
            "enger ist als das Kabel. Er führt, hält aber nicht gegen Zug; "
            "dafür ist die Durchführung da.\n\n"
            "Dazu kommen Schraubenloch, Magnettasche, Kabeldurchführung, "
            "Rippe, Schlüsselloch, gedrucktes Gewinde, Nutfeder, Wandhalter "
            "und die Prüfkörper aus dem vorigen Kapitel. Der Katalog ordnet sie "
            "in Gruppen und zeigt zu jedem ein Bild — eine "
            "Bibliothek, die man nicht sieht, gibt es für den Benutzer nicht.\n\n"
            "![](figure:catalog)\n\n"
            "**Jeder Baustein bleibt änderbar wie jede andere Operation.** Er "
            "steht im Verlauf, seine Maße lassen sich später korrigieren, und "
            "die Stellen, an denen er ansetzt, behalten ihren Namen."
        ),
    ),
    Page(
        key="own-parts",
        summary=_("Ein selbst gebautes Teil so ablegen, dass es beim nächsten Mal fertig dasteht."),
        title=_("Eigene Bausteine"),
        body=_(
            "Der Halter für die Werkbank hat einen Abend gekostet. Beim "
            "nächsten Mal soll er ein Menüeintrag sein — mit einstellbarer "
            "Breite, weil das nächste Brett dicker ist.\n\n"
            "**Der Weg beginnt im Bausteinkatalog** (*Datei → Bausteinkatalog …*, "
            "Strg+K) und nicht im Bausteinmenü: Dort steht *Auswahl als Baustein "
            "speichern …*. Was Sie gebaut haben, wird "
            "damit zu einem Eintrag wie Mutternfalle oder Rastnase — mit "
            "Vorschaubild, mit Feldern zum Einstellen, und mit Stellen, an "
            "denen später etwas ausgerichtet werden kann.\n\n"
            "![](figure:own-part)\n\n"
            "**Vorher brauchen Sie Projektparameter.** Das ist die eine "
            "Bedingung, an der es sonst scheitert: Einstellbar wird genau, "
            "was im Projekt einen Namen hat. Wer die Breite seines Halters "
            "als feste Zahl in den Quader geschrieben hat, bekommt einen "
            "Baustein, der genau eine Breite kann. Legen Sie die Werte, die "
            "sich ändern sollen, vorher als Parameter an und binden Sie die "
            "Maße daran — das Kapitel *Parameter und Ausdrücke* zeigt, wie. "
            "Der Knopf im Katalog bleibt gesperrt, bis das erledigt ist, und "
            "sagt daneben, was ihm fehlt.\n\n"
            "**Der Dialog fragt fünf Dinge.** Einen Namen, unter dem der Baustein im "
            "Katalog steht. Eine Gruppe, in die er einsortiert wird. Eine "
            "Beschreibung, die in der Detailspalte des Katalogs steht. Zu jedem "
            "Parameter, ob er einstellbar sein soll — mit "
            "Beschriftung, Einheit, kleinstem und größtem Wert, Vorgabe und "
            "einem Satz, was passiert, wenn man ihn ändert. Und zu jedem "
            "erkannten Merkmal, ob man es später anklicken können soll: eine "
            "Bohrung, an der ein anderes Teil ausgerichtet wird, eine Fläche, "
            "auf die etwas gesetzt wird.\n\n"
            "**Beim Anlegen wird gerechnet, nicht nur gespeichert.** Der "
            "Baustein entsteht einmal an jeder Ecke des Bereichs, den Sie "
            "angegeben haben — kleinste Breite mit größter Höhe und so fort. "
            "Kommt dabei irgendwo kein brauchbarer Körper heraus, steht das "
            "am Eintrag im Katalog. Ein Baustein, der bei 8 mm zerfällt, ist "
            "besser vor dem ersten Einsetzen bekannt als danach.\n\n"
            "**Er gehört Ihnen und bleibt auf diesem Rechner.** Nichts wird "
            "hochgeladen, nichts wird geteilt. Im Katalog steht er mit einer "
            "Markierung neben den mitgelieferten. Wenn Sie ein Projekt "
            "weitergeben, in dem er verwendet wird, reist er als Rezept mit — "
            "als Liste von Schritten und Werten, nicht als Programm. Trägt "
            "Ihr Rechner schon einen Baustein desselben Namens, gewinnt "
            "Ihrer, und der mitgereiste bekommt einen eigenen.\n\n"
            "**Ändern heißt neu speichern.** Speichern Sie unter demselben "
            "Namen — der Knopf heißt dann *Baustein ersetzen*, und getauscht "
            "werden Datei, Katalogeintrag und Rechnung zusammen. Ein Rezept "
            "hat eine Fassung, die "
            "sich aus seinem Inhalt ergibt. Öffnen Sie später ein Projekt, das eine "
            "ältere benutzt hat, sagt es Ihnen das — die alte Fassung reist im "
            "Projekt mit und steht als eigener Eintrag im Katalog, und Sie "
            "entscheiden, welche gilt. Ändert sich nichts, sagt auch "
            "niemand etwas."
        ),
    ),
    Page(
        key="printing",
        summary=_("Vom fertigen Modell zur Übergabe an den Slicer."),
        title=_("Auf das Bett und hinaus"),
        body=_(
            "**Auf dem Bett anordnen** legt die Objekte nebeneinander und "
            "beginnt eine neue Platte, sobald die aktuelle voll ist. Was auch "
            "dann nicht passt, wird nicht weggelassen, sondern gemeldet.\n\n"
            "**Zu groß für das Bett?** *Trennen* schneidet dort, wo man "
            "hinzeigt; *Automatisch teilen* schneidet, bis jedes "
            "Stück passt. Die Trennebene wird gesucht und nicht geraten, in jede "
            "Schnittfläche kommen zwei Passstifte, und jeder Schnitt bleibt eine "
            "Zahl, die man danach ändern kann.\n\n"
            "![](figure:split)\n\n"
            "**Was schräg nach außen wächst, braucht irgendwann Stützen.** Wie "
            "schräg, hängt am Drucker und nicht an einer Faustregel — deshalb "
            "misst der Überhangfächer es aus.\n\n"
            "![](figure:overhang)\n\n"
            "**Zu dünne Wände drucken nicht.** Weniger als zwei Bahnen "
            "nebeneinander trägt nichts und reißt, sobald man die Stützen "
            "abmacht.\n\n"
            "![](figure:wall)\n\n"
            "**Exportiert wird nach STL, 3MF oder STEP.** 3MF ist, was Slicer "
            "bevorzugen, und es trägt die Materialslots als Farbgruppen mit; STL "
            "kennt keine Farbe und verliert sie folgerichtig. STEP gibt es für "
            "exakte Körper, mit echten Flächen und Kanten.\n\n"
            "**Zum Herzeigen gibt es GLB.** Nicht zum Drucken — dafür kennt es "
            "keine Einheit —, sondern zum Verschicken: Farben und Name reisen "
            "mit, und der Empfänger dreht das Teil im Browser, ohne irgendetwas "
            "zu installieren.\n\n"
            "**Der Slicer bleibt außen.** Die Schichtanalyse sucht und bewertet "
            "— Inseln, Spannweiten, dünne Stellen, die beste Lage —, aber die "
            "Druckdatei schreibt der Slicer. Wo beide Zahlen nennen, wird immer "
            "ausgewiesen, welche woher kommt.\n\n"
            "![](figure:layers)"
        ),
    ),
    Page(
        key="splitting",
        summary=_("Teilen, verstiften und anordnen, wenn der Bauraum nicht reicht."),
        title=_("Wenn das Teil nicht auf das Bett passt"),
        body=_(
            "Ein Bauraum ist endlich, und das Teil, das man braucht, ist es "
            "manchmal nicht. Dann wird geteilt — und die Frage ist nicht *ob*, "
            "sondern *wo* und *wie die Hälften wieder zusammenkommen*.\n\n"
            "**Der kürzeste Weg** ist das Werkzeug *Trennen* unten in der "
            "Werkzeugzeile (Alt+7). Zwei Klicks auf das Teil ziehen eine "
            "Linie, und getrennt wird zwischen ihnen — gerade in den "
            "Bildschirm hinein. Wer sieht, wo die Naht hingehört, muss diese "
            "Stelle damit nicht mehr in eine Koordinate übersetzen. Der "
            "Haken *Zum Zusammenstecken vorbereiten* steht dabei von Anfang "
            "an: Stifte in die eine Hälfte, die passenden Löcher in die "
            "andere. Daneben steht, womit sie halten:\n\n"
            "* **Rund** druckt am saubersten und braucht zwei Stück, sonst "
            "lassen sich die Hälften gegeneinander verdrehen.\n"
            "* **Sechskant** hält schon einzeln gegen Verdrehen.\n"
            "* **Schwalbenschwanz** hält zusätzlich gegen Auseinanderziehen "
            "quer zur Naht — er ist hinten schmaler als vorn.\n"
            "* **Schnapper** rastet ein: ein Federarm in der einen Hälfte, "
            "eine Tasche mit Rastkante in der anderen. Er hält ohne Kleber, "
            "und man bekommt die Hälften auch wieder auseinander. Dafür "
            "braucht er Platz — die Naht muss mindestens 5,4 mm hergeben, "
            "sonst wäre der Arm zu kurz zum Federn. Ist sie schmaler, werden "
            "es runde Stifte, und der Prüfbericht sagt warum.\n\n"
            "**Vorbereiten → Automatisch teilen** nimmt auch die Suche ab. Die "
            "Trennebene wird gesucht, nicht geraten: über dieselbe "
            "Schichtanalyse wie die Orientierungssuche, und bewertet werden "
            "drei Dinge. Eine Naht, die aus **einer** Kontur besteht, ist "
            "besser als eine, die in fünf dünne Stege zerfällt. Ein "
            "prismatischer Verlauf — der Querschnitt ändert sich über einen "
            "Millimeter kaum — klebt sich sauberer als eine Schräge. Und die "
            "Hälften sollen ähnlich groß sein. Die Konturzahl wiegt am "
            "schwersten: eine Naht in mehreren Stegen ist schlimmer als jede "
            "Unwucht.\n\n"
            "![](figure:split)\n\n"
            "**In jede Schnittfläche kommen zwei Passstifte.** Ihr "
            "Durchmesser kommt aus der Fläche, ihr Spiel aus dem kalibrierten "
            "Materialprofil — nicht aus einer geratenen Zahl. Zu jedem Stift "
            "entsteht ein Passungspaar, und das wird bei jeder Auswertung "
            "geprüft. Zwei Stifte statt einem, damit sich die Hälften nicht "
            "gegeneinander verdrehen lassen.\n\n"
            "**Jeder Schnitt ist eine eigene Operation.** Die Trennebene "
            "bleibt damit eine Zahl, die man nachträglich verschieben kann, "
            "und ein Undo nimmt einen Schnitt zurück statt der ganzen "
            "Teilung.\n\n"
            "**Der Schieber „Explosion“** unter der Ansicht zieht die Teile "
            "zum Ansehen auseinander — er verschiebt nur die Anzeige. Was der "
            "Stapel sagt und was exportiert wird, bleibt, wo es ist.\n\n"
            "Wer die Ebene lieber eintippt als zeigt, nimmt *Vorbereiten → "
            "Teilen* und trägt Achse und Position ein. "
            "Dieselbe Operation, nur ohne die Suche davor; null Stifte heißt "
            "dort: nur schneiden.\n\n"
            "**Wie die Hälften heißen, sagt, welche welche ist.** Nach dem "
            "Verstiften stehen im Objektbaum „… A · Stifte“ und "
            "„… B · Löcher“ — beim Export ist der Dateiname die einzige "
            "Auskunft darüber, welches der beiden Teile man gerade in der "
            "Hand hat."
        ),
    ),
    Page(
        key="variants",
        summary=_("Mehrere Maße nebeneinander drucken und den gemessenen Wert übernehmen."),
        title=_("Ausprobieren statt raten: Varianten und Kalibrieren"),
        body=_(
            "Die Zahl, die über eine Passung entscheidet, ist das Spiel — und "
            "sie hängt am Drucker, am Material und an der Düse. Geraten wird "
            "sie einmal; danach misst man sie.\n\n"
            "**Der Weg dorthin ist ein Prüfstück.** Unter *Bausteine → "
            "Toleranz-Testkörper* entsteht eine Reihe von Zapfen und "
            "Bohrungen mit abgestuftem Spiel — vorgegeben sind vier Stufen "
            "von 0,10 mm an, je 0,05 mm weiter, also bis 0,25 mm. Beides "
            "lässt sich im Dialog ändern, wenn der Bereich nicht trifft. "
            "Einmal drucken, durchprobieren, den Wert merken, der saugend "
            "passt.\n\n"
            "![](figure:part-fit-ladder)\n\n"
            "**Dieser Wert gehört ins Materialprofil**, nicht ins Modell: "
            "*Bearbeiten → Material kalibrieren*. Weil jede Toleranz im "
            "Programm ein **Verweis** ist und keine Zahl, rechnet danach auch "
            "ein Teil damit, das vor der Kalibrierung entstanden ist. Ein "
            "Deckel von letzter Woche passt nach dem Eintrag besser, ohne "
            "dass ihn jemand anfasst.\n\n"
            "Dasselbe gibt es für Wandstärken (*Wandstärkenleiter*) und "
            "Überhänge (*Überhangfächer*) — die zwei anderen Zahlen, die man "
            "sonst schätzt.\n\n"
            "**Wenn eine Zahl nicht am Material hängt, sondern am Teil**, "
            "hilft der Variantengenerator: *Ändern → Varianten erzeugen* "
            "dreht einen Projektparameter durch einen Bereich und legt die "
            "Ausführungen nebeneinander. Fünf Griffdurchmesser auf einer "
            "Platte, ein Druck, eine Entscheidung. Der Stapel bleibt dabei "
            "unberührt — die Varianten sind eine Ausgabe, keine Änderung am "
            "Projekt."
        ),
    ),
    Page(
        key="chat",
        summary=_("Wie man mit dem Agenten spricht, was er sieht und was ein Vorschlag kostet."),
        title=_("Der Chat"),
        body=_(
            "Der Chat ruft dieselben Operationen auf, die auch in den Menüs "
            "stehen — er ist eine zweite Hand am selben Werkzeug und kein "
            "zweiter Weg an ihm vorbei.\n\n"
            "Daraus folgen zwei Dinge. **Jeder Vorschlag ist genau eine "
            "Transaktion**: ein Undo nimmt ihn vollständig zurück, nie halb. Und "
            "**der Chat rechnet keine Geometrie** — er wählt Operationen und "
            "Werte, gerechnet wird im Programm.\n\n"
            "**Der Ablauf ist immer derselbe.** Sie schreiben, was Sie "
            "wollen. Der Chat antwortet mit einem Vorschlag — einer Liste von "
            "Operationen, noch nicht ausgeführt. Die Ansicht zeigt in "
            "Blau und Orange, was dazukäme und was verschwände. Erst *Übernehmen* "
            "trägt ihn in den Verlauf ein; *Verwerfen* lässt nichts zurück.\n\n"
            "**Vier Regeln hat er mitbekommen**, und sie stehen nicht zur "
            "Verhandlung: Bausteine vor selbst gebauten Formen, eine Op-Liste "
            "vor OpenSCAD-Quelltext, benannte Parameter vor eingetippten "
            "Zahlen — und **fragen vor raten**. Wenn Ihre Anfrage zwei "
            "Lesarten hat, kommt eine Rückfrage und kein Ergebnis.\n\n"
            "**Was er sieht**, ist nicht der rohe Verlauf, sondern ein "
            "Steckbrief: Maße, erkannte Merkmale, Projektparameter, die "
            "aktuelle Auswahl, der Prüfbericht. Ein zurückgenommener Beitrag "
            "gilt als verworfen — nach einem Undo argumentiert er nicht mehr "
            "mit einem Zustand, den es nicht mehr gibt.\n\n"
            "**An jeder Transaktion steht, woher sie kommt** (§26.4): Modell, "
            "Version des Systemprompts, Version der Regelsammlung. Wer in "
            "einem halben Jahr wissen will, warum eine Bohrung dort sitzt, "
            "findet die Antwort im Verlauf.\n\n"
            "Er braucht ein Modell: entweder einen eigenen Schlüssel "
            "(*Bearbeiten → Chat einrichten*, abgelegt im "
            "Schlüsselbund des Systems, nie in der Projektdatei) oder ein "
            "lokales Ollama. Für die Werkzeugaufrufe muss es groß genug sein; "
            "unter 7B scheitern sie reproduzierbar.\n\n"
            "Alles andere in Solidon kommt ohne Sprachmodell aus. Ohne "
            "Schlüssel ist der Chat ausgegraut und sagt in einem Satz warum — "
            "mehr passiert nicht."
        ),
    ),
    Page(
        key="generating",
        summary=_(
            "Aus Text oder Bild ein Netz — und was danach nötig ist, damit es druckbar wird."
        ),
        title=_("Ein Modell erzeugen lassen"),
        body=_(
            "Der dritte Weg (§2.2): Sie beschreiben ein Teil oder legen ein "
            "Bild hin, und ein Generator macht daraus ein Netz. **Datei → "
            "Modell erzeugen.**\n\n"
            "Gerechnet wird das nicht in Solidon, sondern in einem lokalen "
            "**ComfyUI** auf Port 8188. Läuft keines, bleibt der Eintrag "
            "ausgegraut und sagt warum; alles andere funktioniert weiter. "
            "Welche Knoten benutzt werden, steht in zwei Dateien neben dem "
            "Programm — wer einen anderen Generator hat, tauscht die Datei "
            "und nicht den Quelltext.\n\n"
            "**Was zurückkommt, ist eine Oberfläche und keine Konstruktion.** "
            "Das ist der wichtigste Satz zu diesem Weg. Ein erzeugtes Netz "
            "hat keine Bohrungen, keine Passungen und oft keine "
            "Wasserdichtheit — es hat eine Form. Bohrungen und Passungen "
            "entstehen **danach** als eigene Operationen, nicht dadurch, dass "
            "man das Netz vermisst.\n\n"
            "**Die Modelle gehören nicht uns, und ihre Lizenzen auch "
            "nicht.** Welches Modell ComfyUI benutzt, entscheiden Sie — "
            "Solidon liefert keines mit. Der mitgelieferte Ablauf setzt auf "
            "**TripoSG**, dessen MIT-Lizenz hier nichts offenlässt; das "
            "verbreitetere Hunyuan3D ist für die Europäische Union "
            "ausdrücklich **nicht** lizenziert. Der Ablauf nennt Rollen und "
            "keine Dateinamen: ein anderes Modell einzusetzen heißt, es zu "
            "installieren, sonst nichts.\n\n"
            "**Das Erzeugte wird eine Quelle, keine Operation.** Ein "
            "Generator ist keine Funktion: dieselbe Anfrage liefert nach "
            "einem Modellwechsel etwas anderes. Die Bytes liegen deshalb im "
            "Projekt wie eine hineingezogene Datei, und der Stapel darüber "
            "ist der gewöhnliche — *Laden*, dann *Reparieren*. Anfrage und "
            "Startwert stehen in der Quelle, damit die Datei sagt, woher die "
            "Geometrie stammt.\n\n"
            "**Die Reparaturkette läuft ohne Nachfrage**, aber als eigener "
            "Schritt: sichtbar im Verlauf, sichtbar im Bericht, "
            "zurücknehmbar. Erzeugte Netze sind selten geschlossen, und was "
            "sie brauchen, ist immer dasselbe — Löcher schließen, Punkte "
            "verschweißen, Normalen richten.\n\n"
            "Derselbe Startwert liefert dasselbe Ergebnis, soweit das Modell "
            "auf der anderen Seite das zulässt. Er steht im Dialog und wird "
            "mitgespeichert."
        ),
    ),
    Page(
        key="extras",
        summary=_(
            "Die vier Programme, die Solidon benutzen kann — was jedes bringt, und "
            "was nach dem Installieren noch zu tun ist."
        ),
        title=_("Zusätzliche Programme einrichten"),
        body=_(
            "**Keines davon ist Pflicht.** Ohne alle vier läuft der ganze "
            "Kernweg: Modell einlesen, ändern, prüfen, exportieren. Was fehlt, "
            "sind einzelne Funktionen — und welche, sagt diese Seite.\n\n"
            "Die Liste steht unter **Hilfe → Zusätzliche Programme**. Jede Zeile "
            "nennt den Zweck, den Zustand und den Ort; wo Solidon selbst "
            "installieren kann, steht dort ein Knopf. Installiert wird nur, "
            "wenn jemand ihn drückt.\n\n"
            "Auf Windows läuft das über **winget**, auf macOS über **Homebrew**, "
            "auf Linux über **Flatpak** — und immer ohne Administratorrechte. "
            "Fehlt die Paketverwaltung, steht der Befehl zum Kopieren daneben "
            "und die Seite des Herstellers dazu.\n\n"
            "**Wo etwas an einer ungewöhnlichen Stelle liegt**, hilft *Ort "
            "angeben …*: eine portable Installation auf einem zweiten Laufwerk "
            "findet kein Suchverfahren, und diese Angabe gewinnt danach immer.\n\n"
            "## OpenSCAD\n\n"
            "Die Rückfallebene für Formen, für die es keinen Baustein gibt. Wird "
            "nur aufgerufen, nie mitgeliefert, und jeder Quelltext davor "
            "geprüft. Fehlt es, sagt die betroffene Operation das und schlägt "
            "einen Baustein vor.\n\n"
            "## Der Slicer\n\n"
            "Für die Druckdatei und die Gegenprobe aus dem G-Code. Erkannt wird "
            "jeder der üblichen — PrusaSlicer, OrcaSlicer, ElegooSlicer, "
            "BambuStudio, Cura. Solidon liest auch sein Druckerprofil aus und "
            "schlägt beim ersten Start den Drucker vor, den der Slicer zuletzt "
            "hatte.\n\n"
            "## Ollama — für den Chat ohne eigenen Schlüssel\n\n"
            "**Hier sind es drei Schritte, und der erste ist der kleinste.** "
            "Installiert bringt Ollama kein Modell mit und läuft nicht "
            "zwangsläufig — beides erledigt *Bearbeiten → Chat einrichten*:\n\n"
            "1. **Läuft es?** Der Dialog sagt es in einem Satz. Steht dort "
            "„installiert, läuft aber nicht“, startet ein Knopf es. Läuft es auf "
            "einem anderen Rechner, gehört seine Adresse in die Liste der "
            "zusätzlichen Programme.\n"
            "2. **Ein Modell holen.** Die Auswahl nennt, was installiert ist, "
            "und darunter die bewährten mit ihrer Größe. *Modell holen* lädt es "
            "— fünf bis neun Gigabyte, mit Fortschritt und Abbrechen. Ein "
            "abgebrochener Download setzt beim nächsten Versuch fort.\n"
            "3. **Werkzeuge prüfen.** Der wichtigste Schritt, und er beantwortet "
            "zwei Fragen. Ob ein Modell Werkzeuge wirklich aufruft, sagt weder "
            "seine Größe noch sein Anbieter — die Probe macht einen echten Zug. "
            "Sagt sie „schreibt seine Aufrufe als Text“, antwortet der Chat "
            "zwar, führt aber nichts aus; dann hilft ein anderes Modell.\n\n"
            "Und sie misst, **wie schnell dieser Rechner es tut**. Ollama "
            "benutzt nur bestimmte Grafikkarten; bei allen anderen rechnet es "
            "auf dem Prozessor, und das ist keine andere Geschwindigkeit, "
            "sondern eine andere Größenordnung — gemessen auf einem Rechner mit "
            "Intel-Arc-Grafik knapp acht Token je Sekunde beim Einlesen. Der "
            "Auftrag von Solidon ist rund 19 000 Token lang; es dauert dort "
            "**einundvierzig Minuten**, bis eine Antwort überhaupt beginnt. "
            "Steht das in der Probe, ist es keine Störung, sondern die "
            "Auskunft: Auf diesem Rechner lohnt der lokale Weg nicht, und ein "
            "kleineres Modell ändert daran wenig.\n\n"
            "Es gibt einen zweiten lokalen Weg, und Solidon richtet ihn nicht "
            "ein: Für Intel-Grafik gibt es **IPEX-LLM**, für AMD **ROCm**, für "
            "beides **OpenVINO** — jedes davon ist eine eigene Installation mit "
            "eigenen Fallen, und keines wird von Ollama selbst angeboten. Wer "
            "sich darauf einlässt, bekommt seine Karte genutzt; wer nicht, nimmt "
            "einen Schlüssel für ein gehostetes Modell. Beides ist vertretbar, "
            "und alles außer dem Chat läuft ohne beides.\n\n"
            "Bewährt hat sich **qwen3:14b**: vier von fünf Werkzeugaufrufen "
            "getroffen, und dafür braucht es eine Grafikkarte mit 16 GB. "
            "Kleinere Modelle sind schneller und treffen seltener; unter sieben "
            "Milliarden Parametern scheitern die Aufrufe reproduzierbar.\n\n"
            "Ein lokales Modell ist langsamer und ungenauer als ein gehostetes. "
            "Für kurze Anweisungen reicht es; für lange Züge lohnt ein eigener "
            "Schlüssel, und der liegt dann im Schlüsselbund des Systems.\n\n"
            "## ComfyUI — für das Erzeugen aus Text oder Bild\n\n"
            "**Auch hier ist installiert erst die Hälfte.** ComfyUI braucht die "
            "Knoten, die der Ablauf anspricht, und das Modell, das sie laden. "
            "Beides legt Solidon selbst hinein: in der Liste der zusätzlichen "
            "Programme steht in der Zeile von ComfyUI *Knoten und Modell "
            "einrichten …*.\n\n"
            "**Der kurze Weg führt über den Erzeugungsdialog selbst.** *Datei → "
            "Modell erzeugen* sagt, wie weit der Generator ist, und "
            "unterscheidet drei Lagen: es läuft keiner, es läuft einer ohne die "
            "Knoten, oder alles ist bereit. In der Mitte steht der Knopf zur "
            "Einrichtung direkt daneben — man muss nicht erst erzeugen lassen, "
            "um zu erfahren, dass etwas fehlt.\n\n"
            "Der Dialog findet ComfyUI selbst. Die **Desktop-Version** von "
            "comfy.org muss er dabei nicht raten — sie trägt ein, wohin sie "
            "installiert hat, auch bei einem selbst gewählten Ordner. Die "
            "tragbare Version entpacken Sie selbst; steht sie an einer "
            "ungewöhnlichen Stelle, gehört der Ordner angegeben — gesucht wird "
            "der, in dem `custom_nodes` und `main.py` liegen.\n\n"
            "Dann laufen fünf Schritte: Knoten hinlegen, den TripoSG-Quelltext "
            "holen, zwei Stellen darin richten, die fehlenden Pakete nachziehen "
            "— und **nachsehen, ob ComfyUI die Knoten laden kann**. Der letzte "
            "kostet zwei Sekunden und ist der, der zählt: Ohne ihn meldete die "
            "Einrichtung „fertig“, und der Fehler kam erst beim Erzeugen. Auf "
            "Wunsch danach das Modell, rund 7,5 GB — bricht die Verbindung ab, "
            "setzt ein neuer Lauf dort fort, wo er stand.\n\n"
            "**Danach ComfyUI einmal neu starten.** Es liest seine Knoten beim "
            "Start; ohne den Neustart bleibt *Modell erzeugen* ausgegraut, "
            "obwohl alles an seinem Platz liegt.\n\n"
            "Für den Weg über **Text** kommt ein SDXL-Modell unter "
            "`models/checkpoints` dazu — das ist ComfyUIs eigene Sache. Für den "
            "Weg über ein **Bild** wird keines gebraucht.\n\n"
            "**Wie lange es dauert, entscheidet die Grafikkarte.** Auf einer "
            "RTX 4080 sind es dreizehn Sekunden je Körper; auf einer "
            "Intel-Arc-Grafik ohne CUDA gemessene zwei Minuten. Beides "
            "funktioniert, und Solidon wartet, solange ComfyUI rechnet — was "
            "abbricht, ist ein Fehler und keine Langsamkeit, und dann steht der "
            "Satz von ComfyUI im Dialog.\n\n"
            "## Und das, was mitkommt\n\n"
            "OpenCASCADE für exakte Kanten und V-HACD für den Hinweis, wo ein "
            "Körper von selbst auseinanderfällt, liegen im Installationspaket "
            "bei. Wer Solidon aus den Quellen fährt, findet sie in derselben "
            "Liste und installiert sie von dort."
        ),
    ),
    Page(
        key="surfaces",
        summary=_("Muster als echte Geometrie, Gitterfüllungen und ausgehöhlte Körper."),
        title=_("Oberflächen und Füllungen"),
        body=_(
            "Ein Rändel für den Griff, eine Wabe fürs Aussehen, ein Gitter "
            "statt massiven Materials — beides ist echte Geometrie, keine "
            "Textur im Bild. Was der Slicer bekommt, ist das, was Sie "
            "sehen.\n\n"
            "**Acht Muster stehen zur Wahl** — Rippe, Welle, Rändel gerade und "
            "gekreuzt, Wabe, Noppen, Voronoi und Rauschen. Rändel gibt Griff, "
            "Wabe und Rippe sind Zierde, Voronoi und Rauschen verstecken die "
            "Schichtlinien. Im Dialog steht neben der Auswahl eine Vorschau, "
            "gezeichnet aus denselben Umrissen, die danach gedruckt "
            "werden.\n\n"
            "![](figure:textures)\n\n"
            "**Textur aufbringen** prägt ein Muster auf eine Fläche, erhaben "
            "oder vertieft. Zwei Zahlen entscheiden, ob es druckbar ist: die "
            "Teilung muss breiter sein als zwei Bahnen der Düse, die Tiefe "
            "höher als eine Schicht. Beides prüft Solidon, bevor es rechnet "
            "— eine Prägung, die feiner ist als der Drucker, verschwindet, und "
            "das merkt man sonst erst am fertigen Teil.\n\n"
            "![](figure:texture)\n\n"
            "Auf einem runden Teil wird das Muster **umlaufend** aufgelegt. "
            "Flach aufgelegt träfe das Feld den Zylinder nur in seiner Mitte "
            "und stünde an den Rändern in der Luft.\n\n"
            "**Gitter füllen** ersetzt das Innere eines Körpers durch eine "
            "Struktur — Gyroid, Wabe oder Würfelgitter. Das ist nicht "
            "dasselbe wie die Füllung des Slicers: diese hier gehört zum "
            "Modell, reist mit der Datei und lässt sich messen. Die Wandstärke "
            "der Struktur wird gegen die Düse geprüft, so wie bei der "
            "Textur."
        ),
    ),
    Page(
        key="remote",
        summary=_(
            "Ein anderes Programm bedient diese Installation — lokal, abschaltbar, rücknehmbar."
        ),
        title=_("Fernsteuerung"),
        body=_(
            "Ein anderes Programm auf demselben Rechner darf Solidon "
            "bedienen — über MCP, dieselbe Schnittstelle, mit der Claude Code "
            "und ähnliche Werkzeuge arbeiten. Es ruft dabei genau die "
            "Operationen auf, die auch in den Menüs stehen.\n\n"
            "**Sie ist aus, bis Sie sie einschalten.** Der Schalter steht in "
            "den Einstellungen, zusammen mit dem Port. Danach hört Solidon "
            "auf `127.0.0.1` und nur dort: von einem anderen Rechner ist die "
            "Schnittstelle nicht erreichbar, auch nicht aus dem eigenen "
            "Netz.\n\n"
            "Was hereinkommt, ist eine Transaktion wie jede andere. Ein "
            "Strg+Z im Fenster nimmt sie zurück, der Verlauf zeigt sie, und "
            "am Eintrag steht, dass sie von außen kam.\n\n"
            "Zwei Dinge gehen nicht durch die Leitung, und das ist Absicht: "
            "OpenSCAD-Quelltext und alles, was wie ein Dateipfad aussieht. "
            "Beides würde bedeuten, dass ein fremdes Programm bestimmt, was "
            "auf diesem Rechner ausgeführt oder gelesen wird.\n\n"
            "In der Gegenstelle wird sie als Server mit der Adresse "
            "`http://127.0.0.1:8787/mcp` eingetragen.\n\n"
            "**Welche Werkzeuge es gibt, steht in diesem Handbuch.** Jede "
            "Operation der folgenden Kapitel ist eines — mit denselben "
            "Parametern, denselben Grenzen und denselben Vorgaben, die auch "
            "der Dialog zeigt. Eine eigene Schnittstellenliste gibt es "
            "deshalb nicht: sie wäre eine zweite Version derselben Auskunft "
            "und sagte nach dem zweiten Monat etwas anderes."
        ),
    ),
    Page(
        key="trouble",
        summary=_("Die häufigsten Fälle am Anfang, mit dem, was dahintersteckt."),
        title=_("Wenn etwas nicht geht"),
        body=_(
            "Die Fälle, die am Anfang am häufigsten sind — was dahintersteckt "
            "und was hilft.\n\n"
            "**„Das Modell ist nicht geschlossen.“**\n"
            "In der Datei fehlen Flächen, oder Dreiecke liegen verkehrt herum. "
            "Bei heruntergeladenen Modellen ist das normal. *Reparieren* im "
            "Prüfbericht schließt kleine Löcher und dreht Flächen um. Fehlt eine "
            "ganze Wand, kann das keine Reparatur erraten — dann ist die Datei "
            "kaputt und eine andere Quelle der kürzere Weg.\n\n"
            "**Eine Verknüpfung schlägt fehl oder frisst zu viel.**\n"
            "Boolesche Operationen brauchen saubere Eingangskörper. Solidon "
            "versucht es der Reihe nach mit mehreren Verfahren und sagt "
            "hinterher, welches getragen hat. Steht dort *voxel*, wurde grob "
            "gerechnet und Genauigkeit ist verloren gegangen — dann erst "
            "reparieren, dann noch einmal verknüpfen.\n\n"
            "**Zwei Flächen liegen genau aufeinander.**\n"
            "Der klassische Fall, in dem eine Differenz nichts wegnimmt oder "
            "Flimmern entsteht. Abhilfe: den abzuziehenden Körper einen "
            "Hundertstelmillimeter überstehen lassen. Die Bausteine machen das "
            "von sich aus.\n\n"
            "**Das Teil passt nicht auf das Bett.**\n"
            "*Automatisch teilen* schneidet es, bis jedes Stück passt, und setzt "
            "Passstifte in die Schnittflächen. Steht im Druckerprofil ein "
            "falscher Bauraum, ist das die eigentliche Ursache — nachsehen lohnt "
            "sich.\n\n"
            "**Die Passung sitzt zu stramm oder zu locker.**\n"
            "Nicht am Modell ändern, sondern messen: den Toleranz-Testkörper "
            "drucken, ausprobieren und den Wert unter *Material kalibrieren* "
            "eintragen. Er gilt danach für jede Passung, auch für die in schon "
            "gebauten Projekten.\n\n"
            "**Ein Schritt lässt sich nicht mehr ändern.**\n"
            "Wenn eine Änderung die Anzahl der Objekte ändern würde, während "
            "spätere Schritte mit diesen Objekten arbeiten, hält die Auswertung "
            "an. Das ist Absicht: die neuen Körper sind nicht die alten, und ein "
            "stillschweigend woanders gelandeter Schritt wäre schlimmer als eine "
            "Meldung. Die späteren Schritte zurücknehmen, ändern, neu aufbauen.\n\n"
            "**Verrundung, Fase oder STEP sind ausgegraut.**\n"
            "Diese Operationen brauchen den zweiten Konstruktionskern mit echten "
            "Kanten. Er ist eine zusätzliche Installation. Ohne ihn läuft alles "
            "andere unverändert weiter.\n\n"
            "**Der Chat antwortet nicht.**\n"
            "Er braucht ein Sprachmodell — einen eigenen Schlüssel oder ein "
            "lokales Ollama. Kleine Modelle unter etwa sieben Milliarden "
            "Parametern scheitern an den Werkzeugaufrufen, und zwar "
            "zuverlässig. Alles außer dem Chat funktioniert ohne.\n\n"
            "**Alles ist zäh.**\n"
            "Beim Arbeiten läuft die Entwurfsqualität; die feine Rechnung "
            "kommt erst beim Export. Bei sehr großen Netzen hilft es, früh zu "
            "vereinfachen — die Dreieckszahl steht im Objektbaum.\n\n"
            "**Grundsätzlich gilt:** Kein Fehler in Solidon endet bei der "
            "Feststellung. Steht keine Handlung dabei, mit der es weitergeht, "
            "ist das ein Fehler in Solidon und einen Bericht wert. Der Weg "
            "dahin ist *Hilfe → Rückmeldung senden*: Bildschirmfoto, "
            "Protokoll und auf Wunsch die laufende Sitzung gehen mit, die "
            "Vorschau zeigt vorher alles, und ein Knopf schickt es an den "
            "Support. Wer nichts aus der Hand geben möchte, legt im selben "
            "Dialog stattdessen einen Ordner auf dem eigenen Rechner ab.\n\n"
            "**Während der Demo fragt Solidon von selbst.** Nach einer halben "
            "Stunde Arbeit — gezählt werden nur Minuten, in denen Sie etwas "
            "getan haben — legt sich eine Karte über die Ansicht und fragt, "
            "wie es läuft. Sie hält nichts an und wartet, bis Sie hinsehen. "
            "*Rückmeldung geben* öffnet denselben Dialog wie *Hilfe → "
            "Rückmeldung senden*, mit drei Feldern darin: wie gut Sie "
            "zurechtkommen, was gut funktioniert hat, was gefehlt hat. Kein "
            "Feld ist Pflicht, die Vorschau zeigt vorher alles, und ohne Ihren "
            "Klick geht nichts hinaus. *Nein danke* gilt dauerhaft; wer die "
            "Karte einfach stehen lässt, sieht sie höchstens dreimal."
        ),
    ),
    Page(
        key="glossary",
        summary=_("Die Begriffe, die in Menüs und Meldungen vorkommen, kurz erklärt."),
        title=_("Wörterbuch"),
        body=_(
            "Die Wörter, die in Solidon, in Slicern und in Druckforen "
            "vorkommen — kurz erklärt.\n\n"
            "**Netz (Mesh)** — ein Körper als Hülle aus Dreiecken. STL und OBJ "
            "enthalten nichts anderes: keine Kreise, keine Maße, nur Dreiecke.\n\n"
            "**Geschlossen (wasserdicht)** — die Hülle hat kein Loch, innen und "
            "außen sind eindeutig. Nur ein geschlossener Körper lässt sich "
            "zuverlässig verknüpfen und drucken.\n\n"
            "**Operation** — ein Arbeitsschritt: bohren, verrunden, teilen, "
            "einen Baustein setzen. In Solidon entsteht Geometrie nur so.\n\n"
            "**Transaktion** — alles, was ein Rückgängig auf einmal zurücknimmt. "
            "Ein Vorschlag des Chats ist genau eine, auch wenn er aus fünf "
            "Operationen besteht.\n\n"
            "**Parameter** — ein benanntes Maß des Projekts, etwa `breite`. "
            "Operationen dürfen damit rechnen; ändert sich der Wert, ändert sich "
            "alles, was daran hängt.\n\n"
            "**Baustein** — ein fertiges Konstruktionselement aus der "
            "Bibliothek, mit Maßen aus einer Tabelle statt aus dem Gedächtnis.\n\n"
            "**Passung** — wie stramm zwei Teile ineinandersitzen. Das nötige "
            "Spiel kommt aus dem Materialprofil.\n\n"
            "**Spiel** — der Abstand zwischen Zapfen und Loch, damit sich beides "
            "fügen lässt. Zu wenig klemmt, zu viel wackelt.\n\n"
            "**Presspassung** — Übermaß statt Spiel: das Teil wird eingepresst "
            "und hält von selbst.\n\n"
            "**Toleranz** — der Betrag, um den ein Maß absichtlich vom Nennmaß "
            "abweicht, damit das gedruckte Ergebnis stimmt.\n\n"
            "**Schwund** — Kunststoff zieht sich beim Abkühlen zusammen. "
            "Deshalb ist ein gedrucktes Teil etwas kleiner als gezeichnet.\n\n"
            "**Elefantenfuß** — die unterste Schicht wird gegen das Bett "
            "gedrückt und läuft nach außen aus. Das Teil ist unten breiter als "
            "geplant.\n\n"
            "**Überhang** — eine Fläche, die schräg nach außen wächst. Ab einem "
            "gewissen Winkel hat die Schicht darunter nichts mehr, worauf sie "
            "sich legen kann.\n\n"
            "**Stützen** — mitgedrucktes Material unter einem Überhang, das "
            "hinterher abgebrochen wird.\n\n"
            "**Insel** — ein Bereich einer Schicht, unter dem nichts ist. Ohne "
            "Stütze druckt der Drucker dort in die Luft.\n\n"
            "**Brücke (Spannweite)** — ein waagerechter Steg zwischen zwei "
            "Stützpunkten. Kurze Brücken gelingen ohne Stütze, lange hängen "
            "durch.\n\n"
            "**Düse** — die Öffnung, durch die der Kunststoff austritt, "
            "üblicherweise 0,4 mm. Sie begrenzt, wie fein ein Detail sein kann.\n\n"
            "**Extrusionsbreite** — wie breit eine gelegte Bahn wird. Zwei "
            "Bahnen nebeneinander sind die dünnste sinnvolle Wand.\n\n"
            "**Schichthöhe** — wie dick eine Lage ist, meist 0,2 mm. Kleiner "
            "heißt feiner und langsamer.\n\n"
            "**Slicer** — das Programm, das aus dem Modell die Druckdatei "
            "macht. Solidon ist keiner und ersetzt keinen.\n\n"
            "**G-Code** — die fertige Anweisungsliste für den Drucker. Sie "
            "kommt aus dem Slicer.\n\n"
            "**STL** — das verbreitetste Format: nur Dreiecke, keine Einheit, "
            "keine Farbe.\n\n"
            "**3MF** — der moderne Nachfolger: mit Einheit, Farben und mehreren "
            "Objekten in einer Datei. Wo der Slicer es kann, ist es die bessere "
            "Wahl.\n\n"
            "**STEP** — ein Format mit echten Flächen und Kanten statt "
            "Dreiecken. Das, was klassische CAD-Programme austauschen.\n\n"
            "**GLB** — das Format der Betrachter: Dreiecke mit Farben, in einer "
            "einzigen Datei, die jeder Browser öffnet. Zum Zeigen gedacht, "
            "nicht zum Drucken.\n\n"
            "**Prüfbericht** — die Liste dessen, was an der Szene auffällt, "
            "jeweils mit einer Handlung, die es behebt.\n\n"
            "**Materialslot** — die Zuordnung einer Fläche zu einem Material "
            "oder einer Farbe beim Mehrfarbendruck."
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
        f"{_('Version')}: {collection.version}",
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
                "wann eine Wand zu dünn ist — zwei Extrusionsbahnen sind die Grenze."
            )
        )
    )
    lines.append("")
    lines.append(
        f"| {_('Drucker')} | {_('Bauraum')} | {_('Düse')} | {_('Schichthöhe')} "
        f"| {_('Extrusionsbreite')} | {_('geschlossen')} |"
    )
    lines.append("|---|---|---|---|---|---|")
    for printer in printer_profiles().values():
        x, y, z = printer.build_volume
        enclosed = _("ja") if printer.enclosed else _("nein")
        lines.append(
            f"| {printer.title} | {x:.0f} × {y:.0f} × {z:.0f} "
            f"| {decimal(printer.nozzle_diameter, 2)} "
            f"| {decimal(printer.layer_height, 2)} | {decimal(printer.extrusion_width, 2)} "
            f"| {enclosed} |"
        )
    lines.append("")

    lines.append(f"### {_('Normteile')}")
    lines.append("")
    lines.append(
        str(
            _(
                "Woher die Maße kommen, wenn ein Baustein ein Schraubenloch oder eine "
                "Mutternfalle setzt. Nichts davon wird geschätzt."
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
                "Jeder Eintrag hier ist dieselbe Operation, die auch im Menü steht, mit "
                "denselben Parametern. Was hereinkommt, wird eine Transaktion wie jede "
                "andere: Der Verlauf zeigt sie, ein Strg+Z nimmt sie zurück."
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

    from app.core import errors

    # Die Hierarchie ist die Wahrheit, ``vars(errors)`` nur ihr Stammmodul:
    # OpenSCAD, Sprachmodell, Mesh-Erzeugung, Lizenzschlüssel und die
    # Analysekarten deklarieren ihre Ausnahmen in eigenen Modulen —
    # ausgerechnet die, die ein Nutzer am ehesten sieht und nachschlägt,
    # fehlten in der Tabelle, obwohl der Satz darüber Vollständigkeit
    # verspricht. Der Import füllt die Hierarchie, bevor sie abgelaufen wird.
    for module in (
        "app.core.backends.openscad",
        "app.core.backends.llm",
        "app.core.backends.mesh",
        "app.core.activation.key",
        "app.core.perceive.maps",
    ):
        importlib.import_module(module)

    def walk(kind: type[errors.AppError]) -> list[type[errors.AppError]]:
        found: list[type[errors.AppError]] = []
        for child in kind.__subclasses__():
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


def knowledge_pages() -> tuple[Page, ...]:
    """Die zwei Seiten, die zeigen, *wonach* gerechnet wird.

    Bis hierher stand im Handbuch, was die Anwendung tut, und in den Tabellen
    unter ``knowledge/data/``, mit welchen Werten sie es tut — sichtbar war nur
    das Ergebnis. Wer wissen wollte, ab wann eine Wand als zu dünn gilt oder
    welches Spiel PETG bekommt, fand es nirgends.

    Erzeugt und nicht geschrieben, aus demselben Grund wie die Referenz: Eine
    zweite Liste veraltet. Ändert jemand eine Toleranz, ändert sich diese Seite
    mit — sonst stünde hier eine Zahl, nach der niemand mehr rechnet.
    """

    def titled(title: object, body: str) -> str:
        # Die Überschrift gehört in den Text, wie bei den Kategorie-Seiten:
        # daran erkennt der Ankersetzer das Kapitel, und das Verzeichnis
        # springt hin, statt ins Leere zu zeigen.
        return f"## {title}\n\n{body}"

    rules_title = _("Wonach Solidon urteilt")
    profiles_title = _("Material, Drucker, Normteile")
    remote_title = _("Die Werkzeuge der Fernsteuerung")
    messages_title = _("Meldungen im Wortlaut")
    return (
        Page(
            key="rules",
            title=rules_title,
            body=titled(rules_title, rules_text()),
            generated=True,
        ),
        Page(
            key="profiles",
            title=profiles_title,
            body=titled(profiles_title, profiles_text()),
            generated=True,
        ),
        Page(
            key="remote-tools",
            title=remote_title,
            body=titled(remote_title, remote_text()),
            generated=True,
        ),
        Page(
            key="messages",
            title=messages_title,
            body=titled(messages_title, messages_text()),
            generated=True,
        ),
    )


def pages(registry: Registry | None = None) -> tuple[Page, ...]:
    """Alle Seiten: erst die geschriebenen, dann das Wissen, dann eine je
    Kategorie."""
    source = registry or REGISTRY
    generated = tuple(
        Page(
            key=category,
            title=CATEGORIES[category],
            body=documentation(source, category=category),
            generated=True,
        )
        for category in source.by_category()
    )
    return INTRODUCTION + knowledge_pages() + generated


def find(key: str, registry: Registry | None = None) -> Page | None:
    """Eine Seite beim Namen — für den Weg von einer Operation in ihr Kapitel."""
    for page in pages(registry):
        if page.key == key:
            return page
    return None


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

    ``with_figures`` behält die Bildverweise, wie sie im Text stehen — das
    braucht, wer daraus HTML oder ein PDF macht. Ohne das tritt an jede Stelle
    der Alt-Text der Abbildung: eine Textausgabe, in der plötzlich eine Aussage
    fehlt, weil sie im Bild stand, wäre eine unvollständige.
    """
    parts = []
    for page in pages(registry):
        # Über ``Page.text`` und nicht über ``page.body``: Die Kurzfassung
        # gehört zur Seite, und das Handbuchfenster liest dieselbe Methode.
        text = page.text() if with_figures else without_figures(page.text())
        parts.append(titled(page, text))
    return "\n\n".join(parts).rstrip() + "\n"


def as_html(
    registry: Registry | None = None,
    *,
    figure_source: Callable[[str], str] | None = None,
    dark_source: Callable[[str], str] | None = None,
) -> str:
    """Das ganze Handbuch als HTML-Rumpf — für die Website und für das PDF.

    ``figure_source`` sagt, unter welcher Adresse eine Abbildung zu finden ist;
    wer nichts liefert, bekommt an ihrer Stelle den Alt-Text. Wo die Datei
    liegt, entscheidet damit der Aufrufer und nicht der Kern — hier soll keine
    Ablagestruktur festgeschrieben werden.

    ``dark_source`` beantwortet dieselbe Frage für ein dunkles Farbschema. Wer
    für einen Schlüssel nichts liefert, bekommt dort ein gewöhnliches Bild —
    ein Bildschirmfoto hat keine zweite Version, eine Zeichnung schon.
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

    return to_html(as_markdown(registry, with_figures=True), resolve)


def without_figures(body: str) -> str:
    """Bildverweise durch ihren Alt-Text ersetzen."""
    from app.core import figures

    def describe(match: re.Match[str]) -> str:
        figure = figures.find(match.group(1))
        return f"*{_('Abbildung')}: {figure.alt}*" if figure else ""

    return FIGURE_PATTERN.sub(describe, body)
