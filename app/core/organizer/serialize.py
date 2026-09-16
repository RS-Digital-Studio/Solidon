"""Ein geschlossener Datenvertrag für rechtwinklige Fachaufteilungen (§13, §32)."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Final, Literal

from app.core import expressions
from app.core.errors import AppError, ValidationError
from app.i18n import TranslatableText, _

Number = float | str
MAX_TEXT: Final = 262_144
MAX_NODES: Final = 512
MAX_LAYOUT_DEPTH: Final = 16
MAX_LAYOUT_CELLS: Final = 256
MAX_COUNT: Final = 32
MAX_DIMENSION: Final = 2000.0
_ID = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")


def _index(value: str, *, maximum: int = MAX_COUNT) -> bool:
    """Kurze kanonische Indizes prüfen, bevor Python eine Zahl daraus liest."""
    return (
        1 <= len(value) <= 2
        and value.isascii()
        and value.isdigit()
        and value[0] != "0"
        and 1 <= int(value) <= maximum
    )


def _wall_id(value: str) -> bool:
    """Einen stabilen Wandpfad einschließlich des begrenzten Wandindexes prüfen."""
    pieces = value.split("/")
    return (
        len(value) <= MAX_LAYOUT_DEPTH * 60
        and len(pieces) >= 2
        and bool(_ID.fullmatch(pieces[0]))
        and all(_ID.fullmatch(piece) or _index(piece) for piece in pieces[1:-1])
        and pieces[-1].startswith("wall_")
        and _index(pieces[-1][5:], maximum=MAX_COUNT - 1)
    )


@dataclass(frozen=True, slots=True)
class Node:
    """Eine benannte Zelle, Teilung oder Wiederholung; Zahlen bleiben Ausdrücke."""

    kind: Literal["cell", "split", "repeat"]
    id: str
    width: Number = 0.0
    depth: Number = 0.0
    radius: Number = 0.0
    axis: Literal["x", "y"] = "x"
    wall: Number = 0.0
    heights: tuple[tuple[int, Number], ...] = ()
    opening_radius: Number = 0.0
    children: tuple[Node, ...] = ()
    count: Number = 1.0


@dataclass(frozen=True, slots=True)
class LayoutSpec:
    """Maßbezug und geschlossener Teilungsbaum in Format 1."""

    basis: Literal["outer", "inner"]
    root: Node
    wall_heights: tuple[tuple[str, Number], ...] = ()


def invalid(detail: TranslatableText | str) -> ValidationError:
    """Fehler am einen sichtbaren Fachaufteilungsfeld bündeln."""
    return ValidationError(field="layout", constraint="organizer_layout", detail=detail)


def _number(value: Any) -> Number:
    """Nur endliche Zahlen und die bereits vorhandene Ausdrucksgrammatik lesen."""
    if isinstance(value, str) and expressions.is_expression(value):
        expressions.check(value)
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        try:
            numeric = float(value)
        except OverflowError:
            numeric = math.inf
        if math.isfinite(numeric):
            return numeric
    raise invalid(_("Ein Fachmaß braucht eine endliche Zahl oder einen gültigen Maßausdruck."))


def _object(value: Any, fields: set[str], required: set[str]) -> dict[str, Any]:
    """Unbekannte oder fehlende Felder nie in eine andere Aufteilung umdeuten."""
    if not isinstance(value, dict) or set(value) - fields or required - set(value):
        raise invalid(_("Die Fachaufteilung ist beschädigt. Öffnen Sie die Aufteilung erneut."))
    return value


def layout_from_text(text: str) -> LayoutSpec:
    """Begrenzt lesen, vollständig prüfen und alle Maßausdrücke erhalten."""
    if not isinstance(text, str) or len(text) > MAX_TEXT:
        raise invalid(_("Die Fachaufteilung ist zu groß. Verwenden Sie weniger Teilungen."))
    try:
        raw = json.loads(text)
    except (ValueError, RecursionError) as error:
        raise invalid(
            _("Die Fachaufteilung ist beschädigt. Öffnen Sie die Aufteilung erneut.")
        ) from error
    data = _object(
        raw, {"version", "basis", "layout", "wall_heights"}, {"version", "basis", "layout"}
    )
    if type(data["version"]) is not int or data["version"] != 1:
        raise invalid(
            _("Diese Fachaufteilung hat ein unbekanntes Format. Aktualisieren Sie Solidon.")
        )
    if data["basis"] not in ("inner", "outer"):
        raise invalid(_("Wählen Sie Außenmaße oder lichte Fachmaße als Bezug."))
    seen: set[str] = set()
    overrides = data.get("wall_heights", {})
    if not isinstance(overrides, dict) or len(overrides) > MAX_LAYOUT_CELLS * 2:
        raise invalid(
            _("Die gespeicherten Trennwandhöhen sind ungültig. Wählen Sie die Wände erneut.")
        )
    for key in overrides:
        if not isinstance(key, str) or not _wall_id(key):
            raise invalid(
                _("Die gespeicherten Trennwandhöhen sind ungültig. Wählen Sie die Wände erneut.")
            )
    return LayoutSpec(
        data["basis"],
        _node(data["layout"], seen, 0),
        tuple((key, _number(value)) for key, value in sorted(overrides.items())),
    )


def _node(raw: Any, seen: set[str], level: int) -> Node:
    """Die drei erlaubten Knotentypen mit einer gemeinsamen Kennungsprüfung lesen."""
    if level >= MAX_LAYOUT_DEPTH or len(seen) >= MAX_NODES:
        raise invalid(_("Die Fachaufteilung ist zu tief oder zu groß. Entfernen Sie eine Teilung."))
    if not isinstance(raw, dict) or raw.get("kind") not in ("cell", "split", "repeat"):
        raise invalid(
            _("Die Fachaufteilung enthält eine unbekannte Teilung. Wählen Sie sie erneut.")
        )
    identifier = raw.get("id")
    if not isinstance(identifier, str) or not _ID.fullmatch(identifier) or identifier in seen:
        raise invalid(
            _("Die Fachkennungen sind ungültig oder doppelt. Legen Sie die Teilung erneut an.")
        )
    seen.add(identifier)
    if raw["kind"] == "cell":
        data = _object(raw, {"kind", "id", "width", "depth", "radius"}, {"width", "depth"})
        return Node(
            "cell",
            identifier,
            _number(data["width"]),
            _number(data["depth"]),
            _number(data.get("radius", 0)),
        )
    fields = {"kind", "id", "axis", "wall", "heights", "opening_radius"}
    fields |= {"children"} if raw["kind"] == "split" else {"count", "child"}
    data = _object(
        raw,
        fields,
        {"axis", "wall"} | ({"children"} if raw["kind"] == "split" else {"count", "child"}),
    )
    if data["axis"] not in ("x", "y"):
        raise invalid(_("Wählen Sie eine Teilung längs oder quer."))
    heights = data.get("heights", {})
    if not isinstance(heights, dict) or len(heights) >= MAX_COUNT:
        raise invalid(_("Die Trennwandhöhen sind ungültig. Wählen Sie die betroffene Wand erneut."))
    parsed_heights = []
    for key, value in heights.items():
        if not isinstance(key, str) or not _index(key, maximum=MAX_COUNT - 1):
            raise invalid(
                _("Die Trennwandhöhen sind ungültig. Wählen Sie die betroffene Wand erneut.")
            )
        parsed_heights.append((int(key), _number(value)))
    children = data.get("children", [data.get("child")])
    if not isinstance(children, list) or not 1 <= len(children) <= MAX_COUNT:
        raise invalid(_("Eine Teilung braucht gültige Fächer. Wählen Sie die Fachzahl erneut."))
    return Node(
        data["kind"],
        identifier,
        axis=data["axis"],
        wall=_number(data["wall"]),
        heights=tuple(sorted(parsed_heights)),
        opening_radius=_number(data.get("opening_radius", 0)),
        children=tuple(_node(child, seen, level + 1) for child in children),
        count=_number(data.get("count", 1)),
    )


def node_data(node: Node) -> dict[str, Any]:
    """Den überprüften Baum ohne aufgelöste oder gerundete Maße zurückschreiben."""
    data: dict[str, Any] = {"kind": node.kind, "id": node.id}
    if node.kind == "cell":
        return {**data, "width": node.width, "depth": node.depth, "radius": node.radius}
    data.update(
        axis=node.axis,
        wall=node.wall,
        heights={str(k): v for k, v in node.heights},
        opening_radius=node.opening_radius,
    )
    if node.kind == "repeat":
        data.update(count=node.count, child=node_data(node.children[0]))
    else:
        data["children"] = [node_data(child) for child in node.children]
    return data


def layout_to_text(spec: LayoutSpec) -> str:
    """Die gespeicherten Daten kanonisch und ohne Projektpfade schreiben."""
    return json.dumps(
        {
            "version": 1,
            "basis": spec.basis,
            "layout": node_data(spec.root),
            **({"wall_heights": dict(spec.wall_heights)} if spec.wall_heights else {}),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def node_numbers(node: Node) -> tuple[Number, ...]:
    """Genau die fachlichen Zahlen eines Knotens, gemeinsam für Bezug und Auflösung."""
    if node.kind == "cell":
        return node.width, node.depth, node.radius
    return (
        node.wall,
        node.opening_radius,
        *(height for _index, height in node.heights),
        *((node.count,) if node.kind == "repeat" else ()),
    )


def layout_references(text: str, *, strict: bool = False) -> frozenset[str]:
    """Alle verschachtelten Maßbezüge an Cache, Rezepte und Parameteranzeige melden."""
    found: set[str] = set()
    try:
        spec = layout_from_text(text)
        for _key, value in spec.wall_heights:
            if isinstance(value, str):
                found.update(expressions.references(value))
        pending = [spec.root]
        while pending:
            node = pending.pop()
            for value in node_numbers(node):
                if isinstance(value, str):
                    found.update(expressions.references(value))
            pending.extend(node.children)
    except AppError:
        if strict:
            raise
        return frozenset()
    return frozenset(found)


def grid_layout(
    rows: Number = 3,
    columns: Number = 3,
    *,
    cell_width: Number = 50,
    cell_depth: Number = 40,
    wall: Number = 3,
    radius: Number = 3,
    basis: Literal["inner", "outer"] = "outer",
) -> LayoutSpec:
    """Ein echtes Reihen-/Spaltenraster als wiederholbare Daten erzeugen."""
    cell = Node("cell", "cell", width=cell_width, depth=cell_depth, radius=radius)
    row = Node("repeat", "columns", axis="x", wall=wall, children=(cell,), count=columns)
    return LayoutSpec(
        basis, Node("repeat", "rows", axis="y", wall=wall, children=(row,), count=rows)
    )
