"""Die Unterpakete des Kerns und wer wen importiert.

``test_layer_direction.py`` prüft die vier Schichten — ``core`` importiert nie
``ui``. Eine Ebene tiefer prüfte niemand, und dort sieht es anders aus, als die
Karte vermuten lässt: Gemessen am 07.09.2026 hängen acht der dreizehn
Unterpakete des Kerns über **eifrige** Importe (auf Modulebene) in einem Kreis
— ``geom`` allein mit sechs Nachbarn in beide Richtungen. ``app/core/lazy.py``
hält die Paket-``__init__`` deshalb träge; die Karte nannte als Grund den
Deadlock zweier Threads, nicht die Kreise, die ihn möglich machen.

Dieser Test baut die Kreise nicht ab. Er friert den Stand ein, damit er nicht
weiter wächst — dieselbe Bauart wie eine Verbotstabelle, nur mit dem
Ist-Zustand als erster Zeile:

* **Keine Kante, die hier nicht steht.** Eine neue Abhängigkeit zwischen zwei
  Kernpaketen ist eine Entscheidung; sie wird hier eingetragen, nicht still
  gezogen.
* **Keine Kante, die es nicht mehr gibt.** Eine abgebaute Abhängigkeit
  verschwindet auch aus der Liste — ein Eintrag über eine Kante, die keiner
  mehr zieht, verspricht einen Zustand, den es nicht gibt, und deckt die
  nächste Neuauflage.
* **Der eifrige Kreis bleibt, wie er ist, oder wird kleiner.** Ein Paket, das
  neu hineingerät, macht den Lauf rot; eines, das ihn verlässt, ändert die
  Liste und damit sichtbar den Stand.

Eifrig und träge werden unterschieden, weil nur eifrig ein Kreis ist, der beim
Import zuschlagen kann; ein Import in einer Funktion ist Kopplung, kein Kreis
(``.claude/memory/architektur-sonde-type-checking.md``). Importe unter
``TYPE_CHECKING`` zählen hier nicht: Sie laufen nie. Relative Importe werden
aufgelöst, nicht übersprungen — ``from ..geom import x`` verlässt sein Paket
genauso wie die ausgeschriebene Form.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import Final

import app.core

CORE: Final = Path(app.core.__file__).parent

#: Die Unterpakete des Kerns. Ein vierzehntes ohne Zeile hier macht
#: :func:`test_every_core_package_is_known` rot — es hätte sonst keine Regel.
PACKAGES: Final[frozenset[str]] = frozenset(
    {
        "activation",
        "agent",
        "backends",
        "brep",
        "export",
        "geom",
        "ingest",
        "knowledge",
        "perceive",
        "registry",
        "scene",
        "sketch",
        "slice",
    }
)

#: Eifrige Kanten: ``a`` importiert ``b`` mindestens einmal auf Modulebene.
#: Stand 07.09.2026, 47 Kanten.
EAGER: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("agent", "activation"),
        ("agent", "backends"),
        ("agent", "geom"),
        ("agent", "knowledge"),
        ("agent", "perceive"),
        ("agent", "registry"),
        ("agent", "scene"),
        ("agent", "slice"),
        ("backends", "geom"),
        ("backends", "ingest"),
        ("brep", "geom"),
        ("brep", "registry"),
        ("brep", "sketch"),
        ("export", "activation"),
        ("export", "geom"),
        ("export", "ingest"),
        ("export", "knowledge"),
        ("export", "slice"),
        ("geom", "knowledge"),
        ("geom", "registry"),
        ("geom", "scene"),
        ("geom", "sketch"),
        ("geom", "slice"),
        ("ingest", "brep"),
        ("ingest", "geom"),
        ("ingest", "perceive"),
        ("ingest", "registry"),
        ("ingest", "scene"),
        ("knowledge", "geom"),
        ("knowledge", "registry"),
        ("knowledge", "scene"),
        ("perceive", "geom"),
        ("perceive", "knowledge"),
        ("perceive", "registry"),
        ("perceive", "slice"),
        ("scene", "activation"),
        ("scene", "geom"),
        ("scene", "ingest"),
        ("scene", "knowledge"),
        ("scene", "perceive"),
        ("scene", "registry"),
        ("scene", "sketch"),
        ("sketch", "brep"),
        ("sketch", "geom"),
        ("sketch", "registry"),
        ("slice", "geom"),
        ("slice", "knowledge"),
    }
)

#: Träge Kanten: ``a`` importiert ``b`` nur innerhalb von Funktionen.
#: Stand 07.09.2026, zwölf Kanten — jede davon ist die Rückrichtung einer
#: eifrigen, träge gemacht, damit der Import nicht im Kreis läuft.
LAZY: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("brep", "perceive"),
        ("export", "brep"),
        ("geom", "brep"),
        ("geom", "export"),
        ("geom", "ingest"),
        ("geom", "perceive"),
        ("knowledge", "brep"),
        ("knowledge", "export"),
        ("knowledge", "ingest"),
        ("knowledge", "perceive"),
        ("knowledge", "sketch"),
        ("registry", "knowledge"),
    }
)

#: Der eine Kreis über eifrige Kanten — jedes dieser Pakete erreicht jedes
#: andere, ohne eine Funktion zu betreten. Schrumpft er, wird diese Zeile
#: kürzer; wächst er, ist der Lauf rot.
EAGER_CYCLE: Final[frozenset[str]] = frozenset(
    {"brep", "geom", "ingest", "knowledge", "perceive", "scene", "sketch", "slice"}
)

#: Fremder Code unter den Daten des Kerns — die ComfyUI-Knoten — gehört keinem
#: Paket und importiert nichts aus dem Kern.
_FOREIGN_DIR: Final = "data"


def _package_of(module: str) -> str | None:
    """``app.core.geom.mesh`` → ``geom``; ``app.core.errors`` → ``None``."""
    parts = module.split(".")
    if len(parts) >= 3 and parts[:2] == ["app", "core"] and parts[2] in PACKAGES:
        return parts[2]
    return None


def _targets(node: ast.Import | ast.ImportFrom, own: list[str]) -> list[str]:
    """Die Kernpakete, die ein Import-Knoten anspricht.

    ``own`` ist der Modulpfad der Datei unterhalb von ``app.core`` — für die
    Auflösung relativer Importe. ``from app.core import activation`` zählt
    ebenso wie ``from app.core.activation import store``: Beide holen das
    Paket.
    """
    if isinstance(node, ast.Import):
        return [found for alias in node.names if (found := _package_of(alias.name))]
    if node.level:
        base = own[: len(own) - node.level]
        module = ".".join(["app", "core", *base, *(node.module.split(".") if node.module else [])])
    else:
        module = node.module or ""
    if module == "app.core":
        return [alias.name for alias in node.names if alias.name in PACKAGES]
    found = _package_of(module)
    return [found] if found else []


def _imports_of(path: Path, own: list[str]) -> list[tuple[str, str, int]]:
    """Jeder Kernimport der Datei: Zielpaket, Art (``eager``/``lazy``/``typing``), Zeile."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, str, int]] = []

    def walk(node: ast.AST, in_function: bool, in_typing: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Import | ast.ImportFrom):
                kind = "typing" if in_typing else ("lazy" if in_function else "eager")
                found.extend((target, kind, child.lineno) for target in _targets(child, own))
            elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
                walk(child, True, in_typing)
            elif isinstance(child, ast.If) and _guards_typing(child):
                for statement in child.body:
                    walk_statement(statement, in_function, True)
                for statement in child.orelse:
                    walk_statement(statement, in_function, in_typing)
            else:
                walk(child, in_function, in_typing)

    def walk_statement(statement: ast.stmt, in_function: bool, in_typing: bool) -> None:
        if isinstance(statement, ast.Import | ast.ImportFrom):
            kind = "typing" if in_typing else ("lazy" if in_function else "eager")
            found.extend((target, kind, statement.lineno) for target in _targets(statement, own))
        else:
            walk(statement, in_function, in_typing)

    walk(tree, False, False)
    return found


def _guards_typing(node: ast.If) -> bool:
    test = node.test
    name = getattr(test, "id", None) or getattr(test, "attr", None)
    return name == "TYPE_CHECKING"


def _sources() -> dict[str, list[Path]]:
    """Die Quelldateien je Paket — ohne fremden Code unter ``data/``."""
    sources: dict[str, list[Path]] = {package: [] for package in PACKAGES}
    for path in sorted(CORE.rglob("*.py")):
        parts = path.relative_to(CORE).parts
        if len(parts) < 2 or _FOREIGN_DIR in parts[:-1]:
            continue
        if parts[0] in sources:
            sources[parts[0]].append(path)
    return sources


def _edges() -> dict[tuple[str, str], dict[str, list[str]]]:
    """Alle Kanten zwischen Kernpaketen, je Art mit ihren Fundstellen."""
    edges: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    sources = _sources()
    files = [path for paths in sources.values() for path in paths]
    assert len(files) > 100, f"nur {len(files)} Quelldateien — der Test hätte fast nichts geprüft"
    for package, paths in sources.items():
        for path in paths:
            own = list(path.relative_to(CORE).with_suffix("").parts)
            if own[-1] == "__init__":
                own.pop()
            for target, kind, line in _imports_of(path, own):
                if target != package:
                    place = f"{path.relative_to(CORE.parent.parent)}:{line}"
                    edges[(package, target)][kind].append(place)
    return edges


def _components(edges: set[tuple[str, str]]) -> list[frozenset[str]]:
    """Die starken Zusammenhangskomponenten über den gegebenen Kanten (Tarjan)."""
    following: dict[str, set[str]] = defaultdict(set)
    for source, target in edges:
        following[source].add(target)
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[frozenset[str]] = []

    def strong(node: str) -> None:
        index[node] = low[node] = len(index)
        stack.append(node)
        on_stack.add(node)
        for other in sorted(following[node]):
            if other not in index:
                strong(other)
                low[node] = min(low[node], low[other])
            elif other in on_stack:
                low[node] = min(low[node], index[other])
        if low[node] == index[node]:
            member = stack.pop()
            members = {member}
            on_stack.discard(member)
            while member != node:
                member = stack.pop()
                members.add(member)
                on_stack.discard(member)
            components.append(frozenset(members))

    for node in sorted(PACKAGES):
        if node not in index:
            strong(node)
    return components


def test_every_core_package_is_known() -> None:
    """Ein vierzehntes Paket hätte keine Zeile und damit keine Regel."""
    on_disk = {
        entry.name
        for entry in CORE.iterdir()
        if entry.is_dir()
        and not entry.name.startswith("_")
        and entry.name != _FOREIGN_DIR
        and any(entry.rglob("*.py"))
    }
    assert on_disk == PACKAGES, (
        f"neu auf der Platte: {sorted(on_disk - PACKAGES)}, "
        f"nur noch hier: {sorted(PACKAGES - on_disk)}"
    )


def test_no_core_package_imports_outside_the_frozen_map() -> None:
    """Eine neue Kante ist eine Entscheidung und steht dann hier — nicht still im Code."""
    offenders: list[str] = []
    for (source, target), kinds in sorted(_edges().items()):
        if kinds["eager"] and (source, target) not in EAGER:
            verdict = "träge erlaubt, eifrig nicht" if (source, target) in LAZY else "nicht erlaubt"
            offenders.extend(
                f"{place}: {source} → {target} eifrig ({verdict})" for place in kinds["eager"]
            )
        if kinds["lazy"] and (source, target) not in EAGER | LAZY:
            offenders.extend(
                f"{place}: {source} → {target} träge (nicht erlaubt)" for place in kinds["lazy"]
            )
    assert not offenders, "Kernpakete importieren an der Karte vorbei:\n" + "\n".join(offenders)


def test_every_frozen_edge_is_still_drawn() -> None:
    """Eine Kante, die niemand mehr zieht, steht nicht in der Liste.

    Sonst deckt der alte Eintrag die nächste Neuauflage, und wer die Liste liest,
    hält eine abgebaute Abhängigkeit für eine bestehende. Eine träge Kante, die
    eifrig geworden ist, gehört nach ``EAGER`` — das fängt der Test darüber.
    """
    edges = _edges()
    stale = [
        f"{source} → {target} (eifrig)"
        for source, target in sorted(EAGER)
        if not edges[(source, target)]["eager"]
    ]
    stale.extend(
        f"{source} → {target} (träge)"
        for source, target in sorted(LAZY)
        if not edges[(source, target)]["lazy"]
    )
    assert not stale, "in der Liste, aber nicht mehr im Code — streichen:\n" + "\n".join(stale)
    assert not EAGER & LAZY, f"eine Kante ist entweder eifrig oder träge: {sorted(EAGER & LAZY)}"


def test_the_eager_cycle_does_not_grow() -> None:
    """Der Kreis über eifrige Importe kennt seine Mitglieder — und keines dazu.

    Gerechnet wird auf den gemessenen Kanten, nicht auf der Liste: Die Liste
    prüfen die Tests darüber, dieser prüft die Sache. Verlässt ein Paket den
    Kreis, schrumpft ``EAGER_CYCLE`` — dann wird die Zeile hier kürzer, und
    genau das soll man sehen.
    """
    eager = {pair for pair, kinds in _edges().items() if kinds["eager"]}
    cycles = sorted((c for c in _components(eager) if len(c) > 1), key=sorted)
    assert cycles == [EAGER_CYCLE], (
        f"eifrige Kreise im Kern: {[sorted(c) for c in cycles]}, "
        f"eingefroren ist {sorted(EAGER_CYCLE)}"
    )
