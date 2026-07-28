"""The part registry (Bauplan §24.1, §24.4).

Declared once, like an operation: from one declaration come the catalogue entry,
the parameter dialog, the agent's ``find_part`` and the documentation. What is
missing here fails at import time, not in a surface later on.

Two things a part carries that an operation does not:

* **a version and a change log** (§24.4). The library is part of the way a
  project was computed, so a correction to ``heatset_m4`` must not quietly
  recompute old projects differently — Leitprinzip 4 would be broken.
* **whether it adds or removes material**. A screw hole is a shape to subtract,
  a rib is one to add, and ``insert_part`` needs to know which without asking.
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

#: Groups of the catalogue (§24.3). They order what the user sees.
GROUPS: Final[dict[str, TranslatableText]] = {
    "fasteners": _("Verbindungen"),
    "inserts": _("Einlegeteile"),
    "mechanics": _("Mechanik"),
    "mounting": _("Befestigung"),
    "structure": _("Struktur"),
    "routing": _("Kabel und Schläuche"),
}


@dataclass(frozen=True, slots=True)
class PartChange:
    """One entry of the change log §24.4 asks for, per part."""

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
    """Holds the declarations. One default instance; tests build their own."""

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
        """What ``find_part`` answers with (§26.2). Plain word matching — a part
        library of a few dozen entries needs no index, and a wrong hit from a
        clever ranking would be worse than an honest miss."""
        words = [word for word in re.split(r"\W+", text.casefold()) if len(word) > 2]
        if not words:
            return ()
        found = []
        for spec in self.all():
            haystack = f"{spec.name} {spec.title} {spec.doc}".casefold()
            if any(word in haystack for word in words):
                found.append(spec)
        return tuple(found)

    def versions(self) -> dict[str, str]:
        """Every part with its own version — the comparison §24.4 runs on."""
        return {spec.name: spec.version for spec in self.all()}

    def mark_source(self, name: str, source: str) -> PartSpec:
        """Record where a part came from — the catalogue marks own ones (§24.5)."""
        import dataclasses

        spec = dataclasses.replace(self.get(name), source=source)
        self._parts[name] = spec
        return spec

    def clear(self) -> None:
        self._parts.clear()


#: The registry the application uses.
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
    """Declare a part. The decorated function stays callable as before."""

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


#: Version of the library as a whole. Goes into every project file (§16.2) and
#: is raised whenever a part changes in a way that moves dimensions.
LIBRARY_VERSION: Final = "1"


def changed_since(before: dict[str, str], registry: PartRegistry | None = None) -> tuple[str, ...]:
    """Parts whose version moved since a project was saved (§24.4).

    Only the ones the project actually used are worth a word, so the caller
    passes exactly those — with the version each was computed with.
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
    """Used parts that changed since a project was computed (§24.4).

    A project file records the library version, not a version per part — so the
    comparison runs over the change logs: whoever has an entry newer than that
    version has moved, and only the parts the project actually used are worth
    a word.
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
    """Which parts a stack uses, read off the operation names (§24.4)."""
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
    """Parts a project used that this installation does not have (§24.5).

    An own part from someone else's machine lands here, and the evaluation has
    to stop rather than compute something else (§15.2).
    """
    current = (registry or PARTS).versions()
    return tuple(name for name in sorted(before) if name not in current)
