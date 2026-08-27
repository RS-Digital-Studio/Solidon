"""Ein Vorschlag, eine Transaktion (Bauplan §26.5, AGENTS.md Regel 16).

Alles, was ein Agentenzug ändern will, wird hier gesammelt und in einem Zug
angewandt — oder gar nicht. Genau das macht „ein Undo nimmt es zurück" wahr
statt bloß gewollt, und darum werden die Operationen gesammelt, statt einzeln
angewandt zu werden, während das Modell noch redet.

Parameter und Passungen sind keine Operationen, eine Transaktion allein nähme
sie also nicht zurück. Der Vorschlag trägt darum mit, was sie vorher waren,
und ihn zurückzunehmen stellt genau das wieder her.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.scene.history import OperationDraft
from app.core.types import Finding, Fit, Origin, Parameter, ParameterName, TransactionId


@dataclass(slots=True)
class Question:
    """Eine Sache, die der Agent gefragt hat, statt zu raten (§26.2)."""

    text: str
    options: tuple[str, ...] = ()
    answer: str | None = None


@dataclass(slots=True)
class Proposal:
    """Was eine Anfrage erzeugt hat, bevor jemand sie angenommen hat."""

    request: str
    answer: str = ""
    drafts: list[OperationDraft] = field(default_factory=list)
    parameters: dict[ParameterName, Parameter] = field(default_factory=dict)
    """Parameter, die der Vorschlag hinzufügen oder ändern will."""
    fits: list[Fit] = field(default_factory=list)
    print_target: tuple[str, str] | None = None
    """(Drucker, Material) nach einem Wechsel über ``set_print_target`` —
    reist als ``DocumentChange`` in der Transaktion, wie Parameter auch."""
    readings: list[str] = field(default_factory=list)
    """Welche lesenden Werkzeuge der Zug benutzt hat — die Suite misst
    daran, ob eine Frage nachgesehen oder geraten wurde (§40)."""
    undo_of: TransactionId | None = None
    undo_sweeps: tuple[TransactionId, ...] = ()
    """Welche Transaktionen ein ``undo_of`` **wirklich** zurücknimmt — die
    genannte und jede jüngere, von der jüngsten an aufgezählt.

    Undo ist ein Stapel und kennt keine Verzweigungen (§15.4): Zu einem
    älteren Eintrag zu kommen heißt, die neueren mitzunehmen. Solange das
    nirgends stand, kündigte der Vorschlag eine Transaktion an und nahm vier
    zurück (Regel 16). Es gibt keinen Weg, einen Eintrag aus der Mitte
    herauszupflücken — also wird gesagt, was geschieht, und die Annahme prüft,
    dass es beim Anwenden noch dieselben sind.

    Ist die genannte Transaktion die jüngste, steht hier genau sie."""
    questions: list[Question] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    """Was die Prüfung nach jeder Operation gefunden hat (§26.5)."""
    origin: Origin = field(default_factory=lambda: Origin(by="agent"))
    steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    """Alle Werkzeugaufrufe des Zuges — der Nenner der Kennzahl aus §40."""
    invalid_calls: int = 0
    """Aufrufe, die die Mechanik ablehnen musste, bevor gerechnet wurde.

    Die Linie: **alles, was ohne Rechnung abgelehnt wird, zählt** —
    unbekanntes Werkzeug, schemaungültige Werte, geratene Skizzenparameter,
    unbekannte Referenzen (Transaktion, Parameter, Objekt-ID, Tabelle,
    Analyseart, Profil), die Misch-Schranke aus Regel 16 und Bedienfehler
    beim Anwenden (``UserError``). Geometrische Ablehnungen zählen nicht:
    dass eine Boolesche Operation am Netz scheitert, ist ein Ergebnis der
    Rechnung und kein Fehlgriff des Aufrufers — die Quote misst das Modell,
    nicht das Netz."""
    stopped: str = ""
    """Gesetzt, wenn der Zug nicht von selbst geendet hat.

    Vier Gründe: ``steps`` und ``tokens`` sind die harten Grenzen aus §26.5,
    ``truncated`` und ``refused`` kommen vom Modell (``stop_reason``). Die
    beiden letzten tragen zusätzlich einen Befund mit dem, was jetzt hilft —
    eine Kennung allein erklärt niemandem etwas."""

    @property
    def changes_geometry(self) -> bool:
        return bool(self.drafts)

    @property
    def creates_something(self) -> bool:
        """Ob der Vorschlag etwas anlegt oder ändert — die eine Bedingung für
        die Misch-Schranke aus Regel 16 (§15.4).

        Sie stand dreimal ausgeschrieben, und die dritte Stelle driftete ab:
        die Schranke in der Sitzung kannte das Druckziel nicht, und ein Zug
        aus ``set_print_target`` und ``undo_transaction`` baute einen
        Vorschlag, den die Annahme nur noch mit einer Ausnahme quittieren
        konnte.
        """
        return bool(self.drafts or self.parameters or self.fits or self.print_target)

    @property
    def empty(self) -> bool:
        """Ein Vorschlag, der nur geantwortet hat — nichts anzunehmen, nichts
        zurückzunehmen.
        """
        return not (self.creates_something or self.undo_of)

    @property
    def asked(self) -> bool:
        return bool(self.questions)

    def summary(self) -> str:
        """Eine Zeile für den Verlaufseintrag und den Chat.

        Ein Zug, der nur zurücknimmt, hatte hier nichts zu sagen: keine
        Entwürfe, oft kein Antworttext — der Chatbeitrag blieb leer. Was er
        tut, steht in :attr:`undo_sweeps`, und dort steht auch, wie viele
        Schritte wirklich zurückgehen.
        """
        if self.answer:
            return self.answer.strip().splitlines()[0]
        if self.drafts:
            return ", ".join(draft.op for draft in self.drafts)
        if self.undo_of:
            return f"undo {', '.join(self.undo_sweeps or (self.undo_of,))}"
        return ""
