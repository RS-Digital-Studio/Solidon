"""Die Touren durch die Beispielprojekte (Bauplan §37.2, §2.2).

§37.2 nennt die Beispiele „Dokumentation, Abnahmetest und
Startbildschirm-Inhalt zugleich" — aber ein fertiges Projekt erklärt sich
nicht selbst: wer eines öffnet, sieht ein Ergebnis und keinen Auftrag. Die
Tour ist der fehlende Teil. Sie sagt Schritt für Schritt, was zu tun ist,
und erkennt am Dokument, wann es getan wurde — die Beispiele bleiben dabei
fertige Projekte und damit Abnahmetest, das Lehrmittel ist der Verlauf
selbst: ändern, zurücknehmen, wiederholen.

Der Kern kennt kein Qt: eine Tour ist Text plus Prüfungen auf Dokument und
Verlauf. Die Oberfläche ruft die Prüfung des aktuellen Schritts nach jeder
Änderung auf und schaltet weiter; Schritte ohne Prüfung erklären nur, dort
schaltet der Nutzer selbst.

Die Zahlen in den Prüfungen sind die Ausgangswerte aus
``tools/make_examples.py`` — erkannt wird eine *Abweichung* davon.
Driften die beiden auseinander, gilt eine Prüfung schon beim Öffnen als
getan, und genau das schlägt in ``tests/test_tour.py`` fehl.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Literal

from app.core.registry import REGISTRY
from app.core.scene.history import History
from app.core.types import Document, Operation
from app.core.units import is_close
from app.i18n import TranslatableText, _

#: Liest Dokument und Verlauf und sagt, ob der Schritt getan ist.
StepCheck = Callable[[Document, History], bool]

#: Die Bereiche des Fensters, auf die ein Schritt zeigen kann. Der Kern nennt
#: sie beim Namen und weiß nicht, wo sie liegen — das ist Sache der Oberfläche.
TourTarget = Literal["tree", "parameters", "history", "report", "viewport", "toolbar", "tools"]


@dataclass(frozen=True, slots=True)
class TourStep:
    """Ein Auftrag an den Nutzer, und woran er als erledigt zu erkennen ist.

    ``done`` ist ``None`` bei Schritten, die nur erklären — dort gibt es
    nichts zu erkennen, und die Oberfläche bietet das Weiterschalten an.
    """

    text: TranslatableText | str
    done: StepCheck | None = None
    shows: TourTarget | None = None
    """Wovon der Schritt spricht. „Sehen Sie links in den Verlauf" ist eine
    Anweisung, die vier Bereiche offenlässt; wer sie zum ersten Mal liest, sucht.
    Die Oberfläche lässt den genannten Bereich kurz aufleuchten — der Kern sagt
    nur, welcher es ist."""


@dataclass(frozen=True, slots=True)
class Tour:
    """Die Tour eines Beispielprojekts: Einstieg, Schritte, Abschluss."""

    example_id: str
    intro: TranslatableText | str
    steps: tuple[TourStep, ...]
    closing: TranslatableText | str


# --- Prüfbausteine ---------------------------------------------------------------


def _first_op(document: Document, name: str) -> Operation | None:
    """Die erste Operation dieses Namens im Stapel, oder nichts."""
    return next((entry for entry in document.ops if entry.op == name), None)


def _number(value: object) -> float | None:
    """Ein Parameterwert als Zahl — Ausdrücke (``=@name``) sind keine."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _op_number_changed(name: str, field: str, original: float) -> StepCheck:
    """Getan, sobald ein Zahlenparameter der Operation vom Ausgangswert
    abweicht — egal wohin: die Übung ist das Ändern, nicht ein Zielwert."""

    def check(document: Document, history: History) -> bool:
        for entry in document.ops:
            if entry.op != name:
                continue
            value = _number(entry.params.get(field))
            if value is not None and not is_close(value, original):
                return True
        return False

    return check


def _op_text_changed(name: str, field: str, original: str) -> StepCheck:
    """Dasselbe für einen Textparameter."""

    def check(document: Document, history: History) -> bool:
        entry = _first_op(document, name)
        return entry is not None and str(entry.params.get(field, original)) != original

    return check


def _parameter_changed(name: str, original: float) -> StepCheck:
    """Getan, sobald der Projektparameter einen anderen Wert trägt."""

    def check(document: Document, history: History) -> bool:
        parameter = document.parameters.get(name)
        return parameter is not None and not is_close(parameter.value, original)

    return check


def _undo_happened(document: Document, history: History) -> bool:
    """Getan, sobald etwas zurückgenommen und noch nicht wiederholt ist."""
    return history.can_redo


def _op_present(name: str) -> StepCheck:
    """Getan, sobald eine Operation dieses Namens im Stapel steht."""

    def check(document: Document, history: History) -> bool:
        return _first_op(document, name) is not None

    return check


def _op_restored(name: str) -> StepCheck:
    """Getan, sobald die Operation wieder da und nichts mehr zurückgenommen
    ist — die Erkennung für ein Redo nach einem Undo."""

    def check(document: Document, history: History) -> bool:
        return _first_op(document, name) is not None and not history.can_redo

    return check


def _parts_inserted(at_least: int) -> StepCheck:
    """Getan, sobald der Stapel so viele Bausteine trägt — welcher, ist egal:
    die Übung ist der Weg über Katalog oder Menü, nicht ein bestimmtes Teil."""

    def check(document: Document, history: History) -> bool:
        count = sum(
            1
            for entry in document.ops
            if REGISTRY.has(entry.op) and REGISTRY.get(entry.op).category == "parts"
        )
        return count >= at_least

    return check


# --- Die Touren -------------------------------------------------------------------

TOURS: Final[tuple[Tour, ...]] = (
    Tour(
        example_id="weg1-halterung-anpassen",
        intro=_(
            "Der häufigste Fall: eine heruntergeladene Halterung, die fast passt. "
            "Dieses Projekt hat den Weg schon einmal durchgespielt — jetzt sind Sie dran."
        ),
        steps=(
            TourStep(
                shows="history",
                text=_(
                    "Sehen Sie links in den Verlauf: vier Schritte — laden, reparieren, "
                    "auf das Bett, bohren. Das Modell ist hier nicht das Netz, sondern "
                    "diese Liste, und jeder Schritt bleibt änderbar."
                ),
            ),
            TourStep(
                shows="history",
                text=_(
                    "Öffnen Sie den letzten Schritt „Bohrung setzen“ mit einem "
                    "Doppelklick im Verlauf und ändern Sie den Durchmesser — etwa auf "
                    "6 mm. Das Loch wird nicht neu gebohrt: es ist derselbe Schritt "
                    "mit einer anderen Zahl."
                ),
                done=_op_number_changed("drill_hole", "diameter", 4.2),
            ),
            TourStep(
                text=_(
                    "Drücken Sie Strg+Z. Der letzte Schritt verschwindet als Ganzes, "
                    "das Loch ist zu — als wäre nie gebohrt worden."
                ),
                done=_undo_happened,
            ),
            TourStep(
                text=_(
                    "Holen Sie ihn mit Strg+Y zurück. Nichts geht hier verloren: "
                    "Rückgängig und Wiederholen gelten für jeden Schritt, auch nächste "
                    "Woche noch."
                ),
                done=_op_restored("drill_hole"),
            ),
            TourStep(
                shows="report",
                # **Der Satz muss halten, was rechts wirklich steht.** Hier
                # stand „was die Reparatur am Anfang gefunden hat" — und der
                # Bericht dieses Beispiels sagt „An diesem Netz war nichts zu
                # reparieren". Wer als Erstes einen Widerspruch zwischen
                # Anleitung und Anwendung liest, glaubt danach keiner von
                # beiden. Genannt wird deshalb, was dasteht: drei Hinweise,
                # keine Warnung. ``tests/test_tour.py`` hält die Zahl fest.
                text=_(
                    "Rechts steht der Prüfbericht — hier drei Hinweise und keine Warnung: "
                    'verschweißte Doppelpunkte vom Einlesen, „nichts zu reparieren" für '
                    "dieses Netz, und die Bohrung, die um die Materialtoleranz gewachsen "
                    "ist. Bei heruntergeladenen Modellen steht dort öfter eine Warnung."
                ),
            ),
        ),
        closing=_(
            "Das war Weg 1: einlesen, reparieren, ändern. Am Ende steht "
            "Datei → Exportieren — die Datei geht in den Slicer, und der macht den "
            "G-Code."
        ),
    ),
    Tour(
        example_id="weg2-halter-konstruieren",
        intro=_(
            "Hier ist nichts importiert: der Halter besteht aus drei benannten Maßen "
            "und Bausteinen aus der Bibliothek."
        ),
        steps=(
            TourStep(
                shows="parameters",
                text=_(
                    "Links unter Parameter stehen Breite, Tiefe und Stärke. Ändern "
                    "Sie hier eine Zahl; alle passenden Schritte im Verlauf verwenden "
                    "sie automatisch."
                ),
            ),
            TourStep(
                text=_(
                    "Ändern Sie den Wert von Breite — etwa auf 90. Das ganze Teil "
                    "folgt sofort, und die Schraubenlöcher bleiben, wo sie hingehören."
                ),
                done=_parameter_changed("breite", 60.0),
            ),
            TourStep(
                text=_(
                    "Die Schraubenlöcher und die Versteifung sind Bausteine: die Maße "
                    "für M4 kommen aus der Normteiltabelle, das Spiel aus dem "
                    "Materialprofil. Der ganze Katalog liegt unter Strg+K."
                )
            ),
            TourStep(
                shows="tree",
                text=_(
                    "Setzen Sie selbst einen Baustein: den Halter im Objektbaum "
                    "anklicken, dann mit der rechten Maustaste *Bausteine*, dann "
                    "*Baustein einsetzen* — der Katalog zeigt jeden mit Bild."
                ),
                done=_parts_inserted(4),
            ),
        ),
        closing=_(
            "Das war Weg 2: konstruieren mit Parametern und Bausteinen. "
            "Bearbeiten → Varianten erzeugen exportiert dasselbe Teil in gestaffelten "
            "Größen."
        ),
    ),
    Tour(
        example_id="weg3-generiert-aufbereiten",
        intro=_(
            "Dieser Körper kommt aus einem Generator. So ein Netz ist eine "
            "Oberfläche, keine Konstruktion — deshalb beginnt Weg 3 mit der "
            "Reparaturkette."
        ),
        steps=(
            TourStep(
                shows="history",
                text=_(
                    "Die ersten Schritte im Verlauf sind Erzeugen und Reparieren: "
                    "generierte Netze kommen mit Löchern und doppelten Flächen, und "
                    "die Kette schließt sie, bevor irgendetwas anderes passiert."
                ),
            ),
            TourStep(
                shows="report",
                text=_(
                    "Rechts im Prüfbericht steht, was die Kette gefunden und "
                    "geschlossen hat — mit Herkunft: eine Schätzung wird nie als "
                    "Messung ausgegeben."
                ),
            ),
            TourStep(
                shows="viewport",
                text=_(
                    "Maße entstehen danach als eigene Schritte, nicht durch Vermessen "
                    "des Netzes: klicken Sie eine Fläche an, dann "
                    "Rechtsklick → Bohrung setzen."
                ),
                done=_op_present("drill_hole"),
            ),
            TourStep(
                text=_(
                    "Strg+Z nimmt die Bohrung zurück — ein erzeugter Körper ist "
                    "danach so bearbeitbar wie jeder andere."
                ),
                done=_undo_happened,
            ),
        ),
        closing=_(
            "Das war Weg 3. Eigene Körper erzeugen Sie unter Datei → Modell "
            "erzeugen, sobald ein ComfyUI eingerichtet ist — bis dahin bringt dieses "
            "Beispiel sein Netz mit."
        ),
    ),
    Tour(
        example_id="weg4-figur-formen",
        intro=_(
            "Manche Formen lassen sich nicht bemaßen. Weg 4 baut die grobe Gestalt "
            "aus Grundkörpern und formt sie dann von Hand — dieses Beispiel hört "
            "genau dort auf, wo Sie den Pinsel nehmen."
        ),
        steps=(
            TourStep(
                shows="history",
                # **Sechs, und der Gemeinte ist nicht mehr der letzte.** Der
                # Verlauf führt Quader, Kugel, Versetzen, Verschmelzen,
                # Vernetzen und Auf-das-Bett-Setzen — nachgezählt. Die Zahl
                # stand zweimal falsch: erst „vier" (gemeint war das
                # Vernetzen, gezählt das Versetzen), dann „fünf", bis das
                # Beispiel am 23.08.2026 einen Schritt bekam, damit es nicht
                # unter der Druckplatte endet.
                #
                # **Eine von Hand gepflegte Zahl neben einer erzeugten Datei
                # veraltet immer — es ist nur eine Frage, wann.** Dass es
                # auffällt und nicht der Kunde es findet, liegt an
                # ``tests/test_tour.py``: Er zählt gegen den **echten**
                # Verlauf und nicht gegen eine zweite gepflegte Zahl.
                text=_(
                    "Im Verlauf stehen sechs Schritte: zwei Grundkörper, einer davon "
                    "versetzt, beide weich verschmolzen, gleichmäßig vernetzt und zum "
                    "Schluss auf das Bett gesetzt. Das Vernetzen ist der, den man "
                    "auslässt und danach vermisst — ohne ihn hat der Pinsel zu wenige "
                    "Eckpunkte."
                ),
            ),
            TourStep(
                shows="history",
                text=_(
                    "Doppelklick auf *Weich verschmelzen* und den Übergang auf 8 "
                    "stellen: Der Hals wird dicker, ohne dass irgendetwas neu gebaut "
                    "wird. Das ist der Unterschied zu einem Sculpting-Programm."
                ),
                done=_op_number_changed("blend_union", "radius", 4.0),
            ),
            TourStep(
                shows="toolbar",
                text=_(
                    "Jetzt der Pinsel: die Figur anklicken, dann oben in der "
                    "Werkzeugleiste auf „Formen“ mit dem Pinselsymbol zeigen und "
                    "klicken. Ziehen Sie ein paar Striche über den Körper, sehen Sie "
                    "in der Leiste unten auf die Wandstärke — und beenden Sie mit "
                    "Fertig."
                ),
                done=_op_present("sculpt_strokes"),
            ),
            TourStep(
                shows="history",
                text=_(
                    "Strg+Z nimmt die ganze Sitzung zurück, nicht den letzten Zug: Im "
                    "Verlauf steht ein Schritt, so viele Züge er auch enthält."
                ),
                done=_undo_happened,
            ),
            TourStep(
                shows="toolbar",
                text=_(
                    "„Skelett“ steht in derselben Werkzeugleiste und gehört zum "
                    "selben Weg: zwei Klicks setzen einen Knochen, Fertig fragt "
                    "danach nach den Winkeln. So bekommt eine Figur ihre Haltung, "
                    "ohne dass sie neu gebaut wird."
                ),
            ),
        ),
        closing=_(
            "Das war Weg 4. Was ihn von den anderen dreien unterscheidet: Hier zählt "
            "eine Geste und keine Zahl — und trotzdem bleibt jeder Schritt änderbar."
        ),
    ),
    Tour(
        example_id="gehaeuse-mit-bausteinen",
        intro=_(
            "Ein Gehäuseboden mit vier Bausteinen, die einzeln je eine halbe Stunde "
            "Konstruktion wären: Mutternfalle, Heat-Set-Buchse, Schraubenloch, "
            "Kabeldurchführung."
        ),
        steps=(
            TourStep(
                shows="history",
                text=_(
                    "Der Verlauf zeigt sie als Transaktionen: Boden, Befestigung, "
                    "Kabel. Jeder Baustein sitzt an Zahlen, die Sie später noch "
                    "ändern können."
                ),
            ),
            TourStep(
                shows="viewport",
                text=_(
                    "Das kleine Teil daneben ist ein Prüfstück: ein Ausschnitt um die "
                    "Mutternfalle. Zwei Minuten Druck sagen, ob die Passung stimmt — "
                    "statt zwei Stunden für das ganze Gehäuse."
                ),
            ),
            TourStep(
                shows="parameters",
                text=_(
                    "Ändern Sie links den Parameter Wandstärke — etwa auf 10. Boden und "
                    "Bausteine folgen; die Buchse sitzt weiter bündig."
                ),
                done=_parameter_changed("wand", 8.0),
            ),
            TourStep(
                shows="history",
                text=_(
                    "Öffnen Sie die Mutternfalle mit einem Doppelklick im Verlauf und "
                    "stellen Sie die Größe auf M4 um — alle Maße kommen aus der "
                    "Normteiltabelle, keines aus dem Gefühl."
                ),
                done=_op_text_changed("insert_nut_trap", "size", "M3"),
            ),
        ),
        closing=_(
            "Passungen wie die Mutternfalle stehen und fallen mit dem Spiel Ihres "
            "Druckers. Messen lässt es sich mit dem Beispiel „Kalibrieren“, "
            "eintragen unter Bearbeiten → Material kalibrieren."
        ),
    ),
    Tour(
        example_id="schild-zweifarbig",
        intro=_(
            "Zweifarbig auf zwei Wegen: Schrift mit einem eigenen Filament für "
            "den Farbwechsel im 3MF — und Lettern als eigener Körper."
        ),
        steps=(
            TourStep(
                shows="history",
                text=_(
                    "Öffnen Sie „Beschriftung“ mit einem Doppelklick im Verlauf und "
                    "schreiben Sie Ihren eigenen Text. Die Schrift bleibt dem zweiten "
                    "Filament zugeordnet."
                ),
                done=_op_text_changed("label_text", "text", "Solidon3D"),
            ),
            TourStep(
                shows="viewport",
                # **Ohne die Jahreszahl im Satz.** Sie stand hier wörtlich und
                # war damit an den Inhalt des Beispiels gebunden: Wer ihn
                # ändert, macht den Tourtext falsch und braucht fünf neue
                # Übersetzungen dazu. Der Satz zeigt jetzt auf die Sache und
                # nicht auf den Wortlaut.
                text=_(
                    "Die Lettern daneben sind der zweite Weg: ein eigener "
                    "Körper. Für Drucker mit einem Werkzeug — gedruckt und "
                    "aufgeklebt, oder mit Filamentwechsel von Hand."
                ),
            ),
            TourStep(
                shows="history",
                text=_(
                    "Auf der Rückseite sitzt eine Schlüsselloch-Aufhängung. "
                    "Verschieben Sie sie: Doppelklick auf „Aufhängung“, dann die "
                    "x-Position ändern."
                ),
                done=_op_number_changed("insert_keyhole", "x", -30.0),
            ),
            TourStep(
                text=_(
                    "Beim Export trägt 3MF die Slots als Farbgruppen mit — der "
                    "Slicer macht daraus den Farbwechsel. STL kennt keine Farbe und "
                    "verliert sie."
                )
            ),
        ),
        closing=_(
            "Beschriftungen liegen im Menü Erzeugen: jede Schrift kann einem "
            "Filament zugeordnet oder ein eigener Körper sein."
        ),
    ),
    Tour(
        example_id="drucker-kalibrieren",
        intro=_(
            "Drei Prüfkörper auf einer Platte: Toleranzleiter, Wandstärkenleiter, "
            "Überhangfächer. Einmal gedruckt, wissen Sie dreierlei über Ihren "
            "Drucker."
        ),
        steps=(
            TourStep(
                shows="viewport",
                text=_(
                    "Die Toleranzleiter zeigt, welches Spiel eine Passung braucht; "
                    "die Wandleiter, ab welcher Stärke wirklich Material liegt; der "
                    "Fächer, ab welchem Winkel Stützen nötig sind — gemessen statt "
                    "Faustregel 45 Grad."
                ),
            ),
            TourStep(
                # **Wo doppelgeklickt werden soll, wird gezeigt.** Dieser
                # Schritt war der einzige im ganzen Bestand, der zum Verlauf
                # schickt, ohne ihn aufblinken zu lassen — und damit die
                # einzige Tour ohne jeden Bereichsverweis. Jede andere Stelle
                # mit „Doppelklick im Verlauf" trägt ihn.
                shows="history",
                text=_(
                    "Die Platte ordnet ein eigener Schritt an: öffnen Sie "
                    "„Anordnen“ mit einem Doppelklick und ändern Sie den Abstand — "
                    "die drei Körper rücken sofort um."
                ),
                done=_op_number_changed("arrange_bed", "spacing", 8.0),
            ),
            TourStep(
                shows="viewport",
                text=_(
                    "Nach dem Druck: messen, welcher Stift sauber sitzt, welche Wand "
                    "trägt und wo der Fächer hässlich wird."
                ),
            ),
            TourStep(
                text=_(
                    "Die Werte gehören ins Materialprofil, nicht ins Modell: "
                    "Bearbeiten → Material kalibrieren. Sie gelten danach für jede "
                    "Passung — auch in Projekten, die Sie früher gebaut haben."
                )
            ),
        ),
        closing=_(
            "Kalibrieren lohnt sich je Material einmal: PETG schrumpft anders als "
            "PLA, und das Spiel wandert mit."
        ),
    ),
    Tour(
        example_id="aushoehlen-und-teilen",
        intro=_(
            "Ein Klotz, der so nicht gedruckt werden müsste: zu viel Material, das "
            "keiner sieht. Dieses Projekt teilt ihn und höhlt beide Hälften aus."
        ),
        steps=(
            TourStep(
                shows="history",
                text=_(
                    "Erst teilen, dann aushöhlen — nicht umgekehrt: eine ausgehöhlte "
                    "Wand wäre an der Schnittfläche zu dünn für Passstifte. Deshalb "
                    "steht „Teilen und verstiften“ im Verlauf vor dem „Aushöhlen“."
                ),
            ),
            TourStep(
                text=_(
                    "In jeder Schnittfläche stecken zwei Stifte. Ihr Spiel kommt aus "
                    "dem kalibrierten Materialprofil — nicht aus einer geratenen "
                    "Zahl."
                )
            ),
            TourStep(
                shows="history",
                text=_(
                    "Öffnen Sie eines der beiden „Aushöhlen“ im Verlauf und stellen "
                    "Sie die Wandstärke um — etwa auf 5 mm. Die Entlüftungsbohrungen "
                    "wandern mit."
                ),
                done=_op_number_changed("hollow_object", "wall", 3.0),
            ),
            TourStep(
                shows="tools",
                text=_(
                    "Unter dem Viewport liegt die Werkzeugzeile: Explosion zieht die "
                    "Hälften auseinander, dann sehen Sie Stifte und Hohlraum."
                ),
            ),
        ),
        closing=_(
            # **Drei Wege, und der erste hat eine Bedingung.** Hier stand
            # allein *Automatisch teilen*, dazu im falschen Menü — der Eintrag
            # trägt die Kategorie ``prepare`` und ist mit ihr nach
            # *Vorbereiten* umgezogen, der Satz blieb bei *Bearbeiten* zurück.
            #
            # Schwerer wog der Inhalt: *Automatisch teilen* zerschneidet ein
            # Teil, **das nicht auf das Bett passt** (so steht es an seinem
            # eigenen Menüeintrag). Diese Tour teilt aber, um Material zu
            # sparen — wer ihrem Schlusssatz folgte, griff zu einer Funktion,
            # die seinen Fall gar nicht meint, und die beiden Wege, auf denen
            # er die Naht selbst legt, standen nirgends.
            "Passt ein Teil nicht auf das Bett, sucht Vorbereiten → Automatisch "
            "teilen die Trennebene selbst. Soll die Naht woanders liegen, legen "
            "Sie sie mit Vorbereiten → Teilen an eine Ebene — oder ziehen sie mit "
            "Vorbereiten → An gezeichneter Linie trennen dorthin, wo Sie sie haben "
            "wollen."
        ),
    ),
    Tour(
        example_id="dose-mit-deckel",
        intro=_(
            "Eine Dose mit Deckel — und darin steckt alles, was die anderen "
            "Beispiele einzeln zeigen: benannte Maße, ein ausgehöhlter Körper, "
            "Bausteine in der Wand, ein Deckel und eine Beschriftung."
        ),
        steps=(
            TourStep(
                shows="parameters",
                text=_(
                    "Links stehen vier Maße mit Namen. Stellen Sie die Höhe auf "
                    "60 mm — die Dose wächst, der Deckel bleibt, wo er hingehört, "
                    "und die Kabeldurchführung wandert mit der Wand."
                ),
                done=_parameter_changed("hoehe", 40.0),
            ),
            TourStep(
                shows="history",
                text=_(
                    "Im Verlauf steht „Aushöhlen“ mit dem Schalter *Oben öffnen*. "
                    "Er ist der Grund, warum es überhaupt einen Deckel geben kann: "
                    "ein geschlossener Hohlraum ist ein Hohlraum, kein Fach."
                ),
            ),
            TourStep(
                shows="viewport",
                text=_(
                    "Der Deckel ist nicht nachgezeichnet, sondern aus der Öffnung "
                    "geschnitten. Sein Kragen ist der Hohlraum, geschrumpft um das "
                    "Spiel aus dem Materialprofil — dieselbe Zahl, die über jede "
                    "andere Passung entscheidet."
                ),
            ),
            TourStep(
                shows="report",
                text=_(
                    "Deshalb steht die Passung auch im Prüfbericht. Wer sein "
                    "Material einmal kalibriert, verbessert damit diesen Deckel, "
                    "ohne ihn anzufassen."
                ),
            ),
        ),
        closing=_(
            "Dasselbe geht mit jeder Schachtel, die schon da ist: Fläche an der "
            "Öffnung anklicken, mit rechts *Bausteine*, dann *Deckel erzeugen*."
        ),
    ),
)


def tour_for(example_id: str) -> Tour | None:
    """Die Tour zu einem Beispiel, oder nichts — ein Beispiel ohne Tour ist
    kein Fehler, es erklärt sich dann nur nicht selbst."""
    for tour in TOURS:
        if tour.example_id == example_id:
            return tour
    return None
