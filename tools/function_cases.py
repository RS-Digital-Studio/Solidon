"""Welche Sprachfälle ein Paket braucht: einen je Einrichtung seiner Startszenen (FD-101).

Ein Sprachfall geht die Flächen aller Zeilen eines Pakets in einem Prozess ab
(``function_language.LanguageFlow``). Was eine Startszene über ihre Datei
hinaus verlangt, gilt für den ganzen Prozess und ab seinem Start: eine fehlende
Bibliothek (``preconditions``, etwa ``opencascade = fehlt``) hielte jede exakte
Szene danach an, und eigene Bausteine (``own_parts``) liest die Anwendung nur
beim Start aus dem Nutzerordner. Vorher bekam ein Sprachfall weder das eine
noch das andere, und *Installieren* und *Gespeicherte Bausteine behalten*
fanden ihren Befund nie. Jetzt laufen solche Zeilen in einem eigenen Sprachfall
je Einrichtung; seine Kennung ist ``<paket>@<einrichtung>``, die Zeilen ohne
Einrichtung bleiben unter ``<paket>``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

#: Trennt Paket und Einrichtung in der Kennung eines Sprachfalls.
SEPARATOR: Final = "@"

#: Der Ausgang eines Sprachfalls, der vor einer Fläche einen neuen Prozess braucht,
#: weil die vorige den Ausgangszustand verändert hat (FD-132). ``EX_TEMPFAIL``.
RESTART_EXIT: Final = 75

#: Vorbedingungen der Spezifikation, die keine Einrichtung des Prozesses sind:
#: Lizenz und Druckart haben eigene Läufe (``function_setup.spec_variants``).
ROW_PRECONDITIONS: Final[frozenset[str]] = frozenset({"licence", "printer"})

#: Zustände, die jeder Fall ohnehin hat: „vorhanden“ ist die Maschine selbst,
#: „gesehen“ das Profil jedes Falls (``function_setup.profile_settings``). Sie
#: ändern den Prozess nicht und bilden keine Einrichtung — ein eigener Prozess
#: dafür kostete nur Zeit.
EVERY_CASE_STATES: Final[frozenset[str]] = frozenset({"vorhanden", "gesehen"})


@dataclass(frozen=True, slots=True)
class Setup:
    """Was die Startszenen einer Zeile vor dem Start des Prozesses verlangen."""

    key: str = ""
    """Leer ohne Einrichtung, sonst z. B. ``opencascade=fehlt`` oder ``bausteine:<szene>``."""
    preconditions: Mapping[str, str] = field(default_factory=dict)
    own_parts: tuple[str, ...] = ()
    """Die Startszenen, deren eigene Bausteine im Nutzerordner liegen müssen."""


def setup_of(row: Mapping[str, Any]) -> Setup:
    """Die Einrichtung einer Zeile: Vorbedingungen und eigene Bausteine ihrer Startszenen.

    Wie beim Funktionsfall (``file_acceptance.function_cases``): Die Szene der
    Zeile geht der des Fehlfalls vor, die Szenen gehen der Spezifikation vor. Aus
    der Spezifikation zählen die Vorbedingungen ohne Lizenz und Druckart — die
    prüfen eigene Läufe; ohne sie lief der Druckhinweis im Sprachfall nie offen
    (FD-101, FD-121). Was jeder Fall ohnehin hat (:data:`EVERY_CASE_STATES`),
    bleibt im Sprachfall des Pakets.
    """
    from tools.function_scenes import row_scenes
    from tools.function_setup import scene_setup

    spec = row.get("spec") or {}
    needed: dict[str, str] = {
        str(name): str(state)
        for name, state in (spec.get("preconditions") or {}).items()
        if name not in ROW_PRECONDITIONS
    }
    parts: list[str] = []
    for key in reversed(row_scenes(row)):
        setup = scene_setup(key)
        needed.update(setup.preconditions)
        if setup.own_parts:
            parts.append(key)
    needed = {name: state for name, state in needed.items() if state not in EVERY_CASE_STATES}
    words = [f"{name}={state}" for name, state in sorted(needed.items())]
    words += [f"bausteine:{key}" for key in sorted(parts)]
    return Setup(",".join(words), needed, tuple(sorted(parts)))


def language_groups(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[Setup]]:
    """Je Paket die Einrichtungen seiner Zeilen, die ohne zuerst."""
    found: dict[str, dict[str, Setup]] = {}
    for row in rows:
        setup = setup_of(row)
        found.setdefault(str(row.get("package")), {}).setdefault(setup.key, setup)
    return {
        package: [setups[key] for key in sorted(setups)]
        for package, setups in sorted(found.items())
    }


def language_cases(
    rows: Iterable[Mapping[str, Any]], packages: Iterable[str], spoken: Iterable[str], number: int
) -> list[Any]:
    """Die Sprachfälle der Pakete: je Paket, Einrichtung und Sprache einer, ab ``number``.

    Die Vorbedingungen der Einrichtung stehen in der Variante des Falls;
    ``file_acceptance.function_child`` wendet sie vor dem Start der Anwendung an
    und legt die eigenen Bausteine in den Nutzerordner.
    """
    from tools.file_acceptance import Case
    from tools.function_setup import Variant

    wanted = set(packages)
    languages = tuple(spoken)
    cases: list[Any] = []
    groups = language_groups(row for row in rows if str(row.get("package")) in wanted)
    for package, setups in groups.items():
        for setup in setups:
            for language in languages:
                entry: dict[str, Any] = {"set": "sprachen", "language": language}
                if setup.preconditions:
                    entry["preconditions"] = dict(setup.preconditions)
                name = case_row(package, setup)
                variant = Variant.of(entry).as_dict()
                cases.append(
                    Case(
                        number,
                        f"{name} [{language}]",
                        "",
                        "",
                        kind="language",
                        row=name,
                        variant=variant,
                    )
                )
                number += 1
    return cases


def most_restarts(rows: Iterable[Mapping[str, Any]], case: str) -> int:
    """Wie oft ein Sprachfall höchstens neu startet: einmal je Zeile (FD-132).

    Ein frischer Prozess misst seine erste Fläche immer im Ausgangszustand;
    mehr Neustarts als Zeilen hieße, er käme nicht voran.
    """
    return len(rows_of(rows, case))


def case_row(package: str, setup: Setup) -> str:
    """Die Kennung des Sprachfalls eines Pakets mit dieser Einrichtung."""
    return f"{package}{SEPARATOR}{setup.key}" if setup.key else package


def package_of(case: str) -> str:
    """Das Paket hinter der Kennung eines Sprachfalls."""
    return case.partition(SEPARATOR)[0]


def rows_of(rows: Iterable[Mapping[str, Any]], case: str) -> list[Mapping[str, Any]]:
    """Die Zeilen, die der Sprachfall ``case`` abgeht: Paket und Einrichtung gleich."""
    package, _separator, key = case.partition(SEPARATOR)
    return [row for row in rows if row.get("package") == package and setup_of(row).key == key]


def setup_of_case(rows: Iterable[Mapping[str, Any]], case: str) -> Setup:
    """Die Einrichtung des Sprachfalls ``case`` — leer, wenn er keine Zeile hat."""
    chosen = rows_of(rows, case)
    return setup_of(chosen[0]) if chosen else Setup()
