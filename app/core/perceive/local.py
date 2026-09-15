"""Begrenzte Merkmalsuche mit Abschlussnachweis am unveränderten Original (§21)."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Final

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import CANCEL, CORRECT_INPUT, ValidationError
from app.core.geom.mesh import MeshData, face_components
from app.core.perceive import features as detection
from app.core.perceive.matching import match, moved_features
from app.core.perceive.relations import cavity_chains
from app.core.types import Feature, FeatureId, Transform, Vec3, is_a_cavity
from app.core.units import EPS_GEOM, match_tolerance, weld_tolerance
from app.i18n import _

#: Feine Kundennetze werden unverändert erkannt: Schlauchhalter und Figur mit
#: rund 400 000 beziehungsweise 900 000 Dreiecken benötigen kalt 7 bis 13 Sekunden,
#: aus dem Cache unter 50 Millisekunden. Die Schranke bleibt: ein Schiff mit
#: 1,22 Millionen Dreiecken benötigt 157 Sekunden und deutlich mehr Speicher.
#: Die Topologie entscheidet mit: auf 990 000 reduziert bleibt es bei 123 Sekunden.
#: §31 bleibt das Leistungsziel; dieses Budget begrenzt die zugelassenen Netze.
FEATURE_LIMIT_TRIANGLES = 1_000_000

#: Ausführungsbudget für einen lokalen Fit, keine Lockerung einer Formtoleranz.
#: Die Großmodellproben benötigen 471 bis 5120 Dreiecke; 50 000 begrenzt die
#: Fitphase auch bei dichter Oberfläche und lässt für die Abschlussflächen Platz.
LOCAL_FACE_LIMIT: Final = 50_000
#: Ein Originaldurchgang belegt höchstens diese Dreiecke gleichzeitig und
#: prüft danach den Abbruch. Ein 1,4-Millionen-Netz braucht 22 solche Blöcke.
SCAN_BLOCK: Final = 65_536


@dataclass(frozen=True, slots=True)
class LocalDetection:
    """Nur vollständige Merkmale; Indizes beziehen sich immer auf das Original."""

    features: dict[FeatureId, Feature] = field(default_factory=dict)
    selected: tuple[FeatureId, ...] = ()
    examined_faces: tuple[int, ...] = ()
    reason: str | None = None
    seed_choices: tuple[int, ...] = ()
    unfinished: tuple[Feature, ...] = ()
    open_curvature: bool = False

    @property
    def complete(self) -> bool:
        """Die veröffentlichte Auswahl ist vollständig geprüft, nicht das ganze Netz."""
        return self.reason is None and bool(self.features)


def local_error(reason: str) -> ValidationError:
    """Jeder nicht abgeschlossene Auftrag nennt einen ausführbaren Rückweg."""
    messages = {
        "boundary": _(
            "Das Merkmal setzt sich über den Suchbereich hinaus fort. "
            "Vergrößern Sie den Suchradius oder wählen Sie eine andere Stelle."
        ),
        "budget": _(
            "Dieser Bereich enthält zu viele Dreiecke für die lokale Suche. "
            "Wählen Sie einen kleineren Bereich oder verringern Sie zuerst die Dreiecke."
        ),
        "seed": _("Die gewählte Stelle liegt nicht mehr auf dieser Fläche. Wählen Sie sie erneut."),
        "ambiguous_seed": _(
            "An dieser Stelle liegen mehrere Flächen. Wählen Sie die gemeinte Fläche."
        ),
        "no_feature": _(
            "Hier wurde kein vollständig bestimmtes Merkmal gefunden. "
            "Wählen Sie eine andere Stelle oder vergrößern Sie den Suchradius."
        ),
        "topology": _(
            "Die Begrenzung dieses Merkmals ist nicht eindeutig. "
            "Reparieren Sie das Netz oder wählen Sie eine andere Stelle."
        ),
    }
    return ValidationError(detail=messages[reason], suggestions=[CORRECT_INPUT, CANCEL])


def _check(callback: Callable[[], None] | None) -> None:
    """Abbruch ohne einen zweiten Zustand oder einen globalen Arbeiter."""
    if callback is not None:
        callback()


def _check_patch_size(count: int) -> None:
    """Auch entfernte Rollenbelege dürfen das lokale Fitbudget nicht umgehen."""
    if count > LOCAL_FACE_LIMIT:
        raise local_error("budget")


def _region(
    mesh: MeshData, point: np.ndarray, radius: float, check: Callable[[], None] | None
) -> np.ndarray | None:
    """Konservative Dreieckshüllen: ein langer Rand darf nicht am Schwerpunkt fehlen."""
    selected: list[np.ndarray] = []
    count = 0
    vertices, faces = np.asarray(mesh.raw.vertices), np.asarray(mesh.raw.faces)
    for start in range(0, len(faces), SCAN_BLOCK):
        _check(check)
        triangles = vertices[faces[start : start + SCAN_BLOCK]]
        keep = (triangles.min(axis=1) <= point + radius).all(axis=1)
        keep &= (triangles.max(axis=1) >= point - radius).all(axis=1)
        indices = np.flatnonzero(keep) + start
        count += len(indices)
        if count > LOCAL_FACE_LIMIT:
            return None
        selected.append(indices)
    _check(check)
    return np.concatenate(selected) if selected else np.empty(0, dtype=np.int64)


def _part(mesh: MeshData, indices: np.ndarray) -> MeshData:
    """Nur umnummerieren, niemals schneiden, reparieren oder Dreiecke erzeugen."""
    faces = np.asarray(mesh.raw.faces)[indices]
    vertices, inverse = np.unique(faces.ravel(), return_inverse=True)
    return MeshData.of(
        trimesh.Trimesh(
            np.asarray(mesh.raw.vertices)[vertices], inverse.reshape(-1, 3), process=False
        )
    )


def _seeds(
    mesh: MeshData,
    indices: np.ndarray,
    point: np.ndarray,
    normal: np.ndarray,
    hints: Sequence[int],
) -> tuple[int, ...]:
    """Die gespeicherte Dreiecksnummer ist nur ein geometrisch geprüfter Hinweis."""
    triangles = np.asarray(mesh.raw.vertices)[np.asarray(mesh.raw.faces)[indices]]
    closest_point: Any = trimesh.triangles.closest_point
    closest = closest_point(triangles, np.broadcast_to(point, (len(indices), 3)))
    tolerance = max(EPS_GEOM, weld_tolerance(mesh.bounds.diagonal))
    on_surface = np.linalg.norm(closest - point, axis=1) <= tolerance
    aligned = np.asarray(mesh.raw.face_normals)[indices] @ normal >= math.cos(
        math.radians(detection.EPS_ANGLE)
    )
    found = indices[on_surface & aligned]
    preferred = sorted({int(index) for index in hints}.intersection(found))
    if not len(found):
        return ()
    # Zwei Dreiecke derselben Fläche sind beim Treffer auf ihrer Diagonale
    # keine zwei möglichen Flächen. Getrennte Schalen bleiben dagegen getrennt.
    pairs = np.asarray(mesh.raw.face_adjacency)
    pairs = pairs[np.isin(pairs, found).all(axis=1)]
    groups = trimesh.graph.connected_components(pairs, nodes=found, engine="scipy")
    if preferred:
        return tuple(
            sorted(
                min(set(preferred).intersection(group))
                for group in groups
                if not set(preferred).isdisjoint(group)
            )
        )
    return tuple(sorted(int(np.min(group)) for group in groups))


def _numbered(features: Sequence[Feature]) -> dict[FeatureId, Feature]:
    """Gleiche Originalflächen zusammenlegen und unabhängig vom Suchlauf benennen."""
    unique: dict[tuple[str, tuple[int, ...]], Feature] = {}
    for feature in features:
        key = feature.kind, tuple(sorted(feature.face_indices))
        previous = unique.get(key)
        if previous is None or float(feature.params.get("local_search_radius", math.inf)) < float(
            previous.params.get("local_search_radius", math.inf)
        ):
            unique[key] = feature
    ordered = sorted(
        unique.values(), key=lambda entry: (entry.kind, tuple(sorted(entry.face_indices)))
    )
    counts: dict[str, int] = {}
    result = {}
    for feature in ordered:
        stem = "curve" if feature.kind == "curved_face" else feature.kind
        counts[stem] = counts.get(stem, 0) + 1
        identifier = f"{stem}_{counts[stem]}"
        result[identifier] = replace(
            feature, id=identifier, face_indices=tuple(sorted(feature.face_indices))
        )
    return result


def _recognise_region(
    mesh: MeshData,
    indices: np.ndarray,
    seeds: Sequence[int],
    check: Callable[[], None] | None,
    point: np.ndarray,
    radius: float,
) -> LocalDetection:
    """Fits am Ausschnitt, Begrenzung und Hohlraum am vollständigen Original."""
    _check(check)
    local = _part(mesh, indices)
    found = detection.detect(local, check_cancelled=check)
    _check(check)
    body = mesh.raw
    pairs = np.asarray(body.face_adjacency)
    inside = np.zeros(mesh.triangle_count, dtype=bool)
    inside[indices] = True
    crossing = inside[pairs[:, 0]] != inside[pairs[:, 1]]
    cut = pairs[crossing]
    inner_cut = np.where(inside[cut[:, 0]], cut[:, 0], cut[:, 1])
    angles = np.degrees(np.asarray(body.face_adjacency_angles)[crossing])
    continuing = {int(index) for index in inner_cut[angles < detection.CURVATURE_LIMIT]}
    # Ein Fit kann seine äußerste Dreiecksreihe bereits verworfen haben.
    # Deshalb gilt der unvollständige Rand für die ganze glatt verbundene
    # Oberfläche, nicht nur für die zufällig veröffentlichten Randdreiecke.
    smooth = inside[pairs].all(axis=1) & (
        np.degrees(np.asarray(body.face_adjacency_angles)) < detection.CURVATURE_LIMIT
    )
    for component in trimesh.graph.connected_components(
        pairs[smooth], nodes=indices, engine="scipy"
    ):
        _check(check)
        if not continuing.isdisjoint(component):
            continuing.update(int(index) for index in component)
    mapped = {
        name: replace(
            feature, face_indices=tuple(int(index) for index in indices[list(feature.face_indices)])
        )
        for name, feature in found.items()
        if feature.face_indices and feature.kind not in {"edge_loop", "void"}
    }
    complete = {
        name: feature
        for name, feature in mapped.items()
        if continuing.isdisjoint(feature.face_indices)
        and _inside_radius(body, feature, point, radius)
    }
    # Eine Randschleife aus dem Ausschnitt ist kein Defekt des Originalnetzes.
    # Einschlüsse werden ausschließlich am ganzen Netz eingeordnet.
    voids = detection.detect_voids(mesh)
    void_faces = {index for feature in voids for index in feature.face_indices}
    complete = {
        name: feature
        for name, feature in complete.items()
        if void_faces.isdisjoint(feature.face_indices)
    }
    for feature in voids:
        if all(inside[index] for index in feature.face_indices) and _inside_radius(
            body, feature, point, radius
        ):
            complete[feature.id] = feature
    _check(check)

    # Originalkanten mit nur einem oder mehr als zwei Besitzern können keinen
    # vollständigen Boden belegen. Die Prüfung gilt auch für dessen Innenrand,
    # nicht nur für seine direkte Naht an der Bohrungswand.
    edge_uses = np.bincount(np.asarray(body.edges_unique_inverse))
    sound_faces = np.all(
        edge_uses[np.asarray(body.edges_unique_inverse).reshape(-1, 3)] == 2, axis=1
    )
    _check(check)

    # Auch kleine Böden unterhalb der benennbaren Flächengröße können einen
    # Hohlraum abschließen. Eine Mündung braucht ihren ganzen Originalrand,
    # aber nicht die komplette Deckfläche bis zum Ende eines großen Körpers.
    # Diese Kontextflächen werden dadurch nicht als Merkmal veröffentlicht.
    flat: set[int] = set()
    for facet in local.raw.facets:
        _check(check)
        global_faces = indices[np.asarray(facet)]
        if sound_faces[global_faces].all():
            flat.update(int(index) for index in global_faces)
    owners = {index: name for name, feature in complete.items() for index in feature.face_indices}
    refused = set()
    for name, feature in complete.items():
        _check(check)
        if not is_a_cavity(feature) or feature.kind == "void":
            continue
        if not sound_faces[list(feature.face_indices)].all():
            refused.add(name)
            continue
        members = np.zeros(mesh.triangle_count, dtype=bool)
        members[list(feature.face_indices)] = True
        boundary = pairs[members[pairs[:, 0]] != members[pairs[:, 1]]]
        neighbours = np.where(members[boundary[:, 0]], boundary[:, 1], boundary[:, 0])
        # Ohne die Mündungs-/Bodendreiecke fehlt der Abschlussnachweis auch
        # dann, wenn der Zylindermantel selbst vollständig ist.
        if not inside[neighbours].all():
            refused.add(name)
            continue
        if any(int(index) not in flat and int(index) not in owners for index in neighbours):
            refused.add(name)
            continue
        # Eine unvollständige Aufweitung darf nicht als Nachbar wegfallen und
        # dadurch ihre Bohrung zu einem alleinstehenden Hohlraum machen.
        for other_name, other in mapped.items():
            if (
                other_name not in complete
                and is_a_cavity(other)
                and not set(neighbours).isdisjoint(other.face_indices)
            ):
                refused.add(name)
                break
    # Zusammenhängende Höhlungen werden gemeinsam freigegeben. Sonst könnte
    # eine vollständige Senkung über einer abgelehnten Teilbohrung übrig bleiben.
    # Eine Ringschulter hat keine direkte Wandnaht; ihre Verbindung kommt aus
    # derselben Topologieauskunft wie Baum und Merkmalbearbeitung.
    chains = cavity_chains(found, local)
    while True:
        newly_refused = set()
        for chain in chains:
            names = {feature.id for feature in chain}
            if names - complete.keys() or names.intersection(refused):
                newly_refused.update(names.intersection(complete) - refused)
        bad_faces = {index for name in refused for index in complete[name].face_indices}
        for name, feature in complete.items():
            if name in refused or not is_a_cavity(feature):
                continue
            neighbours = pairs[np.isin(pairs, feature.face_indices).any(axis=1)].ravel()
            if not bad_faces.isdisjoint(neighbours):
                newly_refused.add(name)
        if not newly_refused:
            break
        refused.update(newly_refused)
    complete = {name: feature for name, feature in complete.items() if name not in refused}
    _check(check)
    roles = detection.face_roles(
        mesh,
        [feature for feature in complete.values() if feature.kind == "face"],
        check_cancelled=check,
        check_patch_size=_check_patch_size,
    )
    bounds = detection._ThroughBounds(body)
    verified: list[Feature] = []
    for feature in complete.values():
        _check(check)
        if feature.id in roles:
            feature = replace(feature, params={**feature.params, "inner": roles[feature.id]})
        if feature.kind == "hole":
            fit = detection.fit_cylinder(body, list(feature.face_indices))
            if fit is None or not fit.good:
                continue
            feature = replace(
                feature,
                params={
                    **feature.params,
                    "through": detection._is_through(
                        mesh, fit, [], feature.face_indices, bounds=bounds
                    ),
                },
            )
        centre = detection.centre_of(feature)
        if centre is not None:
            shift = float(np.linalg.norm(centre - point))
            feature = replace(
                feature,
                params={
                    **feature.params,
                    "local_search_radius": radius + (shift if shift > EPS_GEOM else 0.0),
                },
            )
        verified.append(feature)
    _check(check)
    numbered = _numbered(verified)
    unfinished = tuple(feature for name, feature in mapped.items() if name not in complete)
    curved_pairs = pairs[
        smooth & (np.degrees(np.asarray(body.face_adjacency_angles)) > detection.EPS_ANGLE)
    ]
    open_curvature = not continuing.isdisjoint(curved_pairs.ravel())
    selected = tuple(
        name
        for name, feature in numbered.items()
        if not set(seeds).isdisjoint(feature.face_indices)
    )
    if not numbered:
        return LocalDetection(
            examined_faces=tuple(int(index) for index in indices),
            reason="boundary" if len(cut) else "no_feature",
            unfinished=unfinished,
            open_curvature=open_curvature,
        )
    return LocalDetection(
        numbered,
        selected,
        tuple(int(index) for index in indices),
        unfinished=unfinished,
        open_curvature=open_curvature,
    )


def _inside_radius(body: Any, feature: Feature, point: np.ndarray, radius: float) -> bool:
    """Alle belegten Flächenpunkte liegen im freigegebenen Suchumfang."""
    vertices = np.asarray(body.vertices)[
        np.unique(np.asarray(body.faces)[list(feature.face_indices)])
    ]
    return bool(np.all(np.linalg.norm(vertices - point, axis=1) <= radius + EPS_GEOM))


def transformed_searches(
    features: Mapping[FeatureId, Feature], transform: Transform
) -> dict[FeatureId, Feature]:
    """Belegte Suchkugeln konservativ mitnehmen, bekannte Formmaße nur exakt ändern."""
    matrix = np.asarray(transform, dtype=float)[:3, :3]
    factors = np.linalg.svd(matrix, compute_uv=False)
    uniform = bool(np.allclose(factors, factors[0], rtol=0.0, atol=EPS_GEOM))
    result = moved_features(dict(features), transform)
    for name, feature in result.items():
        params = dict(feature.params)
        if "local_search_radius" in params:
            params["local_search_radius"] *= float(factors[0])
        if uniform:
            for key in (
                "diameter",
                "depth",
                "length",
                "radius",
                "tube_diameter",
                "ring_diameter",
                "pitch",
                "width",
                "height",
            ):
                if key in params:
                    params[key] *= float(factors[0])
            if "area" in params:
                params["area"] *= float(factors[0]) ** 2
            if "volume" in params:
                params["volume"] *= float(factors[0]) ** 3
        elif feature.kind in {"hole", "pin"}:
            # Verschiedene Achsfaktoren können einen Kreis erhalten, z. B.
            # beim Verlängern in Z. Eine Ellipse erhält kein Kreis-Sollmaß.
            axis = np.asarray(features[name].params["axis"], dtype=float)
            _u, _s, vectors = np.linalg.svd(axis.reshape(1, 3))
            radial = matrix @ vectors[1:].T
            radial_factors = np.linalg.svd(radial, compute_uv=False)
            along = matrix @ axis
            if (
                np.allclose(radial_factors, radial_factors[0], rtol=0.0, atol=EPS_GEOM)
                and (np.abs(along @ radial) <= EPS_GEOM).all()
            ):
                params["diameter"] *= float(radial_factors[0])
                if "depth" in params:
                    params["depth"] *= float(np.linalg.norm(along))
        if feature.kind == "face":
            normal = np.asarray(features[name].params["normal"], dtype=float)
            transformed = np.linalg.solve(matrix.T, normal)
            norm = float(np.linalg.norm(transformed))
            params["normal"] = tuple(float(value) for value in transformed / norm)
            if not uniform and "area" in params:
                params["area"] *= abs(float(np.linalg.det(matrix))) * norm
        result[name] = replace(feature, params=params)
    return result


def rigid_transform(transform: Transform) -> bool:
    """Nur eine starre Bewegung erlaubt ungeprüftes Mitnehmen unveränderter Maße."""
    matrix = np.asarray(transform, dtype=float)[:3, :3]
    return bool(np.allclose(matrix.T @ matrix, np.eye(3), rtol=0.0, atol=EPS_GEOM))


def _query_is_complete(
    mesh: MeshData, expected: Feature, found: Mapping[FeatureId, Feature]
) -> bool:
    """Ein vollständiger Treffer am erwarteten Ort macht fremde Suchränder irrelevant."""
    matched = match({expected.id: expected}, dict(found), mesh.bounds.centre, mesh.bounds.diagonal)
    identifier = matched.mapping.get(expected.id)
    if identifier is None:
        return False
    candidate = found[identifier]
    centre, other = detection.centre_of(expected), detection.centre_of(candidate)
    if centre is None or other is None:
        return False
    offset = other - centre
    tolerance = match_tolerance(mesh.bounds.diagonal)
    if expected.kind in {"hole", "pin", "slot"}:
        axis = detection.axis_of(expected)
        if axis is None:
            return False
        along = float(offset @ axis)
        if abs(along) > float(candidate.params.get("depth") or 0.0) / 2.0 + tolerance:
            return False
        offset -= along * axis
    return bool(np.linalg.norm(offset) <= tolerance)


def detect_local(
    mesh: MeshData,
    point: Vec3,
    *,
    normal: Vec3,
    radius: float,
    seed_faces: Sequence[int] = (),
    check_cancelled: Callable[[], None] | None = None,
) -> LocalDetection:
    """Am Original auswählen; bei Suchrand, Budget oder Mehrdeutigkeit nichts erfinden."""
    _check(check_cancelled)
    place, direction = np.asarray(point, dtype=float), np.asarray(normal, dtype=float)
    if (
        place.shape != (3,)
        or direction.shape != (3,)
        or not np.isfinite(place).all()
        or not np.isfinite(direction).all()
        or np.linalg.norm(direction) <= EPS_GEOM
        or not math.isfinite(radius)
        or radius <= EPS_GEOM
    ):
        raise local_error("seed")
    direction /= np.linalg.norm(direction)
    indices = _region(mesh, place, radius, check_cancelled)
    if indices is None:
        return LocalDetection(reason="budget")
    if not len(indices):
        return LocalDetection(reason="seed")
    _check(check_cancelled)
    stitched = detection._one_body(mesh)
    _check(check_cancelled)
    seeds = _seeds(stitched, indices, place, direction, seed_faces)
    if not seeds:
        return LocalDetection(reason="seed")
    if len(seeds) > 1:
        return LocalDetection(reason="ambiguous_seed", seed_choices=seeds)
    # Ein naher zweiter Körper wird nicht zur gleichen Auswahl. Die Flutung
    # läuft nur im betrachteten Teil und verändert seine Originalindizes nicht.
    local = _part(stitched, indices)
    connected = next(
        component for component in face_components(local.raw) if seeds[0] in indices[component]
    )
    indices = indices[connected]
    return _recognise_region(stitched, indices, seeds, check_cancelled, place, radius)


def detect_known(
    mesh: MeshData,
    features: Mapping[FeatureId, Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Bekannte Merkmale nach einer Änderung lokal messen, dann wie üblich zuordnen."""
    _check(check_cancelled)
    stitched = detection._one_body(mesh)
    gathered: list[Feature] = []
    visited: set[tuple[int, ...]] = set()
    for feature in features.values():
        _check(check_cancelled)
        if feature.provenance == "generated" and not feature.recognised:
            continue
        centre = detection.centre_of(feature)
        if centre is None:
            continue
        # Der bekannte Merkmalsumfang bestimmt die Umgebung. Eine Suchgrenze
        # verändert keine Maßtoleranz; fehlender Abschluss bleibt ein Fehler.
        extent = max(
            float(feature.params.get(key) or 0.0)
            for key in ("diameter", "depth", "length", "tube_diameter", "ring_diameter")
        )
        radius = max(extent, float(feature.params.get("local_search_radius") or 0.0))
        if radius <= EPS_GEOM:
            if feature.provenance == "generated" and not feature.recognised:
                continue
            raise local_error("boundary")
        indices = _region(stitched, centre, radius, check_cancelled)
        if indices is None:
            raise local_error("budget")
        key = tuple(int(index) for index in indices)
        if key in visited:
            continue
        visited.add(key)
        result = (
            _recognise_region(stitched, indices, (), check_cancelled, centre, radius)
            if len(indices)
            else LocalDetection(reason="no_feature")
        )
        # Ein ganz verschlossenes Loch darf verschwinden. Große ebene
        # Kontextflächen allein belegen keinen abgeschnittenen Lochrest.
        # Ein gekrümmter Suchrand oder eine unvollständige Höhlung dagegen
        # verhindert eine Aussage über das Verschwinden des Vorgängers.
        blocked = result.open_curvature or any(
            candidate.kind != "face" for candidate in result.unfinished
        )
        if feature.kind == "face":
            normal = np.asarray(feature.params["normal"], dtype=float)
            blocked |= any(
                candidate.kind == "face"
                and np.dot(normal, np.asarray(candidate.params["normal"]))
                >= math.cos(math.radians(detection.EPS_ANGLE))
                and abs(float((np.asarray(candidate.params["centre"]) - centre) @ normal))
                <= EPS_GEOM
                for candidate in result.unfinished
            )
        if blocked and not _query_is_complete(stitched, feature, result.features):
            raise local_error("boundary")
        gathered.extend(result.features.values())
    return _numbered(gathered)
