"""Die Regelsammlung (Bauplan §39).

Der Bauplan nennt sie das eigentliche Produkt, also wird sie wie eines
behandelt: eine eigene Datei mit Version und Änderungsverlauf, kein Absatz in
einem Prompt. Der Systemprompt nennt die Version, jede Transaktion hält sie
fest (§26.4) — und das ist der einzige Weg, später herauszufinden, unter
welcher Regel eine Operation zustande kam.

Regeln sind Daten, wie die Druckerprofile. Eine Regel, die sich ändert, soll
kein Release brauchen, und eine Regel, die die Suite verschlechtert hat, soll
sich entfernen lassen, ohne Code anzufassen.
"""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from app.core.log import get_logger

_log = get_logger(__name__)

_DATA_FILE: Final = Path(__file__).parent / "data" / "rules.toml"

#: Steiler als das gegen die Platte, und es braucht Stützen (§39, §18.4).
#:
#: **Die Linie stand dreimal im Code, und einmal davon in anderer Gestalt.**
#: Die Orientierungssuche und die Analysekarte führten je eigene 45 Grad; die
#: Schichtanalyse dieselbe Entscheidung als Faktor 1.0, mit dem Satz „das sind
#: genau 45 Grad" im Kommentar daneben. Drei Stellen, die dieselbe Frage
#: beantworten, sind nur so lange einig, wie niemand eine davon anfasst — und
#: wer eine Winkelgrenze ändert, sucht nach Winkeln, nicht nach Faktoren.
#: Danach hätte die Orientierungssuche eine Lage empfohlen, die die
#: Schichtanalyse am selben Teil als Überhang meldet.
#:
#: Sie wohnt hier, weil §39 sie zieht: die Regelsammlung ist die Stelle, an
#: der Druckwissen steht (Robert, 27.08.2026).
OVERHANG_LIMIT_DEGREES: Final = 45.0

#: Wie weit eine Schicht seitlich wachsen darf, in Schichthöhen — dieselbe
#: Linie wie darüber, nur wie die Schichtanalyse sie braucht. Abgeleitet und
#: nicht abgeschrieben: Wer den Winkel ändert, ändert beides.
OVERHANG_ANGLE_FACTOR: Final = math.tan(math.radians(OVERHANG_LIMIT_DEGREES))

_rules: RuleSet | None = None


@dataclass(frozen=True, slots=True)
class Rule:
    """Eine Regel, in den Worten, die der Agent zu lesen bekommt."""

    id: str
    title: str
    text: str
    applies_to: tuple[str, ...] = ()
    translations: dict[str, tuple[str, str]] = field(default_factory=dict)
    """Titel und Text je Handbuchsprache, aus ``title_<sprache>``/``text_<sprache>``.

    **Nicht für den Agenten.** Der liest weiter die deutschen Felder, in jeder
    Sprache — zwei Versionen einer Regel wären zwei Wahrheiten, und die
    Suite-Quote hinge davon ab, welche gerade galt. Fehlt eine Übersetzung,
    steht das deutsche Original da; ein Handbuch mit einer Lücke wäre
    schlechter als eines mit einem fremdsprachigen Absatz.
    """

    def as_line(self) -> str:
        """Eine Regel als ein Absatz — die Form, die der Systemprompt benutzt."""
        return f"- {self.title}: {' '.join(self.text.split())}"

    def reading(self, language: str) -> tuple[str, str]:
        """Titel und Text in der Sprache, in der gelesen wird."""
        translated = self.translations.get(language)
        if translated:
            title, text = translated
            return title, " ".join(text.split())
        return self.title, " ".join(self.text.split())


@dataclass(frozen=True, slots=True)
class Change:
    """Ein Eintrag des Änderungsverlaufs, den §39 verlangt."""

    version: str
    date: str
    reason: str
    suite_before: str = ""
    suite_after: str = ""


@dataclass(frozen=True, slots=True)
class RuleSet:
    """Alle Regeln mit ihrer Version."""

    version: str
    rules: tuple[Rule, ...]
    changes: tuple[Change, ...] = ()

    def for_topic(self, topic: str) -> tuple[Rule, ...]:
        return tuple(rule for rule in self.rules if topic in rule.applies_to)

    def as_text(self) -> str:
        """Die ganze Sammlung, so wie der Systemprompt sie trägt."""
        return "\n".join(rule.as_line() for rule in self.rules)


def _translations(entry: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """Sammelt ``title_<sprache>``/``text_<sprache>``-Paare ein — nur vollständige.

    Eine halbe Übersetzung (Titel ohne Text oder umgekehrt) fällt aufs deutsche
    Original zurück, statt einen zweisprachigen Absatz zu erzeugen.
    """
    found: dict[str, tuple[str, str]] = {}
    for key, value in entry.items():
        if not key.startswith("title_"):
            continue
        language = key.removeprefix("title_")
        text = str(entry.get(f"text_{language}", "")).strip()
        if str(value) and text:
            found[language] = (str(value), text)
    return found


def load(path: Path | None = None) -> RuleSet:
    """Liest die Regelsammlung. Gecacht, denn sie wird bei jeder Anfrage
    gebraucht.
    """
    global _rules
    if _rules is not None and path is None:
        return _rules

    with (path or _DATA_FILE).open("rb") as stream:
        table: dict[str, Any] = tomllib.load(stream)

    rules = tuple(
        Rule(
            id=str(entry["id"]),
            title=str(entry["title"]),
            text=str(entry["text"]).strip(),
            applies_to=tuple(entry.get("applies_to", ())),
            translations=_translations(entry),
        )
        for entry in table.get("rules", ())
    )
    changes = tuple(
        Change(
            version=str(entry["version"]),
            date=str(entry["date"]),
            reason=str(entry["reason"]),
            suite_before=str(entry.get("suite_before", "")),
            suite_after=str(entry.get("suite_after", "")),
        )
        for entry in table.get("changes", ())
    )
    loaded = RuleSet(version=str(table.get("version", "0")), rules=rules, changes=changes)
    if path is None:
        _rules = loaded
    _log.info("rule set %s with %d rules", loaded.version, len(loaded.rules))
    return loaded


def version() -> str:
    """Die Version, die jede Transaktion eines Agenten tragen muss (§26.4)."""
    return load().version
