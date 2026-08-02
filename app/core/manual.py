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
        title=_("Was Formwerk ist"),
        body=_(
            "Formwerk baut, ändert und druckreif macht — Modelle für den "
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
            "aus dem Slicer, Formwerk sucht und bewertet nur. Keine Cloud — kein "
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
            "— die Maße lassen sich später ändern. Überspringen geht auch, dann "
            "gelten Vorgaben.\n\n"
            "![](figure:start-screen)\n\n"
            "**2. Eine Datei auf das Fenster ziehen.** STL, 3MF, STEP, OBJ. Ist "
            "in der Datei keine Einheit vermerkt — bei STL nie —, fragt Formwerk "
            "nach, statt zu raten. Im Zweifel Millimeter: fast alles im Netz ist "
            "in Millimetern.\n\n"
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
        key="ways",
        title=_("Die drei Wege"),
        body=_(
            "Fast jede Aufgabe geht einen von drei Wegen. Zu jedem liegt ein "
            "Beispielprojekt bereit — auf dem Startbildschirm, zum Öffnen und "
            "Nachsehen.\n\n"
            "![](figure:ways)\n\n"
            "**Weg 1 — ein fremdes Modell anpassen.** Etwas heruntergeladen, es "
            "passt fast: einlesen, reparieren, bohren, exportieren. Der "
            "häufigste Weg, und der, bei dem die Reparatur zählt.\n\n"
            "**Weg 2 — selbst konstruieren.** Aus Grundkörpern und Bausteinen "
            "etwas Neues, mit benannten Parametern: Breite, Tiefe, Stärke. "
            "Ändert sich eine Zahl, ändert sich das Teil.\n\n"
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
            "Erlaubt sind die vier Grundrechenarten, Klammern, `min`, `max`, "
            "`abs`, `round` und Verweise auf andere Parameter. Nicht erlaubt ist "
            "alles andere: der Ausdruck wird von einem eigenen Auswerter "
            "gerechnet, nicht von Python. Eine Projektdatei ist eine Datei und "
            "kein Programm, und daran ändert auch ein Sprachmodell nichts.\n\n"
            "Ringschlüsse werden erkannt und benannt, statt bis zum Anschlag zu "
            "rechnen.\n\n"
            "Gerechnet wird durchgehend in Millimetern und doppelter "
            "Genauigkeit. Gerundet wird nur, was angezeigt wird."
        ),
    ),
    Page(
        key="tolerances",
        title=_("Material, Toleranzen, Passungen"),
        body=_(
            "Das Stück, das Formwerk von einem Slicer unterscheidet.\n\n"
            "Ein gedrucktes Teil ist nie so groß wie gezeichnet. Kunststoff "
            "schwindet beim Abkühlen, ein Loch von 5 mm kommt enger heraus, und "
            "die unterste Schicht wird breiter gedrückt als alle darüber. Wer "
            "zwei Teile ineinanderstecken will, muss das einrechnen — und genau "
            "das nimmt Formwerk ab.\n\n"
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
            "Er braucht ein Modell: entweder einen eigenen Schlüssel oder ein "
            "lokales Ollama. Für die Werkzeugaufrufe muss es groß genug sein; "
            "unter 7B scheitern sie reproduzierbar.\n\n"
            "Alles andere in Formwerk kommt ohne Sprachmodell aus."
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
            "Boolesche Operationen brauchen saubere Eingangskörper. Formwerk "
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
            "**Grundsätzlich gilt:** Kein Fehler in Formwerk endet bei der "
            "Feststellung. Steht keine Handlung dabei, mit der es weitergeht, "
            "ist das ein Fehler in Formwerk und einen Bericht wert."
        ),
    ),
    Page(
        key="glossary",
        title=_("Wörterbuch"),
        body=_(
            "Die Wörter, die in Formwerk, in Slicern und in Druckforen "
            "vorkommen — kurz erklärt.\n\n"
            "**Netz (Mesh)** — ein Körper als Hülle aus Dreiecken. STL und OBJ "
            "enthalten nichts anderes: keine Kreise, keine Maße, nur Dreiecke.\n\n"
            "**Geschlossen (wasserdicht)** — die Hülle hat kein Loch, innen und "
            "außen sind eindeutig. Nur ein geschlossener Körper lässt sich "
            "zuverlässig verknüpfen und drucken.\n\n"
            "**Operation** — ein Arbeitsschritt: bohren, verrunden, teilen, "
            "einen Baustein setzen. In Formwerk entsteht Geometrie nur so.\n\n"
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
            "macht. Formwerk ist keiner und ersetzt keinen.\n\n"
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
) -> str:
    """Das ganze Handbuch als HTML-Rumpf — für die Website und für das PDF.

    ``figure_source`` sagt, unter welcher Adresse eine Abbildung zu finden ist;
    wer nichts liefert, bekommt an ihrer Stelle den Alt-Text. Wo die Datei
    liegt, entscheidet damit der Aufrufer und nicht der Kern — hier soll keine
    Ablagestruktur festgeschrieben werden.
    """
    from app.core import figures
    from app.core.markup import to_html

    def resolve(key: str) -> tuple[str, str, str] | None:
        figure = figures.find(key)
        if figure is None:
            return None
        source = figure_source(key) if figure_source else ""
        return source, str(figure.alt), str(figure.caption)

    return to_html(as_markdown(registry, with_figures=True), resolve)


def without_figures(body: str) -> str:
    """Bildverweise durch ihren Alt-Text ersetzen."""
    from app.core import figures

    def describe(match: re.Match[str]) -> str:
        figure = figures.find(match.group(1))
        return f"*{_('Abbildung')}: {figure.alt}*" if figure else ""

    return FIGURE_PATTERN.sub(describe, body)
