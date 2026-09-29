"""Fädelt ``rings_by_plane`` durch brep/edit.py (einmaliges Umbauskript, RM-279)."""

import io
import sys

TREE = sys.argv[1]
path = TREE + "/app/core/brep/edit.py"
text = io.open(path, encoding="utf-8", newline="").read()


def swap(old: str, new: str, count: int = 1) -> None:
    global text
    found = text.count(old)
    assert found == count, (old, found)
    text = text.replace(old, new)


swap(
    "    keys: Sequence[str],\n    checked: tuple[int, ...] | None,\n) -> list[EdgeInfo]:\n",
    "    keys: Sequence[str],\n    checked: tuple[int, ...] | None,\n    *,\n    rings_by_plane: bool = True,\n) -> list[EdgeInfo]:\n",
)
swap(
    "        return _wanted(working, choice, keys)\n",
    "        return _wanted(working, choice, keys, rings_by_plane=rings_by_plane)\n",
)
swap(
    "def choose(solid: Solid, choice: EdgeChoice) -> list[EdgeInfo]:\n"
    '    """Die Kanten, die eine benannte Auswahl meint."""\n'
    "    return choose_by_place(edges_of(solid), choice)\n",
    "def choose(solid: Solid, choice: EdgeChoice, *, rings_by_plane: bool = True) -> list[EdgeInfo]:\n"
    '    """Die Kanten, die eine benannte Auswahl meint."""\n'
    "    return choose_by_place(edges_of(solid), choice, rings_by_plane=rings_by_plane)\n",
)
swap(
    "def _wanted(solid: Solid, choice: EdgeChoice, keys: Sequence[str]) -> list[EdgeInfo]:\n",
    "def _wanted(\n    solid: Solid, choice: EdgeChoice, keys: Sequence[str], *, rings_by_plane: bool = True\n) -> list[EdgeInfo]:\n",
)
swap(
    "    return edges_wanted(edges_of(solid), choice, keys)\n",
    "    return edges_wanted(edges_of(solid), choice, keys, rings_by_plane=rings_by_plane)\n",
)
swap(
    "    *,\n    selected_edges: Sequence[int] | None = None,\n    cancelled: CancelToken | None = None,\n    law: RadiusLaw | None = None,\n) -> Solid:\n",
    "    *,\n    selected_edges: Sequence[int] | None = None,\n    rings_by_plane: bool = True,\n    cancelled: CancelToken | None = None,\n    law: RadiusLaw | None = None,\n) -> Solid:\n",
)
swap(
    "    *,\n    selected_edges: Sequence[int] | None = None,\n    shape: ChamferShape | None = None,\n    cancelled: CancelToken | None = None,\n) -> Solid:\n",
    "    *,\n    selected_edges: Sequence[int] | None = None,\n    rings_by_plane: bool = True,\n    shape: ChamferShape | None = None,\n    cancelled: CancelToken | None = None,\n) -> Solid:\n",
)
swap(
    "    chosen = _edges_for(working, choice, keys, checked)\n",
    "    chosen = _edges_for(working, choice, keys, checked, rings_by_plane=rings_by_plane)\n",
    count=2,
)
swap(
    "    ``keys``, ``selected_edges`` und ``cancelled`` wie bei :func:`fillet`:",
    "    ``keys``, ``selected_edges``, ``rings_by_plane`` und ``cancelled`` wie bei\n    :func:`fillet`:",
)
swap(
    "    je Kante, um den nativen Bau und um die Prüfung danach.\n\n    ``law``",
    "    je Kante, um den nativen Bau und um die Prüfung danach.\n\n"
    "    ``rings_by_plane`` wie bei :func:`app.core.geom.edges.choose`: aus nur für\n"
    "    Schritte, die vor Format 37 gespeichert wurden (RM-279).\n\n    ``law``",
)
io.open(path, "w", encoding="utf-8", newline="").write(text)
print("ok")
