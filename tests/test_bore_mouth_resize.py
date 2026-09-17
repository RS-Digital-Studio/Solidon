"""Schräge Senkbohrungen vollständig ändern und Nachbarwände prüfen."""

from __future__ import annotations

import io
import math
from pathlib import Path

import numpy as np
import pytest

from app.core.deferred import trimesh
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect
from app.core.perceive.relations import cavity_chain_at
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import Feature, OpContext, OpResult, Profile, Quality, Scene, SceneObject
from app.core.units import EPS_GEOM


def _sloping_bore() -> tuple[MeshData, dict[str, Feature], Feature]:
    """Eigene Reproduktion: Ø9, schräge Senkung Ø11 und Nachbarloch Ø9,5.

    Alle Punkte werden hier aus festen Maßen konstruiert. Der Boden liegt
    bei z=3+0,04*x, der Zylinder endet bei z=17+0,10*x und die Senkung an der
    schrägen Außenfläche z=18+0,08*x. Kein Dreieck stammt aus einer Kundendatei.
    """
    sections = 120
    angles = np.arange(sections) * math.tau / sections
    vertices = []
    for radius, height, slope in ((4.5, 3.0, 0.04), (4.5, 17.0, 0.10), (5.5, 18.0, 0.08)):
        x, y = radius * np.cos(angles), radius * np.sin(angles)
        vertices.extend(zip(x, y, height + slope * x, strict=True))
    faces = []
    for ring in range(2):
        for at in range(sections):
            following = (at + 1) % sections
            lower, upper = ring * sections, (ring + 1) * sections
            faces.extend(
                (
                    (lower + at, lower + following, upper + following),
                    (lower + at, upper + following, upper + at),
                )
            )
    for ring, height in ((0, 3.0), (2, 18.0)):
        hub = len(vertices)
        vertices.append((0.0, 0.0, height))
        for at in range(sections):
            faces.append((ring * sections + at, ring * sections + (at + 1) % sections, hub))
    cavity = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    trimesh.repair.fix_normals(cavity)
    stock = trimesh.creation.box(extents=(34.0, 26.0, 18.0))
    stock.apply_translation((5.0, 0.0, 9.0))
    points = np.asarray(stock.vertices).copy()
    top = points[:, 2] > 9.0
    points[top, 2] += 0.08 * points[top, 0]
    stock.vertices = points
    neighbour = trimesh.creation.cylinder(radius=4.75, height=20.0, sections=120)
    neighbour.apply_translation((12.0, 0.0, 13.0))
    mesh = boolean(
        "difference",
        [MeshData.of(stock), MeshData.of(cavity), MeshData.of(neighbour)],
        quality="fine",
    ).mesh
    features = detect(mesh)
    hole = min(
        (feature for feature in features.values() if feature.kind == "hole"),
        key=lambda feature: abs(float(feature.params["centre"][0])),
    )
    return mesh, features, hole


def _resize(
    mesh: MeshData,
    features: dict[str, Feature],
    hole: Feature,
    diameter: float,
    profile: Profile,
    *,
    quality: Quality = "fine",
) -> OpResult:
    """Den registrierten Dialogweg mit denselben Parametern ausführen."""
    return _operation(
        "resize_hole",
        mesh,
        features,
        hole,
        profile,
        diameter=diameter,
        compensate=False,
        quality=quality,
    )


def _operation(
    name: str,
    mesh: MeshData,
    features: dict[str, Feature],
    feature: Feature,
    profile: Profile,
    *,
    quality: Quality = "fine",
    **params: object,
) -> OpResult:
    """Eine Merkmalsoperation durch ihren registrierten Kundenvertrag auswerten."""
    source = SceneObject(id="obj_1", name="Bohrungsprüfung", mesh=mesh, features=features)
    spec = REGISTRY.get(name)
    return spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(at_feature=feature.id, **params),
            profile=profile,
            quality=quality,
            seed=20260915,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def _why_no_rings(body, feature: Feature) -> str:
    """Welche der fünf Absagen ``_face_boundary_rings`` gibt.

    Die Funktion antwortet auf fünf verschiedene Fragen mit demselben ``None``,
    und eine davon trifft auf dem Mac der CI zu. Nachgerechnet wird hier, was
    sie rechnet — die Absage selbst trägt ihren Grund nicht.
    """
    indices = np.asarray(feature.face_indices, dtype=np.int64)
    if not len(indices) or indices.min() < 0 or indices.max() >= len(body.faces):
        return "ungültig: Flächennummern außerhalb des Netzes"
    faces = np.asarray(body.faces)[indices]
    edges = np.sort(np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])), axis=1)
    unique, count = np.unique(edges, axis=0, return_counts=True)
    if (count > 2).any():
        return f"ungültig: {int((count > 2).sum())} Kanten an mehr als zwei Dreiecken"
    boundary = unique[count == 1]
    if not len(boundary):
        return "ungültig: kein Rand — der Ausschnitt ist geschlossen"
    vertices, degrees = np.unique(boundary, return_counts=True)
    if (degrees != 2).any():
        schief = {
            int(grad): int(wie_oft)
            for grad, wie_oft in zip(*np.unique(degrees, return_counts=True), strict=True)
            if grad != 2
        }
        return f"ungültig: ausgefranster Rand, Knotengrade {schief} statt 2"
    from app.core.deferred import trimesh as _trimesh

    for component in _trimesh.graph.connected_components(boundary, nodes=vertices, engine="scipy"):
        if len(component) < 3:
            return f"ungültig: Randkomponente aus nur {len(component)} Knoten"
    return "ungültig: Grund nicht nachgerechnet"


def _who_owns_the_notch(mesh: MeshData, detected: dict, candidates: dict) -> str:
    """Wem die Dreiecke am ausgefransten Rand gehören — frei oder fremd.

    ``features._without_notches`` schließt eine Kerbe nur mit einem **freien**
    Dreieck; gehört es einem anderen Fleck, bleibt sie offen, und das ist
    Absicht. Ob dieser Fall vorliegt, sagt keine Zahl im Merkmal — also hier.
    """
    from app.core.perceive.features import _notch_faces

    body = mesh.raw
    besitzer: dict[int, str] = {}
    for name, feature in detected.items():
        for index in feature.face_indices:
            besitzer[int(index)] = name

    teile = []
    for name, feature in candidates.items():
        kerben = _notch_faces(body, [int(i) for i in feature.face_indices])
        if not kerben:
            continue
        wem = {face: besitzer.get(face, "frei") for face in sorted(kerben)}
        teile.append(f"{name}: Kerbe an {wem}")
    return "Kerben am Rand: " + ("; ".join(teile) if teile else "keine")


def _what_the_border_looks_like(mesh: MeshData, candidates: dict) -> str:
    """Wo der geteilte Punkt liegt und ob das Netz dort eingeschnürt ist.

    Die Fächertrennung liefert auf dem Mac **einen** Ring statt zweier: Der
    Rand der Senkung läuft dort durch einen Punkt. Zwei Erklärungen bleiben,
    und sie verlangen verschiedene Fixe — im Kegel steckt ein Dreieck, das
    nicht zum Mantel gehört, oder das Netz berührt sich an dieser Stelle
    wirklich selbst. Gemessen wird beides: die Höhen der Randknoten (ein
    Mantel hat zwei Niveaus) und ob ein zweiter Eckpunkt auf demselben Ort
    liegt.
    """
    body = mesh.raw
    teile = []
    for name, feature in candidates.items():
        indices = np.asarray(feature.face_indices, dtype=np.int64)
        faces = np.asarray(body.faces)[indices]
        edges = np.sort(
            np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])), axis=1
        )
        unique, count = np.unique(edges, axis=0, return_counts=True)
        boundary = unique[count == 1]
        if not len(boundary):
            continue
        nodes, degrees = np.unique(boundary, return_counts=True)
        shared = nodes[degrees > 2]
        if not len(shared):
            continue
        punkte = np.asarray(body.vertices)
        hoehen = sorted({round(float(punkte[int(n)][2]), 3) for n in nodes})
        zeile = [f"{name}: Randhöhen {hoehen[:3]}…{hoehen[-3:] if len(hoehen) > 6 else ''}"]
        for node in shared:
            ort = punkte[int(node)]
            gleich = int(np.sum(np.all(np.isclose(punkte, ort, atol=1e-9), axis=1)))
            zeile.append(
                f"  Ecke {int(node)} bei {np.round(ort, 4).tolist()}, "
                f"Grad {int(degrees[nodes == node][0])}, "
                f"{gleich} Eckpunkt(e) an diesem Ort"
            )
        teile.append("\n".join(zeile))
    return "Randbild:\n" + ("\n".join(teile) if teile else "  keine geteilte Ecke")


def _why_no_chain(mesh: MeshData, detected: dict, chosen: Feature) -> str:
    """Warum aus diesen Merkmalen keine Kette wurde — für einen Lauf, den ich nicht sehe.

    ``cavity_chain_at`` antwortet mit ``None`` auf drei verschiedene Fragen:
    kein Nachbar, mehrdeutiger Nachbar, ungültiger Rand. Auf dem Mac der CI
    kam am 17.09.2026 eine davon heraus und auf Windows und Ubuntu keine —
    ohne die Zwischenschritte ist das ein ``assert None is not None`` und
    sonst nichts. Gemessen kostet die Auskunft nur im Fehlerfall etwas.
    """
    from app.core.perceive.relations import _cavity_links, _shoulder_connections, boundary_rings
    from app.core.types import is_a_cavity

    body = mesh.raw
    candidates = {
        name: feature
        for name, feature in detected.items()
        if feature.kind in {"hole", "cone"} and is_a_cavity(feature)
    }
    zeilen = [
        f"Netz: {len(body.faces)} Dreiecke, {len(body.vertices)} Ecken",
        f"gewählt war {chosen.id} ({chosen.kind})",
        "erkannt:",
    ]
    for name, feature in sorted(detected.items()):
        masse = {
            key: round(float(value), 4)
            for key, value in feature.params.items()
            if key in {"diameter", "depth", "angle"} and isinstance(value, int | float)
        }
        zeilen.append(f"  {name} {feature.kind} {masse}")

    owners: dict[frozenset[tuple[int, int]], list[str]] = {}
    zeilen.append("Randringe je Hohlraumabschnitt:")
    for name, feature in candidates.items():
        rings = boundary_rings(body, feature)
        grund = _why_no_rings(body, feature) if rings is None else str(len(rings))
        zeilen.append(f"  {name}: {grund} ({len(feature.face_indices)} Dreiecke)")
        for ring in rings or ():
            owners.setdefault(ring, []).append(name)

    geteilt = {tuple(sorted(names)) for names in owners.values() if len(names) > 1}
    zeilen.append(f"gemeinsame Ringe: {sorted(geteilt) or 'keine'}")
    zeilen.append(_who_owns_the_notch(mesh, detected, candidates))
    zeilen.append(_what_the_border_looks_like(mesh, candidates))
    schultern = _shoulder_connections(body, owners, candidates)
    zeilen.append(f"Schulterverbindungen: {[sorted(set(a)) for a, _f in schultern] or 'keine'}")
    graph, invalid, touching = _cavity_links(candidates, mesh)
    zeilen.append(f"Graph: { {k: sorted(v) for k, v in graph.items()} }")
    zeilen.append(f"ungültig: {sorted(invalid)}, berührend: {sorted(touching)}")
    return "\n".join(zeilen)


def _contains(mesh: MeshData, points: list[tuple[float, float, float]]) -> np.ndarray:
    """Innen/Außen unabhängig aus der Summe der orientierten Raumwinkel."""
    inside = []
    for point in points:
        directions = np.asarray(mesh.raw.triangles) - np.asarray(point)
        directions /= np.linalg.norm(directions, axis=2)[:, :, None]
        first, second, third = directions.transpose(1, 0, 2)
        numerator = np.einsum("ij,ij->i", first, np.cross(second, third))
        denominator = (
            1.0
            + np.einsum("ij,ij->i", first, second)
            + np.einsum("ij,ij->i", second, third)
            + np.einsum("ij,ij->i", third, first)
        )
        angle = 2.0 * np.arctan2(numerator, denominator).sum()
        inside.append(abs(angle) > 2.0 * np.pi)
    return np.asarray(inside)


def test_sloping_bore_and_its_entire_countersink_share_one_chain() -> None:
    """Der echte gemeinsame Rand entscheidet trotz des schrägen Kegelfits."""
    mesh, features, hole = _sloping_bore()
    chain = cavity_chain_at(hole, features, mesh)
    assert chain is not None
    assert [section.kind for section in chain] == ["hole", "cone"]


def test_numerically_unchanged_diameter_does_not_recut_a_bore(profile: Profile) -> None:
    """Die bestehende Gleichheitsgrenze gilt vor jedem möglichen Neuschnitt."""
    mesh, features, hole = _sloping_bore()
    diameter = float(hole.params["diameter"]) - EPS_GEOM / 2.0
    result = _resize(mesh, features, hole, diameter, profile)
    changed = result.outputs[0].mesh
    assert isinstance(changed, MeshData)
    assert np.array_equal(changed.raw.vertices, mesh.raw.vertices)
    assert np.array_equal(changed.raw.faces, mesh.raw.faces)
    assert result.solver is None


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("diameter", [4.0, 10.0])
def test_follow_keeps_the_countersink_width_angle_and_blind_floor(
    profile: Profile, kind: str, diameter: float
) -> None:
    """Beide Kerne ändern Schaft und Einlauf mit denselben unabhängigen Sollmaßen."""
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data
    from app.core.sketch.planes import frame_of

    exact = edit.bore_profile(
        edit.box(30.0, 24.0, 12.0),
        [(0.0, 2.0), (3.0, 2.0), (3.0, 10.0), (5.0, 12.0), (0.0, 12.0), (0.0, 2.0)],
        frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
    )
    body = exact if kind == "brep" else as_mesh_data(exact)
    features = features_of(exact) if kind == "brep" else detect(body)
    hole = next(f for f in features.values() if f.kind == "hole")
    source = SceneObject(id="obj_1", name="Senkbohrung", kind=kind, mesh=body, features=features)
    spec = REGISTRY.get("resize_hole")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(at_feature=hole.id, diameter=diameter, entrance_mode="follow"),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    changed = result.outputs[0]
    assert changed.kind == kind
    mesh = as_mesh_data(changed.mesh)
    assert mesh.is_watertight and mesh.raw.nondegenerate_faces().all()
    radius = diameter / 2.0
    assert _contains(mesh, [(radius + 0.6, 0.0, 10.5), (0.0, 0.0, 1.99)]).all()
    assert not _contains(mesh, [(radius + 0.4, 0.0, 10.5), (0.0, 0.0, 2.01)]).any()
    found = features_of(changed.mesh) if kind == "brep" else detect(mesh)
    sink = next(f for f in found.values() if f.kind == "cone")
    previous_sink = next(f for f in features.values() if f.kind == "cone")
    assert sink.params["angle"] == pytest.approx(previous_sink.params["angle"], abs=0.2)
    assert sink.params["diameter"] == pytest.approx(diameter + 4.0, abs=0.05)
    assert hole.id in changed.features
    if kind == "brep":
        expected = 30.0 * 24.0 * 12.0 - math.pi * radius**2 * 8.0
        expected -= math.pi * 2.0 / 3.0 * (radius**2 + radius * (radius + 2) + (radius + 2) ** 2)
        assert changed.mesh.volume == pytest.approx(expected, abs=1e-5)


def test_follow_default_is_explicit_only_for_a_suitable_feature_action(profile: Profile) -> None:
    """Alte Operationen behalten keep; die belegte Senkbohrung bietet follow an."""
    from app.core.perceive.actions import actions_for

    mesh, features, hole = _sloping_bore()
    spec = REGISTRY.get("resize_hole")
    assert spec.params(at_feature=hole.id).entrance_mode == "keep"
    action = next(a for a in actions_for(hole, features, mesh=mesh) if a.op == "resize_hole")
    assert next(f.value for f in action.fields if f.name == "entrance_mode") == "follow"


@pytest.mark.parametrize("mode", ["keep", "follow"])
def test_resized_bore_keeps_its_proven_nominal_diameter(profile: Profile, mode: str) -> None:
    """Die neue Wand hat Sehnenfehler; ihr bekanntes Operationsmaß driftet dadurch nicht."""
    mesh, features, hole = _sloping_bore()
    changed = _operation(
        "resize_hole", mesh, features, hole, profile, diameter=14.86, entrance_mode=mode
    ).outputs[0]
    resized = changed.features[hole.id]
    origin = np.asarray(hole.params["centre"])
    axis = np.asarray(hole.params["axis"])
    axis /= np.linalg.norm(axis)
    vertices = changed.mesh.raw.vertices[np.unique(changed.mesh.raw.faces[resized.face_indices, :])]
    offset = vertices - origin
    radii = np.linalg.norm(offset - np.outer(offset @ axis, axis), axis=1)
    assert radii.max() == pytest.approx(7.43, abs=1e-5)
    assert radii.min() >= 7.43 * math.cos(math.pi / 48) - 1e-5
    assert resized.params["diameter"] == pytest.approx(14.86, abs=EPS_GEOM)
    assert resized.provenance == "generated"
    unchanged = _operation(
        "resize_hole",
        changed.mesh,
        changed.features,
        resized,
        profile,
        diameter=14.86,
        entrance_mode=mode,
    )
    assert unchanged.solver is None
    assert np.array_equal(unchanged.outputs[0].mesh.raw.vertices, changed.mesh.raw.vertices)


def test_repeated_follow_keeps_the_nominal_angle_without_facet_drift(profile: Profile) -> None:
    """Wiederholte Änderungen verwenden den gesetzten Winkel statt den erneuten Facettenfit."""
    mesh, features, hole = _sloping_bore()
    sink = next(f for f in features.values() if f.kind == "cone")
    angle = sink.params["angle"]
    for diameter in (6.0, 8.0, 6.0):
        changed = _operation(
            "resize_hole",
            mesh,
            features,
            hole,
            profile,
            diameter=diameter,
            entrance_mode="follow",
        ).outputs[0]
        assert changed.features[sink.id].params["angle"] == pytest.approx(angle, abs=EPS_GEOM)
        indices = changed.features[sink.id].face_indices
        vertices = changed.mesh.raw.vertices[np.unique(changed.mesh.raw.faces[indices, :])]
        radii = np.linalg.norm(vertices[:, :2], axis=1)
        expected = diameter / 2.0 + (vertices[:, 2] - 17.0) * math.tan(math.radians(angle / 2.0))
        assert np.all(radii <= expected + 1e-5)
        assert np.all(radii >= expected * math.cos(math.pi / 48) - 1e-5)
        mesh, features, hole = changed.mesh, changed.features, changed.features[hole.id]


@pytest.mark.parametrize("sections", [24, 72])
def test_nominal_bore_uses_the_actual_tool_subdivision(sections: int) -> None:
    """Der Feldschnitt mit 72 Segmenten braucht ein engeres Band als das 48er-Bohrwerkzeug."""
    from dataclasses import replace

    from app.core.geom.prepare_ops import _with_nominal_bore

    nominal = 10.0
    radius = nominal / 2.0 * (math.cos(math.pi / sections) + math.cos(math.pi / 48)) / 2.0
    mesh = MeshData.of(trimesh.creation.annulus(r_min=radius, r_max=8, height=8, sections=72))
    found = next(feature for feature in detect(mesh).values() if feature.kind == "hole")
    expected = replace(found, params={**found.params, "diameter": nominal})
    actual = _with_nominal_bore(mesh, found, expected, nominal, sections=sections)
    if sections < 48:
        assert actual.params["diameter"] == pytest.approx(nominal, abs=EPS_GEOM)
    else:
        assert actual is found


def test_resized_known_bore_uses_bounded_detection(monkeypatch) -> None:
    """Der neue Sollumfang gelangt vor der Zuordnung in die lokale Suche."""
    from app.core.geom import prepare_ops
    from app.core.perceive import local

    mesh, _features, hole = _sloping_bore()
    observed = []
    real = local.detect_known

    def bounded(body, expected, **kwargs):
        observed.extend(expected.values())
        return real(body, expected, **kwargs)

    monkeypatch.setattr(local, "FEATURE_LIMIT_TRIANGLES", 0)
    monkeypatch.setattr(local, "detect_known", bounded)
    result = prepare_ops._recognised_resized_feature(mesh, hole, float(hole.params["diameter"]))
    assert result is not None and result.id == hole.id
    assert len(observed) == 1 and observed[0].id == hole.id
    assert observed[0].params["diameter"] == hole.params["diameter"]


@pytest.mark.parametrize("diameter", [6.0, 10.0])
def test_follow_sends_every_expected_section_to_the_bounded_search(
    profile: Profile, monkeypatch, diameter: float
) -> None:
    """Die lokale Nachprüfung kennt Schaft und Senkung vor dem ersten Fit gemeinsam."""
    from app.core.perceive import local

    mesh, features, hole = _sloping_bore()
    chain = cavity_chain_at(hole, features, mesh)
    assert chain is not None
    observed = []
    real = local.detect_known

    def bounded(body, expected, **kwargs):
        observed.append(dict(expected))
        assert kwargs["check_cancelled"] is not None
        return real(body, expected, **kwargs)

    monkeypatch.setattr(local, "FEATURE_LIMIT_TRIANGLES", 0)
    monkeypatch.setattr(local, "detect_known", bounded)
    changed = _operation(
        "resize_hole", mesh, features, hole, profile, diameter=diameter, entrance_mode="follow"
    ).outputs[0]
    assert len(observed) == 1
    assert set(observed[0]) == {section.id for section in chain}
    assert all(section.id in changed.features for section in chain)
    assert changed.features[hole.id].params["diameter"] == pytest.approx(diameter, abs=EPS_GEOM)


def test_large_mesh_resize_keeps_the_real_blind_depth(profile: Profile, monkeypatch) -> None:
    """Ø6 auf Ø8 am echten Millionennetz: Sackloch, Volumen und örtliche Suche bleiben belegt."""
    from app.core.perceive import features as detection
    from app.core.perceive import local
    from tests.test_local_detection import blind_cylinder, bore_seed

    mesh = blind_cylinder(dense=True)
    assert mesh.triangle_count > local.FEATURE_LIMIT_TRIANGLES
    face, point, normal = bore_seed(mesh)
    found = local.detect_local(mesh, point, normal=normal, radius=8, seed_faces=(face,))
    assert found.complete
    hole = next(feature for feature in found.features.values() if feature.kind == "hole")
    actual = detection.detect

    def limited(body, **kwargs):
        assert body.triangle_count <= local.FEATURE_LIMIT_TRIANGLES
        return actual(body, **kwargs)

    monkeypatch.setattr(detection, "detect", limited)
    result = _resize(mesh, found.features, hole, 8.0, profile)
    changed = result.outputs[0]
    assert changed.mesh.is_watertight and changed.mesh.component_count == 1
    assert result.solver is not None and result.solver.strategy == "direct"
    resized = changed.features[hole.id]
    assert resized.params["diameter"] == pytest.approx(8.0, abs=EPS_GEOM)
    assert resized.params["depth"] == pytest.approx(5.0, abs=EPS_GEOM)
    assert resized.params["through"] is False
    previous_area = 0.5 * 1024 * math.sin(math.tau / 1024) * 3.0**2
    new_area = 0.5 * 48 * math.sin(math.tau / 48) * 4.0**2
    assert mesh.volume - changed.mesh.volume == pytest.approx(
        5.0 * (new_area - previous_area), abs=1e-6
    )


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_follow_preserves_a_radial_shoulder_before_the_cone(profile: Profile, kind: str) -> None:
    """Eine echte Ringschulter vor der Senkung bleibt mit ihrer radialen Breite erhalten."""
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data
    from app.core.sketch.planes import frame_of

    exact = edit.bore_profile(
        edit.box(30.0, 24.0, 12.0),
        [(0.0, 2.0), (3.0, 2.0), (3.0, 10.0), (4.0, 10.0), (6.0, 12.0), (0.0, 12.0), (0.0, 2.0)],
        frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
    )
    body = exact if kind == "brep" else as_mesh_data(exact)
    features = features_of(exact) if kind == "brep" else detect(body)
    hole = next(f for f in features.values() if f.kind == "hole")
    source = SceneObject(id="obj_1", name="Senkbohrung", kind=kind, mesh=body, features=features)
    spec = REGISTRY.get("resize_hole")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(at_feature=hole.id, diameter=4.0, entrance_mode="follow"),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    changed = result.outputs[0]
    mesh = as_mesh_data(changed.mesh)
    assert mesh.is_watertight
    assert _contains(mesh, [(2.5, 0.0, 9.9), (3.6, 0.0, 10.5)]).all()
    assert not _contains(mesh, [(2.5, 0.0, 10.1), (3.4, 0.0, 10.5)]).any()
    if kind == "brep":
        expected = 30.0 * 24.0 * 12.0 - math.pi * 2.0**2 * 8.0
        expected -= math.pi * 2.0 / 3.0 * (3.0**2 + 3.0 * 5.0 + 5.0**2)
        assert changed.mesh.volume == pytest.approx(expected, abs=1e-5)


def test_follow_reports_when_only_the_sink_opens_an_outer_flank(profile: Profile) -> None:
    """Auch ein intakter Schaft kann über seine größer werdende Senkung die Außenwand öffnen."""
    from app.core.brep import edit
    from app.core.geom.mesh import as_mesh_data
    from app.core.sketch.planes import frame_of

    exact = edit.bore_profile(
        edit.box(14.0, 24.0, 12.0),
        [(0.0, 2.0), (3.0, 2.0), (3.0, 10.0), (5.0, 12.0), (0.0, 12.0), (0.0, 2.0)],
        frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
    )
    mesh = as_mesh_data(exact)
    features = detect(mesh)
    hole = next(f for f in features.values() if f.kind == "hole")
    result = _operation(
        "resize_hole", mesh, features, hole, profile, diameter=12.0, entrance_mode="follow"
    )
    assert any(f.code == "bore.over_the_edge" for f in result.findings)


def test_follow_checks_the_actual_mouth_below_a_taller_neighbour(profile: Profile) -> None:
    """Der hohe Nachbarkörper verschiebt keine Mündung ans obere Ende der Gesamthülle."""
    from app.core.brep import edit
    from app.core.geom.mesh import as_mesh_data
    from app.core.sketch.planes import frame_of

    exact = edit.bore_profile(
        edit.box(30.0, 24.0, 12.0),
        [(0.0, 2.0), (3.0, 2.0), (3.0, 10.0), (5.0, 12.0), (0.0, 12.0), (0.0, 2.0)],
        frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
    )
    raw = as_mesh_data(exact).raw.copy()
    raw.apply_transform(trimesh.transformations.rotation_matrix(math.radians(7), (0, 1, 0)))
    taller = trimesh.creation.box(extents=(3.0, 3.0, 80.0))
    taller.apply_translation((30.0, 0.0, 40.0))
    mesh = MeshData.of(trimesh.util.concatenate([raw, taller]))
    features = detect(mesh)
    hole = next(f for f in features.values() if f.kind == "hole")
    result = _operation(
        "resize_hole", mesh, features, hole, profile, diameter=4.0, entrance_mode="follow"
    )
    assert not any(f.code == "bore.over_the_edge" for f in result.findings)


@pytest.mark.parametrize("diameter", [6.0, 10.0, 14.86])
@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_follow_opens_a_sloping_mouth_and_keeps_its_sloping_floor(
    profile: Profile, diameter: float, quality: Quality
) -> None:
    """Die nominale Senkung bleibt auch an der schräg geschnittenen Außenfläche vollständig."""
    mesh, features, hole = _sloping_bore()
    result = _operation(
        "resize_hole",
        mesh,
        features,
        hole,
        profile,
        diameter=diameter,
        compensate=False,
        entrance_mode="follow",
        quality=quality,
    )
    changed = result.outputs[0].mesh
    assert isinstance(changed, MeshData)
    assert changed.is_watertight and changed.raw.nondegenerate_faces().all()
    radius = diameter / 2.0
    assert not _contains(changed, [(radius + 0.2, 0.0, 17.8)]).any()
    assert _contains(changed, [(0.0, 0.0, 2.99), (radius - 0.1, 0.0, 2.99)]).all()
    assert not _contains(changed, [(0.0, 0.0, 3.01)]).any()
    assert hole.id in result.outputs[0].features
    reread = trimesh.load(io.BytesIO(changed.raw.export(file_type="stl")), file_type="stl")
    assert reread.is_watertight and reread.nondegenerate_faces().all()


@pytest.mark.parametrize("conical", [False, True])
@pytest.mark.parametrize("diameter", [4.0, 8.0])
def test_follow_moves_all_unambiguous_steps_by_the_same_radial_amount(
    profile: Profile, conical: bool, diameter: float
) -> None:
    """Stufenweiten wachsen gemeinsam; ihre Höhe und der Boden bleiben stehen."""
    mesh, features, hole = _stepped_blind_bore(conical, 0.0)
    result = _operation(
        "resize_hole",
        mesh,
        features,
        hole,
        profile,
        diameter=diameter,
        compensate=False,
        entrance_mode="follow",
    )
    changed = result.outputs[0].mesh
    assert isinstance(changed, MeshData)
    radius = diameter / 2.0 + 3.0
    assert not _contains(changed, [(radius - 0.1, 0.0, 16.0)]).any()
    assert _contains(changed, [(radius + 0.1, 0.0, 16.0), (0.0, 0.0, 1.99)]).all()
    assert changed.is_watertight and changed.raw.nondegenerate_faces().all()


def test_follow_rejects_an_inner_undercut_with_the_available_keep_choice(profile: Profile) -> None:
    """Eine äußere Plansenkung verspricht keine still gewählte Änderung der inneren Abschnitte."""
    from app.core.errors import ValidationError

    mesh, features, _hole = _stepped_blind_bore(True, 0.0)
    wide = max(
        (f for f in features.values() if f.kind == "hole"), key=lambda f: f.params["diameter"]
    )
    with pytest.raises(ValidationError) as problem:
        _operation(
            "resize_hole", mesh, features, wide, profile, diameter=4.0, entrance_mode="follow"
        )
    assert problem.value.field == "entrance_mode"
    assert "Nur Bohrungsdurchmesser" in str(problem.value.detail)


def test_follow_on_a_plain_cylinder_is_the_same_operation(profile: Profile) -> None:
    """Ohne Einlauf hat die Wahl keine zusätzliche geometrische Bedeutung."""
    mesh, features, hole = _two_bores(15.0)
    keep = (
        _operation("resize_hole", mesh, features, hole, profile, diameter=8.0, entrance_mode="keep")
        .outputs[0]
        .mesh
    )
    follow = (
        _operation(
            "resize_hole", mesh, features, hole, profile, diameter=8.0, entrance_mode="follow"
        )
        .outputs[0]
        .mesh
    )
    assert np.array_equal(keep.raw.vertices, follow.raw.vertices)
    assert np.array_equal(keep.raw.faces, follow.raw.faces)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_follow_preserves_a_deep_neighbour_outside_the_old_cavity(
    profile: Profile, kind: str
) -> None:
    """Ein weiter Einlauf erlaubt keinen breiten Füllzylinder durch fremde Details."""
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data
    from app.core.sketch.planes import frame_of

    exact = edit.bore_profile(
        edit.box(30.0, 24.0, 12.0),
        [(0.0, 2.0), (3.0, 2.0), (3.0, 10.0), (5.0, 12.0), (0.0, 12.0), (0.0, 2.0)],
        frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
    )
    exact = edit.cut_bore(
        exact, position=(6.5, 0.0, 4.0), direction=(0.0, 0.0, 1.0), diameter=4.0, depth=4.0
    )
    body = exact if kind == "brep" else as_mesh_data(exact)
    features = features_of(exact) if kind == "brep" else detect(body)
    hole = min(
        (f for f in features.values() if f.kind == "hole"), key=lambda f: abs(f.params["centre"][0])
    )
    source = SceneObject(id="obj_1", name="Senkbohrung", kind=kind, mesh=body, features=features)
    spec = REGISTRY.get("resize_hole")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(at_feature=hole.id, diameter=4.0, entrance_mode="follow"),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    probes = [(4.7, 0.0, 4.0), (6.5, 0.0, 4.0)]
    assert not _contains(as_mesh_data(body), probes).any()
    assert not _contains(as_mesh_data(result.outputs[0].mesh), probes).any()


@pytest.mark.parametrize("diameter", [4.0, 10.0])
def test_follow_keeps_an_exact_countersink_on_a_sloping_outer_face(
    profile: Profile, diameter: float
) -> None:
    """Der schräge Schnitt ist eine Ellipse; der Kegel und sein Winkel bleiben exakt."""
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data
    from app.core.sketch.planes import frame_of

    angle = math.radians(7.0)
    co, si = math.cos(angle), math.sin(angle)
    stock = edit.transformed(
        edit.box(30.0, 24.0, 12.0),
        ((co, 0.0, si, 0.0), (0.0, 1.0, 0.0, 0.0), (-si, 0.0, co, 0.0), (0.0, 0.0, 0.0, 1.0)),
    )
    exact = edit.bore_profile(
        stock,
        [(0.0, 2.0), (3.0, 2.0), (3.0, 10.0), (13.0, 20.0), (0.0, 20.0), (0.0, 2.0)],
        frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
    )
    features = features_of(exact)
    hole = next(f for f in features.values() if f.kind == "hole")
    source = SceneObject(
        id="obj_1", name="Schräger Eintritt", kind="brep", mesh=exact, features=features
    )
    spec = REGISTRY.get("resize_hole")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(at_feature=hole.id, diameter=diameter, entrance_mode="follow"),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    changed = result.outputs[0]
    assert changed.kind == "brep" and changed.mesh.is_closed
    mesh = as_mesh_data(changed.mesh)
    assert mesh.is_watertight
    radius = diameter / 2.0
    assert _contains(mesh, [(radius + 0.5, 0.0, 10.4), (0.0, 0.0, 1.99)]).all()
    assert not _contains(mesh, [(radius + 0.3, 0.0, 10.4), (0.0, 0.0, 2.01)]).any()
    assert changed.features[hole.id].params["diameter"] == pytest.approx(diameter, abs=EPS_GEOM)
    sink = next(f for f in features_of(changed.mesh).values() if f.kind == "cone")
    assert sink.params["angle"] == pytest.approx(90.0, abs=EPS_GEOM)


def test_follow_declines_a_duplicated_owner_of_the_same_ring(profile: Profile) -> None:
    """Dieselbe Kegelfläche zweimal ist keine eindeutige Änderungsanweisung."""
    from dataclasses import replace

    from app.core.errors import ValidationError

    mesh, features, hole = _sloping_bore()
    sink = next(f for f in features.values() if f.kind == "cone")
    features["cone_copy"] = replace(sink, id="cone_copy")
    with pytest.raises(ValidationError) as problem:
        _operation(
            "resize_hole", mesh, features, hole, profile, diameter=8.0, entrance_mode="follow"
        )
    assert problem.value.field == "entrance_mode"


def test_follow_does_not_recentre_an_eccentric_counterbore(profile: Profile) -> None:
    """Eine belegte Verbindung erlaubt kein stilles Zentrieren einer versetzten Stufe."""
    from app.core.errors import ValidationError

    stock = trimesh.creation.box(extents=(30.0, 24.0, 18.0))
    stock.apply_translation((0.0, 0.0, 9.0))
    inner = trimesh.creation.cylinder(radius=3.0, height=17.0, sections=96)
    inner.apply_translation((0.0, 0.0, 10.5))
    outer = trimesh.creation.cylinder(radius=6.0, height=8.0, sections=96)
    outer.apply_translation((0.2, 0.0, 16.0))
    mesh = boolean(
        "difference", [MeshData.of(stock), MeshData.of(inner), MeshData.of(outer)], quality="fine"
    ).mesh
    features = detect(mesh)
    hole = min(
        (f for f in features.values() if f.kind == "hole"), key=lambda f: f.params["diameter"]
    )
    assert cavity_chain_at(hole, features, mesh) is not None
    with pytest.raises(ValidationError):
        _operation(
            "resize_hole", mesh, features, hole, profile, diameter=4.0, entrance_mode="follow"
        )


def test_follow_survives_project_roundtrip_and_one_undo_redo(
    profile: Profile, tmp_path: Path
) -> None:
    """Der gespeicherte Umfang berechnet nach dem Laden dasselbe Ergebnis als einen Schritt."""
    from app.core.geom.mesh import as_mesh_data
    from app.core.ingest.plan import import_plan
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, checksum, load, new_project, save
    from app.core.types import Source

    mesh, _features, _hole = _sloping_bore()
    payload = mesh.raw.export(file_type="stl")
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/bore.stl", sha256=checksum(payload)
    )
    project.sources["src_1"] = payload
    plan = import_plan("src_1", "bore.stl", payload, first_model=True)
    history = History(project.document)
    history.apply(plan.title, [plan.draft])
    before = evaluate(project.document, profile, sources=ProjectSources(project))
    original = before.scene.objects["obj_1"]
    hole = min(
        (f for f in original.features.values() if f.kind == "hole"),
        key=lambda f: f.params["diameter"],
    )
    history.apply(
        "Bohrung mit Einlauf ändern",
        [
            OperationDraft(
                op="resize_hole",
                inputs=(original.id,),
                params={
                    "at_feature": hole.id,
                    "diameter": 6.0,
                    "entrance_mode": "follow",
                    "compensate": False,
                },
                seed=7,
            )
        ],
    )
    after = evaluate(project.document, profile, sources=ProjectSources(project))
    assert after.complete
    changed = as_mesh_data(after.scene.objects["obj_1"].mesh)
    path = save(project, tmp_path / "follow.p3d")
    reopened = load(path)
    assert reopened.document.ops[-1].params["entrance_mode"] == "follow"
    restored = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    loaded_mesh = as_mesh_data(restored.scene.objects["obj_1"].mesh)
    assert np.array_equal(changed.raw.vertices, loaded_mesh.raw.vertices)
    assert np.array_equal(changed.raw.faces, loaded_mesh.raw.faces)
    history.undo()
    undone = evaluate(project.document, profile, sources=ProjectSources(project))
    undo_mesh = as_mesh_data(undone.scene.objects["obj_1"].mesh)
    assert np.array_equal(as_mesh_data(original.mesh).raw.vertices, undo_mesh.raw.vertices)
    assert np.array_equal(as_mesh_data(original.mesh).raw.faces, undo_mesh.raw.faces)
    history.redo()
    redone = evaluate(project.document, profile, sources=ProjectSources(project))
    redo_mesh = as_mesh_data(redone.scene.objects["obj_1"].mesh)
    assert np.array_equal(changed.raw.vertices, redo_mesh.raw.vertices)
    assert np.array_equal(changed.raw.faces, redo_mesh.raw.faces)


def test_resize_a_shallow_bore_also_opens_its_rounded_entrance(profile: Profile) -> None:
    """Die kurze Bohrung reicht bis zur Außenfläche, ihr Boden bleibt bei 1,5 mm."""
    from tests.data.make_corpus import rounded_magnet_bore

    mesh = MeshData.of(rounded_magnet_bore())
    features = detect(mesh)
    hole = next(feature for feature in features.values() if feature.kind == "hole")
    changed = _resize(mesh, features, hole, 10.0, profile).outputs[0].mesh
    assert isinstance(changed, MeshData)
    lips = [(4.9, 0.0, z) for z in (0.01, 0.1, 0.25, 1.49)]
    assert _contains(mesh, lips).all()
    assert not _contains(changed, lips).any()
    assert _contains(changed, [(0.0, 0.0, 1.501)]).all()
    assert not _contains(changed, [(0.0, 0.0, 1.499)]).any()


def test_resize_reaches_the_sloping_mouth_and_keeps_the_floor(profile: Profile) -> None:
    """An der alten Mündung bleibt kein Material innerhalb des neuen Lochs."""
    mesh, features, hole = _sloping_bore()
    result = _resize(mesh, features, hole, 14.86, profile)
    changed = result.outputs[0].mesh
    assert isinstance(changed, MeshData)
    assert changed.is_watertight
    # Der gemeldete Span liegt tatsächlich im Material, nicht nur in einer
    # orangefarbenen Auswahlschicht. Beide Höhen liegen unter der Außenfläche.
    lips = [(6.0, 0.0, 18.1), (6.0, 0.0, 18.3)]
    assert _contains(mesh, lips).all()
    assert not _contains(changed, lips).any()
    # Der schräge Sacklochboden bleibt bei z=3+0,04*x, auch am neuen Radius.
    assert _contains(changed, [(0.0, 0.0, 2.99), (6.0, 0.0, 3.23)]).all()
    assert not _contains(changed, [(0.0, 0.0, 3.01), (6.0, 0.0, 3.25)]).any()
    assert any(finding.code == "resize.widening_swallowed" for finding in result.findings)


def test_resize_reports_the_new_connection_to_its_neighbour(profile: Profile) -> None:
    """Die unterbrochene innere Wand ist auch ohne neue Komponente ein Konflikt."""
    mesh, features, hole = _sloping_bore()
    result = _resize(mesh, features, hole, 14.86, profile)
    conflicts = [finding for finding in result.findings if finding.code == "bore.neighbour_opened"]
    assert len(conflicts) == 1
    assert hole.id in conflicts[0].feature_ids
    assert len(conflicts[0].feature_ids) == 2


def _two_bores(
    spacing: float, *, upper: bool = False
) -> tuple[MeshData, dict[str, Feature], Feature]:
    """Zwei bekannte Sacklöcher, auf Wunsch ohne gemeinsame Tiefenlage."""
    stock = trimesh.creation.box(extents=(36.0, 24.0, 24.0))
    stock.apply_translation((6.0, 0.0, 12.0))
    first = trimesh.creation.cylinder(radius=3.0, height=8.0, sections=96)
    first.apply_translation((0.0, 0.0, 4.0))
    second = trimesh.creation.cylinder(radius=3.0, height=8.0, sections=96)
    second.apply_translation((spacing, 0.0, 20.0 if upper else 4.0))
    mesh = boolean(
        "difference", [MeshData.of(stock), MeshData.of(first), MeshData.of(second)], quality="fine"
    ).mesh
    features = detect(mesh)
    hole = min(
        (feature for feature in features.values() if feature.kind == "hole"),
        key=lambda feature: abs(float(feature.params["centre"][0])),
    )
    return mesh, features, hole


@pytest.mark.parametrize("upper", [False, True])
def test_projected_neighbours_only_warn_when_their_depths_overlap(
    profile: Profile, upper: bool
) -> None:
    """Ein Abstand im Grundriss allein beweist keine verlorene Trennwand."""
    mesh, features, hole = _two_bores(7.5, upper=upper)
    result = _resize(mesh, features, hole, 10.0, profile)
    assert any(f.code == "bore.neighbour_opened" for f in result.findings) is not upper


def test_resize_reports_a_remaining_wall_below_the_material_limit(profile: Profile) -> None:
    """Eine noch geschlossene, zu dünne Nachbarwand wird ebenfalls benannt."""
    wall = profile.minimum_wall_thickness / 2.0
    mesh, features, hole = _two_bores(8.0 + wall)
    result = _resize(mesh, features, hole, 10.0, profile)
    findings = [f for f in result.findings if f.code == "bore.neighbour_wall_thin"]
    assert len(findings) == 1
    assert float(findings[0].values["thickness"]) == pytest.approx(wall, abs=0.01)


def test_resize_preserves_a_sufficient_neighbour_wall(profile: Profile) -> None:
    """Eine tragende Restwand bekommt keine vorsorgliche Warnung."""
    mesh, features, hole = _two_bores(8.0 + profile.minimum_wall_thickness * 2.0)
    result = _resize(mesh, features, hole, 10.0, profile)
    assert not [f for f in result.findings if f.code.startswith("bore.neighbour_")]


@pytest.mark.parametrize("diameter", [6.0, 10.0, 14.86])
@pytest.mark.parametrize("turned", [False, True])
def test_resize_keeps_the_sloping_floor_and_the_feature_reference(
    profile: Profile, diameter: float, turned: bool
) -> None:
    """Die tatsächlichen Endflächen tragen auch nach freier Drehung und Versatz."""
    mesh, features, hole = _sloping_bore()
    transform = np.eye(4)
    if turned:
        transform = trimesh.transformations.rotation_matrix(0.73, (1.0, 2.0, 3.0))
        transform[:3, 3] = (17.0, -31.0, 9.0)
        body = mesh.raw.copy()
        body.apply_transform(transform)
        mesh = MeshData.of(body)
        features = detect(mesh)
        expected = trimesh.transform_points([[0.0, 0.0, 10.0]], transform)[0]
        hole = min(
            (f for f in features.values() if f.kind == "hole"),
            key=lambda f: np.linalg.norm(np.asarray(f.params["centre"]) - expected),
        )
    result = _resize(mesh, features, hole, diameter, profile)
    changed = result.outputs[0].mesh
    assert isinstance(changed, MeshData)
    assert changed.is_watertight
    radius = -(diameter / 2.0 - 0.05)
    floor = 3.0 + 0.04 * radius
    probes = trimesh.transform_points(
        [(radius, 0.0, floor - 0.01), (radius, 0.0, floor + 0.01)], transform
    )
    assert _contains(changed, probes).tolist() == [True, False]
    assert hole.id in result.outputs[0].features


def test_moderate_growth_keeps_the_outer_countersink_surface(profile: Profile) -> None:
    """Der Zylinder wächst bis in den Kegel; dessen verbleibende Außenform bleibt."""
    mesh, features, hole = _sloping_bore()
    result = _resize(mesh, features, hole, 10.0, profile)
    changed = result.outputs[0].mesh
    assert isinstance(changed, MeshData)
    assert _contains(mesh, [(4.9, 0.0, 17.8)]).all()
    assert not _contains(changed, [(4.9, 0.0, 17.8)]).any()
    probes = [(5.4, 0.0, 18.3), (5.4, 0.0, 18.38)]
    assert _contains(changed, probes).tolist() == _contains(mesh, probes).tolist() == [True, False]
    assert any(f.code == "resize.widening_kept" for f in result.findings)


def test_shrinking_keeps_the_countersink_and_recognises_the_new_shoulder(profile: Profile) -> None:
    """Die unveränderte Senkung hängt über die neue Ringstufe am kleineren Loch."""
    mesh, features, hole = _sloping_bore()
    changed = _resize(mesh, features, hole, 6.0, profile).outputs[0].mesh
    assert isinstance(changed, MeshData)
    # Die alte Übergangsebene wird zur Schulter, nicht zum erhabenen Kragen.
    probes = [(3.5, 0.0, 17.34), (3.5, 0.0, 17.36), (5.4, 0.0, 18.3), (5.4, 0.0, 18.38)]
    assert _contains(changed, probes).tolist() == [True, False, True, False]
    detected = detect(changed)
    smaller = min(
        (f for f in detected.values() if f.kind == "hole"), key=lambda f: f.params["diameter"]
    )
    chain = cavity_chain_at(smaller, detected, changed)
    assert chain is not None, _why_no_chain(changed, detected, smaller)
    assert [f.kind for f in chain] == ["hole", "cone"]


def test_shrinking_a_large_bore_leaves_no_channels_around_the_added_ring(profile: Profile) -> None:
    """Der ergänzte Ring greift am gesamten Umfang in die bisherige Wand."""
    raw = trimesh.creation.revolve(
        [(30.0, 0.0), (50.0, 0.0), (50.0, 10.0), (30.0, 10.0), (30.0, 0.0)], sections=192
    )
    mesh = MeshData.of(raw)
    features = detect(mesh)
    hole = next(f for f in features.values() if f.kind == "hole")
    changed = _resize(mesh, features, hole, 40.0, profile).outputs[0].mesh
    assert isinstance(changed, MeshData)
    angles = (np.arange(48) + 0.5) * math.tau / 48.0
    probes = [(29.97 * math.cos(a), 29.97 * math.sin(a), 5.0) for a in angles]
    assert _contains(changed, probes).all()


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_shrinking_float32_boundaries_does_not_create_degenerate_slivers(
    profile: Profile, quality: Quality
) -> None:
    """Eine STL-genaue Randebene wird beim Auffüllen nicht in Hautdreiecke zerlegt."""
    mesh, _features, _hole = _sloping_bore()
    raw = mesh.raw.copy()
    raw.vertices = np.asarray(raw.vertices, dtype=np.float32).astype(np.float64)
    mesh = MeshData.of(raw)
    assert mesh.is_watertight and mesh.raw.nondegenerate_faces().all()
    features = detect(mesh)
    hole = min(
        (f for f in features.values() if f.kind == "hole"), key=lambda f: f.params["diameter"]
    )
    changed = _resize(mesh, features, hole, 6.0, profile, quality=quality).outputs[0].mesh
    assert isinstance(changed, MeshData)
    assert changed.is_watertight
    assert changed.raw.nondegenerate_faces().all()
    restored = trimesh.load(
        io.BytesIO(changed.raw.export(file_type="stl")), file_type="stl", process=True
    )
    assert restored.is_watertight and restored.nondegenerate_faces().all()


def _stepped_blind_bore(
    conical: bool, slope: float
) -> tuple[MeshData, dict[str, Feature], Feature]:
    """Eigene Stufensenkung mit Ø6/Ø12 und optionalem Kegel Ø6/Ø11."""
    outline = [(12.0, 0.0), (12.0, 17.0), (6.0, 17.0), (6.0, 8.5)]
    if conical:
        outline.extend([(5.5, 8.5), (3.0, 6.0)])
    else:
        outline.append((3.0, 8.5))
    outline.extend([(3.0, 2.0), (0.0, 2.0), (0.0, 0.0), outline[0]])
    raw = trimesh.creation.revolve(outline, sections=120)
    points = np.asarray(raw.vertices).copy()
    points[:, 2] += slope * points[:, 0]
    raw.vertices = points
    mesh = MeshData.of(raw)
    features = detect(mesh)
    hole = min(
        (f for f in features.values() if f.kind == "hole"), key=lambda f: f.params["diameter"]
    )
    return mesh, features, hole


@pytest.mark.parametrize("conical", [False, True])
@pytest.mark.parametrize("slope", [0.0, 0.07])
@pytest.mark.parametrize("diameter", [4.0, 8.0, 14.0])
def test_resize_a_blind_stepped_cavity_preserves_its_floor(
    profile: Profile, conical: bool, slope: float, diameter: float
) -> None:
    """Plan- und Kegelsenkung reichen bis außen; der Boden trägt unverändert."""
    mesh, features, hole = _stepped_blind_bore(conical, slope)
    chain = cavity_chain_at(hole, features, mesh)
    assert chain is not None and len(chain) == (3 if conical else 2)
    result = _resize(mesh, features, hole, diameter, profile)
    changed = result.outputs[0].mesh
    assert isinstance(changed, MeshData)
    assert changed.is_watertight
    radius = diameter / 2.0 - 0.05
    probes = [
        (radius, 0.0, 2.0 + slope * radius - 0.01),
        (radius, 0.0, 2.0 + slope * radius + 0.01),
    ]
    assert _contains(changed, probes).tolist() == [True, False]
    if diameter > 12.0:
        assert not _contains(changed, [(radius, 0.0, 17.0 + slope * radius - 0.01)]).any()
    else:
        assert not _contains(changed, [(5.9, 0.0, 16.0)]).any()
    assert hole.id in result.outputs[0].features


@pytest.mark.parametrize("conical", [False, True])
def test_resizing_the_outer_counterbore_keeps_the_inner_sections(
    profile: Profile, conical: bool
) -> None:
    """Die breitere Plansenkung trägt unter ihrer Stufe nichts vom Innenloch ab."""
    mesh, features, _hole = _stepped_blind_bore(conical, 0.07)
    wide = max(
        (f for f in features.values() if f.kind == "hole"), key=lambda f: f.params["diameter"]
    )
    changed = _resize(mesh, features, wide, 14.0, profile).outputs[0].mesh
    assert isinstance(changed, MeshData)
    assert _contains(changed, [(6.9, 0.0, 8.5 + 0.07 * 6.9 - 0.01)]).all()
    assert not _contains(changed, [(6.9, 0.0, 8.5 + 0.07 * 6.9 + 0.01)]).any()
    assert _contains(changed, [(3.1, 0.0, 3.0)]).all()


@pytest.mark.parametrize("diameter", [4.0, 8.0])
def test_shrinking_the_outer_counterbore_does_not_extend_the_inner_cone(
    profile: Profile, diameter: float
) -> None:
    """Beim Ändern braucht der innere Kegel keinen künstlichen Weg durch die Stufe."""
    mesh, features, _hole = _stepped_blind_bore(True, 0.07)
    wide = max(
        (f for f in features.values() if f.kind == "hole"), key=lambda f: f.params["diameter"]
    )
    changed = _resize(mesh, features, wide, diameter, profile).outputs[0].mesh
    assert isinstance(changed, MeshData)
    radius = diameter / 2.0
    assert _contains(changed, [(radius + 0.05, 0.0, 16.0)]).all()
    assert not _contains(changed, [(radius - 0.05, 0.0, 16.0)]).any()
    assert not _contains(changed, [(5.2, 0.0, 8.3 + 0.07 * 5.2), (2.9, 0.0, 3.0)]).any()


@pytest.mark.parametrize("sections", ["single", "chain"])
def test_removing_a_sloping_countersink_keeps_the_requested_scope(
    profile: Profile, sections: str
) -> None:
    """Nur Senkung oder ganzer Hohlraum: beide Antworten bleiben geometrisch klar."""
    mesh, features, hole = _sloping_bore()
    chain = cavity_chain_at(hole, features, mesh)
    assert chain is not None
    cone = chain[1]
    changed = (
        _operation("remove_feature", mesh, features, cone, profile, sections=sections)
        .outputs[0]
        .mesh
    )
    assert isinstance(changed, MeshData)
    assert changed.is_watertight
    if sections == "single":
        probes = [(4.4, 0.0, 18.34), (-4.4, 0.0, 17.63), (4.6, 0.0, 18.1)]
        assert _contains(changed, probes).tolist() == [False, False, True]
        assert _contains(changed, [(4.4, 0.0, 3.176 - 0.01)]).all()
        assert not _contains(changed, [(4.4, 0.0, 3.176 + 0.01)]).any()
    else:
        assert _contains(changed, [(0.0, 0.0, 3.1), (0.0, 0.0, 17.9)]).all()
