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
    except TypeError, ValueError:
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


def _first_op_number_changed(name: str, field: str, original: float) -> StepCheck:
    """Wie :func:`_op_number_changed`, aber nur an der **ersten** Operation dieses Namens.

    Für Beispiele mit mehreren gleichen Schritten, deren Werte verschieden
    beginnen — zwei Schnitte an zwei Stellen: Die Übung gilt dem ersten.
    """

    def check(document: Document, history: History) -> bool:
        entry = _first_op(document, name)
        value = _number(entry.params.get(field)) if entry is not None else None
        return value is not None and not is_close(value, original)

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


def _undo_put_back(name: str, field: str, value: float) -> StepCheck:
    """Getan, sobald ein Undo den Wert eines Schritts zurückgestellt hat — und
    der Schritt selbst noch steht.

    ``_undo_happened`` fragte nur ``can_redo`` und bestätigte damit auch einen
    Satz, der das Gegenteil behauptete: Die erste Tour sagte, das Loch sei
    zu, während das Undo nur den Durchmesser auf 4,2 mm zurückstellte
    (Gesamtreview 05.09.2026, CORE-32). Die Prüfung sagt jetzt genau das,
    was der Satz beschreibt.
    """

    def check(document: Document, history: History) -> bool:
        if not history.can_redo:
            return False
        entry = _first_op(document, name)
        if entry is None:
            return False
        current = entry.params.get(field, value)
        try:
            return is_close(float(current), value)
        except TypeError, ValueError:
            return False

    return check


def _op_present(name: str) -> StepCheck:
    """Getan, sobald eine Operation dieses Namens im Stapel steht."""

    def check(document: Document, history: History) -> bool:
        return _first_op(document, name) is not None

    return check


def _op_gone(name: str) -> StepCheck:
    """Getan, sobald keine Operation dieses Namens mehr im Stapel steht.

    **Die Gegenprüfung zu ``_op_present``, und sie ist präziser als
    ``_undo_happened``.** Jenes fragt nur, ob *irgendetwas* zurückgenommen
    wurde (``history.can_redo``) — bei einem Beispiel, in dem hinter dem
    gemeinten Schritt noch einer steht, quittiert es schon nach dem ersten
    Strg+Z, während der Zustand, den die Tour beschreibt, noch gar nicht
    erreicht ist. Der Nutzer tut, was dasteht, sieht das Gegenteil, und die
    Führung bestätigt ihn (gefunden von 72 am elften Beispiel, 31.08.2026).

    Hier wird gefragt, ob der genannte Schritt weg ist — also der Zustand
    selbst und nicht eine Bewegung dorthin.
    """

    def check(document: Document, history: History) -> bool:
        return _first_op(document, name) is None

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
            "Der häufigste Fall: eine heruntergeladene Halterung, die fast passt. Jetzt passen "
            "Sie sie selbst an."
        ),
        steps=(
            TourStep(
                shows="history",
                text=_(
                    "Links im Verlauf stehen vier Schritte: laden, reparieren, auf das Bett, "
                    "bohren. Jeder bleibt änderbar."
                ),
            ),
            TourStep(
                shows="history",
                text=_(
                    "Öffnen Sie „Bohrung setzen“ im Verlauf mit einem Doppelklick und ändern Sie "
                    "den Durchmesser, etwa auf 6 mm."
                ),
                done=_op_number_changed("drill_hole", "diameter", 4.2),
            ),
            TourStep(
                text=_(
                    "Drücken Sie Strg+Z. Der Durchmesser steht wieder auf 4,2 mm, die Bohrung "
                    "bleibt."
                ),
                done=_undo_put_back("drill_hole", "diameter", 4.2),
            ),
            TourStep(
                text=_(
                    "Holen Sie die Änderung mit Strg+Y zurück. Rückgängig und Wiederholen gelten "
                    "für jeden Schritt."
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
                # beiden. Genannt wird deshalb, was dasteht: zwei Hinweise,
                # keine Warnung. ``tests/test_tour.py`` hält die Zahl fest.
                # Zwei sind es seit dem 14.09.2026 („Doppelte Punkte wurden
                # verschweißt" war das Lesen einer STL und ist kein Befund
                # mehr, ``ingest.loader.normalise``). Vom 20. bis zum
                # 21.09.2026 stand ein dritter da — der Hinweis auf die
                # Analysekarte „Formabweichung" an jedem Körper mit belegten
                # Flächen; seither ist er ein Befund mit Maß und steht nur,
                # wo belegte Punkte neben der Form liegen
                # (``evaluate.check_form_deviation``), und an dieser Halterung
                # liegen sie nicht.
                text=_(
                    "Rechts im Prüfbericht stehen zwei Hinweise: nichts zu reparieren, und die "
                    "Bohrung wurde für den Druck vergrößert."
                ),
            ),
        ),
        closing=_(
            "Das war Weg 1. Datei → Exportieren gibt das Teil an den Slicer weiter, der den "
            "G-Code macht."
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
                    "Links unter Parameter stehen Breite, Tiefe und Stärke. Alle Schritte, die "
                    "sie verwenden, folgen jeder Änderung."
                ),
            ),
            TourStep(
                text=_(
                    "Stellen Sie Breite etwa auf 90. Das Teil folgt, und die Schraubenlöcher "
                    "bleiben an ihrem Platz."
                ),
                done=_parameter_changed("breite", 60.0),
            ),
            TourStep(
                text=_(
                    "Schraubenlöcher und Versteifung sind Bausteine, ihre Maße kommen aus der "
                    "Normteiltabelle und dem Materialprofil. Der Katalog liegt unter Strg+K."
                )
            ),
            TourStep(
                shows="tree",
                text=_(
                    "Setzen Sie einen Baustein: den Halter im Objektbaum anklicken, dann rechts "
                    "unter Auswahl auf „Bausteine“."
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
            "Dieser Körper kommt aus einem Generator. Weg 3 beginnt deshalb mit der Reparaturkette."
        ),
        steps=(
            TourStep(
                shows="history",
                text=_(
                    "Die ersten Schritte im Verlauf sind Erzeugen und Reparieren. Die Reparatur "
                    "schließt Löcher und entfernt doppelte Flächen."
                ),
            ),
            TourStep(
                shows="report",
                text=_(
                    "Rechts im Prüfbericht steht, was die Reparatur gefunden und geschlossen hat."
                ),
            ),
            TourStep(
                shows="viewport",
                text=_(
                    "Klicken Sie eine Fläche an, dann rechts unter Auswahl auf „Bohrung setzen“."
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
            "Ein extern erzeugtes GLB oder STL bearbeiten Sie wie jeden Körper. „Modell "
            "erzeugen“ erzeugt Modelle über ein lokales ComfyUI."
        ),
    ),
    Tour(
        example_id="weg4-figur-formen",
        intro=_(
            "Manche Formen lassen sich nicht bemaßen. Weg 4 baut die Gestalt aus Grundkörpern "
            "und formt sie mit dem Pinsel."
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
                    "Im Verlauf stehen sechs Schritte. „Dreiecke angleichen“ gibt dem Pinsel "
                    "genug Eckpunkte zum Formen."
                ),
            ),
            TourStep(
                shows="history",
                text=_(
                    "Öffnen Sie „Weich verschmelzen“ im Verlauf mit einem Doppelklick und "
                    "stellen Sie den Übergang auf 8. Der Hals wird dicker."
                ),
                done=_op_number_changed("blend_union", "radius", 4.0),
            ),
            TourStep(
                shows="toolbar",
                text=_(
                    "Figur anklicken, oben in der Werkzeugleiste „Formen“ wählen, ein paar "
                    "Striche ziehen und mit „Fertig“ beenden."
                ),
                done=_op_present("sculpt_strokes"),
            ),
            TourStep(
                shows="history",
                text=_(
                    "Drücken Sie Strg+Z. Die ganze Sitzung ist ein Schritt im Verlauf und "
                    "verschwindet auf einmal."
                ),
                done=_undo_happened,
            ),
            TourStep(
                shows="toolbar",
                text=_(
                    "Daneben in der Werkzeugleiste steht „Skelett“: Zwei Klicks setzen einen "
                    "Knochen, und „Fertig“ fragt nach den Winkeln."
                ),
            ),
        ),
        closing=_(
            "Das war Weg 4. Hier zählt eine Geste statt einer Zahl, und trotzdem bleibt jeder "
            "Schritt änderbar."
        ),
    ),
    Tour(
        example_id="gehaeuse-mit-bausteinen",
        intro=_(
            "Ein Gehäuseboden mit vier Bausteinen: Mutternfalle, Heat-Set-Buchse, Schraubenloch "
            "und Kabeldurchführung."
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
                    "Das kleine Teil daneben ist ein Prüfstück um die Mutternfalle. Drucken Sie "
                    "es vor dem ganzen Gehäuse."
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
                    "Öffnen Sie die Mutternfalle im Verlauf mit einem Doppelklick und stellen "
                    "Sie die Größe auf M4."
                ),
                done=_op_text_changed("insert_nut_trap", "size", "M3"),
            ),
        ),
        closing=_(
            "Das Spiel Ihres Druckers messen Sie mit dem Beispiel „Kalibrieren“ und tragen es "
            "unter Bearbeiten → Material kalibrieren ein."
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
                    "Öffnen Sie „Beschriftung“ im Verlauf mit einem Doppelklick und schreiben "
                    "Sie Ihren eigenen Text."
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
                    "Die Lettern daneben sind ein eigener Körper. Drucker mit einem Werkzeug "
                    "drucken sie extra und kleben sie auf."
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
                    "3MF trägt die Filamente als Farbgruppen in den Slicer. STL kennt keine Farbe."
                )
            ),
        ),
        closing=_(
            "Beschriftungen liegen im Menü Erzeugen: jede Schrift kann einem "
            "Filament zugeordnet oder ein eigener Körper sein."
        ),
    ),
    Tour(
        example_id="skizze-mit-massen",
        intro=_(
            "Eine runde Platte, gezeichnet statt eingetippt. Der Unterschied zeigt sich, wenn "
            "Sie ein Maß ändern."
        ),
        steps=(
            TourStep(
                shows="viewport",
                text=_(
                    "Der Umriss ist ein Kreis mit einer Bedingung: Der Rand hat überall "
                    "denselben Abstand zum Mittelpunkt."
                ),
            ),
            TourStep(
                shows="parameters",
                text=_(
                    "Stellen Sie „Durchmesser“ auf 80. Umriss und Tasche folgen und bleiben "
                    "rund, weil die Bedingung die Änderung überlebt."
                ),
                done=_parameter_changed("durchmesser", 60.0),
            ),
            TourStep(
                shows="history",
                text=_(
                    "Die Tasche ist ein zweiter Umriss im Körper. Ihre Tiefe ändern Sie mit "
                    "einem Doppelklick auf „Tasche schneiden“."
                ),
            ),
        ),
        closing=_(
            "Skizzen liegen im Menü Erzeugen. Sie lohnen sich, wo ein Maß später noch stimmen muss."
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
                    "Die Toleranzleiter misst das Spiel, die Wandleiter die dünnste Wand, der "
                    "Fächer den steilsten Überhang ohne Stützen."
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
                    "Öffnen Sie „Anordnen“ mit einem Doppelklick und ändern Sie den Abstand. Die "
                    "drei Körper rücken sofort um."
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
                    "Tragen Sie die Werte unter Bearbeiten → Material kalibrieren ein. Sie "
                    "gelten dann für jede Passung, auch in alten Projekten."
                )
            ),
        ),
        closing=_(
            "Prüfen Sie Passungen mit dem verwendeten Material. Wiederholen Sie Druckproben, "
            "wenn sich Drucker, Material oder Druckeinstellungen ändern."
        ),
    ),
    Tour(
        example_id="aushoehlen-und-teilen",
        intro=_(
            "Ein massiver Klotz verbraucht Material, das keiner sieht. Dieses Projekt teilt ihn "
            "und höhlt beide Hälften aus."
        ),
        steps=(
            TourStep(
                shows="history",
                text=_(
                    "Im Verlauf steht „Teilen und verstiften“ vor „Aushöhlen“, denn eine hohle "
                    "Wand wäre zu dünn für Passstifte."
                ),
            ),
            TourStep(
                text=_(
                    "In jeder Schnittfläche stecken zwei Stifte. Ihr Spiel kommt aus dem "
                    "gewählten Materialprofil."
                )
            ),
            TourStep(
                shows="history",
                text=_(
                    "Öffnen Sie ein „Aushöhlen“ im Verlauf mit einem Doppelklick und stellen Sie "
                    "die Wandstärke auf 5 mm."
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
            # allein *Automatisch teilen*. Die vorbereitenden Operationen
            # stehen rechts bei der Auswahl; dieser eigene Ablauf bleibt
            # im Menü *Bearbeiten*.
            #
            # Schwerer wog der Inhalt: *Automatisch teilen* zerschneidet ein
            # Teil, **das nicht auf das Bett passt** (so steht es an seinem
            # eigenen Menüeintrag). Diese Tour teilt aber, um Material zu
            # sparen — wer ihrem Schlusssatz folgte, griff zu einer Funktion,
            # die seinen Fall gar nicht meint, und die beiden Wege, auf denen
            # er die Naht selbst legt, standen nirgends.
            "Zu große Teile teilt Bearbeiten → Automatisch teilen. Eigene Nähte legen „Teilen“ "
            "und „An gezeichneter Linie trennen“."
        ),
    ),
    Tour(
        example_id="zu-gross-automatisch-teilen",
        intro=_(
            "Eine Wandleiste von 60 cm ist zu lang für jedes übliche Bett. Automatisch teilen "
            "hat sie in drei Stücke zerlegt."
        ),
        steps=(
            TourStep(
                shows="history",
                text=_(
                    "Im Verlauf stehen zwei gewöhnliche Schritte „Teilen“. Weniger als drei "
                    "Stücke gehen auf ein 220er Bett nicht."
                ),
            ),
            TourStep(
                shows="viewport",
                text=_(
                    "In jeder Naht stecken zwei Stifte, ihr Spiel kommt aus dem Materialprofil."
                ),
            ),
            TourStep(
                shows="history",
                text=_(
                    "Öffnen Sie den ersten „Teilen“-Schritt mit einem Doppelklick und ändern Sie "
                    "die Position. Stifte und Passungen wandern mit."
                ),
                done=_first_op_number_changed("split_pinned", "position", -100.0),
            ),
            TourStep(
                shows="tools",
                text=_(
                    "Die Stücke liegen schon nebeneinander auf dem Bett. Die "
                    "Explosion in der Werkzeugzeile zeigt, wie sie zusammengehören."
                ),
            ),
        ),
        closing=_(
            "Für Ihr eigenes Modell: Bearbeiten → Automatisch teilen. Ein spiegelgleiches Teil "
            "wird in der Mitte geteilt."
        ),
    ),
    Tour(
        example_id="dose-mit-deckel",
        intro=_("Eine Dose mit Deckel vereint, was die anderen Beispiele einzeln zeigen."),
        steps=(
            TourStep(
                shows="parameters",
                text=_(
                    "Stellen Sie links die Höhe auf 60 mm. Der Deckel bleibt oben, und die "
                    "Kabeldurchführung wandert mit."
                ),
                done=_parameter_changed("hoehe", 40.0),
            ),
            TourStep(
                shows="history",
                text=_(
                    "Im Verlauf steht „Aushöhlen“ mit „Oben öffnen“. Erst die offene Seite macht "
                    "aus dem Hohlraum ein Fach."
                ),
            ),
            TourStep(
                shows="viewport",
                text=_(
                    "Der Deckel ist aus der Öffnung geschnitten, sein Kragen um das Spiel aus "
                    "dem Materialprofil kleiner."
                ),
            ),
            TourStep(
                shows="report",
                text=_(
                    "Zur Passung steht nichts im Prüfbericht, denn das Spiel stimmt mit dem "
                    "Materialprofil überein."
                ),
            ),
        ),
        closing=_(
            "Für eine eigene Schachtel die Fläche an der Öffnung anklicken, dann Erzeugen → "
            "Bausteine → Deckel erzeugen."
        ),
    ),
    # **Die einzige Tour, die mit einer Warnung anfängt.** Die anderen zeigen,
    # wie etwas geht; diese zeigt, was zu tun ist, wenn etwas nicht mehr geht —
    # und beides gehört in eine Dokumentation, die den Kunden ernst nimmt.
    Tour(
        example_id="passung-nach-materialwechsel",
        intro=_(
            "Der Deckel soll aus weichem TPU sein, doch sein Spiel reicht dafür nicht. So "
            "beheben Sie die Warnung."
        ),
        steps=(
            TourStep(
                shows="report",
                text=_(
                    "Die Meldung im Prüfbericht nennt das vorhandene Spiel von 0,20 mm und die "
                    "0,35 mm, die TPU braucht."
                ),
            ),
            TourStep(
                shows="report",
                text=_(
                    "Klicken Sie auf die Meldung. Die Ansicht fliegt an die Öffnung, und eine "
                    "Marke zeigt die Stelle."
                ),
            ),
            TourStep(
                # Die Differenz steht im Prüfbericht — dorthin zeigt der Schritt
                # (``tests/test_tour.py`` hält Ort und Text zusammen).
                shows="report",
                text=_(
                    "Soll der Deckel aus TPU bleiben, vergrößern Sie das Spiel um die Differenz "
                    "aus dem Prüfbericht."
                ),
            ),
            TourStep(
                shows="history",
                text=_(
                    "Nehmen Sie den letzten Schritt „Deckel aus TPU“ im Verlauf mit Strg+Z "
                    "zurück. Die Warnung verschwindet."
                ),
                done=_op_gone("set_material"),
            ),
        ),
        closing=_(
            "Niemand musste nachrechnen. Wer das Material wechselt, erfährt beim Öffnen, welche "
            "Passungen es betrifft."
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
