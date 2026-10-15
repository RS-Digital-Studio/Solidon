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
    Zeile geht der des Fehlfalls vor.
    """
    from tools.function_scenes import row_scenes
    from tools.function_setup import scene_setup

    needed: dict[str, str] = {}
    parts: list[str] = []
    for key in reversed(row_scenes(row)):
        setup = scene_setup(key)
        needed.update(setup.preconditions)
        if setup.own_parts:
            parts.append(key)
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
