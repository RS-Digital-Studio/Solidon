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

    def figures(self) -> tuple[str, ...]:
        """Die Schlüssel der Abbildungen, in der Reihenfolge ihres Auftretens."""
        return tuple(FIGURE_PATTERN.findall(str(self.body)))


#: Ein Bildverweis im Fließtext einer Seite.
FIGURE_PATTERN: Final = re.compile(r"!\[\]\(figure:([a-z0-9-]+)\)")


#: Die geschriebenen Seiten, in der Reihenfolge, in der sie jemand liest.
INTRODUCTION: Final[tuple[Page, ...]] = (
    Page(
        key="what",
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
            "Konto, keine Telemetrie, nichts, was den Rechner verlässt.\n\n"
            "Ohne Netz, ohne Konto und ohne Sprachmodell bleibt alles außer dem "
            "Chat benutzbar."
        ),
    ),
    Page(
        key="start",
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
            "**3. In den Prüfbericht schauen.** Rechts steht, was mit dem Modell "
            "nicht stimmt. Löcher, doppelte Flächen, verkehrt herum liegende "
            "Dreiecke — bei heruntergeladenen Modellen ist das die Regel, nicht "
            "die Ausnahme. Jeder Befund hat eine Schaltfläche, die ihn behebt.\n\n"
            "![](figure:report)\n\n"
            "**4. Reparieren.** Meist genügt die vorgeschlagene Handlung im "
            "Bericht. Das Modell bleibt dabei, was es war — die Reparatur ist ein "
            "Schritt im Verlauf und lässt sich zurücknehmen.\n\n"
            "![](figure:main-window)\n\n"
            "**5. Die Fläche anklicken, in die das Loch soll.** Sie hebt sich "
            "hervor. Ein Rechtsklick zeigt genau die Operationen, die auf diese "
            "Fläche passen — bei einer ebenen Fläche zum Beispiel *Bohrung "
            "setzen*.\n\n"
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
        title=_("Das Fenster"),
        body=_(
            "Drei Zonen, und keine davon versteckt sich.\n\n"
            "![](figure:window)\n\n"
            "**Oben die Werkzeugleiste:** Neu, Öffnen, Speichern, *Modell "
            "einfügen* — und *Zeichnen*, das die Mitte zur Zeichenfläche "
            "macht, solange gezeichnet wird. Escape kommt daraus zurück wie "
            "aus jedem anderen Werkzeug.\n\n"
            "**Unter dem Modell die Werkzeugzeile:** *Schnitt*, *Messen*, "
            "*Bewegen*, *Analyse*, *Schichten*, *Explosion*, *Bemalen*. Die "
            "meisten davon sehen nur hin; *Bewegen* und *Bemalen* ändern das "
            "Modell wirklich, und beide tun es als Schritt im Verlauf.\n\n"
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
        title=_("Zeichnen"),
        body=_(
            "Für den Umriss, den kein Grundkörper hergibt. Ein Klotz mit einer "
            "Bohrung braucht keine Zeichnung — eine Grundplatte mit einer "
            "Aussparung, in die ein Netzteil passt, schon.\n\n"
            "**Angefangen wird oben in der Werkzeugleiste.** Der Knopf "
            "*Zeichnen* macht die Mitte des Fensters zur Zeichenfläche, und was daraus "
            "entsteht, entscheiden Sie am Ende — nicht vorher. Escape kommt "
            "wieder heraus, wie aus jedem anderen Werkzeug.\n\n"
            "![](figure:sketch-mode)\n\n"
            "**Zuerst die Ebene, dann die Linie.** *XY* liegt flach wie die "
            "Druckplatte, *XZ* und *YZ* stehen. Ist ein Körper in der Szene, "
            "stehen dessen ebene Flächen mit in der Liste — dann zeichnen Sie "
            "direkt auf der Oberseite eines Teils. Der Satz neben der Wahl "
            "sagt, wie die Druckschichten dazu liegen: auf *XY* parallel zur "
            "Zeichnung, sonst quer — und quer heißt, dass eine waagerechte "
            "Linie im Bild später eine Fuge ist.\n\n"
            "**Die Werkzeuge und ihre Tasten:** Linie `L`, Kreis `C`, Bogen "
            "`A`, Punkt `P`, Spline `S`, Trimmen `T`. `Esc` schaltet zurück "
            "aufs Auswählen und bricht ein angefangenes Element ab. Die Linie "
            "läuft als Zug weiter — das Ende ist der Anfang der nächsten. Ein "
            "Spline sammelt, bis ein Doppelklick oder die Eingabetaste ihn "
            "schließt.\n\n"
            "**Fertige Umrisse liegen bereit.** Unter *Grundform*: Rechteck "
            "(`R`), Langloch, Kreis, Sechseck — und die beiden, die sonst Handarbeit "
            "wären, Lochkreis und Lochraster. Sie kommen als Zeichnung mit "
            "Bedingungen herein, nicht als Punkthaufen, und sind danach "
            "bemaßbar wie selbst Gezeichnetes.\n\n"
            "**Ein Klick nahe einem vorhandenen Punkt fängt ihn.** Das ist "
            "mehr als Bequemlichkeit: die beiden Punkte bekommen eine "
            "*Deckung* und bleiben zusammen, auch wenn später etwas anderes "
            "wandert. Zwei Punkte, die nur zufällig dieselben Koordinaten "
            "haben, tun das nicht.\n\n"
            "**Bemaßen, während man zeichnet.** Nach dem ersten Klick steht "
            "das Maßfeld in der Leiste bereit: Länge oder Durchmesser "
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
            "**Der Rand des Bauraums ist eingezeichnet.** Die Zeichenfläche "
            "ist die früheste Stelle, an der auffällt, dass ein Teil nicht "
            "auf die Platte passt — früher als jeder Prüfbericht.\n\n"
            "![](figure:sketch-uses)\n\n"
            "**Zum Schluss fragt Solidon, was daraus wird.** Der Knopf "
            "*Fertig* zeigt die fünf Arten mit einem Satz dazu: "
            "extrudieren, als Tasche einschneiden, um die senkrechte Achse "
            "drehen, entlang eines Bogens führen, oder zwischen zwei "
            "Umrissen aufspannen. *Zurück zum Zeichnen* geht dort auch — es "
            "wirft nichts weg, sondern öffnet dieselbe Zeichnung wieder.\n\n"
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
        title=_("Die drei Wege"),
        body=_(
            "Fast jede Aufgabe geht einen von drei Wegen. Zu jedem liegt ein "
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
            "Grundkörper hergibt, wird gezeichnet — der Knopf *Zeichnen* oben "
            "in der Werkzeugleiste, beschrieben im Kapitel davor.\n\n"
            "**Weg 3 — ein erzeugtes Modell aufbereiten.** Was ein Bildmodell "
            "liefert, ist eine Oberfläche und keine Konstruktion. Sie kommt "
            "durch die Reparaturkette, und Bohrungen entstehen danach als "
            "eigene Schritte — nicht dadurch, dass man das Netz vermisst."
        ),
    ),
    Page(
        key="history",
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
            "Dazu kommen Schraubenloch, Magnettasche, Kabeldurchführung, "
            "Rippe, Schlüsselloch, gedrucktes Gewinde und die Prüfkörper aus "
            "dem vorigen Kapitel. Der Katalog zeigt zu jedem ein Bild — eine "
            "Bibliothek, die man nicht sieht, gibt es für den Benutzer nicht.\n\n"
            "![](figure:catalog)\n\n"
            "**Jeder Baustein bleibt änderbar wie jede andere Operation.** Er "
            "steht im Verlauf, seine Maße lassen sich später korrigieren, und "
            "die Stellen, an denen er ansetzt, behalten ihren Namen."
        ),
    ),
    Page(
        key="printing",
        title=_("Auf die Platte und hinaus"),
        body=_(
            "**Auf dem Bett anordnen** legt die Objekte nebeneinander und "
            "beginnt eine neue Platte, sobald die aktuelle voll ist. Was auch "
            "dann nicht passt, wird nicht weggelassen, sondern gemeldet.\n\n"
            "**Zu groß für das Bett?** *Automatisch teilen* schneidet, bis jedes "
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
            "**Der Slicer bleibt außen.** Die Schichtanalyse sucht und bewertet "
            "— Inseln, Spannweiten, dünne Stellen, die beste Lage —, aber die "
            "Druckdatei schreibt der Slicer. Wo beide Zahlen nennen, wird immer "
            "ausgewiesen, welche woher kommt.\n\n"
            "![](figure:layers)"
        ),
    ),
    Page(
        key="splitting",
        title=_("Wenn das Teil nicht auf die Platte passt"),
        body=_(
            "Ein Bauraum ist endlich, und das Teil, das man braucht, ist es "
            "manchmal nicht. Dann wird geteilt — und die Frage ist nicht *ob*, "
            "sondern *wo* und *wie die Hälften wieder zusammenkommen*.\n\n"
            "**Bearbeiten → Automatisch teilen** nimmt beides ab. Die "
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
            "Wer die Ebene selbst legen will, nimmt *Ändern → Teilen und "
            "verstiften* und trägt Achse und Position ein. Dieselbe Operation, "
            "nur ohne die Suche davor."
        ),
    ),
    Page(
        key="variants",
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
            "(*Bearbeiten → Zugang zum Sprachmodell*, abgelegt im "
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
        key="surfaces",
        title=_("Oberflächen und Füllungen"),
        body=_(
            "Ein Rändel für den Griff, eine Wabe fürs Aussehen, ein Gitter "
            "statt massiven Materials — beides ist echte Geometrie, keine "
            "Textur im Bild. Was der Slicer bekommt, ist das, was Sie "
            "sehen.\n\n"
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
            "`http://127.0.0.1:8787/mcp` eingetragen."
        ),
    ),
    Page(
        key="trouble",
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
            "ist das ein Fehler in Solidon und einen Bericht wert."
        ),
    ),
    Page(
        key="glossary",
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
            "**Prüfbericht** — die Liste dessen, was an der Szene auffällt, "
            "jeweils mit einer Handlung, die es behebt.\n\n"
            "**Materialslot** — die Zuordnung einer Fläche zu einem Material "
            "oder einer Farbe beim Mehrfarbendruck."
        ),
    ),
)


def pages(registry: Registry | None = None) -> tuple[Page, ...]:
    """Alle Seiten: erst die geschriebenen, dann eine je Kategorie."""
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
    return INTRODUCTION + generated


def find(key: str, registry: Registry | None = None) -> Page | None:
    """Eine Seite beim Namen — für den Weg von einer Operation in ihr Kapitel."""
    for page in pages(registry):
        if page.key == key:
            return page
    return None


def as_markdown(registry: Registry | None = None, *, with_figures: bool = False) -> str:
    """Das ganze Handbuch am Stück, für die Kommandozeile und zum Nachlesen.

    ``with_figures`` behält die Bildverweise, wie sie im Text stehen — das
    braucht, wer daraus HTML oder ein PDF macht. Ohne das tritt an jede Stelle
    der Alt-Text der Abbildung: eine Textausgabe, in der plötzlich eine Aussage
    fehlt, weil sie im Bild stand, wäre eine unvollständige.
    """
    parts = []
    for page in pages(registry):
        body = str(page.body) if with_figures else without_figures(str(page.body))
        parts.append(body if page.generated else f"## {page.title}\n\n{body}")
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
    ein Bildschirmfoto hat keine zweite Fassung, eine Zeichnung schon.
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
