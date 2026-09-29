"""Fädelt ``rings_by_plane`` durch edges.py (einmaliges Umbauskript, RM-279)."""

import io
import sys

TREE = sys.argv[1]
path = TREE + "/app/core/geom/edges.py"
text = io.open(path, encoding="utf-8", newline="").read()


def swap(old: str, new: str, count: int = 1) -> None:
    global text
    found = text.count(old)
    assert found == count, (old, found)
    text = text.replace(old, new)


swap(
    "    keys: Sequence[str],\n    selected_edges: Sequence[int] | None,\n) -> list[AnyEdge]:\n",
    "    keys: Sequence[str],\n    selected_edges: Sequence[int] | None,\n    *,\n    rings_by_plane: bool = True,\n) -> list[AnyEdge]:\n",
)
swap(
    "        return wanted(edges, choice, keys)\n",
    "        return wanted(edges, choice, keys, rings_by_plane=rings_by_plane)\n",
)
swap(
    "def wanted[AnyEdge: SelectableEdge](\n    edges: Sequence[AnyEdge], choice: EdgeChoice, keys: Sequence[str]\n) -> list[AnyEdge]:\n",
    "def wanted[AnyEdge: SelectableEdge](\n    edges: Sequence[AnyEdge],\n    choice: EdgeChoice,\n    keys: Sequence[str],\n    *,\n    rings_by_plane: bool = True,\n) -> list[AnyEdge]:\n",
)
swap(
    "    chosen = choose(edges, choice)\n",
    "    chosen = choose(edges, choice, rings_by_plane=rings_by_plane)\n",
)
swap(
    "    chosen = selected_or_wanted(entries, choice, keys, selected_edges)\n",
    "    chosen = selected_or_wanted(\n        entries, choice, keys, selected_edges, rings_by_plane=rings_by_plane\n    )\n",
)
swap(
    "    chosen = selected_or_wanted(edges_of(mesh), choice, keys, selected_edges)\n",
    "    chosen = selected_or_wanted(\n        edges_of(mesh), choice, keys, selected_edges, rings_by_plane=rings_by_plane\n    )\n",
)
# round_edges, bevel_edges, bead_edges, _worked_edges: Schlüsselwort nach selected_edges.
swap(
    "    *,\n    selected_edges: Sequence[int] | None = None,\n    quality: Quality = \"fine\",\n",
    "    *,\n    selected_edges: Sequence[int] | None = None,\n    rings_by_plane: bool = True,\n    quality: Quality = \"fine\",\n",
    count=3,
)
swap(
    "    *,\n    selected_edges: Sequence[int] | None = None,\n    rounded: bool,\n",
    "    *,\n    selected_edges: Sequence[int] | None = None,\n    rings_by_plane: bool = True,\n    rounded: bool,\n",
)
swap(
    "        selected_edges=selected_edges,\n        rounded=True,\n",
    "        selected_edges=selected_edges,\n        rings_by_plane=rings_by_plane,\n        rounded=True,\n",
)
swap(
    "        selected_edges=selected_edges,\n        rounded=False,\n",
    "        selected_edges=selected_edges,\n        rings_by_plane=rings_by_plane,\n        rounded=False,\n",
)
io.open(path, "w", encoding="utf-8", newline="").write(text)
print("ok")
