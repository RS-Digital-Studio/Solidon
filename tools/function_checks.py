"""Das Prüfschema des Funktionsdurchgangs: Prüfpunkte, Kriterien, Schwellen (RM-737, D0-U).

Der Prüfstand (``tools/file_acceptance.py`` mit ``tools/function_bench.py``)
fährt je Funktion einen Fall am echten Fenster und schreibt das Messprotokoll
``cases/<nr>/function.json`` (Konzept §5, Stufe A). Hier steht, wonach es
beurteilt wird: die 19 Prüfpunkte (:data:`CHECKPOINTS`), die 35 Kriterien E1
bis I6 (:data:`CRITERIA`) mit Stufe, Schwelle und Quelle, die Wertebereiche
der Urteile und das Schema des Protokolls (:data:`PROTOCOL_SCHEMA`).

Drei Module teilen sich die Arbeit, damit keines die Größengrenze der
Codestruktur (2 000 Zeilen, W1) reißt:

* hier das Schema und das Datenmodell,
* ``tools/function_judges.py`` die Urteilsfunktion je Prüfpunkt und Kriterium,
* ``tools/function_samples.py`` die Gegenproben (``BROKEN_SAMPLES``).

**Was gemessen werden kann, wird gemessen; was ein Urteil ist, bleibt Stufe
B.** Ein Prüfpunkt, dessen Stufe-A-Teil besteht, heißt deshalb nicht
„erfüllt“, wenn er auch ein Urteil verlangt, sondern ``stufe_b``. Fehlt ein
Feld im Protokoll, heißt das „nicht gelaufen“ und nie „gut“.

**Die Schwellen haben je eine Quelle.** Wo die Anwendung die Zahl führt,
kommt sie von dort (``op_dialog``, ``style``, ``motion``, ``loading``,
``session``); die übrigen stehen hier als Konstante. Die Kriterientabellen in
den Skills ``ux-review`` (E, V) und ``ui-design`` (G, Z, I) sind die Quelle für
Menschen — ``tests/test_function_report.py`` hält Skill-Text und Konstante
über :func:`skill_mismatches` gleich (gehaltener Zwilling mit Wächter,
``.claude/rules/zwillinge.md``).

Kein Einstieg: Aufgerufen wird über ``tools/file_acceptance.py report``
(``tools/function_report.py``) und aus der Suite.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from dataclasses import fields as dataclass_fields
from typing import Any, Final, get_args

from app.core.units import DISPLAY_UNITS
from app.ui.guide_targets import ClickReason, Zone
from app.ui.loading import BAR_AFTER_MS, DELAY_MS
from app.ui.manual_window import ManualWindow
from app.ui.motion import ACCENT_MS, MEDIUM_MS
from app.ui.op_dialog import (
    MAX_FRONT_FIELDS,
    MAX_LEAD_WORDS,
    MAX_LEAD_WORDS_TRANSLATED,
)
from app.ui.style import LEVELS, SPACE
from tools.function_list import ROW_KINDS, Row

# --- Wertebereiche --------------------------------------------------------

#: Stufen des Prüfschemas (Konzept §5).
STAGES: Final = ("A", "B", "C")

#: Ergebnis je Prüfpunkt oder Kriterium (Konzept §4). ``nicht_gelaufen``
#: heißt: Das Protokoll trägt die Messung nicht — ist die Stufe C, steht in der
#: Abhakliste „C“, sonst „?“.
RESULTS: Final = ("erfuellt", "fund", "entfaellt", "stufe_b", "nicht_gelaufen", "nicht_pruefbar")

#: Die geschlossene Liste der Gründe für *entfällt* (Konzept §4, „Urteil und
#: Schwere“). Ein anderer Grund wird abgewiesen.
NOT_APPLICABLE: Final[dict[str, str]] = {
    "ohne_rechnung": "Operation ohne Rechnung",
    "ohne_auswahlbezug": "ohne Auswahlbezug",
    "ohne_dialog": "ohne Dialog",
    "ohne_agentenwerkzeug": "ohne Agentenwerkzeug",
    "nur_stufe_c": "nur Stufe C",
}

#: Schwere eines Funds, von schwer nach leicht (Konzept §4).
SEVERITIES: Final = ("schwer", "mittel", "leicht", "Vorschlag")

#: Arten eines Funds (Konzept §7).
FINDING_KINDS: Final = (
    "Leistung",
    "Stabilität",
    "Fehler",
    "Zwillinge",
    "Aufräumen",
    "Einfachheit",
    "Verständlichkeit",
    "Gestaltung",
)

#: Warum ein Schritt geklickt wurde, und die Bereiche des Fensters für E4: die
#: Werte von ``guide_targets.ClickReason`` und ``Zone`` (Teilpaket W), gelesen
#: statt abgeschrieben. Nur ``ziel`` ist die Handlung selbst; alles andere ist ein
#: Wegklick.
WHY: Final[tuple[str, ...]] = get_args(ClickReason)
ZONES: Final[tuple[str, ...]] = get_args(Zone)

#: Die sechs Auswahlstufen von Prüfpunkt 13 (Konzept Funktionsdurchgang §4).
SELECTION_STAGES: Final = (
    "ohne",
    "ein_koerper",
    "mehrere_koerper",
    "ein_merkmal",
    "mehrere_merkmale",
    "eine_kante",
)

#: Wie ein Ziel an einer Auswahlstufe dasteht (Prüfpunkt 13); ``nicht
#: herstellbar`` heißt, der Prüfstand konnte die Auswahl nicht herstellen —
#: gemessen ist dann nichts, und das sagt der Vermerk.
MATRIX_UNREACHABLE: Final = "nicht herstellbar"
MATRIX_STATES: Final = ("angeboten", "grau", "fehlt", MATRIX_UNREACHABLE)

#: Die Lizenzzustände eines Laufs (Prüfpunkt 18) und ob Schreibendes in ihnen
#: offensteht (``Activation.unlocked``). Die Anwendung führt keine Aufzählung,
#: sie liest den Zustand an Eigenschaften von ``app.core.activation.Activation``
#: ab; deren Namen sind die Zustände. Ein Wächter setzt jeden Zustand wie die
#: Suite über ``activation._cached`` und prüft Eigenschaft und Freischaltung.
#:
#: ``over`` (Demo abgelaufen) ist kein Lauf: Dort startet die Anwendung nicht
#: (``app.ui.app``, ``show_expired_demo``) — das prüft eine eigene Zeile des
#: Pakets D12. ``in_demo`` ist auch nach dem Demo-Ende wahr und kein Zustand.
LICENCE_UNLOCKED: Final[dict[str, bool]] = {
    "sale_without_trial": False,
    "needs_activation": False,
    "licensed": True,
    "expired": False,
}
LICENCE_STATES: Final = tuple(LICENCE_UNLOCKED)
#: Gesperrt heißt: Schreibendes ist grau mit Grund, nur Lesendes läuft weiter.
LOCKED_STATES: Final = frozenset(state for state, open_ in LICENCE_UNLOCKED.items() if not open_)


def licence_runs() -> tuple[str, ...]:
    """Die Läufe, die Prüfpunkt 18 je Zeile verlangt: die erreichbaren Zustände.

    Ohne ``store.TRIAL_FROM`` (die Verkaufsversion) gibt es keinen Testlauf,
    also auch keinen abgelaufenen — wer keinen Schlüssel hat, sieht die lesende
    Verkaufsversion. Mit ``TRIAL_FROM`` ist es umgekehrt. Kaufcode ohne
    Gerätefreigabe und gekauft gibt es in beiden.
    """
    from app.core.activation.store import TRIAL_FROM

    first = "sale_without_trial" if TRIAL_FROM is None else "expired"
    return (first, "needs_activation", "licensed")


#: Die zwei Wege zum Ändern eines Schritts (Prüfpunkt 12): *Diesen Schritt
#: ändern* im Menü und der Doppelklick im Verlauf (Konzept §4).
REVISE_WAYS: Final = ("menue", "doppelklick")

#: Wann der Projektwechsel geprüft wird (Prüfpunkt 16): während Vorschau,
#: Entwurf und Rechnung (Konzept §4).
SWITCH_PHASES: Final = ("vorschau", "entwurf", "rechnung")

#: Die Phasen des Prüfstands, die der Hauptweg zum Beispielziel sind. Nur ihre
#: Schritte zählen für Prüfpunkt 2 und E1 bis E4; Suche, Escape, Matrix,
#: Fehlfall und die übrigen Phasen klicken auch, aber nicht auf dem Weg des
#: Kunden (Festlegung Koordinator).
MAIN_PHASES: Final = ("weg", "übernehmen")

#: Was der Prüfstand unterwegs findet (``findings[].kind``): ein Klickziel, über
#: dem etwas anderes liegt, und ein Ziel, zu dem kein Weg führt (Konzept §5).
COVERED: Final = "verdeckt"
NOT_FOUND: Final = "nicht auffindbar"
BENCH_FINDINGS: Final = (COVERED, NOT_FOUND)

#: Rohe Qt-Fenster, die im Kundenweg nicht erscheinen (Z5).
RAW_CLASSES: Final = frozenset({"QMessageBox", "QInputDialog", "QColorDialog"})

#: Das Handbuchfenster: Muss der Kunde es öffnen, ist V6 verletzt.
MANUAL_WINDOW: Final = ManualWindow.__name__

#: Der Satz im Vorschauband einer groben Vorschau (Prüfpunkt 3) — die
#: Message-ID aus ``MainWindow._show_preview``. Ein Wächter in der Suite hält
#: sie: Steht sie in keinem Katalog mehr, hat die Anwendung den Satz geändert.
COARSE_NOTE: Final = "Grobe Vorschau — beim Übernehmen wird genau gerechnet"

#: Warum ein Urteil abgewiesen wird, wo es der Messung der Stufe A
#: widerspricht — die Gegenproben verlangen genau diese Gründe.
GOOD_OVER_FINDING: Final = "„gut“ gegen einen Fund der Stufe A"
UNMEASURED_VERDICT: Final = "„gut“ ohne Messung der Stufe A"
NOT_APPLICABLE_OVER_FINDING: Final = "entfällt gegen einen Fund der Stufe A"

# --- Schwellen ohne Codequelle (Wächter gegen die Skills) ------------------

#: E1: Klicks bis zum Ergebnis mit den Vorgaben, am Merkmal nach der Auswahl.
MAX_CLICKS: Final = 3
MAX_CLICKS_AT_FEATURE: Final = 2
#: E2: Pflichteingaben bis zum Beispielziel, bei diesem Anteil der Funktionen.
MAX_INPUTS: Final = 1
INPUT_SHARE: Final = 0.9
#: E3: Entscheidungen, die Vorwissen verlangen.
MAX_DECISIONS: Final = 1
#: E4: Blickwechsel zwischen den Bereichen des Fensters.
MAX_GLANCES: Final = 2
#: E6, E7, V1 und Z5: Was gar nicht vorkommen darf.
MAX_QUESTIONS: Final = 0
MAX_DEAD_ENDS: Final = 0
MAX_NEGATIVE_WORDS: Final = 0
MAX_RAW_WINDOWS: Final = 0
#: V3: Anteil der Felder mit eigenem Satz und größter Anteil seiner Wörter,
#: die er mit dem Titel teilt.
OWN_SENTENCE_SHARE: Final = 1.0
MAX_TITLE_OVERLAP: Final = 0.5
#: V6: Kurzhilfen, die man bis zum Ziel öffnen muss.
MAX_SHORT_HELPS: Final = 1
#: G1: Hauptaktionen je Dialog oder Karte, Akzente je Fenster.
MAX_PRIMARY: Final = 1
MAX_ACCENTS: Final = 1
#: G6: Kontrast für normale Schrift, für große Schrift und Symbole.
MIN_CONTRAST: Final = 4.5
MIN_CONTRAST_LARGE: Final = 3.0
#: Z1: Verzug bis zum nächsten gemalten Bild beim Ziehen, auf die Referenz
#: umgerechnet (Bauplan §31).
MAX_DRAG_MS: Final = 33
#: Z6: Die Startgröße des Fensters (``MainWindow.__init__``, ein Wächter hält
#: sie), der Laptop mit Taskleiste und die Skalierungen.
START_SIZE: Final = (1280, 820)
LAPTOP_SIZE: Final = (1366, 728)
SCALES: Final = (1.0, 1.5, 2.0)
#: I3: Anteil der häufigsten Kundenziele, die ohne Suche dastehen.
GOAL_SHARE: Final = 0.8
#: Prüfpunkt 1 und I6: höchster Rang eines Suchtreffers.
MAX_RANK: Final = 3
#: Prüfpunkt 6: größte Lücke im Hauptfaden.
MAIN_GAP_MS: Final = 100
#: Übereinstimmung zweier Prüfer je Prüfpunkt (Konzept §4).
AGREEMENT: Final = 0.9
#: Anteil der Zeilen, die ein zweiter Prüfer unabhängig urteilt (Konzept §4).
SECOND_REVIEW_SHARE: Final = 0.1

#: Prüfpunkt 6 und 14: ab wann Zeiger, ab wann Balken und *Abbrechen* (Bauplan §2.8,
#: aus ``app.ui.loading``).
FEEDBACK_AFTER_S: Final = DELAY_MS / 1000
BAR_AFTER_S: Final = BAR_AFTER_MS / 1000

# --- Das Messprotokoll -------------------------------------------------------

#: Die Schlüssel einer Zeile: die Felder von ``function_list.Row`` (Teilpaket L),
#: die Arten (``ROW_KINDS``) ebenfalls von dort.
ROW_KEYS: Final = frozenset(item.name for item in dataclass_fields(Row))

#: Wo der Kunde eine Funktion findet (``place.where``, Prüfpunkt 1 und 17).
PLACES: Final = ("karte", "menue", "werkzeugleiste", "kuerzel", "kontext")

#: Die Szenenabdrücke in ``states`` (Konzept §5, Stufe A); ``aborted`` ist der Stand nach
#: *Abbrechen* der Rechnung (Prüfpunkt 14), ``cancelled`` der Abbruch im Dialog.
STATE_KEYS: Final = (
    "before",
    "preview",
    "applied",
    "undo",
    "redo",
    "escape",
    "cancelled",
    "aborted",
    "after_switch",
)


@dataclass(frozen=True)
class ProtocolField:
    """Ein Feld des Messprotokolls: Form, Schlüssel und erlaubte Werte.

    ``shape`` ist ``tabelle`` (ein Objekt), ``liste`` (eine Liste von
    Objekten), ``texte`` (eine Liste von Texten), ``text``, ``zahl`` oder
    ``wahr``. ``keys`` sind bei einer Tabelle ihre Schlüssel, bei einer Liste
    die Schlüssel jedes Eintrags; ``None`` heißt frei (Suchproben, Abdrücke).
    ``values`` legt für einzelne Schlüssel die erlaubten Werte fest, ``choices``
    die eines einzelnen Texts, ``needs`` die Pflichtschlüssel der Einträge.
    """

    shape: str
    keys: frozenset[str] | None = None
    values: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    choices: tuple[str, ...] = ()
    required: bool = False
    #: Schlüssel, die jeder Eintrag einer Liste tragen muss.
    needs: frozenset[str] = frozenset()


def _keys(*names: str) -> frozenset[str]:
    return frozenset(names)


#: Das Schema des Messprotokolls ``cases/<nr>/function.json`` (Konzept §5, Stufe A
#: mit den Ergänzungen dieses Pakets, Bericht „Schnittstelle“). Es gehört D0-U;
#: der Prüfstand schreibt danach und prüft sich mit :func:`validate_protocol`.
#: Ein unbekanntes Feld oder ein unbekannter Schlüssel ist eine ungültige
#: Eingabe — sonst wüchse das Protokoll an einer Stelle, die niemand liest.
PROTOCOL_SCHEMA: Final[dict[str, ProtocolField]] = {
    "row": ProtocolField(
        "tabelle",
        ROW_KEYS,
        {"kind": ROW_KINDS},
        required=True,
    ),
    "kind": ProtocolField("text", choices=ROW_KINDS, required=True),
    "package": ProtocolField("text", required=True),
    "spec": ProtocolField(
        "tabelle",
        _keys(
            "start_scene", "route", "example_goal", "inputs", "search_probes", "questions",
            "expectation", "fault_case", "preconditions", "not_applicable", "budget_s",
            "budget_ref", "criteria",
        ),
    ),
    "variant": ProtocolField(
        "tabelle",
        _keys(
            "language", "theme", "unit", "licence", "preconditions", "platform", "screen",
            "scale", "window_size", "motion", "set", "phases", "placed",
        ),
        {"theme": ("light", "dark"), "unit": DISPLAY_UNITS, "licence": LICENCE_STATES},
        required=True,
    ),
    "version": ProtocolField("tabelle", _keys("commit", "app"), required=True),
    "scene": ProtocolField("tabelle", _keys("key", "triangles", "build_s", "eval_s")),
    "steps": ProtocolField(
        "liste",
        _keys(
            "target", "why", "button", "rect", "point", "widget_at", "hit", "zone", "typed",
            "key", "decision", "t", "phase", "finding", "detail",
        ),
        {"why": WHY, "zone": ZONES, "finding": BENCH_FINDINGS},
        needs=_keys("phase"),
    ),
    "states": ProtocolField("tabelle", frozenset(STATE_KEYS)),
    "preview": ProtocolField(
        "tabelle", _keys("bodies", "coarse", "banner_text", "volume", "extent")
    ),
    "result": ProtocolField("tabelle", _keys("metrics", "digest")),
    "cli": ProtocolField("tabelle", _keys("digest", "max_deviation_mm", "print_equal")),
    "timing": ProtocolField(
        "tabelle",
        _keys(
            "total_s", "first_feedback_s", "progress_shown_s", "cancel_shown_s", "main_gap_ms",
            "budget_s",
        ),
    ),
    "frames": ProtocolField("tabelle", _keys("drag_ms", "reference_factor")),
    "modals": ProtocolField("liste", _keys("class", "title", "allowed", "question")),
    "raw_windows": ProtocolField("liste", _keys("class", "title", "allowed")),
    "windows": ProtocolField("liste", _keys("class", "title")),
    "messages": ProtocolField("liste", _keys("text", "actions")),
    "texts": ProtocolField("liste", _keys("text", "carrier", "need_px", "width_px", "cut", "lead")),
    "fields": ProtocolField(
        "liste", _keys("label", "accessible_name", "description", "tooltip", "front")
    ),
    "tab_chain": ProtocolField("liste", _keys("name", "rect")),
    "names": ProtocolField("texte"),
    "focus_return": ProtocolField("wahr"),
    "matrix": ProtocolField("tabelle", frozenset(SELECTION_STAGES)),
    "search": ProtocolField("tabelle"),
    "place": ProtocolField("tabelle", _keys("where", "path", "error"), {"where": PLACES}),
    "spot": ProtocolField("tabelle", _keys("point", "covered_by")),
    "layout": ProtocolField(
        "liste",
        _keys(
            "kind", "surface", "primary", "accents", "group", "spacing", "margins",
            "label_edges", "field_edges", "values",
        ),
        {"kind": ("primary", "spacing", "form")},
    ),
    "fonts": ProtocolField("liste", _keys("surface", "widget", "level", "stylesheet")),
    "state_images": ProtocolField("liste", _keys("surface", "widget", "states")),
    "contrast": ProtocolField(
        "liste",
        _keys("surface", "widget", "theme", "foreground", "background", "large", "symbol"),
        {"theme": ("light", "dark")},
    ),
    "icons": ProtocolField(
        "liste",
        _keys(
            "surface", "widget", "text", "icon", "own", "tooltip", "shortcut", "style", "scale",
            "pixmap_ratio",
        ),
    ),
    "animations": ProtocolField("liste", _keys("surface", "widget", "duration_ms")),
    "scrollbars": ProtocolField(
        "liste", _keys("surface", "window_size", "front", "vertical", "horizontal")
    ),
    "hover_labels": ProtocolField("liste", _keys("kind", "label")),
    "empty_states": ProtocolField("liste", _keys("surface", "sentence", "button", "intended")),
    "licence_runs": ProtocolField("tabelle", frozenset(LICENCE_STATES)),
    "halt": ProtocolField("tabelle", _keys("text", "step")),
    "insertion": ProtocolField(
        "tabelle", _keys("outcome", "text", "actions"), {"outcome": ("ergebnis", "absage")}
    ),
    "switch": ProtocolField("tabelle", _keys("phases", "late_events")),
    "revise": ProtocolField(
        "liste",
        _keys("way", "opened", "fields", "params", "history_before", "history_after"),
        {"way": REVISE_WAYS},
    ),
    "abort": ProtocolField("tabelle", _keys("eval_s", "cancel_shown_s", "clicked")),
    "findings": ProtocolField(
        "liste", _keys("phase", "kind", "target", "detail"), {"kind": BENCH_FINDINGS}
    ),
    "closed_by_escape": ProtocolField("liste", _keys("phase", "times")),
    "unmeasured": ProtocolField("tabelle"),
    "images": ProtocolField("texte"),
    "errors": ProtocolField("texte"),
}  # fmt: skip

#: Die Felder des Protokolls.
PROTOCOL_FIELDS: Final = frozenset(PROTOCOL_SCHEMA)
#: Pflichtfelder jedes Protokolls.
REQUIRED_FIELDS: Final = tuple(name for name, spec in PROTOCOL_SCHEMA.items() if spec.required)


# --- Datenmodell ----------------------------------------------------------


@dataclass(frozen=True)
class Issue:
    """Ein gemessener Verstoß mit vorgeschlagener Schwere (Konzept §4)."""

    text: str
    severity: str
    criterion: str | None = None


@dataclass(frozen=True)
class Outcome:
    """Das Ergebnis eines Prüfpunkts oder Kriteriums an einem Fall (Konzept §4).

    ``subject`` ist die Nummer des Prüfpunkts oder die Kennung des
    Kriteriums; :meth:`record` schreibt sie als ``point`` oder ``criterion``.
    """

    subject: int | str
    stage: str
    verdict: str
    summary: str = ""
    measurement: Mapping[str, Any] = field(default_factory=dict)
    issues: tuple[Issue, ...] = ()
    reason: str = ""
    notes: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    finding: str | None = None

    def record(self) -> dict[str, Any]:
        """Das Ergebnis als Eintrag nach Konzept §4."""
        key = "point" if isinstance(self.subject, int) else "criterion"
        return {
            key: self.subject,
            "stage": self.stage,
            "measurement": dict(self.measurement),
            "verdict": self.verdict,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "finding": self.finding,
            "summary": self.summary,
            "issues": [
                {"text": issue.text, "severity": issue.severity, "criterion": issue.criterion}
                for issue in self.issues
            ],
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class Context:
    """Was ein Urteil außerhalb des Protokolls braucht.

    Aus dem Baum gebaut über ``function_report.repository_context``; die
    Gegenproben setzen ihre eigenen Werte (``function_samples.sample_context``).
    Die Funktionen bekommen die Zeile nach Konzept §3.
    """

    #: V1: die Negativliste als (Wort, Sprache, Suchmuster), das Muster nach
    #: ``re`` wie in ``tests/data/customer_vocabulary.json``.
    negative_words: tuple[tuple[str, str, str], ...]
    #: V2: die eingefrorenen zu langen Texte.
    frozen_texts: frozenset[str]
    #: Prüfpunkt 3: der Satz der groben Vorschau in einer Sprache.
    coarse_note: Callable[[str], str]
    #: Prüfpunkt 11: Seite und Stelle im Handbuch, ``None`` ohne Stelle.
    manual_place: Callable[[Mapping[str, Any]], str | None]
    #: Prüfpunkt 11: Website-Seiten, die die Funktion nennen.
    website_hits: Callable[[Mapping[str, Any]], tuple[str, ...]]
    #: Prüfpunkt 17: Ort laut Agentenwerkzeug (``menue``, ``karte``,
    #: ``katalog``) und sein Menüpfad, ``None`` ohne Werkzeug.
    agent_place: Callable[[Mapping[str, Any]], tuple[str, str] | None]
    #: I3: die Ziele (``target``) der häufigsten Kundenziele. Nur an ihren
    #: Zeilen wird I3 gemessen; der Anteil steht in den Paketwerten.
    common_goal_targets: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CaseOutcome:
    """Alle Ergebnisse eines Falls: je Prüfpunkt eines, je geltendem Kriterium eines."""

    row: Mapping[str, Any]
    variant: Mapping[str, Any]
    points: Mapping[int, Outcome]
    criteria: Mapping[str, Outcome]
    problems: tuple[str, ...] = ()

    @property
    def row_id(self) -> str:
        return str(self.row.get("id", ""))

    def get(self, subject: int | str) -> Outcome | None:
        """Das Ergebnis eines Prüfpunkts oder Kriteriums, ``None``, wo es nicht gilt."""
        if isinstance(subject, int):
            return self.points.get(subject)
        return self.criteria.get(subject)


@dataclass(frozen=True)
class Checkpoint:
    """Ein Prüfpunkt des Schemas (Konzept §4)."""

    number: int
    title: str
    stages: tuple[str, ...]
    fields: tuple[str, ...]
    #: Kriterien, deren Ergebnis in diesen Prüfpunkt eingeht.
    parts: tuple[str, ...] = ()
    #: Zahlen der Schwelle, die ein Skill nennt, falls er den Prüfpunkt führt.
    numbers: tuple[float, ...] = ()


@dataclass(frozen=True)
class Criterion:
    """Ein Kriterium aus Einfachheit, Verständlichkeit oder Gestaltung (Konzept §4)."""

    key: str
    measure: str
    threshold: str
    numbers: tuple[float, ...]
    stages: tuple[str, ...]
    source: str
    fields: tuple[str, ...]
    #: G9, Z3, Z4, I1 bis I6: ein Urteil dazu ist ein Gestaltungsurteil.
    design_judgement: bool = False
    #: Bauplanzusage: ein Fehlen ist ein Fund, kein Vorschlag (I1, I5).
    promised: bool = False

    @property
    def group(self) -> str:
        return self.key[0]

    @property
    def skill(self) -> str:
        """Welcher Skill die Tabelle führt: E und V ``ux-review``, sonst ``ui-design``."""
        return "ux-review" if self.group in "EV" else "ui-design"


# --- Zählen ---------------------------------------------------------------


def words(text: str) -> int:
    """Wörter wie ein Leser sie zählt: alles mit einem Buchstaben oder einer Ziffer.

    Die eine Zählung für E5 hier und für die Lead-Grenze in
    ``tests/test_interface_limits.py``.
    """
    return sum(1 for word in text.split() if any(char.isalnum() for char in word))


# --- Tabellen --------------------------------------------------------------


#: Die Kriterien, die in Prüfpunkt 19 (Gestaltung) eingehen.
DESIGN_PARTS: Final = (
    "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9",
    "Z1", "Z2", "Z3", "Z4", "Z5", "Z6", "Z7",
    "I1", "I2", "I3", "I5", "I6",
)  # fmt: skip


def _criterion(
    key: str,
    measure: str,
    threshold: str,
    numbers: Iterable[float],
    stages: str,
    fields_: tuple[str, ...],
    source: str = "tools/function_checks.py",
    *,
    design: bool = False,
    promised: bool = False,
) -> Criterion:
    return Criterion(
        key=key,
        measure=measure,
        threshold=threshold,
        numbers=tuple(float(n) for n in numbers),
        stages=tuple(stages),
        source=source,
        fields=fields_,
        design_judgement=design,
        promised=promised,
    )


#: Die 35 Kriterien (Konzept §4) mit Stufe, Schwelle
#: und Quelle (Konzept §4). ``numbers`` sind die Zahlen, die die Schwelle im Skill
#: nennen muss.
CRITERIA: Final[dict[str, Criterion]] = {
    c.key: c
    for c in (
        _criterion(
            "E1",
            "Klicks bis zum Ergebnis mit den Vorgaben",
            f"≤ {MAX_CLICKS}; am Merkmal ≤ {MAX_CLICKS_AT_FEATURE} nach der Auswahl",
            (MAX_CLICKS, MAX_CLICKS_AT_FEATURE),
            "AB",
            ("steps",),
        ),
        _criterion(
            "E2",
            "Pflichteingaben bis zum Beispielziel",
            f"≤ {MAX_INPUTS} bei {INPUT_SHARE:.0%} der Funktionen",
            (MAX_INPUTS, INPUT_SHARE * 100),
            "A",
            ("steps",),
        ),
        _criterion(
            "E3",
            "Entscheidungen, die Vorwissen verlangen",
            f"≤ {MAX_DECISIONS}",
            (MAX_DECISIONS,),
            "AB",
            ("steps",),
        ),
        _criterion(
            "E4",
            "Blickwechsel zwischen den Bereichen des Fensters",
            f"≤ {MAX_GLANCES}; kein Dialog verdeckt die bearbeitete Stelle",
            (MAX_GLANCES,),
            "A",
            ("steps", "spot"),
        ),
        _criterion(
            "E5",
            "Felder vorn, Wörter über dem ersten Feld",
            f"≤ {MAX_FRONT_FIELDS - 1} Felder (höchstens {MAX_FRONT_FIELDS}); "
            f"≤ {MAX_LEAD_WORDS} Wörter, übersetzt ≤ {MAX_LEAD_WORDS_TRANSLATED}",
            (MAX_FRONT_FIELDS - 1, MAX_FRONT_FIELDS, MAX_LEAD_WORDS, MAX_LEAD_WORDS_TRANSLATED),
            "A",
            ("fields", "texts"),
            "app/ui/op_dialog.py",
        ),
        _criterion(
            "E6",
            "Nachfragen außerhalb der Ausnahmen von Regel 19",
            f"{MAX_QUESTIONS}",
            (MAX_QUESTIONS,),
            "A",
            ("modals",),
        ),
        _criterion(
            "E7",
            "Sackgassen",
            f"{MAX_DEAD_ENDS}",
            (MAX_DEAD_ENDS,),
            "A",
            ("matrix", "empty_states", "messages"),
        ),
        _criterion(
            "V1",
            "Wörter der Negativliste im sichtbaren Text",
            f"{MAX_NEGATIVE_WORDS}",
            (MAX_NEGATIVE_WORDS,),
            "A",
            ("texts",),
            "tests/data/customer_vocabulary.json",
        ),
        _criterion(
            "V2",
            "Satzlängen",
            "die Grenzen aus `test_text_length`",
            (),
            "A",
            ("texts",),
            "tests/data/text_lengths/",
        ),
        _criterion(
            "V3",
            "Felder mit eigenem Satz",
            f"{OWN_SENTENCE_SHARE:.0%}; höchstens die Hälfte der Wörter mit dem Titel geteilt",
            (OWN_SENTENCE_SHARE * 100, MAX_TITLE_OVERLAP * 100),
            "A",
            ("fields",),
        ),
        _criterion(
            "V4",
            "Vorhersage vor dem Übernehmen",
            "Abweichung vom Ergebnis ist ein Fund",
            (),
            "B",
            (),
        ),
        _criterion("V5", "Meldungen", "jede Handlung löst das Problem", (), "AB", ("messages",)),
        _criterion(
            "V6",
            "Kurzhilfen bis zum Ziel",
            f"≤ {MAX_SHORT_HELPS}; nie das Handbuch",
            (MAX_SHORT_HELPS,),
            "AB",
            ("windows",),
        ),
        _criterion(
            "G1",
            "Hauptknöpfe und Akzente",
            f"≤ {MAX_PRIMARY} Hauptaktion je Dialog oder Karte, ≤ {MAX_ACCENTS} Akzent je Fenster",
            (MAX_PRIMARY, MAX_ACCENTS),
            "A",
            ("layout",),
        ),
        _criterion(
            "G2",
            "Abstände",
            f"Vielfaches von `SPACE` ({SPACE}), je Gruppe einheitlich",
            (SPACE,),
            "A",
            ("layout",),
            "app/ui/style.py",
        ),
        _criterion(
            "G3", "Ausrichtung", "bündig; Werte rechtsbündig mit Einheit", (), "A", ("layout",)
        ),
        _criterion(
            "G4",
            "Schrift",
            "nur die Stufen aus `LEVELS`; keine Größe oder Farbe im Stylesheet",
            (len(LEVELS),),
            "A",
            ("fonts",),
            "app/ui/style.py",
        ),
        _criterion(
            "G5",
            "Zustände",
            "jeder unterscheidbar, zweite Kodierung, Fokus sichtbar",
            (),
            "AB",
            ("state_images",),
        ),
        _criterion(
            "G6",
            "Kontrast",
            f"≥ {MIN_CONTRAST:g}:1, große Schrift und Symbole ≥ {MIN_CONTRAST_LARGE:g}:1",
            (MIN_CONTRAST, MIN_CONTRAST_LARGE),
            "A",
            ("contrast",),
        ),
        _criterion(
            "G7",
            "Symbole",
            "Symbol aus dem eigenen Satz, Tooltip mit Name und Kürzel, ein Stil",
            (),
            "A",
            ("icons",),
        ),
        _criterion(
            "G8",
            "Bewegung",
            f"Übergang aus `motion`, {ACCENT_MS}-{MEDIUM_MS} ms, abschaltbar",
            (ACCENT_MS, MEDIUM_MS),
            "A",
            ("animations",),
            "app/ui/motion.py",
        ),
        _criterion(
            "G9",
            "Direkt statt Formular",
            "Gestaltungsurteil, höchstens leicht",
            (),
            "B",
            (),
            design=True,
        ),
        _criterion(
            "Z1",
            "Ziehen",
            f"≤ {MAX_DRAG_MS} ms bis zum nächsten Bild",
            (MAX_DRAG_MS,),
            "A",
            ("frames",),
        ),
        _criterion(
            "Z2", "Nicht-modal", "kein modales Fenster außer den Ausnahmen", (), "A", ("modals",)
        ),
        _criterion(
            "Z3",
            "Am Objekt",
            "ja je Zeile mit Merkmals- oder Körperbezug",
            (),
            "AB",
            ("steps",),
            design=True,
        ),
        _criterion(
            "Z4",
            "Leere Zustände führen weiter",
            "Knopf zur nächsten Handlung",
            (),
            "AB",
            ("empty_states",),
            design=True,
        ),
        _criterion(
            "Z5",
            "Rohe Qt-Fenster im Kundenweg",
            f"{MAX_RAW_WINDOWS}, außer `QFileDialog`",
            (MAX_RAW_WINDOWS,),
            "A",
            ("raw_windows",),
        ),
        _criterion(
            "Z6",
            "Größen und Skalierungen",
            f"{START_SIZE[0]} x {START_SIZE[1]} und {LAPTOP_SIZE[0]} x {LAPTOP_SIZE[1]} "
            "ohne Rollleiste vorn; Symbole scharf bei "
            + ", ".join(f"{scale:.0%}" for scale in SCALES),
            (*START_SIZE, *LAPTOP_SIZE, *(s * 100 for s in SCALES)),
            "A",
            ("scrollbars", "icons"),
        ),
        _criterion(
            "Z7",
            "Die ersten fünf Minuten",
            "Schritte und Fehlklicks, jeder Fehlklick ein Fund",
            (),
            "C",
            (),
        ),
        _criterion(
            "I1",
            "Name und Maß beim Überfahren",
            "ja an jeder erkannten Art",
            (),
            "AB",
            ("hover_labels",),
            design=True,
            promised=True,
        ),
        _criterion(
            "I2",
            "Druckfolge im Vorschauband",
            "ja an jeder Zeile mit gerechneter Vorschau",
            (),
            "AB",
            ("preview",),
            design=True,
        ),
        _criterion(
            "I3",
            "Vorschlag statt Suche",
            f"≥ {GOAL_SHARE:.0%} der häufigsten Kundenziele",
            (GOAL_SHARE * 100,),
            "A",
            ("steps",),
            "tests/data/common_goals.toml",
            design=True,
        ),
        _criterion(
            "I4",
            "Befund mit Lösung",
            "Zahl genannt; jede Art ohne Handlung ist ein Vorschlag",
            (),
            "A",
            (),
            design=True,
        ),
        _criterion(
            "I5",
            "Vorher und nachher",
            "ja an der Zeile Vorher/Nachher",
            (),
            "AB",
            ("steps",),
            design=True,
            promised=True,
        ),
        _criterion(
            "I6",
            "Sagen statt suchen",
            f"Rang ≤ {MAX_RANK}",
            (MAX_RANK,),
            "A",
            ("search",),
            design=True,
        ),
    )
}


CHECKPOINTS: Final[dict[int, Checkpoint]] = {
    c.number: c
    for c in (
        Checkpoint(1, "Auffindbar", ("A", "B"), ("place", "search"), numbers=(MAX_RANK,)),
        Checkpoint(
            2, "Weg", ("A", "B"), ("steps", "spot"), parts=("E1", "E3", "E4", "E5", "E6", "E7")
        ),
        Checkpoint(3, "Vorschau", ("A",), ("preview", "states", "result", "scene")),
        Checkpoint(4, "Ergebnis", ("A",), ("result", "cli", "spec")),
        Checkpoint(5, "Rückweg", ("A",), ("states",)),
        Checkpoint(
            6,
            "Rückmeldung und Zeit",
            ("A",),
            ("timing",),
            numbers=(MAIN_GAP_MS, FEEDBACK_AFTER_S, BAR_AFTER_S),
        ),
        Checkpoint(7, "Fehlerweg", ("A", "B"), ("messages", "spec"), parts=("V5",)),
        Checkpoint(
            8,
            "Verständlich",
            ("A", "B"),
            ("texts", "fields", "windows"),
            parts=("V1", "V2", "V3", "V6"),
        ),
        Checkpoint(9, "Sprachen und Darstellung", ("A", "B"), ("texts", "variant")),
        Checkpoint(
            10, "Tastatur und Zugänglichkeit", ("A",), ("tab_chain", "names", "focus_return")
        ),
        Checkpoint(11, "Versprechen", ("A", "B"), ("row",)),
        Checkpoint(12, "Nachträglich ändern", ("A",), ("revise",)),
        Checkpoint(13, "Auswahlstufen", ("A", "B"), ("matrix",)),
        Checkpoint(
            14, "Abbruch während der Rechnung", ("A",), ("abort", "states"), numbers=(BAR_AFTER_S,)
        ),
        Checkpoint(15, "Halt und Einfügemarke", ("A",), ("halt", "insertion")),
        Checkpoint(16, "Projektwechsel", ("A",), ("switch",)),
        Checkpoint(17, "Agentenweg", ("A",), ("place", "row")),
        Checkpoint(18, "Lizenzzustand", ("A",), ("licence_runs",)),
        Checkpoint(
            19,
            "Gestaltung",
            ("A", "B", "C"),
            ("layout", "fonts", "state_images", "contrast", "icons", "animations", "scrollbars"),
            parts=DESIGN_PARTS,
        ),
    )
}


# --- Das Protokoll ----------------------------------------------------------


def _entry_problems(name: str, entry: Any, spec: ProtocolField) -> list[str]:
    """Schlüssel und Werte eines Objekts gegen sein Feld im Schema."""
    if not isinstance(entry, Mapping):
        return [f"{name} ist keine Tabelle"]
    problems = []
    if spec.keys is not None:
        problems += [
            f"{name}: unbekannter Schlüssel {key}" for key in sorted(set(entry) - spec.keys)
        ]
    for key, allowed in spec.values.items():
        value = entry.get(key)
        if value is not None and value not in allowed:
            problems.append(f"{name}: {key} = {value!r} nicht in {list(allowed)}")
    problems += [f"{name}: Pflichtschlüssel {key} fehlt" for key in sorted(spec.needs - set(entry))]
    return problems


def validate_protocol(protocol: object) -> list[str]:
    """Was an einem Messprotokoll ungültig ist — leer, wenn es gelesen werden kann.

    Geprüft werden Feldnamen, Form, Pflichtfelder, die Schlüssel jedes Objekts
    und die Werte aus geschlossenen Listen (:data:`PROTOCOL_SCHEMA`). Ein Feld
    mit ``null`` ist eine fehlende Messung, kein Fehler — außer bei einem
    Pflichtfeld. Der Prüfstand fährt diese Prüfung über das, was er schreibt.
    """
    if not isinstance(protocol, Mapping):
        return ["das Protokoll ist keine Tabelle"]
    problems = [f"Pflichtfeld fehlt: {name}" for name in REQUIRED_FIELDS if name not in protocol]
    for name in sorted(protocol):
        spec = PROTOCOL_SCHEMA.get(name)
        value = protocol[name]
        if spec is None:
            problems.append(f"unbekanntes Feld: {name}")
            continue
        if value is None:
            if spec.required:
                problems.append(f"Pflichtfeld leer: {name}")
            continue
        if spec.shape == "tabelle":
            problems += _entry_problems(name, value, spec)
        elif spec.shape == "liste":
            if not isinstance(value, list):
                problems.append(f"{name} ist keine Liste")
                continue
            for index, entry in enumerate(value, 1):
                problems += _entry_problems(f"{name}[{index}]", entry, spec)
        elif spec.shape == "texte":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                problems.append(f"{name} ist keine Liste von Texten")
        elif spec.shape == "text":
            if not isinstance(value, str):
                problems.append(f"{name} ist kein Text")
            elif spec.choices and value not in spec.choices:
                problems.append(f"{name} = {value!r} nicht in {list(spec.choices)}")
        elif spec.shape == "wahr" and not isinstance(value, bool):
            problems.append(f"{name} ist nicht wahr oder falsch")
    for name in ("matrix", "licence_runs", "states"):
        table = protocol.get(name)
        for key, entry in sorted(table.items()) if isinstance(table, Mapping) else ():
            if entry is not None and not isinstance(entry, Mapping):
                problems.append(f"{name}.{key} ist keine Tabelle")
    matrix = protocol.get("matrix")
    for stage, entry in sorted(matrix.items()) if isinstance(matrix, Mapping) else ():
        if isinstance(entry, Mapping) and entry.get("state") not in MATRIX_STATES:
            problems.append(
                f"matrix.{stage}: Zustand {entry.get('state')!r} nicht in {list(MATRIX_STATES)}"
            )
    return problems


# --- Wächter -----------------------------------------------------------------


def start_size_in_window(source: str) -> tuple[int, int] | None:
    """Die Startgröße aus ``MainWindow.__init__`` (``self.resize(b, h)``), für den Wächter."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    for call in ast.walk(item):
                        if (
                            isinstance(call, ast.Call)
                            and isinstance(call.func, ast.Attribute)
                            and call.func.attr == "resize"
                            and len(call.args) == 2
                            and all(
                                isinstance(a, ast.Constant) and isinstance(a.value, int)
                                for a in call.args
                            )
                        ):
                            first, second = call.args
                            assert isinstance(first, ast.Constant) and isinstance(
                                second, ast.Constant
                            )
                            assert isinstance(first.value, int) and isinstance(second.value, int)
                            return first.value, second.value
    return None


# --- Skill-Tabellen (Wächter Skill ↔ Konstante) ---------------------------

_SKILL_COLUMNS: Final = ("Kennung", "Zählgröße", "Schwelle", "Stufe", "Messung")
_NUMBER_WORDS: Final = {
    "zwei": 2.0,
    "drei": 3.0,
    "vier": 4.0,
    "fünf": 5.0,
    "sechs": 6.0,
    "zehn": 10.0,
    "hälfte": 50.0,
}


@dataclass(frozen=True)
class SkillRow:
    """Eine Zeile einer Kriterientabelle im Skill."""

    key: str
    measure: str
    threshold: str
    stage: str
    measurement: str


def skill_rows(text: str) -> dict[str, SkillRow]:
    """Die Zeilen jeder Kriterientabelle eines Skills.

    Eine Kriterientabelle hat die Spalten ``Kennung | Zählgröße | Schwelle |
    Stufe | Messung``. Die Kopfzellen werden am Anfang verglichen: „Messung
    (Feld im Protokoll)“ zählt mit.
    """
    rows: dict[str, SkillRow] = {}
    inside = False
    for line in text.splitlines():
        cells = (
            [cell.strip() for cell in line.strip().strip("|").split("|")]
            if line.lstrip().startswith("|")
            else None
        )
        if cells is None:
            inside = False
            continue
        if len(cells) >= len(_SKILL_COLUMNS) and all(
            cell.startswith(name) for cell, name in zip(cells, _SKILL_COLUMNS, strict=False)
        ):
            inside = True
            continue
        if not inside or set("".join(cells)) <= set("-: "):
            continue
        key = cells[0].strip("*` ")
        if len(cells) >= len(_SKILL_COLUMNS):
            rows[key] = SkillRow(key, cells[1], cells[2], cells[3], cells[4])
    return rows


def threshold_numbers(text: str) -> frozenset[float]:
    """Die Zahlen einer Schwelle, wie ein Leser sie liest.

    Weg fallen Code in Backticks, Abschnittsverweise (``§4``), Kennungen
    (``Z2``, ``RM-12``) und das „: 1“ eines Kontrastverhältnisses; Zahlwörter
    von zwei bis zehn und „Hälfte“ (50 %) zählen mit.
    """
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"§\s*\d+(?:\.\d+)*", " ", text)
    text = re.sub(r"\b(?:RM-\d+|[EVGZIPD]\d+)\b", " ", text)
    text = re.sub(r"\s*:\s*1(?!\d|[.,]\d)", " ", text)
    found = {float(match.replace(",", ".")) for match in re.findall(r"\d+(?:[.,]\d+)?", text)}
    for word in re.findall(r"\w+", text.lower()):
        if word in _NUMBER_WORDS:
            found.add(_NUMBER_WORDS[word])
    return frozenset(round(value, 6) for value in found)


def skill_stages(text: str) -> frozenset[str]:
    """Die Stufen einer Zelle: A, B und C als eigene Wörter."""
    return frozenset(re.findall(r"(?<![\w-])([ABC])(?![\w-])", text))


def skill_fields(text: str) -> frozenset[str]:
    """Die Protokollfelder, die eine Messzelle in Backticks nennt (oberste Ebene)."""
    names = {re.split(r"[.\[(]", token, maxsplit=1)[0] for token in re.findall(r"`([^`]+)`", text)}
    return frozenset(names & PROTOCOL_FIELDS)


def skill_mismatches(skill: str, text: str) -> list[str]:
    """Wo die Kriterientabelle eines Skills von :data:`CRITERIA` abweicht."""
    expected = {key: c for key, c in CRITERIA.items() if c.skill == skill}
    rows = {
        key: row for key, row in skill_rows(text).items() if key in CRITERIA or key[:1] in "EVGZI"
    }
    problems = []
    if not rows:
        return [f"{skill}: keine Kriterientabelle mit den Spalten {' | '.join(_SKILL_COLUMNS)}"]
    for key in sorted(set(expected) - set(rows)):
        problems.append(f"{skill}: {key} fehlt in der Tabelle")
    for key in sorted(set(rows) - set(expected)):
        problems.append(
            f"{skill}: {key} steht in der Tabelle, aber nicht in CRITERIA dieses Skills"
        )
    for key in sorted(set(rows) & set(expected)):
        row, criterion = rows[key], expected[key]
        said = threshold_numbers(row.threshold)
        meant = frozenset(round(n, 6) for n in criterion.numbers)
        if said != meant:
            problems.append(
                f"{skill}: {key} Schwelle nennt {sorted(said)}, "
                f"die Konstanten sagen {sorted(meant)}"
            )
        stages = skill_stages(row.stage)
        if stages != set(criterion.stages):
            problems.append(
                f"{skill}: {key} Stufe {sorted(stages)}, CRITERIA {list(criterion.stages)}"
            )
        named = skill_fields(row.measurement)
        unread = sorted(named - set(criterion.fields))
        if unread:
            problems.append(
                f"{skill}: {key} nennt Protokollfelder, die das Urteil nicht liest: {unread}"
            )
        unnamed = sorted(set(criterion.fields) - named)
        if unnamed:
            problems.append(
                f"{skill}: {key} nennt nicht alle Protokollfelder des Urteils: {unnamed}"
            )
    return problems
