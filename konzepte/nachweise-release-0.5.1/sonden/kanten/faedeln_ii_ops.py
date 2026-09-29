"""(ii) am exakten Kern: dieselbe Auslassung vor OpenCASCADE (einmaliges Umbauskript)."""

import io
import sys

TREE = sys.argv[1]
path = TREE + "/app/core/geom/edge_ops.py"
text = io.open(path, encoding="utf-8", newline="").read()


def swap(old: str, new: str, count: int = 1) -> None:
    global text
    found = text.count(old)
    assert found == count, (old[:70], found)
    text = text.replace(old, new)


swap(
    """    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid

    try:
        if rounded:""",
    """    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid

    narrow: Finding | None = None
    if selected_edges is None and not keys and choice != "named":
        fitted = _group_that_fits(
            source,
            size,
            choice,
            rounded=rounded,
            narrowest=narrowest_face(profile),
            shape=shape,
            law=law,
            rings_by_plane=rings_by_plane,
        )
        if fitted is not None:
            selected_edges, narrow = fitted
    try:
        if rounded:""",
)
swap(
    """        findings=[dataclasses.replace(empty, object_id=source.id)] if empty is not None else [],
    )


def _why_it_does_not_fit(""",
    """        findings=[
            dataclasses.replace(entry, object_id=source.id)
            for entry in (narrow, empty)
            if entry is not None
        ],
    )


def _group_that_fits(
    source: SceneObject,
    size: float,
    choice: EdgeChoice,
    *,
    rounded: bool,
    narrowest: float,
    shape: ChamferShape | None,
    law: RadiusLaw | None,
    rings_by_plane: bool,
) -> tuple[tuple[int, ...], Finding] | None:
    \"\"\"Die Kanten einer Gruppe am exakten Körper, die das Maß tragen — und der Befund.

    **Dieselbe Frage wie am Netz** (``edges.contact_band_limits``, RM-279 (ii)):
    gefragt an der Tessellierung des Körpers, deren ebene Flächen exakt sind,
    wie :func:`_why_it_does_not_fit`. Eine exakte Kante fällt heraus, wenn ein
    Punkt auf ihr auf einer zu engen Kante der Tessellierung liegt; übrig
    bleiben ihre nativen Indizes für ``selected_edges``. ``None``, wenn jede
    Kante das Maß trägt oder keine — dann bleibt der bisherige Weg mit seiner
    Absage.
    \"\"\"
    import numpy as np

    from app.core.brep import edit
    from app.core.brep.kernel import Solid
    from app.core.geom.edges import (
        contact_band_limits,
        edges_of,
        too_narrow_finding,
        wanted,
    )
    from app.core.units import weld_tolerance

    solid = cast(Solid, source.mesh)
    mesh = as_mesh_data(source.mesh)
    entries = edges_of(mesh)
    tolerance = weld_tolerance(mesh.bounds.diagonal)
    try:
        chosen = wanted(entries, choice, (), rings_by_plane=rings_by_plane)
    except GeometryError:
        return None
    varying = law if law is not None and not law.constant else None
    limits = contact_band_limits(
        entries,
        chosen,
        size,
        rounded=rounded,
        tolerance=tolerance,
        narrowest=narrowest,
        shape=shape,
        law=varying,
    )
    narrow = [entry for entry in chosen if id(entry) in limits]
    if not narrow or len(narrow) == len(chosen):
        return None
    starts = np.concatenate([np.asarray(entry.points[:-1], dtype=float) for entry in narrow])
    stops = np.concatenate([np.asarray(entry.points[1:], dtype=float) for entry in narrow])
    span = stops - starts
    square = np.maximum(np.einsum("ij,ij->i", span, span), 1e-24)

    def on_narrow(point: Vec3) -> bool:
        offset = np.asarray(point, dtype=float) - starts
        share = np.clip(np.einsum("ij,ij->i", offset, span) / square, 0.0, 1.0)
        gap = np.linalg.norm(offset - share[:, None] * span, axis=1)
        return bool(gap.min() <= 10.0 * tolerance + MAX_FACET_SAG)

    group = edit.choose(solid, choice, rings_by_plane=rings_by_plane)
    kept = []
    for entry in group:
        points = edit.edge_points(entry)
        probes = (points[len(points) // 3], points[(2 * len(points)) // 3])
        if not all(on_narrow(point) for point in probes):
            kept.append(entry)
    if not kept or len(kept) == len(group):
        return None
    finding = too_narrow_finding(
        len(group) - len(kept),
        min(limits.values()),
        size,
        worked=len(kept),
        rounded=rounded,
        varying=varying is not None,
        place=narrow[0].points[0],
    )
    return edit.native_edge_indices(solid, kept), finding


def _why_it_does_not_fit(""",
)
swap(
    "from app.core.units import DEGREE_UNIT, EPS_GEOM, format_length\n",
    "from app.core.units import DEGREE_UNIT, EPS_GEOM, MAX_FACET_SAG, format_length\n",
)
io.open(path, "w", encoding="utf-8", newline="").write(text)
print("ok")
