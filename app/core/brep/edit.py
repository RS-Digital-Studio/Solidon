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
from typing import Any, Literal, cast

from app.core.brep.canonical import CylinderSurface
from app.core.brep.kernel import (
    DEFLECTION,
    Solid,
    boolean_builder,
    carried_face_slots,
    keep_filament_boundaries,
    require,
)
from app.core.errors import (
    CANCEL,
    CHANGE_SELECTION,
    CORRECT_INPUT,
    PROGRAMMING_ERRORS,
    GeometryError,
    InternalError,
    OperationCancelled,
)
from app.core.geom.edges import EDGE_CHOICES as SHARED_EDGE_CHOICES
from app.core.geom.edges import ChamferShape, chamfer_reaches
from app.core.geom.edges import EdgeChoice as SharedEdgeChoice
from app.core.geom.edges import choose as choose_by_place
from app.core.geom.edges import named_edges as edges_named
from app.core.geom.edges import wanted as edges_wanted
from app.core.geom.section import SectionPlane
from app.core.log import get_logger
from app.core.types import CancelToken, PlaneFrame, Point2, Transform, Vec3
from app.core.units import EPS_DISPLAY, EPS_GEOM, is_close
from app.i18n import _

_log = get_logger(__name__)

#: Welche Kanten eine Auswahl meint — **die Tabelle steht in ``geom.edges``**
#: und gilt für beide Kerne. Hier bleibt der Name, unter dem das Register und
#: die Operationen sie ansprechen; zwei Aufzählungen hießen, dass ein Kern
#: eines Tages eine sechste Art kennt und der andere nicht.
EdgeChoice = SharedEdgeChoice
EDGE_CHOICES: tuple[EdgeChoice, ...] = SHARED_EDGE_CHOICES


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
) -> list[EdgeInfo]:
    """Die Kanten dieses Aufrufs: ausdrücklich gewählte vor Schlüsseln vor Gruppe.

    ``checked`` sind die am Eingabe-Solid geprüften Indizes seines
    ``edges()``-Raums (:meth:`Solid.checked_edge_indices`, **vor** der
    Kopie); die Arbeitskopie führt sie nach. Eine ausdrückliche Auswahl
    fällt nie auf Schlüssel oder Gruppe zurück (§21.3).
    """
    if checked is None:
        return _wanted(working, choice, keys)
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
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection

    curve = BRepAdaptor_Curve(entry.edge)
    sampler = GCPnts_QuasiUniformDeflection(curve, max(deflection, EPS_GEOM))
    if not sampler.IsDone() or sampler.NbPoints() < 2:
        first = curve.Value(curve.FirstParameter())
        last = curve.Value(curve.LastParameter())
        return ((first.X(), first.Y(), first.Z()), (last.X(), last.Y(), last.Z()))
    points = (sampler.Value(index) for index in range(1, sampler.NbPoints() + 1))
    return tuple((point.X(), point.Y(), point.Z()) for point in points)


@dataclass(frozen=True, slots=True)
class LoopPiece:
    """Ein Stück vom Rand einer exakten Fläche — beschrieben über das, was es ist.

    ``line`` trägt in ``points`` Anfang und Ende; ``circle`` einen Punkt auf
    dem ganzen Kreis; ``arc`` Anfang und Ende, und der Bogen läuft **gegen den
    Uhrzeigersinn um** ``axis`` vom Anfang zum Ende; ``curve`` ist alles
    andere und trägt die abgetastete Kette. Kreis und Bogen führen dazu
    ``centre``, ``axis`` und ``radius`` aus der Kurve selbst, nicht aus
    Punkten gerechnet.
    """

    kind: Literal["line", "arc", "circle", "curve"]
    points: tuple[Vec3, ...]
    centre: Vec3 | None = None
    axis: Vec3 | None = None
    radius: float = 0.0


@dataclass(frozen=True, slots=True)
class FaceLoop:
    """Ein geschlossener Rand einer Fläche: außen einer, innen je Loch einer."""

    outer: bool
    pieces: tuple[LoopPiece, ...]


def face_loops(
    solid: Solid, face_index: int, deflection: float = DEFLECTION
) -> tuple[FaceLoop, ...]:
    """Die Ränder der Fläche ``face_index`` — Strecken, Kreise und Bögen exakt.

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
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection
    from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
    from OCP.TopAbs import TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    def spot(point: Any) -> Vec3:
        return (float(point.X()), float(point.Y()), float(point.Z()))

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
            else:
                sampler = GCPnts_QuasiUniformDeflection(curve, max(deflection, EPS_GEOM))
                if sampler.IsDone() and sampler.NbPoints() >= 2:
                    chain = tuple(
                        spot(sampler.Value(index)) for index in range(1, sampler.NbPoints() + 1)
                    )
                else:
                    chain = (start, end)
                pieces.append(LoopPiece("curve", chain))
            edges.Next()
        if pieces:
            loops.append(FaceLoop(outer=bool(wire.IsSame(outer_wire)), pieces=tuple(pieces)))
        wires.Next()
    return tuple(loops)


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


def choose(solid: Solid, choice: EdgeChoice) -> list[EdgeInfo]:
    """Die Kanten, die eine benannte Auswahl meint."""
    return choose_by_place(edges_of(solid), choice)


def _wanted(solid: Solid, choice: EdgeChoice, keys: Sequence[str]) -> list[EdgeInfo]:
    """Die Kanten, die dieser Aufruf behandelt — genannte vor Gruppe (E4).

    **Die Auswahl selbst steht in ``geom.edges``**, aus demselben Grund wie
    :func:`edge_key`: Sie fragt nur nach ``upright``, ``flat`` und der Mitte,
    und beide Kerne beantworten das gleich. Zwei Fassungen hießen, dass
    „alle senkrechten Kanten" hier bald etwas anderes bedeutet als am Netz —
    bei derselben Menüzeile und demselben Parameter.
    """
    return edges_wanted(edges_of(solid), choice, keys)


def fillet(
    solid: Solid,
    radius: float,
    choice: EdgeChoice = "all",
    keys: Sequence[str] = (),
    *,
    selected_edges: Sequence[int] | None = None,
) -> Solid:
    """Rundet die gewählten Kanten. Exakt, weil die Kante eine Kurve
    ist (§30).

    ``keys`` sind einzelne Kanten (:func:`edge_key`, E4). Sind welche genannt,
    gelten sie und nicht die Gruppe: Wer eine bestimmte Kante angibt, meint
    sie — nicht alle senkrechten dazu. ``selected_edges`` geht noch einen
    Schritt weiter: Indizes in ``solid.edges()``, am aktuellen Eigentümer
    bestimmt und ohne gerundeten Schlüssel dazwischen — der Weg, den der
    Radiuswechsel für die belegte scharfe Kante nimmt.
    """
    require()
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet

    checked = None if selected_edges is None else solid.checked_edge_indices(selected_edges)
    working = replace(solid)
    chosen = _edges_for(working, choice, keys, checked)

    _fits_the_wall(working, radius, chosen, "fillet")
    builder = BRepFilletAPI_MakeFillet(working.shape)
    for entry in chosen:
        builder.Add(radius, entry.edge)
    return _built(working, builder, "fillet", radius, len(chosen))


def chamfer(
    solid: Solid,
    distance: float,
    choice: EdgeChoice = "all",
    keys: Sequence[str] = (),
    *,
    selected_edges: Sequence[int] | None = None,
    shape: ChamferShape | None = None,
) -> Solid:
    """Bricht die gewählten Kanten im 45-Grad-Winkel — oder mit ``shape`` asymmetrisch.

    ``keys`` und ``selected_edges`` wie bei :func:`fillet`: einzelne Kanten
    haben Vorrang vor der Gruppe, eine ausdrückliche Auswahl vor beidem.

    **Zwei Abstände oder Abstand und Winkel** (P6.2): Je Kante werden die
    beiden angrenzenden Flächen an ihrer Mitte gefragt, welche die
    Bezugsfläche ist und wie weit jede zurückweicht — dieselben Zeilen wie
    am Netz (``geom.edges.chamfer_reaches``) —, und ``BRepFilletAPI`` bekommt
    beide Abstände samt der Fläche, auf der der erste gilt.
    """
    require()
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer

    checked = None if selected_edges is None else solid.checked_edge_indices(selected_edges)
    working = replace(solid)
    chosen = _edges_for(working, choice, keys, checked)

    asymmetric = shape is not None and (shape.second is not None or shape.angle is not None)
    reaches: list[tuple[Any, float, float]] = []
    if asymmetric:
        for entry in chosen:
            (first_face, first_normal), (_second_face, second_normal) = _faces_at_edge(
                working, entry
            )
            one, two = chamfer_reaches(distance, shape, first_normal, second_normal)
            reaches.append((first_face, one, two))
    widest = max((max(one, two) for _face, one, two in reaches), default=distance)
    _fits_the_wall(working, widest, chosen, "chamfer")
    builder = BRepFilletAPI_MakeChamfer(working.shape)
    for index, entry in enumerate(chosen):
        if asymmetric:
            face, one, two = reaches[index]
            builder.Add(one, two, entry.edge, face)
        else:
            builder.Add(distance, entry.edge)
    return _built(working, builder, "chamfer", distance, len(chosen))


def _faces_at_edge(solid: Solid, entry: EdgeInfo) -> list[tuple[Any, tuple[float, float, float]]]:
    """Die zwei Flächen an einer Kante mit ihrer nach außen zeigenden Normale an der Kantenmitte.

    Die Normale kommt aus der Fläche selbst (``BRepLProp_SLProps``) am
    Fußpunkt der Kantenmitte, mit der Orientierung der Fläche im Körper — an
    einer ebenen Fläche die Ebenennormale, an einer gekrümmten die an dieser
    Stelle.
    """
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    neighbours = NeighbourMap()
    TopExp.MapShapesAndAncestors_s(solid.shape, TopAbs_EDGE, TopAbs_FACE, neighbours)
    if not neighbours.Contains(entry.edge):
        raise _chamfer_sides_unknown()
    found: list[tuple[Any, tuple[float, float, float]]] = []
    for shape in neighbours.FindFromKey(entry.edge):
        face = TopoDS.Face(shape)
        if any(face.IsSame(known) for known, _normal in found):
            continue
        projector = GeomAPI_ProjectPointOnSurf(gp_Pnt(*entry.middle), BRep_Tool.Surface_s(face))
        if projector.NbPoints() < 1:
            raise _chamfer_sides_unknown()
        u, v = projector.LowerDistanceParameters()
        props = BRepLProp_SLProps(BRepAdaptor_Surface(face), u, v, 1, 1e-6)
        if not props.IsNormalDefined():
            raise _chamfer_sides_unknown()
        normal = props.Normal()
        sign = -1.0 if face.Orientation() == TopAbs_REVERSED else 1.0
        found.append((face, (sign * normal.X(), sign * normal.Y(), sign * normal.Z())))
    if len(found) != 2:
        raise _chamfer_sides_unknown()
    return found


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


def _edge_wall_faces(solid: Solid, edges: Sequence[EdgeInfo]) -> list[int]:
    """Die echten Trägerflächen der gewählten Kanten, in stabiler Flächenordnung."""
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp

    neighbours = NeighbourMap()
    TopExp.MapShapesAndAncestors_s(solid.shape, TopAbs_EDGE, TopAbs_FACE, neighbours)
    wanted = ShapeMap()
    for entry in edges:
        if not neighbours.Contains(entry.edge):
            raise _wall_not_proven()
        for face in neighbours.FindFromKey(entry.edge):
            wanted.Add(face)
    return [index for index, face in enumerate(solid.faces()) if wanted.Contains(face)]


def _thinnest_wall(solid: Solid, edges: Sequence[EdgeInfo]) -> float:
    """Die dünnste belegte Wand an den Trägerflächen dieser Kanten.

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
    """
    from app.core.geom.measure import wall_thickness
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.maps import wall_thickness_map

    try:
        mesh = as_mesh_data(solid)
        measured = wall_thickness_map(mesh).values
        if len(measured) != solid.triangle_count:
            raise _wall_not_proven()
        values: list[float] = []
        for face in _edge_wall_faces(solid, edges):
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
            values.append(min(known))
    except GeometryError:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # ohne Messung ist der native Aufruf nicht sicher
        raise _wall_not_proven() from problem
    if not values:
        raise _wall_not_proven()
    return min(values)


def _fits_the_wall(solid: Solid, size: float, edges: Sequence[EdgeInfo], kind: str) -> None:
    """Hält an, wo die Rundung dicker wäre als eine Wand ihrer Trägerflächen."""
    thinnest = _thinnest_wall(solid, edges)
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


def _built(solid: Solid, builder: Any, kind: str, size: float, edges: int) -> Solid:
    """Führt den Builder aus und macht aus seinem Scheitern einen Satz, auf
    den jemand reagieren kann.
    """
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

    if not BRepCheck_Analyzer(shape).IsValid():
        raise GeometryError(
            detail=_too_large(kind),
            suggestions=(CORRECT_INPUT, CANCEL),
            values={"size_mm": round(size, 3), "edges": edges},
        )
    outcome = solid.replacing(shape, history=builder)
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


def boolean(kind: Literal["union", "difference", "intersection"], parts: list[Solid]) -> Solid:
    """Präzise Boolesche Ops: keine Tessellation, also keine
    Tessellations-Artefakte (§30).

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
        operation = boolean_builder(kind, shape, other.shape)
        operation.Build()
        if not operation.IsDone():
            # Nicht „fehlgeschlagen" (Regel 17), und nicht die geerbten
            # Vorschläge: Mesh-Reparatur und offene Kanten gibt es für einen
            # B-Rep-Körper nicht. Der häufigste Grund ist eine Berührung
            # ohne Überlappung — und die behebt eine Bewegung, keine
            # Reparatur.
            raise GeometryError(
                detail=_(
                    "Die gewählte Bearbeitung funktioniert mit diesen Körpern in ihrer "
                    "jetzigen Lage nicht — meist berühren sie sich nur an einer Fläche "
                    "oder Kante. Verschieben Sie einen der beiden so weit, dass sich die "
                    "Körper wirklich überlappen."
                ),
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        result = operation.Shape()
        sources = [(shape, slots)]
        if kind != "difference":
            sources.append((other.shape, other.face_slots))
        slots = carried_face_slots(result, sources, history=operation)
        shape = result
    return Solid(shape, deflection=parts[0].deflection, face_slots=slots)


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


def _slot_tool(
    position: Vec3,
    direction: Vec3,
    diameter: float,
    depth: float,
    length: float,
    angle_deg: float,
    overlap: float,
) -> Solid:
    """Der vollständige Langlochumriss zum Schneiden und zum Wiederauffüllen."""
    from app.core.brep.profiles import extrude
    from app.core.geom.prepare import slot_profile, slot_travel
    from app.core.sketch.planes import frame_of

    if depth <= EPS_GEOM:
        raise ValueError("a detected bore must have a positive depth")
    span = math.sqrt(sum(float(value) ** 2 for value in direction))
    if span <= EPS_GEOM:
        raise ValueError("a bore direction must not be zero")
    unit: Vec3 = (
        float(direction[0]) / span,
        float(direction[1]) / span,
        float(direction[2]) / span,
    )
    frame = frame_of(unit, position)
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
    if depth <= EPS_GEOM:
        raise ValueError("a detected bore must have a positive depth")

    length = math.sqrt(sum(float(value) ** 2 for value in direction))
    if length <= EPS_GEOM:
        raise ValueError("a bore direction must not be zero")
    unit: Vec3 = (
        float(direction[0]) / length,
        float(direction[1]) / length,
        float(direction[2]) / length,
    )
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
    if depth <= EPS_GEOM:
        raise ValueError("a detected bore must have a positive depth")
    span = math.sqrt(sum(float(value) ** 2 for value in direction))
    if span <= EPS_GEOM:
        raise ValueError("a bore direction must not be zero")
    unit: Vec3 = (
        float(direction[0]) / span,
        float(direction[1]) / span,
        float(direction[2]) / span,
    )
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
    """
    require()
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cone

    faces = solid.faces()
    ends: list[tuple[tuple[float, float, float], float]] = []
    half_angle = 0.0
    for index in face_indices:
        if index < 0 or index >= len(faces):
            return None
        adaptor = BRepAdaptor_Surface(faces[index])
        if adaptor.GetType() != GeomAbs_Cone:
            return None
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
    """
    require()
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_Copy,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeSolid,
        BRepBuilderAPI_Sewing,
    )
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepLib import BRepLib
    from OCP.collections import HSequence_TopoDS_Shape
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL
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
            owners = {numbered.FindIndex(other) - 1 for other in neighbours.FindFromKey(edge)}
            if owners - wanted:
                rim.Append(edge)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    wires = ShapeAnalysis_FreeBounds.ConnectEdgesToWires_s(rim, EPS_GEOM, False)
    if wires.Length() not in allowed_rings:
        return None
    sewing = BRepBuilderAPI_Sewing(EPS_GEOM)
    for index in chosen:
        sewing.Add(BRepBuilderAPI_Copy(faces[index], True, False).Shape())
    for position in range(1, wires.Length() + 1):
        wire = TopoDS.Wire(wires.Value(position))
        if not wire.Closed():
            return None
        cap = BRepBuilderAPI_MakeFace(wire, True)
        if not cap.IsDone():
            return None
        sewing.Add(cap.Face())
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


def transformed(solid: Solid, matrix: Transform, *, cancelled: CancelToken | None = None) -> Solid:
    """Transformiert den exakten Körper; die Variante daneben führt Flächen mit."""
    return transformed_with_faces(solid, matrix, cancelled=cancelled)[0]


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
        if (
            solid.solid_count < 1
            or not solid.is_closed
            or not BRepCheck_Analyzer(solid.shape).IsValid()
        ):
            raise _invalid_transform(result=True)
        gram = linear.T @ linear
        squared_scale = float(np.trace(gram) / 3.0)
        similarity = bool(
            np.allclose(gram, np.eye(3) * squared_scale, atol=roundoff * squared_scale, rtol=0.0)
        )
        builder: Any
        if similarity:
            transform = gp_Trsf()
            transform.SetValues(*(float(value) for value in values[:3].flat))
            builder = BRepBuilderAPI_Transform(solid.shape, transform, False)
        else:
            general = gp_GTrsf(
                gp_Mat(*(float(value) for value in linear.flat)),
                gp_XYZ(*(float(value) for value in values[:3, 3])),
            )
            builder = BRepBuilderAPI_GTransform(solid.shape, general, True)
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
        rigid = similarity and math.isclose(determinant, 1.0, rel_tol=roundoff, abs_tol=0.0)
        if rigid and not shape.IsPartner(solid.shape):
            raise _invalid_transform(result=True)
        if not BRepCheck_Analyzer(shape).IsValid():
            raise _invalid_transform(result=True)
        result = solid.replacing(shape, history=builder, cancelled=cancelled)
        if result.solid_count != solid.solid_count or not result.is_closed:
            raise _invalid_transform(result=True)
        if not rigid:
            expected_volume = solid._properties("volume", cancelled=cancelled).mass * abs(
                determinant
            )
            if (
                expected_volume <= 0.0
                or not math.isfinite(expected_volume)
                or not math.isclose(
                    result._properties("volume", cancelled=cancelled).mass,
                    expected_volume,
                    rel_tol=2.0 * INTEGRAL_RELATIVE_ERROR,
                    abs_tol=0.0,
                )
            ):
                raise _invalid_transform(result=True)
        source_faces, target_faces = ShapeMap(), ShapeMap()
        TopExp.MapShapes_s(solid.shape, TopAbs_FACE, source_faces)
        TopExp.MapShapes_s(shape, TopAbs_FACE, target_faces)
        mapping = []
        for index in range(1, source_faces.Extent() + 1):
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            # ModifiedShape verkettet bei GTransform auch die NURBS-Konvertierung.
            # Modified liefert in OCCT 8 bei diesem Builder eine leere Liste.
            changed = builder.ModifiedShape(source_faces.FindKey(index))
            target = int(target_faces.FindIndex(changed)) - 1
            if target < 0 or target >= len(result._copied_faces):
                raise _invalid_transform(result=True)
            mapping.append(result._copied_faces[target])
        if sorted(mapping) != list(range(target_faces.Extent())):
            raise _invalid_transform(result=True)
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
                "An dieser Stelle findet der Kern keine Rundung mehr — ein Schritt "
                "davor hat den Körper verändert. Wählen Sie sie neu."
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
        for raw in neighbours.FindFromIndex(shared):
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
        for modified in builder.Modified(wall):
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
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
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
        distance = BRepExtrema_DistShapeShape(probe, face)
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if not distance.IsDone():
            return None
        away = distance.Value()
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

    radial = radial_rounding(
        solid, centre, radius, wanted, selected_faces=selected_faces, cancelled=cancelled
    )
    if radial is not None:
        return radial
    sharp, edge = _unround(solid, centre, radius, selected_faces, cancelled)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if edge is None:
        raise GeometryError(detail=NOT_BETWEEN_TWO_PLANES, suggestions=(CHANGE_SELECTION, CANCEL))
    result = fillet(sharp, wanted, selected_edges=(edge,))
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    return result


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
        return None
    surface = solid.surface(solid.face_index(face), cancelled=cancelled)
    if not isinstance(surface, CylinderSurface) or surface.turn < math.pi - EPS_GEOM:
        return None
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
    volume = skin._properties("volume", cancelled=cancelled).mass
    area = skin._properties("surface", cancelled=cancelled).mass
    solid._properties("volume", cancelled=cancelled)
    subtracted = (wanted > actual) == inward
    result = boolean("difference" if subtracted else "union", [solid, skin])
    result._properties("volume", cancelled=cancelled)
    validate_radial_change(solid, result, volume, area)
    return result
