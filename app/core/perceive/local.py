"""Begrenzte Merkmalsuche mit Abschlussnachweis am unveränderten Original (§21)."""

from __future__ import annotations

import dataclasses
import hashlib
import math
import threading
from collections import OrderedDict
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Final

import numpy as np

from app.core import units
from app.core.deferred import trimesh
from app.core.errors import CANCEL, CORRECT_INPUT, ValidationError
from app.core.geom.mesh import MeshData, refined_units, remember_refined_units
from app.core.perceive import features as detection
from app.core.perceive import recognition_time
from app.core.perceive.helix import _facet_of_face
from app.core.perceive.matching import DIAMETER_TOLERANCE, match, transformed_features
from app.core.perceive.relations import cavity_chains
from app.core.perceive.surfaces import clipped_patches, reindexed_patches
from app.core.types import Feature, FeatureId, Transform, Vec3, is_a_cavity
from app.core.units import EPS_GEOM, match_tolerance, weld_tolerance
from app.i18n import _

#: Automatische Vollerkennung; darüber bleibt die lokale Suche verfügbar.
FEATURE_LIMIT_TRIANGLES = 1_500_000
#: Vollerkennung größerer Importe nur nach ausdrücklicher gespeicherter Wahl.
CONFIRMED_FEATURE_LIMIT_TRIANGLES: Final = 5_000_000
#: Spitzenbedarf des ganzen Imports je Dreieck, Einlesen eingeschlossen:
#: 1 600 Byte am Gartenschlauchhalter, 1 660 am Drachen, 1 770 am Schiff.
RECOGNITION_BYTES_PER_TRIANGLE: Final = 1_800


def recognition_minutes(
    triangles: int, *, check_cancelled: Callable[[], None] | None = None
) -> tuple[int, int]:
    """Grobe Zeitspanne auf diesem Rechner, keine Zusage.

    Die Referenz wird mit einer kurzen Rechenprobe dieses Rechners skaliert
    (:mod:`app.core.perceive.recognition_time`); die Topologie bestimmt die
    wirkliche Dauer mit, deshalb die weite Spanne. Die Warnung nennt
    ausdrücklich mögliche längere Laufzeiten.
    """
    return recognition_time.estimate_minutes(triangles, check_cancelled=check_cancelled)


#: Netze, deren Vollerkennung in diesem Prozess am Arbeitsspeicher scheiterte
#: (Netzabdruck aus ``features._mesh_key``). Kein Dokumentzustand: Er
#: verhindert nur, dass dasselbe Netz bei jeder Auswertung Minuten bis zum
#: selben Fehler rechnet; das Ergebnis ist dasselbe wie beim ersten Rückfall.
_OUT_OF_MEMORY: set[bytes] = set()
#: Mehr Netze merkt sich der Prozess nicht; darüber beginnt er von vorn.
OUT_OF_MEMORY_LIMIT: Final = 64


def remember_out_of_memory(mesh: MeshData) -> None:
    """Hält fest, dass die Vollerkennung dieses Netzes am Speicher scheiterte."""
    if len(_OUT_OF_MEMORY) >= OUT_OF_MEMORY_LIMIT:
        _OUT_OF_MEMORY.clear()
    _OUT_OF_MEMORY.add(detection._mesh_key(mesh))


def ran_out_of_memory(mesh: MeshData) -> bool:
    """Ob die Vollerkennung dieses Netzes in diesem Prozess schon scheiterte."""
    return bool(_OUT_OF_MEMORY) and detection._mesh_key(mesh) in _OUT_OF_MEMORY


def forget_out_of_memory() -> None:
    """Vergisst jeden gemerkten Speicherfehler — nach einem ausdrücklichen neuen Versuch.

    *Alle Merkmale erkennen* und ein anderes Projekt sind eine neue
    Entscheidung: Wer nach dem Fehler Programme schließt und es erneut
    versucht, bekam sonst ohne einen Versuch denselben Satz (Review N2).
    """
    _OUT_OF_MEMORY.clear()


def recognition_gigabytes(triangles: int) -> int:
    """Arbeitsspeicher der Vollerkennung in ganzen GB, aufgerundet.

    Genannt wird der Bedarf des ganzen Vorgangs: Ein Rechner, der ihn nicht
    hat, lagert aus oder bricht die Erkennung mit einem Speicherfehler ab.
    """
    return max(1, -(-triangles * RECOGNITION_BYTES_PER_TRIANGLE // 1_000_000_000))


#: Ausführungsbudget für einen lokalen Fit, keine Lockerung einer Formtoleranz.
#: Die Großmodellproben benötigen 471 bis 5120 Dreiecke; 50 000 begrenzt die
#: Fitphase auch bei dichter Oberfläche und lässt für die Abschlussflächen Platz.
LOCAL_FACE_LIMIT: Final = 50_000
#: Ab dieser Größe prüft der Mantelnachweis an der Stelle zuerst Teile des
#: Flecks (:func:`features.planar_facet`): Trägt schon ein Teil dieser Größe
#: keine Rundform, trägt das Ganze keine. Darunter wird gleich das Ganze
#: geprüft — die Deckfläche eines Zylinders mit fein aufgelöster Verrundung
#: hängt über sie und den Mantel an 147 000 Dreiecken, die Sohle des Drachen an
#: seiner ganzen Haut.
MANTLE_PROOF_LIMIT: Final = 250_000
#: So viele Nachmessungen merkt sich der Prozess (:func:`detect_known`).
KNOWN_MEMORY_LIMIT: Final = 32
#: Wie weit ein Rundungsstück über koplanare Dreiecke verfolgt wird: Ein Stück
#: aus einem Streifen von Dreiecken braucht je Dreieck eine Runde.
PIECE_ROUNDS: Final = 8
#: Wann ein Knick „parallel zur Randkante“ läuft: Bei einer Rundung liegen alle
#: Knicke längs derselben Achse; die Ecke eines Stumpfs steht 45° und mehr quer.
ALONG_THE_RIM_DEGREES: Final = 10.0
#: Wie weit sich eine hohle Rundung hinter der Flanke umwenden muss, damit sie
#: ein Langlochende ist und keine Verrundung: Ein Halbzylinder wendet die
#: Normale bis zur Gegenflanke, 180°, eine Verrundung an einer rechtwinkligen
#: Kante um 90°. Ein Ende aus zwei Stücken je Halbkreis steht schon bei 135°,
#: seine Gegenflanke bei 180° — die Grenze liegt dazwischen.
SLOT_END_TURN_DEGREES: Final = 150.0
#: So viele Rundungsstücke verfolgt der Gang höchstens.
ROUND_STEPS: Final = 256
#: Ein Stück, das mehr als doppelt so breit ist wie das erste der Rundung, ist
#: keine Rundung mehr, sondern die nächste Fläche: Dort endet der Gang.
STRIP_GROWTH: Final = 2.0
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
    errors = {
        "boundary": ValidationError(
            constraint="local_boundary",
            detail=_(
                "Das Merkmal setzt sich über den Suchbereich hinaus fort. "
                "Vergrößern Sie den Suchradius oder wählen Sie eine andere Stelle."
            ),
            suggestions=[CORRECT_INPUT, CANCEL],
        ),
        "budget": ValidationError(
            constraint="local_budget",
            detail=_(
                "Dieser Bereich enthält zu viele Dreiecke für die lokale Suche. "
                "Wählen Sie einen kleineren Bereich oder verringern Sie zuerst die Dreiecke."
            ),
            suggestions=[CORRECT_INPUT, CANCEL],
        ),
        "seed": ValidationError(
            constraint="local_seed",
            detail=_(
                "Die gewählte Stelle liegt nicht mehr auf dieser Fläche. Wählen Sie sie erneut."
            ),
            suggestions=[CORRECT_INPUT, CANCEL],
        ),
        "ambiguous_seed": ValidationError(
            constraint="local_ambiguous_seed",
            detail=_("An dieser Stelle liegen mehrere Flächen. Wählen Sie die gemeinte Fläche."),
            suggestions=[CORRECT_INPUT, CANCEL],
        ),
        "no_feature": ValidationError(
            constraint="local_no_feature",
            detail=_(
                "Hier wurde kein vollständig bestimmtes Merkmal gefunden. "
                "Wählen Sie eine andere Stelle oder vergrößern Sie den Suchradius."
            ),
            suggestions=[CORRECT_INPUT, CANCEL],
        ),
        "topology": ValidationError(
            constraint="local_topology",
            detail=_(
                "Die Begrenzung dieses Merkmals ist nicht eindeutig. "
                "Reparieren Sie das Netz oder wählen Sie eine andere Stelle."
            ),
            suggestions=[CORRECT_INPUT, CANCEL],
        ),
    }
    return errors[reason]


def _check(callback: Callable[[], None] | None) -> None:
    """Abbruch ohne einen zweiten Zustand oder einen globalen Arbeiter."""
    if callback is not None:
        callback()


def _region(
    mesh: MeshData,
    point: np.ndarray,
    radius: float,
    check: Callable[[], None] | None,
    *,
    bounded: bool = True,
) -> np.ndarray | None:
    """Konservative Dreieckshüllen: ein langer Rand darf nicht am Schwerpunkt fehlen.

    ``None`` heißt: mehr als :data:`LOCAL_FACE_LIMIT` Dreiecke. Mit
    ``bounded=False`` kommt der ganze Würfel zurück — für den Treffer am Punkt
    und für den Teil, der mit ihm zusammenhängt (:func:`detect_local`).
    """
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
        if bounded and count > LOCAL_FACE_LIMIT:
            return None
        selected.append(indices)
    _check(check)
    return np.concatenate(selected) if selected else np.empty(0, dtype=np.int64)


def _connected_to(mesh: MeshData, indices: np.ndarray, seed: int) -> np.ndarray:
    """Der Teil des Würfels, der über gemeinsame Kanten am Treffer hängt.

    Am ganzen, bereits verschweißten Netz gefragt, ohne ein Teilnetz zu bauen:
    Ein Würfel über der Budgetgrenze kann Hunderttausende Dreiecke tragen.
    """
    inside = np.zeros(mesh.triangle_count, dtype=bool)
    inside[indices] = True
    pairs = np.asarray(mesh.raw.face_adjacency)
    within = pairs[inside[pairs[:, 0]] & inside[pairs[:, 1]]]
    for component in trimesh.graph.connected_components(
        within, nodes=indices, engine="scipy", min_len=1
    ):
        if seed in component:
            return np.sort(np.asarray(component, dtype=np.int64))
    return np.asarray([seed], dtype=np.int64)


def _part(mesh: MeshData, indices: np.ndarray) -> MeshData:
    """Nur umnummerieren, niemals schneiden, reparieren oder Dreiecke erzeugen.

    **Auch nicht verschweißen.** Der Ausschnitt stammt aus dem schon
    verschweißten Körper, aber sein Schnittrand ist offen, und ``detect``
    hielt ihn deshalb für ungeschweißt: ``_one_body`` legte Ecken innerhalb
    der Toleranz *seiner* Diagonale zusammen, die am ganzen Körper getrennt
    sind. Am Schaber verlor eine Deckfläche so sechs ihrer 239 Dreiecke, und
    die Stelle fand sie bei 5 mm nicht (25.09.2026).
    """
    faces = np.asarray(mesh.raw.faces)[indices]
    vertices, inverse = np.unique(faces.ravel(), return_inverse=True)
    part = MeshData.of(
        trimesh.Trimesh(
            np.asarray(mesh.raw.vertices)[vertices], inverse.reshape(-1, 3), process=False
        )
    )
    # Der Ausschnitt zählt seine Dreiecke wie der Körper, aus dem er stammt:
    # nach *Kanten verfeinern* je Ursprung (``geom.mesh.refined_units``, R1).
    units = refined_units(mesh.raw)
    if units is not None:
        remember_refined_units(part.raw, units[np.asarray(indices, dtype=np.intp)])
    detection.as_its_own_body(part)
    return part


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
    facing = (np.asarray(mesh.raw.face_normals)[indices] * normal).sum(axis=1)
    aligned = facing >= units.exact_cos_degrees(detection.EPS_ANGLE)
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


@dataclass(frozen=True, slots=True)
class _Seams:
    """Was der Langlochgang je Dreieck und Naht liest — einmal je Fläche geholt.

    Jeder Zugriff auf ein Feld am Körper geht durch den Merker von trimesh,
    und der prüft dabei die Daten: An einer Deckfläche mit 8 192 Randkanten
    kosteten die Zugriffe allein 0,7 s. ``angles`` sind die Knicke aller
    Nachbarpaare in Grad.
    """

    neighbours: np.ndarray
    rows: np.ndarray
    normals: np.ndarray
    centres: np.ndarray
    vertices: np.ndarray
    faces: np.ndarray
    edges: np.ndarray
    angles: np.ndarray

    @classmethod
    def of(cls, body: Any, angles: np.ndarray) -> _Seams:
        """Die Felder eines Körpers, einmal gelesen."""
        neighbours, rows = detection._neighbour_index(body)
        return cls(
            neighbours,
            rows,
            np.asarray(body.face_normals),
            np.asarray(body.triangles_center),
            np.asarray(body.vertices),
            np.asarray(body.faces),
            np.asarray(body.face_adjacency_edges),
            angles,
        )


def _may_turn_round(
    seams: _Seams,
    starts: np.ndarray,
    own: np.ndarray,
    normal: np.ndarray,
    check: Callable[[], None] | None,
) -> bool:
    """Ob die Rundung hinter den Randkanten überhaupt bis zur Gegenflanke wendet.

    Die notwendige Bedingung für jeden Gang von :func:`_turns_round_like_a_slot_end`,
    einmal für alle Randkanten gefragt (Review R2, vierte Runde): Ein Gang geht
    nur über Nähte unter :data:`features.CURVATURE_LIMIT` und nie in die Fläche;
    trägt kein so erreichbares Dreieck eine Normale gegen die Fläche, kann keiner
    „ja“ sagen. An einer Hohlkehle mit 8 192 Stücken ging bis dahin jede
    Randkante bis zur Wand — 3,7 s für eine Antwort, die hier in einem Zug steht.
    Wächst die Rundung über :data:`MANTLE_PROOF_LIMIT`, bleibt die Frage bei den
    Gängen.
    """
    opposite = -units.exact_cos_degrees(180.0 - SLOT_END_TURN_DEGREES)
    seen = np.zeros(len(seams.normals), dtype=bool)
    seen[own] = True
    frontier = np.unique(starts)
    seen[frontier] = True
    count = len(frontier)
    while len(frontier):
        _check(check)
        if float((seams.normals[frontier] * normal).sum(axis=1).min()) <= opposite:
            return True
        if count > MANTLE_PROOF_LIMIT:
            return True
        near, via = seams.neighbours[frontier].ravel(), seams.rows[frontier].ravel()
        present = near >= 0
        near, via = near[present], via[present]
        passable = ~seen[near] & (seams.angles[via] < detection.CURVATURE_LIMIT)
        frontier = np.unique(near[passable])
        seen[frontier] = True
        count += len(frontier)
    return False


def _turns_round_like_a_slot_end(
    seams: _Seams,
    start: int,
    normal: np.ndarray,
    along: np.ndarray,
    face: Collection[int],
) -> bool:
    """Ob die Rundung hinter einer Flankenkante ein Langlochende ist (Review N5).

    Hohl muss sie sein — sie wölbt sich zur Seite der Flächennormalen, um die
    Luft des Lochs; das prüft :func:`_recognise_region` für alle Randkanten
    zugleich, bevor der Gang beginnt —, und sie muss die Normale bis zur
    Gegenflanke umwenden.
    Gegangen wird Stück für Stück quer zur Randkante: über jeden Knick, der
    parallel zu ihr läuft, bis ein Stück breiter wird als eine Rundung
    (``STRIP_GROWTH``) oder keines mehr folgt. Eine Verrundung an einer
    Außenkante ist nicht hohl, eine in einer Innenecke endet nach 90° an ihrer
    Wand; beides schluckt die Vollerkennung in kein Langloch. Ob eine solche
    Fläche überhaupt eine ist, entscheidet nicht dieser Gang, sondern die
    Ebenenregel der Vollerkennung (:func:`features.planar_facet`). ``face``
    sind die Dreiecke der Fläche selbst. Gemerkt wird nur, was der Gang
    berührt — kein Feld in Netzgröße je Randkante (Review R2: 19,6 s an einer
    Deckfläche mit 8 192 Randkanten).
    """
    neighbours, rows = seams.neighbours, seams.rows
    face_normals, vertices, faces = seams.normals, seams.vertices, seams.faces
    edges, angles = seams.edges, seams.angles
    parallel = units.exact_cos_degrees(ALONG_THE_RIM_DEGREES)
    opposite = -units.exact_cos_degrees(180.0 - SLOT_END_TURN_DEGREES)
    visited: set[int] = set()

    def piece_of(seed: int) -> np.ndarray:
        # Ein Stück der Rundung ist eine koplanare Gruppe, wenige Runden weit.
        piece, frontier, seen = [seed], [seed], {seed}
        for _round in range(PIECE_ROUNDS):
            reached = []
            for triangle in frontier:
                for other, row in zip(neighbours[triangle], rows[triangle], strict=True):
                    if other < 0 or other in seen or other in visited or other in face:
                        continue
                    if angles[row] <= detection.EPS_ANGLE:
                        seen.add(int(other))
                        reached.append(int(other))
            if not reached:
                break
            piece.extend(reached)
            frontier = reached
        return np.asarray(piece, dtype=np.int64)

    def width_of(piece: np.ndarray, facing: np.ndarray) -> float:
        across = np.cross(facing, along)
        across = across / math.sqrt(float((across * across).sum()))
        heights = (vertices[faces[piece]].reshape(-1, 3) * across).sum(axis=1)
        return float(heights.max() - heights.min())

    current = piece_of(start)
    first_width: float | None = None
    for _step in range(ROUND_STEPS):
        facing = face_normals[current[0]]
        if float((facing * normal).sum()) <= opposite:
            return True
        width = width_of(current, facing)
        if first_width is None:
            first_width = width
        elif width > STRIP_GROWTH * first_width:
            return False
        visited.update(int(index) for index in current)
        following: int | None = None
        for triangle in current:
            for other, row in zip(neighbours[triangle], rows[triangle], strict=True):
                if other < 0 or other in visited or other in face:
                    continue
                if not detection.EPS_ANGLE < angles[row] < detection.CURVATURE_LIMIT:
                    continue
                edge = vertices[edges[row]]
                direction = edge[1] - edge[0]
                length = math.sqrt(float((direction * direction).sum()))
                if length > 0.0 and abs(float((direction * along).sum())) / length >= parallel:
                    following = int(other)
                    break
            if following is not None:
                break
        if following is None:
            return False
        current = piece_of(following)
    return False


def _recognise_region(
    mesh: MeshData,
    indices: np.ndarray,
    seeds: Sequence[int],
    check: Callable[[], None] | None,
    point: np.ndarray,
    radius: float,
    proven: Collection[int] = (),
    recorded: float | None = None,
) -> LocalDetection:
    """Fits am Ausschnitt, Begrenzung und Hohlraum am vollständigen Original.

    ``proven`` ist die ebene Facette am Treffer: Sie ist durch ihre eigenen
    Kanten vollständig begrenzt und gilt deshalb auch dann, wenn sie über den
    Suchradius hinausreicht. ``recorded`` ist der Suchumfang, den die
    gefundenen Merkmale als ``local_search_radius`` weitertragen, wenn er
    größer ist als der gerade durchsuchte (:func:`detect_known`).
    """
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
    at_the_rim = {int(index) for index in inner_cut[angles < detection.CURVATURE_LIMIT]}
    # Ein Fit kann seine äußerste Dreiecksreihe bereits verworfen haben.
    # Deshalb gilt der unvollständige Rand für die ganze glatt verbundene
    # Oberfläche, nicht nur für die zufällig veröffentlichten Randdreiecke —
    # **für eine eingepasste Form bis zum nächsten Krümmungssprung**, an dem
    # auch die Vollerkennung eine Fläche in Stücke trennt
    # (``features.curvature_jumps``, am ganzen Körper). Die Magnettaschen des
    # Schabers gehen über eine gerundete Mündung glatt in die gewölbte
    # Oberseite über: Der Ausschnitt fand jede Tasche genau wie die
    # Vollerkennung, und die Sperre über die Oberseite verwarf sie bei jedem
    # Radius (25.09.2026). Hinter einem Sprung liegt eine andere Fläche; die
    # eigene Fortsetzung eines Fits trägt dieselbe Krümmung. **Eine gerundete
    # Seite ist dagegen ein Rest** — was nach allen Einpassungen übrig bleibt,
    # und wie viel das ist, hängt am Ausschnitt: Am Schaber kamen sonst Stücke
    # von 38 bis 92 Dreiecken einer Seite heraus, die die Vollerkennung als eine
    # mit 8 840 führt. Für sie gilt weiter die ganze glatte Fläche.
    angle_soft = np.degrees(np.asarray(body.face_adjacency_angles)) < detection.CURVATURE_LIMIT
    # **Die Sprünge nur an den Nähten, die den Ausschnitt berühren** — nur dort
    # werden sie gelesen (hier und an den Randnähten der Höhlungen unten).
    # Am ganzen Körper gerechnet kosteten sie nach jedem Versetzen am
    # Gartenschlauchhalter 1,15 s (Durchsicht 0.5.1, bohrung); die Zahlen je
    # Naht sind dieselben (``features.curvature_jumps_at``).
    touching = np.flatnonzero(angle_soft & inside[pairs].any(axis=1))
    soft_seams = np.zeros(len(pairs), dtype=bool)
    soft_seams[touching] = (
        detection.curvature_jumps_at(body, touching, check) <= detection.CURVATURE_JUMP
    )
    smooth = inside[pairs].all(axis=1) & angle_soft

    def spread(seams: np.ndarray) -> set[int]:
        """Die Randdreiecke samt allem, was über ``seams`` mit ihnen zusammenhängt."""
        reached = set(at_the_rim)
        for component in trimesh.graph.connected_components(
            pairs[seams], nodes=indices, engine="scipy"
        ):
            _check(check)
            if not reached.isdisjoint(component):
                reached.update(int(index) for index in component)
        return reached

    continuing = spread(smooth & soft_seams)
    continuing_surface = spread(smooth)
    mapped = {
        name: replace(
            feature,
            face_indices=tuple(int(index) for index in indices[list(feature.face_indices)]),
            surface_patches=reindexed_patches(
                feature.surface_patches, indices, check_cancelled=check
            ),
        )
        for name, feature in found.items()
        if feature.face_indices and feature.kind not in {"edge_loop", "void"}
    }
    # **Eine ebene Fläche ist vollständig, wenn ihre Facette es ist.** Die
    # Regel darüber gilt Fits, die ihre äußerste Reihe verworfen haben können;
    # eine Facette hat keinen Fit, ihre Grenze ist die letzte koplanare Kante.
    # Ohne diese Unterscheidung galt jede Fläche als abgeschnitten, deren Rand
    # weich in eine Rundung übergeht — am Drachen alle vier Fußsohlen, deren
    # Kanten unter 30° knicken (24.09.2026).
    #
    # Gefragt wird an den Facetten des Bereichs samt seinem Randring: Setzt sich
    # eine Facette über den Rand fort, liegt ihr koplanarer Nachbar im Ring. Die
    # Facetten des ganzen Netzes kosteten an 3,26 Millionen Dreiecken 3,2 s je
    # Folgeschritt (Review 24.09.2026).
    ring: np.ndarray | None = None
    ring_facets: Any = None
    ring_labels: np.ndarray | None = None
    proven_faces = {int(index) for index in proven}
    all_angles = np.degrees(np.asarray(body.face_adjacency_angles))

    def cut_facet(feature: Feature) -> bool | None:
        nonlocal ring, ring_facets, ring_labels
        if ring_labels is None:
            ring = np.union1d(indices, cut.ravel())
            ring_facets = [ring[np.asarray(facet)] for facet in _part(mesh, ring).raw.facets]
            ring_labels = np.full(len(ring), -1, dtype=np.int64)
            for label, members in enumerate(ring_facets):
                ring_labels[np.searchsorted(ring, members)] = label
        assert ring is not None
        own = ring_labels[np.searchsorted(ring, np.asarray(feature.face_indices))]
        if (own < 0).any():
            return None
        return not all(inside[ring_facets[label]].all() for label in np.unique(own))

    def continues_tangentially(feature: Feature) -> bool:
        """Ob die Fläche die Flanke eines Langlochs ist: stetig in ein Langlochende.

        Die Flanke eines Langlochs ist eine ganze Facette, geht aber tangential
        in die Bögen über, und die Vollerkennung schluckt sie ins Langloch. Ein
        Zylinder aus n Stücken knickt je Kante um 360°/n, an der tangentialen
        Ebene um die Hälfte davon — und sein nächster Knick läuft **parallel**
        zur Randkante. Eine Fußsohle knickt stärker in ihre Nachbarn, als diese
        in sich knicken; die ebenen Seiten eines Stumpfs knicken an ihren Ecken,
        quer zur Randkante. Beides ist keine Rundung. **Und eine Verrundung ist
        kein Langlochende** (:func:`_turns_round_like_a_slot_end`): Die
        Vollerkennung schluckt eine Flanke nur in ein Langloch, und eine Fläche
        an einer Verrundung blieb sonst „abgeschnitten“, bis sie ganz im
        Suchradius lag (Review N5).
        """
        members = {int(index) for index in feature.face_indices}
        own = np.asarray(sorted(members), dtype=np.int64)
        surface = _Seams.of(body, all_angles)
        neighbours, rows = surface.neighbours, surface.rows
        edges, vertices = surface.edges, surface.vertices
        # Randkanten: ein Nachbar außerhalb der Fläche, über einen weichen Knick.
        around, via = neighbours[own].ravel(), rows[own].ravel()
        outside = around >= 0
        outside[outside] = ~np.isin(around[outside], own)
        rim_rows = via[outside]
        soft = all_angles[rim_rows] < detection.CURVATURE_LIMIT
        rim_rows, rim_starts = rim_rows[soft], around[outside][soft]
        normal = np.asarray(feature.params["normal"], dtype=float)
        # Nur hinter einer hohlen Rundung kann ein Langlochende liegen: Sie
        # wölbt sich zur Seite der Flächennormalen. An der Verrundung einer
        # Außenkante fällt so jede Randkante weg, bevor ein Stück entsteht.
        ends = vertices[edges[rim_rows]]
        offsets = surface.centres[rim_starts] - (ends[:, 0] + ends[:, 1]) / 2.0
        hollow = (offsets * normal).sum(axis=1) > 0.0
        rim_rows, rim_starts = rim_rows[hollow], rim_starts[hollow]
        if not len(rim_rows) or not _may_turn_round(surface, rim_starts, own, normal, check):
            return False
        order = np.argsort(rim_rows, kind="stable")
        along = units.exact_cos_degrees(ALONG_THE_RIM_DEGREES)

        pieces: list[tuple[int, int, set[int], list[int]]] = []
        wanted: list[int] = []
        for row, start in zip(rim_rows[order].tolist(), rim_starts[order].tolist(), strict=True):
            # Ein Stück der Rundung besteht oft aus mehreren koplanaren
            # Dreiecken; der Knick zum nächsten Stück liegt am Partner.
            piece, frontier = {start}, [start]
            for _round in range(PIECE_ROUNDS):
                reached = []
                for triangle in frontier:
                    for other, seam in zip(neighbours[triangle], rows[triangle], strict=True):
                        if (
                            other >= 0
                            and other not in piece
                            and other not in members
                            and all_angles[seam] <= detection.EPS_ANGLE
                        ):
                            piece.add(int(other))
                            reached.append(int(other))
                if not reached:
                    break
                frontier = reached
            seams = [
                int(seam)
                for triangle in piece
                for other, seam in zip(neighbours[triangle], rows[triangle], strict=True)
                if other >= 0
                and other not in piece
                and other not in members
                and detection.EPS_ANGLE < all_angles[seam] < detection.CURVATURE_LIMIT
            ]
            pieces.append((row, start, piece, seams))
            wanted.append(row)
            wanted.extend(seams)
        # Die Richtungen aller beteiligten Kanten in einem Zug, nicht je Knick:
        # An einer Deckfläche mit 8 192 Randkanten waren es sonst 50 000
        # einzelne Rechnungen.
        needed = np.unique(np.asarray(wanted, dtype=np.int64))
        ends = vertices[edges[needed]]
        steps = ends[:, 1] - ends[:, 0]
        lengths = np.sqrt((steps * steps).sum(axis=1))
        units_of = steps / np.where(lengths > 0.0, lengths, 1.0)[:, None]
        direction = dict(zip(needed.tolist(), units_of.tolist(), strict=True))
        for row, start, _piece, seams in pieces:
            rim = direction[row]
            leaving = [
                float(all_angles[seam])
                for seam in seams
                if abs(
                    direction[seam][0] * rim[0]
                    + direction[seam][1] * rim[1]
                    + direction[seam][2] * rim[2]
                )
                >= along
            ]
            if (
                leaving
                and all_angles[row] <= min(leaving)
                and _turns_round_like_a_slot_end(surface, start, normal, np.asarray(rim), members)
            ):
                return True
        return False

    def planar_in_full(feature: Feature) -> bool:
        # **Ob eine Fläche eine ist, sagt die Regel der Vollerkennung am ganzen
        # Körper** (Review R1) — nicht der Ausschnitt, an dem ``detect`` lief.
        return detection.planar_facet(
            body, feature.face_indices, limit=MANTLE_PROOF_LIMIT, check_cancelled=check
        )

    # **Eine gerundete Seite misst sich am ganzen Körper.** Die Vollerkennung
    # nimmt sie ab einem Hundertstel seiner Oberfläche (``CURVED_SIDE_SHARE``),
    # der Ausschnitt ab einem Hundertstel des Ausschnitts — am Schaber kamen so
    # 14 Stücke heraus, die die Vollerkennung nirgends führt (25.09.2026).
    side_floor = max(detection.MIN_FACE_AREA, float(body.area) * detection.CURVED_SIDE_SHARE)
    face_areas = np.asarray(body.area_faces, dtype=float)

    def bounded(feature: Feature) -> bool:
        blocked = continuing_surface if feature.kind == "curved_face" else continuing
        return blocked.isdisjoint(feature.face_indices) and _inside_radius(
            body, feature, point, radius
        )

    def within(feature: Feature) -> bool:
        """Ob das Merkmal diesseits des Suchrands endet — die Randfrage allein."""
        if feature.kind != "face":
            return bounded(feature)
        cut_off = None if continues_tangentially(feature) else cut_facet(feature)
        if cut_off is None:
            return bounded(feature)
        return not cut_off and (
            proven_faces.issuperset(feature.face_indices)
            or _inside_radius(body, feature, point, radius)
        )

    def is_complete(feature: Feature) -> bool:
        if feature.kind == "curved_face":
            large = float(face_areas[list(feature.face_indices)].sum()) >= side_floor
            return large and within(feature)
        if feature.kind != "face":
            return within(feature)
        # Erst der Suchrand, dann die Ebenenregel: Eine abgeschnittene Fläche
        # ist keine, gleich was der Mantelnachweis sagte — an einem fein
        # unterteilten Zylinder gingen sonst 5 von 5,8 s an Flächen, die der
        # Rand danach verwarf (Review S3).
        return within(feature) and planar_in_full(feature)

    complete = {name: feature for name, feature in mapped.items() if is_complete(feature)}
    # Eine Randschleife aus dem Ausschnitt ist kein Defekt des Originalnetzes.
    # Einschlüsse werden ausschließlich am ganzen Netz eingeordnet.
    voids = detection.detect_voids(mesh, check_cancelled=check)
    local_void_patches = reindexed_patches(
        tuple(
            patch
            for feature in found.values()
            if feature.kind == "void"
            for patch in feature.surface_patches
        ),
        indices,
        check_cancelled=check,
    )
    voids = [
        replace(
            feature,
            surface_patches=clipped_patches(
                local_void_patches,
                feature.face_indices,
                check_cancelled=check,
            ),
        )
        for feature in voids
    ]
    # Der lokale Fit belegt bereits diese Originaldreiecke. Der Vollkörper
    # entscheidet nur die Luftzugehörigkeit und übernimmt genau diesen Anteil.
    with_voids = detection.voids_instead_of_phantom_bores(mapped, voids, check_cancelled=check)
    voids = [with_voids[feature.id] for feature in voids]
    void_faces = {index for feature in voids for index in feature.face_indices}
    complete = {
        name: feature
        for name, feature in complete.items()
        if void_faces.isdisjoint(feature.face_indices)
    }
    for feature in voids:
        # Eine Materialinsel trägt eine getrennte Grenzschale derselben Luft.
        # Der angeklickte Originalpunkt bestimmt die Kammer; der Radius muss
        # ihre gesamte Grenze einschließlich aller Inseln umfassen.
        if not set(seeds).isdisjoint(feature.face_indices) and _inside_radius(
            body, feature, point, radius, check
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
        seams = members[pairs[:, 0]] != members[pairs[:, 1]]
        boundary = pairs[seams]
        neighbours = np.where(members[boundary[:, 0]], boundary[:, 1], boundary[:, 0])
        # Ohne die Mündungs-/Bodendreiecke fehlt der Abschlussnachweis auch
        # dann, wenn der Zylindermantel selbst vollständig ist.
        if not inside[neighbours].all():
            refused.add(name)
            continue
        # Wo die Wand glatt weiterläuft, muss der Nachbar belegt sein — eben
        # oder ein vollständiges Merkmal —, sonst setzt sich hinter ihm
        # vielleicht die Wand fort. Hinter einem Knick oder Krümmungssprung
        # beginnt eine andere Fläche: An der gerundeten Mündung einer
        # Magnettasche sind das Dreiecke der Rundung, die kein Merkmal trägt.
        continued = neighbours[soft_seams[seams]]
        if any(int(index) not in flat and int(index) not in owners for index in continued):
            refused.add(name)
            continue
        # Eine unvollständige Aufweitung darf nicht als Nachbar wegfallen und
        # dadurch ihre Bohrung zu einem alleinstehenden Hohlraum machen.
        # **Aufweitung heißt Kettenglied** — Bohrung oder Kegel, die zwei Arten,
        # die ``relations.cavity_chains`` zu einer Kette verbindet. Eine hohle
        # Verrundung oder ein Torus, in den eine Mündung öffnet, ist die Fläche
        # um sie, kein Glied: Am Gartenschlauchhalter mündet eine Senkbohrung
        # in die Hohlkehle, die jeden Suchradius überragt, und die Nachmessung
        # verwarf deshalb die ganze Kette — nach jedem Versetzen die volle
        # Erkennung, in der genauen Vorschau 33 statt 5 s je Zahl (Durchsicht
        # 0.5.1, REST-BOHRUNG-07).
        for other_name, other in mapped.items():
            if (
                other_name not in complete
                and other.kind in ("hole", "cone")
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
        limit=MANTLE_PROOF_LIMIT,
        check_cancelled=check,
    )
    bounds = detection._ThroughBounds(body)
    verified: list[Feature] = []
    for feature in complete.values():
        _check(check)
        if feature.id in roles:
            feature = replace(feature, params={**feature.params, "inner": roles[feature.id]})
        if feature.kind == "hole":
            fit = detection.fit_cylinder(body, list(feature.face_indices), check_cancelled=check)
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
                    "local_search_radius": max(radius, recorded or 0.0)
                    + (shift if shift > EPS_GEOM else 0.0),
                },
            )
        verified.append(feature)
    _check(check)
    numbered = _numbered(verified)
    unfinished = tuple(feature for name, feature in mapped.items() if name not in complete)
    curved_pairs = pairs[
        smooth & (np.degrees(np.asarray(body.face_adjacency_angles)) > detection.EPS_ANGLE)
    ]
    open_curvature = not continuing_surface.isdisjoint(curved_pairs.ravel())
    selected = tuple(
        name
        for name, feature in numbered.items()
        if not set(seeds).isdisjoint(feature.face_indices)
    )
    # **Gefragt ist die angeklickte Stelle.** Ist ihr eigenes Merkmal am
    # Suchrand abgeschnitten, sagt die Antwort das, auch wenn daneben
    # vollständige Merkmale liegen: Am Schaber stand bei 5 mm eine Liste aus
    # zwei Verrundungen da, ohne die angeklickte Deckfläche und ohne Wort zum
    # Suchrand (25.09.2026). Der Rückweg ist der größere Radius.
    cut_at_the_seed = not selected and any(
        not set(seeds).isdisjoint(feature.face_indices) and not within(feature)
        for feature in unfinished
    )
    if not numbered or cut_at_the_seed:
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


def _inside_radius(
    body: Any,
    feature: Feature,
    point: np.ndarray,
    radius: float,
    check: Callable[[], None] | None = None,
) -> bool:
    """Alle belegten Flächenpunkte liegen im freigegebenen Suchumfang."""
    vertices, faces = np.asarray(body.vertices), np.asarray(body.faces)
    limit = radius + EPS_GEOM
    # Ein einziger ferner Originalpunkt widerlegt bereits den vollständigen
    # Einschluss. Große bekannte Außenmäntel brauchen dafür keine Punktwolke.
    if feature.face_indices:
        delta = vertices[faces[feature.face_indices[0], 0]] - point
        if np.any(np.abs(delta) > limit):
            return False
    for start in range(0, len(feature.face_indices), SCAN_BLOCK):
        _check(check)
        indices = feature.face_indices[start : start + SCAN_BLOCK]
        points = vertices[np.unique(faces[list(indices)])]
        delta = points - point
        if np.any(np.abs(delta) > limit) or not np.all(np.linalg.norm(delta, axis=1) <= limit):
            return False
    return True


def features_in_region(
    mesh: MeshData,
    features: Mapping[FeatureId, Feature],
    point: Vec3,
    *,
    radius: float,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[FeatureId, ...]:
    """Vorhandene vollständige Originalflächen auswählen, ohne erneut zu erkennen."""
    place = np.asarray(point, dtype=float)
    chosen = []
    for name, feature in features.items():
        _check(check_cancelled)
        if (
            feature.face_indices
            and feature.recognised
            and _inside_radius(mesh.raw, feature, place, radius, check_cancelled)
        ):
            chosen.append(name)
    _check(check_cancelled)
    return tuple(chosen)


def transformed_searches(
    features: Mapping[FeatureId, Feature],
    transform: Transform,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Suchkugeln und Maßkandidaten aus derselben Auskunft wie die globale Zuordnung."""
    return transformed_features(features, transform, check_cancelled=check_cancelled).candidates


def rigid_transform(transform: Transform) -> bool:
    """Nur eine starre Bewegung erlaubt ungeprüftes Mitnehmen unveränderter Maße."""
    from app.core.geom.transform import is_rigid

    return is_rigid(np.asarray(transform, dtype=float))


def _query_is_complete(
    mesh: MeshData,
    expected: Feature,
    found: Mapping[FeatureId, Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> bool:
    """Ein vollständiger Treffer am erwarteten Ort macht fremde Suchränder irrelevant."""
    matched = match(
        {expected.id: expected},
        dict(found),
        mesh.bounds.centre,
        mesh.bounds.diagonal,
        check_cancelled=check_cancelled,
    )
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
        along = float((offset * axis).sum())
        if abs(along) > float(candidate.params.get("depth") or 0.0) / 2.0 + tolerance:
            return False
        offset -= along * axis
    return math.sqrt(float((offset * offset).sum())) <= tolerance


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
    _check(check_cancelled)
    stitched = detection._one_body(mesh)
    _check(check_cancelled)
    # Der Treffer braucht nur die Dreiecke am Punkt, nicht den ganzen Würfel:
    # Sonst entschied das Budget des Suchbereichs schon darüber, ob überhaupt
    # eine Stelle gewählt ist.
    reach = max(EPS_GEOM, weld_tolerance(mesh.bounds.diagonal))
    near = _region(stitched, place, reach, check_cancelled, bounded=False)
    if near is None or not len(near):
        return LocalDetection(reason="seed")
    seeds = _seeds(stitched, near, place, direction, seed_faces)
    if not seeds:
        return LocalDetection(reason="seed")
    if len(seeds) > 1:
        return LocalDetection(reason="ambiguous_seed", seed_choices=seeds)
    seed = seeds[0]
    indices = _region(stitched, place, radius, check_cancelled, bounded=False)
    assert indices is not None
    _check(check_cancelled)
    # Ein naher zweiter Körper wird nicht zur gleichen Auswahl, und **das
    # Budget gilt dem, was zur Stelle gehört** (RM-235): Der Würfel zählte jede
    # dichte Fläche in seiner Ecke mit, auch eine, die mit der angeklickten
    # nichts zu tun hat; am Drachen reichte schon ein Suchradius von 8 mm über
    # die Grenze. Die Flutung verändert keine Originalindizes.
    indices = _connected_to(stitched, indices, seed)
    # **Die ebene Fläche am Treffer gehört immer dazu**, auch über den
    # Suchradius hinaus: Ihre Facette begrenzt sie selbst. Am Drachen lag
    # zwischen „Suchrand“ und „zu viele Dreiecke“ kein Radius, der eine
    # Fußsohle ganz fasste — die Vollerkennung findet genau diese vier.
    labels = _facet_of_face(stitched.raw)
    plane = np.flatnonzero(labels == labels[seed]) if labels[seed] >= 0 else np.empty(0, np.int64)
    if len(plane) > LOCAL_FACE_LIMIT:
        # Eine Ebene über dem Budget trägt die Suche nicht; dann gilt der
        # begrenzte Bereich wie ohne sie, und ein kleinerer Suchradius hilft.
        plane = np.empty(0, np.int64)
    indices, crowded = _with_its_facet(indices, plane)
    if not len(indices):
        return LocalDetection(reason="budget")
    result = _recognise_region(
        stitched, indices, seeds, check_cancelled, place, radius, proven=plane
    )
    # Fand die Facette allein nichts, lag es am Budget und nicht am Suchrand:
    # Gesucht war der ganze Teil im Suchradius.
    return replace(result, reason="budget") if crowded and result.reason else result


def _with_its_facet(indices: np.ndarray, plane: np.ndarray) -> tuple[np.ndarray, bool]:
    """Der Suchbereich samt der Facette am Treffer — und ob das Budget dafür reichte.

    **Hängt an der Stelle mehr als das Budget, bleibt die Facette allein**,
    und die Stelle ist der Bereich *mit* seiner Facette: Bis zum 25.09.2026
    fiel die Facette nur zurück, wenn der Bereich schon selbst über dem
    Budget lag. Brachte erst die Facette ihn darüber, sagte die Suche „zu
    viele Dreiecke — wählen Sie einen kleineren Bereich“, und ein größerer
    Radius fand die Fläche. ``plane`` passt selbst ins Budget oder ist leer;
    ein leeres Ergebnis heißt dann: nichts, was ins Budget passt.
    """
    joined = np.union1d(indices, plane)
    if len(joined) <= LOCAL_FACE_LIMIT:
        return joined, False
    return plane, True


_KNOWN: OrderedDict[bytes, dict[FeatureId, Feature]] = OrderedDict()
_KNOWN_LOCK = threading.Lock()

#: Wovon eine Suche in :func:`detect_known` abhängt: Dreiecke, Facette, belegter
#: Suchumfang, Suchradius und die Mitte der Kugel als Bytes.
type _SearchKey = tuple[tuple[int, ...], tuple[int, ...], float, float, bytes]


def forget_known() -> None:
    """Vergisst die gemerkten Nachmessungen — für Tests und Messungen."""
    with _KNOWN_LOCK:
        _KNOWN.clear()


def _plain(value: Any) -> Any:
    """Ein Wert als ausgeschriebene Grundform — für einen Abdruck ohne gekürzte Felder."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return tuple(
            (item.name, _plain(getattr(value, item.name))) for item in dataclasses.fields(value)
        )
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), _plain(item)) for key, item in value.items()))
    if isinstance(value, np.ndarray):
        return ("array", value.dtype.str, value.shape, value.tobytes())
    if isinstance(value, (list, tuple)):
        return tuple(_plain(item) for item in value)
    if isinstance(value, (float, np.floating)):
        return float(value).hex()
    if isinstance(value, np.integer):
        return int(value)
    return value


def _known_key(
    mesh: MeshData,
    features: Mapping[FeatureId, Feature],
    required: Collection[FeatureId] | None,
    standing: Collection[FeatureId],
) -> bytes:
    """Wovon eine Nachmessung abhängt: Netz, Merkmale, Anspruch, Budgets."""
    digest = hashlib.blake2b(digest_size=20)
    digest.update(detection._mesh_key(mesh))
    digest.update(
        repr(
            (
                tuple((name, _plain(features[name])) for name in sorted(features)),
                None if required is None else tuple(sorted(required)),
                tuple(sorted(standing)),
                LOCAL_FACE_LIMIT,
                MANTLE_PROOF_LIMIT,
            )
        ).encode("utf-8")
    )
    return digest.digest()


def detect_known(
    mesh: MeshData,
    features: Mapping[FeatureId, Feature],
    *,
    required: Collection[FeatureId] | None = None,
    standing: Collection[FeatureId] = (),
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Bekannte Merkmale nach einer Änderung lokal messen, dann wie üblich zuordnen.

    ``required`` nennt die Merkmale, die ein späterer Schritt oder eine Passung
    noch braucht; ``None`` heißt alle. Nur für sie hält eine Umgebung an, die
    sich nicht nachmessen lässt (Suchrand, Budget). Jedes andere Merkmal fehlt
    dann im Ergebnis und verliert seine Belegung wie am Netz üblich — vorher
    hielt ein einziges großes Merkmal, das niemand brauchte, den ganzen
    Schritt an (RM-235).

    **Gesucht wird wie an einer Stelle** (Review 25.09.2026): Eine ebene Fläche
    bringt ihre Facette mit, und über dem Budget zählt nur der Teil, der an ihr
    hängt (:func:`detect_local`). Und zuerst im eigenen Umfang des Merkmals,
    erst danach im belegten Suchumfang: Der schließt die ganze Umgebung der
    ursprünglichen Stelle ein. Vorher fand die Suche am Drachen eine Fußsohle,
    und die Nachmessung im nächsten Schritt verwarf sie wieder — ihr Würfel
    fasste 50 000 Dreiecke mehr als die Sohle.

    ``standing`` nennt Merkmale, deren Belege am neuen Netz unverändert
    gelten — nach einer belegten starren Bewegung die exakt mitbewegten
    (Review R6). Sie werden übernommen, nicht gesucht: Die Nachmessung
    einer starren Bewegung kann ihr Ergebnis nicht ändern und kostete am
    Drachen je Verschieben und Auswertung vier bis sechs Sekunden mehr.

    **Und dieselbe Nachmessung wird einmal gerechnet** (Review S2): Das
    Ergebnis ist eine reine Funktion von Netz, Merkmalen, Anspruch und
    Budgets (:func:`_known_key`); die Auswertung fragt sie bei jedem Lauf,
    auch ohne Änderung, und am skalierten Drachen kostete jeder Lauf 6,3 s.
    Ein Halt wird nicht gemerkt — er ist selten und fragt wieder.
    """
    _check(check_cancelled)
    memo_key = _known_key(mesh, features, required, standing)
    with _KNOWN_LOCK:
        remembered = _KNOWN.get(memo_key)
        if remembered is not None:
            _KNOWN.move_to_end(memo_key)
            return dict(remembered)
    stitched = detection._one_body(mesh)
    reach = max(EPS_GEOM, weld_tolerance(mesh.bounds.diagonal))
    labels: np.ndarray | None = None
    facet_areas: np.ndarray | None = None
    gathered: list[Feature] = []
    # Je Suche einmal gerechnet und einmal gesammelt; ob ein Merkmal anhält,
    # entscheidet es selbst an diesem Ergebnis — sonst verdeckte ein
    # unbenötigtes Merkmal ein benötigtes mit derselben Suche. **Die Suche ist
    # mehr als ihr Würfel**: Was als vollständig gilt, misst sich an der Kugel
    # um die Mitte (``_inside_radius``). Zwei Würfel mit denselben Dreiecken um
    # verschiedene Mitten teilten sonst ein Ergebnis, und eine Bohrung hielt
    # mit der Kugel ihres Nachbarn am Suchrand an, obwohl sie in ihrer eigenen
    # vollständig lag.
    results: dict[_SearchKey, LocalDetection] = {}
    gathered_keys: set[_SearchKey] = set()
    unmeasured: list[tuple[Feature, str]] = []
    for name, feature in features.items():
        _check(check_cancelled)
        needed = required is None or name in required
        if feature.provenance == "generated" and not feature.recognised:
            continue
        if name in standing and feature.face_indices:
            gathered.append(feature)
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
        # **Eine Fläche trägt keines dieser Längenmaße.** Ihr Umfang steht in
        # ihrer Größe, und ohne diese Zeile bekam sie den Radius null: Der
        # Sackboden einer auf Ø8 geänderten Bohrung galt damit als
        # abgeschnitten — „Das Merkmal setzt sich über den Suchbereich hinaus
        # fort" für eine Kreisfläche, die vollständig im Netz lag. Der
        # flächengleiche Durchmesser ist dasselbe großzügige Maß, das
        # ``diameter`` für eine Bohrung liefert: Er deckt den Rand mit, statt
        # auf dem halben Weg dorthin zu enden.
        area = float(feature.params.get("area") or 0.0)
        if area > 0.0:
            extent = max(extent, 2.0 * math.sqrt(area / math.pi))
        searched = float(feature.params.get("local_search_radius") or 0.0)
        radii = sorted({value for value in (extent, searched) if value > EPS_GEOM})
        if not radii:
            if not needed:
                continue
            raise local_error("boundary")
        seed: int | None = None
        plane = np.empty(0, dtype=np.int64)
        if feature.kind == "face":
            if labels is None or facet_areas is None:
                labels = _facet_of_face(stitched.raw)
                grouped = labels >= 0
                facet_areas = np.bincount(
                    labels[grouped],
                    weights=np.asarray(stitched.raw.area_faces, dtype=float)[grouped],
                )
            seed = _face_seed(
                stitched,
                centre,
                np.asarray(feature.params["normal"], dtype=float),
                reach,
                radii[-1],
                check_cancelled,
                _same_face(labels, facet_areas, area),
            )
            if seed is not None:
                plane = np.flatnonzero(labels == labels[seed])
                if len(plane) > LOCAL_FACE_LIMIT:
                    plane = np.empty(0, dtype=np.int64)
        failure: str | None = "budget"
        for radius in radii:
            indices = _region(stitched, centre, radius, check_cancelled, bounded=False)
            assert indices is not None
            if len(indices) + len(plane) > LOCAL_FACE_LIMIT and seed is not None:
                indices = _connected_to(stitched, indices, seed)
            indices, crowded = _with_its_facet(indices, plane)
            if crowded and not len(indices):
                failure = "budget"
                continue
            key: _SearchKey = (
                tuple(int(index) for index in indices),
                tuple(int(index) for index in plane),
                radii[-1],
                radius,
                np.asarray(centre, dtype=np.float64).tobytes(),
            )
            result = results.get(key)
            if result is None:
                result = (
                    _recognise_region(
                        stitched,
                        indices,
                        (),
                        check_cancelled,
                        centre,
                        radius,
                        proven=plane,
                        recorded=radii[-1],
                    )
                    if len(indices)
                    else LocalDetection(reason="no_feature")
                )
                results[key] = result
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
                    and float((normal * np.asarray(candidate.params["normal"])).sum())
                    >= units.exact_cos_degrees(detection.EPS_ANGLE)
                    and abs(
                        float(((np.asarray(candidate.params["centre"]) - centre) * normal).sum())
                    )
                    <= EPS_GEOM
                    for candidate in result.unfinished
                )
            # **Hat nur die Facette gesucht, muss sie das Merkmal liefern**
            # (Review R4), wie in :func:`detect_local`: Sonst traf die Suche
            # eine andere Fläche in derselben Ebene, und das benötigte Merkmal
            # fiel still weg, statt am Budget anzuhalten.
            if (blocked or crowded) and not _query_is_complete(
                stitched, feature, result.features, check_cancelled=check_cancelled
            ):
                failure = "budget" if crowded else "boundary"
                continue
            failure = None
            if key not in gathered_keys:
                gathered_keys.add(key)
                gathered.extend(result.features.values())
            break
        if failure is not None and needed:
            unmeasured.append((feature, failure))
    measured = _numbered(gathered)
    # **Ein Glied einer Kette findet oft erst die Suche seines Nachbarn**
    # (Durchsicht 0.5.1, REST-BOHRUNG-07): Die Kette aus Bohrung, Senkung und
    # Aufweitung ist länger als jede Kugel um eine ihrer Mitten, und nur die
    # Suche am Kegel dazwischen fasst sie ganz. Angehalten wird für ein
    # benötigtes Merkmal erst, wenn auch keine andere Suche es vollständig
    # zurückgab (:func:`_query_is_complete`, dieselbe Frage wie am Suchrand).
    for feature, failure in unmeasured:
        if not _query_is_complete(stitched, feature, measured, check_cancelled=check_cancelled):
            raise local_error(failure)
    with _KNOWN_LOCK:
        _KNOWN[memo_key] = dict(measured)
        while len(_KNOWN) > KNOWN_MEMORY_LIMIT:
            _KNOWN.popitem(last=False)
    return measured


def _face_seed(
    mesh: MeshData,
    centre: np.ndarray,
    normal: np.ndarray,
    reach: float,
    radius: float,
    check: Callable[[], None] | None,
    fits: Callable[[int], bool],
) -> int | None:
    """Ein Dreieck der bekannten ebenen Fläche am neuen Netz — oder keines.

    Zuerst das Dreieck an der Flächenmitte, wie ein Treffer an der Stelle.
    Liegt die Mitte nicht auf der Fläche — ein Ring, eine Platte mit Bohrung
    in der Mitte —, dann das nächste Dreieck in ihrer Ebene mit ihrer Normalen.
    Liegen an der Mitte mehrere Flächen übereinander, wird nicht gewählt
    (Regel 21); die Nachmessung sucht dann ohne Facette.

    **Und nur ein Dreieck, dessen Facette die Fläche sein kann** (``fits``,
    Review R4): Eine Insel in einer Ringnut liegt so hoch wie die Deckfläche
    um sie herum, und die Mitte der Deckfläche liegt auf ihr.
    """
    near = _region(mesh, centre, reach, check, bounded=False)
    assert near is not None
    if len(near):
        seeds = [seed for seed in _seeds(mesh, near, centre, normal, ()) if fits(seed)]
        if len(seeds) == 1:
            return seeds[0]
        if seeds:
            return None
    region = _region(mesh, centre, radius, check, bounded=False)
    assert region is not None
    if not len(region):
        return None
    normals = np.asarray(mesh.raw.face_normals)[region]
    aligned = (normals * normal).sum(axis=1) >= units.exact_cos_degrees(detection.EPS_ANGLE)
    offset = np.asarray(mesh.raw.triangles_center)[region] - centre
    height = np.abs((offset * normal).sum(axis=1))
    on_plane = aligned & (height <= reach)
    if not on_plane.any():
        return None
    distances = (offset[on_plane] * offset[on_plane]).sum(axis=1)
    for candidate in region[on_plane][np.argsort(distances, kind="stable")].tolist():
        if fits(int(candidate)):
            return int(candidate)
    return None


def _same_face(labels: np.ndarray, areas: np.ndarray, area: float) -> Callable[[int], bool]:
    """Ob die Facette eines Dreiecks die bekannte Fläche sein kann.

    Mit derselben Grenze, mit der die Zuordnung die Größe einer Fläche
    vergleicht (:data:`matching.DIAMETER_TOLERANCE` — im Merkmalsvektor
    einer Fläche steht ihr Inhalt an der Stelle des Durchmessers): Eine
    Facette, die sie nicht als dieselbe Fläche nähme, trägt die Suche nicht.
    """

    def fits(triangle: int) -> bool:
        label = int(labels[triangle])
        if label < 0:
            return False
        if area <= EPS_GEOM:
            return True
        found = float(areas[label])
        return abs(found - area) <= DIAMETER_TOLERANCE * max(found, area)

    return fits
