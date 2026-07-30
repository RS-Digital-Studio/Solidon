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

from dataclasses import dataclass
from typing import Final

from app.core.registry import documentation
from app.core.registry.registry import CATEGORIES, REGISTRY, Registry
from app.i18n import TranslatableText, _


@dataclass(frozen=True, slots=True)
class Page:
    """Eine Seite des Handbuchs. ``body`` ist Markdown."""

    key: str
    title: TranslatableText | str
    body: TranslatableText | str
    generated: bool = False
    """Erzeugte Seiten kommen aus dem Register und stehen hinter den anderen."""


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
            "**Was es nicht ist:** kein CAD-Ersatz — es gibt keine Skizzen und "
            "keine Zwangsbedingungen. Kein Slicer — die Druckdatei kommt weiter "
            "aus dem Slicer, Formwerk sucht und bewertet nur. Keine Cloud — kein "
            "Konto, keine Telemetrie, nichts, was den Rechner verlässt.\n\n"
            "Ohne Netz, ohne Konto und ohne Sprachmodell bleibt alles außer dem "
            "Chat benutzbar."
        ),
    ),
    Page(
        key="ways",
        title=_("Die drei Wege"),
        body=_(
            "Fast jede Aufgabe geht einen von drei Wegen. Zu jedem liegt ein "
            "Beispielprojekt bereit — auf dem Startbildschirm, zum Öffnen und "
            "Nachsehen.\n\n"
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
            "Jede Operation steht im Verlauf, und dort bleibt sie änderbar.\n\n"
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
            "**Das Spiel steht im Materialprofil, nicht im Modell.** Wer einen "
            "Stift in ein Loch stecken will, trägt keine 0,2 ein — er sagt "
            "*Passung*, und die Zahl kommt aus dem Profil des Materials, mit "
            "dem gedruckt wird.\n\n"
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
            "**Exportiert wird nach STL, 3MF oder STEP.** 3MF ist, was Slicer "
            "bevorzugen, und es trägt die Materialslots als Farbgruppen mit; STL "
            "kennt keine Farbe und verliert sie folgerichtig. STEP gibt es für "
            "exakte Körper, mit echten Flächen und Kanten.\n\n"
            "**Der Slicer bleibt außen.** Die Schichtanalyse sucht und bewertet "
            "— Inseln, Spannweiten, dünne Stellen, die beste Lage —, aber die "
            "Druckdatei schreibt der Slicer. Wo beide Zahlen nennen, wird immer "
            "ausgewiesen, welche woher kommt."
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


def as_markdown(registry: Registry | None = None) -> str:
    """Das ganze Handbuch am Stück, für die Kommandozeile und zum Nachlesen."""
    parts = []
    for page in pages(registry):
        if page.generated:
            parts.append(str(page.body))
        else:
            parts.append(f"## {page.title}\n\n{page.body}")
    return "\n\n".join(parts).rstrip() + "\n"
