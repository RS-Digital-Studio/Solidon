"""The operation registry (Bauplan §10).

An operation is declared exactly once; menu, context menu, palette, command
line, agent tool schema and documentation are generated from that declaration
(§1, Leitprinzip 3). A registration that is incomplete fails here, at import
time, not in a surface later on.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Final, get_args

from app.core.errors import InternalError
from app.core.types import BaseParams, FeatureKind, OpFn
from app.i18n import TranslatableText, _

FEATURE_KINDS: Final[tuple[str, ...]] = get_args(FeatureKind)

#: Categories from the operation catalogue (§25). They order the menu.
#: The catalogue of §25, in the order it appears in the menu. Four of these hold
#: no operations and are not going to: parameters and fits live in the document
#: and are changed by their panels and by the agent (§13, §14); export and the
#: variant generator are flows that run *around* an evaluation rather than
#: inside one — a variant set re-evaluates the whole stack, which an operation
#: within that evaluation cannot do (§15.1). Empty categories never reach a
#: menu, so they cost nothing but this paragraph.
CATEGORIES: Final[dict[str, TranslatableText]] = {
    "scene": _("Szene"),
    "parameters": _("Parameter"),
    "fits": _("Passungen"),
    "repair": _("Reparatur"),
    "transform": _("Transformation"),
    "boolean": _("Boolesch"),
    "holes": _("Bohrungen"),
    "parts": _("Bausteine"),
    "prepare": _("Druckvorbereitung"),
    "import": _("Import"),
    "export": _("Export"),
    "colour": _("Farbe"),
    "label": _("Beschriftung"),
    "mesh": _("Netz"),
    "variants": _("Varianten"),
}

_NAME_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]*$")

#: ``produces=VARIABLE``: as many objects out as went in.
VARIABLE: Final = -1


@dataclass(frozen=True, slots=True)
class OperationSpec:
    """Everything known about one operation. The single source for all surfaces."""

    name: str
    title: TranslatableText | str
    category: str
    params: type[BaseParams]
    fn: OpFn
    reversible: bool = True
    consumes: int = 1
    """How many objects the operation takes. Zero means any number."""
    produces: int = 1
    """How many it returns. ``VARIABLE`` means as many as it took — for
    operations like arranging, which change every object and create none."""
    applies_to: tuple[str, ...] = ()
    """Feature kinds this operation offers itself for — drives the context menu."""
    touches_features: bool = False
    deterministic: bool = True
    shortcut: str | None = None
    doc: TranslatableText | str = ""

    @property
    def requires_seed(self) -> bool:
        """Randomised procedures carry a stored seed (§11.3)."""
        return not self.deterministic

    @property
    def takes_whole_scene(self) -> bool:
        """Does this operation work on every object at once?

        Arranging and the collision check do: they take no particular object
        and hand back all of them. Every surface has to pass the whole scene in
        — an operation of this kind with no inputs runs on nothing and looks
        broken, which is exactly how it looked before this property existed.
        """
        return self.consumes == 0 and self.produces == VARIABLE


class Registry:
    """Holds the declarations. One default instance; tests build their own."""

    def __init__(self) -> None:
        self._ops: dict[str, OperationSpec] = {}

    def register(self, spec: OperationSpec) -> OperationSpec:
        self._check(spec)
        self._ops[spec.name] = spec
        return spec

    def _check(self, spec: OperationSpec) -> None:
        if not _NAME_PATTERN.match(spec.name):
            raise InternalError(
                detail=f"operation name {spec.name!r} is not lower_snake_case",
                values={"op": spec.name},
            )
        if spec.name in self._ops:
            raise InternalError(
                detail=f"operation {spec.name!r} is registered twice",
                values={"op": spec.name},
            )
        if spec.category not in CATEGORIES:
            raise InternalError(
                detail=f"unknown category {spec.category!r}",
                values={"op": spec.name, "known": sorted(CATEGORIES)},
            )
        if not (isinstance(spec.params, type) and issubclass(spec.params, BaseParams)):
            raise InternalError(
                detail=f"{spec.name!r} needs a parameter set derived from BaseParams",
                values={"op": spec.name},
            )
        unknown = [kind for kind in spec.applies_to if kind not in FEATURE_KINDS]
        if unknown:
            raise InternalError(
                detail=f"{spec.name!r} applies to unknown feature kinds {unknown}",
                values={"op": spec.name, "known": list(FEATURE_KINDS)},
            )
        if spec.consumes < 0 or spec.produces < VARIABLE:
            raise InternalError(
                detail=f"{spec.name!r} declares a negative object count",
                values={"op": spec.name},
            )
        if spec.shortcut:
            taken = self.by_shortcut(spec.shortcut)
            if taken is not None:
                raise InternalError(
                    detail=f"shortcut {spec.shortcut!r} is already used by {taken.name!r}",
                    values={"op": spec.name, "shortcut": spec.shortcut},
                )

    def get(self, name: str) -> OperationSpec:
        if name not in self._ops:
            raise InternalError(
                detail=f"unknown operation {name!r}",
                values={"requested": name, "known": sorted(self._ops)},
            )
        return self._ops[name]

    def has(self, name: str) -> bool:
        return name in self._ops

    def all(self) -> tuple[OperationSpec, ...]:
        return tuple(self._ops[name] for name in sorted(self._ops))

    def by_category(self) -> dict[str, tuple[OperationSpec, ...]]:
        """Operations grouped in catalogue order; empty categories are dropped."""
        grouped: dict[str, list[OperationSpec]] = {name: [] for name in CATEGORIES}
        for spec in self.all():
            grouped[spec.category].append(spec)
        return {name: tuple(entries) for name, entries in grouped.items() if entries}

    def for_feature(self, kind: str) -> tuple[OperationSpec, ...]:
        """What the context menu on a feature offers (§18.5)."""
        return tuple(spec for spec in self.all() if kind in spec.applies_to)

    def by_shortcut(self, shortcut: str) -> OperationSpec | None:
        wanted = shortcut.casefold()
        for spec in self._ops.values():
            if spec.shortcut and spec.shortcut.casefold() == wanted:
                return spec
        return None

    def clear(self) -> None:
        self._ops.clear()


#: The registry the application uses.
REGISTRY: Final = Registry()


def register_op(
    *,
    name: str,
    title: TranslatableText | str,
    category: str,
    params: type[BaseParams],
    reversible: bool = True,
    consumes: int = 1,
    produces: int = 1,
    applies_to: Iterable[str] = (),
    touches_features: bool = False,
    deterministic: bool = True,
    shortcut: str | None = None,
    doc: TranslatableText | str = "",
    registry: Registry | None = None,
) -> Callable[[OpFn], OpFn]:
    """Declare an operation. The decorated function stays callable as before."""

    def decorate(fn: OpFn) -> OpFn:
        (registry or REGISTRY).register(
            OperationSpec(
                name=name,
                title=title,
                category=category,
                params=params,
                fn=fn,
                reversible=reversible,
                consumes=consumes,
                produces=produces,
                applies_to=tuple(applies_to),
                touches_features=touches_features,
                deterministic=deterministic,
                shortcut=shortcut,
                doc=doc,
            )
        )
        return fn

    return decorate


@dataclass(frozen=True, slots=True)
class MenuSection:
    """One menu section, derived from a category (§10)."""

    category: str
    title: TranslatableText | str
    entries: tuple[OperationSpec, ...] = field(default_factory=tuple)
