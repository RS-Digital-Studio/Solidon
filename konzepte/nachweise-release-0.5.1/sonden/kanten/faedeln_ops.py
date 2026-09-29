"""Fädelt ``rings_by_plane`` durch geom/edge_ops.py (einmaliges Umbauskript, RM-279)."""

import io
import sys

TREE = sys.argv[1]
path = TREE + "/app/core/geom/edge_ops.py"
text = io.open(path, encoding="utf-8", newline="").read()


def swap(old: str, new: str, count: int = 1) -> None:
    global text
    found = text.count(old)
    assert found == count, (old, found)
    text = text.replace(old, new)


# Der Satz zum Feld steht einmal, wie _CHOICE_DOC.
swap(
    "#: Und derselbe Satz zum Feld der einzeln gewählten Kanten.\n",
    "#: Wie runde Ränder zu den Gruppen stehen (RM-279) — ein Satz für alle drei.\n"
    "_RINGS_DOC = _(\n"
    '    "Ein runder Rand wie die Mündung einer Bohrung zählt so, wie er steht: senkrecht "\n'
    '    "an einer Seitenwand, waagerecht oben oder unten. Ohne Haken zählt jeder runde Rand "\n'
    '    "als waagerecht, wie in Schritten aus älteren Versionen."\n'
    ")\n\n"
    "#: Und derselbe Satz zum Feld der einzeln gewählten Kanten.\n",
)

FIELD = (
    "    edges: str = param(\n"
    '        title=_("Kanten"),\n'
    '        default="vertical",\n'
    "        choices=EDGE_CHOICES,\n"
    "        doc=_CHOICE_DOC,\n"
    "    )\n"
)
swap(
    FIELD,
    FIELD
    + "    # **Aus nur für gespeicherte Schritte** (RM-279): Bis Format 36 zählte\n"
    "    # jeder Ring als waagerecht, und die Migration 36 → 37 schreibt ihnen den\n"
    "    # Haken aus, damit sie beim Öffnen dieselben Kanten treffen.\n"
    "    rings_by_plane: bool = _rings_param()\n",
    count=3,
)
swap(
    "def _chosen_edges(choice: str, value: str) -> tuple[str, ...]:\n",
    "def _rings_param() -> bool:\n"
    '    """Das Feld „Runde Ränder nach ihrer Lage“ — gleich an allen drei Operationen."""\n'
    "    return cast(\n"
    "        bool,\n"
    "        param(\n"
    '            title=_("Runde Ränder nach ihrer Lage"),\n'
    "            default=True,\n"
    '            placement="advanced",\n'
    "            doc=_RINGS_DOC,\n"
    '            depends_on=("edges", ("vertical", "horizontal", "top", "bottom")),\n'
    "        ),\n"
    "    )\n\n\n"
    "def _chosen_edges(choice: str, value: str) -> tuple[str, ...]:\n",
)

# Die drei Operationen reichen den Wert weiter.
swap(
    "        _chosen_edges(params.edges, params.edge_keys),\n        rounded=True,\n        law=law,\n    )\n",
    "        _chosen_edges(params.edges, params.edge_keys),\n        rounded=True,\n"
    "        rings_by_plane=params.rings_by_plane,\n        law=law,\n    )\n",
)
swap(
    "        _chosen_edges(params.edges, params.edge_keys),\n        rounded=False,\n        shape=chamfer_shape(params),\n    )\n",
    "        _chosen_edges(params.edges, params.edge_keys),\n        rounded=False,\n"
    "        rings_by_plane=params.rings_by_plane,\n        shape=chamfer_shape(params),\n    )\n",
)
swap(
    '        selected_edges=ctx.bound_edges.get("edge_keys"),\n        quality=ctx.quality,\n        cancelled=ctx.cancelled,\n    )\n    empty = _too_small_to_see(body, outcome.mesh, ctx.profile, kind="bead")\n',
    '        selected_edges=ctx.bound_edges.get("edge_keys"),\n        rings_by_plane=params.rings_by_plane,\n'
    '        quality=ctx.quality,\n        cancelled=ctx.cancelled,\n    )\n    empty = _too_small_to_see(body, outcome.mesh, ctx.profile, kind="bead")\n',
)

# _worked
swap(
    "    *,\n    rounded: bool,\n    shape: ChamferShape | None = None,\n    law: RadiusLaw | None = None,\n) -> OpResult:\n",
    "    *,\n    rounded: bool,\n    rings_by_plane: bool = True,\n    shape: ChamferShape | None = None,\n    law: RadiusLaw | None = None,\n) -> OpResult:\n",
)
swap(
    "            selected_edges=bound,\n            profile=ctx.profile,\n            rounded=rounded,\n",
    "            selected_edges=bound,\n            rings_by_plane=rings_by_plane,\n            profile=ctx.profile,\n            rounded=rounded,\n",
)
swap(
    "            selected_edges=bound,\n            quality=ctx.quality,\n            cancelled=ctx.cancelled,\n            narrowest=narrowest_face(ctx.profile),\n            shape=shape,\n",
    "            selected_edges=bound,\n            rings_by_plane=rings_by_plane,\n            quality=ctx.quality,\n            cancelled=ctx.cancelled,\n            narrowest=narrowest_face(ctx.profile),\n            shape=shape,\n",
)
swap(
    "        selected_edges=bound,\n        quality=ctx.quality,\n        cancelled=ctx.cancelled,\n        narrowest=narrowest_face(ctx.profile),\n        law=law,\n",
    "        selected_edges=bound,\n        rings_by_plane=rings_by_plane,\n        quality=ctx.quality,\n        cancelled=ctx.cancelled,\n        narrowest=narrowest_face(ctx.profile),\n        law=law,\n",
)

# _on_a_solid
swap(
    "    *,\n    selected_edges: Sequence[int] | None = None,\n    profile: Profile | None,\n",
    "    *,\n    selected_edges: Sequence[int] | None = None,\n    rings_by_plane: bool = True,\n    profile: Profile | None,\n",
)
swap(
    "                selected_edges=selected_edges,\n                cancelled=cancelled,\n                law=law,\n",
    "                selected_edges=selected_edges,\n                rings_by_plane=rings_by_plane,\n                cancelled=cancelled,\n                law=law,\n",
)
swap(
    "                selected_edges=selected_edges,\n                shape=shape,\n                cancelled=cancelled,\n",
    "                selected_edges=selected_edges,\n                rings_by_plane=rings_by_plane,\n                shape=shape,\n                cancelled=cancelled,\n",
)
swap(
    "            narrowest_face(profile),\n            shape,\n            law,\n        )\n",
    "            narrowest_face(profile),\n            shape,\n            law,\n            rings_by_plane=rings_by_plane,\n        )\n",
)

# _why_it_does_not_fit
swap(
    "    shape: ChamferShape | None = None,\n    law: RadiusLaw | None = None,\n) -> GeometryError | None:\n",
    "    shape: ChamferShape | None = None,\n    law: RadiusLaw | None = None,\n    *,\n    rings_by_plane: bool = True,\n) -> GeometryError | None:\n",
)
swap(
    "        chosen = wanted(entries, choice, keys)\n",
    "        chosen = wanted(entries, choice, keys, rings_by_plane=rings_by_plane)\n",
)
io.open(path, "w", encoding="utf-8", newline="").write(text)
print("ok")
