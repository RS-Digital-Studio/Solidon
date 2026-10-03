"""Einen B-Rep-Körper formen (Bauplan §30, §25).

Die zwei Operationen, die der Grund für einen zweiten Kern sind: Verrundung
und Fase an echten Kanten. Auf einem Netz sind beide Näherungen einer
Näherung — die Kante ist schon eine Kette von Segmenten, und sie zu runden
rundet die Segmente. Hier ist die Kante eine Kurve, und das Ergebnis ist
exakt.

Welche Kanten behandelt werden, ist eine Auswahl, und die Auswahl läuft über
Geometrie, nicht über Indizes: ein Index in die Topologie eines Körpers
ändert sich, sobald sich irgendetwas anderes an ihm ändert, und eine
Verrundung, die wandert, wenn ein unbeteiligtes Loch gebohrt wird, ist
schlimmer als gar keine (§21.2, derselbe Grund, aus dem Merkmalsbezeichner
zugeordnet werden).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Final, Literal, cast

from app.core.brep.canonical import CylinderSurface
from app.core.brep.kernel import (
    DEFLECTION,
    Solid,
    boolean_builder,
    carried_face_slots,
    keep_filament_boundaries,
    listed,
    nearest_distance,
    require,
)
from app.core.errors import (
    BOOLEAN_GEOMETRY_UNSAFE_DETAIL,
    CANCEL,
    CHANGE_SELECTION,
    CORRECT_INPUT,
    PROGRAMMING_ERRORS,
    GeometryError,
    InternalError,
    OperationCancelled,
)
from app.core.geom.edges import (
    LOOP_START,
    ChamferShape,
    EdgeSide,
    EdgeSides,
    LawOnChain,
    MeshEdge,
    RadiusLaw,
    chamfer_reaches,
    check_varying_radius,
    law_at_ends,
    points_forward,
    samples_along,
    starts_at_first,
)
from app.core.geom.edges import EdgeChoice as SharedEdgeChoice
from app.core.geom.edges import choose as choose_by_place
from app.core.geom.edges import named_edges as edges_named
from app.core.geom.edges import wanted as edges_wanted
from app.core.geom.mesh import MeshData
from app.core.geom.section import SectionPlane
from app.core.log import get_logger
from app.core.types import (
    BoundingBox,
    CancelToken,
    PlaneFrame,
    Point2,
    ProgressFn,
    Transform,
    Vec3,
)
from app.core.units import EPS_DISPLAY, EPS_GEOM, dot3, exact_centre, is_close, weld_tolerance
from app.i18n import _

_log = get_logger(__name__)

#: Welche Kanten eine Auswahl meint — **die Tabelle steht in ``geom.edges``**
#: (``EDGE_CHOICES``) und gilt für beide Kerne; zwei Aufzählungen hießen, dass
#: ein Kern eines Tages eine sechste Art kennt und der andere nicht.
EdgeChoice = SharedEdgeChoice


@dataclass(frozen=True, slots=True)
class EdgeInfo:
    """Eine Kante, beschrieben über das, was sie ist, statt über ihren
    Speicherplatz.
    """

    edge: Any
    length: float
    direction: Vec3
    middle: Vec3

    @property
    def upright(self) -> bool:
        return abs(self.direction[2]) > 0.9

    @property
    def flat(self) -> bool:
        return abs(self.direction[2]) < 0.1

    @property
    def extent(self) -> float:
        """Der größte Abstand vom Linienschwerpunkt, am Kreis sein Radius.

        Die Abtastung bleibt unter der Auflösung des Schlüssels. Bei einem
        Kreis liegen alle Punkte im selben Abstand von seiner Mitte.
        """
        return max(math.dist(self.middle, point) for point in edge_points(self, EPS_DISPLAY / 10.0))


def box(width: float, depth: float, height: float) -> Solid:
    """Ein Quader auf dem Bett, in X und Y zentriert — derselbe Ankerpunkt wie
    auf der Mesh-Seite.
    """
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    corner = gp_Pnt(-width / 2.0, -depth / 2.0, 0.0)
    return Solid(BRepPrimAPI_MakeBox(corner, width, depth, height).Shape())


def cylinder(diameter: float, height: float) -> Solid:
    """Ein Zylinder, stehend auf Z = 0."""
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    return Solid(BRepPrimAPI_MakeCylinder(diameter / 2.0, height).Shape())


def torus(centre: Vec3, axis: Vec3, ring_diameter: float, tube_diameter: float) -> Solid:
    """Ein voller Ring um eine Achse durch einen Punkt — das Werkzeug eines Torusmerkmals (P2.6).

    Ein Wulst wird damit vereinigt, eine Kehle damit geschnitten. Was vom Ring
    im Schaft liegt, ist dort ohnehin Material beziehungsweise wird ohnehin
    weggenommen — der Ring braucht keinen Zuschnitt auf den Schaft, anders als
    am Netz (``prepare_ops._torus_tool_mesh``).
    """
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    frame = gp_Ax2(gp_Pnt(*centre), gp_Dir(*axis))
    return Solid(BRepPrimAPI_MakeTorus(frame, ring_diameter / 2.0, tube_diameter / 2.0).Shape())


def sphere(diameter: float) -> Solid:
    """Eine Kugel um den Ursprung — der Grundkörper des Kerns (P2.8)."""
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere

    return Solid(BRepPrimAPI_MakeSphere(diameter / 2.0).Shape())


def cone(bottom: float, top: float, height: float) -> Solid:
    """Ein Kegel oder Kegelstumpf auf Z = 0 — eine Null macht die Seite zur Spitze (P2.8)."""
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone

    return Solid(BRepPrimAPI_MakeCone(bottom / 2.0, top / 2.0, height).Shape())


def defeatured(
    solid: Solid, face_indices: Sequence[int], *, cancelled: CancelToken | None = None
) -> Solid | None:
    """Die Flächen weggenommen, die Nachbarn verlängert — oder ``None`` (P2.6).

    Dasselbe ``BRepAlgoAPI_Defeaturing`` wie in :func:`unround`, für die
    Ringflächen eines Wulstes oder einer Kehle: Der Kern kennt die Torusfläche
    als Ding und weiß, dass der Schaft darunter weitergeht. Gemessen an einem
    Schaft Ø 20 mit Wulst und mit Kehle R 10 / r 3: Nach dem Wegnehmen bleibt
    der Zylinder mit seinem Volumen auf 10⁻¹⁶. Was der Kern nicht wegnehmen
    kann — einen ganzen Ring, dessen Fläche der ganze Körper ist, oder ein
    Torusstück, hinter dem sich die Nachbarn nicht treffen —, gibt er
    unverändert zurück; dann ist es ``None``, und der Aufrufer sagt, was das
    Merkmal ist. Gearbeitet wird an einer privaten Kopie (§21.2).
    """
    require()
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Defeaturing
    from OCP.collections import List_TopoDS_Shape

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    indices = solid.checked_face_indices(face_indices, cancelled=cancelled)
    if not indices:
        return None
    working = replace(solid)
    faces = working.faces()
    chosen = List_TopoDS_Shape()
    for index in indices:
        chosen.Append(faces[working._copied_faces[index]])
    builder = BRepAlgoAPI_Defeaturing()
    builder.SetShape(working.shape)
    builder.AddFacesToRemove(chosen)
    builder.Build()
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if not builder.IsDone():
        return None
    result = working.replacing(builder.Shape(), history=builder, cancelled=cancelled)
    if result.face_count == working.face_count and is_close(result.volume, working.volume):
        return None
    return result


def _seam_edges(solid: Solid) -> Any:
    """Die Nahtkanten des Körpers — als OCCT-Menge, einmal je Körper.

    Eine Naht gehört **einer** Fläche: der Stelle, an der deren
    Parametrisierung umläuft. Gefragt wird deshalb je Fläche nach ihren
    eigenen Kanten und nicht je Kante nach allen Flächen — das erste ist
    linear in den Kantenvorkommen, das zweite ihr Produkt.
    """
    from OCP.BRep import BRep_Tool
    from OCP.collections import (
        IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap,
    )
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    seams = ShapeMap()
    for face in solid.faces():
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            edge = explorer.Current()
            if BRep_Tool.IsClosed_s(TopoDS.Edge(edge), TopoDS.Face(face)):
                seams.Add(edge)
            explorer.Next()
    return seams


def edges_of(solid: Solid) -> list[EdgeInfo]:
    """Jede Kante mit den Zahlen, aus denen sich eine Auswahl treffen lässt."""
    require()

    # **Nahtkanten gehören nicht dazu.** Wo eine Fläche in sich geschlossen ist
    # — der Mantel eines Zylinders, einer Kugel, eines Kegels —, trägt sie eine
    # Naht: die Stelle, an der ihre Parametrisierung umläuft. Das sieht wie
    # eine Kante aus und ist keine; zwischen zwei Flächen liegt sie nicht,
    # sondern in einer.
    #
    # Verrunden lässt sie sich deshalb nicht, und OpenCASCADE sagt das je nach
    # Plattform verschieden: Unter Windows und Linux meldet der Builder
    # „nicht fertig", auf dem Intel-Mac **stürzt der Prozess ab** (gemessen am
    # 08.09.2026, `test_a_selection_that_matches_nothing_says_so`, Stack in
    # `_built`). Ein Kunde verlöre dabei seine Arbeit. Was gar nicht erst in
    # die Auswahl kommt, kann auch nicht gebaut werden — und der vorhandene
    # Satz „Zu dieser Auswahl gehört keine Kante." trifft die Lage genauer als
    # „Der Radius ist zu groß".
    #
    # **Einmal eingesammelt, nicht je Kante gesucht.** Der erste Anlauf fragte
    # ``any(IsClosed_s(edge, face) for face in faces)`` — Kanten mal Flächen,
    # und an einem Teil mit ein paar hundert von jedem ist das der teuerste
    # Posten der ganzen Auswahl. Eine Naht gehört ohnehin **einer** Fläche;
    # gefragt wird deshalb je Fläche nach ihren eigenen Kanten, und das ist
    # linear in der Zahl der Kantenvorkommen.
    seams = _seam_edges(solid)

    described: list[EdgeInfo] = []
    for edge in solid.edges():
        entry = _described_edge(edge, seams)
        if entry is not None:
            described.append(entry)
    return described


def _described_edge(edge: Any, seams: Any) -> EdgeInfo | None:
    """Eine Kante beschreiben — oder nichts für Nähte und Nullkanten."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.LinearProperties_s(edge, props)
    length = float(props.Mass())
    if length <= EPS_GEOM or seams.Contains(edge):
        return None
    curve = BRepAdaptor_Curve(edge)
    start = curve.Value(curve.FirstParameter())
    end = curve.Value(curve.LastParameter())
    span = (end.X() - start.X(), end.Y() - start.Y(), end.Z() - start.Z())
    norm = max((span[0] ** 2 + span[1] ** 2 + span[2] ** 2) ** 0.5, EPS_GEOM)
    centre = props.CentreOfMass()
    return EdgeInfo(
        edge=edge,
        length=length,
        direction=(span[0] / norm, span[1] / norm, span[2] / norm),
        middle=(centre.X(), centre.Y(), centre.Z()),
    )


def native_edge_indices(solid: Solid, entries: Sequence[EdgeInfo]) -> tuple[int, ...]:
    """Die Indizes dieser Kanten im Raum ``solid.edges()`` — über echte Mitgliedschaft.

    Die Position in :func:`edges_of` ist kein nativer Index: Die Liste lässt
    Nähte und Nullkanten aus. Gefragt wird deshalb die Kantenkarte des Solids
    (dieselbe, aus der :meth:`Solid.edges` liest), und eine Kante, die dort
    nicht steht, gehört einem anderen Körper — ein Programmfehler, kein
    Bedienfehler.
    """
    require()
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp

    found = ShapeMap()
    TopExp.MapShapes_s(solid.shape, TopAbs_EDGE, found)
    indices: list[int] = []
    for entry in entries:
        index = int(found.FindIndex(entry.edge))
        if index == 0:
            raise InternalError(
                detail="edge does not belong to this solid",
                values={"middle": [round(value, 3) for value in entry.middle]},
            )
        indices.append(index - 1)
    return tuple(indices)


def _edges_at(working: Solid, indices: Sequence[int]) -> list[EdgeInfo]:
    """Die ausdrücklich gewählten Kanten der Arbeitskopie, im Indexraum ``edges()``.

    Keine Suche nach einem ähnlichen Ersatz und kein gerundeter Schlüssel
    dazwischen: Der Aufrufer hat die Kante am aktuellen Eigentümer bestimmt,
    die private Kopie hat sie über ``_copied_edges`` nachgeführt, und genau
    diese Kante bekommt der Builder. Eine Naht oder Nullkante ist keine
    Kante, die sich bearbeiten ließe — derselbe Satz wie bei einer leeren
    Gruppe.
    """
    seams = _seam_edges(working)
    edges = working.edges()
    chosen: list[EdgeInfo] = []
    for index in indices:
        entry = _described_edge(edges[index], seams)
        if entry is None:
            raise GeometryError(
                detail=_("Zu dieser Auswahl gehört keine Kante."),
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        chosen.append(entry)
    return chosen


def _edges_for(
    working: Solid,
    choice: SharedEdgeChoice,
    keys: Sequence[str],
    checked: tuple[int, ...] | None,
    *,
    rings_by_plane: bool = True,
) -> list[EdgeInfo]:
    """Die Kanten dieses Aufrufs: ausdrücklich gewählte vor Schlüsseln vor Gruppe.

    ``checked`` sind die am Eingabe-Solid geprüften Indizes seines
    ``edges()``-Raums (:meth:`Solid.checked_edge_indices`, **vor** der
    Kopie); die Arbeitskopie führt sie nach. Eine ausdrückliche Auswahl
    fällt nie auf Schlüssel oder Gruppe zurück (§21.3).
    """
    if checked is None:
        return _wanted(working, choice, keys, rings_by_plane=rings_by_plane)
    return _edges_at(working, [working._copied_edges[index] for index in checked])


def edge_points(entry: EdgeInfo, deflection: float = DEFLECTION) -> tuple[Vec3, ...]:
    """Die Kante als Punktfolge — was die Ansicht braucht, um sie zu treffen.

    :class:`EdgeInfo` beschreibt eine Kante über Mitte, Richtung und Länge,
    und für die Auswahl nach Lage reicht das. Für einen Klick reicht es
    nicht: Ein Bogen liegt nirgends dort, wo Mitte und Richtung ihn
    vermuten lassen — der Viertelkreis einer Verrundung hat seinen
    Schwerpunkt neben sich selbst, und ein Zeiger, der auf die Sehne
    zielt, trifft die Kante nie.

    Abgetastet wird nach **Abweichung**, nicht nach fester Punktzahl: Eine
    Strecke kommt mit zwei Punkten zurück, ein Kreis mit so vielen, wie
    ``deflection`` verlangt. Dieselbe Zahl, mit der der Kern tesselliert
    — was im Bild rund aussieht, soll sich auch rund anklicken lassen.

    Scheitert die Abtastung, stehen wenigstens Anfang und Ende da: Eine
    Kante ohne Punkte wäre für den Zeiger nicht vorhanden, und das ist
    schlechter als eine, die nur an ihren Enden getroffen wird.
    """
    require()
    from OCP.BRepAdaptor import BRepAdaptor_Curve

    points = _sampled_edge_points(entry, deflection)
    if points:
        return points
    curve = BRepAdaptor_Curve(entry.edge)
    first = curve.Value(curve.FirstParameter())
    last = curve.Value(curve.LastParameter())
    return ((first.X(), first.Y(), first.Z()), (last.X(), last.Y(), last.Z()))


def _sampled_edge_points(entry: EdgeInfo, deflection: float) -> tuple[Vec3, ...]:
    """Eine vollständige Abtastung; bloße Endpunkte sind kein Zuordnungsbeleg."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection

    curve = BRepAdaptor_Curve(entry.edge)
    sampler = GCPnts_QuasiUniformDeflection(curve, max(deflection, EPS_GEOM))
    if not sampler.IsDone() or sampler.NbPoints() < 2:
        return ()
    points = (sampler.Value(index) for index in range(1, sampler.NbPoints() + 1))
    return tuple((point.X(), point.Y(), point.Z()) for point in points)


def native_edges_of_chains(
    solid: Solid,
    mesh: MeshData,
    chains: Sequence[MeshEdge],
    *,
    cancelled: CancelToken | None = None,
) -> tuple[tuple[int, ...], ...]:
    """Die nativen Kanten, die ein Netzzug belegt — je Zug, ohne Wiederholung.

    Die Zusammenfassung von :func:`native_edges_of_segments`. Eine leere
    Bindung heißt unbekannt, niemals alle Kanten oder glatt.
    """
    return tuple(
        tuple(dict.fromkeys(index for index in claimed if index is not None))
        for claimed in native_edges_of_segments(solid, mesh, chains, cancelled=cancelled)
    )


def native_edges_of_segments(
    solid: Solid,
    mesh: MeshData,
    chains: Sequence[MeshEdge],
    *,
    cancelled: CancelToken | None = None,
) -> tuple[tuple[int | None, ...], ...]:
    """Je Zug und Strecke die native Kante, die sie belegt — ``None``, wo keine eindeutig ist.

    Über Flächenherkunft und tatsächlichen Verlauf. Auch innerhalb einer
    einzigen nativen Fläche kann ein geometrischer Knick liegen; dort gibt es
    keine Kante. Teilen zwei Flächen mehrere native Kanten, muss jede Strecke
    räumlich zu genau einer passen. Und jede belegte native Kante muss
    vollständig von den gewählten Zügen abgedeckt sein: Ein Ausschnitt darf
    nicht zur Bearbeitung der ganzen Kurve werden.

    **Entschieden wird je native Kante, nicht je Zug** (RM-435 M2): Eine
    unvollständig belegte Kante verliert ihre Strecken, die übrigen Kanten
    desselben Zugs bleiben belegt. Am Crimper fiel sonst ein 43-mm-Zug samt
    einer eindeutigen 20-mm-Kante, weil sein Knick an einer 0,85-mm-Kante
    tangential auslief. Die Abdeckung einer Kante hängt nur an den Strecken,
    die sie belegen — ein Durchgang genügt.
    """
    from itertools import pairwise

    import numpy as np
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp

    from app.core.brep.kernel import face_sources

    _check(cancelled)
    sources = face_sources(mesh)
    if len(sources) != mesh.triangle_count or np.any((sources < 0) | (sources >= solid.face_count)):
        return tuple((None,) * max(len(chain.points) - 1, 0) for chain in chains)
    neighbours = NeighbourMap()
    TopExp.MapShapesAndAncestors_s(solid.shape, TopAbs_EDGE, TopAbs_FACE, neighbours)
    _check(cancelled)
    entries = edges_of(solid)
    indices = native_edge_indices(solid, entries)
    by_faces: dict[tuple[int, ...], list[int]] = {}
    for index, entry in zip(indices, entries, strict=True):
        _check(cancelled)
        faces = tuple(
            sorted({solid.face_index(face) for face in listed(neighbours.FindFromKey(entry.edge))})
        )
        if len(faces) == 2 and faces[0] >= 0:
            by_faces.setdefault(faces, []).append(index)
    native = dict(zip(indices, entries, strict=True))
    selected_segments: set[tuple[int, int]] = set()
    for chain in chains:
        _check(cancelled)
        selected_segments.update((min(pair), max(pair)) for pair in pairwise(chain.node_indices))
    face_pairs: dict[tuple[int, int], tuple[int, ...]] = {}
    adjacency = np.asarray(mesh.raw.face_adjacency, dtype=np.int64)
    for nodes, triangles in zip(np.asarray(mesh.raw.face_adjacency_edges), adjacency, strict=True):
        _check(cancelled)
        key = (int(min(nodes)), int(max(nodes)))
        if key in selected_segments:
            face_pairs[key] = tuple(sorted(set(map(int, sources[triangles]))))

    # Zwei Sehnenzüge dürfen je um ihre Tessellierungsgrenze abweichen;
    # verschweißte Ecken zusätzlich um die vorhandene Schweißgrenze.
    join_tolerance = weld_tolerance(mesh.bounds.diagonal)
    reach = 2.0 * max(solid.deflection, EPS_GEOM) + join_tolerance
    sampled: dict[int, tuple[Vec3, ...]] = {}
    claims: list[tuple[int | None, ...]] = []
    for chain in chains:
        _check(cancelled)
        chain_segments = tuple(pairwise(chain.points))
        if len(chain.node_indices) != len(chain.points) or not chain_segments:
            claims.append((None,) * len(chain_segments))
            continue
        found: list[int | None] = []
        for nodes, segment in zip(pairwise(chain.node_indices), chain_segments, strict=True):
            _check(cancelled)
            faces = face_pairs.get((min(nodes), max(nodes)), ())
            candidates = []
            for index in by_faces.get(faces, ()):
                _check(cancelled)
                if index not in sampled:
                    sampled[index] = _sampled_edge_points(native[index], solid.deflection)
                    _check(cancelled)
                points = sampled[index]
                if points and _curve_is_covered(
                    segment, tuple(pairwise(points)), reach, join_tolerance, cancelled
                ):
                    candidates.append(index)
            found.append(candidates[0] if len(candidates) == 1 else None)
        claims.append(tuple(found))
    covered: dict[int, list[tuple[Vec3, Vec3]]] = {}
    for chain, claimed in zip(chains, claims, strict=True):
        _check(cancelled)
        for claim, segment in zip(claimed, pairwise(chain.points), strict=True):
            if claim is not None:
                covered.setdefault(claim, []).append(segment)
    complete: set[int] = set()
    for index, segments in covered.items():
        _check(cancelled)
        if _curve_is_covered(sampled[index], segments, reach, join_tolerance, cancelled):
            complete.add(index)
    return tuple(
        tuple(claim if claim in complete else None for claim in claimed) for claimed in claims
    )


def _curve_is_covered(
    points: Sequence[Vec3],
    segments: Sequence[tuple[Vec3, Vec3]],
    reach: float,
    join_tolerance: float,
    cancelled: CancelToken | None,
) -> bool:
    """Jede Sehne ist durchgehend gedeckt, nicht bloß an einzelnen Proben.

    Die Projektion eines Gegenstücks begrenzt sein Intervall auf der Sehne.
    Liegen beide Intervallenden im Abstand ``reach`` vom Gegenstück, gilt
    das auch dazwischen: Der Abstand zu einer Strecke ist konvex. Die
    Vereinigungsintervalle dürfen nur um die Schweißgrenze auseinanderliegen;
    das Sehnenband selbst darf fehlende ausgewählte Strecken nicht auffüllen.
    """
    from itertools import pairwise

    if len(points) < 2:
        return False
    for start, end in pairwise(points):
        _check(cancelled)
        span = tuple(after - before for before, after in zip(start, end, strict=True))
        square = dot3(span, span)
        if square <= EPS_GEOM * EPS_GEOM:
            return False
        intervals = []
        for first, second in segments:
            _check(cancelled)
            shares = [
                dot3(tuple(value - base for value, base in zip(point, start, strict=True)), span)
                / square
                for point in (first, second)
            ]
            lower, upper = max(0.0, min(shares)), min(1.0, max(shares))
            if upper <= lower:
                continue
            ends = tuple(
                cast(
                    Vec3, tuple(base + share * step for base, step in zip(start, span, strict=True))
                )
                for share in (lower, upper)
            )
            if _points_follow_segments(ends, ((first, second),), reach, cancelled):
                intervals.append((lower, upper))
        if not intervals:
            return False
        joined = 0.0
        gap = join_tolerance / math.sqrt(square)
        for lower, upper in sorted(intervals):
            _check(cancelled)
            if lower > joined + gap:
                return False
            joined = max(joined, upper)
        if joined < 1.0 - gap:
            return False
    return True


def _points_follow_segments(
    points: Sequence[Vec3],
    segments: Sequence[tuple[Vec3, Vec3]],
    reach: float,
    cancelled: CancelToken | None,
) -> bool:
    """Jeder Punkt liegt im Sehnenband; kleine Produkte ohne BLAS oder FMA."""
    for point in points:
        _check(cancelled)
        for start, end in segments:
            _check(cancelled)
            span = tuple(after - before for before, after in zip(start, end, strict=True))
            offset = tuple(value - before for before, value in zip(start, point, strict=True))
            square = dot3(span, span)
            if square <= EPS_GEOM * EPS_GEOM:
                continue
            share = min(max(dot3(offset, span) / square, 0.0), 1.0)
            difference = tuple(
                value - share * direction for value, direction in zip(offset, span, strict=True)
            )
            if dot3(difference, difference) <= reach * reach:
                break
        else:
            return False
    return True


@dataclass(frozen=True, slots=True)
class LoopPiece:
    """Ein Stück vom Rand einer exakten Fläche — beschrieben über das, was es ist.

    ``line`` trägt in ``points`` Anfang und Ende; ``circle`` einen Punkt auf
    dem ganzen Kreis; ``arc`` Anfang und Ende, und der Bogen läuft **gegen den
    Uhrzeigersinn um** ``axis`` vom Anfang zum Ende; ``curve`` ist alles
    andere und trägt die abgetastete Kette. Kreis und Bogen führen dazu
    ``centre``, ``axis`` und ``radius`` aus der Kurve selbst, nicht aus
    Punkten gerechnet.

    ``ellipse`` und ``elliptical_arc`` (RM-188 P6.6a) wie Kreis und Bogen, dazu
    die Enden ihrer beiden Halbachsen: ``major_end`` auf der Hauptachse,
    ``minor_end`` auf der Nebenachse — genau die drei Punkte, die eine
    Skizzenellipse trägt.
    """

    kind: Literal["line", "arc", "circle", "ellipse", "elliptical_arc", "curve"]
    points: tuple[Vec3, ...]
    centre: Vec3 | None = None
    axis: Vec3 | None = None
    radius: float = 0.0
    major_end: Vec3 | None = None
    minor_end: Vec3 | None = None


@dataclass(frozen=True, slots=True)
class FaceLoop:
    """Ein geschlossener Rand einer Fläche: außen einer, innen je Loch einer."""

    outer: bool
    pieces: tuple[LoopPiece, ...]


def face_loops(
    solid: Solid, face_index: int, deflection: float = DEFLECTION
) -> tuple[FaceLoop, ...]:
    """Die Ränder der Fläche ``face_index`` — Strecken, Kreise, Bögen und
    Ellipsen exakt.

    Für die Flächenkontur der Skizze (RM-188 P3.4): Am exakten Körper ist der
    Rand einer Bohrung ein Kreis und keine Kette aus Sehnen, und so soll er in
    der Zeichnung ankommen — ihr Mittelpunkt ist dann ein Punkt, an dem man
    eine neue Bohrung ausrichten kann. Was weder Strecke noch Kreis ist, wird
    nach Abweichung abgetastet (``deflection``, dieselbe Zahl, mit der der
    Kern tesselliert).

    Die Drähte kommen in der Reihenfolge der Fläche, die Kanten je Draht in
    Laufrichtung (``BRepTools_WireExplorer``). Außen ist der Draht, den
    OpenCASCADE als äußeren nennt (``BRepTools.OuterWire``).
    """
    require()
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection
    from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Ellipse, GeomAbs_Line
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_WIRE
    from OCP.TopExp import TopExp, TopExp_Explorer
    from OCP.TopoDS import TopoDS

    # Welche Flächen an einer Kante hängen — erst gebaut, wenn eine Kante
    # weder Strecke noch Kreis noch Ellipse ist (:func:`_section_ellipse`).
    neighbours: Any = None

    def spot(point: Any) -> Vec3:
        return (float(point.X()), float(point.Y()), float(point.Z()))

    def reach(centre: Vec3, direction: Any, length: float) -> Vec3:
        return (
            centre[0] + length * float(direction.X()),
            centre[1] + length * float(direction.Y()),
            centre[2] + length * float(direction.Z()),
        )

    face = solid.faces()[face_index]
    outer_wire = BRepTools.OuterWire_s(face)
    loops: list[FaceLoop] = []
    wires = TopExp_Explorer(face, TopAbs_WIRE)
    while wires.More():
        wire = TopoDS.Wire(wires.Current())
        pieces: list[LoopPiece] = []
        edges = BRepTools_WireExplorer(wire, face)
        while edges.More():
            curve = BRepAdaptor_Curve(edges.Current())
            first, last = curve.FirstParameter(), curve.LastParameter()
            start, end = spot(curve.Value(first)), spot(curve.Value(last))
            kind = curve.GetType()
            if kind == GeomAbs_Line:
                if math.dist(start, end) > EPS_GEOM:
                    pieces.append(LoopPiece("line", (start, end)))
            elif kind == GeomAbs_Circle:
                circle = curve.Circle()
                direction = circle.Axis().Direction()
                # Der Parameter eines Kreises läuft gegen den Uhrzeigersinn um
                # seine Achse — vom ersten zum letzten ist also der Bogen,
                # gleich in welcher Richtung der Draht die Kante durchläuft.
                whole = last - first >= 2.0 * math.pi - EPS_GEOM
                pieces.append(
                    LoopPiece(
                        "circle" if whole else "arc",
                        (start,) if whole else (start, end),
                        centre=spot(circle.Location()),
                        axis=(float(direction.X()), float(direction.Y()), float(direction.Z())),
                        radius=float(circle.Radius()),
                    )
                )
            elif kind == GeomAbs_Ellipse:
                # Wie beim Kreis: Der Parameter läuft gegen den Uhrzeigersinn um
                # die Achse, im rechtshändigen Rahmen aus Haupt- und Nebenachse
                # (``gp_Ax2``) — vom ersten zum letzten ist der Bogen.
                ellipse = curve.Ellipse()
                position = ellipse.Position()
                direction = position.Direction()
                middle = spot(ellipse.Location())
                whole = last - first >= 2.0 * math.pi - EPS_GEOM
                pieces.append(
                    LoopPiece(
                        "ellipse" if whole else "elliptical_arc",
                        (start,) if whole else (start, end),
                        centre=middle,
                        axis=(float(direction.X()), float(direction.Y()), float(direction.Z())),
                        radius=float(ellipse.MajorRadius()),
                        major_end=reach(middle, position.XDirection(), ellipse.MajorRadius()),
                        minor_end=reach(middle, position.YDirection(), ellipse.MinorRadius()),
                    )
                )
            else:
                sampler = GCPnts_QuasiUniformDeflection(curve, max(deflection, EPS_GEOM))
                if sampler.IsDone() and sampler.NbPoints() >= 2:
                    chain = tuple(
                        spot(sampler.Value(index)) for index in range(1, sampler.NbPoints() + 1)
                    )
                else:
                    chain = (start, end)
                if neighbours is None:
                    neighbours = NeighbourMap()
                    TopExp.MapShapesAndAncestors_s(
                        solid.shape, TopAbs_EDGE, TopAbs_FACE, neighbours
                    )
                middle_spot = spot(curve.Value((first + last) / 2.0))
                recognised = _section_ellipse(neighbours, face, edges.Current(), chain, middle_spot)
                pieces.append(recognised or LoopPiece("curve", chain))
            edges.Next()
        if pieces:
            loops.append(FaceLoop(outer=bool(wire.IsSame(outer_wire)), pieces=tuple(pieces)))
        wires.Next()
    return tuple(loops)


def _section_ellipse(
    neighbours: Any, face: Any, edge: Any, chain: Sequence[Vec3], middle: Vec3
) -> LoopPiece | None:
    """Die Ellipse, die eine B-Spline-Kante in Wahrheit ist — oder nichts
    (RM-188 P6.6a).

    OpenCASCADE rechnet den Schnitt einer Ebene mit einer extrudierten
    Ellipse als B-Spline: Nach einer elliptischen Tasche in einem exakten
    Block trägt die Deckfläche keine Ellipse mehr, und ihre Kontur kam als
    Kette aus 35 Strecken in die Zeichnung (gemessen,
    ``konzepte/nachweise-release-0.5.0/sonden/p66/sonde_ellipse_boolean.py``).
    Steht die Ebene aber senkrecht auf der Extrusionsrichtung und die
    Grundellipse ebenso, ist dieser Schnitt die Grundellipse selbst, in die
    Ebene verschoben — eine Aussage
    über die beiden Flächen, keine Anpassung an Punkte.

    **Geprüft wird sie trotzdem.** Liegt ein Abtastpunkt der Kante weiter als
    ihre eigene Toleranz neben der Ellipse, bleibt es bei der Kette; gemessen
    wird radial, und das ist nie weniger als der wahre Abstand. ``middle``
    ist der Punkt auf halbem Parameterweg: Er sagt, in welcher Richtung die
    Kante läuft, denn anders als bei Kreis und Ellipse legt ein B-Spline das
    nicht fest.
    """
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Ellipse, GeomAbs_Plane, GeomAbs_SurfaceOfExtrusion
    from OCP.TopoDS import TopoDS

    flat = BRepAdaptor_Surface(face)
    if flat.GetType() != GeomAbs_Plane or not neighbours.Contains(edge) or len(chain) < 2:
        return None
    plane = flat.Plane()
    normal = plane.Axis().Direction()
    origin = plane.Location()
    allowed = max(float(BRep_Tool.Tolerance_s(TopoDS.Edge(edge))), EPS_GEOM)
    for shape in neighbours.FindFromKey(edge):
        wall = BRepAdaptor_Surface(TopoDS.Face(shape))
        if wall.GetType() != GeomAbs_SurfaceOfExtrusion:
            continue
        basis = wall.BasisCurve()
        if basis.GetType() != GeomAbs_Ellipse:
            continue
        ellipse = basis.Ellipse()
        position = ellipse.Position()
        direction = wall.Direction()
        facing = direction.Dot(normal)
        if 1.0 - abs(facing) > EPS_GEOM or 1.0 - abs(position.Direction().Dot(normal)) > EPS_GEOM:
            continue
        centre = ellipse.Location()
        along = (
            (origin.X() - centre.X()) * normal.X()
            + (origin.Y() - centre.Y()) * normal.Y()
            + (origin.Z() - centre.Z()) * normal.Z()
        ) / facing
        middle_point: Vec3 = (
            centre.X() + along * direction.X(),
            centre.Y() + along * direction.Y(),
            centre.Z() + along * direction.Z(),
        )
        frame = _SectionFrame(
            centre=middle_point,
            x_axis=_vector(position.XDirection()),
            y_axis=_vector(position.YDirection()),
            major=float(ellipse.MajorRadius()),
            minor=float(ellipse.MinorRadius()),
        )
        if max(frame.off(point) for point in (*chain, middle)) > allowed:
            continue
        ends = (chain[0], chain[-1])
        whole = math.dist(*ends) <= allowed
        if not whole:
            # Nur eine Entscheidung und mit großem Abstand — hier darf ``atan2``
            # stehen (RM-187): Läuft die Kante über ``middle`` gegen den
            # Uhrzeigersinn vom ersten zum letzten Punkt, oder andersherum?
            turn = 2.0 * math.pi
            begin = frame.angle(ends[0])
            if (frame.angle(middle) - begin) % turn > (frame.angle(ends[1]) - begin) % turn:
                ends = (ends[1], ends[0])
        return LoopPiece(
            "ellipse" if whole else "elliptical_arc",
            (ends[0],) if whole else ends,
            centre=middle_point,
            axis=_vector(position.Direction()),
            radius=frame.major,
            major_end=frame.reached(frame.x_axis, frame.major),
            minor_end=frame.reached(frame.y_axis, frame.minor),
        )
    return None


def _vector(direction: Any) -> Vec3:
    """Eine Richtung aus OpenCASCADE als Zahlentripel."""
    return (float(direction.X()), float(direction.Y()), float(direction.Z()))


@dataclass(frozen=True, slots=True)
class _SectionFrame:
    """Eine Ellipse im Raum, wie :func:`_section_ellipse` sie prüft: Mitte,
    die Richtungen beider Achsen und ihre Halbachsen."""

    centre: Vec3
    x_axis: Vec3
    y_axis: Vec3
    major: float
    minor: float

    def local(self, point: Vec3) -> tuple[float, float]:
        """Der Punkt im Kreis der Ellipse — auf ihr hat er die Länge eins."""
        gap = [point[place] - self.centre[place] for place in range(3)]
        return (
            sum(gap[place] * self.x_axis[place] for place in range(3)) / self.major,
            sum(gap[place] * self.y_axis[place] for place in range(3)) / self.minor,
        )

    def off(self, point: Vec3) -> float:
        """Wie weit der Punkt radial neben der Ellipse liegt — nie weniger als
        der wahre Abstand, null genau auf ihr."""
        u, v = self.local(point)
        size = math.hypot(u, v)
        reach = math.dist(point, self.centre)
        return reach * abs(1.0 - 1.0 / size) if size > 0.0 else reach

    def angle(self, point: Vec3) -> float:
        """Der Parameterwinkel des Punkts — nur für Entscheidungen."""
        u, v = self.local(point)
        return math.atan2(v, u)

    def reached(self, direction: Vec3, length: float) -> Vec3:
        """Der Punkt ``length`` von der Mitte in ``direction``."""
        return (
            self.centre[0] + length * direction[0],
            self.centre[1] + length * direction[1],
            self.centre[2] + length * direction[2],
        )


def edge_key(entry: EdgeInfo) -> str:
    """Der stabile Verweis auf **eine** Kante (E4, RM-147, §21).

    Eine Kante hat keine Kennung, die eine zweite Auswertung überlebt: Ihr
    nativer Handle gehört dem Lauf, der ihn erzeugt hat, und ihr Platz in
    ``solid.edges()`` verschiebt sich, sobald eine Operation davor etwas
    ändert. Beides in eine Projektdatei zu schreiben hieße, beim nächsten
    Öffnen eine andere Kante zu verrunden — still.

    Der Schlüssel kommt deshalb aus der **Geometrie**: Mittelpunkt und
    Richtung, auf hundertstel Millimeter beziehungsweise drei Stellen
    gerundet. Bei geschlossenen Kurven kommt ihre Ausdehnung hinzu, damit
    die konzentrischen Ränder eines Rohrs verschieden heißen.

    **Die Richtung ohne Vorzeichen**, denn dieselbe Kante kann in beide
    Richtungen laufen, je nachdem, welche Fläche sie beschreibt: Die erste
    Komponente ungleich null wird positiv gemacht. Ohne das trüge dieselbe
    Kante nach einer Booleschen Operation einen anderen Schlüssel, und die
    Verrundung fiele aus, statt zu greifen.

    Gerundet wird auf ein Hundertstel, weil das die Größenordnung ist, in der
    dieser Drucker arbeitet (§11) — feiner hieße, dass ein Kern mit anderer
    Toleranz denselben Punkt anders schreibt.
    """
    # **Die Formatierung steht einmal**, in ``geom.edges``: Sie gilt für
    # beide Kerne, und dieselbe Kante muss aus beiden denselben Schlüssel
    # bekommen. Zwei Fassungen liefen daran schon auseinander — an der
    # negativen Null, die sich als ``-0.000`` schreibt.
    from app.core.geom.edges import edge_key as shared

    return shared(entry)


def named_edges(solid: Solid, keys: Sequence[str]) -> list[EdgeInfo]:
    """Die Kanten zu diesen Schlüsseln — in der Reihenfolge der Schlüssel.

    Was nicht mehr da ist, fehlt in der Antwort; **wer daraus einen Fehler
    macht, entscheidet der Aufrufer.** Eine Kante kann verschwunden sein, weil
    ein Schritt davor sie weggenommen hat, und dann ist das eine Auskunft an
    den Kunden und kein Programmfehler (Regel 17).
    """
    return edges_named(edges_of(solid), keys)


def choose(solid: Solid, choice: EdgeChoice, *, rings_by_plane: bool = True) -> list[EdgeInfo]:
    """Die Kanten, die eine benannte Auswahl meint."""
    return choose_by_place(edges_of(solid), choice, rings_by_plane=rings_by_plane)


def _wanted(
    solid: Solid, choice: EdgeChoice, keys: Sequence[str], *, rings_by_plane: bool = True
) -> list[EdgeInfo]:
    """Die Kanten, die dieser Aufruf behandelt — genannte vor Gruppe (E4).

    **Die Auswahl selbst steht in ``geom.edges``**, aus demselben Grund wie
    :func:`edge_key`: Sie fragt nur nach ``upright``, ``flat`` und der Mitte,
    und beide Kerne beantworten das gleich. Zwei Fassungen hießen, dass
    „alle senkrechten Kanten" hier bald etwas anderes bedeutet als am Netz —
    bei derselben Menüzeile und demselben Parameter.
    """
    return edges_wanted(edges_of(solid), choice, keys, rings_by_plane=rings_by_plane)


def fillet(
    solid: Solid,
    radius: float,
    choice: EdgeChoice = "all",
    keys: Sequence[str] = (),
    *,
    selected_edges: Sequence[int] | None = None,
    rings_by_plane: bool = True,
    cancelled: CancelToken | None = None,
    law: RadiusLaw | None = None,
) -> Solid:
    """Rundet die gewählten Kanten. Exakt, weil die Kante eine Kurve
    ist (§30).

    ``keys`` sind einzelne Kanten (:func:`edge_key`, E4). Sind welche genannt,
    gelten sie und nicht die Gruppe: Wer eine bestimmte Kante angibt, meint
    sie — nicht alle senkrechten dazu. ``selected_edges`` geht noch einen
    Schritt weiter: Indizes in ``solid.edges()``, am aktuellen Eigentümer
    bestimmt und ohne gerundeten Schlüssel dazwischen — der Weg, den der
    Radiuswechsel für die belegte scharfe Kante nimmt. ``cancelled`` wird
    vor und nach jedem teuren Schritt gefragt: Wandkarte, je Trägerfläche,
    je Kante, um den nativen Bau und um die Prüfung danach.

    ``rings_by_plane`` wie bei :func:`app.core.geom.edges.choose`: aus nur für
    Schritte, die vor Format 37 gespeichert wurden (RM-279).

    ``law`` gibt jeder Kante einen veränderlichen Radius (P6.1): Jede Kontur
    — eine Kante mit allen tangential anschließenden, so wie OpenCASCADE sie
    zusammenfasst — bekommt den Verlauf von ihrem Anfang
    (:func:`~app.core.geom.edges.starts_at_first`) zu ihrem Ende, als dichte
    Liste aus Stelle und Radius (:meth:`RadiusLaw.samples`). Ein eigenes
    ``Law_Function`` nimmt der Kern nicht an; gemessen steht das an
    :data:`~app.core.geom.edges.LAW_SAMPLES`.
    """
    require()
    _check(cancelled)
    varying = law is not None and not law.constant
    if law is not None:
        radius = law.largest
    checked = None if selected_edges is None else solid.checked_edge_indices(selected_edges)
    working = replace(solid)
    chosen = _edges_for(working, choice, keys, checked, rings_by_plane=rings_by_plane)

    if varying:
        from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet

        builder = BRepFilletAPI_MakeFillet(working.shape)
        assert law is not None
        _laid_along(builder, chosen, law)
        _fits_the_wall(working, radius, chosen, "fillet", cancelled=cancelled)
        return _built(working, builder, "fillet", radius, len(chosen), cancelled=cancelled)
    _fits_the_wall(working, radius, chosen, "fillet", cancelled=cancelled)
    return _build_constant_fillet(working, chosen, radius, cancelled=cancelled)


#: Bis zu wie vielen Konturen die letzte Stufe der Gruppensuche jede einmal
#: weglässt — je Kontur ein Bau der ganzen übrigen Gruppe. Darüber sagt die
#: Gruppe ab, statt minutenlang zu bauen (RM-435): Die Vorgängerin ließ jede
#: Kante einzeln weg und brauchte an ``pegboard-goot-ceramic-screwdrivers-v3``
#: 288 Bauten und 148 s für eine Absage. Eine Zahl und keine Zeit, damit
#: dieselbe Datei auf jeder Maschine dasselbe Teil ergibt.
LEAVE_ONE_OUT_LIMIT: Final = 32

#: Was die Leiste während der Gruppensuche sagt (§2.8) — je Stufe von
#: :class:`_GroupSearch`. Der erste Bau meldet nichts: Gelingt er, ist die
#: Rundung so schnell wie ohne Suche.
_SEARCH_STAGES: Final = {
    "named": _("Die Rundung wird ohne die gemeldeten Stellen gebaut …"),
    "probe": _("Die Kanten werden einzeln geprüft …"),
    "leave_out": _("Die Gruppe wird ohne je eine Kante gebaut …"),
}


@dataclass(frozen=True, slots=True)
class _GroupCandidate:
    """Ein Bau eines Teils der Gruppe — und wen er beschuldigt, wenn er scheitert.

    ``solid`` steht nur nach einem vollständig geprüften Bau, der trägt;
    ``passed`` gilt auch für eine Probe ohne Tessellierung. ``blamed`` sind
    gewählte Kanten (Indizes in ``edges()`` des Eingangs), deren Kontur der
    Bau als Fehlstelle nennt — leer, wenn er keine benennt.
    """

    passed: bool
    solid: Solid | None = None
    blamed: frozenset[int] = frozenset()
    certain: bool = True
    """Ob der Builder selbst benennt (Fehlkontur, Fehlecke) — sonst ist es eine
    Ortung über Flächen des Ergebnisses, und die trifft auch Nachbarn."""


#: Bis zu wie vielen über Flächen beschuldigten Konturen die Suche zuerst jede
#: einzeln weglässt, bevor alle fallen (:class:`_GroupSearch`).
SUSPECTS_TRIED_ALONE: Final = 8


@dataclass(frozen=True, slots=True)
class GroupFillet:
    """Was :func:`fillet_group` gerundet und ausgelassen hat — Kanten als Indizes des Eingangs."""

    solid: Solid
    omitted: tuple[int, ...] = ()
    """Kanten, die mit den übrigen nicht zusammen gebaut werden konnten."""
    thin: tuple[int, ...] = ()
    """Kanten, an deren Kontur eine Wand nicht dicker ist als der Radius — vor
    jedem Bau ausgelassen, denn dort kann der Bau die Anwendung beenden."""
    thinnest: float = math.inf
    """Die dünnste Wand an diesen Kanten in mm: Darunter passt der Radius dort."""


def fillet_group(
    solid: Solid,
    radius: float,
    selected_edges: Sequence[int],
    *,
    cancelled: CancelToken | None = None,
    progress: ProgressFn | None = None,
) -> GroupFillet:
    """Rundet eine belegte Kantengruppe und lässt aus, was OpenCASCADE nicht baut.

    Gerufen für jede Gruppe konstanter Radien, die ``geom.edge_ops`` an native
    Kanten gebunden hat. Gelingt der erste Bau, bleibt es bei ihm — so schnell
    wie :func:`fillet`. Sonst sucht sie, was die Gruppe zu Fall bringt, und
    zwar **je Kontur**: OpenCASCADE setzt eine Rundung über tangential
    anschließende Kanten fort, und eine Kante einer Kontur wegzulassen ließe
    sie trotzdem gerundet. In dieser Reihenfolge, jeder Bau auf frischer Form:

    1. **Was der Bau selbst sagt.** Ein gescheiterter Builder nennt
       Fehlkonturen und Fehlecken, ein gebauter, aber ungültiger Körper seine
       ungültigen Flächen, eine offene Schale ihre freien Kanten, eine undichte
       Tessellierung ihre offenen Dreiecke. Über die Historie des Builders
       führen sie zu den Konturen, deren Rundung dort liegt; die fallen weg,
       und der Rest wird neu gebaut — solange der Bau etwas benennt.
    2. **Jede Kontur allein**, wenn er nichts benennt, als Probe ohne
       Tessellierung. Was allein nicht trägt, fällt weg.
    3. **Je eine Kontur weg**, bis :data:`LEAVE_ONE_OUT_LIMIT` Konturen — für
       das, was nur im Verbund scheitert.

    **Die Wand prüft sie je Kontur, vor jedem Bau** (der Schutz aus
    :func:`_fits_the_wall`): Ist eine Wand an einer Kante der Kontur nicht
    dicker als der Radius — auch an einer tangential fortgesetzten, die
    niemand gewählt hat —, fällt die Kontur aus der Gruppe (``thin``), statt
    die ganze Gruppe abzusagen. Eine Kontur ist eine gewählte Kante mit allen
    tangential anschließenden; das hängt an der Form, nicht am Radius oder an
    den übrigen Kanten, und gilt deshalb für jede Teilmenge.

    Jede Kombination wird höchstens einmal gebaut. ``progress`` erfährt ab dem
    ersten gescheiterten Bau, wie weit die Suche ist (§2.8). Trägt kein Teil
    der Gruppe, kommt die Absage „zu groß“. Gemessen an
    ``pegboard-gs-100-v2.step``, „alle Kanten“ R 0,5: drei Bauten statt 134,
    61 statt 58 Kanten gerundet.
    """
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    from OCP.TopoDS import TopoDS

    require()
    _check(cancelled)
    checked = solid.checked_edge_indices(selected_edges, cancelled=cancelled)
    working = replace(solid)
    _check(cancelled)
    chosen = _edges_for(working, "all", (), checked)
    builder = BRepFilletAPI_MakeFillet(working.shape)
    for entry in chosen:
        builder.Add(radius, entry.edge)
    rounds = _RoundsOf(working, builder, chosen, checked)
    members = [sorted(contour) for contour in rounds.members]
    walls = iter(
        _edge_walls(
            working,
            [
                TopoDS.Edge(rounds.known.FindKey(member))
                for contour in members
                for member in contour
            ],
            cancelled=cancelled,
        )
    )
    contour_walls = [min(next(walls) for _member in contour) for contour in members]
    carried = [number for number, wall in enumerate(contour_walls) if radius < wall]
    if not carried:
        raise GeometryError(
            detail=_too_large("fillet"),
            suggestions=(CORRECT_INPUT, CANCEL),
            values={
                "size_mm": round(radius, 3),
                "edges": len(chosen),
                "wall_mm": round(min(contour_walls), 2),
            },
        )
    contours = tuple(tuple(sorted(rounds.chosen_in[number])) for number in carried)
    thin = [number for number in range(len(members)) if number not in carried]
    found = _GroupSearch(solid, radius, contours, cancelled=cancelled, progress=progress).run()
    if found is None:
        raise GeometryError(
            detail=_too_large("fillet"),
            suggestions=(CORRECT_INPUT, CANCEL),
            values={"size_mm": round(radius, 3), "edges": len(chosen)},
        )
    result, omitted = found
    return GroupFillet(
        result,
        omitted=tuple(index for number in sorted(omitted) for index in contours[number]),
        thin=tuple(index for number in thin for index in sorted(rounds.chosen_in[number])),
        thinnest=min((contour_walls[number] for number in thin), default=math.inf),
    )


class _GroupSearch:
    """Eine Suche: welche Konturen der Gruppe zusammen tragen (:func:`fillet_group`)."""

    def __init__(
        self,
        solid: Solid,
        radius: float,
        contours: tuple[tuple[int, ...], ...],
        *,
        cancelled: CancelToken | None,
        progress: ProgressFn | None,
    ) -> None:
        self.solid = solid
        self.radius = radius
        self.contours = contours
        self.cancelled = cancelled
        self.progress = progress
        self.reached = 0.0
        self.tried: dict[tuple[frozenset[int], bool], _GroupCandidate] = {}
        self.contour_of = {
            index: number for number, members in enumerate(contours) for index in members
        }

    def build(self, numbers: Sequence[int], *, whole: bool = True) -> _GroupCandidate:
        """Baut diese Konturen einmal; eine zweite Frage bekommt die erste Antwort."""
        key = (frozenset(numbers), whole)
        known = self.tried.get(key)
        if known is not None:
            return known
        indices = tuple(index for number in sorted(numbers) for index in self.contours[number])
        outcome = _group_candidate(
            self.solid, self.radius, indices, whole=whole, cancelled=self.cancelled
        )
        self.tried[key] = outcome
        return outcome

    def named(self, outcome: _GroupCandidate, remaining: Sequence[int]) -> list[int]:
        """Die übrigen Konturen, die ein gescheiterter Bau benennt."""
        numbers = {self.contour_of[index] for index in outcome.blamed if index in self.contour_of}
        return [number for number in remaining if number in numbers]

    def report(self, share: float, stage: str) -> None:
        """Meldet einen Anteil, der nie zurückgeht (§2.8)."""
        _check(self.cancelled)
        if self.progress is None:
            return
        self.reached = max(self.reached, min(share, 1.0))
        self.progress(self.reached, str(_SEARCH_STAGES[stage]))

    def run(self) -> tuple[Solid, list[int]] | None:
        """Der Körper und die ausgelassenen Konturen — ``None``, wenn kein Teil trägt."""
        remaining = list(range(len(self.contours)))
        outcome = self.build(remaining)
        if outcome.solid is not None:
            return outcome.solid, []
        omitted: list[int] = []
        probed = False
        rounds = 0
        while len(remaining) > 1:
            named = self.named(outcome, remaining)
            if named and len(named) < len(remaining):
                rounds += 1
                self.report(min(0.3, 0.1 * rounds), "named")
                if not outcome.certain and len(named) <= SUSPECTS_TRIED_ALONE:
                    # Über Flächen geortet ist eine Vermutung: Oft genügt eine
                    # der beschuldigten Konturen (am Stift auf der Plattenkante
                    # R 0,3 eine statt vier).
                    for number in named:
                        trial = self.build([other for other in remaining if other != number])
                        if trial.solid is not None:
                            return trial.solid, [*omitted, number]
            elif probed:
                break
            else:
                probed = True
                named = []
                for position, number in enumerate(remaining):
                    self.report(0.3 + 0.4 * position / len(remaining), "probe")
                    if not self.build([number], whole=False).passed:
                        named.append(number)
                if len(named) == len(remaining):
                    return None
                if not named:
                    break
            omitted.extend(named)
            remaining = [number for number in remaining if number not in named]
            outcome = self.build(remaining)
            if outcome.solid is not None:
                return outcome.solid, omitted
        if 1 < len(remaining) <= LEAVE_ONE_OUT_LIMIT:
            for position, number in enumerate(remaining):
                self.report(0.7 + 0.3 * position / len(remaining), "leave_out")
                outcome = self.build([other for other in remaining if other != number])
                if outcome.solid is not None:
                    return outcome.solid, [*omitted, number]
        return None


def _group_candidate(
    solid: Solid,
    radius: float,
    indices: Sequence[int],
    *,
    whole: bool,
    cancelled: CancelToken | None,
) -> _GroupCandidate:
    """Baut ``indices`` auf frischer Form und prüft wie :func:`_built` — mit Ortung.

    Dieselben Fragen wie dort, von billig nach teuer: gebaut, gültig,
    geschlossen, so viele Körper wie vorher, dann (``whole``) die Kopie mit
    Filamenten, die Dichtheit der Tessellierung und zuletzt das Volumen — am
    gerundeten Körper eine Randintegration und die teuerste Frage, die ein
    Zwischenstand der Suche deshalb nie stellt. Ohne ``whole`` ist es eine
    Probe ohne Kopie und ohne Tessellierung.
    """
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet

    _check(cancelled)
    candidate = replace(solid)
    _check(cancelled)
    entries = _edges_for(candidate, "all", (), tuple(indices))
    builder = BRepFilletAPI_MakeFillet(candidate.shape)
    for entry in entries:
        _check(cancelled)
        builder.Add(radius, entry.edge)
    rounds = _RoundsOf(candidate, builder, entries, indices)
    _check(cancelled)
    try:
        builder.Build()
        done = bool(builder.IsDone())
    except PROGRAMMING_ERRORS:
        raise
    except Exception:  # OpenCASCADE wirft eigene Ausnahmearten
        done = False
    _check(cancelled)
    if not done:
        return _GroupCandidate(False, blamed=rounds.at_faults())
    shape = builder.Shape()
    if not BRepCheck_Analyzer(shape).IsValid():
        return _GroupCandidate(
            False, blamed=rounds.at_faces(shape, _invalid_faces(shape)), certain=False
        )
    _check(cancelled)
    if not whole:
        loose = _faces_at_free_edges(shape)
        if loose:
            return _GroupCandidate(False, blamed=rounds.at_faces(shape, loose), certain=False)
        return _GroupCandidate(_solid_count(shape) == candidate.solid_count)
    outcome = candidate.replacing(shape, history=builder, cancelled=cancelled)
    _check(cancelled)
    if not outcome.is_closed:
        # Dieselbe Frage wie ``is_closed``, nur mit den Flächen an den freien
        # Kanten — gestellt erst, wenn die Antwort nein ist.
        loose = _faces_at_free_edges(shape)
        return _GroupCandidate(False, blamed=rounds.at_faces(shape, loose), certain=False)
    if outcome.solid_count != candidate.solid_count:
        return _GroupCandidate(False)
    if not outcome.is_watertight:
        return _GroupCandidate(
            False, blamed=rounds.at_faces(shape, _open_faces(outcome)), certain=False
        )
    _check(cancelled)
    if outcome.volume <= EPS_GEOM:
        return _GroupCandidate(False)
    _log.info("fillet of %.2f mm on %d edge(s) of a group", radius, len(entries))
    return _GroupCandidate(True, outcome)


class _RoundsOf:
    """Die Konturen eines Builders und die gewählten Kanten darin — für die Ortung.

    ``chosen_in`` steht je Kontur in der Zählung des Builders (Kontur 1 an
    Stelle 0) und nennt die Indizes des Eingangs. Eine Kontur trägt auch die
    tangential fortgesetzten Kanten, die niemand gewählt hat
    (``members``, Nummern der Kantenkarte der Arbeitskopie).
    """

    def __init__(
        self, candidate: Solid, builder: Any, entries: Sequence[EdgeInfo], indices: Sequence[int]
    ) -> None:
        from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
        from OCP.TopAbs import TopAbs_EDGE
        from OCP.TopExp import TopExp

        self.candidate = candidate
        self.builder = builder
        self.known = ShapeMap()
        TopExp.MapShapes_s(candidate.shape, TopAbs_EDGE, self.known)
        picked = {
            int(self.known.FindIndex(entry.edge)): index
            for entry, index in zip(entries, indices, strict=True)
        }
        self.members: list[frozenset[int]] = []
        self.chosen_in: list[frozenset[int]] = []
        for number in range(1, int(builder.NbContours()) + 1):
            members = frozenset(
                int(self.known.FindIndex(builder.Edge(number, position)))
                for position in range(1, int(builder.NbEdges(number)) + 1)
            )
            self.members.append(members)
            self.chosen_in.append(frozenset(picked[k] for k in members if k in picked))

    def _of(self, numbers: set[int]) -> frozenset[int]:
        return frozenset(index for number in numbers for index in self.chosen_in[number - 1])

    def at_faults(self) -> frozenset[int]:
        """Die Konturen, die ein gescheiterter Bau als Fehlkontur oder an einer Fehlecke nennt.

        ``FaultyContour`` zählt die Streifen des Builders; nur die ersten
        ``NbContours`` sind Konturen — am Prüfkasten aus RM-284 nannte er
        Streifen 25 bei 17 Konturen. Ein solcher Streifen benennt nichts.
        """
        from OCP.collections import (
            IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
        )
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
        from OCP.TopExp import TopExp

        builder = self.builder
        numbers: set[int] = set()
        count = len(self.members)
        for position in range(1, int(builder.NbFaultyContours()) + 1):
            number = int(builder.FaultyContour(position))
            if 1 <= number <= count:
                numbers.add(number)
        if builder.NbFaultyVertices():
            around = NeighbourMap()
            TopExp.MapShapesAndAncestors_s(self.candidate.shape, TopAbs_VERTEX, TopAbs_EDGE, around)
            for position in range(1, int(builder.NbFaultyVertices()) + 1):
                vertex = builder.FaultyVertex(position)
                if not around.Contains(vertex):
                    continue
                touching = {
                    int(self.known.FindIndex(edge)) for edge in listed(around.FindFromKey(vertex))
                }
                numbers.update(
                    number for number, members in enumerate(self.members, 1) if members & touching
                )
        return self._of(numbers)

    def at_faces(self, shape: Any, faces: set[int]) -> frozenset[int]:
        """Die Konturen, deren Rundung an diesen Flächen des Ergebnisses liegt.

        ``faces`` zählt die Flächenkarte von ``shape`` (ab 1). Eine Fläche,
        die eine Kontur erzeugt hat — an einer ihrer Kanten oder an einer
        ihrer Ecken (``Generated``) —, gehört ihr. **Liegt eine der Flächen
        auf einer Rundung, zählen nur diese Konturen**; erst ohne eine solche
        gehört eine geänderte alte Fläche den Konturen, deren Rundungen an sie
        grenzen. Am goot-Lochbrett (senkrecht R 1) waren sechs Flächen offen,
        zwei davon Rundungen: Deren Konturen fallen weg, nicht dazu zwei
        Nachbarn der beschnittenen Wände.
        """
        from OCP.collections import (
            IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
        )
        from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
        from OCP.TopExp import TopExp, TopExp_Explorer
        from OCP.TopoDS import TopoDS

        if not faces:
            return frozenset()
        out = ShapeMap()
        TopExp.MapShapes_s(shape, TopAbs_FACE, out)
        made: dict[int, set[int]] = {}
        for number, members in enumerate(self.members, 1):
            for member in members:
                edge = TopoDS.Edge(self.known.FindKey(member))
                for source in (edge, TopExp.FirstVertex_s(edge), TopExp.LastVertex_s(edge)):
                    for face in listed(self.builder.Generated(source)):
                        index = int(out.FindIndex(face))
                        if index:
                            made.setdefault(index, set()).add(number)
        numbers: set[int] = set()
        for face in faces:
            numbers |= made.get(face, set())
        if numbers:
            return self._of(numbers)
        neighbours = NeighbourMap()
        TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, neighbours)
        for face in sorted(faces):
            explorer = TopExp_Explorer(out.FindKey(face), TopAbs_EDGE)
            while explorer.More():
                edge = explorer.Current()
                if neighbours.Contains(edge):
                    for other in listed(neighbours.FindFromKey(edge)):
                        numbers |= made.get(int(out.FindIndex(other)), set())
                explorer.Next()
        return self._of(numbers)


def _invalid_faces(shape: Any) -> set[int]:
    """Die Flächen der Form, die ``BRepCheck`` für sich allein ablehnt (Kartenzählung ab 1)."""
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp

    faces = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, faces)
    return {
        number
        for number in range(1, faces.Extent() + 1)
        if not BRepCheck_Analyzer(faces.FindKey(number)).IsValid()
    }


def _faces_at_free_edges(shape: Any) -> set[int]:
    """Die Flächen an freien oder falsch orientierten Kanten — leer bei geschlossener Schale.

    Dieselbe Frage wie :attr:`Solid.is_closed` (``CheckOrientedShells`` mit
    freien Kanten); eine Form ohne Schale ist nie geschlossen und hat hier
    keine Fläche, an der die Schuld läge — sie bekommt alle.
    """
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.ShapeAnalysis import ShapeAnalysis_Shell
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp, TopExp_Explorer

    faces = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, faces)
    checker = ShapeAnalysis_Shell()
    checker.LoadShells(shape)
    if not checker.NbLoaded():
        return set(range(1, faces.Extent() + 1))
    checker.CheckOrientedShells(shape, True)
    if not checker.HasFreeEdges() and not checker.HasBadEdges():
        return set()
    neighbours = NeighbourMap()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, neighbours)
    found: set[int] = set()
    for compound in (checker.FreeEdges(), checker.BadEdges()):
        if compound.IsNull():
            continue
        explorer = TopExp_Explorer(compound, TopAbs_EDGE)
        while explorer.More():
            edge = explorer.Current()
            if neighbours.Contains(edge):
                found.update(
                    int(faces.FindIndex(face)) for face in listed(neighbours.FindFromKey(edge))
                )
            explorer.Next()
    found.discard(0)
    return found or set(range(1, faces.Extent() + 1))


def _solid_count(shape: Any) -> int:
    """Wie viele Körper eine Form trägt — dieselbe Zählung wie :attr:`Solid.solid_count`."""
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp

    found = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_SOLID, found)
    return int(found.Extent())


def _open_faces(outcome: Solid) -> set[int]:
    """Die Flächen, an denen die Tessellierung nicht dicht ist — gezählt wie die Form davor.

    Eine Netzkante, die nicht genau zwei Dreiecke trennt, ist offen oder
    verzweigt. Ihre Dreiecke führen über die Flächenherkunft zur Fläche des
    Körpers und über dessen Kopierabbildung zur Fläche der Form, die der
    Builder gebaut hat (Kartenzählung ab 1). Ganze Zahlen, keine Geometrie —
    auf jeder Maschine dieselbe Antwort.
    """
    import numpy as np

    from app.core.brep.kernel import face_sources
    from app.core.geom.mesh import unique_edges

    raw = outcome.mesh.raw
    sources = face_sources(outcome.mesh)
    _unique, inverse, counts = unique_edges(
        np.asarray(raw.edges, dtype=np.int64), return_inverse=True, return_counts=True
    )
    owners = np.asarray(raw.edges_face, dtype=np.int64)[counts[inverse] != 2]
    copied = {int(face) for face in np.unique(sources[owners])} if len(sources) else set()
    back = {target: source for source, target in enumerate(outcome._copied_faces)}
    return {back[face] + 1 for face in copied if face in back}


def _build_constant_fillet(
    solid: Solid,
    chosen: Sequence[EdgeInfo],
    radius: float,
    *,
    cancelled: CancelToken | None = None,
) -> Solid:
    """Baut und prüft eine konstante Rundung auf einer frischen nativen Form."""
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet

    builder = BRepFilletAPI_MakeFillet(solid.shape)
    for entry in chosen:
        _check(cancelled)
        builder.Add(radius, entry.edge)
    return _built(solid, builder, "fillet", radius, len(chosen), cancelled=cancelled)


def _laid_along(builder: Any, chosen: Sequence[EdgeInfo], law: RadiusLaw) -> None:
    """Legt den Verlauf auf jede Kontur der gewählten Kanten — oder sagt, warum nicht.

    Vorher gefragt wird dasselbe wie am Netz (:func:`check_varying_radius`):
    Auf einem Ring müssen Anfang und Ende denselben Radius tragen, und zwei
    Konturen mit verschiedenen Radien an einer gemeinsamen Ecke haben keine
    Form. Die Ecke erkennt der Kern an ihrem Knoten; als Kennung dient seine
    Lage, auf ein Millionstel gerundet. Wo ein Ring anfängt, sucht
    :func:`_loop_start_on` an den Kurven selbst — derselbe Punkt, den das Netz
    an seinem Sehnenzug findet (``geom.edges.loop_start``).
    """
    from OCP.BRep import BRep_Tool
    from OCP.collections import Array1_gp_Pnt2d
    from OCP.gp import gp_Pnt2d

    for entry in chosen:
        if builder.Contour(entry.edge) == 0:
            builder.Add(entry.edge)
    ends: list[tuple[Any, Any, tuple[float, float]]] = []
    plans: list[tuple[int, list[_ContourPiece], LawOnChain]] = []
    for contour in range(1, builder.NbContours() + 1):
        start = BRep_Tool.Pnt_s(builder.FirstVertex(contour))
        stop = BRep_Tool.Pnt_s(builder.LastVertex(contour))
        first = (start.X(), start.Y(), start.Z())
        last = (stop.X(), stop.Y(), stop.Z())
        pieces = _contour_pieces(builder, contour)
        total = pieces[-1].high if pieces else 0.0
        first_key = tuple(round(value, 6) for value in first)
        if builder.Closed(contour):
            loop_start, forward = _loop_start_on(pieces)
            on_chain = LawOnChain(law.as_loop(), total, loop_start, forward, True)
            ends.append((first_key, first_key, (law.at(0.0), law.at(1.0))))
        else:
            on_chain = LawOnChain(law, total, 0.0, starts_at_first(first, last), False)
            last_key = tuple(round(value, 6) for value in last)
            ends.append((first_key, last_key, law_at_ends((first, last), law)))
        plans.append((contour, pieces, on_chain))
    check_varying_radius(ends, mixed_corner=False)
    for contour, pieces, on_chain in plans:
        # **Je Kante der Kontur ihr Stück** — ``SetRadius(UandR, IC, IinC)``
        # gilt nur der Kante ``IinC``. Mit einer Tabelle für die ganze Kette
        # an Kante 1 lief der Verlauf an einer Kette Gerade-Bogen-Gerade über
        # die erste Gerade allein, und der Rest blieb beim Endradius
        # (gemessen 23.09.2026: 2,17 statt 1,59 mm in der Mitte der Geraden).
        for number, piece in enumerate(pieces, start=1):
            pairs = samples_along(on_chain, piece.low, piece.high)
            table = Array1_gp_Pnt2d(1, len(pairs))
            for index, (share, radius) in enumerate(pairs, start=1):
                table.SetValue(index, gp_Pnt2d(share, radius))
            builder.SetRadius(table, contour, number)


@dataclass(frozen=True, slots=True)
class _ContourPiece:
    """Eine Kante einer Fillet-Kontur: ihre Kurve, und wo sie in der Kontur liegt.

    ``low``/``high`` sind Bogenlängen ab dem ersten Knoten der Kontur;
    ``along`` sagt, ob der Kurvenparameter in Konturrichtung wächst.
    """

    curve: Any
    first: float
    last: float
    along: bool
    low: float
    high: float


def _contour_pieces(builder: Any, contour: int) -> list[_ContourPiece]:
    """Die Kanten einer Kontur der Reihe nach, mit Bogenlänge und Richtung.

    Gelaufen wird vom ersten Knoten der Kontur von Kante zu Kante über den
    gemeinsamen Knoten; die Längen misst ``GCPnts_AbscissaPoint``. Auf einem
    Ring endet die letzte Kante wieder am ersten Knoten — ``Abscissa`` gäbe dort
    null statt der ganzen Länge.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.TopExp import TopExp

    current = builder.FirstVertex(contour)
    reached = 0.0
    pieces: list[_ContourPiece] = []
    for number in range(1, builder.NbEdges(contour) + 1):
        edge = builder.Edge(contour, number)
        head, tail = TopExp.FirstVertex_s(edge), TopExp.LastVertex_s(edge)
        along = head.IsSame(current)
        curve = BRepAdaptor_Curve(edge)
        first, last = curve.FirstParameter(), curve.LastParameter()
        length = float(GCPnts_AbscissaPoint.Length_s(curve, first, last))
        pieces.append(_ContourPiece(curve, first, last, along, reached, reached + length))
        reached += length
        current = tail if along else head
    return pieces


def _loop_start_on(pieces: Sequence[_ContourPiece]) -> tuple[float, bool]:
    """Wo ein Ring anfängt (Bogenlänge ab dem ersten Knoten) und ob die Kontur vorwärts läuft.

    Der Punkt kleinster Lage in :data:`~app.core.geom.edges.LOOP_START`, an den
    Kurven gesucht: je Kante abgetastet, am kleinsten Wert mit dem goldenen
    Schnitt verfeinert. Vorwärts heißt, dass die Tangente in Konturrichtung
    nach :func:`~app.core.geom.edges.points_forward` zeigt.
    """
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.gp import gp_Pnt, gp_Vec

    weight = LOOP_START
    norm = math.sqrt(sum(value * value for value in weight))

    def lying(piece: _ContourPiece, parameter: float) -> float:
        point = piece.curve.Value(parameter)
        return float(point.X() * weight[0] + point.Y() * weight[1] + point.Z() * weight[2]) / norm

    best: tuple[float, int, float] | None = None
    for number, piece in enumerate(pieces):
        count = 64
        parameters = [
            piece.first + (piece.last - piece.first) * index / count for index in range(count + 1)
        ]
        values = [lying(piece, parameter) for parameter in parameters]
        at = min(range(len(values)), key=values.__getitem__)
        low = parameters[max(at - 1, 0)]
        high = parameters[min(at + 1, count)]
        golden = (math.sqrt(5.0) - 1.0) / 2.0
        for _step in range(60):
            one = high - golden * (high - low)
            two = low + golden * (high - low)
            if lying(piece, one) <= lying(piece, two):
                high = two
            else:
                low = one
        parameter = (low + high) / 2.0
        value = lying(piece, parameter)
        if best is None or value < best[0] - EPS_GEOM * EPS_GEOM:
            best = (value, number, parameter)
    assert best is not None
    _value, number, parameter = best
    piece = pieces[number]
    if piece.along:
        into = float(GCPnts_AbscissaPoint.Length_s(piece.curve, piece.first, parameter))
    else:
        into = float(GCPnts_AbscissaPoint.Length_s(piece.curve, parameter, piece.last))
    point, tangent = gp_Pnt(), gp_Vec()
    piece.curve.D1(parameter, point, tangent)
    direction = (tangent.X(), tangent.Y(), tangent.Z())
    if not piece.along:
        direction = (-direction[0], -direction[1], -direction[2])
    total = pieces[-1].high
    return (piece.low + into) % total, points_forward(direction)


def chamfer(
    solid: Solid,
    distance: float,
    choice: EdgeChoice = "all",
    keys: Sequence[str] = (),
    *,
    selected_edges: Sequence[int] | None = None,
    rings_by_plane: bool = True,
    shape: ChamferShape | None = None,
    cancelled: CancelToken | None = None,
) -> Solid:
    """Bricht die gewählten Kanten im 45-Grad-Winkel — oder mit ``shape`` asymmetrisch.

    ``keys``, ``selected_edges``, ``rings_by_plane`` und ``cancelled`` wie bei
    :func:`fillet`:
    einzelne Kanten haben Vorrang vor der Gruppe, eine ausdrückliche Auswahl
    vor beidem.

    **Zwei Abstände oder Abstand und Winkel** (P6.2): Je Kante werden die
    beiden angrenzenden Flächen an ihrer Mitte gefragt, welche die
    Bezugsfläche ist und wie weit jede zurückweicht — dieselben Zeilen wie
    am Netz (``geom.edges.chamfer_reaches``) —, und ``BRepFilletAPI`` bekommt
    beide Abstände samt der Fläche, auf der der erste gilt.
    """
    require()
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer

    _check(cancelled)
    checked = None if selected_edges is None else solid.checked_edge_indices(selected_edges)
    working = replace(solid)
    chosen = _edges_for(working, choice, keys, checked, rings_by_plane=rings_by_plane)

    asymmetric = shape is not None and (shape.second is not None or shape.angle is not None)
    reaches: list[tuple[Any, float, float]] = []
    if asymmetric:
        for entry in chosen:
            _check(cancelled)
            (first_face, first_normal), (_second_face, second_normal) = _faces_at_edge(
                working, entry
            )
            one, two = chamfer_reaches(distance, shape, first_normal, second_normal)
            reaches.append((first_face, one, two))
    widest = max((max(one, two) for _face, one, two in reaches), default=distance)
    _fits_the_wall(working, widest, chosen, "chamfer", cancelled=cancelled)
    builder = BRepFilletAPI_MakeChamfer(working.shape)
    for index, entry in enumerate(chosen):
        _check(cancelled)
        if asymmetric:
            face, one, two = reaches[index]
            builder.Add(one, two, entry.edge, face)
        else:
            builder.Add(distance, entry.edge)
    return _built(working, builder, "chamfer", distance, len(chosen), cancelled=cancelled)


def _check(cancelled: CancelToken | None) -> None:
    """Fragt den Abbruch — ein Satz statt dreier Zeilen an jeder Stelle."""
    if cancelled is not None:
        cancelled.raise_if_cancelled()


def _faces_at_edge(solid: Solid, entry: EdgeInfo) -> list[tuple[Any, tuple[float, float, float]]]:
    """Die zwei Flächen an einer Kante mit ihrer nach außen zeigenden Normale an der Kantenmitte.

    Die Normale kommt aus der Fläche selbst (``BRepLProp_SLProps``) am
    Fußpunkt der Kantenmitte, mit der Orientierung der Fläche im Körper — an
    einer ebenen Fläche die Ebenennormale, an einer gekrümmten die an dieser
    Stelle.

    **Die Kantenmitte liegt auf der Kante** (:func:`_point_on_edge`), nicht im
    Linienschwerpunkt ``entry.middle``. Der liegt bei einem Kreis in dessen
    Mitte, und von dort auf einen Kegel oder Zylinder projiziert fand sich
    keine Normale: Jede obere Kante eines Zylinders wies eine Fase mit zwei
    Abständen mit „lassen sich nicht bestimmen" ab (P6.2, gemessen 23.09.2026).
    """
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    from app.core.brep.canonical import outward_normal

    neighbours = NeighbourMap()
    TopExp.MapShapesAndAncestors_s(solid.shape, TopAbs_EDGE, TopAbs_FACE, neighbours)
    if not neighbours.Contains(entry.edge):
        raise _chamfer_sides_unknown()
    on_edge, _tangent = _point_on_edge(entry)
    found: list[tuple[Any, tuple[float, float, float]]] = []
    for shape in neighbours.FindFromKey(entry.edge):
        face = TopoDS.Face(shape)
        if any(face.IsSame(known) for known, _normal in found):
            continue
        normal = outward_normal(face, on_edge)
        if normal is None:
            raise _chamfer_sides_unknown()
        found.append((face, normal))
    if len(found) != 2:
        raise _chamfer_sides_unknown()
    return found


def _point_on_edge(entry: EdgeInfo) -> tuple[Vec3, Vec3]:
    """Der Punkt in der Mitte des Kurvenparameters und die Richtung der Kante dort.

    An einer Strecke ist das ihre Mitte und ``entry.direction``; an einem
    Kreis ein Punkt auf ihm und seine Tangente — beides, was der
    Linienschwerpunkt nicht ist.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.gp import gp_Pnt, gp_Vec

    curve = BRepAdaptor_Curve(entry.edge)
    point = gp_Pnt()
    tangent = gp_Vec()
    curve.D1((curve.FirstParameter() + curve.LastParameter()) / 2.0, point, tangent)
    size = tangent.Magnitude()
    if size <= EPS_GEOM:
        raise _chamfer_sides_unknown()
    return (
        (point.X(), point.Y(), point.Z()),
        (tangent.X() / size, tangent.Y() / size, tangent.Z() / size),
    )


def edge_sides(solid: Solid, entry: EdgeInfo) -> EdgeSides:
    """Die zwei Flächen einer Kante, in der Folge, in der :func:`chamfer` sie fragt (P6.2).

    Die Normalen sind die aus :func:`_faces_at_edge` — dieselben, aus denen
    :func:`chamfer` Bezugsfläche und Rücknahmen bestimmt. Die Richtung in
    jede Fläche steht quer zur Kante in der Tangentialebene; welches der
    beiden Vorzeichen in die Fläche führt, entscheidet ein Punkt knapp daneben,
    den die Fläche selbst einordnet (``BRepClass_FaceClassifier``). Eine
    Regel über Außen- und Innenkante wäre eine zweite Rechnung derselben
    Frage und stimmte an einer gekrümmten Fläche nur ungefähr.
    """
    require()
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_OUT

    at, tangent = _point_on_edge(entry)
    # Knapp daneben heißt: weit unter jeder Fase, weit über der Toleranz der
    # Einordnung — ein Hundertstel der Kantenlänge, höchstens 0,05 mm.
    probe = min(0.05, max(entry.length / 100.0, 10.0 * EPS_GEOM))
    sides: list[EdgeSide] = []
    for face, normal in _faces_at_edge(solid, entry):
        across = (
            tangent[1] * normal[2] - tangent[2] * normal[1],
            tangent[2] * normal[0] - tangent[0] * normal[2],
            tangent[0] * normal[1] - tangent[1] * normal[0],
        )
        size = math.hypot(*across)
        if size <= EPS_GEOM:
            raise _chamfer_sides_unknown()
        towards = tuple(value / size for value in across)
        beside = gp_Pnt(*(at[axis] + probe * towards[axis] for axis in range(3)))
        if BRepClass_FaceClassifier(face, beside, probe / 10.0).State() == TopAbs_OUT:
            towards = tuple(-value for value in towards)
        sides.append(EdgeSide(normal=normal, towards=cast(Vec3, towards)))
    return EdgeSides(at=at, one=sides[0], two=sides[1])


def _chamfer_sides_unknown() -> GeometryError:
    """Eine Kante, an der sich die zwei Flächen einer Fase nicht bestimmen lassen."""
    return GeometryError(
        detail=_(
            "An dieser Kante lassen sich die beiden Flächen der Fase nicht bestimmen. "
            "Wählen Sie gleiche Breiten oder eine andere Kante."
        ),
        suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
    )


def _wall_not_proven() -> GeometryError:
    """Erzeugt die sichere Absage für eine unbelegte Wandmessung.

    **Nicht ``RETRY``, und aus demselben Grund, den ``_built`` unten
    aufschreibt.** *Erneut versuchen* ist im Fenster genau dann verdrahtet,
    solange ein gescheitertes Schreiben ansteht (``main_window.error_handlers``,
    Zweig ``_write_failure``; ``tests/test_ui.py`` führt ``retry`` deshalb in
    ``postponed``). Hier steht kein solches Schreiben an, der Rat käme also nur
    als Satz an — und er wäre auch dann falsch: Dieselbe Wandkarte über
    demselben Netz scheitert beim zweiten Anlauf genauso. Regel 17 wäre
    optisch erfüllt und in der Sache verletzt.

    Was bleibt, ist der Weg zurück in den Schritt: An einem Körper, dessen
    Wand sich nicht belegen lässt, gibt es keine Größe, die durchkommt — die
    Antwort ist ein anderer Schritt oder keiner, und *Eingabe korrigieren*
    öffnet genau ihn (``main_window._correct_after_error``). Damit gibt jede
    Absage dieser Datei denselben Rat, und der Kunde bekommt für „die
    Verrundung ist nicht entstanden" einen Knopf statt zwei verschiedene.
    """
    return GeometryError(
        detail=_("Die Wandstärke konnte für diese Kanten nicht sicher geprüft werden."),
        suggestions=(CORRECT_INPUT, CANCEL),
    )


def _thinnest_wall(
    solid: Solid, edges: Sequence[EdgeInfo], *, cancelled: CancelToken | None = None
) -> float:
    """Die dünnste belegte Wand an den Trägerflächen dieser Kanten (:func:`_edge_walls`)."""
    return min(_edge_walls(solid, [entry.edge for entry in edges], cancelled=cancelled))


def _edge_walls(
    solid: Solid, edges: Sequence[Any], *, cancelled: CancelToken | None = None
) -> list[float]:
    """Je Kante die dünnste belegte Wand ihrer Trägerflächen — eine Wandkarte für alle.

    Eine 3-mm-Grundplatte begrenzt keine senkrechte Rundung am massiven
    Aufbau. Auch ihre Stirnflächen berühren senkrechte Kanten nur am Ende;
    sie tragen die Kante nicht. Die Topologie entscheidet deshalb, welche
    Werte der unveränderten Wandkarte zur Auswahl gehören (§18.3).

    Der Schutz bleibt vor dem nativen Bau: Am 3-mm-Hohlkasten kann Radius 3
    die ganze Anwendung in ``MakeFillet::Build`` beenden. Seine dünnen
    Seitenwände tragen die oberen Kanten und bleiben vollständig geprüft.
    Jede beteiligte Fläche braucht dafür wenigstens eine endliche positive
    Wandprobe. Wo das Raster an einer schmalen Fläche keine liefert, misst
    derselbe Wandstrahl wie das Messwerkzeug ihre Dreiecksschwerpunkte.
    Ohne belegte Zuordnung und Wandprobe gibt es keine Freigabe.

    **Je Kante**, damit eine Gruppe eine Kante an einer dünnen Wand auslassen
    kann, statt ganz abzusagen (:func:`fillet_group`); die Karte und jede
    Fläche werden dabei einmal gemessen.
    """
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp

    from app.core.geom.measure import wall_thickness
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.maps import wall_thickness_map

    try:
        mesh = as_mesh_data(solid)
        _check(cancelled)
        measured = wall_thickness_map(mesh).values
        _check(cancelled)
        if len(measured) != solid.triangle_count:
            raise _wall_not_proven()
        neighbours = NeighbourMap()
        TopExp.MapShapesAndAncestors_s(solid.shape, TopAbs_EDGE, TopAbs_FACE, neighbours)
        per_face: dict[int, float] = {}

        def face_wall(face: int) -> float:
            """Die dünnste belegte Wand einer Fläche — einmal gemessen."""
            known_wall = per_face.get(face)
            if known_wall is not None:
                return known_wall
            _check(cancelled)
            indices = solid.triangles_of_face(face)
            known = [
                measured[index]
                for index in indices
                if math.isfinite(measured[index]) and measured[index] > 0.0
            ]
            if not known:
                for index in indices:
                    centre = cast(
                        Vec3, tuple(float(value) for value in mesh.raw.triangles_center[index])
                    )
                    inward = cast(
                        Vec3, tuple(-float(value) for value in mesh.raw.face_normals[index])
                    )
                    value = wall_thickness(mesh, centre, inward)
                    if value is not None and math.isfinite(value) and value > 0.0:
                        known.append(value)
            if not known:
                raise _wall_not_proven()
            per_face[face] = min(known)
            return per_face[face]

        walls: list[float] = []
        for edge in edges:
            if not neighbours.Contains(edge):
                raise _wall_not_proven()
            faces = sorted(
                {solid.face_index(face) for face in listed(neighbours.FindFromKey(edge))}
            )
            if not faces or faces[0] < 0:
                raise _wall_not_proven()
            walls.append(min(face_wall(face) for face in faces))
    except GeometryError, OperationCancelled:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # ohne Messung ist der native Aufruf nicht sicher
        raise _wall_not_proven() from problem
    if not walls:
        raise _wall_not_proven()
    return walls


def _fits_the_wall(
    solid: Solid,
    size: float,
    edges: Sequence[EdgeInfo],
    kind: str,
    *,
    cancelled: CancelToken | None = None,
) -> None:
    """Hält an, wo die Rundung dicker wäre als eine Wand ihrer Trägerflächen."""
    thinnest = _thinnest_wall(solid, edges, cancelled=cancelled)
    if size < thinnest:
        return
    raise GeometryError(
        detail=_too_large(kind),
        suggestions=(CORRECT_INPUT, CANCEL),
        values={"size_mm": round(size, 3), "edges": len(edges), "wall_mm": round(thinnest, 2)},
    )


def _too_large(kind: str) -> Any:
    """Der Satz zum gescheiterten Bau — in den Worten des Feldes, das ihn
    ausgelöst hat.

    Beide Wege endeten in „Der Radius ist für diese Kanten zu groß.", auch die
    Fase. Deren Feld heißt aber **Breite** (``distance``, Titel „Breite"), und
    einen Radius gibt es dort nirgends: Wer *Fase anbringen* mit der Vorgabe
    1,0 mm auf ein eingelesenes STEP-Teil anwendet, bekommt eine Absage über
    eine Größe, die in seinem Dialog nicht vorkommt, und sucht ein Feld, das es
    nicht gibt. Gemessen an ``build_tray_v3.step`` aus dem Kundenbestand:
    0,2 mm geht, 0,5 mm und darüber nicht — der Satz kommt also im Normalfall
    und nicht im Ausnahmefall.
    """
    # **Und der Satz nennt den Weg** (Übertrag der Durchsicht v0.4.1): Allein
    # stand er da wie ein Titel. Wo die Ursache die Berührlinien sind, ersetzt
    # ihn ``geom.edge_ops`` durch den Satz mit dem größten Maß, das passt.
    if kind == "chamfer":
        return _(
            "Die Breite ist für diese Kanten zu groß. Wählen Sie eine kleinere Breite "
            "oder weniger Kanten."
        )
    return _(
        "Der Radius ist für diese Kanten zu groß. Wählen Sie einen kleineren Radius "
        "oder weniger Kanten."
    )


def _built(
    solid: Solid,
    builder: Any,
    kind: str,
    size: float,
    edges: int,
    *,
    cancelled: CancelToken | None = None,
) -> Solid:
    """Führt den Builder aus und macht aus seinem Scheitern einen Satz, auf
    den jemand reagieren kann.
    """
    _check(cancelled)
    try:
        builder.Build()
        if not builder.IsDone():
            raise GeometryError(
                detail=_too_large(kind),
                # **Nicht die Vorgabe des Geometriefehlers.** Die heißt
                # „Reparieren und erneut versuchen" und „Stellen zeigen" — an
                # einem exakten Körper gibt es nichts zu reparieren, und
                # Stellen nennt dieser Fehler keine. Beide Handlungen haben
                # einen Handler, erscheinen also als Knopf, und beide täten
                # nichts: Regel 17 wäre optisch erfüllt und in der Sache
                # verletzt. Die Antwort auf einen zu großen Radius ist ein
                # kleinerer.
                suggestions=(CORRECT_INPUT, CANCEL),
                values={"size_mm": round(size, 3), "edges": edges},
            )
        shape = builder.Shape()
    except GeometryError:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # OpenCASCADE raises its own exception types
        raise GeometryError(
            detail=_too_large(kind),
            suggestions=(CORRECT_INPUT, CANCEL),
            values={"size_mm": round(size, 3), "edges": edges},
        ) from problem
    # **Gebaut heißt nicht heil.** Zwischen der Größe, die OpenCASCADE
    # ablehnt, und der, die es abstürzen lässt, liegt ein Bereich, in dem es
    # ein Ergebnis liefert und ``IsDone()`` meldet — und der Körper darin ist
    # kaputt: An Roberts Kasten trennte ein Radius von 2 mm die 3 mm dicke
    # Wand auf, aus einem Solid wurden zwei, und das Volumen wuchs um acht
    # Prozent. ``BRepCheck_Analyzer`` sagt es in Millisekunden; ohne diese
    # Zeile reist der kaputte Körper weiter, bis eine spätere Operation an ihm
    # scheitert oder der Drucker ihn nicht drucken kann.
    from OCP.BRepCheck import BRepCheck_Analyzer

    _check(cancelled)
    if not BRepCheck_Analyzer(shape).IsValid():
        raise GeometryError(
            detail=_too_large(kind),
            suggestions=(CORRECT_INPUT, CANCEL),
            values={"size_mm": round(size, 3), "edges": edges},
        )
    _check(cancelled)
    outcome = solid.replacing(shape, history=builder, cancelled=cancelled)
    _check(cancelled)
    if (
        outcome.solid_count != solid.solid_count
        or not outcome.is_closed
        or outcome.volume <= EPS_GEOM
    ):
        raise GeometryError(
            detail=_too_large(kind),
            suggestions=(CORRECT_INPUT, CANCEL),
            values={"size_mm": round(size, 3), "edges": edges},
        )
    _log.info("%s of %.2f mm on %d edge(s)", kind, size, edges)
    return outcome


def boolean(
    kind: Literal["union", "difference", "intersection"], parts: list[Solid], *, cut_slot: int = 0
) -> Solid:
    """Präzise Boolesche Ops: keine Tessellation, also keine
    Tessellations-Artefakte (§30).

    ``cut_slot`` gibt bei der Differenz den Flächen, die ein Werkzeug in den
    Körper schneidet — Wände und Böden —, diesen Slot, wie ``cut_slot`` am Netz
    (``geom.boolean``). Ohne ihn bleiben sie in Slot null.

    Eine Rückfallkette gibt es hier nicht, und das ist keine Auslassung — die
    Kette aus §17.2 existiert, weil Netze sich uneinig sind, was innen ist.
    Zwei B-Rep-Volumen sind das nicht, und wo das hier scheitert, ist die
    Antwort ein echter Fehler statt eines gröberen Versuchs.
    """
    require()
    if len(parts) < 2:
        raise ValueError("a boolean operation needs at least two bodies")
    shape = parts[0].shape
    slots = parts[0].face_slots
    for other in parts[1:]:
        shape, slots, _operation = _boolean_pair(kind, shape, slots, other, cut_slot=cut_slot)
    return Solid(shape, deflection=parts[0].deflection, face_slots=slots)


def fuse_solids(solid: Solid, *, cancelled: CancelToken | None = None) -> Solid:
    """Vereinigt die Volumenkörper einer Form, wenn sie sich berühren oder überlagern.

    Getrennte Teile bleiben als Compound erhalten. Die native Historie ordnet
    durchgereichte Flächen und ihre Filamentslots dem Ergebnis zu.
    """
    if solid.solid_count < 2:
        return solid
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCP.collections import List_TopoDS_Shape
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer

    solids = []
    explorer = TopExp_Explorer(solid.shape, TopAbs_SOLID)
    while explorer.More():
        solids.append(explorer.Current())
        explorer.Next()
    if len(solids) < 2:
        return solid

    arguments = List_TopoDS_Shape()
    arguments.Append(solids[0])
    tools = List_TopoDS_Shape()
    for part in solids[1:]:
        tools.Append(part)
    operation = BRepAlgoAPI_Fuse()
    operation.SetNonDestructive(True)
    operation.SetRunParallel(True)
    operation.SetToFillHistory(True)
    operation.SetArguments(arguments)
    operation.SetTools(tools)
    operation.Build()
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if not operation.IsDone():
        raise GeometryError(
            detail=BOOLEAN_GEOMETRY_UNSAFE_DETAIL,
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    result = solid.replacing(operation.Shape(), history=operation, cancelled=cancelled)
    if not result.is_closed or result.solid_count < 1 or result.volume <= EPS_GEOM:
        raise GeometryError(
            detail=BOOLEAN_GEOMETRY_UNSAFE_DETAIL,
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return result if result.solid_count < solid.solid_count else solid


def bore(
    solid: Solid,
    *,
    position: Vec3,
    axis: Literal["x", "y", "z"],
    diameter: float,
    depth: float = 0.0,
    anchor: Literal["mouth", "centre"] = "mouth",
) -> Solid:
    """Schneidet eine zylindrische Bohrung. Tiefe null bohrt ganz durch.

    Die Semantik ist wörtlich die von :func:`app.core.geom.prepare.drill` —
    dieselben Parameter bedeuten dasselbe, sonst wäre das Umschalten zwischen
    den Kernen (``MENU_TWINS``) kein Umschalten, sondern eine andere Bohrung.
    ``mouth`` ist, was jemand meint, der eine Fläche anklickt: dort fängt die
    Bohrung an und geht ins Material. Für eine durchgehende macht es keinen
    Unterschied.

    **Der Zylinder entsteht gleich an seiner Stelle**, über ``gp_Ax2``, statt
    stehend und dann gedreht. Eine Drehung um eine Achse, die nicht durch den
    Ursprung geht, ist zwei Bewegungen und eine Gelegenheit, sich um ein
    Vorzeichen zu irren; die Achse mitzugeben ist eine Zeile.

    **Die Toleranz gehört nicht hierher.** ``diameter`` ist das Maß, das
    geschnitten wird — was das Material frisst, rechnet
    :func:`app.core.geom.prepare.bore_diameter` einmal für beide Kerne aus.
    Zweimal gerechnet wäre sie zweimal drauf.
    """
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    index = {"x": 0, "y": 1, "z": 2}[axis]
    box = solid.bounds
    through = depth <= EPS_GEOM
    if through:
        # Lang genug, um von jeder Position aus in beide Richtungen
        # hinauszureichen — dieselbe Überlegung wie auf der Mesh-Seite, nur
        # ohne den Überlappungszuschlag: Zwei B-Rep-Volumen sind sich einig,
        # was innen ist, und eine bündige Fläche ist hier kein Sonderfall.
        span = box.size[index]
        length = span * 2.0 + abs(position[index] - box.centre[index]) * 2.0
        start = box.centre[index] - length / 2.0
    else:
        length = depth
        if anchor == "mouth":
            # Ins Material hinein, und das ist die Richtung, in der der Körper
            # liegt: Wer die Oberseite anklickt, bohrt nach unten. Der
            # Gleichstand — die Achsmitte, die Vorgabeposition — geht wie auf
            # der Mesh-Seite (``into_the_body``, ``>=``) nach unten; sonst
            # bohrt ein Umschalten zwischen create_box und create_brep_box in
            # die Gegenrichtung, und MENU_TWINS ist kein Umschalten mehr.
            into = -1.0 if position[index] >= box.centre[index] else 1.0
            start = position[index] if into > 0 else position[index] - length
        else:
            start = position[index] - length / 2.0

    origin = [position[0], position[1], position[2]]
    origin[index] = start
    direction = [0.0, 0.0, 0.0]
    direction[index] = 1.0

    frame = gp_Ax2(gp_Pnt(*origin), gp_Dir(*direction))
    cutter = Solid(BRepPrimAPI_MakeCylinder(frame, diameter / 2.0, length).Shape())
    return boolean("difference", [solid, cutter])


def bore_profile(solid: Solid, outline: list[Point2], frame: PlaneFrame) -> Solid:
    """Schneidet das gemeinsame Bohrungsprofil als exakten Rotationskörper."""
    return boolean("difference", [solid, revolved_bore_tool(outline, frame)])


def revolved_bore_tool(outline: list[Point2], frame: PlaneFrame) -> Solid:
    """Das gemeinsame radiale Bohrungsprofil als exakter Werkzeugkörper."""
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt

    wire = BRepBuilderAPI_MakePolygon()
    previous: Point2 | None = None
    # Der erste Punkt schließt sich über Close; doppelte Punkte entstehen
    # bei einer Aufweitung ohne geraden Abschnitt und bilden keine Kante.
    for radius, height in outline[:-1]:
        if (
            previous is not None
            and math.hypot(radius - previous[0], height - previous[1]) <= EPS_GEOM
        ):
            continue
        wire.Add(
            gp_Pnt(
                *(
                    frame.origin[i] + radius * frame.x_axis[i] + height * frame.normal[i]
                    for i in range(3)
                )
            )
        )
        previous = (radius, height)
    wire.Close()
    face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
    axis = gp_Ax1(gp_Pnt(*frame.origin), gp_Dir(*frame.normal))
    tool = BRepPrimAPI_MakeRevol(face, axis, math.tau)
    if not tool.IsDone():
        raise GeometryError(
            detail=_("Aus diesen Bohrungsmaßen entsteht kein geschlossener Schneidkörper."),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return Solid(tool.Shape())


def clipped_bore_tool(solid: Solid, planes: Sequence[SectionPlane]) -> Solid:
    """Begrenzt ein Bohrwerkzeug an den wirklichen Mündungs- und Bodenebenen."""
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeHalfSpace
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

    for plane in planes:
        origin = plane.origin
        normal = plane.normal
        face = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(*origin), gp_Dir(*normal))).Face()
        inside = gp_Pnt(*(origin[i] - normal[i] for i in range(3)))
        half = BRepPrimAPI_MakeHalfSpace(face, inside).Solid()
        builder = boolean_builder("intersection", solid.shape, half)
        builder.Build()
        if not builder.IsDone():
            raise GeometryError(
                detail=_("Das Bohrwerkzeug konnte nicht an seinem Rand begrenzt werden."),
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        solid = solid.replacing(builder.Shape(), history=builder)
    return solid


def collared(solid: Solid, mouths: Sequence[tuple[SectionPlane, float]]) -> Solid:
    """``solid`` mit einem Kragen über jeder ebenen Fläche, die in einer der
    Ebenen aus ``mouths`` liegt — deren Prisma um die Weite daneben entlang
    der Ebenennormale.

    Das exakte Gegenstück zu ``prepare_ops._past_the_mouths`` am Netz: Ein
    Hohlraum aus seinen Flächen (:func:`solid_from_faces`) endet bündig in der
    Oberfläche, und eine bündige Differenz lässt eine Haut stehen (§39). Die
    Ebenen sind die offenen Mündungen, ihre Normalen zeigen nach außen; was
    der Kragen dort einnimmt, liegt in der Luft und trägt nichts ab. Liegt
    keine Fläche in einer der Ebenen, bleibt ``solid``, wie es ist.
    """
    require()
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.gp import gp_Vec

    pieces = [solid]
    for face in solid.faces():
        adaptor = BRepAdaptor_Surface(face)
        if adaptor.GetType() != GeomAbs_Plane:
            continue
        surface = adaptor.Plane()
        where = surface.Location()
        facing = surface.Axis().Direction()
        normal = (facing.X(), facing.Y(), facing.Z())
        point = (where.X(), where.Y(), where.Z())
        for plane, distance in mouths:
            parallel = abs(sum(a * b for a, b in zip(normal, plane.normal, strict=True)))
            offset = sum(a * b for a, b in zip(point, plane.normal, strict=True)) - plane.position
            if parallel < _COLLAR_PARALLEL or abs(offset) > _COLLAR_OFF:
                continue
            shift = gp_Vec(*(value * distance for value in plane.normal))
            # Mit Kopie der Grundfläche: Die Fläche gehört ``solid`` (Eigentumsvertrag).
            prism = BRepPrimAPI_MakePrism(face, shift, True).Shape()
            pieces.append(Solid(prism, deflection=solid.deflection))
            break
    if len(pieces) == 1:
        return solid
    return unified(boolean("union", pieces))


#: Wie parallel eine Fläche zu einer Mündungsebene stehen muss, damit
#: :func:`collared` sie als deren Deckel nimmt — als Betrag des Kosinus der
#: Normalen. Ein Deckel aus :func:`solid_from_faces` liegt in der Ebene seines
#: Rings; die Ebene der Mündung ist am Netz-Zwilling gemessen.
_COLLAR_PARALLEL: Final = 0.999

#: Wie weit ein Deckel neben der Mündungsebene liegen darf (mm) — weit unter
#: dem Überstand, um den der Kragen reicht, weit über der Messung am Zwilling.
_COLLAR_OFF: Final = 0.005


def slot_bore(
    solid: Solid,
    *,
    position: Vec3,
    direction: Vec3,
    diameter: float,
    depth: float,
    length: float,
    angle_deg: float,
    overlap: float,
) -> Solid:
    """Zieht eine erkannte Bohrung zu einem Langloch — exakt, mit echten Bögen.

    Das Gegenstück zu :func:`app.core.geom.prepare.slot_bore`. Der Umriss ist
    derselbe, aufgezogen wird er als Prisma statt als abgetastetes Netz: Die
    beiden Enden bleiben Zylinderflächen, und der STEP-Export trägt sie mit.

    ``overlap`` ist die Zugabe auf den Durchmesser; sie hält die alte
    Bohrungswand von der neuen fern (§39) und kommt vom Aufrufer, damit beide
    Kerne dieselbe Zahl verwenden.
    """
    tool = _slot_tool(position, direction, diameter, depth, length, angle_deg, overlap)
    # Beim Nachziehen liegen die alten und neuen Flanken in derselben Ebene.
    # Ihre künstlichen Teilungsnähte gehören nicht zum Langlochmantel.
    return unified(boolean("difference", [solid, tool]))


def unified(solid: Solid) -> Solid:
    """Koplanare und gleichflächige Teilflächen zusammenlegen — Filamentgrenzen bleiben.

    Eine Boolesche hinterlässt an jeder Berührung eine Naht: Der Deckel eines
    Füllkörpers zerteilt die Platte, in der er liegt, in Ring und Scheibe, die
    Flanken eines nachgezogenen Langlochs die alten Flanken. Für die Erkennung
    ist das eine Fläche, und ``ShapeUpgrade_UnifySameDomain`` macht sie wieder
    zu einer; ``keep_filament_boundaries`` hält die Kanten zwischen
    verschiedenen Slots dabei fest. Bis zum 20.09.2026 tat das nur
    :func:`slot_bore`; eine mit :func:`fill_bore` geschlossene Bohrung ließ
    zehn Flächen an einer Platte, die sechs hat.
    """
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain

    joined = ShapeUpgrade_UnifySameDomain(solid.shape, True, True, False)
    keep_filament_boundaries(solid, joined)
    joined.Build()
    return solid.replacing(joined.Shape(), history=joined.History())


def _bore_unit(direction: Vec3, depth: float) -> Vec3:
    """Die Einheitsachse einer erkannten Bohrung — oder die Absage des Netz-Zwillings.

    Dieselbe Frage und derselbe Satz wie in :func:`app.core.geom.prepare.resize_bore`
    und :func:`~app.core.geom.prepare.slot_bore` (``bore_geometry_error``). Hier
    stand bis zum 29.09.2026 dreimal ein nacktes ``ValueError`` ohne
    Handlungsvorschlag (Regel 17), und eine Richtung oder Tiefe mit NaN kam an
    ``<= EPS_GEOM`` vorbei bis zu OpenCASCADE. ``math.hypot`` wie am Netz, statt
    einer Summe über ``** 2`` (``kern.md``: plattformgleich).
    """
    from app.core.geom.prepare import bore_geometry_error

    if not math.isfinite(depth) or depth <= EPS_GEOM:
        raise bore_geometry_error()
    span = math.hypot(float(direction[0]), float(direction[1]), float(direction[2]))
    if not math.isfinite(span) or span <= EPS_GEOM:
        raise bore_geometry_error()
    return (float(direction[0]) / span, float(direction[1]) / span, float(direction[2]) / span)


def _slot_tool(
    position: Vec3,
    direction: Vec3,
    diameter: float,
    depth: float,
    length: float,
    angle_deg: float,
    overlap: float,
) -> Solid:
    """Der vollständige Langlochumriss zum Schneiden und zum Wiederauffüllen.

    Der Winkel zählt im Rahmen des Netz-Zwillings (``prepare.slot_frame``).
    """
    from app.core.brep.profiles import extrude
    from app.core.geom.prepare import slot_frame, slot_profile, slot_travel

    unit = _bore_unit(direction, depth)
    frame = slot_frame(unit, position)
    floor = replace(
        frame,
        origin=cast(
            Vec3,
            tuple(float(position[i]) - frame.normal[i] * depth / 2.0 for i in range(3)),
        ),
    )
    return extrude(
        slot_profile(
            radius=(diameter + overlap) / 2.0,
            travel=slot_travel(diameter=diameter, length=length),
            angle_deg=angle_deg,
        ),
        depth,
        frame=floor,
    )


def resize_bore(
    solid: Solid,
    *,
    position: Vec3,
    direction: Vec3,
    previous_diameter: float,
    diameter: float,
    depth: float,
) -> Solid:
    """Ändert eine erkannte Bohrung und erhält den exakten Körper.

    Dieselbe Konstruktion wie beim Netz-Zwilling: Vergrößern trägt einen
    Zylinder ab, Verkleinern vereinigt einen Ring mit der vorhandenen Wand.
    Der Ring greift um ``EPS_GEOM`` ins Material, damit zwei Flächen nicht nur
    aufeinanderliegen. Das Ergebnismaß bleibt der innere Radius und damit
    exakt der gewählte Durchmesser.
    """
    if is_close(diameter, previous_diameter):
        return solid
    unit = _bore_unit(direction, depth)
    start: Vec3 = (
        float(position[0]) - unit[0] * depth / 2.0,
        float(position[1]) - unit[1] * depth / 2.0,
        float(position[2]) - unit[2] * depth / 2.0,
    )
    cutter = _oriented_cylinder(start, unit, diameter / 2.0, depth)
    if diameter > previous_diameter:
        return boolean("difference", [solid, cutter])

    outer = _oriented_cylinder(
        start,
        unit,
        previous_diameter / 2.0 + EPS_GEOM,
        depth,
    )
    ring = boolean("difference", [outer, cutter])
    return boolean("union", [solid, ring])


def fill_bore(
    solid: Solid,
    *,
    position: Vec3,
    direction: Vec3,
    diameter: float,
    depth: float,
    length: float = 0.0,
    angle_deg: float = 0.0,
    opening: tuple[Vec3, Vec3] | None = None,
    planes: Sequence[SectionPlane] = (),
    within: Solid | None = None,
) -> Solid:
    """Schließt eine erkannte Bohrung wieder — das Gegenstück zum Bohren.

    Ohne diesen Weg konnte am exakten Körper kein Merkmal die Stelle wechseln:
    Die alte Bohrung wäre stehen geblieben und die neue daneben entstanden.
    Der Netz-Kern löst das seit dem 03.09.2026 mit
    ``prepare_ops._closed_at``; hier ist die exakte Hälfte davon, damit
    zwischen den beiden Kernen kein Unterschied bleibt (Robert, 10.09.2026:
    „zwischen den beiden soll es keinen unterschied geben bei garnichts").

    **Der Füllkörper ist breiter als der Hohlraum und genauso lang.** Radial
    greift er um ``EPS_GEOM`` ins volle Material — dieselbe Bauart, mit der
    :func:`resize_bore` seinen Ring aufsetzt —, denn ``diameter`` ist am
    tessellierten Netz gemessen und ein Vieleck liegt innerhalb seines
    Umkreises. Axial bleibt er exakt: Die Mündungen liegen in ebenen Flächen,
    und die tesselliert OpenCASCADE ohne Sehnenfehler; eine Zugabe dort ließe
    einen Zapfen stehen, den beim exakten Körper nichts wieder abschneidet.

    **Und die Mündungen liegen nicht immer quer zur Achse.** ``planes`` sind
    die Ebenen der Randringe (``prepare_ops._bore_end_planes``, am
    Netz-Zwilling gemessen); gibt der Aufrufer sie, wird der Stopfen dort
    begrenzt statt an seinen Deckeln. An einer um 17,5° gekippten Bohrung
    durch eine 10-mm-Platte standen die Deckel sonst oben und unten bis
    1,8 mm über der Platte (22.09.2026) — ``depth`` ist dann die Achsspanne der
    Wand, und die reicht an der einen Seite der Ellipse über die Fläche.
    Wo die Ränder keine Ebenen hergeben, begrenzt ``within`` (die konvexe
    Hülle, wie am Netz ``prepare.shell``).
    """
    if length > diameter + EPS_GEOM:
        tool = _slot_tool(position, direction, diameter, depth, length, angle_deg, 2.0 * EPS_GEOM)
    else:
        tool = _centred_bore(position, direction, diameter, depth, EPS_GEOM)
    if planes:
        tool = clipped_bore_tool(tool, planes)
    elif within is not None:
        tool = boolean("intersection", [tool, within])
    if opening is not None:
        # Der Stopfen endet an der tatsächlichen Außenebene. Sonst wächst
        # beim Versetzen einer Randöffnung Material außerhalb des Bauteils.
        from app.core.sketch.planes import frame_of

        mouth, outward = opening
        frame = frame_of((-outward[0], -outward[1], -outward[2]), mouth)
        reach = solid.bounds.diagonal * 2.0
        matrix = cast(
            Transform,
            (
                *((frame.x_axis[i], frame.y_axis[i], frame.normal[i], mouth[i]) for i in range(3)),
                (0.0, 0.0, 0.0, 1.0),
            ),
        )
        envelope = transformed(box(reach * 2.0, reach * 2.0, reach), matrix)
        tool = boolean("intersection", [tool, envelope])
    return unified(boolean("union", [solid, tool]))


def cut_bore(
    solid: Solid,
    *,
    position: Vec3,
    direction: Vec3,
    diameter: float,
    depth: float,
) -> Solid:
    """Schneidet eine Bohrung an einer freien Achse, gemessen von ihrer Mitte.

    :func:`bore` nimmt eine der drei Hauptachsen und die **Mündung**; das ist
    die Sicht dessen, der eine Fläche anklickt. Hier ist die Sicht eines
    erkannten Merkmals: eine freie Achse, und die Mitte als Bezug — dieselben
    zwei Zahlen, die :func:`fill_bore` und :func:`resize_bore` lesen. Gebraucht
    wird das beim Versetzen: An der neuen Stelle gibt es noch keine Bohrung,
    also lässt sich dort auch keine ändern.
    """
    return boolean("difference", [solid, _centred_bore(position, direction, diameter, depth, 0.0)])


def _centred_bore(
    position: Vec3, direction: Vec3, diameter: float, depth: float, gain: float
) -> Solid:
    """Der Zylinder einer erkannten Bohrung: Mitte auf ``position``, Achse frei.

    ``gain`` weitet den Radius. Beim Füllen ist er nötig — ``diameter`` ist am
    tessellierten Netz gemessen, und ein Vieleck liegt innerhalb seines
    Umkreises —, beim Schneiden wäre er ein Maßfehler. In der Länge bleibt der
    Körper in beiden Fällen exakt: Die Mündungen liegen in ebenen Flächen, die
    OpenCASCADE ohne Sehnenfehler tesselliert, und eine Zugabe dort ließe beim
    Füllen einen Zapfen stehen, den am exakten Körper nichts wieder abschneidet.
    """
    require()
    unit = _bore_unit(direction, depth)
    start: Vec3 = (
        float(position[0]) - unit[0] * depth / 2.0,
        float(position[1]) - unit[1] * depth / 2.0,
        float(position[2]) - unit[2] * depth / 2.0,
    )
    return _oriented_cylinder(start, unit, diameter / 2.0 + gain, depth)


def _oriented_cylinder(origin: Vec3, direction: Vec3, radius: float, height: float) -> Solid:
    """Ein exakter Zylinder an freier Achse, gemeinsam für die Ringrechnung."""
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    frame = gp_Ax2(gp_Pnt(*origin), gp_Dir(*direction))
    return Solid(BRepPrimAPI_MakeCylinder(frame, radius, height).Shape())


@dataclass(frozen=True, slots=True)
class ConeExtent:
    """Die Enden eines nativen Kegelstumpfs: weit, schmal, und die Achse dazwischen."""

    wide_centre: Vec3
    wide_radius: float
    narrow_radius: float
    #: Einheitsvektor vom weiten zum schmalen Ende.
    direction: Vec3
    height: float
    half_angle: float


def cone_extent(solid: Solid, face_indices: Sequence[int]) -> ConeExtent | None:
    """Die Enden des Kegels, den diese nativen Flächen tragen — oder ``None``.

    Die Erkennung nennt am Kegel Durchmesser, Winkel, Achse und die Mitte
    des weiten Endes, nicht aber seine Höhe und den schmalen Radius. Beides
    steht im Parameterbereich der Fläche: Ein Punkt der Kegelfläche liegt bei
    ``Location + v·cos(w)·Achse`` mit dem Radius ``RefRadius + v·sin(w)`` (``w``
    der halbe Öffnungswinkel),
    und die Grenzen von ``v`` sind die beiden Enden. Mehrere Flächen desselben
    Kegels (ein Mantel in zwei Hälften) geben dieselben Enden.

    **Derselbe Kegel als B-Spline** (P2.3) nennt seine Enden über den
    belegten Träger (``canonical.ConeSurface``): Spitze, Achse in die Nappe
    und die axialen Abstände ``near`` und ``far`` der Flächengrenzen.
    """
    require()
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cone

    from app.core.brep.canonical import ConeSurface

    faces = solid.faces()
    ends: list[tuple[tuple[float, float, float], float]] = []
    half_angle = 0.0
    for index in face_indices:
        if index < 0 or index >= len(faces):
            return None
        adaptor = BRepAdaptor_Surface(faces[index])
        if adaptor.GetType() != GeomAbs_Cone:
            surface = solid.surface(index)
            if not isinstance(surface, ConeSurface):
                return None
            half_angle = math.degrees(surface.half_angle)
            slope = math.tan(surface.half_angle)
            for along in (surface.near, surface.far):
                ends.append(
                    (
                        (
                            surface.apex[0] + along * surface.axis[0],
                            surface.apex[1] + along * surface.axis[1],
                            surface.apex[2] + along * surface.axis[2],
                        ),
                        along * slope,
                    )
                )
            continue
        cone = adaptor.Cone()
        angle = float(cone.SemiAngle())
        radius = float(cone.RefRadius())
        axis = cone.Axis().Direction()
        location = cone.Location()
        half_angle = math.degrees(abs(angle))
        for v in (float(adaptor.FirstVParameter()), float(adaptor.LastVParameter())):
            along = v * math.cos(angle)
            ends.append(
                (
                    (
                        location.X() + along * axis.X(),
                        location.Y() + along * axis.Y(),
                        location.Z() + along * axis.Z(),
                    ),
                    abs(radius + v * math.sin(angle)),
                )
            )
    if not ends:
        return None
    ends.sort(key=lambda end: end[1])
    (narrow_centre, narrow_radius), (wide_centre, wide_radius) = ends[0], ends[-1]
    direction = tuple(narrow_centre[i] - wide_centre[i] for i in range(3))
    height = math.hypot(*direction)
    if height <= EPS_GEOM or wide_radius <= EPS_GEOM:
        return None
    return ConeExtent(
        wide_centre=wide_centre,
        wide_radius=wide_radius,
        narrow_radius=narrow_radius,
        direction=(direction[0] / height, direction[1] / height, direction[2] / height),
        height=height,
        half_angle=half_angle,
    )


def _oriented_cone(
    base: Vec3, direction: Vec3, base_radius: float, top_radius: float, height: float
) -> Solid:
    """Ein exakter Kegelstumpf an freier Achse — von ``base`` aus entlang ``direction``."""
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    frame = gp_Ax2(gp_Pnt(*base), gp_Dir(*direction))
    return Solid(BRepPrimAPI_MakeCone(frame, base_radius, top_radius, height).Shape())


def void_body(solid: Solid, face_indices: Sequence[int]) -> Solid | None:
    """Die Luft eines Einschlusses als exakter Körper — aus seinen Schalen, ohne die Inseln.

    Ein Einschluss hat keinen Randring: Seine Flächen sind ganze Schalen des
    Körpers — die Innenschale, die ihn begrenzt, und die Außenschalen der
    Materialinseln darin. Jede vollständig gewählte Schale wird als private
    Kopie zum Körper geschlossen (dieselbe Bauart wie in
    ``features._void_features``); die Luft ist die größte davon ohne die
    übrigen, so wie die Erkennung ihr Volumen nennt. Beim Versetzen nimmt
    dieser Körper die Insel mit: Geschnitten wird die Luft **um** sie herum.
    ``None``, wenn keine Schale ganz gewählt ist oder eine nicht schließt.
    """
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy, BRepBuilderAPI_MakeSolid
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepLib import BRepLib
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_FACE, TopAbs_SHELL
    from OCP.TopExp import TopExp, TopExp_Explorer
    from OCP.TopoDS import TopoDS

    faces = solid.faces()
    chosen = {int(index) for index in face_indices}
    if not chosen or min(chosen) < 0 or max(chosen) >= len(faces):
        return None
    numbered = ShapeMap()
    for face in faces:
        numbered.Add(face)
    bodies: list[Solid] = []
    shells = TopExp_Explorer(solid.shape, TopAbs_SHELL)
    while shells.More():
        shell = TopoDS.Shell(shells.Current())
        shells.Next()
        members = ShapeMap()
        TopExp.MapShapes_s(shell, TopAbs_FACE, members)
        owned = {numbered.FindIndex(members.FindKey(i)) - 1 for i in range(1, members.Extent() + 1)}
        if not owned or not owned <= chosen:
            continue
        copied = BRepBuilderAPI_Copy(shell, True, False).Shape()
        maker = BRepBuilderAPI_MakeSolid(TopoDS.Shell(copied))
        if not maker.IsDone():
            return None
        body = maker.Solid()
        if not BRepLib.OrientClosedSolid_s(body) or not BRepCheck_Analyzer(body).IsValid():
            return None
        bodies.append(Solid(body))
    if not bodies:
        return None
    bodies.sort(key=lambda body: body.volume, reverse=True)
    air = bodies[0]
    if len(bodies) > 1:
        air = boolean("difference", [air, *bodies[1:]])
    return air if air.volume > EPS_GEOM else None


def convex_hull(solid: Solid) -> Solid:
    """Die konvexe Hülle des Körpers als exakter Vielflächner — zum Beschneiden eines Stopfens.

    Der exakte Kern kennt keine Hülle; sie kommt aus dem Netz-Zwilling
    (``trimesh``) und wird aus dessen Dreiecken genäht, ebene Nachbarn legt
    ``unified`` zusammen — die Hülle eines Quaders ist sein Quader. Gebraucht
    wird sie, wo ``geom.prepare.plug`` sie braucht: Ein Stopfen aus Zahlen darf
    nicht aus dem Körper herauswachsen, den er füllt, und ohne Merkmal gibt es
    keine Mündung, an der sich schneiden ließe.
    """
    require()
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakePolygon,
        BRepBuilderAPI_MakeSolid,
        BRepBuilderAPI_Sewing,
    )
    from OCP.BRepLib import BRepLib
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    hull = solid.to_mesh().raw.convex_hull
    sewing = BRepBuilderAPI_Sewing(EPS_GEOM)
    for corners in hull.triangles:
        polygon = BRepBuilderAPI_MakePolygon(
            gp_Pnt(float(corners[0][0]), float(corners[0][1]), float(corners[0][2])),
            gp_Pnt(float(corners[1][0]), float(corners[1][1]), float(corners[1][2])),
            gp_Pnt(float(corners[2][0]), float(corners[2][1]), float(corners[2][2])),
            True,
        )
        sewing.Add(BRepBuilderAPI_MakeFace(polygon.Wire(), True).Face())
    sewing.Perform()
    shells = TopExp_Explorer(sewing.SewedShape(), TopAbs_SHELL)
    if not shells.More() or sewing.NbFreeEdges() != 0:
        raise InternalError(detail="the convex hull of a solid did not sew into a closed shell")
    body = BRepBuilderAPI_MakeSolid(TopoDS.Shell(shells.Current())).Solid()
    BRepLib.OrientClosedSolid_s(body)
    return unified(Solid(body))


def solid_from_faces(
    solid: Solid,
    face_indices: Sequence[int],
    *,
    allowed_rings: tuple[int, ...] = (1, 2),
    fan_caps: bool = False,
    cancelled: CancelToken | None = None,
) -> Solid | None:
    """Der Körper, den diese nativen Flächen einnehmen — an ebenen Randringen geschlossen.

    Das exakte Gegenstück zu ``geom.prepare_ops._body_from_faces``: Die
    gewählten Flächen (der Mantel eines Zapfens, die Kuppe, der Mantel eines
    Kegelstumpfs) werden an ihren Randkanten zu Drähten verbunden, jeder
    geschlossene Ring bekommt einen **ebenen** Deckel, und Flächen samt
    Deckeln werden zu einer Schale genäht und zum Körper geschlossen. Ein
    Zapfen hat zwei Ringe (oben und am Fuß), eine Kuppe einen; wie viele
    erlaubt sind, sagt der Aufrufer, denn ein zweiter Ring bedeutet je nach
    Geometrie etwas anderes (siehe dort). ``None``, wenn ein Ring nicht in
    einer Ebene liegt, die Schale nicht schließt oder der Körper ungültig
    bleibt — dann wird nichts geraten.

    Die Originalflächen werden nicht angefasst: genäht werden private
    Kopien (``BRepBuilderAPI_Copy``), wie es der Eigentumsvertrag verlangt.

    ``fan_caps`` schließt einen Ring, der **nicht** in einer Ebene liegt, mit
    der Fläche um ihn, über das Loch fortgesetzt (:func:`_continued_cap`,
    RM-248): auf dem Träger der Nachbarfläche, wo der Ring in einer liegt, sonst
    als Füllung mit Stützpunkten auf der gemessenen Fläche. Wo keine glatte
    Fläche um den Ring steht oder das Nähen damit nicht hält, bleibt es beim
    Fächer — der Regelfläche vom Mittelpunkt an jede Kante (:func:`_fan_cap`).
    Dasselbe tut der Netzkern an einer Mündung in einer gekrümmten Fläche
    (``prepare_ops._body_from_faces``, ``curved_rims``) — dort mit Dreiecken,
    hier mit den echten Randkurven. Das braucht nur ein Stopfen, der einen
    Hohlraum füllt; ob der Ring dafür eben genug ist, entscheidet der Aufrufer.
    """
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy, BRepBuilderAPI_MakeFace
    from OCP.collections import HSequence_TopoDS_Shape
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp, TopExp_Explorer
    from OCP.TopoDS import TopoDS

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    faces = solid.faces()
    chosen = sorted({int(index) for index in face_indices})
    if not chosen or chosen[0] < 0 or chosen[-1] >= len(faces):
        return None
    numbered = ShapeMap()
    for face in faces:
        numbered.Add(face)
    neighbours = NeighbourMap()
    TopExp.MapShapesAndAncestors_s(solid.shape, TopAbs_EDGE, TopAbs_FACE, neighbours)
    wanted = set(chosen)
    seen = ShapeMap()
    rim = HSequence_TopoDS_Shape()
    for index in chosen:
        walk = TopExp_Explorer(faces[index], TopAbs_EDGE)
        while walk.More():
            edge = walk.Current()
            walk.Next()
            if seen.Contains(edge):
                continue
            seen.Add(edge)
            owners = {
                numbered.FindIndex(other) - 1 for other in listed(neighbours.FindFromKey(edge))
            }
            if owners - wanted:
                rim.Append(edge)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    wires = ShapeAnalysis_FreeBounds.ConnectEdgesToWires_s(rim, EPS_GEOM, False)
    if wires.Length() not in allowed_rings:
        return None
    planar: list[Any] = []
    curved: list[Any] = []
    for position in range(1, wires.Length() + 1):
        wire = TopoDS.Wire(wires.Value(position))
        if not wire.Closed():
            return None
        cap = BRepBuilderAPI_MakeFace(wire, True)
        if cap.IsDone():
            planar.append(cap.Face())
        elif fan_caps:
            curved.append(wire)
        else:
            return None
    # **Erst die Fläche um den Rand, fortgesetzt; sonst der Fächer** (RM-248).
    # Hält die fortgesetzte Fläche beim Nähen nicht — eine Füllung trifft ihre
    # Randkanten nur auf ihre Genauigkeit —, gilt der Fächer wie bisher.
    continued = [_continued_cap(wire, wanted, faces, numbered, neighbours) for wire in curved]
    attempts = [continued] if any(entry is not None for entry in continued) else []
    attempts.append([None] * len(curved))
    for caps in attempts:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        pieces = list(planar)
        for wire, cap_faces in zip(curved, caps, strict=True):
            fan = cap_faces if cap_faces is not None else _fan_cap(wire)
            if fan is None:
                return None
            pieces.extend(fan)
        built = _sewn_body(
            [BRepBuilderAPI_Copy(faces[index], True, False).Shape() for index in chosen], pieces
        )
        if built is not None:
            return built
    return None


def _sewn_body(copies: list[Any], caps: list[Any]) -> Solid | None:
    """Flächen und Deckel zu einem geschlossenen, gültigen Körper genäht — oder ``None``."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Sewing
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepLib import BRepLib
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    sewing = BRepBuilderAPI_Sewing(EPS_GEOM)
    for shape in (*copies, *caps):
        sewing.Add(shape)
    sewing.Perform()
    if sewing.NbFreeEdges() != 0:
        return None
    sewn = sewing.SewedShape()
    shells = TopExp_Explorer(sewn, TopAbs_SHELL)
    if not shells.More():
        return None
    # ``Closed()`` ist ein Flag, das Sewing nicht setzt — an einer Kuppe stand
    # es auf falsch bei null freien Kanten und gültigem Körper (gemessen
    # 20.09.2026). Geschlossen ist, was keine freie Kante hat.
    shell = TopoDS.Shell(shells.Current())
    shells.Next()
    if shells.More():
        return None
    maker = BRepBuilderAPI_MakeSolid(shell)
    if not maker.IsDone():
        return None
    body = maker.Solid()
    if not BRepLib.OrientClosedSolid_s(body) or not BRepCheck_Analyzer(body).IsValid():
        return None
    built = Solid(body)
    if built.volume <= EPS_GEOM:
        return None
    return built


def _continued_cap(
    wire: Any, chosen: set[int], faces: list[Any], numbered: Any, neighbours: Any
) -> list[Any] | None:
    """Der Deckel eines gekrümmten Rands als Fortsetzung der Fläche um ihn — oder ``None``.

    **Liegt der Rand ganz in einer Fläche, ist ihr Träger der Deckel**: eine
    Fläche auf demselben Träger, begrenzt vom Randdraht (:func:`_cap_on_carrier`).
    Ein Zylinder, eine Kugel, eine Ebene laufen unter dem Loch weiter, und eine
    Spline-Fläche, deren Loch ein innerer Draht ist, ebenso. An der Platte mit
    einer Unterseite im Zylinder R 40 blieb unter der Zylindersenkung mit dem
    Fächer eine Mulde von 4,0 mm³ — mit dem Träger 0,0000.

    **Sonst eine Füllung**: der Randdraht als Grenze, Stützpunkte auf der
    Fläche, die um den Rand gemessen und eingepasst wurde (``mouth_cap``, an
    einer feinen Vernetzung der Flächen um den Rand — :func:`_faces_near` —,
    damit die Stützpunkte auf der exakten Fläche liegen und nicht auf ihren
    Sehnen). Wo die Nachbarschaft keine glatte Fläche ist — die
    Mündungsrundung der Lochplatte gs-100 —, ``None``, und es bleibt beim
    Fächer.
    """
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    edges: list[Any] = []
    owners: set[int] = set()
    walk = TopExp_Explorer(wire, TopAbs_EDGE)
    while walk.More():
        edge = walk.Current()
        walk.Next()
        edges.append(edge)
        owners |= {
            numbered.FindIndex(other) - 1 for other in listed(neighbours.FindFromKey(edge))
        } - chosen
    if not owners:
        return None
    if len(owners) == 1:
        carried = _cap_on_carrier(faces[next(iter(owners))], edges, wire)
        if carried is not None:
            return [carried]
    return _filled_cap(wire, _faces_near(wire, faces, chosen))


def _faces_near(wire: Any, faces: list[Any], chosen: set[int]) -> list[Any]:
    """Die Flächen um den Randdraht, so weit die Anpassung tastet — ohne die des Hohlraums.

    **Dieselbe Nachbarschaft, die der Netzkern sieht** (``mouth_cap.MOUTH_REACH``
    des Radius um den Rand), nicht nur die Flächen, an denen der Rand liegt: An
    der Lochplatte ``pegboard-gs-100-v2.step`` sind das vier Spline-Flächen
    einer Mündungsrundung, ein Band von 1,7 mm um die Zylindersenkung, und ein
    Polynom über dieses Band allein, über das ganze Loch fortgesetzt, lief als
    Trichter hinein: Versetzen um 1 mm fehlten 7,8 statt 4,1 mm³ (Durchsicht 0.5.1).
    Mit dem Zylinder dahinter findet die Anpassung dort keine glatte Fläche,
    genau wie am Netz, und es bleibt beim Fächer.

    Genommen wird jede Fläche, deren Hüllquader den Würfel um den Rand trifft;
    was davon zu steil ist oder weiter weg liegt, sortiert die Anpassung selbst
    aus (``mouth_cap._facet_heights``).
    """
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    from app.core.geom.mouth_cap import MOUTH_REACH

    points = _wire_points(wire)
    if len(points) < 3:
        return []
    centre = exact_centre(points)
    radius = max(math.dist(point, centre) for point in points)
    reach = radius * (1.0 + MOUTH_REACH)
    around = Bnd_Box()
    around.Update(
        centre[0] - reach,
        centre[1] - reach,
        centre[2] - reach,
        centre[0] + reach,
        centre[1] + reach,
        centre[2] + reach,
    )
    near: list[Any] = []
    for index, face in enumerate(faces):
        if index in chosen:
            continue
        bounds = Bnd_Box()
        BRepBndLib.Add_s(face, bounds, False)
        if not bounds.IsOut(around):
            near.append(face)
    return near


def _cap_on_carrier(neighbour: Any, edges: list[Any], wire: Any) -> Any | None:
    """Eine Fläche auf dem Träger von ``neighbour``, begrenzt vom Loch, das diese
    Fläche um ``edges`` trägt — oder ``None``, wenn das Ergebnis nicht trägt.

    Der Loch-Draht der Nachbarfläche umgekehrt ist der Rand des Deckels: Seine
    Kanten tragen ihre Parameterkurven auf genau diesem Träger schon, und das
    Nähen trifft sie ohne Toleranz. Welche Richtung die beschränkte Seite ist,
    sagt die Fläche selbst — die umschlossene ist endlich und etwa so groß wie
    die Öffnung, die andere unendlich oder der ganze Rest einer Kugel.
    """
    from OCP.BRep import BRep_Builder, BRep_Tool
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS, TopoDS_Face

    hole = None
    walk = TopExp_Explorer(neighbour, TopAbs_WIRE)
    while walk.More() and hole is None:
        candidate = TopoDS.Wire(walk.Current())
        walk.Next()
        members: list[Any] = []
        inner = TopExp_Explorer(candidate, TopAbs_EDGE)
        while inner.More():
            members.append(inner.Current())
            inner.Next()
        if len(members) == len(edges) and all(
            any(member.IsSame(edge) for edge in edges) for member in members
        ):
            hole = candidate
    if hole is None:
        return None
    opening = _opening_area(wire)
    location = TopLoc_Location()
    carrier = BRep_Tool.Surface_s(neighbour, location)
    builder = BRep_Builder()
    for bound in (hole.Reversed(), hole):
        cap = TopoDS_Face()
        builder.MakeFace(cap, carrier, location, BRep_Tool.Tolerance_s(neighbour))
        builder.Add(cap, bound)
        cap.Orientation(neighbour.Orientation())
        if not BRepCheck_Analyzer(cap).IsValid():
            continue
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(cap, props)
        area = float(props.Mass())
        if math.isfinite(area) and 0.0 < area <= _CAP_AREA_LIMIT * opening:
            return cap
    return None


#: Wie viel größer als die Öffnung ein Deckel auf dem Träger höchstens sein
#: darf. Eine gekrümmte Fläche über einem Loch ist etwas größer als seine
#: Projektion; die andere Seite des Randdrahts ist unendlich oder der ganze Rest
#: einer geschlossenen Fläche — beides um ein Vielfaches mehr.
_CAP_AREA_LIMIT: Final = 4.0


def _opening_area(wire: Any) -> float:
    """Die Fläche, die der Randdraht in seiner Ausgleichsebene umschließt."""
    from app.core.units import plane_axes, plane_fit, ring_area

    points = _wire_points(wire)
    if len(points) < 3:
        return 0.0
    centre, normal, _spread = plane_fit(points)
    axes = plane_axes(normal)
    if axes is None:
        return 0.0
    first, second = axes
    flat = [
        (
            sum((point[k] - centre[k]) * first[k] for k in range(3)),
            sum((point[k] - centre[k]) * second[k] for k in range(3)),
        )
        for point in points
    ]
    return ring_area(flat)


def _wire_points(wire: Any) -> list[Vec3]:
    """Punkte entlang des Drahts in seiner Laufrichtung — je Kante :data:`_FAN_SAMPLES`."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.TopAbs import TopAbs_REVERSED

    points: list[Vec3] = []
    walk = BRepTools_WireExplorer(wire)
    while walk.More():
        edge = walk.Current()
        walk.Next()
        curve = BRepAdaptor_Curve(edge)
        first, last = curve.FirstParameter(), curve.LastParameter()
        if edge.Orientation() == TopAbs_REVERSED:
            first, last = last, first
        for step in range(_FAN_SAMPLES):
            point = curve.Value(first + (last - first) * step / _FAN_SAMPLES)
            points.append((point.X(), point.Y(), point.Z()))
    return points


def _filled_cap(wire: Any, neighbours: list[Any]) -> list[Any] | None:
    """Eine Füllung über dem Randdraht, gestützt auf die Fläche um ihn — oder ``None``.

    ``neighbours`` sind die Flächen um den Rand (:func:`_faces_near`).
    """
    import numpy as np
    from OCP.BRep import BRep_Builder
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeFilling
    from OCP.GeomAbs import GeomAbs_C0
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS, TopoDS_Compound

    from app.core.brep.kernel import tessellate
    from app.core.geom import mouth_cap
    from app.core.units import MAX_FACET_SAG

    rim = _wire_points(wire)
    if len(rim) < 3:
        return None
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    for face in neighbours:
        builder.Add(compound, face)
    # Fein genug, dass die Facetten auf der exakten Fläche liegen: ein Zehntel
    # der Facettengrenze, mit der der Zwilling vernetzt ist.
    fine = tessellate(compound, deflection=MAX_FACET_SAG / 10.0)
    surface = mouth_cap.mouth_surface(fine, np.zeros(0, dtype=np.int64), np.asarray(rim))
    if surface is None:
        return None
    filling = BRepOffsetAPI_MakeFilling()
    walk = TopExp_Explorer(wire, TopAbs_EDGE)
    while walk.More():
        filling.Add(TopoDS.Edge(walk.Current()), GeomAbs_C0)
        walk.Next()
    for x, y, z in mouth_cap.support_points(surface).tolist():
        filling.Add(gp_Pnt(x, y, z))
    filling.Build()
    if not filling.IsDone():
        return None
    face = TopoDS.Face(filling.Shape())
    if not BRepCheck_Analyzer(face).IsValid():
        return None
    return [face]


def _fan_cap(wire: Any) -> list[Any] | None:
    """Die Flächen eines Fächers über einem nicht ebenen Ring — oder ``None``.

    Der Mittelpunkt ist der der abgetasteten Randpunkte, in Grundrechenarten
    (``units.exact_centre``, RM-187), wie am Netz. Je Randkante entsteht die
    Regelfläche von diesem Punkt an die Kante (``BRepOffsetAPI_ThruSections``
    zwischen einem Punkt und dem Ring): Ihr Rand ist die Kante selbst, und das
    Nähen schließt sie an die Fläche, zu der die Kante gehört.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    points: list[Vec3] = []
    walk = TopExp_Explorer(wire, TopAbs_EDGE)
    while walk.More():
        curve = BRepAdaptor_Curve(TopoDS.Edge(walk.Current()))
        walk.Next()
        first, last = curve.FirstParameter(), curve.LastParameter()
        for step in range(_FAN_SAMPLES):
            point = curve.Value(first + (last - first) * step / _FAN_SAMPLES)
            points.append((point.X(), point.Y(), point.Z()))
    if len(points) < 3:
        return None
    hub = exact_centre(points)
    builder = BRepOffsetAPI_ThruSections(False, True)
    builder.AddVertex(BRepBuilderAPI_MakeVertex(gp_Pnt(*hub)).Vertex())
    builder.AddWire(wire)
    builder.Build()
    if not builder.IsDone():
        return None
    pieces = []
    faces = TopExp_Explorer(builder.Shape(), TopAbs_FACE)
    while faces.More():
        pieces.append(faces.Current())
        faces.Next()
    return pieces or None


#: Wie viele Punkte je Randkante den Mittelpunkt eines Fächers bestimmen
#: (:func:`_fan_cap`). Gleichmäßig im Parameter, damit er nicht von der
#: Tessellierung abhängt.
_FAN_SAMPLES = 16


def transformed(solid: Solid, matrix: Transform, *, cancelled: CancelToken | None = None) -> Solid:
    """Transformiert den exakten Körper; die Variante daneben führt Flächen mit."""
    return transformed_with_faces(solid, matrix, cancelled=cancelled)[0]


#: Bis wohin eine Matrix als Rundungsrauschen einer Ähnlichkeit gilt, relativ
#: zum Quadrat ihres Maßstabs. Eine Drehung aus mehreren Schritten trägt mehr
#: als die 64 eps einer einzelnen; eine gewollte Scherung dieser Größe
#: verschöbe an einem Meter einen Mikrometer.
_SIMILARITY_NOISE: Final = 1e-9


def _nearest_similarity(linear: Any, scale: float, *, mirrored: bool) -> Any:
    """Die Ähnlichkeit, deren Rauschen ``linear`` ist — Gram-Schmidt in Grundrechenarten.

    Ohne Zerlegung über LAPACK, damit die Lage auf jeder Plattform dieselbe
    bleibt (RM-187). Ein Maßstab, der nur im Rauschen von eins abweicht, ist
    eins: sonst baute OCCT die Flächen neu, statt die Form nur zu legen.
    """
    import numpy as np

    def unit(vector: tuple[float, float, float]) -> tuple[float, float, float]:
        length = math.hypot(*vector)
        return (vector[0] / length, vector[1] / length, vector[2] / length)

    first = unit((float(linear[0, 0]), float(linear[1, 0]), float(linear[2, 0])))
    column = (float(linear[0, 1]), float(linear[1, 1]), float(linear[2, 1]))
    along = first[0] * column[0] + first[1] * column[1] + first[2] * column[2]
    second = unit(
        (column[0] - along * first[0], column[1] - along * first[1], column[2] - along * first[2])
    )
    sign = -1.0 if mirrored else 1.0
    third = (
        sign * (first[1] * second[2] - first[2] * second[1]),
        sign * (first[2] * second[0] - first[0] * second[2]),
        sign * (first[0] * second[1] - first[1] * second[0]),
    )
    if abs(scale - 1.0) <= _SIMILARITY_NOISE:
        scale = 1.0
    return np.array(
        [[scale * first[row], scale * second[row], scale * third[row]] for row in range(3)],
        dtype=np.float64,
    )


def _invalid_transform(*, result: bool = False) -> GeometryError:
    """Nennt ungültige Eingaben und nicht belegbare native Ergebnisse getrennt."""
    return GeometryError(
        detail=_(
            "Der exakte Körper lässt sich mit dieser Änderung nicht gültig erhalten. "
            "Verkleinern Sie die Änderung oder wählen Sie eine andere Ausgangsform."
        )
        if result
        else _(
            "Diese Transformation ist nicht endlich und umkehrbar. "
            "Prüfen Sie Maßstab und Richtung der Änderung."
        ),
        suggestions=(CORRECT_INPUT, CANCEL),
    )


def transformed_with_faces(
    solid: Solid, matrix: Transform, *, cancelled: CancelToken | None = None
) -> tuple[Solid, tuple[int, ...]]:
    """Affine Geometrie und belegte Zuordnung alter zu final besessenen Flächen.

    ``gp_Trsf.SetValues`` orthogonalisiert seine Eingabe. Nur eine Ähnlichkeit
    darf deshalb diesen Weg nehmen; Scherung und anisotroper Maßstab verwenden
    ``gp_GTrsf``. Die Flächenkarte wird durch beide Builder und die abschließende
    Solid-Kopie verkettet, nie aus deren Besuchsreihenfolge geraten.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    require()
    import numpy as np
    from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform, BRepBuilderAPI_Transform
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.gp import gp_GTrsf, gp_Mat, gp_Trsf, gp_XYZ
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp

    from app.core.brep.properties import INTEGRAL_RELATIVE_ERROR

    try:
        values = np.asarray(matrix, dtype=np.float64)
    except (TypeError, ValueError) as problem:
        raise _invalid_transform() from problem
    # Nur Rundungsrauschen der 4x4-Matrix, keine Längen-/Fertigungstoleranz.
    roundoff = 64.0 * np.finfo(np.float64).eps
    if (
        values.shape != (4, 4)
        or not np.isfinite(values).all()
        or not np.allclose(values[3], (0.0, 0.0, 0.0, 1.0), atol=roundoff, rtol=0.0)
    ):
        raise _invalid_transform()
    linear = values[:3, :3]
    singular_values = np.linalg.svd(linear, compute_uv=False)
    determinant = float(np.linalg.det(linear))
    if (
        singular_values[-1] <= singular_values[0] * roundoff
        or not math.isfinite(determinant)
        or abs(determinant) <= 0.0
    ):
        raise _invalid_transform()
    if np.allclose(values, np.eye(4), atol=roundoff, rtol=0.0):
        return solid, tuple(range(len(solid._copied_faces)))
    try:
        gram = linear.T @ linear
        squared_scale = float(np.trace(gram) / 3.0)
        deviation = float(np.abs(gram - np.eye(3) * squared_scale).max())
        similarity = bool(deviation <= roundoff * squared_scale)
        if not similarity and deviation <= _SIMILARITY_NOISE * squared_scale:
            # Rauschen einer Drehung, keine Scherung: auf die Ähnlichkeit
            # legen, sonst nähme sie den Weg über GTransform und wäre keine
            # starre Bewegung mehr (RM-407, 175,7° an carpet-corner-clip.step).
            values = values.copy()
            values[:3, :3] = linear = _nearest_similarity(
                linear, math.sqrt(squared_scale), mirrored=determinant < 0.0
            )
            determinant = float(np.linalg.det(linear))
            similarity = True
        rigid = similarity and math.isclose(determinant, 1.0, rel_tol=roundoff, abs_tol=0.0)
        # Ein Flächenmodell ohne geschlossenes Volumen ist kein Grund, es nicht
        # zu bewegen (RM-407, ``surfaces.step``): Die starre Bewegung belegt
        # sich über die Partnerschaft und erbt die Gültigkeit ihrer Eingabe.
        closed = solid.solid_count >= 1 and solid.is_closed
        if not rigid and not BRepCheck_Analyzer(solid.shape).IsValid():
            raise _invalid_transform(result=True)
        builder: Any
        # Wessen Form der Builder bekommt, und welche Fläche dieser Form zu
        # welcher Fläche des Eingangs gehört: ohne Kopie dieselbe Nummer, mit
        # Kopie deren belegte Abbildung (``_copied_faces``).
        owner, owned_faces = solid, tuple(range(len(solid._copied_faces)))
        if similarity:
            transform = gp_Trsf()
            transform.SetValues(*(float(value) for value in values[:3].flat))
            builder = BRepBuilderAPI_Transform(owner.shape, transform, False)
        else:
            # **Auf einer privaten Kopie**: ``BRepBuilderAPI_GTransform`` setzt
            # trotz ``Copy=True`` das Prüfkennzeichen von Kanten seiner Eingabe
            # zurück (NURBS-Platte mit Bohrung, Scherung: vier Unterformen,
            # gemessen 22.09.2026) — und die Eingabe gehört Szene und Cache.
            # Die Kopie ist ein ``Solid``, damit sie die Filamente mitführt.
            owner = replace(solid)
            owned_faces = owner._copied_faces
            general = gp_GTrsf(
                gp_Mat(*(float(value) for value in linear.flat)),
                gp_XYZ(*(float(value) for value in values[:3, 3])),
            )
            builder = BRepBuilderAPI_GTransform(owner.shape, general, True)
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if not builder.IsDone() or builder.Shape().IsNull():
            raise _invalid_transform(result=True)
        shape = builder.Shape()
        # **Eine starre Bewegung bewegt dieselbe Form, sie baut keine neue.**
        # Ohne Maßstab und Spiegelung ändert der Builder nur die Lage
        # (``Copy=False``), und der Beleg dafür ist die Partnerschaft der
        # Formen: dieselbe Topologie und Geometrie, anders gelegt. Damit steht
        # das Volumen fest, ohne ein Integral — das stand hier bis zum
        # 21.09.2026 zweimal je Bewegung und kostete an einem Gewinde 27 s für
        # ein Verschieben um drei Millimeter (Review,
        # ``edit.moved(m6_rechts.step)``). Maßstab, Spiegelung und die
        # allgemeine affine Abbildung bauen die Flächen neu — eine Lage trägt
        # keinen Maßstab —, und dort belegt das Integral gegen die Determinante
        # weiterhin, dass nichts verloren ging.
        if rigid and not shape.IsPartner(solid.shape):
            raise _invalid_transform(result=True)
        if not rigid and not BRepCheck_Analyzer(shape).IsValid():
            raise _invalid_transform(result=True)
        result = owner.replacing(shape, history=builder, cancelled=cancelled)
        if result.solid_count != solid.solid_count or result.is_closed != solid.is_closed:
            raise _invalid_transform(result=True)
        # Ohne Volumen belegt die Fläche den Maßstab; eine allgemeine affine
        # Abbildung eines Flächenmodells hat keinen festen Flächenfaktor, dort
        # tragen Gültigkeit und die vollständige Flächenzuordnung unten.
        measure = "volume" if closed else "surface" if similarity else None
        if not rigid and measure is not None:
            factor = abs(determinant) if closed else squared_scale
            expected = solid._properties(measure, cancelled=cancelled).mass * factor
            if (
                expected <= 0.0
                or not math.isfinite(expected)
                or not math.isclose(
                    result._properties(measure, cancelled=cancelled).mass,
                    expected,
                    rel_tol=2.0 * INTEGRAL_RELATIVE_ERROR,
                    abs_tol=0.0,
                )
            ):
                raise _invalid_transform(result=True)
        source_faces, target_faces = ShapeMap(), ShapeMap()
        TopExp.MapShapes_s(owner.shape, TopAbs_FACE, source_faces)
        TopExp.MapShapes_s(shape, TopAbs_FACE, target_faces)
        mapping = []
        for index in range(len(owned_faces)):
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            # ModifiedShape verkettet bei GTransform auch die NURBS-Konvertierung.
            # Modified liefert in OCCT 8 bei diesem Builder eine leere Liste.
            changed = builder.ModifiedShape(source_faces.FindKey(owned_faces[index] + 1))
            target = int(target_faces.FindIndex(changed)) - 1
            if target < 0 or target >= len(result._copied_faces):
                raise _invalid_transform(result=True)
            mapping.append(result._copied_faces[target])
        if sorted(mapping) != list(range(target_faces.Extent())):
            raise _invalid_transform(result=True)
        # **Eine Verschiebung verschiebt auch den Hüllquader.** Gemessen kostet
        # er an ``build_tray_v3.step`` 0,47 s, und der erste, der ihn nach
        # dem Verschieben fragt, ist das Fenster (Review 22.09.2026). Bei
        # Drehung und Maßstab ist die achsparallele Hülle eine andere — dort
        # misst der Körper selbst, beim ersten Fragen.
        known = solid._cache.get("bounds")
        if known is not None and np.allclose(linear, np.eye(3), atol=roundoff, rtol=0.0):
            dx, dy, dz = (float(value) for value in values[:3, 3])
            low, high = known.minimum, known.maximum
            result._cache["bounds"] = BoundingBox(
                (low[0] + dx, low[1] + dy, low[2] + dz),
                (high[0] + dx, high[1] + dy, high[2] + dz),
            )
        return result, tuple(mapping)
    except OperationCancelled:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except GeometryError:
        raise
    except Exception as problem:
        raise _invalid_transform(result=True) from problem


def moved(solid: Solid, offset: Vec3) -> Solid:
    """Verschiebt über denselben geprüften Transformationsvertrag."""
    return transformed(
        solid,
        (
            (1.0, 0.0, 0.0, offset[0]),
            (0.0, 1.0, 0.0, offset[1]),
            (0.0, 0.0, 1.0, offset[2]),
            (0.0, 0.0, 0.0, 1.0),
        ),
    )


def unround(
    solid: Solid,
    centre: Vec3,
    radius: float,
    *,
    selected_faces: Sequence[int] | None = None,
    cancelled: CancelToken | None = None,
) -> Solid:
    """Nimmt eine Verrundung weg und stellt die scharfe Kante her (§30).

    Über ``BRepAlgoAPI_Defeaturing`` und nicht über einen Füllkörper: Der
    Kern kennt die Rundungsfläche als Ding und weiß, welche Nachbarn sie
    verlängern muss. Gemessen an einem Quader mit vier Rundungen zu R = 3:
    23884,115 mm³ nach dem Wegnehmen einer, analytisch 23845,487 + 1,9314·20 —
    dieselbe Zahl auf vier Stellen, in 18 ms.

    Ohne ausdrückliche Auswahl wird die Fläche wie bisher über Lage und
    Radius gesucht. ``selected_faces`` benennt dagegen genau eine vollständige
    aktuelle Zylinderfläche mit diesem Radius. Ihr Index gehört ausschließlich
    zum Eingabe-Solid und wird durch dessen private Kopie nachgeführt (§21.2).
    Eine leere, mehrteilige oder unpassende Auswahl löst keine Ersatzsuche aus.
    """
    return _unround(solid, centre, radius, selected_faces, cancelled)[0]


def _unround(
    solid: Solid,
    centre: Vec3,
    radius: float,
    selected_faces: Sequence[int] | None,
    cancelled: CancelToken | None,
) -> tuple[Solid, int | None]:
    """Nimmt die Rundung weg und belegt, welche Kante an ihre Stelle tritt.

    Der zweite Wert ist der Index der neuen scharfen Kante in
    ``result.edges()`` — oder ``None``, wenn die Builder-Historie ihn nicht
    eindeutig hergibt (:func:`_sharp_edge_after`). Der Radiuswechsel verrundet
    genau diese Kante; er sucht nicht die nächste an der alten Mitte.
    """
    require()
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Defeaturing

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    indices = (
        None
        if selected_faces is None
        else solid.checked_face_indices(selected_faces, cancelled=cancelled)
    )
    if indices is not None and len(indices) != 1:
        raise GeometryError(
            detail=_(
                "Wählen Sie genau eine vollständige Rundungsfläche mit dem bisherigen Radius."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    working = replace(solid)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if indices is None:
        # Gesucht wird am Eingang, dessen Träger das Memo schon kennt (der
        # Radiuswechsel hat sie eben erst gelesen), und die Arbeitskopie
        # übernimmt die Fläche über ihre belegte Abbildung — nicht über eine
        # zweite Suche auf kaltem Cache.
        found = _cylinder_at(solid, centre, radius, cancelled=cancelled)
        face = (
            None
            if found is None
            else working.faces()[working._copied_faces[solid.face_index(found)]]
        )
    else:
        source_index = indices[0]
        face = working.faces()[working._copied_faces[source_index]]
        surface = solid.surface(source_index, cancelled=cancelled)
        if not isinstance(surface, CylinderSurface) or not is_close(
            float(surface.cylinder.Radius()), radius
        ):
            raise GeometryError(
                detail=_(
                    "Wählen Sie genau eine vollständige Rundungsfläche mit dem bisherigen Radius."
                ),
                suggestions=(CORRECT_INPUT, CANCEL),
            )
    if face is None:
        raise GeometryError(
            detail=_(
                "An dieser Stelle ist keine Rundung mehr — ein Schritt davor hat den "
                "Körper verändert. Wählen Sie sie neu."
            ),
            values={"radius_mm": round(radius, 3)},
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    builder = BRepAlgoAPI_Defeaturing()
    builder.SetShape(working.shape)
    builder.AddFaceToRemove(face)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    builder.Build()
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if not builder.IsDone():
        raise GeometryError(
            detail=_(
                "Diese Rundung lässt sich nicht wegnehmen — die Nachbarflächen "
                "treffen sich danach nicht. Nehmen Sie sie zusammen mit den "
                "angrenzenden weg, oder verrunden Sie stattdessen neu."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    result = working.replacing(builder.Shape(), history=builder, cancelled=cancelled)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    sharp = _sharp_edge_after(working, face, builder, result, cancelled=cancelled)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    return result, sharp


def _sharp_edge_after(
    working: Solid, face: Any, builder: Any, result: Solid, *, cancelled: CancelToken | None
) -> int | None:
    """Die Kante, die an die Stelle der entfernten Rundung tritt — belegt über
    die Builder-Historie, oder ``None``.

    Der Beleg (gemessen am 20.09.2026 an vier gleichen Rundungen R3): Die
    Rundung grenzt an ihre zwei **Wände** quer zur Achse und an Deckel und
    Boden. ``Modified(Wand)`` nennt je Wand genau eine verlängerte Fläche,
    und diese beiden teilen sich im Ergebnis **genau eine** Kante — die
    scharfe. Deckel und Boden gehören nicht dazu; über alle vier Nachbarn
    ist der Schnitt leer. Die nächste Kante zur alten Mitte traf dort
    zufällig dieselbe; sie ist kein Beleg.

    Ohne genau zwei ebene Wände quer zur Achse — eine Rundung zwischen Ebene
    und Zylindermantel — oder mit einer anderen Zahl gemeinsamer Kanten gibt
    es keinen Beleg, und der Aufrufer sagt das, statt zu raten (Regel 21).
    Welche Wand quer zur Achse steht, entscheidet dieselbe Grenze wie am
    Netz (``units.UPRIGHT_TO_AXIS``).
    """
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    from app.core.brep.canonical import PlaneSurface
    from app.core.units import UPRIGHT_TO_AXIS

    surface = working.surface(working.face_index(face), cancelled=cancelled)
    if not isinstance(surface, CylinderSurface):
        return None
    direction = surface.cylinder.Axis().Direction()
    axis = (float(direction.X()), float(direction.Y()), float(direction.Z()))
    neighbours = NeighbourMap()
    TopExp.MapShapesAndAncestors_s(working.shape, TopAbs_EDGE, TopAbs_FACE, neighbours)
    walls: list[Any] = []
    rim = ShapeMap()
    TopExp.MapShapes_s(face, TopAbs_EDGE, rim)
    for index in range(1, rim.Extent() + 1):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        shared = neighbours.FindIndex(rim.FindKey(index))
        if shared == 0:
            continue
        for raw in listed(neighbours.FindFromIndex(shared)):
            if raw.IsSame(face) or any(raw.IsSame(wall) for wall in walls):
                continue
            # Die Nachbarkarte gibt nackte Formen zurück; der Träger will die
            # echte Fläche — dieselbe Falle wie in ``Solid._explore``. Ihre
            # Nummer kennt der Körper, und damit ihr Memo.
            number = working.face_index(raw)
            if number < 0:
                continue
            other = TopoDS.Face(raw)
            plane = working.surface(number, cancelled=cancelled)
            if not isinstance(plane, PlaneSurface):
                continue
            normal = plane.normal
            across = abs(normal[0] * axis[0] + normal[1] * axis[1] + normal[2] * axis[2])
            if across <= UPRIGHT_TO_AXIS:
                walls.append(other)
    if len(walls) != 2:
        return None
    built_edges = ShapeMap()
    TopExp.MapShapes_s(builder.Shape(), TopAbs_EDGE, built_edges)
    common: set[int] | None = None
    for wall in walls:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        edges: set[int] = set()
        for modified in listed(builder.Modified(wall)):
            owned = ShapeMap()
            TopExp.MapShapes_s(modified, TopAbs_EDGE, owned)
            edges.update(
                int(built_edges.FindIndex(owned.FindKey(number))) - 1
                for number in range(1, owned.Extent() + 1)
            )
        common = edges if common is None else common & edges
    if not common or len(common) != 1:
        return None
    # Vom Index in der Builder-Form zum Index im Ergebnis: ``replacing`` hat
    # die Form kopiert, und die Kopie führt ihre Kanten über ``_copied_edges``.
    (built,) = common
    if built < 0 or built >= len(result._copied_edges):
        return None
    return result._copied_edges[built]


def _cylinder_at(
    solid: Solid, centre: Vec3, radius: float, *, cancelled: CancelToken | None = None
) -> Any | None:
    """Die Zylinderfläche dieses Radius an dieser Stelle — oder ``None``."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.gp import gp_Pnt

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    probe = BRepBuilderAPI_MakeVertex(gp_Pnt(*centre)).Vertex()
    best: Any | None = None
    closest = math.inf
    for index, face in enumerate(solid.faces()):
        surface = solid.surface(index, cancelled=cancelled)
        if not isinstance(surface, CylinderSurface):
            continue
        cylinder = surface.cylinder
        # Der Radius kommt aus derselben exakten Topologie. Ein relatives
        # Fenster verwechselte die nahe Außenwand einer dünnen C-Klemme mit
        # ihrer Innenwand, weil deren Fläche dem Schwerpunkt näher liegt.
        if not is_close(float(cylinder.Radius()), radius):
            continue
        # Die begrenzte Fläche unterscheidet auch zwei Rundungen auf derselben
        # Achse. Weder die unendliche Achse noch ihr beliebiger Ursprung tun das.
        away = nearest_distance(probe, face)
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if away is None:
            return None
        if away < closest:
            best, closest = face, away
    return best


def reround(
    solid: Solid,
    centre: Vec3,
    radius: float,
    wanted: float,
    *,
    selected_faces: Sequence[int] | None = None,
    cancelled: CancelToken | None = None,
) -> Solid:
    """Ändert den Radius einer Verrundung, ohne den Ausgabevertrag zu ändern."""
    result, _triangles = _reround(
        solid,
        centre,
        radius,
        wanted,
        selected_faces=selected_faces,
        cancelled=cancelled,
        collect_triangles=False,
    )
    return result


def reround_with_created_triangles(
    solid: Solid,
    centre: Vec3,
    radius: float,
    wanted: float,
    *,
    selected_faces: Sequence[int] | None = None,
    cancelled: CancelToken | None = None,
) -> tuple[Solid, tuple[int, ...]]:
    """Gibt neben dem Körper die Dreiecke der belegten neuen Rundungsfläche zurück.

    Im normalen Weg kommt der Herkunftsnachweis aus der vom Builder erzeugten
    Fläche der scharfen Kante. Beim radialen Weg wird der eindeutige Zylinder
    mit Sollradius und gleicher Achse auf der versetzten Haut verfolgt; die
    Belege aus ``Modified`` und ``Generated`` ordnen ihn den Ergebnisdreiecken
    zu. Fehlt ein eindeutiger Flächenbeleg, bleiben die Dreiecke leer.
    """
    return _reround(
        solid,
        centre,
        radius,
        wanted,
        selected_faces=selected_faces,
        cancelled=cancelled,
        collect_triangles=True,
    )


def _reround(
    solid: Solid,
    centre: Vec3,
    radius: float,
    wanted: float,
    *,
    selected_faces: Sequence[int] | None,
    cancelled: CancelToken | None,
    collect_triangles: bool,
) -> tuple[Solid, tuple[int, ...]]:
    """Ändert den Radius einer Verrundung — wegnehmen, neu verrunden.

    Dieselbe Zweiteilung wie am Netz (``geom.edges.reround``), und aus
    demselben Grund: Dazwischen liegt die scharfe Kante, und die ist der
    Zustand, an dem beide Hälften prüfbar sind.

    Beide Übergänge sind belegt, keiner geraten: ``selected_faces`` benennt
    die Rundungsfläche am aktuellen Eigentümer (wie bei :func:`unround`),
    und die neue scharfe Kante kommt aus der Builder-Historie der beiden
    Wände (:func:`_sharp_edge_after`), ohne gerundeten Schlüssel dazwischen.
    Gibt die Historie keine eindeutige Kante her, sagt der Weg es mit
    demselben Satz wie der Netzweg — statt die nächste Kante an der alten
    Mitte zu nehmen, die bei zwei nahen Rundungen die falsche wäre.
    Ohne ausdrückliche Auswahl bleibt der ältere Suchmodus über Lage und
    Radius bestehen.
    """
    from app.core.errors import CHANGE_SELECTION
    from app.core.geom.edges import NOT_BETWEEN_TWO_PLANES

    if collect_triangles:
        radial, triangles = radial_rounding_with_created_triangles(
            solid, centre, radius, wanted, selected_faces=selected_faces, cancelled=cancelled
        )
    else:
        radial = radial_rounding(
            solid, centre, radius, wanted, selected_faces=selected_faces, cancelled=cancelled
        )
        triangles = ()
    if radial is not None:
        return radial, triangles
    sharp, edge = _unround(solid, centre, radius, selected_faces, cancelled)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if edge is None:
        raise GeometryError(detail=NOT_BETWEEN_TWO_PLANES, suggestions=(CHANGE_SELECTION, CANCEL))
    if collect_triangles:
        checked = sharp.checked_edge_indices((edge,))
        working = replace(sharp)
        chosen = _edges_at(working, [working._copied_edges[index] for index in checked])
        _fits_the_wall(working, wanted, chosen, "fillet", cancelled=cancelled)
        from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet

        builder = BRepFilletAPI_MakeFillet(working.shape)
        for entry in chosen:
            _check(cancelled)
            builder.Add(wanted, entry.edge)
        result = _built(working, builder, "fillet", wanted, len(chosen), cancelled=cancelled)
        triangles = _generated_triangles(result, builder, chosen[0].edge, cancelled=cancelled)
    else:
        result = fillet(sharp, wanted, selected_edges=(edge,), cancelled=cancelled)
        triangles = ()
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    return result, triangles


def _generated_triangles(
    result: Solid, builder: Any, source_edge: Any, *, cancelled: CancelToken | None
) -> tuple[int, ...]:
    """Ordnet vom Builder erzeugte Flächen der Tessellation des Ergebnisses zu."""
    return _triangles_for_shapes(
        result,
        builder,
        listed(builder.Generated(source_edge)),
        cancelled=cancelled,
    )


def _boolean_pair(
    kind: Literal["union", "difference", "intersection"],
    shape: Any,
    slots: tuple[int, ...],
    other: Solid,
    *,
    cut_slot: int = 0,
    cancelled: CancelToken | None = None,
) -> tuple[Any, tuple[int, ...], Any]:
    """Baut einen Booleschen Schritt und gibt Form, Filamentslots und Historie zurück."""
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    operation = boolean_builder(kind, shape, other.shape)
    operation.Build()
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if not operation.IsDone():
        # Nicht „fehlgeschlagen" (Regel 17) oder die geerbten Vorschläge:
        # Mesh-Reparatur und offene Kanten gibt es für einen B-Rep-Körper
        # nicht. Bei bloßer Berührung behebt Bewegung die Ursache.
        raise _boolean_refused()
    result = operation.Shape()
    if not _holds(result, shape):
        operation, result = _fuzzy_retry(kind, shape, other.shape, cancelled)
    sources = [(shape, slots)]
    if kind != "difference":
        sources.append((other.shape, other.face_slots))
    elif cut_slot:
        sources.append((other.shape, (cut_slot,) * other.face_count))
    updated_slots = carried_face_slots(result, sources, history=operation, cancelled=cancelled)
    return result, updated_slots, operation


#: Warum eine exakte Boolesche nicht gebaut wurde und was hilft (RM-385): Der
#: häufigste Grund ist bloße Berührung an einer Fläche oder Kante, und die
#: behebt eine Bewegung, keine Reparatur. Bis ``eab5f4f47`` stand dieser Satz
#: da; der allgemeine „ließ sich nicht zuverlässig berechnen" nannte weder
#: Grund noch Weg (§2.7).
BOOLEAN_REFUSED_DETAIL: Final = _(
    "Die gewählte Bearbeitung funktioniert mit diesen Körpern in ihrer jetzigen Lage nicht — "
    "meist berühren sie sich nur an einer Fläche oder Kante. Verschieben Sie einen der beiden "
    "so weit, dass sich die Körper wirklich überlappen."
)


#: Mit welcher Unschärfe eine Boolesche noch einmal rechnet, deren Ergebnis
#: nicht gültig ist (RM-408). OpenCASCADE meldet ``IsDone`` auch für einen
#: Körper mit einer zweiten Schale, wo zwei Flächen fast zusammenfallen — an
#: einer Lochplatte aus STEP trug eine Bohrung Ø 5 neben einer Senkbohrung so
#: einen ungültigen Körper mit 670 mm³ mehr Netzvolumen weiter. Die Stufen
#: liegen über der Fertigungsgenauigkeit üblicher STEP-Dateien (bis 1e-5 mm)
#: und weit unter allem, was ein Drucker zeigt.
BOOLEAN_FUZZ: Final = (EPS_GEOM * 10.0, EPS_GEOM * 100.0)


def _shells(shape: Any) -> int:
    """Wie viele Schalen eine Form trägt."""
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer

    count = 0
    walk = TopExp_Explorer(shape, TopAbs_SHELL)
    while walk.More():
        count += 1
        walk.Next()
    return count


def _holds(result: Any, source: Any) -> bool:
    """Ob ein Boolesches Ergebnis gültig ist — geprüft, wo es verdächtig ist.

    Die volle Prüfung (``BRepCheck_Analyzer``) kostet an großen Körpern
    spürbar; sie läuft, wo das Ergebnis mehr Schalen trägt als der Körper
    davor. Genau dort lag der kaputte Fall: eine zweite Schale, die kein
    Hohlraum war (RM-408). Ein echter innerer Hohlraum besteht die Prüfung.
    """
    if _shells(result) <= _shells(source):
        return True
    from OCP.BRepCheck import BRepCheck_Analyzer

    return bool(BRepCheck_Analyzer(result).IsValid())


def _fuzzy_retry(
    kind: Literal["union", "difference", "intersection"],
    shape: Any,
    tool: Any,
    cancelled: CancelToken | None,
) -> tuple[Any, Any]:
    """Dieselbe Boolesche mit Unschärfe — oder die Absage, nie ein ungültiger Körper."""
    for fuzz in BOOLEAN_FUZZ:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        operation = boolean_builder(kind, shape, tool, tolerance=fuzz)
        operation.Build()
        if operation.IsDone() and _holds(operation.Shape(), shape):
            _log.info("boolean %s held only with fuzzy value %g", kind, fuzz)
            return operation, operation.Shape()
    raise _boolean_refused()


def _boolean_refused() -> GeometryError:
    """Der vorhandene Handlungsvorschlag für unvereinbare B-Rep-Körper."""
    return GeometryError(
        detail=BOOLEAN_REFUSED_DETAIL,
        suggestions=(CORRECT_INPUT, CANCEL),
    )


def _boolean_with_created_triangles(
    kind: Literal["difference", "union"],
    solid: Solid,
    tool: Solid,
    source_face: Any,
    *,
    cancelled: CancelToken | None,
) -> tuple[Solid, tuple[int, ...]]:
    """Ordnet eine Werkzeugfläche über die Boolesche Historie dem Ergebnis zu."""
    shape, slots, builder = _boolean_pair(
        kind, solid.shape, solid.face_slots, tool, cancelled=cancelled
    )
    result = Solid(shape, deflection=solid.deflection, face_slots=slots)
    triangles = _history_triangles(result, builder, source_face, cancelled=cancelled)
    return result, triangles


def _history_triangles(
    result: Solid, builder: Any, source_face: Any, *, cancelled: CancelToken | None
) -> tuple[int, ...]:
    """Ordnet eine Quellfläche über unveränderte, geänderte oder erzeugte Flächen zu."""
    shapes = [source_face]
    for method_name in ("Modified", "Generated"):
        method = getattr(builder, method_name, None)
        if callable(method):
            shapes.extend(listed(method(source_face)))
    return _triangles_for_shapes(result, builder, shapes, cancelled=cancelled)


def _triangles_for_shapes(
    result: Solid, builder: Any, shapes: Sequence[Any], *, cancelled: CancelToken | None
) -> tuple[int, ...]:
    """Mappt B-Rep-Flächen des Builders durch die Ergebniskopie auf Dreiecke."""
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp

    built_faces = ShapeMap()
    TopExp.MapShapes_s(builder.Shape(), TopAbs_FACE, built_faces)
    triangles: set[int] = set()
    for shape in shapes:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if shape.IsNull():
            continue
        source_faces = ShapeMap()
        TopExp.MapShapes_s(shape, TopAbs_FACE, source_faces)
        for number in range(1, source_faces.Extent() + 1):
            built_index = int(built_faces.FindIndex(source_faces.FindKey(number))) - 1
            if not 0 <= built_index < len(result._copied_faces):
                continue
            result_index = result._copied_faces[built_index]
            triangles.update(result.triangles_of_face(result_index))
    return tuple(sorted(triangles))


def radial_rounding(
    solid: Solid,
    centre: Vec3,
    radius: float,
    wanted: float,
    *,
    selected_faces: Sequence[int] | None = None,
    cancelled: CancelToken | None = None,
) -> Solid | None:
    """Versetzt einen mindestens halben Zylindermantel innerhalb seiner echten Randkurven.

    ``selected_faces`` benennt die Fläche am aktuellen Eigentümer; sonst wird
    sie wie bisher über Lage und Radius gesucht. Eine ausdrückliche Auswahl,
    die keine passende Zylinderfläche ist, löst keine Ersatzsuche aus.
    """
    result, _triangles = _radial_rounding(
        solid,
        centre,
        radius,
        wanted,
        selected_faces=selected_faces,
        cancelled=cancelled,
        collect_triangles=False,
    )
    return result


def radial_rounding_with_created_triangles(
    solid: Solid,
    centre: Vec3,
    radius: float,
    wanted: float,
    *,
    selected_faces: Sequence[int] | None = None,
    cancelled: CancelToken | None = None,
) -> tuple[Solid | None, tuple[int, ...]]:
    """Gibt den radialen Körper und den Beleg seiner neuen Zylinderfläche zurück."""
    return _radial_rounding(
        solid,
        centre,
        radius,
        wanted,
        selected_faces=selected_faces,
        cancelled=cancelled,
        collect_triangles=True,
    )


def _radial_rounding(
    solid: Solid,
    centre: Vec3,
    radius: float,
    wanted: float,
    *,
    selected_faces: Sequence[int] | None,
    cancelled: CancelToken | None,
    collect_triangles: bool,
) -> tuple[Solid | None, tuple[int, ...]]:
    """Versetzt den Mantel und ordnet ihn bei Bedarf über Boolesche Historie zu."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepLib import BRepLib
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopoDS import TopoDS

    from app.core.geom.edges import validate_radial_change

    if selected_faces is None:
        face = _cylinder_at(solid, centre, radius, cancelled=cancelled)
    else:
        indices = solid.checked_face_indices(selected_faces, cancelled=cancelled)
        if len(indices) != 1:
            raise GeometryError(
                detail=_(
                    "Wählen Sie genau eine vollständige Rundungsfläche mit dem bisherigen Radius."
                ),
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        face = solid.faces()[indices[0]]
        chosen = solid.surface(indices[0], cancelled=cancelled)
        if not isinstance(chosen, CylinderSurface) or not is_close(
            float(chosen.cylinder.Radius()), radius
        ):
            raise GeometryError(
                detail=_(
                    "Wählen Sie genau eine vollständige Rundungsfläche mit dem bisherigen Radius."
                ),
                suggestions=(CORRECT_INPUT, CANCEL),
            )
    if face is None:
        return None, ()
    surface = solid.surface(solid.face_index(face), cancelled=cancelled)
    if not isinstance(surface, CylinderSurface) or surface.turn < math.pi - EPS_GEOM:
        return None, ()
    # Linkshändige Zylindersysteme kehren die natürliche Mantelnormale um;
    # die Topologieorientierung allein bezeichnet dort die falsche Seite.
    inward = surface.inward
    actual = float(surface.cylinder.Radius())
    offset = (actual - wanted) if inward else (wanted - actual)
    try:
        private = BRepBuilderAPI_Copy(face, True, False).Shape()
        builder = BRepOffsetAPI_MakeThickSolid()
        builder.MakeThickSolidBySimple(private, offset)
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if not builder.IsDone():
            raise ValueError("Radial offset did not produce a shape")
        shape = builder.Shape()
        if shape.ShapeType() != TopAbs_SOLID or not BRepCheck_Analyzer(shape).IsValid():
            raise ValueError("Radial offset did not produce a valid solid")
        skin_shape = TopoDS.Solid(shape)
        # Die Materialseite gehört zum privaten Aufbau. Veröffentlichte Maße
        # dürfen keine negative Orientierung durch einen Absolutbetrag verdecken.
        if (
            not BRepLib.OrientClosedSolid_s(skin_shape)
            or skin_shape.IsNull()
            or not BRepCheck_Analyzer(skin_shape).IsValid()
        ):
            raise ValueError("Radial offset has no valid closed orientation")
    except OperationCancelled:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:
        raise GeometryError(
            detail=_(
                "Diese Zylinderfläche lässt sich innerhalb ihrer Ränder nicht versetzen. "
                "Wählen Sie einen kleineren Unterschied zum bisherigen Radius."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        ) from problem
    skin = Solid(skin_shape)
    tracked_faces = []
    if collect_triangles:
        for index, candidate_face in enumerate(skin.faces()):
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            candidate = skin.surface(index, cancelled=cancelled)
            if (
                isinstance(candidate, CylinderSurface)
                and is_close(float(candidate.cylinder.Radius()), wanted)
                and _same_cylinder_axis(surface, candidate)
            ):
                tracked_faces.append(candidate_face)
    volume = skin._properties("volume", cancelled=cancelled).mass
    area = skin._properties("surface", cancelled=cancelled).mass
    solid._properties("volume", cancelled=cancelled)
    subtracted = (wanted > actual) == inward
    kind: Literal["difference", "union"] = "difference" if subtracted else "union"
    if collect_triangles and len(tracked_faces) == 1:
        result, triangles = _boolean_with_created_triangles(
            kind, solid, skin, tracked_faces[0], cancelled=cancelled
        )
    else:
        result = boolean(kind, [solid, skin])
        triangles = ()
    result._properties("volume", cancelled=cancelled)
    validate_radial_change(solid, result, volume, area)
    return result, triangles


def _same_cylinder_axis(first: CylinderSurface, second: CylinderSurface) -> bool:
    """Ob zwei analytische Zylinder dieselbe unendliche Achse tragen."""
    one, two = first.cylinder.Axis(), second.cylinder.Axis()
    one_point, two_point = one.Location(), two.Location()
    one_direction, two_direction = one.Direction(), two.Direction()
    a = (float(one_direction.X()), float(one_direction.Y()), float(one_direction.Z()))
    b = (float(two_direction.X()), float(two_direction.Y()), float(two_direction.Z()))
    parallel = (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )
    if math.hypot(*parallel) > EPS_GEOM:
        return False
    delta = (
        float(two_point.X() - one_point.X()),
        float(two_point.Y() - one_point.Y()),
        float(two_point.Z() - one_point.Z()),
    )
    offset = (
        delta[1] * a[2] - delta[2] * a[1],
        delta[2] * a[0] - delta[0] * a[2],
        delta[0] * a[1] - delta[1] * a[0],
    )
    return math.hypot(*offset) <= EPS_GEOM
