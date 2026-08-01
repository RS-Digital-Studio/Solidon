"""Das Bausteinregister (Bauplan §24.1, §24.4).

Einmal deklariert, wie eine Operation: aus einer Deklaration kommen der
Katalogeintrag, der Parameterdialog, das ``find_part`` des Agenten und die
Dokumentation. Was hier fehlt, scheitert beim Import, nicht später in einer
Oberfläche.

Zwei Dinge trägt ein Baustein, die eine Operation nicht hat:

* **eine Version und einen Änderungsverlauf** (§24.4). Die Bibliothek ist Teil
  der Art, wie ein Projekt gerechnet wurde — eine Korrektur an ``heatset_m4``
  darf alte Projekte also nicht still anders nachrechnen; Leitprinzip 4 wäre
  gebrochen.
* **ob er Material hinzufügt oder wegnimmt**. Ein Schraubenloch ist eine Form
  zum Abziehen, eine Rippe eine zum Hinzufügen, und ``insert_part`` muss das
  wissen, ohne zu fragen.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from app.core.errors import InternalError
from app.core.types import BaseParams, PartFn
from app.i18n import TranslatableText, _

_NAME_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]*$")

#: Kürzestes Wort, das die Suche ernst nimmt.
MIN_SEARCH_WORD: Final = 4

#: Wörter, die in fast jeder Beschreibung vorkommen und darum nichts sagen.
STOP_WORDS: Final[frozenset[str]] = frozenset(
    {
        "auch",
        "eine",
        "einen",
        "einem",
        "eines",
        "damit",
        "dass",
        "durch",
        "haben",
        "kann",
        "nach",
        "nicht",
        "oder",
        "sich",
        "sind",
        "über",
        "wenn",
        "wird",
        "zwei",
    }
)

#: Gruppen des Katalogs (§24.3). Sie ordnen, was der Nutzer sieht.
GROUPS: Final[dict[str, TranslatableText]] = {
    "fasteners": _("Verbindungen"),
    "inserts": _("Einlegeteile"),
    "mechanics": _("Mechanik"),
    "mounting": _("Befestigung"),
    "structure": _("Struktur"),
    "routing": _("Kabel und Schläuche"),
    "calibration": _("Kalibrierung"),
}


@dataclass(frozen=True, slots=True)
class PartChange:
    """Ein Eintrag des Änderungsverlaufs, den §24.4 verlangt, je Baustein."""

    version: str
    date: str
    reason: str
    effect: str = ""
    """What it does to the dimensions — the part that matters for old projects."""


@dataclass(frozen=True, slots=True)
class PartSpec:
    """Everything known about one part."""

    name: str
    title: TranslatableText | str
    group: str
    params: type[BaseParams]
    fn: PartFn
    version: str = "1"
    subtractive: bool = False
    """True for a shape that is subtracted: a hole, a pocket, a trap."""
    features: tuple[str, ...] = ()
    """Provenance features the part promises to name (§24.1)."""
    doc: TranslatableText | str = ""
    changes: tuple[PartChange, ...] = ()
    source: str = "shipped"
    """``shipped`` or ``user`` — the catalogue marks the difference (§24.5)."""

    @property
    def own(self) -> bool:
        return self.source == "user"


class PartRegistry:
    """Hält die Deklarationen. Eine Vorgabe-Instanz; Tests bauen ihre eigene."""

    def __init__(self) -> None:
        self._parts: dict[str, PartSpec] = {}

    def register(self, spec: PartSpec) -> PartSpec:
        self._check(spec)
        self._parts[spec.name] = spec
        return spec

    def _check(self, spec: PartSpec) -> None:
        if not _NAME_PATTERN.match(spec.name):
            raise InternalError(
                detail=f"part name {spec.name!r} is not lower_snake_case",
                values={"part": spec.name},
            )
        if spec.name in self._parts:
            raise InternalError(
                detail=f"part {spec.name!r} is registered twice",
                values={"part": spec.name},
            )
        if spec.group not in GROUPS:
            raise InternalError(
                detail=f"unknown group {spec.group!r}",
                values={"part": spec.name, "known": sorted(GROUPS)},
            )
        if not (isinstance(spec.params, type) and issubclass(spec.params, BaseParams)):
            raise InternalError(
                detail=f"{spec.name!r} needs a parameter set derived from BaseParams",
                values={"part": spec.name},
            )
        if not spec.features:
            raise InternalError(
                detail=f"{spec.name!r} names no provenance features (§24.1)",
                values={"part": spec.name},
            )

    def get(self, name: str) -> PartSpec:
        if name not in self._parts:
            raise InternalError(
                detail=f"unknown part {name!r}",
                values={"requested": name, "known": sorted(self._parts)},
            )
        return self._parts[name]

    def has(self, name: str) -> bool:
        return name in self._parts

    def all(self) -> tuple[PartSpec, ...]:
        return tuple(self._parts[name] for name in sorted(self._parts))

    def by_group(self) -> dict[str, tuple[PartSpec, ...]]:
        grouped: dict[str, list[PartSpec]] = {name: [] for name in GROUPS}
        for spec in self.all():
            grouped[spec.group].append(spec)
        return {name: tuple(entries) for name, entries in grouped.items() if entries}

    def search(self, text: str) -> tuple[PartSpec, ...]:
        """Womit ``find_part`` antwortet (§26.2). Schlichter Wortvergleich — eine
        Bausteinbibliothek aus ein paar Dutzend Einträgen braucht keinen Index,
        und ein falscher Treffer aus einer klugen Rangfolge wäre schlimmer als
        ein ehrlicher Fehlschlag.

        Kurze und häufige Wörter fallen weg: „eine Mutter mit Gewinde" träfe
        sonst jeden Baustein, dessen Beschreibung „mit" enthält — und eine
        Bibliothek, die auf alles antwortet, ist so nutzlos wie eine, die auf
        nichts antwortet.
        """
        words = [
            word
            for word in re.split(r"\W+", text.casefold())
            if len(word) >= MIN_SEARCH_WORD and word not in STOP_WORDS
        ]
        if not words:
            return ()
        found = []
        for spec in self.all():
            haystack = f"{spec.name} {spec.title} {spec.doc}".casefold()
            if any(word in haystack for word in words):
                found.append(spec)
        return tuple(found)

    def versions(self) -> dict[str, str]:
        """Jeder Baustein mit seiner eigenen Version — der Vergleich, auf dem
        §24.4 läuft.
        """
        return {spec.name: spec.version for spec in self.all()}

    def mark_source(self, name: str, source: str) -> PartSpec:
        """Hält fest, woher ein Baustein kam — der Katalog kennzeichnet die
        eigenen (§24.5).
        """
        import dataclasses

        spec = dataclasses.replace(self.get(name), source=source)
        self._parts[name] = spec
        return spec

    def clear(self) -> None:
        self._parts.clear()


#: Das Register, das die Anwendung benutzt.
PARTS: Final = PartRegistry()


def register_part(
    *,
    name: str,
    title: TranslatableText | str,
    group: str,
    params: type[BaseParams],
    version: str = "1",
    subtractive: bool = False,
    features: Iterable[str] = (),
    doc: TranslatableText | str = "",
    changes: Sequence[PartChange] = (),
    source: str = "shipped",
    registry: PartRegistry | None = None,
) -> Callable[[PartFn], PartFn]:
    """Deklariert einen Baustein. Die dekorierte Funktion bleibt aufrufbar
    wie zuvor.
    """

    def decorate(fn: PartFn) -> PartFn:
        (registry or PARTS).register(
            PartSpec(
                name=name,
                title=title,
                group=group,
                params=params,
                fn=fn,
                version=version,
                subtractive=subtractive,
                features=tuple(features),
                doc=doc,
                changes=tuple(changes),
                source=source,
            )
        )
        return fn

    return decorate


#: Version der Bibliothek als Ganzes. Geht in jede Projektdatei (§16.2) und
#: wird erhöht, sobald ein Baustein sich auf eine Art ändert, die Maße
#: verschiebt.
LIBRARY_VERSION: Final = "1"


def changed_since(before: dict[str, str], registry: PartRegistry | None = None) -> tuple[str, ...]:
    """Bausteine, deren Version sich bewegt hat, seit ein Projekt gespeichert
    wurde (§24.4).

    Nur die, die das Projekt wirklich benutzt hat, sind ein Wort wert — der
    Aufrufer übergibt also genau diese, mit der Version, mit der jeder
    gerechnet wurde.
    """
    current = (registry or PARTS).versions()
    return tuple(
        name
        for name, version in sorted(before.items())
        if name in current and current[name] != version
    )


def changed_since_library(
    version: str, used: Iterable[str], registry: PartRegistry | None = None
) -> tuple[str, ...]:
    """Benutzte Bausteine, die sich geändert haben, seit ein Projekt
    gerechnet wurde (§24.4).

    Eine Projektdatei hält die Bibliotheksversion fest, keine Version je
    Baustein — der Vergleich läuft also über die Änderungsverläufe: wer einen
    Eintrag neuer als diese Version hat, hat sich bewegt, und nur die
    Bausteine, die das Projekt wirklich benutzt hat, sind ein Wort wert.
    """
    source = registry or PARTS
    since = _as_number(version)
    return tuple(
        name
        for name in sorted(set(used))
        if source.has(name)
        and any(_as_number(change.version) > since for change in source.get(name).changes)
    )


def _as_number(version: str) -> int:
    try:
        return int(version)
    except ValueError:
        return 0


def used_parts(operations: Iterable[Any]) -> tuple[str, ...]:
    """Welche Bausteine ein Stapel benutzt, abgelesen an den
    Operationsnamen (§24.4).
    """
    prefix = "insert_"
    return tuple(
        sorted(
            {
                str(entry.op)[len(prefix) :]
                for entry in operations
                if str(entry.op).startswith(prefix)
            }
        )
    )


def missing_parts(before: dict[str, str], registry: PartRegistry | None = None) -> tuple[str, ...]:
    """Bausteine, die ein Projekt benutzt hat und die diese Installation
    nicht hat (§24.5).

    Ein eigener Baustein von der Maschine eines anderen landet hier, und die
    Auswertung muss anhalten, statt etwas anderes zu rechnen (§15.2).
    """
    current = (registry or PARTS).versions()
    return tuple(name for name in sorted(before) if name not in current)
